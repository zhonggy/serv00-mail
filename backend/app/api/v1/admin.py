"""管理员后台：开关、用户、API Key、域名。仅 JWT 管理员可调用。"""
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ... import models, schemas
from ...database import get_db
from ...domains import domain_of, get_domain_row
from ...security import encrypt_credential, generate_api_key
from ..deps import get_admin, get_setting, set_setting

router = APIRouter()

# 允许在后台修改的开关
EDITABLE_SETTINGS = {"allow_register", "allow_send", "default_domain"}

DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]+(\.[a-z0-9-]+)+$")


def _check_domain_input(domain: str, master_email: str) -> tuple[str, str]:
    domain = domain.strip().lower()
    master_email = master_email.strip()
    if not DOMAIN_RE.match(domain):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "域名格式不正确")
    if domain_of(master_email) != domain:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "主邮箱必须属于该域名")
    return domain, master_email


def _unset_others_default(db: Session, keep_id: int) -> None:
    db.query(models.MailDomain).filter(
        models.MailDomain.id != keep_id,
        models.MailDomain.is_default.is_(True),
    ).update({"is_default": False})


@router.get("/domains", response_model=list[schemas.MailDomainOut], summary="域名配置列表（管理员）")
def list_domains(admin=Depends(get_admin), db: Session = Depends(get_db)):
    return db.query(models.MailDomain).order_by(models.MailDomain.id).all()


@router.post("/domains", response_model=schemas.MailDomainOut,
             status_code=status.HTTP_201_CREATED, summary="添加域名配置（管理员）")
def create_domain(data: schemas.MailDomainCreateIn,
                  admin=Depends(get_admin), db: Session = Depends(get_db)):
    domain, master_email = _check_domain_input(data.domain, data.master_email)
    if get_domain_row(db, domain):
        raise HTTPException(status.HTTP_409_CONFLICT, "该域名已配置")
    row = models.MailDomain(
        domain=domain, master_email=master_email,
        master_password_enc=encrypt_credential(data.master_password),
        is_default=data.is_default,
    )
    db.add(row)
    db.flush()
    if data.is_default:
        _unset_others_default(db, row.id)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/domains/{domain_id}", response_model=schemas.MailDomainOut, summary="修改域名配置（管理员）")
def update_domain(domain_id: int, data: schemas.MailDomainUpdateIn,
                  admin=Depends(get_admin), db: Session = Depends(get_db)):
    row = db.get(models.MailDomain, domain_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "域名不存在")
    if data.master_email is not None:
        _, master_email = _check_domain_input(row.domain, data.master_email)
        row.master_email = master_email
    if data.master_password:
        row.master_password_enc = encrypt_credential(data.master_password)
    if data.is_default is not None:
        row.is_default = data.is_default
        db.flush()
        if data.is_default:
            _unset_others_default(db, row.id)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/domains/{domain_id}", summary="删除域名配置（管理员）")
def delete_domain(domain_id: int,
                  admin=Depends(get_admin), db: Session = Depends(get_db)):
    row = db.get(models.MailDomain, domain_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "域名不存在")
    used = db.query(models.Mailbox).filter(
        models.Mailbox.email.like(f"%@{row.domain}")).count()
    if used:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"该域名下还有 {used} 个邮箱，先删除这些邮箱再删域名")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/settings", response_model=list[schemas.SettingOut], summary="系统设置列表（管理员）")
def list_settings(admin=Depends(get_admin), db: Session = Depends(get_db)):
    rows = db.query(models.Setting).all()
    return [schemas.SettingOut(key=r.key, value=r.value) for r in rows]


@router.put("/settings/{key}", response_model=schemas.SettingOut, summary="修改系统设置（管理员）")
def update_setting(key: str, data: schemas.SettingUpdateIn,
                   admin=Depends(get_admin), db: Session = Depends(get_db)):
    if key not in EDITABLE_SETTINGS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不允许修改的配置项：{key}")
    value = data.value.strip().lower()
    if key in ("allow_register", "allow_send") and value not in ("true", "false"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "开关值只能是 true / false")
    set_setting(db, key, data.value.strip())
    return schemas.SettingOut(key=key, value=data.value.strip())


@router.get("/users", response_model=list[schemas.UserOut], summary="用户列表（管理员）")
def list_users(admin=Depends(get_admin), db: Session = Depends(get_db)):
    return db.query(models.User).all()


@router.patch("/users/{user_id}", response_model=schemas.UserOut, summary="修改用户（管理员）")
def update_user(user_id: int, data: schemas.UserUpdateIn,
                admin: models.User = Depends(get_admin), db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if user.id == admin.id and data.is_admin is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能取消自己的管理员身份")
    if data.can_send is not None:
        user.can_send = data.can_send
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    db.commit()
    db.refresh(user)
    return user


@router.post("/api-keys", response_model=schemas.ApiKeyOut, status_code=status.HTTP_201_CREATED, summary="创建 API Key（管理员）")
def create_api_key(data: schemas.ApiKeyCreateIn,
                   admin=Depends(get_admin), db: Session = Depends(get_db)):
    raw, key_hash, prefix = generate_api_key()
    row = models.ApiKey(user_id=admin.id, name=data.name, key_hash=key_hash,
                        key_prefix=prefix, scopes=data.scopes)
    db.add(row)
    db.commit()
    db.refresh(row)
    return schemas.ApiKeyOut(id=row.id, name=row.name, key=raw, key_prefix=row.key_prefix,
                             scopes=row.scopes, is_active=row.is_active,
                             created_at=row.created_at)


@router.get("/api-keys", response_model=list[schemas.ApiKeyOut], summary="API Key 列表（管理员）")
def list_api_keys(admin=Depends(get_admin), db: Session = Depends(get_db)):
    rows = db.query(models.ApiKey).order_by(models.ApiKey.id.desc()).all()
    return [schemas.ApiKeyOut(id=r.id, name=r.name, key_prefix=r.key_prefix,
                              scopes=r.scopes, is_active=r.is_active,
                              created_at=r.created_at) for r in rows]


@router.delete("/api-keys/{key_id}", summary="删除 API Key（管理员）")
def revoke_api_key(key_id: int, admin=Depends(get_admin), db: Session = Depends(get_db)):
    row = db.get(models.ApiKey, key_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API Key 不存在")
    row.is_active = False
    db.commit()
    return {"ok": True}
