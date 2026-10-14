"""FastAPI 入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import admin, auth, codes, domains, mailboxes, messages, user
from .config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="""
## serv00-mail API

自建邮箱系统的后端接口：serv00 做邮件服务器（IMAP 收 / SMTP 发），本项目提供登录、收信、发信、验证码提取和管理能力。

### 鉴权方式（二选一）

1. **网页登录 Token**：`POST /api/v1/auth/login` 获取 `access_token`，之后请求头带
   `Authorization: Bearer <token>`。Token 长期有效，登出或改密码后失效。
2. **API Key（给第三方项目用）**：管理员在「管理后台 → API Keys」创建，
   请求头带 `X-API-Key: <key>`。创建时可勾选权限范围（scopes），只给最小必要权限。

### 登录方式

`POST /api/v1/auth/login` 支持四种凭据（`username` 填用户名或邮箱地址）：

| 登录方式 | 说明 |
|---|---|
| 项目用户名 + 密码 | 管理员创建的项目账号 |
| 独立邮箱地址 + 邮箱密码 | serv00 真实邮箱，身份为该邮箱的归属用户 |
| 别名地址 + 别名密码 | 建别名时设置的项目登录密码（只能登录本项目） |
| 域名主邮箱 + 密码 | 域名管理里配置的主邮箱 |

**身份口径**：只有用项目管理员账号登录才是管理员身份；邮箱/别名登录一律是普通用户身份，
只能看到和操作自己登录的那个邮箱。

### API Key 权限范围（scopes）

| scope | 能力 |
|---|---|
| `mail:read` | 读邮件列表/正文、提取验证码 |
| `mail:send` | 发信 |
| `mailbox:write` | 创建/删除邮箱 |
| `*` | 全部权限（含管理接口） |

### 验证码提取

`GET /api/v1/mailboxes/{mailbox_id}/codes` 从最近邮件中提取验证码，
支持 `since_minutes`（只看 N 分钟内的邮件）和 `limit`。网页端的「验证码」页面和第三方项目用的是同一个接口。
""",
    openapi_tags=[
        {"name": "auth", "description": "登录 / 注册 / 当前用户 / 改密码"},
        {"name": "mailboxes", "description": "邮箱管理：创建、列表、删除、设别名密码"},
        {"name": "messages", "description": "读邮件列表和正文、发信"},
        {"name": "codes", "description": "从最近邮件中提取验证码（网页端和第三方共用）"},
        {"name": "user", "description": "个人功能：已发送 / 草稿箱 / 星标 / 改密码"},
        {"name": "domains", "description": "域名配置（多域名 + 主邮箱）"},
        {"name": "admin", "description": "管理员：用户管理、系统设置、API Keys"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(mailboxes.router, prefix="/api/v1/mailboxes", tags=["mailboxes"])
app.include_router(messages.router, prefix="/api/v1/mailboxes", tags=["messages"])
app.include_router(codes.router, prefix="/api/v1/mailboxes", tags=["codes"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(domains.router, prefix="/api/v1/domains", tags=["domains"])
app.include_router(user.router, prefix="/api/v1", tags=["user"])


@app.get("/health")
def health():
    return {"ok": True, "app": settings.app_name}


# ---- 数据库自动建表 + 域名配置种子（幂等；增量部署新表无需手动迁移） ----
try:
    from sqlalchemy.orm import Session as _Session  # noqa: E402

    from .database import Base, engine  # noqa: E402
    from .domains import seed_domains_from_env  # noqa: E402

    Base.metadata.create_all(engine)
    _db = _Session(engine)
    try:
        seed_domains_from_env(_db)
    finally:
        _db.close()
except Exception as _e:  # noqa: BLE001
    print(f"[warn] DB auto-migrate/seed skipped: {_e}")


# ---- 前端静态托管（同源 serving，避免 CORS） ----
# frontend/dist 由前端构建产物组成；挂载在所有 API 路由之后，
# 因此 /api/*、/docs、/health 不受影响，其余路径走 SPA 的 index.html。
# _DIST 兼容两种部署布局：与 backend 同级的 frontend/（仓库标准布局），
# 以及 backend/ 下的 frontend/（增量更新包的布局）。
import os  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402

_BASE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_DIST_CANDIDATES = [
    os.path.join(_BASE, "frontend", "dist"),
    os.path.join(_BASE, "backend", "frontend", "dist"),
]
_DIST = next((p for p in _DIST_CANDIDATES if os.path.isdir(p)), None)

if _DIST:
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
