# serv00 部署指南

## 0. 准备工作

1. 注册 serv00 账号（https://www.serv00.com），拿到用户名、面板地址
2. 准备一个域名，DNS 托管到 serv00（面板 DevilWEB → DNS zones），并添加 MX 记录指向 serv00 的邮件服务器
3. 在面板创建一个邮箱域名（Mail → Domains），并开一个**主邮箱**（给方案 B 的别名用）

## 1. 开通运行权限

SSH 登录后：

```bash
devil binexec on          # 允许运行自己的程序
devil port add tcp random # 预留一个 TCP 端口，记下端口号（如 18080）
```

面板 DevilWEB → Additional services → Run your own applications → Enable。

## 2. 域名 catch-all（方案 B 别名必需）

面板 Mail → 找到你的域名 → 开启 catch-all，指向主邮箱。
这样任意 `xxx@你的域名` 的邮件都会进主邮箱，后端按收件人过滤。

## 3. 数据库

面板 → MySQL databases → 创建一个数据库和用户，记下：
`库名 / 用户名 / 密码 / 主机（一般是 localhost）`。

## 4. 上传代码并安装

```bash
# 上传 backend/ 到 ~/serv00-mail/backend
cd ~/serv00-mail/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`，重点填：

```
DATABASE_URL=mysql+pymysql://dbuser:dbpass@localhost:3306/dbname
SERV00_IMAP_HOST=...      # 面板 Mail 页面确认，一般是 s*.serv00.com
SERV00_SMTP_HOST=...      # 同上
SERV00_PANEL_URL=https://panel*.serv00.com   # 你的面板地址
SERV00_PANEL_USER=你的serv00用户名
SERV00_PANEL_PASS=你的serv00密码
DEFAULT_DOMAIN=你的域名
MASTER_IMAP_USER=主邮箱地址
MASTER_IMAP_PASS=主邮箱密码
FERNET_KEY=               # 用 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 生成
```

## 5. 初始化并启动

```bash
source venv/bin/activate
python scripts/init_db.py     # 建表 + 创建管理员 + 默认配置
```

首次启动（端口换成第 1 步预留的）：

```bash
nohup venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 18080 \
  > ~/serv00-mail/backend/app.log 2>&1 &
```

## 6. 对外发布

面板 DevilWEB → WWW websites → Add new website：

- Domain：你的域名（或子域名如 mail.example.com）
- Website type：Proxy
- Proxy：`127.0.0.1:18080`（端口换成你预留的）

面板会自动配 Let's Encrypt 证书。前端静态文件可直接放在该网站的 `public_html` 里。

> 实测备注（2026-10-12，panel8/s8）：邮件服务器 `mail8.serv00.com`、
> MySQL 服务器 `mysql8.serv00.com`，面板添加邮箱接口为 `POST /mail/add`
>（字段 `email`/`password1`/`password2`，Django CSRF）。

## 7. 保活（cron）

serv00 没有 systemd，进程挂了不会自起。加一条 cron 每 5 分钟检查：

```bash
crontab -e
# 添加：
*/5 * * * * /home/你的用户名/serv00-mail/backend/scripts/keepalive.sh
```

keepalive.sh 会 curl 健康检查接口，挂了就用 nohup 拉起来。

## 8. 验证

1. 打开 `https://你的域名/docs`（FastAPI 自带文档）确认服务正常
2. 管理员登录 → 确认 `allow_register` / `allow_send` 开关
3. 按 docs/API.md 走一遍：建别名 → 发一封测试邮件到别名 → 调 codes 接口取验证码
4. 再测方案 A：建独立邮箱 → 发测试邮件 → 取码 → 删除

## 注意事项

- 首次部署建议先用**别名方案**验证全链路，再开方案 A（面板自动化）
- 面板自动化依赖 serv00 面板页面结构，若面板改版导致方案 A 失败，看日志里的报错按 `app/provision/panel.py` 注释调整选择器
- 备份 `.env` 和数据库，serv00 免费账号长期不用可能被回收
