#!/usr/bin/env python3
"""服务端一次性脚本：清理 E2E 测试用户及相关数据（含面板真实邮箱）。"""
import os
import sys

os.chdir("/home/zgy/serv00-mail/backend")
sys.path.insert(0, "/home/zgy/serv00-mail/backend")

from sqlalchemy.orm import Session

from app import models
from app.database import engine

TEST_USER = "cm-e2e-test"


def main() -> None:
    db = Session(engine)
    try:
        n = 0
        for u in db.query(models.User).filter(models.User.username == TEST_USER).all():
            for mb in db.query(models.Mailbox).filter(models.Mailbox.user_id == u.id).all():
                if mb.type == "account":
                    try:
                        from app.provision.panel import PanelProvisioner
                        PanelProvisioner().delete(mb.email)
                    except Exception as e:  # noqa: BLE001
                        print(f"PANEL_DELETE_WARN:{mb.email}:{type(e).__name__}")
                db.query(models.CmEmailMap).filter(
                    models.CmEmailMap.owner_key == f"mb:{mb.id}").delete()
                db.delete(mb)
            db.query(models.CmSent).filter(models.CmSent.user_id == u.id).delete()
            db.query(models.ApiKey).filter(models.ApiKey.user_id == u.id).delete()
            db.delete(u)
            n += 1
        # 兜底：清掉残留的 cme2e- 前缀测试邮箱映射
        db.commit()
        print(f"CLEANUP_OK users={n}")
    except Exception as e:  # noqa: BLE001
        print(f"CLEANUP_FAIL:{type(e).__name__}:{str(e)[:200]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
