"""初始化数据库：建表、写入默认配置、创建管理员。

用法：
    ADMIN_USERNAME=admin ADMIN_PASSWORD=xxx python scripts/init_db.py
不传则默认 admin / admin123（首次登录后请立即修改）。
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import get_settings  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app import models  # noqa: E402
from app.domains import seed_domains_from_env  # noqa: E402
from app.security import hash_password  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

settings = get_settings()


def main() -> None:
    Base.metadata.create_all(engine)
    print("数据表创建完成")

    db = Session(engine)
    try:
        defaults = {
            "allow_register": str(settings.default_allow_register).lower(),
            "allow_send": str(settings.default_allow_send).lower(),
            "default_domain": settings.default_domain,
        }
        for key, value in defaults.items():
            if not db.get(models.Setting, key):
                db.add(models.Setting(key=key, value=value))
                print(f"默认配置写入：{key}={value}")

        if db.query(models.User).count() == 0:
            username = os.environ.get("ADMIN_USERNAME", "admin")
            password = os.environ.get("ADMIN_PASSWORD")
            if not password:
                password = getpass.getpass(f"设置管理员 [{username}] 的密码：")
            admin = models.User(
                username=username,
                password_hash=hash_password(password),
                is_admin=True,
            )
            db.add(admin)
            print(f"管理员账号创建完成：{username}（请登录后修改密码）")
        db.commit()
        seed_domains_from_env(db)
    finally:
        db.close()
    print("初始化完成")


if __name__ == "__main__":
    main()
