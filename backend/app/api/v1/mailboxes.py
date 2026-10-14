"""邮箱的创建 / 列表 / 删除 / 发信。"""
import datetime
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ... import models, schemas
from ...config import get_settings
from ...database import get_db
from ...domains import domain_of, get_default_domain, get_domain_row, get_master_creds
from ...mail.smtp_client import send_mail
from ...provision.alias import AliasProvisioner
from ...provision.base import ProvisionResult
from ...provision.panel import PanelError, PanelProvisioner
from ...security import decrypt_credential, encrypt_credential
from ..deps import get_caller, get_mailbox_or_404, get_setting, login_mailbox_id, require_scope

settings = get_settings()
router = APIRouter()

PREFIX_RE = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")


def _random_prefix() -> str:
    return "tmp-" + secrets.token_hex(4)


@router.get("", response_model=list[schemas.MailboxOut], summary="邮箱列表（邮箱登录只返回自己的）")
def list_mailboxes(caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = caller
    q = db.query(models.Mailbox).filter(models.Mailbox.user_id == user.id)
    # 邮箱登录：只能看到登录时用的那个邮箱
    lb = login_mailbox_id(scopes)
    if lb:
        q = q.filter(models.Mailbox.id == lb)
    boxes = q.all()
    return [schemas.MailboxOut(id=b.id, type=b.type, email=b.email,
                               has_password=bool(b.password_enc),
                               created_at=b.created_at)
            for b in boxes]


@router.post("", response_model=schemas.MailboxOut, status_code=status.HTTP_201_CREATED, summary="创建邮箱（独立邮箱/别名）")
def create_mailbox(data: schemas.MailboxCreateIn,
                   caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = caller
    require_scope(scopes, "mailbox:write")

    # 频率限制：每小时每用户最多建 N 个
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    count = db.query(models.Mailbox).filter(
        models.Mailbox.user_id == user.id, models.Mailbox.created_at >= since).count()
    if count >= settings.mailbox_create_limit_per_hour:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "建邮箱太频繁，稍后再试")

    prefix = data.prefix or _random_prefix()
    if not PREFIX_RE.match(prefix):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "prefix 只允许字母数字 . _ -")
    domain = (data.domain or get_default_domain(db)).strip().lower()
    if not get_domain_row(db, domain):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"域名 {domain} 未配置，请先在管理后台 → 域名管理添加该域名")
    email_addr = f"{prefix}@{domain}"
    if db.query(models.Mailbox).filter(models.Mailbox.email == email_addr).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已存在，换个 prefix")

    provisioner = PanelProvisioner() if data.type == "account" else AliasProvisioner()
    try:
        result: ProvisionResult = provisioner.create(domain, prefix)
    except PanelError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"serv00 面板调用失败：{e}")
    except Exception as e:  # noqa: BLE001
        # 面板调用中的非预期异常（如网络错误、页面解析失败）也转为 502，避免直接 500
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"serv00 面板调用异常：{type(e).__name__}")

    password_enc = encrypt_credential(result.password) if result.password else None
    if data.type == "alias" and data.password:
        # 别名登录密码：只用于登录本项目，不能登录 webmail/邮件客户端
        password_enc = encrypt_credential(data.password)
    mb = models.Mailbox(user_id=user.id, type=data.type, email=result.email,
                        password_enc=password_enc)
    db.add(mb)
    db.commit()
    db.refresh(mb)
    return schemas.MailboxOut(id=mb.id, type=mb.type, email=mb.email,
                              password=result.password,
                              has_password=bool(mb.password_enc),
                              created_at=mb.created_at)


@router.patch("/{mailbox_id}/password", summary="设置/重设别名登录密码")
def set_mailbox_password(mailbox_id: int, data: schemas.MailboxPasswordIn,
                         caller=Depends(get_caller), db: Session = Depends(get_db)):
    """设置/重设别名的登录密码（只用于登录本项目）。独立邮箱的密码由 serv00 管理，不可在此修改。"""
    user, scopes = caller
    require_scope(scopes, "mailbox:write")
    mb = get_mailbox_or_404(db, mailbox_id, user, scopes)
    if mb.type != "alias":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "独立邮箱的密码由 serv00 管理，请去面板修改")
    mb.password_enc = encrypt_credential(data.password)
    db.commit()
    return {"ok": True}


@router.delete("/{mailbox_id}", summary="删除邮箱")
def delete_mailbox(mailbox_id: int, caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = caller
    require_scope(scopes, "mailbox:write")
    mb = get_mailbox_or_404(db, mailbox_id, user, scopes)
    if mb.type == "account":
        try:
            PanelProvisioner().delete(mb.email)
        except Exception as e:  # noqa: BLE001
            # 面板删除失败也继续删本地记录，避免僵尸数据；日志里会留下报错
            # （2026-10-12 实测：假域名导致 _get_csrf 的 raise_for_status 抛
            #  requests.HTTPError，若只 catch PanelError 会逃逸成 500）
            print(f"[warn] 面板删除邮箱失败（已删本地记录）：{type(e).__name__}: {e}")
    # 先清兼容层关联数据，避免外键冲突
    db.query(models.CmSent).filter(models.CmSent.mailbox_id == mailbox_id).delete()
    db.query(models.CmEmailMap).filter(
        models.CmEmailMap.owner_key == f"mb:{mailbox_id}").delete()
    db.delete(mb)
    db.commit()
    return {"ok": True}


@router.post("/{mailbox_id}/send", summary="发信")
def send_from_mailbox(mailbox_id: int, data: schemas.SendIn,
                      caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = caller
    require_scope(scopes, "mail:send")

    # 管理员开关：全局 allow_send + 针对用户的 can_send
    if get_setting(db, "allow_send", str(settings.default_allow_send)).lower() != "true":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "管理员已关闭发信功能")
    if not user.can_send:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "你的账号被禁止发信")

    mb = get_mailbox_or_404(db, mailbox_id, user, scopes)

    if mb.type == "account":
        smtp_user = mb.email
        smtp_pass = decrypt_credential(mb.password_enc or "")
        from_addr = mb.email
    else:
        # 别名用该域名主邮箱发，From 写别名地址
        creds = get_master_creds(db, domain_of(mb.email))
        if not creds:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                                "该域名的主邮箱未配置，请在管理后台 → 域名管理添加")
        smtp_user, smtp_pass = creds
        from_addr = mb.email

    try:
        send_mail(
            host=settings.serv00_smtp_host, port=settings.serv00_smtp_port,
            username=smtp_user, password=smtp_pass,
            from_addr=from_addr, to_addrs=data.to,
            subject=data.subject, body=data.body, html=data.html,
            starttls=settings.serv00_smtp_starttls,
        )
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"发信失败：{e}")
    # 存档到已发送（纯文本转简单 HTML，方便展示）
    import html as _html
    body_html = data.body if data.html else (
        '<div style="white-space:pre-wrap">' + _html.escape(data.body or "") + "</div>")
    db.add(models.SentMail(user_id=user.id, mailbox_id=mb.id, from_addr=from_addr,
                           to_addrs=data.to, subject=data.subject or "",
                           body_html=body_html))
    db.commit()
    return {"ok": True}
