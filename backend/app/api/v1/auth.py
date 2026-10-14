"""注册 / 登录。"""
import hmac

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ... import models, schemas
from ...config import get_settings
from ...database import get_db
from ...security import (
    create_access_token,
    decrypt_credential,
    hash_password,
    verify_password,
)
from ..deps import caller_is_admin, get_caller, get_setting, login_mailbox_id

settings = get_settings()
router = APIRouter()


@router.get("/me", response_model=schemas.UserOut, summary="当前登录用户信息")
def me(caller=Depends(get_caller), db: Session = Depends(get_db)):
    """当前登录用户（前端用它判断是否管理员）。
    邮箱登录永远是普通用户身份，且返回登录时用的邮箱 id 和地址。"""
    user, scopes = caller
    mb_id = login_mailbox_id(scopes)
    mb_email = None
    if mb_id:
        mb = db.get(models.Mailbox, mb_id)
        mb_email = mb.email if mb else None
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": caller_is_admin(user, scopes),
        "can_send": user.can_send,
        "login_mailbox_id": mb_id,
        "login_mailbox_email": mb_email,
    }


@router.post("/register", response_model=schemas.UserOut, summary="注册新项目用户（可被管理员关闭）")
def register(data: schemas.RegisterIn, db: Session = Depends(get_db)):
    if get_setting(db, "allow_register", str(settings.default_allow_register)).lower() != "true":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "管理员已关闭注册")
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用户名已存在")
    is_first = db.query(models.User).count() == 0
    user = models.User(
        username=data.username,
        password_hash=hash_password(data.password),
        is_admin=is_first,  # 第一个注册的是管理员
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.TokenOut, summary="登录（用户名/邮箱/别名/主邮箱）")
def login(data: schemas.LoginIn, db: Session = Depends(get_db)):
    # 1) 项目用户登录（users 表）
    user = db.query(models.User).filter(models.User.username == data.username).first()
    if user and verify_password(data.password, user.password_hash):
        return schemas.TokenOut(**{"access_token": create_access_token(user.id)})

    # 2) 邮箱账号登录：用邮箱地址 + 邮箱密码，登录为该邮箱的归属用户。
    #    独立邮箱用建邮箱时的真实密码；别名需在创建时/后台设置登录密码（只用于登录本项目）。
    #    注意：邮箱登录永远是普通用户身份（即使邮箱归属管理员），token 绑定该邮箱。
    mb = db.query(models.Mailbox).filter(models.Mailbox.email == data.username).first()
    if mb and mb.password_enc:
        try:
            real_pw = decrypt_credential(mb.password_enc)
        except RuntimeError:
            real_pw = None
        if real_pw and hmac.compare_digest(data.password, real_pw):
            owner = db.query(models.User).filter(models.User.id == mb.user_id).first()
            if owner:
                # 邮箱登录绑定该邮箱，且永远是普通用户身份（见 deps.caller_is_admin）
                return schemas.TokenOut(**{"access_token": create_access_token(
                    owner.id, login_mailbox_id=mb.id)})

    # 3) 域名主邮箱登录：用域名管理里配的主邮箱地址 + 密码，登录为管理员。
    drow = db.query(models.MailDomain).filter(
        models.MailDomain.master_email == data.username.strip()).first()
    if drow:
        try:
            master_pw = decrypt_credential(drow.master_password_enc)
        except RuntimeError:
            master_pw = None
        if master_pw and hmac.compare_digest(data.password, master_pw):
            admin = db.query(models.User).filter(
                models.User.is_admin.is_(True)).order_by(models.User.id).first()
            if admin:
                return schemas.TokenOut(**{"access_token": create_access_token(admin.id)})

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
