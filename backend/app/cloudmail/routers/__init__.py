from fastapi import APIRouter

from ..envelope import CMRoute
from .account import router as account_router
from .admin import router as admin_router
from .email import router as email_router
from .login import router as login_router
from .my import router as my_router
from .setting import router as setting_router

router = APIRouter(route_class=CMRoute)
router.include_router(login_router)
router.include_router(account_router)
router.include_router(email_router)
router.include_router(my_router)
router.include_router(setting_router)
router.include_router(admin_router)
