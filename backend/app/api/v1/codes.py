"""取验证码：轮询这一个接口即可。"""
import datetime
import email.utils

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ... import schemas
from ...config import get_settings
from ...database import get_db
from ...mail.code_extractor import extract_from_message
from ...mail.imap_client import ImapClient
from ..deps import get_caller, get_mailbox_or_404, require_scope
from .messages import _imap_creds

settings = get_settings()
router = APIRouter()


def _within_minutes(date_str: str, minutes: int) -> bool:
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
    except (TypeError, ValueError):
        return True  # 解析不出时间就不过滤
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    delta = datetime.datetime.now(datetime.timezone.utc) - dt
    return delta.total_seconds() <= minutes * 60


@router.get("/{mailbox_id}/codes", response_model=schemas.CodesOut, summary="提取验证码")
def get_codes(mailbox_id: int,
              since_minutes: int = Query(10, le=120),
              limit: int = Query(10, le=30),
              caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = caller
    require_scope(scopes, "mail:read")
    mb = get_mailbox_or_404(db, mailbox_id, user, scopes)
    host, port, imap_user, imap_pass, recipient = _imap_creds(db, mb)
    try:
        with ImapClient(host, port, imap_user, imap_pass) as client:
            parsed_list = client.latest_messages(limit=limit, recipient=recipient)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"IMAP 读取失败：{e}")

    codes = []
    for parsed in parsed_list:
        if not _within_minutes(parsed.get("date", ""), since_minutes):
            continue
        for c in extract_from_message(parsed):
            codes.append(schemas.CodeOut(**{"from": c["from"], "code": c["code"],
                                            "context": c["context"], "subject": c["subject"],
                                            "date": c["date"]}))
    return schemas.CodesOut(email=mb.email, codes=codes)
