"""cloud-mail 兼容层鉴权。

cloud-mail 前端把 login 返回的 token 原样存 localStorage，
每次请求放在 Authorization 头里（无 Bearer 前缀）。
shim 复用我们自己的 JWT：login 返回 {'token': jwt}。
"""
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import decode_access_token
from .envelope import CMFail


def _user_from_token(db: Session, authorization: str | None) -> models.User | None:
    if not authorization:
        return None
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    payload = decode_access_token(token)
    if not payload:
        return None
    return db.get(models.User, int(payload["sub"]))


def get_cm_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> models.User:
    user = _user_from_token(db, authorization)
    if not user:
        raise CMFail("登录已过期，请重新登录", 401)
    return user


def get_cm_user_optional(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> models.User | None:
    return _user_from_token(db, authorization)
