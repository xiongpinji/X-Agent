# 12. X-Agent 安全与企业合规就绪度审计报告

- **角色标签**: 安全合规审计员
- **任务范围**: 审计 X-Agent Core (v0.1.0) 的认证 (bcrypt/JWT)、授权与 RBAC、多租户隔离、policy engine、审批工作流、审计日志完整性、密钥/凭据管理、路径沙箱、速率限制、依赖漏洞、数据加密与隐私, 以及 SECURITY_DECISIONS.md 决策落实状态; 对标企业采购常见要求 (SOC 2 类控制项、SSO/SAML、SCIM、数据驻留、审计留存) 逐项给出差距。
- **审计日期**: 2026-07-19
- **审计方法**: 逐行阅读后端关键安全代码与配置文件 (所有结论附文件路径+行号), 区分"文档宣称"与"代码实际实现"; 竞品与企业要求部分使用 2025-2026 公开资料并标注来源, 无法验证处明确标注。
- **总体评分**: **安全合规就绪度 35 / 100**(单机自用/内网演示可用; 距离企业采购准入差距显著)

---

## 一、总体结论

X-Agent 在**单机/开发模式安全基线**上做了不少扎实工作: bcrypt 密码散列、API Key bcrypt 存储 + 90 天过期、生产模式强制强密钥、HMAC 签名 + SHA-256 哈希链审计日志、路径穿越/符号链接防护、CSRF 中间件、安全响应头、登录锁定。这些是真实实现、有代码证据的。

但面向**企业商用交付**, 存在三类系统性问题:

1. **"僵尸安全代码"**: 大量企业级安全模块 (SSO/SAML/OIDC、enterprise RBAC、增强审计、API Key 管理器、JWT 密钥轮换、SCIM 类治理) 以核心库形式存在, 但其 API 路由**未挂载进 FastAPI 应用** (`backend/app/main.py:496-547`), 实际运行时不可达——属于"文档/代码宣称有, 实际交付没有"。
2. **认证体系名不副实**: 配置中有 `XAGENT_JWT_SECRET` 与 JWT 密钥轮换模块, 但**全代码库没有任何 `jwt.encode` 调用**, 登录实际签发的是不透明 UUID 会话 token (内存/Redis 存储); 唯一一处 `jwt.decode` 在 OIDC 流程中**显式关闭签名校验**。
3. **企业合规硬项缺失**: 无真实可用的 SSO/SAML (实现为简化版且未挂载)、无 SCIM、无数据驻留、无审计留存/归档策略、用户库为进程内存 (重启即丢)、SAML/OIDC 签名校验为占位实现。

---

## 二、分项审计发现

### 2.1 认证 (Authentication)

| 宣称 | 代码实际 | 证据 |
|---|---|---|
| bcrypt 密码散列 | ✅ 真实: `bcrypt.hashpw(..., gensalt(rounds=12))` | `backend/app/core/admin.py:234-235` |
| JWT 认证 | ❌ **未实现**: 登录签发 `f"xag_{uuid4().hex}"` 不透明 token, 存内存 dict 或 Redis; 全仓库无 `jwt.encode` | `backend/app/api/auth.py:81-98`; grep 仅命中 `saml_sso.py` 的 decode |
| JWT 密钥轮换 | ⚠️ 模块存在 (`JWTKeyRotationStore`, HS256), 但其 API 路由未挂载, 且无 JWT 签发方可用 | `backend/app/core/jwt_key_rotation.py:29,46`; `backend/app/api/jwt_key_rotation.py` 未出现在 `main.py:496-547` |
| OIDC 登录 | ❌ 高危占位: `jwt.decode(id_token, options={"verify_signature": False})`, 注释自承 "Should verify in production" | `backend/app/core/saml_sso.py:498-504` |
| OAuth 登录 (google/github/microsoft) | ❌ 端点存在但返回 501 "not yet implemented" | `backend/app/api/auth.py:359-364` |
| 邮箱验证 / 密码重置邮件 | ❌ verify-email 返回 501; reset-password 的 "发送邮件" 为 TODO, token 仅存服务端 | `backend/app/api/auth.py:416-428, 490-491` |
| 登录防爆破 | ✅ 部分真实: 5 次失败锁 15 分钟 + 恒定时间比较 + 登录限速 | `backend/app/api/auth.py:52-54,169-192`; `backend/app/main.py:367-369` |
| Bootstrap Key | ✅ 支持明文或 SHA-256 哈希比对 (compare_digest), 并有强制更换检查 | `backend/app/dependencies.py:239-249`; `backend/app/core/bootstrap_key_enforcer.py` |
| `XAGENT_JWT_SECRET` / `XAGENT_ENCRYPTION_KEY` 生产强校验 | ✅ 真实: 生产模式拒绝默认值、<32 字符、无大写+数字 | `backend/app/settings.py:87-127` |

**差距**: 企业采购要求的标准化 SSO 会话 (SAML/OIDC) 与可吊销、可跨服务验证的 token 体系 (JWT/JWK) 均不可用; 现有会话 token 无 JTI/签发方声明, 吊销列表为进程内存或单 Redis, 无多实例一致性保证; MFA/WebAuthn 代码存在于 `backend/app/core/sso/` 但路由未挂载。

### 2.2 授权与 RBAC

- ✅ 已实现: 5 角色 (admin/developer/user/viewer/anonymous) × scope 列表, 匿名主体零权限, `enforce_scope` 在多数路由调用 (`backend/app/core/security.py:13-50`; `backend/app/dependencies.py:252-268`)。
- ⚠️ 角色模型**硬编码**, 无自定义角色/权限点, 无资源级 (object-level) ACL——`ROLE_SCOPES` 是模块级常量, 修改需改代码。
- ⚠️ 存在两套互不连通的授权体系: `security.py` 的 scope RBAC (实际使用) 与 `api_key_manager.py`/`advanced_rbac.py` 的 PermissionLevel/资源级 RBAC (**路由未挂载, 未生效**)。
- ⚠️ `viewer` 角色拥有 `audit:read` (`security.py:48`), 配合下文 2.6 的跨租户审计查询参数, 构成低权限用户横向读取他租户审计日志的风险。

### 2.3 多租户隔离

- ✅ 提供 `TenantIsolationValidator.validate_tenant_access / filter_by_tenant / build_tenant_filter` 与 `require_tenant_isolation` 装饰器, 逻辑正确 (admin 放行, 其余比对 tenant_id) (`backend/app/core/tenant_isolation.py:66-147`)。
- ❌ **核心中间件未挂载**: `TenantIsolationMiddleware` 未出现在 `main.py` 的 `add_middleware` 列表 (仅 CORS + CSRF, `main.py:351-360`)。且该中间件本身**信任客户端 `x-tenant-id` 请求头** (`tenant_isolation.py:44`), 即使挂载也存在租户伪造风险。
- ❌ `main.py:404-436` 的内联租户中间件读取 `request.scope.get("principal")`, 但**代码库中无任何位置向 `request.scope` 写入 principal**(principal 仅在路由依赖 `get_current_principal` 内解析)——该中间件是**死代码, 无实际拦截力**。
- ⚠️ 数据库层无行级安全 (RLS) 或租户分区; SQLite 默认单文件 (`settings.py:33`), 租户隔离完全依赖应用层自觉调用 filter, 任何一个遗漏 filter 的查询即越权。

### 2.4 Policy Engine (工具策略)

- ✅ 真实可用: `ToolPolicyEngine` 默认阻断 HIGH/CRITICAL 风险工具并要求审批, scope 三重校验 (`tool:{name}` / `tools:*` / `tools:read`) (`backend/app/core/policy.py:22-42`); `enable_high_risk_tools` 默认 False (`settings.py:67`)。
- ⚠️ 为硬编码 "Phase 0" 引擎 (代码注释自承), 无持久化策略、无租户/角色差异化策略、无 OPA/Rego 类外部策略集成; 沙箱配置档仅 "locked"/"process"/"none" 三档字符串, 未见与 OS 级隔离 (seccomp/容器) 的强制绑定证据。

### 2.5 审批工作流 (Approval)

- ✅ 有完整记录模型与状态机 (pending→approved/rejected→executed), 审批决策写入审计日志 (`backend/app/core/approvals.py:18-45`; `backend/app/api/approvals.py:151,167`)。
- ❌ **审批人身份可伪造**: `ApprovalDecisionRequest.decided_by` 由**请求体**传入且默认 `"anonymous"` (`approvals.py:48-50`), approve/reject 端点不将其覆盖为已认证 principal (`api/approvals.py:139-168`)——审计记录中的"谁批的"不可信。
- ❌ **无职责分离 (SoD)**: 发起审批的 actor 与审批人不做互斥校验, 同一管理员可自提自批。
- ❌ 审批操作**不校验记录 tenant_id 与 principal.tenant_id 是否一致**, `list_approvals` 接受任意 `tenant_id` 过滤参数 (`api/approvals.py:32-41`)。
- ⚠️ 审批存储为单 JSON 文件全量重写 (`approvals.py:209-217`), 无并发写保护以外的 durability 保证, 无审批超时/升级 (escalation) 机制。

### 2.6 审计日志完整性

- ✅ **亮点**: SHA-256 哈希链 (prev_hash) + 可选 HMAC-SHA256 签名; 生产模式无 HMAC secret 直接拒绝启动 (fail-fast); `verify_chain` 支持全链校验; 损坏行加载时告警跳过 (`backend/app/core/audit.py:56-62, 81-109, 151-197`); 开发模式使用临时密钥并明确告警 (`backend/app/dependencies.py:148-165`)。
- ❌ **跨租户读取漏洞**: `GET /api/v1/audit-logs` 接受任意 `tenant_id` 查询参数, 仅要求 `audit:read` scope, 不校验该参数是否等于 principal 所属租户 (`backend/app/api/audit.py:53-60`)。viewer 角色即持有 `audit:read`。
- ❌ **无留存/轮转策略**: 核心审计 JSONL 只追加不轮转, 无 retention、归档、WORM/对象锁存储外送; `audit_enhanced.py` 虽有 7 年留存默认值 (`core/audit_enhanced.py:149`) 与合规报告, 但其路由 (`api/audit_enhanced.py`) **未挂载**。
- ⚠️ 审计详情 `details` 字段无自动脱敏挂钩——`log_sanitizer.py` 的 `LogSanitizer` 仅在本文件内实例化, 未接入 logging 配置或审计写入路径 (grep 仅命中自身定义)。
- ⚠️ 无审计外送 (SIEM/syslog/webhook) 通道; `audit_export.py`/`enterprise_audit.py` 存在但同样未接线。

### 2.7 密钥与凭据管理

- ✅ API Key: `xag_` 前缀 + `token_urlsafe(32)` 生成, bcrypt(rounds=12) 存储, 90 天强制过期, 支持吊销与 last_used 追踪 (`backend/app/core/security.py:136-180, 243-245`)。
- ✅ LLM 等第三方密钥走环境变量 (`settings.py:26-30`), `.gitignore` 已覆盖 `.env` 与 `data/api_keys.json` (`.gitignore:32-38`)。
- ❌ **无 KMS/Vault 集成**, 无主密钥轮换机制 (encryption_key 更换后旧密文不可解); 密钥材料即环境变量字符串。
- ❌ SECURITY_DECISIONS.md **D-3 高风险项未关闭**: `data/api_keys.json` 曾进入 git 历史, 决策栏空白; 本次审计执行 `git ls-files`/`git log` 失败 (exit 128, 仓库状态异常), **历史是否已清洗 = 待验证**。当前 `data/` 目录仅存 audit/runs/tool_executions 三个 jsonl, 未见 api_keys.json 实体文件。
- ⚠️ 仓库根目录存在 `.env.production` 文件 (未读取其内容), 需人工确认其未被 git 跟踪且权限受控。
- ⚠️ `access_control.py:90-92` 允许 `?api_key=` 查询参数传 key (注释自承 "less secure, for testing only")——会进入访问日志/代理日志; 所幸该中间件未挂载。

### 2.8 路径沙箱

- ✅ 质量较高: 符号链接检测在 `resolve()` 之前逐段进行 (修复了先解析后检测的失效问题), 强制 sandbox_root 相对性校验, API 语义化报错 (`backend/app/core/path_security.py:44-89`); SECURITY_DECISIONS.md 亦声明所有文件工具走 `_resolve_tool_path`。
- ⚠️ `get_path_validator` 为全局单例且**默认无 sandbox_root** (`path_security.py:148-149`: 未设 root 时 `is_within_sandbox` 恒为 True)——实际防护强度取决于每个调用方是否显式传入 root, 审计无法在不逐个核对全部文件工具的情况下断言"所有调用点都传了 root", 标记为**部分待验证**。

### 2.9 速率限制

- ✅ 运行中实际生效: `main.py:363-376` 内联中间件——登录 10 次/分/IP、注册 5 次/分/IP、通用 API 100 次/分/IP。
- ❌ **内存单进程实现**, 多实例部署下限额按实例数放大; 无按 API Key/用户/租户维度的配额; 无 429 Retry-After 头。
- ❌ `core/rate_limiter.py` (含 Redis 后端与 `RATE_LIMITS` 预定义, 登录 5 次/15 分钟等更严配置) **是死代码**——grep 显示无任何调用方, 实际生效配置与设计文档不一致。

### 2.10 依赖漏洞

| 报告 | 扫描日期 | 覆盖 | 结果 | 审计评价 |
|---|---|---|---|---|
| `dependency-pip-audit-report.json` | 2026-05-26 | 28 个包 | 0 漏洞, PASS | ⚠️ 覆盖不全 |
| `dependency-safety-report.json` | 2026-05-26 | 28 个包 | 0 漏洞 | ⚠️ 覆盖不全 |

- ❌ **覆盖率严重不足**: `requirements.txt` 有 84 行非空依赖声明, `requirements-lock.txt` 有 287 行, 两份报告仅扫描 28 个包 (且报告内 `dependency_tree` 仅列 14 个直接依赖)。FastAPI 被声明为 `>=0.115.0` 浮动版本 (`requirements.txt:8`), 与"Locked versions for reproducibility and security"的文件头注释自相矛盾。
- ❌ 报告距今 **54 天** (2026-05-26 → 2026-07-19), 期间新披露 CVE 未覆盖; 无 CI 定时扫描证据 (仓库未见 GitHub Actions/CI 中的 audit 步骤, 待验证)。
- ❌ 前端 (`frontend/`)、桌面端 (`desktop/`)、移动端 (`mobile/`) 的 npm 依赖**完全无漏洞报告**。
- 结论: "0 漏洞"不能作为交付证据, 只能视为一次性部分抽测。

### 2.11 数据加密与隐私

- ✅ 静态加密组件质量好: AES-256-GCM, v2 格式随机 salt + PBKDF2-SHA256 100k 迭代派生, 96-bit nonce, 向后兼容 v1 (`backend/app/core/data_encryption.py:22-55, 69-83`); 敏感字段映射表已定义 (`data_encryption.py:222-228`)。
- ⚠️ `SENSITIVE_FIELDS` 仅声明, 未见在存储路径上强制调用的证据 (grep 未见 `SensitiveFieldEncryptor` 在 memory/run/trace 存储中被使用——**部分待验证**)。
- ⚠️ 云端 `cloud/encryption_service.py` (RSA-4096 + AES-256 + "零知识证明"模型) 存在, 但 `cloud/sync_service.py` 中加密仅体现为 `encrypted: bool = False` 标志位 (行 72-73), 未见实际加解密调用——**宣称的端到端加密基本未接线**。
- ❌ 传输加密: 应用自身不提供 TLS; `docker-compose.yml` 无 443/证书配置 (仅 LLM 端点的 https URL), TLS 依赖 Helm/nginx ingress (`deployment/helm/values-production.yaml:117-118` ssl-redirect) ——compose 部署形态下传输明文, 文档中未见强制说明。
- ❌ 无隐私/GDPR 功能: 无数据主体删除 (right-to-erasure) 接口的用户数据级联清除、无同意管理、无 PII 分类执行 (`data_governance.py` 有分类/掩码能力但路由未挂载)、ROADMAP.md:77 自承 "Compliance reporting (GDPR, SOC 2)" 为未完成项。
- ❌ 无数据驻留 (data residency) 设计: 单 region 假设, 无 region 标签/路由。

### 2.12 SECURITY_DECISIONS.md 落实状态

文件日期 2026-06-05, 状态 "Pending owner approval on HIGH-RISK items"。四项待决决策 (**D-1 API key 强制、D-2 webhook secret、D-3 git 历史密钥清洗【高危】、D-4 高危工具审批流**) 的 "Owner decision" 栏**全部空白**——即所有已知风险决策处于悬置状态, 无关闭证据。文件宣称的"已加固"项 (settings 校验、哈希链、路径防护) 经本次代码核对**属实**; 但第 65 行宣称 "PBKDF2HMAC password hashing" 与实际不符——密码实际用 **bcrypt** (`admin.py:235`), PBKDF2 仅用于数据加密密钥派生, 文档表述有误。

---

## 三、对标企业采购要求: 逐项差距表

企业采购基线参照: 2026 年企业级 AI 编码/agent 产品的常见准入清单——SOC 2 Type II、SAML SSO、SCIM  provisioning、审计日志、数据驻留选项、训练数据排除、VPC/自托管 (来源: agentic.ai《Best Enterprise AI Coding Agents in 2026》, 2026-04-07, https://agentic.ai/best/enterprise-coding-agents, 二手行业综述, 权威性一般, 具体条款**待与目标客户的实际采购清单核对**)。

| # | 企业要求 | X-Agent 现状 | 差距评级 |
|---|---|---|---|
| 1 | SSO (SAML 2.0) | 代码存在但**签名验证只是检查 XML 里有没有 "Signature" 字符串** (`enterprise_sso.py:317-323`), 路由未挂载 | 🔴 严重 (不可用且实现不安全) |
| 2 | SSO (OIDC) | id_token **关闭签名校验** (`saml_sso.py:501-504`), 路由未挂载 | 🔴 严重 |
| 3 | SCIM 用户 provisioning | 无任何实现 (grep 全仓库仅命中第三方包 langfuse 的 venv 文件) | 🔴 缺失 |
| 4 | MFA / WebAuthn | `core/sso/mfa_manager.py`、`webauthn_provider.py` 存在, 路由未挂载 | 🟠 有代码未交付 |
| 5 | RBAC | 5 角色硬编码 scope 模型已生效; 无自定义角色、无资源级 ACL | 🟡 基础可用 |
| 6 | 多租户隔离 | 校验器逻辑正确但中间件未挂载; 主应用内联中间件为死代码; 审计/审批接口可跨租户查询 | 🔴 严重 |
| 7 | 审计日志防篡改 | 哈希链 + HMAC 签名 + 生产强制, **此项达标且是亮点** | 🟢 良好 |
| 8 | 审计留存 (如 1-7 年) / 外送 SIEM | 核心审计无轮转/留存; 7 年留存与合规模块未挂载; 无外送 | 🔴 缺失 |
| 9 | SOC 2 控制项 (CC6.x 访问控制 / CC7.x 监控 / CC8.x 变更) | 部分技术控制存在 (CC6.1 认证、CC6.6 边界防护部分), 但无变更管理流程证据、无可用性/监控合规证据、无渗透测试/审计报告 | 🔴 无法通过审核 |
| 10 | 数据加密 (静态/传输) | 静态: AES-256-GCM 组件合格但未全链路接线; 传输: 应用层无 TLS, compose 无明文防护说明 | 🟠 部分 |
| 11 | 数据驻留 / 区域化 | 无 | 🔴 缺失 |
| 12 | 隐私 (GDPR 删除权/同意/PII 治理) | 数据治理模块存在但未挂载; 无删除权级联 | 🔴 缺失 |
| 13 | 供应链安全 (依赖扫描/SBOM/签名) | 一次性部分扫描 (28/84+ 包), 无 SBOM, 无 CI 强制 | 🟠 部分 |
| 14 | 密钥管理 (KMS/轮换) | env 变量 + bcrypt/哈希存储良好; 无 KMS, 无主密钥轮换 | 🟠 部分 |
| 15 | 会话/token 安全 | 不透明 token + 吊销可用; **但无 JWT/JWK 标准体系**, OAuth/邮箱流程 501 | 🟠 部分 |
| 16 | 审批与职责分离 | 审批流存在; decided_by 可伪造、无 SoD、无租户校验 | 🟠 有框架不达标 |
| 17 | 安全响应头/CSP | 头齐全; **CSP 允许 `unsafe-inline` + `unsafe-eval`** (`main.py:455-456`), XSS 防护弱化 | 🟡 需收紧 |
| 18 | API 文档面暴露 | `/docs`、`/openapi.json` 在生产模式仍可匿名访问 (FastAPI 默认 + 无鉴权挂载) | 🟡 信息泄露 |
| 19 | 训练数据排除 / 客户数据隔离承诺 | 无相关机制或合同层文档 | 🔴 缺失 (需法务层补齐) |
| 20 | 渗透测试/安全评估报告 | 无 | 🔴 缺失 |

---

## 四、竞品安全/合规参照 (2025-2026 公开资料)

> 以下来源多为行业评测/媒体, 权威性中等, 具体认证状态建议以厂商官方 trust center 复核 (标注"待验证")。

- **OpenAI Codex / ChatGPT Enterprise**: 第三方评测称 Codex 企业侧提供 "SOC 2 Type 2, SSO, SCIM, audit logs, RBAC" (来源: nocode.mba《OpenAI Codex Review 2026》, 2026-06-08, https://www.nocode.mba/articles/openai-codex-review-2026, 二手评测, **待验证**); ChatGPT Enterprise 宣称 SOC 2 Type II、ISO 27001、HIPAA BAA、SSO/SCIM、10+ region 数据驻留 (来源: onyx.app 竞品综述, 2026-05-08, https://onyx.app/insights/best-enterprise-openclaw-options-2026, **待验证**)。→ 对照上表, X-Agent 在 SSO/SCIM/驻留/认证审核四项全面落后。
- **Hermes Agent (Nous Research)**: MIT 开源、自托管、无遥测、数据全部在用户服务器; v0.7.0 (2026-04-03) 增加凭据轮换; 但**本身不提供企业 SSO/RBAC/审计合规套件**, 其安全模式是"自托管即合规边界" (来源: aibuilderclub.com, 2026-06-02, https://www.aibuilderclub.com/blog/hermes-nous-research-self-improving-agent; ssojet.com 对比评测, 2026-06-07, https://ssojet.com/blog/ai-coding-agents-compared, 均**待验证**)。→ 启示: X-Agent 走自托管路线时, "无遥测 + 客户边界内运行 + 完整本地审计链"可成为对 Codex 云服务的差异化卖点, 但前提是先把本报告第二、三节的阻断项修掉——自托管客户的安全团队会逐条核对。
- **行业实践参照**: 2026 年 CLI agent 治理的五控制面 (访问控制/成本归因/审计日志/提示词 DLP/模型治理) (来源: futureagi.com, 2026-04-28, https://futureagi.com/blog/enterprise-controls-cli-coding-agents-gateway-field-guide-2026/, 厂商博客, **待验证**)。X-Agent 目前仅有第 1、3 面的雏形, 提示词 DLP 与模型治理为零。

---

## 五、提升方案 (按优先级)

**P0 — 商用阻断项 (不修则不能对外销售):**
1. **关闭 SECURITY_DECISIONS.md 全部悬置决策** (D-1~D-4), 尤其 D-3: 确认 `data/api_keys.json` 是否含真实密钥并清洗 git 历史 + 轮换 (当前 git 状态异常, 需先修复仓库)。
2. **修复认证体系名实不符**: 要么实现真正的 JWT (接入已存在的 `jwt_key_rotation` 并挂载路由), 要么删除/改名 `jwt_secret` 相关宣称; 立即删除或修复 `saml_sso.py:501-504` 的 `verify_signature: False` (不验证签名的 OIDC 比没有 OIDC 更危险)。
3. **补齐租户隔离链路**: 挂载 `TenantIsolationMiddleware` 并改为只信 principal 不信 `x-tenant-id` 头; 删除/修复 `main.py:404-436` 死中间件; 在审计、审批接口强制 `tenant_id == principal.tenant_id` (admin 除外)。
4. **审批流可信化**: `decided_by` 强制取自 principal; 增加 SoD 校验 (actor ≠ approver); 审批记录关联租户校验。

**P1 — 企业准入项 (进入采购短名单的前提):**
5. **SSO 真正可用**: 引入 python3-saml / authlib 做真实 XML 签名与断言校验, 挂载 `enterprise_sso`/`sso` 路由并补端到端测试; 实现 SCIM 2.0 (或至少 JIT provisioning + 停用接口)。
6. **持久化用户/租户库**: `UserStore`/`TenantStore` 从进程内存迁移到 Postgres, 支持重启不丢、多实例共享。
7. **审计留存与外送**: 给核心审计加轮转 + 可配置留存 (对齐 `audit_enhanced` 的 7 年默认) + syslog/webhook/S3(WORM) 外送; 挂载 `audit_enhanced` 合规报告路由。
8. **依赖治理**: 以 `requirements-lock.txt` 全量 (287 项) 重新跑 pip-audit + safety, 接入 CI 每日扫描; 补前端/桌面/移动端 npm audit; 生成 SBOM。
9. **传输加密与部署文档**: compose/文档中明确 TLS 终结要求, 提供参考 nginx/Caddy 配置; 收紧 CSP (去 `unsafe-eval`, nonce 化 inline script); 生产模式关闭 `/docs`。

**P2 — 差异化与认证 (6-12 个月):**
10. 挂载并完善 `data_governance`/`compliance_reporting`, 实现 GDPR 删除权级联、PII 分类掩码; 设计数据驻留 (region 标签 + 存储路由)。
11. KMS/Vault 集成与主密钥轮换; 提示词 DLP (密钥/PII 出向扫描); 模型治理 (允许的模型/供应商清单)。
12. 启动 SOC 2 Type I 差距评估 (建议外包), 建立变更管理/事件响应制度文档; 安排第三方渗透测试。

---

## 六、要点摘要

1. **总体评分 35/100**: 单机安全基线 (bcrypt、HMAC 审计链、路径防护、生产密钥校验) 真实可靠; 企业合规面 (SSO/SCIM/驻留/留存) 大面积缺失或未接线。
2. **最严重问题不是"没写", 而是"写了没接"**: SSO/SAML/OIDC/MFA、增强审计、资源级 RBAC、API Key 管理器、JWT 轮换、数据治理等模块的路由全部未挂载进 `main.py`, 构成"宣称 vs 交付"的系统性落差。
3. **现存高危缺陷 3 处**: OIDC id_token 关闭签名校验 (`saml_sso.py:501-504`); SAML 签名验证形同虚设 (`enterprise_sso.py:317-323`); 审计日志可跨租户查询 (`api/audit.py:53-60`)。
4. **认证名不副实**: 全系统无 `jwt.encode`, 登录实际是不透明 UUID token; `XAGENT_JWT_SECRET` 配置与 JWT 轮换模块空转。
5. **审计日志防篡改是唯一达标的企业级亮点** (哈希链 + HMAC + 生产 fail-fast), 但缺留存/外送, 且审批人身份可伪造削弱了其证明力。
6. **依赖"0 漏洞"证据无效**: 仅扫 28/84+ 个 Python 包、54 天前、前端零覆盖; 需以 lock 文件全量重扫并入 CI。
7. **SECURITY_DECISIONS.md 四项决策全部悬置**, 含一项 HIGH 风险 (git 历史密钥), 是 GA 前必须人工关闭的流程缺口。
8. **竞品启示**: Codex 云侧以 SOC2/SSO/SCIM/驻留全配打企业市场; Hermes 以自托管无遥测打数据主权市场——X-Agent 现实路径是先修 P0/P1 做"可自证安全的自托管方案", 再谈对标。
