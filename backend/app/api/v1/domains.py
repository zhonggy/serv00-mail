"""普通用户：查看可用的域名列表（建邮箱时选域名用，不含密码）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import models, schemas
from ...database import get_db
from ..deps import get_caller

router = APIRouter()


@router.get("", response_model=list[schemas.DomainChoiceOut], summary="域名下拉列表")
def list_domains(caller=Depends(get_caller), db: Session = Depends(get_db)):
    rows = db.query(models.MailDomain).order_by(models.MailDomain.id).all()
    return [schemas.DomainChoiceOut(domain=r.domain, is_default=r.is_default)
            for r in rows]
