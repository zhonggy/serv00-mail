#!/usr/bin/env python3
"""服务端一次性脚本：把 admin 的密码哈希换成给定值（只传哈希，不传原文）。"""
import os
import sys

os.chdir("/home/zgy/serv00-mail/backend")
sys.path.insert(0, "/home/zgy/serv00-mail/backend")

HASH = "bcrypt$$2b$12$ZpC2OFyE71a5A4zsfGeOq.yCdJF2C0pGuYLvPJD9izUah0CyCVE3W"

from sqlalchemy.orm import Session
from app import models
from app.database import engine

db = Session(engine)
try:
    u = db.query(models.User).filter(
        models.User.username == "admin",
        models.User.is_admin.is_(True)).first()
    if not u:
        print("PWCHANGE_FAIL:no admin user")
    else:
        u.password_hash = HASH
        db.commit()
        print("PWCHANGE_OK")
except Exception as e:
    print(f"PWCHANGE_FAIL:{type(e).__name__}")
finally:
    db.close()
