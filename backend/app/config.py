"""全局配置，从环境变量 / .env 读取。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "serv00-mail"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 10080  # 7 天

    database_url: str = "mysql+pymysql://user:pass@localhost:3306/serv00mail"

    serv00_imap_host: str = "mail.serv00.com"
    serv00_imap_port: int = 993
    serv00_smtp_host: str = "mail.serv00.com"
    serv00_smtp_port: int = 587
    serv00_smtp_starttls: bool = True

    default_domain: str = "example.com"

    # 方案 B 别名用的主邮箱
    master_imap_user: str = ""
    master_imap_pass: str = ""

    # 方案 A：serv00 面板自动化
    serv00_panel_url: str = "https://panel1.serv00.com"
    serv00_panel_user: str = ""
    serv00_panel_pass: str = ""

    # 邮箱密码加密
    fernet_key: str = ""

    default_allow_register: bool = True
    default_allow_send: bool = True

    mailbox_create_limit_per_hour: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
