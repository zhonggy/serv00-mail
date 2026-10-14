"""cloud-mail 兼容：邮件收发。

收件走 serv00 IMAP（按邮箱过滤），发件走 serv00 SMTP。
emailId 是 cm_email_map 表的自增 id（见 sync.py）。
"""
import email.utils

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import models
from ...api.deps import get_setting
from ...config import get_settings
from ...database import get_db
from ...domains import domain_of, get_master_creds
from ...mail.code_extractor import extract_from_message
from ...mail.imap_client import ImapClient
from ...mail.smtp_client import send_mail
from ...security import decrypt_credential
from ..auth import get_cm_user
from ..envelope import CMFail, CMRoute, ok
from ..sync import (imap_creds_for_mailbox, owner_key_for_mailbox,
                    page_ids, resolve_ids, sync_owner)

settings = get_settings()
router = APIRouter(route_class=CMRoute)


# ---------- 小工具 ----------

def _text_to_html(text: str) -> str:
    """纯文本转简单 HTML：前端内容页只渲染 content（v-if），纯文本邮件也要有内容。"""
    import html as _html
    return '<div style="white-space:pre-wrap">' + _html.escape(text or "") + "</div>"


def _owned_mailbox(db: Session, user: models.User, account_id) -> models.Mailbox:
    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        raise CMFail("邮箱不存在", 404)
    mb = db.query(models.Mailbox).filter(
        models.Mailbox.id == account_id,
        models.Mailbox.user_id == user.id).first()
    if not mb:
        raise CMFail("邮箱不存在", 404)
    return mb


def _ctx_for(db: Session, user: models.User, account_id):
    mb = _owned_mailbox(db, user, account_id)
    creds = imap_creds_for_mailbox(db, mb)
    return mb, owner_key_for_mailbox(mb), creds


def _item_from_parsed(parsed: dict, email_id: int, mailbox_email: str,
                      seen: bool, account_id: int = 0) -> dict:
    name, addr = email.utils.parseaddr(parsed.get("from") or "")
    codes = extract_from_message(parsed, max_codes=1)
    body_text = parsed.get("body_text") or ""
    body_html = parsed.get("body_html") or ""
    return {
        "emailId": email_id,
        "accountId": account_id,
        "sendEmail": addr,
        "name": name or addr,
        "subject": parsed.get("subject") or "(无主题)",
        "code": codes[0]["code"] if codes else "",
        "recipient": parsed.get("to") or "",
        "toEmail": mailbox_email,
        "toName": "",
        "type": 0,
        "status": 0,
        "message": "",
        # 它们的 unread：0=未读，1=已读
        "unread": 1 if seen else 0,
        "createTime": parsed.get("date") or "",
        "isDel": 0,
        "content": body_html or _text_to_html(body_text),
        "text": body_text[:300],
        "listText": (parsed.get("snippet") or body_text[:200]).replace("\n", " ")[:300],
        "isStar": 0,
        "attList": [],
    }


def _fetch_items(creds, pairs: list[tuple[int, str, str]],
                 mailbox_email: str, account_id: int = 0) -> list[dict]:
    """pairs = [(emailId, owner_key, imap_uid)]，按传入顺序返回条目。"""
    if not pairs:
        return []
    host, port, iuser, ipw, recipient = creds
    uids = [p[2] for p in pairs]
    try:
        with ImapClient(host, port, iuser, ipw) as client:
            parsed_map, flags = {}, {}
            for uid in uids:
                p = client.fetch_message(uid, recipient=recipient)
                if p:
                    parsed_map[uid] = p
            try:
                flags = client.get_flags(uids)
            except Exception:  # noqa: BLE001
                flags = {}
    except Exception as e:  # noqa: BLE001
        raise CMFail(f"读取邮件失败：{e}")
    items = []
    for email_id, _ok, uid in pairs:
        p = parsed_map.get(uid)
        if not p:
            continue
        items.append(_item_from_parsed(p, email_id, mailbox_email,
                                       bool(flags.get(uid)), account_id))
    return items


def _pairs_for_ids(db: Session, owner_keys: list[str],
                   ids: list[int]) -> list[tuple[int, str, str]]:
    rows = db.query(models.CmEmailMap).filter(
        models.CmEmailMap.id.in_(ids),
        models.CmEmailMap.owner_key.in_(owner_keys)).all()
    by_id = {r.id: (r.id, r.owner_key, r.imap_uid) for r in rows}
    return [by_id[i] for i in ids if i in by_id]


# ---------- 列表 / 长轮询 ----------

@router.get("/email/list")
def email_list(accountId: int = 0, allReceive: int = 0, emailId: int = 0,
               timeSort: int = 0, size: int = 10, type: int = 0, full: int = 1,
               user=Depends(get_cm_user), db: Session = Depends(get_db)):
    size = min(max(int(size or 10), 1), 50)
    cursor = int(emailId or 0)
    time_sort = int(timeSort or 0)

    if int(type or 0) == 1:
        return ok(_sent_list(db, user, cursor, size, time_sort))

    if int(allReceive or 0):
        boxes = db.query(models.Mailbox).filter(
            models.Mailbox.user_id == user.id).all()
        owners = []  # (owner_key, creds, mailbox)
        for mb in boxes:
            try:
                creds = imap_creds_for_mailbox(db, mb)
            except CMFail:
                continue
            owners.append((owner_key_for_mailbox(mb), creds, mb))
        if not owners:
            return ok({"list": [], "total": 0,
                       "latestEmail": {"emailId": 0, "accountId": 0, "userId": user.id}})
        keys = [o[0] for o in owners]
        for key, creds, _mb in owners:
            sync_owner(db, key, creds)
        ids, total = page_ids(db, keys, cursor, size, time_sort)
        pairs = _pairs_for_ids(db, keys, ids)
        # 多邮箱合并：按每个 owner 的 creds 分批取
        by_owner: dict[str, list] = {}
        for p in pairs:
            by_owner.setdefault(p[1], []).append(p)
        key2mb = {o[0]: (o[1], o[2]) for o in owners}
        items = []
        for key, plist in by_owner.items():
            creds, mb = key2mb[key]
            items += _fetch_items(creds, plist, mb.email, mb.id)
        items.sort(key=lambda x: x["emailId"], reverse=not time_sort)
        latest_id = max([p[0] for p in pairs], default=0)
        return ok({"list": items, "total": total,
                   "latestEmail": {"emailId": latest_id, "accountId": int(accountId or 0),
                                   "userId": user.id}})

    mb, key, creds = _ctx_for(db, user, accountId)
    sync_owner(db, key, creds)
    ids, total = page_ids(db, [key], cursor, size, time_sort)
    pairs = _pairs_for_ids(db, [key], ids)
    items = _fetch_items(creds, pairs, mb.email, mb.id)
    latest_id = max(ids, default=0)
    return ok({"list": items, "total": total,
               "latestEmail": {"emailId": latest_id, "accountId": mb.id,
                               "userId": user.id}})


@router.get("/email/latest")
def email_latest(emailId: int = 0, accountId: int = 0, allReceive: int = 0,
                 user=Depends(get_cm_user), db: Session = Depends(get_db)):
    cursor = int(emailId or 0)
    if int(allReceive or 0):
        boxes = db.query(models.Mailbox).filter(
            models.Mailbox.user_id == user.id).all()
        owners = []
        for mb in boxes:
            try:
                owners.append((owner_key_for_mailbox(mb),
                               imap_creds_for_mailbox(db, mb), mb))
            except CMFail:
                continue
        keys = [o[0] for o in owners]
        for key, creds, _mb in owners:
            sync_owner(db, key, creds)
        ids, _ = page_ids(db, keys, cursor, 20, 1)
        pairs = _pairs_for_ids(db, keys, ids)
        key2mb = {o[0]: (o[1], o[2]) for o in owners}
        items = []
        for key, plist in _group(pairs):
            creds, mb = key2mb[key]
            items += _fetch_items(creds, plist, mb.email, mb.id)
        items.sort(key=lambda x: x["emailId"], reverse=True)
        return ok(items)
    mb, key, creds = _ctx_for(db, user, accountId)
    sync_owner(db, key, creds)
    ids, _ = page_ids(db, [key], cursor, 20, 1)
    pairs = _pairs_for_ids(db, [key], ids)
    return ok(_fetch_items(creds, pairs, mb.email, mb.id))


def _group(pairs):
    by_owner: dict[str, list] = {}
    for p in pairs:
        by_owner.setdefault(p[1], []).append(p)
    return by_owner.items()


def _sent_list(db: Session, user: models.User, cursor: int, size: int,
               time_sort: int) -> dict:
    q = db.query(models.CmSent).filter(models.CmSent.user_id == user.id)
    total = q.count()
    if time_sort:
        q = q.filter(models.CmSent.id > cursor).order_by(models.CmSent.id.asc())
    else:
        if cursor:
            q = q.filter(models.CmSent.id < cursor)
        q = q.order_by(models.CmSent.id.desc())
    rows = q.limit(size).all()
    items = [{
        "emailId": r.id,
        "accountId": r.mailbox_id,
        "sendEmail": "",
        "name": "",
        "subject": r.subject or "(无主题)",
        "code": "",
        "recipient": r.to_addrs,
        "toEmail": r.to_addrs,
        "toName": "",
        "type": 1,
        "status": 1,
        "message": "",
        "unread": 1,
        "createTime": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
        "isDel": 0,
        "content": r.body_html or "",
        "text": (r.body_text or "")[:300],
        "listText": (r.body_text or "").replace("\n", " ")[:300],
        "isStar": 0,
        "attList": [],
    } for r in rows]
    latest_id = max([r.id for r in rows], default=0)
    return {"list": items, "total": total,
            "latestEmail": {"emailId": latest_id, "accountId": 0, "userId": user.id}}


# ---------- 已读 / 删除 ----------

def _parse_ids(raw: str) -> list[int]:
    out = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


def _owned_owner_keys(db: Session, user: models.User) -> list[str]:
    return [owner_key_for_mailbox(mb) for mb in
            db.query(models.Mailbox).filter(models.Mailbox.user_id == user.id).all()]


def _creds_for_owner(db: Session, user: models.User, owner_key: str):
    if owner_key.startswith("mb:"):
        mb = db.query(models.Mailbox).filter(
            models.Mailbox.id == int(owner_key[3:]),
            models.Mailbox.user_id == user.id).first()
        if not mb:
            raise CMFail("邮箱不存在", 404)
        return imap_creds_for_mailbox(db, mb), mb.email
    raise CMFail("无权限", 403)


@router.put("/email/read")
def email_read(body: dict, user=Depends(get_cm_user),
               db: Session = Depends(get_db)):
    ids = body.get("emailIds") or []
    if isinstance(ids, str):
        ids = _parse_ids(ids)
    ids = [int(i) for i in ids if str(i).isdigit()]
    if not ids:
        return ok()
    keys = _owned_owner_keys(db, user)
    pairs = resolve_ids(db, keys, ids)
    by_owner: dict[str, list[str]] = {}
    for key, uid in pairs:
        by_owner.setdefault(key, []).append(uid)
    for key, uids in by_owner.items():
        creds, _mail = _creds_for_owner(db, user, key)
        host, port, iuser, ipw, _rec = creds
        try:
            with ImapClient(host, port, iuser, ipw) as client:
                client.set_seen(uids, True)
        except Exception as e:  # noqa: BLE001
            raise CMFail(f"标记已读失败：{e}")
    return ok()


@router.delete("/email/delete")
def email_delete(emailIds: str = "", user=Depends(get_cm_user),
                 db: Session = Depends(get_db)):
    ids = _parse_ids(emailIds)
    if not ids:
        return ok()
    keys = _owned_owner_keys(db, user)
    pairs = resolve_ids(db, keys, ids)
    by_owner: dict[str, list[str]] = {}
    for key, uid in pairs:
        by_owner.setdefault(key, []).append(uid)
    for key, uids in by_owner.items():
        creds, _mail = _creds_for_owner(db, user, key)
        host, port, iuser, ipw, _rec = creds
        try:
            with ImapClient(host, port, iuser, ipw) as client:
                client.delete_uids(uids)
        except Exception as e:  # noqa: BLE001
            raise CMFail(f"删除失败：{e}")
        # 映射表里清掉已删的
        db.query(models.CmEmailMap).filter(
            models.CmEmailMap.owner_key == key,
            models.CmEmailMap.imap_uid.in_(uids)).delete(synchronize_session=False)
    db.commit()
    return ok()


# ---------- 发信 ----------

@router.post("/email/send")
def email_send(body: dict, user=Depends(get_cm_user),
               db: Session = Depends(get_db)):
    if get_setting(db, "allow_send", str(settings.default_allow_send)).lower() != "true":
        raise CMFail("管理员已关闭发信功能", 403)
    if not user.can_send:
        raise CMFail("你的账号被禁止发信", 403)

    mb = _owned_mailbox(db, user, body.get("accountId"))
    receive = body.get("receiveEmail") or []
    if isinstance(receive, str):
        receive = [receive]
    receive = [r.strip() for r in receive if r and "@" in r]
    if not receive:
        raise CMFail("请填写收件人", 400)
    if body.get("attachments"):
        raise CMFail("暂不支持附件", 400)

    subject = (body.get("subject") or "").strip() or "(无主题)"
    content = body.get("content") or ""
    text = body.get("text") or ""
    html = bool(content)
    mail_body = content if html else text

    if mb.type == "account":
        smtp_user = mb.email
        smtp_pass = decrypt_credential(mb.password_enc or "")
        from_addr = mb.email
    else:
        creds = get_master_creds(db, domain_of(mb.email))
        if not creds:
            raise CMFail(f"域名 {domain_of(mb.email)} 的主邮箱未配置", 500)
        smtp_user, smtp_pass = creds
        from_addr = mb.email

    from_name = (body.get("name") or "").strip()
    try:
        send_mail(
            host=settings.serv00_smtp_host, port=settings.serv00_smtp_port,
            username=smtp_user, password=smtp_pass,
            from_addr=from_addr, to_addrs=receive,
            subject=subject, body=mail_body, html=html,
            starttls=settings.serv00_smtp_starttls, from_name=from_name,
        )
    except Exception as e:  # noqa: BLE001
        raise CMFail(f"发信失败：{e}", 502)

    sent = models.CmSent(user_id=user.id, mailbox_id=mb.id,
                         to_addrs=",".join(receive), subject=subject,
                         body_text=text, body_html=content or None)
    db.add(sent)
    db.commit()
    return ok({"emailId": sent.id})
