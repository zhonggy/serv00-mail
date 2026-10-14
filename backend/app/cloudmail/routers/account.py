"""cloud-mail 兼容：邮箱（account）管理。对应我们的 mailboxes（别名视角）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import models
from ...database import get_db
from ...domains import get_domain_row
from ..auth import get_cm_user
from ..envelope import CMFail, CMRoute, ok
from ..sync import owner_key_for_mailbox

router = APIRouter(route_class=CMRoute)


def _to_account(mb: models.Mailbox) -> dict:
    prefix = mb.email.split("@")[0] if "@" in mb.email else mb.email
    return {
        "accountId": mb.id,
        "email": mb.email,
        "name": prefix,
        "status": 0,
        "allReceive": 0,
        "sort": 0,
        "isDel": 0,
        "latestEmailTime": None,
        "createTime": mb.created_at.strftime("%Y-%m-%d %H:%M:%S") if mb.created_at else "",
    }


def _get_owned(db: Session, user: models.User, account_id: int) -> models.Mailbox:
    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        raise CMFail("邮箱不存在", 404)
    mb = db.query(models.Mailbox).filter(
        models.Mailbox.id == account_id,
        models.Mailbox.user_id == user.id).first()
    if not mb:
        raise CMFail("邮箱不存在", 404)
    return mb


@router.get("/account/list")
def account_list(accountId: int = 0, size: int = 30, lastSort: int = 0,
                 user=Depends(get_cm_user), db: Session = Depends(get_db)):
    size = min(max(int(size or 30), 1), 30)
    boxes = (db.query(models.Mailbox)
             .filter(models.Mailbox.user_id == user.id)
             .order_by(models.Mailbox.id.asc()).limit(size).all())
    return ok([_to_account(b) for b in boxes])


@router.post("/account/add")
def account_add(body: dict, user=Depends(get_cm_user), db: Session = Depends(get_db)):
    email = (body.get("email") or "").strip().lower()
    if "@" not in email:
        raise CMFail("请输入正确的邮箱地址", 400)
    prefix, _, domain = email.partition("@")
    if not prefix or not domain:
        raise CMFail("请输入正确的邮箱地址", 400)
    if not get_domain_row(db, domain):
        raise CMFail(f"域名 {domain} 未配置", 400)
    if db.query(models.Mailbox).filter(models.Mailbox.email == email).first():
        raise CMFail("该邮箱已存在", 400)
    # 对应别名：秒开，无需面板
    mb = models.Mailbox(user_id=user.id, type="alias", email=email, password_enc=None)
    db.add(mb)
    db.commit()
    db.refresh(mb)
    return ok(_to_account(mb))


@router.delete("/account/delete")
def account_delete(accountId: int = 0, user=Depends(get_cm_user),
                   db: Session = Depends(get_db)):
    mb = _get_owned(db, user, accountId)
    owner_key = owner_key_for_mailbox(mb)
    if mb.type == "account":
        # 真实邮箱：尝试面板删除，失败也继续删本地记录（与 v1 逻辑一致）
        try:
            from ...provision.panel import PanelProvisioner
            PanelProvisioner().delete(mb.email)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] cloudmail shim 面板删除失败（已删本地记录）：{type(e).__name__}: {e}")
    db.query(models.CmEmailMap).filter(
        models.CmEmailMap.owner_key == owner_key).delete()
    db.query(models.CmSent).filter(models.CmSent.mailbox_id == mb.id).delete()
    db.delete(mb)
    db.commit()
    return ok()


@router.put("/account/setName")
def account_set_name(body: dict, user=Depends(get_cm_user),
                     db: Session = Depends(get_db)):
    _get_owned(db, user, body.get("accountId"))
    # MVP：名称未持久化，前端显示用邮箱前缀
    return ok()


@router.put("/account/setAllReceive")
def account_set_all_receive(body: dict, user=Depends(get_cm_user),
                            db: Session = Depends(get_db)):
    _get_owned(db, user, body.get("accountId"))
    return ok()


@router.put("/account/setAsTop")
def account_set_as_top(body: dict, user=Depends(get_cm_user),
                       db: Session = Depends(get_db)):
    _get_owned(db, user, body.get("accountId"))
    return ok()
