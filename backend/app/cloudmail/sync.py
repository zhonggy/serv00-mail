"""cloud-mail 兼容层：IMAP 同步与 emailId 映射。

cloud-mail 前端用全局自增整数 emailId 做分页/已读/删除/长轮询，
这里用 cm_email_map 表把 (owner_key, imap_uid) 映射成自增 id。
owner_key：
  - "mb:{mailbox_id}"：某个邮箱视角（收件按该邮箱过滤）
  - "master:{email}"：某域名主邮箱视角（管理员“全部邮件”）
"""
from sqlalchemy.orm import Session

from .. import models
from ..config import get_settings
from ..domains import domain_of, get_master_creds
from ..mail.imap_client import ImapClient
from ..security import decrypt_credential
from .envelope import CMFail

settings = get_settings()


def owner_key_for_mailbox(mb: models.Mailbox) -> str:
    return f"mb:{mb.id}"


def owner_key_for_master(master_email: str) -> str:
    return f"master:{master_email.strip().lower()}"


def imap_creds_for_mailbox(db: Session, mb: models.Mailbox):
    """返回 (host, port, 用户名, 密码, 收件人过滤)。"""
    if mb.type == "account":
        if not mb.password_enc:
            raise CMFail("该邮箱凭据缺失")
        return (settings.serv00_imap_host, settings.serv00_imap_port,
                mb.email, decrypt_credential(mb.password_enc), None)
    creds = get_master_creds(db, domain_of(mb.email))
    if not creds:
        raise CMFail(f"域名 {domain_of(mb.email)} 的主邮箱未配置")
    user, pw = creds
    return settings.serv00_imap_host, settings.serv00_imap_port, user, pw, mb.email


def imap_creds_for_master(db: Session, master_email: str):
    """管理员全部邮件：直接读某主邮箱（不过滤收件人）。"""
    domain = domain_of(master_email)
    creds = get_master_creds(db, domain)
    if not creds:
        raise CMFail(f"域名 {domain} 的主邮箱未配置")
    user, pw = creds
    return settings.serv00_imap_host, settings.serv00_imap_port, user, pw, None


def _recipient_match(parsed: dict, recipient: str | None) -> bool:
    if not recipient:
        return True
    return recipient.lower() in (parsed.get("to") or "").lower()


SYNC_WINDOW = 500  # 每次同步最多处理最近多少封


def sync_owner(db: Session, owner_key: str, creds) -> dict[str, int]:
    """IMAP 增量同步：把新 uid 记入映射表。返回 {imap_uid: emailId}。

    creds = (host, port, user, pw, recipient)。recipient 非空时（别名），
    只映射收件人匹配的 uid，避免共享主邮箱串信。
    """
    host, port, user, pw, recipient = creds
    try:
        with ImapClient(host, port, user, pw) as client:
            all_uids = client.list_uids()[-SYNC_WINDOW:]
            if not all_uids:
                return {}
            mapped = {
                r.imap_uid: r.id
                for r in db.query(models.CmEmailMap)
                .filter(models.CmEmailMap.owner_key == owner_key).all()
            }
            new_uids = [u for u in all_uids if u not in mapped]
            if recipient and new_uids:
                new_uids = client.match_uids_by_recipient(new_uids, recipient)
            if new_uids:
                db.bulk_save_objects([
                    models.CmEmailMap(owner_key=owner_key, imap_uid=u)
                    for u in new_uids
                ])
                db.commit()
                for r in db.query(models.CmEmailMap).filter(
                        models.CmEmailMap.owner_key == owner_key,
                        models.CmEmailMap.imap_uid.in_(new_uids)).all():
                    mapped[r.imap_uid] = r.id
            return mapped
    except CMFail:
        raise
    except Exception as e:  # noqa: BLE001
        raise CMFail(f"IMAP 同步失败：{e}")


def resolve_ids(db: Session, owner_keys: list[str], email_ids: list[int]) -> list[tuple[str, str]]:
    """把前端的 emailId 列表解析回 [(owner_key, imap_uid)]。"""
    if not email_ids:
        return []
    rows = db.query(models.CmEmailMap).filter(
        models.CmEmailMap.id.in_(email_ids),
        models.CmEmailMap.owner_key.in_(owner_keys)).all()
    return [(r.owner_key, r.imap_uid) for r in rows]


def page_ids(db: Session, owner_keys: list[str], cursor: int, size: int,
             time_sort: int) -> tuple[list[int], int]:
    """按 synthetic id 分页。time_sort=1 正序（取比 cursor 大的），否则倒序。返回 (ids, total)。"""
    if isinstance(owner_keys, str):
        owner_keys = [owner_keys]
    q = db.query(models.CmEmailMap).filter(models.CmEmailMap.owner_key.in_(owner_keys))
    total = q.count()
    if time_sort:
        q = q.filter(models.CmEmailMap.id > cursor).order_by(models.CmEmailMap.id.asc())
    else:
        if cursor:
            q = q.filter(models.CmEmailMap.id < cursor)
        q = q.order_by(models.CmEmailMap.id.desc())
    rows = q.limit(size).all()
    return [r.id for r in rows], total
