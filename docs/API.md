# serv00-mail API 文档

基地址：`https://ohyu.pp.ua/api/v1`

在线交互文档（和代码实时同步，可直接点进去试）：https://ohyu.pp.ua/docs

---

## 1. 鉴权

两种方式，二选一，放在请求头里：

| 方式 | 请求头 | 适用 |
|---|---|---|
| 登录 Token | `Authorization: Bearer <access_token>` | 网页端、自己写的脚本 |
| API Key | `X-API-Key: <key>` | 第三方项目调用 |

Token 通过 `POST /api/v1/auth/login` 获取，长期有效；网页端「个人设置 → 修改密码」后旧 Token 失效。

API Key 由管理员在「管理后台 → API Keys」创建，创建时勾选权限范围（scopes），只给最小必要权限。
Key 明文只在创建成功时返回一次，请当时就复制保存。

### API Key 权限范围

| scope | 允许调用 |
|---|---|
| `mail:read` | 读邮件列表/正文、提取验证码 |
| `mail:send` | 发信 |
| `mailbox:write` | 创建/删除邮箱 |
| `*` | 全部（含管理接口） |

---

## 2. 登录方式与身份口径

`POST /api/v1/auth/login` 的 `username` 字段可以填四种凭据：

| 登录方式 | 密码 | 登录后身份 |
|---|---|---|
| 项目用户名 | 项目密码 | 按账号本身（管理员账号就是管理员） |
| 独立邮箱地址 | 邮箱密码（serv00 邮件密码） | 普通用户，绑定该邮箱 |
| 别名地址 | 建别名时设的项目登录密码 | 普通用户，绑定该别名 |
| 域名主邮箱地址 | 主邮箱密码 | 普通用户，绑定主邮箱 |

**身份口径**：只有用项目管理员账号登录才是管理员；邮箱/别名登录一律是普通用户，
只能看到和操作自己登录的那个邮箱（看别人的邮箱会返回 404，`GET /mailboxes` 也只返回自己的）。

别名默认没有登录密码；建别名时传 `password` 参数可设置，或之后调
`PATCH /api/v1/mailboxes/{id}/password` 设置/重设。别名密码只用于登录本项目，不能登录 webmail。

---

## 3. 接口一览

### 3.1 认证

```
POST /api/v1/auth/login             登录（四种凭据见上表）
  body: {"username": "admin", "password": "xxx"}
  返回: {"access_token": "...", "token_type": "bearer"}

POST /api/v1/auth/register          注册新项目用户（管理员可在后台关闭注册）
  body: {"username": "zhangsan", "password": "xxx"}   # 用户名≥3位，密码≥6位

GET  /api/v1/auth/me                当前登录用户信息（含 is_admin、login_mailbox_id/email）

POST /api/v1/auth/change-password  修改自己的登录密码
  body: {"old_password": "旧", "new_password": "新"}  # 新密码≥6位
  说明：项目账号改项目密码；别名改别名登录密码；独立邮箱会拒绝（请去 serv00 面板改）
```

### 3.2 邮箱管理

```
GET    /api/v1/mailboxes            邮箱列表（邮箱登录只返回自己登录的那个）
POST   /api/v1/mailboxes            创建邮箱
  body: {"type": "alias", "prefix": "news", "domain": "ohyu.pp.ua", "password": "xxx"}
  type: alias=别名（走主邮箱 catch-all 收发）；account=serv00 真实独立邮箱
  prefix 不填则随机生成；domain 不填用默认域名；password 仅别名可用
  独立邮箱创建成功时返回一次明文密码（可登录 webmail，务必当时保存）
DELETE /api/v1/mailboxes/{id}       删除邮箱
PATCH  /api/v1/mailboxes/{id}/password   设置/重设别名登录密码（仅别名）
  body: {"password": "新密码"}
```

### 3.3 读邮件与发信

```
GET  /api/v1/mailboxes/{id}/messages          邮件列表（最近 50 封，含主题/发件人/摘要）
GET  /api/v1/mailboxes/{id}/messages/{uid}     邮件正文详情（body_html / body_text）
POST /api/v1/mailboxes/{id}/send               发信（同时存入已发送）
  body: {"to": "a@b.com", "subject": "标题", "body": "<p>正文</p>", "html": true}
  html=true 按富文本发送；发件人固定为该邮箱（邮箱登录时后端会校验）
```

### 3.4 验证码提取（网页端和第三方共用）

```
GET /api/v1/mailboxes/{id}/codes?since_minutes=10&limit=20
```

从该邮箱最近邮件中提取验证码。参数：

- `since_minutes`：只看 N 分钟内的邮件（默认 30）
- `limit`：最多扫描多少封（默认 20）

返回示例：

```json
{
  "codes": [
    {"code": "739512", "from": "no-reply@example.com", "subject": "您的验证码", "date": "2026-10-14 12:00:00"}
  ]
}
```

第三方项目用法：管理员创建一个 scope 含 `mail:read` 的 API Key，调用方先用
`GET /api/v1/mailboxes` 查到邮箱 id，再调本接口。网页端的「验证码」页面（自动轮询）用的就是这个接口。

### 3.5 个人功能（已发送 / 草稿 / 星标）

```
GET    /api/v1/sent                 已发送列表
GET    /api/v1/sent/{sent_id}       已发送邮件详情
GET    /api/v1/drafts               草稿列表
POST   /api/v1/drafts               保存草稿  body: {"mailbox_id":1,"to_addrs":"a@b.com","subject":"t","body_html":"<p>x</p>"}
GET    /api/v1/drafts/{draft_id}    草稿详情
PUT    /api/v1/drafts/{draft_id}    更新草稿
DELETE /api/v1/drafts/{draft_id}    删除草稿
GET    /api/v1/stars                星标邮件列表
POST   /api/v1/stars                加星标  body: {"mailbox_id":1,"imap_uid":"123","from_addr":"...","subject":"...","snippet":"...","date_str":"..."}
DELETE /api/v1/stars/{star_id}      取消星标
```

以上接口的数据都按「当前登录身份」隔离：邮箱登录只能看到自己邮箱的数据。

### 3.6 域名（多域名 + 主邮箱）

```
GET    /api/v1/domains              域名下拉列表（普通用户建邮箱时用，不含密码）
```

以下管理员专用：

```
GET    /api/v1/admin/domains           域名配置列表
POST   /api/v1/admin/domains           添加  body: {"domain":"ohyu.pp.ua","master_email":"m@zgy.serv00.net","master_password":"xxx","is_default":true}
PATCH  /api/v1/admin/domains/{id}      修改主邮箱/密码/设为默认
DELETE /api/v1/admin/domains/{id}      删除（该域名下还有邮箱时拒绝）
```

每个域名配一个主邮箱（需在 serv00 开启 catch-all 指向它）。别名的收发自动走其域名的主邮箱凭据。

### 3.7 管理员

```
GET  /api/v1/admin/users            用户列表
PATCH /api/v1/admin/users/{id}      修改用户  body: {"can_send": false}  # 可禁发信
GET  /api/v1/admin/settings         系统设置（allow_register 注册开关、allow_send 发信开关等）
PUT  /api/v1/admin/settings/{key}   修改设置  body: {"value": "0"}
GET  /api/v1/admin/api-keys         API Key 列表（只显示前缀，不显示明文）
POST /api/v1/admin/api-keys        创建  body: {"name": "给xx项目用", "scopes": "mail:read,mail:send"}
DELETE /api/v1/admin/api-keys/{id}  删除
```

---

## 4. 常见错误码

| 状态码 | 含义 |
|---|---|
| 400 | 参数错误（如旧密码不对、新密码太短） |
| 401 | 未登录 / Token 无效 / 密码错误 |
| 403 | 无权限（普通用户调管理接口、API Key 缺 scope） |
| 404 | 不存在，或（邮箱登录时）试图访问别人的邮箱 |
| 409 | 邮箱地址已存在 |
| 422 | 请求体字段校验失败 |

错误 body 格式：`{"detail": "中文错误信息"}`。

---

## 5. 第三方调用示例（验证码场景）

```bash
# 1. 查邮箱 id（API Key 需 mail:read）
curl -H "X-API-Key: <key>" https://ohyu.pp.ua/api/v1/mailboxes

# 2. 取最近 10 分钟的验证码
curl -H "X-API-Key: <key>" \
  "https://ohyu.pp.ua/api/v1/mailboxes/3/codes?since_minutes=10&limit=20"
```
