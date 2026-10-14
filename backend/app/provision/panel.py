"""方案 A：通过 serv00 面板自动创建真实独立邮箱。

原理：后端模拟登录 DevilWEB 面板，调用面板的添加邮箱表单接口。

实测（2026-10-12，panel8.serv00.com）：
- 添加邮箱页：GET https://panel8.serv00.com/mail/add
- 表单：<form method="post" action="/mail/add">，隐藏字段 csrfmiddlewaretoken
- 字段：email（完整地址）/ password1 / password2
- 注意：社区流传的 /mail/details/add_mailbox/{domain} 在该面板上不存在，
  以本文件为准。

若 serv00 面板改版导致失败，看日志报错按本文件注释调整 URL/选择器即可，
其他模块不受影响。
"""
import logging

import requests
from bs4 import BeautifulSoup

from ..config import get_settings
from ..security import generate_mailbox_password
from .base import BaseProvisioner, ProvisionResult

log = logging.getLogger(__name__)
settings = get_settings()


class PanelError(RuntimeError):
    pass


class PanelProvisioner(BaseProvisioner):
    """serv00 面板自动化开邮箱。"""

    def __init__(self):
        self.base = settings.serv00_panel_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        })
        self._logged_in = False

    # ---------- 登录 ----------
    def _get_csrf(self, url: str) -> str:
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Django 面板：csrfmiddlewaretoken 藏在表单 hidden input 里
        tag = soup.find("input", {"name": "csrfmiddlewaretoken"})
        if not tag or not tag.get("value"):
            raise PanelError(f"无法从 {url} 解析 CSRF token，面板可能改版")
        return tag["value"]

    def login(self) -> None:
        if self._logged_in:
            return
        login_url = f"{self.base}/login/"
        csrf = self._get_csrf(login_url)
        r = self.session.post(
            login_url,
            data={
                "csrfmiddlewaretoken": csrf,
                "username": settings.serv00_panel_user,
                "password": settings.serv00_panel_pass,
                "next": "/",
            },
            headers={"Referer": login_url},
            timeout=30,
            allow_redirects=True,
        )
        # 登录成功一般会跳转离开 login 页
        if "login" in r.url and r.status_code == 200:
            raise PanelError("面板登录失败，请检查 SERV00_PANEL_USER/PASS")
        self._logged_in = True
        log.info("serv00 面板登录成功")

    # ---------- 开邮箱 ----------
    def create(self, domain: str, prefix: str, password: str | None = None) -> ProvisionResult:
        self.login()
        password = password or generate_mailbox_password()
        add_url = f"{self.base}/mail/add"
        csrf = self._get_csrf(add_url)
        email_addr = f"{prefix}@{domain}"
        r = self.session.post(
            add_url,
            data={
                "csrfmiddlewaretoken": csrf,
                "email": email_addr,
                "password1": password,
                "password2": password,
            },
            headers={"Referer": add_url},
            timeout=60,
            allow_redirects=True,
        )
        if r.status_code != 200:
            raise PanelError(f"创建邮箱失败：HTTP {r.status_code}，面板可能改版或配额不足")
        # Django 表单校验失败会原样返回带 errorlist 的表单页
        if "errorlist" in r.text:
            raise PanelError("面板表单校验失败（可能是地址已存在或密码不符合要求）")
        log.info("面板创建邮箱成功：%s", email_addr)
        return ProvisionResult(email=email_addr, password=password)

    # ---------- 删邮箱 ----------
    def delete(self, email: str) -> None:
        self.login()
        # 实测（2026-10-12，panel8）：删除是 POST 表单
        #   POST /mail/details/{domain} 字段 del_email={完整地址} + csrfmiddlewaretoken
        # 页面里是个确认 modal（del_modal_N），直接 POST 即可生效
        _, _, domain = email.partition("@")
        url = f"{self.base}/mail/details/{domain}"
        csrf = self._get_csrf(url)
        r = self.session.post(
            url,
            data={"csrfmiddlewaretoken": csrf, "del_email": email},
            headers={"Referer": url},
            timeout=30,
        )
        if r.status_code != 200 or "errorlist" in r.text:
            raise PanelError(f"删除邮箱失败（{email}）：HTTP {r.status_code}")
        log.info("面板删除邮箱成功：%s", email)
