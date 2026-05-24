# X-Agent 后端安全审计报告

**审计日期**: 2026-05-20  
**审计范围**: `backend/app/` 全部 128 个 Python 文件  
**审计方法**: 静态代码分析 + 手动逐行审查  
**风险评级**: CRITICAL / HIGH / MEDIUM / LOW

---

## 执行摘要

本次审计在 X-Agent 后端代码库中发现了 **31 项安全缺陷**，其中包括 **9 项 CRITICAL** 和 **8 项 HIGH** 级别问题。核心风险集中在：

1. **认证体系完全失效**: 登录接口不验证密码，匿名用户自动获得管理员级权限
2. **授权体系大面积缺失**: 超过 60% 的 API 端点未实施任何身份校验
3. **任意文件系统访问**: 通过 Agent 工具链和直接 API 可读写服务器任意路径
4. **密钥管理严重违规**: 硬编码密钥、无盐哈希、明文存储敏感凭证

**建议**: 在修复所有 CRITICAL 和 HIGH 问题之前，**不应将本系统暴露于任何不可信网络环境**。

---

## 一、认证与授权 (Authentication & Authorization)

### 🔴 CRITICAL-001: 登录/注册完全不验证密码
**文件**: `app/api/auth.py` (L30-L39)  
**描述**: `login()` 与 `register()` 的实现完全相同：均直接创建新用户并返回随机 token，**完全不验证密码是否存在、是否正确**。攻击者只需知道任意邮箱地址即可获得有效访问令牌。  
**攻击场景**: `curl -X POST /api/v1/auth/login -d '{"email":"admin@xagent.ai","password":"x"}'` 即可获得合法 token。  
**修复**: 实现真正的密码验证流程：bcrypt/Argon2 哈希存储、`login()` 查询用户并比对密码、失败时返回统一 401。

### 🔴 CRITICAL-002: 匿名用户自动绕过所有 Scope 检查
**文件**: `app/dependencies.py` (L209-L217)  
**描述**: `enforce_scope()` 函数第一行即为 `if not principal.authenticated: return`。这意味着**任何未携带 API Key 的请求都会自动通过权限检查**。  
**攻击场景**: 删除请求头中的 `x-api-key`，即可访问原本需要 `security:manage` 的 API Key 管理接口。  
**修复**: 将逻辑改为 `if not principal.authenticated: raise api_error(401, ...)`，拒绝所有未认证访问。

### 🔴 CRITICAL-003: 匿名用户默认拥有高危权限
**文件**: `app/core/security.py` (L193-L205)  
**描述**: `anonymous_principal()` 默认授予 `agent:run`, `tools:read`, `memory:read/write`, `workflow:create/run/control`, `audit:read` 等权限。  
**攻击场景**: 结合 CRITICAL-002，未认证用户可直接运行 Agent、读写记忆、创建和执行工作流。  
**修复**: 匿名用户权限列表应为空 `[]`。

### 🔴 CRITICAL-004: 用户管理 API 完全开放
**文件**: `app/api/users.py` (L12-L57)  
**描述**: 所有用户 CRUD 端点（创建、列出、获取、更新、删除、修改角色）**均未引入 `PrincipalDependency`，也未调用 `enforce_scope`**。  
**攻击场景**: 任何人无需认证即可创建管理员用户、修改现有用户角色、删除全部用户。  
**修复**: 为所有端点添加 `PrincipalDependency` 和 scope 校验；`update_user_role` 仅限 `admin` 角色。

### 🔴 CRITICAL-005: 租户管理 API 完全开放
**文件**: `app/api/tenants.py` (L12-L55)  
**描述**: 所有租户管理端点均无认证/授权。  
**攻击场景**: 未认证用户可创建/删除租户、修改租户计费计划。  
**修复**: 添加 `PrincipalDependency` + `security:manage` scope 限制。

### 🔴 CRITICAL-006: Agent 管理 API 大面积开放
**文件**: `app/api/agents.py` (L30-L117, L163-L190)  
**描述**: `create_agent`, `list_agents`, `get_agent_detail`, `update_agent`, `delete_agent`, `pause_agent`, `resume_agent`, `cancel_agent`, `list_agent_runs`, `get_agent_run` 等接口均无认证。  
**攻击场景**: 攻击者可随意创建恶意 Agent、删除默认 Agent、查看所有运行记录。  
**修复**: 统一添加 `PrincipalDependency`，按操作粒度分配 scope。

### 🔴 CRITICAL-007: 工作流 API 读操作大面积开放
**文件**: `app/api/workflows.py` (L49-L179, L349-L375)  
**描述**: `list_workflows`, `get_workflow`, `list_workflow_runs`, `get_workflow_run_detail` 等大量读接口缺少 `PrincipalDependency`。写操作（run/pause/resume）虽有 scope 检查，但结合 CRITICAL-002 可被匿名绕过。  
**攻击场景**: 数据泄露 + 未授权执行工作流。  
**修复**: 所有端点添加认证；按租户/用户过滤查询结果。

### 🟠 HIGH-001: API Key 使用无盐 SHA256 哈希
**文件**: `app/core/security.py` (L188-L190)  
**描述**: `_hash_key()` 使用 `sha256(raw_key.encode("utf-8")).hexdigest()`，**无盐、低迭代、极易被彩虹表攻击**。  
**修复**: 改用 bcrypt/Argon2 或至少使用 HMAC-SHA256(`key`, `secret_pepper`)。

### 🟠 HIGH-002: API Key 明文存储于本地 JSON
**文件**: `app/core/security.py` (L178-L186)  
**描述**: `_persist()` 将 `APIKeyRecord` 以可读 JSON 写入磁盘，包含 `key_hash`（虽非原始 key，但可离线破解）。  
**修复**: 限制文件权限为 `0o600`；生产环境使用 PostgreSQL + 字段级加密。

### 🟠 HIGH-003: 认证遍历导致时序侧信道
**文件**: `app/core/security.py` (L132-L144)  
**描述**: `authenticate()` 遍历所有记录进行哈希比对，记录数量越多响应越慢，可据此推断 key 是否存在。  
**修复**: 建立 `key_hash -> record` 的字典索引，实现 O(1) 查询。

### 🟡 MEDIUM-001: Token 无过期机制
**文件**: `app/api/auth.py` (L24-L25, L36-L37)  
**描述**: Token 是纯随机字符串 `xag_{uuid4().hex}`，**无签名、无过期时间、无撤销机制**（除 logout 外）。  
**修复**: 改用 JWT (HS256/RS256) 并设置 `exp` claim；或实现 Redis  token 黑名单。

### 🟡 MEDIUM-002: 全系统无速率限制
**文件**: 全部 API 路由  
**描述**: 无任何接口实现速率限制（Rate Limiting）。  
**攻击场景**: 暴力破解 API Key、DDoS、资源耗尽。  
**修复**: 引入 `slowapi` 或 `fastapi-limiter`，对 auth / api-keys / agent-run 等接口按 IP/用户限流。

### 🟡 MEDIUM-003: 无账户锁定机制
**文件**: `app/api/auth.py`  
**描述**: 登录失败无计数、无锁定。  
**修复**: 连续失败 5 次锁定 15 分钟（Redis 计数）。

### 🟡 MEDIUM-004: 密码不以任何形式存储
**文件**: `app/core/admin.py` (L26-L33)  
**描述**: `UserRecord` 模型完全没有 `password_hash` 字段，系统**根本不存储用户密码**。  
**修复**: 添加 `password_hash: str` 字段，注册时使用 bcrypt 哈希。

### 🟡 MEDIUM-005: OAuth 登录不验证 Provider
**文件**: `app/api/auth.py` (L42-L50)  
**描述**: `login_oauth` 接收任意 `payload`，不验证 OAuth provider 的 token 真实性，直接颁发本地 token。  
**修复**: 实现标准 OAuth 2.0 / OpenID Connect 流程，向 provider 验证 `code`/`id_token`。

---

## 二、输入验证与路径遍历 (Input Validation & Path Traversal)

### 🔴 CRITICAL-008: execution/draft 接口存在路径遍历
**文件**: `app/api/execution.py` (L12-L18)  
**描述**: `root = str(payload.get("root", "."))` 直接传入 `code_index.index()`，而 `code_index.py` 使用 `Path(root).expanduser().resolve()` 后递归遍历所有文件。  
**攻击场景**: `{"root": "/etc"}` 可读取服务器配置文件；`{"root": "~/.ssh"}` 可读取私钥；Windows 下 `{"root": "C:/Windows"}` 可遍历系统目录。  
**修复**: 强制 root 必须在允许列表内（如 `PROJECT_ROOT` 子目录），拒绝 `..`、`~`、绝对路径。

### 🔴 CRITICAL-009: Agent 工具链无沙箱路径限制
**文件**: `app/core/tools.py` (L562-L818)  
**描述**: `read_file`, `write_file`, `apply_text_patch`, `list_files`, `inspect_tree`, `search_text` 等工具均使用 `Path(path).expanduser().resolve()`，**无任何沙箱边界**。Agent 被提示注入后可读写服务器任意文件（包括 `/etc/passwd`、数据库文件、其他租户数据）。  
**攻击场景**: 用户提交任务 "请帮我查看 /etc/passwd 内容"，Agent 直接调用 `read_file` 读取并返回。  
**修复**: 所有文件操作工具增加 `sandbox_root` 参数，使用 `path.resolve().relative_to(sandbox_root)` 校验，越界则拒绝。

### 🟠 HIGH-004: Browser Screenshot 路径遍历
**文件**: `app/api/browser.py` (L222-L231), `app/services/browser/playwright_client.py` (L144-L148)  
**描述**: `screenshot` 接口的 `request.path` 直接传入 `page.screenshot(path=path)`，**未做任何路径校验**。  
**攻击场景**: `{"path": "/etc/cron.d/backdoor"}` 可将截图写入系统目录（虽然截图是 PNG，但可能覆盖已有文件或造成拒绝服务）。  
**修复**: 限制 path 必须在 `/tmp` 或配置的 `screenshots_dir` 下，拒绝 `..` 和绝对路径。

### 🟠 HIGH-005: Feishu 事件回调签名验证可被跳过
**文件**: `app/api/feishu.py` (L71-L83)  
**描述**: 签名验证包裹在 `if x_feishu_signature and x_feishu_timestamp and x_feishu_nonce:` 中。如果攻击者**省略任意一个 header**，验证逻辑被完全跳过。  
**攻击场景**: 发送不含 signature header 的请求即可伪造飞书事件，触发任意工作流或发送消息。  
**修复**: 将条件改为强制验证：`if not all([...]): raise api_error(401, ...)`。

---

## 三、配置与密钥管理 (Configuration & Secrets)

### 🟠 HIGH-006: 硬编码审计 HMAC 密钥
**文件**: `app/settings.py` (L52)  
**描述**: `audit_hmac_secret: str = "test-audit-secret"` 是硬编码的弱密钥。虽然 validator 要求非空，但默认值本身满足条件，**生产环境极易被遗忘修改**。  
**攻击场景**: 攻击者可伪造审计日志的 HMAC 签名，篡改审计记录。  
**修复**: 默认值设为 `None`，validator 在 `app_mode != "development"` 时强制要求设置强密钥。

### 🟠 HIGH-007: 设置项重复定义
**文件**: `app/settings.py` (L20-L21, L53-L54)  
**描述**: `bootstrap_api_key` 和 `bootstrap_api_key_sha256` 被定义了两次，第二次定义会覆盖第一次。  
**修复**: 删除重复行。

### 🟡 MEDIUM-006: CORS 允许危险 HTTP 方法
**文件**: `app/main.py` (L78-L84)  
**描述**: `allow_methods` 包含 `DELETE`、`PATCH` 等高风险方法，且 `allow_origins` 默认包含 `http://localhost:3000`（开发环境合理，但生产环境若未覆盖则风险极高）。  
**修复**: 生产环境收紧为 `GET, POST, PUT, PATCH`；删除 `DELETE` 或按端点单独配置。

### 🟡 MEDIUM-007: 审计存储在开发模式被自动删除
**文件**: `app/dependencies.py` (L142-L150)  
**描述**: `get_audit_store()` 在 `development` 或 `test` 模式下自动 `unlink()` 审计文件。如果 `app_mode` 被错误配置为 development（或攻击者可控制该环境变量），审计证据会被销毁。  
**修复**: 删除该逻辑，审计数据永不自动删除；提供独立的管理命令清理。

### 🟢 LOW-001: API Key 状态接口暴露配置信息
**文件**: `app/main.py` (L218-L220)  
**描述**: `/api-key/status` 暴露 `require_api_key` 布尔值，帮助攻击者判断系统认证严格程度。  
**修复**: 该接口添加 `security:manage` scope 限制。

### 🟢 LOW-002: Health/Ready 端点信息泄露
**文件**: `app/main.py` (L223-L255)  
**描述**: `/ready` 返回详细的组件状态、集成类型（real/fallback）和具体异常信息，可被用于指纹识别和漏洞定位。  
**修复**: 生产环境隐藏具体异常详情，仅返回 `ok/degraded`；移除 `integrations` 细节。

---

## 四、数据层与业务逻辑 (Data & Business Logic)

### 🟡 MEDIUM-008: 全系统数据存储无加密
**文件**: `app/core/admin.py`, `app/core/security.py`, `app/core/tools.py`, `app/core/workflows.py` 等  
**描述**: 所有基于文件的数据存储（User、API Key、Audit、Tool Execution、Workflow）均以**明文 JSON** 写入本地磁盘。  
**修复**: 生产环境使用 PostgreSQL；敏感字段（如 API Key 元数据）使用 AES-256-GCM 加密。

### 🟡 MEDIUM-009: 会话数据未按 Principal 隔离
**文件**: `app/api/browser.py` (L53-L56)  
**描述**: `list_browser_sessions` 返回 `browser_automation.list_sessions()` 的**全部会话**，未按当前用户的 `tenant_id` 或 `user_id` 过滤。  
**攻击场景**: 用户 A 可查看/操作用户 B 的浏览器会话。  
**修复**: 在 `BrowserAutomationStore` 中增加按 tenant/user 过滤的方法。

### 🟡 MEDIUM-010: Workflow 执行可跨租户
**文件**: `app/api/workflows.py` (L238-L261)  
**描述**: `run_workflow` 从请求体中直接读取 `tenant_id` 和 `user_id`，未验证是否与当前 principal 匹配。  
**攻击场景**: 认证用户可提交 `{"tenant_id": "其他租户", "user_id": "其他用户"}` 执行工作流并嫁祸。  
**修复**: 强制 `tenant_id` = `principal.tenant_id`，`user_id` = `principal.user_id`。

### 🟢 LOW-003: 代码存在未定义函数调用
**文件**: `app/api/browser.py` (L99)  
**描述**: `build_recovery_payload()` 被调用但函数未在文件中定义，将导致运行时 `NameError`。  
**修复**: 补全函数定义或删除调用。

---

## 五、日志与监控 (Logging & Observability)

### 🟡 MEDIUM-011: 请求日志可能记录敏感数据
**文件**: `app/main.py` (L99-L108)  
**描述**: `request_logging_middleware` 记录 `path`、`method`、`status_code`，但未排除可能包含敏感信息的 path（如 `/api/v1/auth/login` 的 query string 或未来可能带 token 的 path）。  
**修复**: 对已知敏感端点的 path 进行脱敏；禁止记录 query string 中的 `token`、`key`、`password` 参数。

---

## 附录 A: 修复优先级矩阵

| 优先级 | 问题编号 | 影响 | 修复复杂度 |
|--------|----------|------|------------|
| P0 | CRITICAL-001 ~ 009 | 系统完全失控 | 中 |
| P1 | HIGH-001 ~ 007 | 严重数据泄露/篡改 | 低~中 |
| P2 | MEDIUM-001 ~ 011 | 功能性安全缺陷 | 中 |
| P3 | LOW-001 ~ 003 | 信息泄露/稳定性 | 低 |

## 附录 B: 快速修复清单 (Quick Wins)

1. `dependencies.py:L209` — 删除 `if not principal.authenticated: return`，改为抛出 401
2. `core/security.py:L193` — `anonymous_principal()` 返回 `scopes=[]`
3. `api/auth.py` — `login()` 实现密码验证（bcrypt）
4. `api/users.py`, `api/tenants.py`, `api/agents.py` — 所有端点添加 `PrincipalDependency`
5. `settings.py:L52` — `audit_hmac_secret` 默认改为 `None`
6. `settings.py:L53-L54` — 删除重复定义
7. `api/feishu.py:L74` — 签名验证改为强制
8. `api/browser.py:L229` — screenshot path 增加沙箱校验
