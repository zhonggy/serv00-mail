"""用户功能：修改密码 / 已发送 / 草稿箱 / 星标邮件。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ... import models, schemas
from ...database import get_db
from ...security import decrypt_credential, encrypt_credential, hash_password, verify_password
from ..deps import get_caller, get_mailbox_or_404, login_mailbox_id, require_scope

router = APIRouter()


def _me(caller) -> tuple[models.User, list[str]]:
    return caller


# ---------- 修改密码 ----------
@router.post("/auth/change-password", summary="修改登录密码")
def change_password(data: schemas.ChangePasswordIn,
                    caller=Depends(get_caller), db: Session = Depends(get_db)):
    """个人设置 → 修改密码。
    邮箱登录：改的是登录用邮箱的密码；项目账号登录：改的是项目登录密码。"""
    user, scopes = _me(caller)
    mb_id = login_mailbox_id(scopes)
    if mb_id:
        mb = get_mailbox_or_404(db, mb_id, user, scopes)
        if mb.type == "account":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "独立邮箱的密码是 serv00 真实密码，请在 serv00 面板修改")
        if not mb.password_enc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "该邮箱未设置登录密码")
        try:
            real_pw = decrypt_credential(mb.password_enc)
        except RuntimeError:
            real_pw = None
        import hmac
        if not real_pw or not hmac.compare_digest(data.old_password, real_pw):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "原密码不正确")
        mb.password_enc = encrypt_credential(data.new_password)
    else:
        if not verify_password(data.old_password, user.password_hash):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "原密码不正确")
        user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"ok": True}


# ---------- 已发送 ----------
@router.get("/sent", response_model=list[schemas.SentMailOut], summary="已发送列表")
def list_sent(limit: int = Query(50, le=200),
              caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = _me(caller)
    require_scope(scopes, "mail:read")
    rows = (db.query(models.SentMail)
            .filter(models.SentMail.user_id == user.id)
            .order_by(models.SentMail.id.desc()).limit(limit).all())
    return rows


@router.get("/sent/{sent_id}", response_model=schemas.SentMailDetailOut, summary="已发送邮件详情")
def get_sent(sent_id: int, caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = _me(caller)
    require_scope(scopes, "mail:read")
    row = db.query(models.SentMail).filter(
        models.SentMail.id == sent_id, models.SentMail.user_id == user.id).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邮件不存在")
    return row


# ---------- 草稿箱 ----------
@router.get("/drafts", response_model=list[schemas.DraftOut], summary="草稿列表")
def list_drafts(caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, _scopes = _me(caller)
    return (db.query(models.Draft)
            .filter(models.Draft.user_id == user.id)
            .order_by(models.Draft.updated_at.desc()).all())


@router.post("/drafts", response_model=schemas.DraftDetailOut, summary="保存草稿")
def create_draft(data: schemas.DraftIn,
                 caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, _scopes = _me(caller)
    if data.mailbox_id:
        get_mailbox_or_404(db, data.mailbox_id, user, _scopes)
    d = models.Draft(user_id=user.id, mailbox_id=data.mailbox_id,
                     to_addrs=data.to_addrs, subject=data.subject,
                     body_html=data.body_html)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@router.get("/drafts/{draft_id}", response_model=schemas.DraftDetailOut, summary="草稿详情")
def get_draft(draft_id: int, caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, _scopes = _me(caller)
    d = db.query(models.Draft).filter(
        models.Draft.id == draft_id, models.Draft.user_id == user.id).first()
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "草稿不存在")
    return d


@router.put("/drafts/{draft_id}", response_model=schemas.DraftDetailOut, summary="更新草稿")
def update_draft(draft_id: int, data: schemas.DraftIn,
                 caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, _scopes = _me(caller)
    d = db.query(models.Draft).filter(
        models.Draft.id == draft_id, models.Draft.user_id == user.id).first()
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "草稿不存在")
    if data.mailbox_id:
        get_mailbox_or_404(db, data.mailbox_id, user, _scopes)
    d.mailbox_id = data.mailbox_id
    d.to_addrs = data.to_addrs
    d.subject = data.subject
    d.body_html = data.body_html
    db.commit()
    db.refresh(d)
    return d


@router.delete("/drafts/{draft_id}", summary="删除草稿")
def delete_draft(draft_id: int, caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, _scopes = _me(caller)
    d = db.query(models.Draft).filter(
        models.Draft.id == draft_id, models.Draft.user_id == user.id).first()
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "草稿不存在")
    db.delete(d)
    db.commit()
    return {"ok": True}


# ---------- 星标邮件 ----------
@router.get("/stars", response_model=list[schemas.StarOut], summary="星标邮件列表")
def list_stars(caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, _scopes = _me(caller)
    rows = (db.query(models.StarredMail)
            .filter(models.StarredMail.user_id == user.id)
            .order_by(models.StarredMail.starred_at.desc()).all())
    mb_map = {m.id: m.email for m in db.query(models.Mailbox)
              .filter(models.Mailbox.user_id == user.id).all()}
    out = []
    for r in rows:
        o = schemas.StarOut.model_validate(r)
        o.mailbox_email = mb_map.get(r.mailbox_id, f"#{r.mailbox_id}")
        out.append(o)
    return out


@router.post("/stars", response_model=schemas.StarOut, summary="加星标")
def star_mail(data: schemas.StarIn,
              caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, scopes = _me(caller)
    get_mailbox_or_404(db, data.mailbox_id, user, scopes)
    r = db.query(models.StarredMail).filter(
        models.StarredMail.user_id == user.id,
        models.StarredMail.mailbox_id == data.mailbox_id,
        models.StarredMail.imap_uid == data.imap_uid).first()
    if not r:
        r = models.StarredMail(user_id=user.id, mailbox_id=data.mailbox_id,
                               imap_uid=data.imap_uid, from_addr=data.from_addr,
                               subject=data.subject, snippet=data.snippet,
                               date_str=data.date_str)
        db.add(r)
        db.commit()
        db.refresh(r)
    mb = db.get(models.Mailbox, data.mailbox_id)
    o = schemas.StarOut.model_validate(r)
    o.mailbox_email = mb.email if mb else f"#{data.mailbox_id}"
    return o


@router.delete("/stars/{star_id}", summary="取消星标")
def unstar_mail(star_id: int, caller=Depends(get_caller), db: Session = Depends(get_db)):
    user, _scopes = _me(caller)
    r = db.query(models.StarredMail).filter(
        models.StarredMail.id == star_id, models.StarredMail.user_id == user.id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "星标不存在")
    db.delete(r)
    db.commit()
    return {"ok": True}
