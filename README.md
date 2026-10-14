# serv00-mail

基于 serv00 免费主机的自建邮箱服务。自用定位：漂亮的 Web 邮箱 + 管理员后台 + 开放 API。

serv00 提供真实的邮件服务器（IMAP 收 / SMTP 发），本项目是在它之上的一层：Web UI、用户管理、API 网关。整个项目可以直接跑在 serv00 本机上（1~2 个进程、<200MB 内存）。

## 功能

- **Web 邮箱**：收件箱（双栏）、读信、写信（富文本）、已发送、草稿箱、星标邮件（Vue 3 + Element Plus 自研前端，见 `frontend/`）
- **身份模型**：管理员登录是管理员；邮箱/别名登录是普通用户，只能看自己的邮箱、发件固定为登录邮箱
- **多域名**：每个域名配一个主邮箱，别名收发自动走对应主邮箱凭据
- **管理员后台**：用户管理、域名管理、API Key 管理、系统开关（注册/发信）
- **开放 API**（供别的项目调用，见 `docs/API.md`）：
  - 创建 / 删除邮箱（`type=account` 真实邮箱 / `type=alias` 无限别名）
  - 查询邮件、提取验证码（支持简繁中文、纯 HTML 邮件回退）
  - 发信（受发信开关控制）
- **验证码提取**：`GET /api/v1/mailboxes/{id}/codes`，网页端和第三方共用同一接口

## 目录结构

```
serv00-mail/
├── README.md
├── docs/
│   ├── API.md          # 开放 API 文档（含两种方案的调用示例）
│   ├── DEPLOY.md       # serv00 部署指南
│   └── ARCHITECTURE.md # 架构说明
├── backend/            # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/     # 接口：auth / mailboxes / messages / codes / admin
│   │   ├── mail/       # IMAP / SMTP / 验证码提取
│   │   └── provision/  # 开邮箱：panel（方案A）/ alias（方案B）
│   └── scripts/        # 初始化、保活脚本
└── frontend/           # Vue 3 + Element Plus 前端（登录/邮箱/写信/验证码/管理后台）
```

## 快速开始

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填好配置
python scripts/init_db.py
uvicorn app.main:app --host 127.0.0.1 --port 18080
```

详细步骤见 [docs/DEPLOY.md](docs/DEPLOY.md)，API 调用见 [docs/API.md](docs/API.md)。

## 许可证

MIT
