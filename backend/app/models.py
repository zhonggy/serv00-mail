"""数据模型。"""
import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    can_send: Mapped[bool] = mapped_column(Boolean, default=True)  # 管理员可单独禁某人发信
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class Mailbox(Base):
    """邮箱。type=account 是 serv00 真实邮箱（方案A），type=alias 是别名（方案B）。"""
    __tablename__ = "mailboxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(16))  # account | alias
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet 加密后的邮箱密码，alias 为空
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256
    key_prefix: Mapped[str] = mapped_column(String(12))  # 展示用前缀，如 sk-abc123
    scopes: Mapped[str] = mapped_column(String(255), default="mailbox:write,mail:read")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class Setting(Base):
    """全局开关：allow_register / allow_send 等。"""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))


class MailDomain(Base):
    """域名配置：每个域名配一个主邮箱（catch-all 指向它）。

    别名（type=alias）的收发走该域名主邮箱的 IMAP/SMTP 凭据：
    收件时 IMAP 登录主邮箱按收件人过滤，发信时用主邮箱 SMTP 登录、From 写别名地址。
    """
    __tablename__ = "mail_domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    master_email: Mapped[str] = mapped_column(String(255))  # 该域名的主邮箱
    master_password_enc: Mapped[str] = mapped_column(Text)  # Fernet 加密后的主邮箱密码
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # 建邮箱时的默认域名
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class CmEmailMap(Base):
    """cloud-mail 兼容层：IMAP uid → 自增 emailId 映射。

    cloud-mail 前端的分页/已读/删除/长轮询全靠全局自增整数 emailId，
    而 IMAP uid 是字符串且按邮箱独立。用 owner_key 区分归属：
      "mb:{mailbox_id}" 某个邮箱视角；"master:{email}" 某域名主邮箱视角（全部邮件）。
    """
    __tablename__ = "cm_email_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_key: Mapped[str] = mapped_column(String(255), index=True)
    imap_uid: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (UniqueConstraint("owner_key", "imap_uid", name="uq_cm_map_owner_uid"),)


class CmSent(Base):
    """cloud-mail 兼容层：已发送邮件本地存储（它的“已发送”箱）。"""
    __tablename__ = "cm_sent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id"), index=True)
    to_addrs: Mapped[str] = mapped_column(String(1024), default="")
    subject: Mapped[str] = mapped_column(String(512), default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class SentMail(Base):
    """已发送邮件（写信发送后本地存档，供“已发送”查看）。"""
    __tablename__ = "sent_mails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id"), index=True)
    from_addr: Mapped[str] = mapped_column(String(255), default="")
    to_addrs: Mapped[str] = mapped_column(String(1024), default="")
    subject: Mapped[str] = mapped_column(String(512), default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class Draft(Base):
    """草稿箱。"""
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mailbox_id: Mapped[int | None] = mapped_column(ForeignKey("mailboxes.id"), nullable=True)
    to_addrs: Mapped[str] = mapped_column(String(1024), default="")
    subject: Mapped[str] = mapped_column(String(512), default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class StarredMail(Base):
    """星标邮件：按 (mailbox_id, imap_uid) 收藏。"""
    __tablename__ = "starred_mails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id"), index=True)
    imap_uid: Mapped[str] = mapped_column(String(64))
    from_addr: Mapped[str] = mapped_column(String(512), default="")
    subject: Mapped[str] = mapped_column(String(512), default="")
    snippet: Mapped[str] = mapped_column(String(512), default="")
    date_str: Mapped[str] = mapped_column(String(64), default="")
    starred_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (
        UniqueConstraint("user_id", "mailbox_id", "imap_uid", name="uq_star_user_mb_uid"),
    )
