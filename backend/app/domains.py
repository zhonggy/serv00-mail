"""多域名支持：每个域名配一个主邮箱（catch-all），别名收发走主邮箱凭据。"""
from sqlalchemy.orm import Session

from . import models
from .config import get_settings
from .security import decrypt_credential, encrypt_credential

settings = get_settings()


def domain_of(email: str) -> str:
    """从邮箱地址取域名部分。"""
    return email.rsplit("@", 1)[-1].strip().lower()


def get_domain_row(db: Session, domain: str) -> models.MailDomain | None:
    return db.query(models.MailDomain).filter(
        models.MailDomain.domain == domain.strip().lower()).first()


def get_master_creds(db: Session, domain: str) -> tuple[str, str] | None:
    """返回某域名主邮箱的 (邮箱, 明文密码)。优先 DB 配置，兜底 .env。"""
    row = get_domain_row(db, domain)
    if row:
        return row.master_email, decrypt_credential(row.master_password_enc)
    if settings.master_imap_user:
        return settings.master_imap_user, settings.master_imap_pass
    return None


def get_default_domain(db: Session) -> str:
    """建邮箱时的默认域名：DB 默认域名 > settings 表 > .env 默认。"""
    row = db.query(models.MailDomain).filter(
        models.MailDomain.is_default.is_(True)).first()
    if row:
        return row.domain
    s = db.get(models.Setting, "default_domain")
    if s and s.value.strip():
        return s.value.strip()
    return settings.default_domain


def seed_domains_from_env(db: Session) -> None:
    """首次运行时把 .env 里的主邮箱导入为一条域名配置（幂等）。"""
    if db.query(models.MailDomain).count() > 0:
        return
    if not settings.master_imap_user or "@" not in settings.master_imap_user:
        return
    domain = domain_of(settings.master_imap_user)
    db.add(models.MailDomain(
        domain=domain,
        master_email=settings.master_imap_user.strip(),
        master_password_enc=encrypt_credential(settings.master_imap_pass or ""),
        is_default=True,
    ))
    db.commit()
