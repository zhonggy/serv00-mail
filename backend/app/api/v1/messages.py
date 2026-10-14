"""读邮件：列表 / 单封。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ... import models, schemas
from ...config import get_settings
from ...database import get_db
from ...domains import domain_of, get_master_creds
from ...mail.imap_client import ImapClient
from ...security import decrypt_credential
from ..deps import get_caller, get_mailbox_or_404, require_scope

settings = get_settings()
router = APIRouter()


def _imap_creds(db, mb: models.Mailbox) -> tuple[str, int, str, str, str | None]:
    """返回 (host, port, 用户名, 密码, 收件人过滤)。别名走该域名主邮箱+按收件人过滤。"""
    if mb.type == "account":
        if not mb.password_enc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "该邮箱凭据缺失")
        return (settings.serv00_imap_host, settings.serv00_imap_port,
                mb.email, decrypt_credential(mb.password_enc), None)
    creds = get_master_creds(db, domain_of(mb.email))
    if not creds:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "该域名的主邮箱未配置，请在管理后台 → 域名管理添加")
    imap_user, imap_pass = creds
    return (settings.serv00_imap_host, settings.serv00_imap_port,
            imap_user, imap_pass, mb.email)


def _to_out(parsed: dict, detail: bool = False):
    base = dict(uid=parsed["uid"], subject=parsed["subject"], **{"from": parsed["from"]},
                to=parsed["to"], date=parsed["date"], snippet=parsed["snippet"])
    if detail:
        base.update(body_text=parsed["body_text"], body_html=parsed.get("body_html"))
        return schemas.MessageDetailOut(**base)
    return schemas.MessageOut(**base)


@router.get("/{mailbox_id}/messages", response_model=list[schemas.MessageOut], summary="邮件列表")
def list_messages(mailbox_id: int, limit: int = Query(20, le=100),
                  caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = caller
    require_scope(scopes, "mail:read")
    mb = get_mailbox_or_404(db, mailbox_id, user, scopes)
    host, port, imap_user, imap_pass, recipient = _imap_creds(db, mb)
    try:
        with ImapClient(host, port, imap_user, imap_pass) as client:
            parsed = client.list_messages(limit=limit, recipient=recipient)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"IMAP 读取失败：{e}")
    return [_to_out(p) for p in parsed]


@router.get("/{mailbox_id}/messages/{uid}", response_model=schemas.MessageDetailOut, summary="邮件正文详情")
def read_message(mailbox_id: int, uid: str,
                 caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = caller
    require_scope(scopes, "mail:read")
    mb = get_mailbox_or_404(db, mailbox_id, user, scopes)
    host, port, imap_user, imap_pass, recipient = _imap_creds(db, mb)
    try:
        with ImapClient(host, port, imap_user, imap_pass) as client:
            parsed = client.fetch_message(uid, recipient=recipient)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"IMAP 读取失败：{e}")
    if not parsed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邮件不存在")
    return _to_out(parsed, detail=True)
