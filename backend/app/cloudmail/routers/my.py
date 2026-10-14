"""cloud-mail 兼容：当前用户信息 / 改密码。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import models
from ...database import get_db
from ...domains import domain_of, get_domain_row
from ...security import hash_password
from ..auth import get_cm_user
from ..envelope import CMFail, CMRoute, ok
from .account import _to_account

router = APIRouter(route_class=CMRoute)

# 管理员权限（去掉未实现的 role / reg-key，两菜单不显示）
ADMIN_PERMS = ["email:query", "email:send", "user:query",
               "setting:query", "all-email:query", "analysis:query"]
USER_PERMS = ["email:query", "email:send"]


def _ensure_account(db: Session, user: models.User) -> models.Mailbox | None:
    """cloud-mail 注册即建号：用户若无邮箱，尝试用用户名（邮箱格式）自动建个别名。"""
    mb = (db.query(models.Mailbox)
          .filter(models.Mailbox.user_id == user.id)
          .order_by(models.Mailbox.id.asc()).first())
    if mb:
        return mb
    email = (user.username or "").strip().lower()
    if "@" in email:
        _prefix, _, domain = email.partition("@")
        if get_domain_row(db, domain) and not db.query(models.Mailbox).filter(
                models.Mailbox.email == email).first():
            mb = models.Mailbox(user_id=user.id, type="alias",
                                email=email, password_enc=None)
            db.add(mb)
            db.commit()
            db.refresh(mb)
            return mb
    # 实在建不出：用默认域名拼一个
    from ...domains import get_default_domain
    default_domain = get_default_domain(db)
    if default_domain and "@" not in (user.username or ""):
        email = f"{user.username}@{default_domain}".lower()
        if not db.query(models.Mailbox).filter(models.Mailbox.email == email).first():
            mb = models.Mailbox(user_id=user.id, type="alias",
                                email=email, password_enc=None)
            db.add(mb)
            db.commit()
            db.refresh(mb)
            return mb
    return None


@router.get("/my/loginUserInfo")
def login_user_info(user=Depends(get_cm_user), db: Session = Depends(get_db)):
    # refresh（get_cm_user 返回的可能是 detached？不，这里同 db session）
    user = db.get(models.User, user.id)
    mb = _ensure_account(db, user)
    account = _to_account(mb) if mb else {
        "accountId": 0, "email": user.username, "name": user.username,
        "status": 0, "allReceive": 0, "sort": 0, "isDel": 0,
        "latestEmailTime": None, "createTime": "",
    }
    return ok({
        "userId": user.id,
        "sendCount": 0,
        "email": user.username,
        "account": account,
        "name": account["name"],
        "permKeys": ADMIN_PERMS if user.is_admin else USER_PERMS,
        "role": {"roleId": 0, "name": "管理员" if user.is_admin else "普通用户"},
        "type": 0 if user.is_admin else 1,
    })


@router.put("/my/resetPassword")
def reset_password(body: dict, user=Depends(get_cm_user),
                   db: Session = Depends(get_db)):
    password = body.get("password") or ""
    if len(password) < 6:
        raise CMFail("密码至少 6 位", 400)
    user = db.get(models.User, user.id)
    user.password_hash = hash_password(password)
    db.commit()
    return ok()


@router.delete("/my/delete")
def delete_me(user=Depends(get_cm_user)):
    raise CMFail("暂不支持自助注销，请联系管理员", 400)
