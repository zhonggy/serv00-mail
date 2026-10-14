#!/usr/bin/env python3
"""服务端一次性脚本：建 E2E 测试用户 + 可用的测试邮箱（密码仅本次验证用）。

策略：
 1. 建测试用户 cm-e2e-test（密码 E2e-Test-9876）。
 2. 若有默认域名且配了主邮箱：建别名 cme2e-xxx@domain（主架构路径）。
 3. 尝试面板建真实邮箱 cme2e-xxx@zgy.serv00.net（备用路径，实测过 serv00 面板）。

输出行（只输出这些，不输出密码）：
  SETUP_OK user=cm-e2e-test alias=<addr|-> account=<addr|->
"""
import os
import random
import string
import sys

os.chdir("/home/zgy/serv00-mail/backend")
sys.path.insert(0, "/home/zgy/serv00-mail/backend")

from sqlalchemy.orm import Session

from app import models
from app.database import engine
from app.domains import get_default_domain, get_domain_row
from app.security import encrypt_credential, hash_password

TEST_USER = "cm-e2e-test"
TEST_PASS = "E2e-Test-9876"


def _rand(n=8):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for n in range(n))


def main() -> None:
    db = Session(engine)
    alias_addr, account_addr = "-", "-"
    try:
        # 幂等清理
        for u in db.query(models.User).filter(models.User.username == TEST_USER).all():
            for mb in db.query(models.Mailbox).filter(models.Mailbox.user_id == u.id).all():
                if mb.type == "account":
                    try:
                        from app.provision.panel import PanelProvisioner
                        PanelProvisioner().delete(mb.email)
                    except Exception:
                        pass
                db.query(models.CmEmailMap).filter(
                    models.CmEmailMap.owner_key == f"mb:{mb.id}").delete()
                db.delete(mb)
            db.query(models.CmSent).filter(models.CmSent.user_id == u.id).delete()
            db.query(models.ApiKey).filter(models.ApiKey.user_id == u.id).delete()
            db.delete(u)
        db.commit()

        u = models.User(username=TEST_USER, password_hash=hash_password(TEST_PASS),
                        is_admin=False, can_send=True)
        db.add(u)
        db.commit()
        db.refresh(u)

        # 别名路径
        domain = get_default_domain(db)
        if domain and get_domain_row(db, domain):
            alias_addr = f"cme2e-{_rand(6)}@{domain}".lower()
            db.add(models.Mailbox(user_id=u.id, type="alias", email=alias_addr))
            db.commit()

        # 真实邮箱路径（面板自动化）
        try:
            from app.provision.panel import PanelProvisioner
            prefix = f"cme2e{_rand(6)}"
            pw = "T3st-" + _rand(10)
            res = PanelProvisioner().create("zgy.serv00.net", prefix, pw)
            account_addr = res.email if hasattr(res, "email") else f"{prefix}@zgy.serv00.net"
            db.add(models.Mailbox(user_id=u.id, type="account", email=account_addr,
                                  password_enc=encrypt_credential(pw)))
            db.commit()
        except Exception as e:  # noqa: BLE001
            print(f"ACCOUNT_SETUP_FAIL:{type(e).__name__}:{str(e)[:120]}")

        print(f"SETUP_OK user={TEST_USER} alias={alias_addr} account={account_addr}")
    except Exception as e:  # noqa: BLE001
        print(f"SETUP_FAIL:{type(e).__name__}:{str(e)[:200]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
