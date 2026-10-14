"""cloud-mail 兼容：登录 / 注册 / 登出。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ... import schemas as v1_schemas
from ...api.v1 import auth as v1_auth
from ...api.deps import get_setting
from ...config import get_settings
from ...database import get_db
from ..auth import get_cm_user
from ..envelope import CMFail, CMRoute, ok

settings = get_settings()
router = APIRouter(route_class=CMRoute)


def _try_login(db: Session, username: str, password: str) -> str | None:
    """复用 v1 登录逻辑（用户名→邮箱→主邮箱），成功返回 JWT，失败返回 None。"""
    try:
        return v1_auth.login(
            v1_schemas.LoginIn(username=username, password=password), db
        ).access_token
    except HTTPException:
        return None


@router.post("/login")
def cm_login(body: dict, db: Session = Depends(get_db)):
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        raise CMFail("请输入邮箱和密码", 400)
    token = _try_login(db, email, password)
    if not token and "@" in email:
        # cloud-mail 登录框是 前缀+后缀域名 的形式；项目用户名可能就是前缀部分
        token = _try_login(db, email.split("@")[0], password)
    if not token:
        raise CMFail("用户名或密码错误", 401)
    return ok({"token": token})


@router.delete("/logout")
def cm_logout(user=Depends(get_cm_user)):
    return ok()


@router.post("/register")
def cm_register(body: dict, db: Session = Depends(get_db)):
    if get_setting(db, "allow_register", str(settings.default_allow_register)).lower() != "true":
        raise CMFail("管理员已关闭注册", 403)
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or "@" not in email:
        raise CMFail("请输入正确的邮箱地址", 400)
    if len(password) < 6:
        raise CMFail("密码至少 6 位", 400)
    try:
        v1_auth.register(v1_schemas.RegisterIn(username=email, password=password), db)
    except HTTPException as e:
        detail = e.detail if isinstance(e.detail, str) else "注册失败"
        raise CMFail(detail, e.status_code)
    return ok({"regVerifyOpen": False})
