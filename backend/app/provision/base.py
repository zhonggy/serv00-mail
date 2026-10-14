"""开邮箱方案的统一接口。"""
from abc import ABC, abstractmethod


class ProvisionResult:
    def __init__(self, email: str, password: str | None = None):
        self.email = email
        self.password = password  # 方案A 有，方案B 为 None


class BaseProvisioner(ABC):
    @abstractmethod
    def create(self, domain: str, prefix: str, password: str | None = None) -> ProvisionResult:
        """创建邮箱/别名。password 仅方案A 使用（不传则自动生成）。"""

    @abstractmethod
    def delete(self, email: str) -> None:
        """删除邮箱/别名。"""
