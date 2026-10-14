"""方案 B：别名。零成本、秒开、数量不限。

前提：域名在 serv00 面板开启了 catch-all 并指向主邮箱（见 docs/DEPLOY.md）。
这样任意 prefix@domain 的邮件都会进入主邮箱，后端按收件人过滤即可。

"创建别名" = 在本地 DB 记一条记录，不需要调 serv00 任何接口，
所以这个 provisioner 永远不会因为面板改版而挂。
"""
from .base import BaseProvisioner, ProvisionResult


class AliasProvisioner(BaseProvisioner):
    def create(self, domain: str, prefix: str, password: str | None = None) -> ProvisionResult:
        email_addr = f"{prefix}@{domain}"
        # catch-all 已接管收信，这里只需返回地址
        return ProvisionResult(email=email_addr, password=None)

    def delete(self, email: str) -> None:
        # 别名只存在于本地 DB，删除由上层删库记录即可
        return None
