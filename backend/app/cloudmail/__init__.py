"""cloud-mail 兼容层：让 cloud-mail 的 mail-vue 前端原样跑在我们的后端上。

收件走 serv00 IMAP，发件走 serv00 SMTP；API 说 cloud-mail 的方言
（根路径 + {code, message, data} 返回包）。
"""
from .routers import router

__all__ = ["router"]
