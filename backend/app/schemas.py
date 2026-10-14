"""Pydantic 请求/响应模型。"""
import datetime

from pydantic import BaseModel, Field


# ---------- 认证 ----------
class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    can_send: bool
    login_mailbox_id: int | None = None  # 邮箱登录时绑定的邮箱 id（写信用）
    login_mailbox_email: str | None = None  # 邮箱登录时绑定的邮箱地址


# ---------- 邮箱 ----------
class MailboxCreateIn(BaseModel):
    type: str = Field(pattern="^(account|alias)$", description="account=独立邮箱，alias=别名")
    prefix: str | None = Field(default=None, min_length=1, max_length=64)
    domain: str | None = Field(default=None, max_length=255, description="域名，不填用默认域名（须已在管理后台配置）")
    password: str | None = Field(default=None, min_length=6, max_length=128,
                                 description="别名登录密码（仅 type=alias 可用，只用于登录本项目）")


class MailboxPasswordIn(BaseModel):
    password: str = Field(min_length=6, max_length=128)


class MailboxOut(BaseModel):
    id: int
    type: str
    email: str
    password: str | None = None  # 仅创建时返回
    has_password: bool = False  # 是否设置了可登录本项目的密码
    created_at: datetime.datetime


class MessageOut(BaseModel):
    uid: str
    subject: str
    from_: str = Field(alias="from")
    to: str
    date: str
    snippet: str

    model_config = {"populate_by_name": True}


class MessageDetailOut(MessageOut):
    body_text: str
    body_html: str | None = None


class CodeOut(BaseModel):
    code: str
    context: str
    from_: str = Field(alias="from")
    subject: str
    date: str

    model_config = {"populate_by_name": True}


class CodesOut(BaseModel):
    email: str
    codes: list[CodeOut]


class SendIn(BaseModel):
    to: str
    subject: str
    body: str
    html: bool = False


# ---------- 域名 ----------
class MailDomainOut(BaseModel):
    id: int
    domain: str
    master_email: str
    is_default: bool
    created_at: datetime.datetime


class MailDomainCreateIn(BaseModel):
    domain: str = Field(min_length=3, max_length=255)
    master_email: str = Field(min_length=3, max_length=255)
    master_password: str = Field(min_length=1, max_length=255)
    is_default: bool = False


class MailDomainUpdateIn(BaseModel):
    master_email: str | None = Field(default=None, max_length=255)
    master_password: str | None = Field(default=None, max_length=255)
    is_default: bool | None = None


class DomainChoiceOut(BaseModel):
    """普通用户建邮箱时的域名下拉选项（不含密码）。"""
    domain: str
    is_default: bool


# ---------- 管理 ----------
class SettingOut(BaseModel):
    key: str
    value: str


class SettingUpdateIn(BaseModel):
    value: str


class UserUpdateIn(BaseModel):
    can_send: bool | None = None
    is_admin: bool | None = None


class ApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scopes: str = "mailbox:write,mail:read"  # 逗号分隔


class ApiKeyOut(BaseModel):
    id: int
    name: str
    key: str | None = None  # 明文仅创建时返回
    key_prefix: str
    scopes: str
    is_active: bool
    created_at: datetime.datetime


# ---------- 用户功能：已发送 / 草稿 / 星标 / 个人设置 ----------
class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


class SentMailOut(BaseModel):
    id: int
    mailbox_id: int
    from_addr: str
    to_addrs: str
    subject: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class SentMailDetailOut(SentMailOut):
    body_html: str


class DraftIn(BaseModel):
    mailbox_id: int | None = None
    to_addrs: str = Field(default="", max_length=1024)
    subject: str = Field(default="", max_length=512)
    body_html: str = ""


class DraftOut(BaseModel):
    id: int
    mailbox_id: int | None
    to_addrs: str
    subject: str
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class DraftDetailOut(DraftOut):
    body_html: str


class StarIn(BaseModel):
    mailbox_id: int
    imap_uid: str = Field(min_length=1, max_length=64)
    from_addr: str = Field(default="", max_length=512)
    subject: str = Field(default="", max_length=512)
    snippet: str = Field(default="", max_length=512)
    date_str: str = Field(default="", max_length=64)


class StarOut(BaseModel):
    id: int
    mailbox_id: int
    mailbox_email: str = ""
    imap_uid: str
    from_addr: str
    subject: str
    snippet: str
    date_str: str
    starred_at: datetime.datetime

    model_config = {"from_attributes": True}
