# 前端（Vue 3 + Element Plus）

自研单页应用，直接对接本项目后端 `backend/` 的全部接口（JWT 登录、管理后台、开放 API 同源）。
原计划复用 cloud-mail 的 mail-vue，但它是为 Cloudflare Workers 后端写的，API 形态差异大，
改造成本高于重写，因此改为按本项目 API 定制的轻量前端。

## 页面

| 路由 | 功能 |
|---|---|
| `#/login` | 登录 / 注册（首个注册用户自动成为管理员） |
| `#/mailboxes` | 邮箱列表：新建（独立邮箱/别名）、删除；独立邮箱密码仅创建时显示一次 |
| `#/mailbox/:id` | 某邮箱的收件箱（列表/读信/HTML 预览）与验证码提取 |
| `#/compose` | 写信（可选 HTML） |
| `#/codes` | 验证码聚合页：选邮箱 + 时间窗口，可 10 秒自动轮询 |
| `#/admin` | 管理后台：全局开关（`allow_register`/`allow_send`/`default_domain`）、用户发件权限、API Key 创建/吊销 |

## 本地开发

```bash
cd frontend
npm install
npm run dev        # vite dev，/api 反向代理到 http://127.0.0.1:8000（见 vite.config.js）
```

## 构建与部署（serv00）

```bash
npm run build      # 产物在 dist/
```

- `vite.config.js` 里 `base: './'`，资源用相对路径，直接把 `dist/` 内容丢进
  `public_html` 即可，无需 rewrite 规则（路由用 hash 模式 `#/...`）。
- 后端 API 基地址默认同源 `/api/v1`；前后端分离部署时复制 `.env.example`
  为 `.env` 并填写 `VITE_API_BASE=https://mail.example.com/api/v1` 后重新构建。
- 后端已开 CORS `*`，分离部署也能直接调用。

## 后端配套改动

- 新增 `GET /api/v1/auth/me`（`backend/app/api/v1/auth.py`）：前端用它判断当前用户
  身份与是否管理员；此前只有 `/register` 与 `/login`，前端拿不到用户信息。
