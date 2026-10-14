"""鉴权依赖：JWT（Web 用户）/ API Key（第三方调用）二选一。"""
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .. import models
from ..config import get_settings
from ..database import get_db
from ..security import decode_access_token, hash_api_key

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


def get_setting(db: Session, key: str, default: str) -> str:
    row = db.get(models.Setting, key)
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(models.Setting, key)
    if row:
        row.value = value
    else:
        db.add(models.Setting(key=key, value=value))
    db.commit()


def get_caller(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> tuple[models.User, list[str]]:
    """返回 (用户, scopes)。Web 用户 scopes 为 ["*"]，API Key 按创建时授予的来。"""
    if x_api_key:
        row = (
            db.query(models.ApiKey)
            .filter(models.ApiKey.key_hash == hash_api_key(x_api_key),
                    models.ApiKey.is_active == True)  # noqa: E712
            .first()
        )
        if not row:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API Key 无效或已停用")
        user = db.get(models.User, row.user_id)
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API Key 关联用户不存在")
        scopes = [s.strip() for s in row.scopes.split(",") if s.strip()]
        return user, scopes

    if credentials:
        payload = decode_access_token(credentials.credentials)
        if payload is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token 无效或已过期")
        user = db.get(models.User, int(payload["sub"]))
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
        scopes = ["*"]
        if payload.get("mb"):
            # 邮箱登录的 token：绑定登录邮箱，且永远是普通用户身份
            # （scopes 不再是纯 ["*"]，get_admin / is_admin 判断会拒绝管理员权限）
            scopes = ["*", f"login-mb:{int(payload['mb'])}"]
        return user, scopes

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "需要登录或提供 X-API-Key")


def require_scope(scopes: list[str], need: str) -> None:
    if "*" not in scopes and need not in scopes:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"缺少权限 scope：{need}")


def caller_is_admin(user: models.User, scopes: list[str]) -> bool:
    """真正的管理员：用户是管理员 且 token 不是邮箱登录（邮箱登录永远是普通身份）。"""
    return bool(user.is_admin) and scopes == ["*"]


def login_mailbox_id(scopes: list[str]) -> int | None:
    """邮箱登录绑定的 mailbox id（项目账号/API Key 登录返回 None）。"""
    for s in scopes:
        if s.startswith("login-mb:"):
            try:
                return int(s.split(":", 1)[1])
            except ValueError:
                return None
    return None


def get_admin(
    caller: tuple[models.User, list[str]] = Depends(get_caller),
) -> models.User:
    """管理员接口只允许 JWT 登录的管理员（API Key 不行，邮箱登录不行）。"""
    user, scopes = caller
    if not caller_is_admin(user, scopes):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员登录")
    return user


def get_mailbox_or_404(db: Session, mailbox_id: int, user: models.User,
                       scopes: list[str] | None = None) -> models.Mailbox:
    scopes = scopes if scopes is not None else ["*"]
    mb = db.get(models.Mailbox, mailbox_id)
    if not mb or (mb.user_id != user.id
                  and not caller_is_admin(user, scopes)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邮箱不存在")
    # 邮箱登录：只能操作登录时用的那个邮箱，看不到/用不了其它邮箱
    lb = login_mailbox_id(scopes)
    if lb and mb.id != lb:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邮箱不存在")
    return mb
