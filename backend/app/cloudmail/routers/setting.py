"""cloud-mail 兼容：站点配置（websiteConfig，前端启动/登录页必需）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ... import models
from ...api.deps import get_setting, set_setting
from ...config import get_settings
from ...database import get_db
from ..auth import get_cm_user, get_cm_user_optional
from ..envelope import CMFail, CMRoute, ok

settings = get_settings()
router = APIRouter(route_class=CMRoute)


def _bool_setting(db: Session, key: str, default: str) -> bool:
    return get_setting(db, key, default).lower() == "true"


def _website_config(db: Session) -> dict:
    domains = [f"@{d.domain}" for d in
               db.query(models.MailDomain).order_by(models.MailDomain.id.asc()).all()]
    return {
        # 开关类（0=开/1=关，与 cloud-mail 的 settingConst 对齐）
        "register": 0 if _bool_setting(db, "allow_register", str(settings.default_allow_register)) else 1,
        "send": 0 if _bool_setting(db, "allow_send", str(settings.default_allow_send)) else 1,
        "addEmail": 0,
        "manyEmail": 0,
        "receive": 0,
        "regKey": 1,  # 1=关闭邀请码
        "registerVerify": 1,
        "regVerifyOpen": False,
        "addVerifyOpen": False,
        "addEmailVerify": 1,
        # 展示类
        "title": "Cloud Mail",
        "domainList": domains,
        "loginDomain": 1,  # 1=隐藏登录框的域名后缀选择器，直接输完整账号
        "minEmailPrefix": 1,
        "autoRefresh": 1,
        "r2Domain": "",
        "siteKey": "",
        "background": "",
        "loginOpacity": 80,
        "notice": 1,  # 1=关闭公告弹窗（前端 notice===0 表示启用）
        "noticeTitle": "",
        "noticeContent": "",
        "noticeType": "info",
        "noticeDuration": 5000,
        "noticePosition": "top-right",
        "noticeWidth": 330,
        "noticeOffset": 20,
        # 第三方登录全部关闭（注意：前端是 Switch === 0 才显示按钮，1=隐藏）
        "linuxdoClientId": "",
        "linuxdoSwitch": 1,
        "githubClientId": "",
        "githubSwitch": 1,
        "googleClientId": "",
        "googleSwitch": 1,
        "projectLink": "https://github.com/maillab/cloud-mail",
    }


@router.get("/setting/websiteConfig")
def website_config(db: Session = Depends(get_db),
                   _user=Depends(get_cm_user_optional)):
    # 登录前也要能调（登录页读 domainList/title）
    return ok(_website_config(db))


@router.get("/setting/query")
def setting_query(user=Depends(get_cm_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise CMFail("无权限", 403)
    return ok(_website_config(db))


@router.put("/setting/set")
def setting_set(body: dict, user=Depends(get_cm_user),
                db: Session = Depends(get_db)):
    if not user.is_admin:
        raise CMFail("无权限", 403)
    # 只映射我们体系里存在的开关，其余忽略
    if "register" in body:
        set_setting(db, "allow_register",
                    "true" if int(body["register"] or 1) == 0 else "false")
    if "send" in body:
        set_setting(db, "allow_send",
                    "true" if int(body["send"] or 1) == 0 else "false")
    return ok()


@router.put("/setting/setBackground")
def set_background(user=Depends(get_cm_user)):
    return ok()


@router.delete("/setting/deleteBackground")
def delete_background(user=Depends(get_cm_user)):
    return ok()


@router.put("/setting/setBlacklist")
def set_blacklist(user=Depends(get_cm_user)):
    return ok()
