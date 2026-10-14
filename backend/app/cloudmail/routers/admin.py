"""cloud-mail 兼容：管理员接口（用户管理 / 全部邮件 / 分析）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import models
from ...database import get_db
from ...domains import domain_of, get_master_creds
from ...mail.imap_client import ImapClient
from ...security import hash_password
from ..auth import get_cm_user
from ..envelope import CMFail, CMRoute, ok
from ..sync import (imap_creds_for_master, owner_key_for_master,
                    page_ids, resolve_ids, sync_owner)
from .account import _to_account
from .email import _fetch_items, _parse_ids

router = APIRouter(route_class=CMRoute)


def _require_admin(user: models.User):
    if not user.is_admin:
        raise CMFail("无权限", 403)


def _to_user(u: models.User, db: Session) -> dict:
    account_count = db.query(models.Mailbox).filter(
        models.Mailbox.user_id == u.id).count()
    send_count = db.query(models.CmSent).filter(
        models.CmSent.user_id == u.id).count()
    return {
        "userId": u.id,
        "email": u.username,
        "type": 0 if u.is_admin else 1,
        "status": 0,
        "createTime": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "",
        "activeTime": "",
        "sendCount": send_count,
        "receiveEmailCount": 0,
        "sendEmailCount": send_count,
        "accountCount": account_count,
        "isDel": 0,
    }


# ---------- 用户管理 ----------

@router.get("/user/list")
def user_list(num: int = 0, size: int = 20, email: str = "",
              user=Depends(get_cm_user), db: Session = Depends(get_db)):
    _require_admin(user)
    q = db.query(models.User)
    if email:
        q = q.filter(models.User.username.like(f"%{email}%"))
    total = q.count()
    rows = q.order_by(models.User.id.asc()).offset(int(num or 0)).limit(
        min(int(size or 20), 50)).all()
    return ok({"list": [_to_user(u, db) for u in rows], "total": total})


@router.post("/user/add")
def user_add(body: dict, user=Depends(get_cm_user), db: Session = Depends(get_db)):
    _require_admin(user)
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or len(password) < 6:
        raise CMFail("邮箱和密码（至少6位）必填", 400)
    if db.query(models.User).filter(models.User.username == email).first():
        raise CMFail("用户已存在", 400)
    u = models.User(username=email, password_hash=hash_password(password),
                    is_admin=bool(int(body.get("type") or 1) == 0),
                    can_send=True)
    db.add(u)
    db.commit()
    return ok({"userId": u.id})


@router.put("/user/setPwd")
def user_set_pwd(body: dict, user=Depends(get_cm_user), db: Session = Depends(get_db)):
    _require_admin(user)
    u = db.get(models.User, int(body.get("userId") or 0))
    if not u:
        raise CMFail("用户不存在", 404)
    if len(body.get("password") or "") < 6:
        raise CMFail("密码至少 6 位", 400)
    u.password_hash = hash_password(body["password"])
    db.commit()
    return ok()


@router.put("/user/setStatus")
def user_set_status(body: dict, user=Depends(get_cm_user)):
    _require_admin(user)
    return ok()


@router.put("/user/setType")
def user_set_type(body: dict, user=Depends(get_cm_user), db: Session = Depends(get_db)):
    _require_admin(user)
    u = db.get(models.User, int(body.get("userId") or 0))
    if not u:
        raise CMFail("用户不存在", 404)
    u.is_admin = int(body.get("type") or 1) == 0
    db.commit()
    return ok()


@router.delete("/user/delete")
def user_delete(userIds: str = "", user=Depends(get_cm_user),
                db: Session = Depends(get_db)):
    _require_admin(user)
    ids = [int(p) for p in (userIds or "").split(",") if p.strip().isdigit()]
    for uid in ids:
        if uid == user.id:
            raise CMFail("不能删除自己", 400)
        u = db.get(models.User, uid)
        if not u:
            continue
        db.query(models.CmSent).filter(models.CmSent.user_id == uid).delete()
        db.query(models.ApiKey).filter(models.ApiKey.user_id == uid).delete()
        for mb in db.query(models.Mailbox).filter(models.Mailbox.user_id == uid).all():
            db.query(models.CmEmailMap).filter(
                models.CmEmailMap.owner_key == f"mb:{mb.id}").delete()
            db.delete(mb)
        db.delete(u)
    db.commit()
    return ok()


@router.put("/user/resetSendCount")
def user_reset_send_count(user=Depends(get_cm_user)):
    _require_admin(user)
    return ok()


@router.put("/user/restore")
def user_restore(user=Depends(get_cm_user)):
    _require_admin(user)
    return ok()


@router.get("/user/allAccount")
def user_all_account(userId: int = 0, num: int = 0, size: int = 20,
                     user=Depends(get_cm_user), db: Session = Depends(get_db)):
    _require_admin(user)
    q = db.query(models.Mailbox).filter(models.Mailbox.user_id == int(userId or 0))
    total = q.count()
    rows = q.order_by(models.Mailbox.id.asc()).offset(int(num or 0)).limit(
        min(int(size or 20), 50)).all()
    return ok({"list": [_to_account(b) for b in rows], "total": total})


@router.delete("/user/deleteAccount")
def user_delete_account(accountId: int = 0, user=Depends(get_cm_user),
                        db: Session = Depends(get_db)):
    _require_admin(user)
    mb = db.get(models.Mailbox, int(accountId or 0))
    if not mb:
        raise CMFail("邮箱不存在", 404)
    db.query(models.CmEmailMap).filter(
        models.CmEmailMap.owner_key == f"mb:{mb.id}").delete()
    db.delete(mb)
    db.commit()
    return ok()


# ---------- 全部邮件 ----------

def _master_owners(db: Session):
    """[(owner_key, creds, master_email)]，每个配置域名一个。"""
    out = []
    for d in db.query(models.MailDomain).order_by(models.MailDomain.id.asc()).all():
        try:
            creds = imap_creds_for_master(db, d.master_email)
        except CMFail:
            continue
        out.append((owner_key_for_master(d.master_email), creds, d.master_email))
    return out


@router.get("/allEmail/list")
def all_email_list(emailId: int = 0, name: str = "", subject: str = "",
                   accountEmail: str = "", userEmail: str = "",
                   type: str = "receive", timeSort: int = 0, size: int = 10,
                   full: int = 1, user=Depends(get_cm_user),
                   db: Session = Depends(get_db)):
    _require_admin(user)
    size = min(max(int(size or 10), 1), 50)
    cursor = int(emailId or 0)
    time_sort = int(timeSort or 0)

    if type == "send":
        q = db.query(models.CmSent)
        total = q.count()
        if time_sort:
            q = q.filter(models.CmSent.id > cursor).order_by(models.CmSent.id.asc())
        else:
            if cursor:
                q = q.filter(models.CmSent.id < cursor)
            q = q.order_by(models.CmSent.id.desc())
        rows = q.limit(size).all()
        items = []
        for r in rows:
            mb = db.get(models.Mailbox, r.mailbox_id)
            items.append({
                "emailId": r.id, "accountId": r.mailbox_id,
                "sendEmail": mb.email if mb else "", "name": "",
                "subject": r.subject or "(无主题)", "code": "",
                "recipient": r.to_addrs, "toEmail": r.to_addrs, "toName": "",
                "type": 1, "status": 1, "message": "", "unread": 1,
                "createTime": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
                "isDel": 0, "content": r.body_html or "",
                "text": (r.body_text or "")[:300],
                "listText": (r.body_text or "").replace("\n", " ")[:300],
                "isStar": 0, "attList": [],
            })
        latest_id = max([r.id for r in rows], default=0)
        return ok({"list": items, "total": total,
                   "latestEmail": {"emailId": latest_id, "accountId": 0,
                                   "userId": user.id}})

    if type in ("delete", "noone"):
        return ok({"list": [], "total": 0,
                   "latestEmail": {"emailId": 0, "accountId": 0, "userId": user.id}})

    owners = _master_owners(db)
    keys = [o[0] for o in owners]
    for key, creds, _m in owners:
        sync_owner(db, key, creds)
    ids, total = page_ids(db, keys, cursor, size, time_sort)
    rows = db.query(models.CmEmailMap).filter(
        models.CmEmailMap.id.in_(ids)).all() if ids else []
    by_id = {r.id: (r.id, r.owner_key, r.imap_uid) for r in rows}
    pairs = [by_id[i] for i in ids if i in by_id]
    key2 = {o[0]: (o[1], o[2]) for o in owners}
    items = []
    for key, plist in _group_pairs(pairs):
        creds, master_email = key2[key]
        items += _fetch_items(creds, plist, master_email)
    items.sort(key=lambda x: x["emailId"], reverse=not time_sort)
    latest_id = max(ids, default=0)
    return ok({"list": items, "total": total,
               "latestEmail": {"emailId": latest_id, "accountId": 0,
                               "userId": user.id}})


def _group_pairs(pairs):
    by_owner: dict[str, list] = {}
    for p in pairs:
        by_owner.setdefault(p[1], []).append(p)
    return by_owner.items()


@router.get("/allEmail/latest")
def all_email_latest(emailId: int = 0, user=Depends(get_cm_user),
                     db: Session = Depends(get_db)):
    _require_admin(user)
    owners = _master_owners(db)
    keys = [o[0] for o in owners]
    for key, creds, _m in owners:
        sync_owner(db, key, creds)
    ids, _ = page_ids(db, keys, int(emailId or 0), 20, 1)
    rows = db.query(models.CmEmailMap).filter(
        models.CmEmailMap.id.in_(ids)).all() if ids else []
    by_id = {r.id: (r.id, r.owner_key, r.imap_uid) for r in rows}
    pairs = [by_id[i] for i in ids if i in by_id]
    key2 = {o[0]: (o[1], o[2]) for o in owners}
    items = []
    for key, plist in _group_pairs(pairs):
        creds, master_email = key2[key]
        items += _fetch_items(creds, plist, master_email)
    items.sort(key=lambda x: x["emailId"], reverse=True)
    return ok(items)


@router.delete("/allEmail/delete")
def all_email_delete(emailIds: str = "", user=Depends(get_cm_user),
                      db: Session = Depends(get_db)):
    _require_admin(user)
    ids = _parse_ids(emailIds)
    if not ids:
        return ok()
    owners = _master_owners(db)
    keys = [o[0] for o in owners]
    pairs = resolve_ids(db, keys, ids)
    key2 = {o[0]: o[1] for o in owners}
    by_owner: dict[str, list[str]] = {}
    for key, uid in pairs:
        by_owner.setdefault(key, []).append(uid)
    for key, uids in by_owner.items():
        host, port, iuser, ipw, _rec = key2[key]
        try:
            with ImapClient(host, port, iuser, ipw) as client:
                client.delete_uids(uids)
        except Exception as e:  # noqa: BLE001
            raise CMFail(f"删除失败：{e}")
        db.query(models.CmEmailMap).filter(
            models.CmEmailMap.owner_key == key,
            models.CmEmailMap.imap_uid.in_(uids)).delete(synchronize_session=False)
    db.commit()
    return ok()


@router.delete("/allEmail/batchDelete")
def all_email_batch_delete(user=Depends(get_cm_user)):
    _require_admin(user)
    raise CMFail("暂不支持按条件批量清理", 400)


# ---------- 分析（简化版） ----------

@router.get("/analysis/echarts")
def analysis_echarts(timeZone: str = "Asia/Shanghai",
                     user=Depends(get_cm_user), db: Session = Depends(get_db)):
    _require_admin(user)
    user_total = db.query(models.User).count()
    account_total = db.query(models.Mailbox).count()
    receive_total = db.query(models.CmEmailMap).count()
    send_total = db.query(models.CmSent).count()
    return ok({
        "numberCount": {
            "receiveTotal": receive_total, "sendTotal": send_total,
            "accountTotal": account_total, "userTotal": user_total,
            "normalReceiveTotal": receive_total, "delReceiveTotal": 0,
            "normalSendTotal": send_total, "delSendTotal": 0,
            "normalAccountTotal": account_total, "delAccountTotal": 0,
            "normalUserTotal": user_total, "delUserTotal": 0,
        },
        "userDayCount": [],
        "receiveRatio": {"nameRatio": []},
        "emailDayCount": {"receiveDayCount": [], "sendDayCount": []},
        "daySendTotal": 0,
    })
