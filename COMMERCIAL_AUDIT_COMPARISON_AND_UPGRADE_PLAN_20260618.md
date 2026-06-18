# X-Agent 三方商用交付审计对比与真实状态核验报告

**生成时间:** 2026-06-18
**核验对象:** 当前本地工作树 `D:\AI编程库\项目库\进行中的项目\X-Agent`
**当前 HEAD:** `2c648ff chore: checkpoint commercial delivery state`
**对比报告:**
- Claude Code / Claude 4.8: `商用交付独立审计报告_2026-06-18.md`
- ZCode / GLM 5.2: `audit_reports/COMMERCIAL_DEEP_AUDIT_20260618.md`
- Codex / GPT 5.5: `COMMERCIAL_DELIVERY_DEEP_AUDIT_20260618.md`

## 1. 总裁决

三方报告的方向基本一致: X-Agent 不是空壳，后端安全、RBAC、SAML、workspace、file preview、部署 hardening 和 RC 本地门禁已有较强基础；但如果按“完整商用交付”而不是“受控试点/RC 候选”评估，当前仍是 **No-Go for commercial GA**。

真实状态可以更精确地表述为:

- **可作为 RC 候选进入多模型深度审计。**
- **可做受控单租户/内测试点，前提是隐藏未收口功能入口。**
- **不可直接对外承诺完整商业 GA/SLA。**
- **域名/HTTPS/443 是最终 Stage3 的外部阻断之一，但不是唯一问题。** 即使排除域名，前后端 API 合约、未挂载/导入失败模块、Hosted workflow fail-open、生产 deploy placeholder、前端认证统一等仍需收口。

## 2. 当前机器核验证据

### 2.1 Git 与门禁

- 审计核验开始前工作树干净: `git status --porcelain=v1 -uall` -> `0`
- 本报告生成后当前新增未跟踪审计产物: `COMMERCIAL_AUDIT_COMPARISON_AND_UPGRADE_PLAN_20260618.md`, `COMMERCIAL_DELIVERY_DEEP_AUDIT_20260618.md`, `商用交付独立审计报告_2026-06-18.md`
- 分支: `fix/p0-p1-security-hardening...origin/fix/p0-p1-security-hardening [ahead 11]`
- 本地非严格 RC final gate: `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`
- 严格 Stage3 final gate: `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal ...` -> failed only on `staging_rehearsal_blocked`
- `python scripts/security_deployment_gate.py` -> OK
- `python scripts/route_auth_audit.py --json` -> `{"issues": [], "ok": true}`
- focused security regression previously rerun in this session: `100 passed, 1 skipped`

### 2.2 运行态路由核验

机器核验输出已保存到 `.xagent_runtime/reports/audit-compare-evidence-20260618.json`。

- `backend/app/api/*.py` 总文件: 137
- 含 APIRouter/路由定义文件: 113
- 当前 FastAPI app 中可从 endpoint module 识别到的已挂载 API 模块: 56
- 当前 FastAPI app 已挂载 APIRoute 数: 374
- 含路由但未挂载模块数: 56

未挂载模块包括:

`agent`, `agents_v2`, `analytics`, `api_keys`, `artifacts`, `artifacts_api`, `audit_enhanced`, `audit_export_api`, `backup`, `backup_monitoring`, `billing`, `code_execution`, `collaboration_enhanced`, `creative_studio`, `enterprise`, `enterprise_audit`, `enterprise_cluster`, `enterprise_im`, `enterprise_migration`, `enterprise_sso`, `files_v2`, `forum`, `forum_search`, `health_checks`, `i18n`, `jwt_key_rotation`, `llm_providers`, `mcp`, `media`, `oauth_routes`, `open_source`, `partners`, `personalization`, `plugin_dev_api`, `plugin_market`, `plugin_marketplace`, `plugin_marketplace_api`, `plugins`, `rbac_enforcement`, `recommendations_advanced`, `scheduler`, `search`, `search_api`, `sessions`, `skill_market`, `skill_market_advanced`, `skill_market_complete`, `skill_marketplace`, `skills`, `skills_api`, `sso`, `streaming_enhanced`, `subscriptions`, `templates`, `tenant_isolation`, `translation_management`, `vision`, `webhooks`。

重要修正: 这不等于 56 个 P0。必须按首版交付范围裁定:

- 前端真实调用且面向商业路径的未挂载模块 = P0/P1。
- 历史、候选、内部诊断、重复实现、非首版功能 = 应归档/删除/隐藏/列入后续版本，而不是直接挂载。
- 任何未来要挂载的模块，必须先通过 import、route auth audit、权限测试和前端合约测试。

### 2.3 前端 API 合约核验

静态提取 `frontend/src` 中 `/api/...` 引用:

- 唯一路径引用: 109
- 当前运行态可匹配: 63
- 当前运行态不可匹配: 46

高影响缺口集中在:

- `AnalyticsDashboard.tsx`: `/api/v1/analytics/*`
- `Forum.tsx`: `/api/v1/forum/*`
- `PluginMarket.tsx`: `/api/v1/plugin-market/*`
- `SkillMarket.tsx`, `SkillMarketComplete.tsx`: `/api/v1/skill-market/*`
- `TemplateMarketplacePage.tsx`, `TemplateEditor.tsx`, `TemplateInstantiationWizard.tsx`: `/api/v1/templates/*`
- `pushNotificationManager.ts`: `/api/v1/notifications/subscribe`
- `RealtimeVisualization.tsx`: `/api/v1/streaming/stream/{id}`

前端认证问题也成立:

- `frontend/src/services/api.ts` 使用 axios interceptor，会注入 `Authorization: Bearer <auth_token>`。
- `frontend/src/services/apiClient.ts` 自己封装 fetch，但默认 headers 只含 `Content-Type`，不会自动注入 token。
- 多个组件直接裸 `fetch(...)` 或 `new EventSource(...)`，没有统一认证/401 处理/CSRF/stream token 策略。

### 2.4 关键模块 import 核验

| 模块 | 当前 import 状态 | 结论 |
| --- | --- | --- |
| `forum` | OK, 26 routes | 存在但未挂载；若纳入首版，需要安全审计与前端合约测试。 |
| `plugin_market` | OK, 12 routes | 存在但未挂载；前端正在调用，是 P0 合约缺口。 |
| `skill_market_advanced` | OK, 16 routes | 存在但未挂载；与其他 skill_market 重复，需要裁决权威实现。 |
| `skills_api` | OK, 11 routes | 存在但未挂载；若首版需要技能执行入口则是 P0。 |
| `sessions` | OK, 10 routes | 存在但未挂载；若前端/BFF依赖则需挂载或隐藏入口。 |
| `enterprise` | OK, 25 routes | 存在但未挂载；企业管理首版范围需裁决。 |
| `streaming_enhanced` | OK, 6 routes | 存在但未挂载；前端有 streaming 缺口。 |
| `sso` | OK, 13 routes | 存在但未挂载；部分 OAuth/WebAuthn 仍是占位/501，不能直接宣传。 |
| `oauth_routes` | OK, 3 routes | 存在但未挂载；需真实 token/session 语义后才能上线。 |
| `analytics` | FAIL: missing `backend.app.api.aggregator` | 当前不可直接挂载。 |
| `plugin_marketplace` | FAIL: dependency assertion | 当前不可直接挂载。 |
| `plugin_marketplace_api` | FAIL: invalid Query parameter type | 当前不可直接挂载。 |
| `skill_market` | FAIL: `from typing import list` | 当前不可直接挂载。 |
| `skill_market_complete` | FAIL: asyncpg Pool response model | 当前不可直接挂载。 |
| `templates` | FAIL: missing `backend.app.core.workflows.template_system` | 当前不可直接挂载。 |

## 3. 三方报告逐项裁决

| 主题 | Claude 4.8 | ZCode GLM 5.2 | Codex GPT 5.5 | 当前裁决 |
| --- | --- | --- | --- | --- |
| 核心引擎真实性 | 真实，不是空壳 | 后端安全和能力较强 | 后端基础较强 | **采纳**。工作流、LLM、memory、MCP、browser、RBAC 等不是纸面实现。 |
| 可直接商用交付 | 不建议 | No-Go | No-Go | **采纳**。可进入 RC 审计/受控试点，不可完整 GA。 |
| 未挂载路由 | P0，大量 API 未挂载 | P0，57 个未挂载 | P0/P1，运行态缺口影响前端 | **部分采纳并修正**。当前核验为 56 个未挂载路由模块。不是全部 P0，需按首版范围裁决。 |
| P0-01/02/03/04 修复是否“死代码” | 部分认为未挂载影响交付 | 明确称部分 P0 修复作用于未挂载路由 | 指出未挂载模块不能纳入真实 route audit | **采纳为流程风险**。已挂载路由审计 clean，但未挂载模块未被运行态审计覆盖。 |
| 前端 API 合约 | 核心链路对齐较好，问题集中部分页面 | 三类失配，裸 fetch 和未挂载端点 | 46 个路径不可匹配 | **采纳 Codex/ZCode 更具体结论**。当前机器核验 109/63/46。 |
| 前端认证 | 鉴权头一致性 P1 | 裸 fetch 缺 auth P0 | 裸 fetch/EventSource 缺统一认证 | **采纳**。必须统一 API client；EventSource 需 cookie/session 或 signed stream token。 |
| CI 质量门禁 | CI 装饰性，安全扫描 fail-open | CI/CD 未端到端验证 | hosted/workflow 仍有 fail-open | **部分采纳并区分**。Commercial RC workflow 较强且已有证据；但 `.github/workflows/security.yml`, `ci.yml`, `quality.yml`, `deploy.yml` 等仍有 fail-open/placeholder。 |
| 部署/Stage3 | 未充分核实 | 未端到端验证 | Stage3/production evidence 缺 | **采纳**。非严格 RC gate 绿；严格 Stage3 rehearsal 仍 blocked。 |
| `.env`/secret | 明文密钥风险，历史未能核实 | 环境/secret 治理需加强 | 本地 hardening 较好但需 secret 管理 | **部分采纳**。当前工作树未发现真实 secret 暂存；仍需历史扫描、secret rotation 和生产 secret manager。 |
| SAML/WebAuthn | 设计较好，有局限 | 基本可用 | SAML c14n 简化、WebAuthn 501 | **采纳**。SAML 测试过，但企业 SSO 前需真实 IdP 联调；WebAuthn 不能宣传为可用。 |
| Audit HMAC fail-open | 降为 P2 | 未突出 | 已有生产 fail-fast | **采纳 Claude 降级**。生产路径已有守卫，但 signer 直接构造时应 fail-closed。 |
| 多租户 body tenant_id | P1 数据层需统一强制 | 多数路由已从 principal 取 tenant | 已有安全基础 | **采纳为架构债**。中间件只看 query，长期应在数据访问层强制 tenant。 |
| token/CSRF/rate limiter 内存状态 | 未突出 | token/CSRF/rate limiter 集群问题 | 需高可用治理 | **采纳为 P1**。单实例可用，多副本商用需要 Redis/共享状态强制。 |
| docs 膨胀/虚标 | 文档可能虚标 | 顶层 md 过多 | 文档和功能边界需收口 | **采纳**。交付文档必须以运行态和首版范围为准。 |
| 浏览器扩展 | 未作为主线 | 可能纳入未来 | 用户已排除首版 | **裁决: 不纳入首版交付范围**。只保留桌面端。 |
| 桌面端 | 未深挖 | 未深挖 | 纳入交付范围 | **裁决: 纳入首版范围**，已有安全硬化证据，但仍需打包/安装/E2E 证据。 |

## 4. 真实问题清单与优先级

### P0-A: 首版范围裁决与前端入口下线/收口

问题: 目前前端页面展示的 marketplace/templates/forum/analytics/notifications/部分 streaming 能力，与后端运行态不匹配。对商业用户表现为 404/401/静默失败。

裁决原则:

- 首版必须交付: workbench、agent run、workspace/file preview、memory、auth/RBAC、desktop、Feishu/GitHub/DeepSeek owner gate、Stage3 evidence chain。
- 首版暂不承诺: browser extension、WebAuthn/passkey、完整 OAuth、forum、analytics、plugin-market、skill-market、templates，除非在本轮显式补齐并通过 E2E。

验收:

- 前端导航/菜单不显示未交付功能，或显示为明确 disabled/coming soon。
- 运行态路由合约测试证明首版入口全部可达。
- 文档不宣传未交付能力。

### P0-B: 前端 API 合约测试和统一认证

问题: 前端存在 46 个运行态不可匹配 API 引用，多处裸 fetch/EventSource 不走统一认证。

验收:

- 建立 `frontend API path -> FastAPI mounted route` 合约测试。
- 受保护接口统一走 `frontend/src/services/api.ts` 或等价 authenticated client。
- 裸 `fetch('/api/...')` 被 lint/测试禁止，允许名单只包含静态 health、公开资源或专门说明的 SSE token 获取。
- EventSource 使用 cookie session 或 signed stream token，不依赖手动 Authorization header。

### P0-C: 未挂载后端模块裁决

问题: 56 个含路由模块未挂载，其中一部分导入失败，一部分是重复/历史实现。

验收:

- 生成 `backend/app/api` 路由模块裁决清单: `ship_now`, `defer_hidden`, `delete/archive`, `internal_only`。
- `ship_now` 模块必须 import OK、include_router、route_auth_audit clean、focused tests pass。
- `defer_hidden` 模块必须从前端入口和文档宣传中移除。
- 导入失败模块不得直接挂载。

### P0-D: Hosted workflow 与生产 deploy fail-open 收口

问题: Commercial RC workflow 较强，但其他 workflow 仍存在 `continue-on-error`, `|| true`, production deploy placeholder 和注释掉的 health check/rollback。

验收:

- 商业 release 必须只以 Commercial RC workflow + strict final gate 为准。
- `.github/workflows/security.yml` 对 high/critical、安全扫描失败、secret verified 不能 fail-open。
- `.github/workflows/deploy.yml` production job 不再是 echo/comment placeholder；真实部署、health check、rollback gate 失败必须阻断。
- 若暂不启用 production deploy workflow，则明确禁用或改名为 template，避免误用。

### P0-E: Stage3 外部证据补齐

问题: 非严格 RC gate 绿，但严格 Stage3 rehearsal 仍 blocked。域名/HTTPS 是其中一部分；五类外部证据仍需真实 refs。

验收:

- `stage3_https_preflight.py --domain www.xiong-agent.com` 通过 DNS/TLS/health/ready。
- `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, `staging_environment_protection` 五类证据由真实外部 refs 支撑。
- `rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal` 通过。

### P1-A: Redis/共享状态强制化

问题: token、reset token、CSRF、rate limiter 存在内存 fallback；单实例可用，多副本商用不稳。

验收:

- production/standard 模式缺 Redis 或共享状态配置时 fail-fast。
- logout/reset/revoke/token validation 跨实例一致。
- rate limit 支持可信代理配置和共享存储。

### P1-B: 日志默认脱敏

问题: logging middleware 可配置记录 body，query 总是可能进入日志；如果生产误开，会泄露 token/password/code。

验收:

- header/query/body 全部通过统一 sanitizer。
- 默认脱敏字段包含 authorization、cookie、token、secret、password、api_key、code、credential、signature。
- 生产禁止 raw body logging，除非显式安全豁免。

### P1-C: SSO/企业认证边界

问题: SAML 当前测试通过，但 XMLDSig/c14n 简化；WebAuthn 501，OAuth 部分占位。

验收:

- 文档明确首版支持范围: SAML profile、OIDC、WebAuthn/OAuth 状态。
- 企业 SSO 前至少完成一个真实 IdP 联调记录: Okta/Azure AD/ADFS 三选一。
- WebAuthn/passkey 不作为首版宣传点。

### P1-D: 文档和交付材料收口

问题: 根目录大量历史完成报告容易造成虚标和混乱。

验收:

- 建立首版 SSoT: README、部署 runbook、release notes、owner quickstart、known limitations。
- 历史报告归档或在文档索引中标记 historical/non-authoritative。
- 文档与运行态路由、前端入口一致。

## 5. 下一步升级修复方案

推荐分 5 个短冲刺，每个冲刺完成后都提交一次，保持工作树干净。

### Sprint 1: 首版范围冻结与前端入口降级

目标: 先阻止用户看到未交付功能。

任务:

1. 建立首版功能清单: `docs/RC_FIRST_VERSION_SCOPE.md`。
2. 在前端导航和页面路由中隐藏/禁用 forum、analytics、plugin-market、skill-market、templates、notifications、WebAuthn/passkey、完整 OAuth。
3. 给禁用入口保留明确 `coming soon` 文案或从导航移除，不能触发后端 API。
4. 增加测试，证明禁用入口不会发起 `/api/v1/forum`, `/api/v1/analytics`, `/api/v1/plugin-market`, `/api/v1/skill-market`, `/api/v1/templates` 请求。

### Sprint 2: API 合约守门

目标: 让 CI 自动发现“前端调用不存在路由”。

任务:

1. 新增脚本 `scripts/frontend_api_contract_audit.py`。
2. 基于 `backend.app.main:app.routes` 提取真实 mounted routes。
3. 扫描 `frontend/src` 的 API 引用，生成 missing/present 列表。
4. 支持 allowlist，allowlist 必须写明 `deferred_feature` 或 `public_static` 原因。
5. 新增 `tests/test_frontend_api_contract_audit.py`。
6. 将该脚本接入 Commercial RC workflow。

### Sprint 3: 前端认证统一

目标: 所有受保护请求走统一客户端。

任务:

1. 选定 `frontend/src/services/api.ts` 作为唯一 authenticated axios client，或抽出 `frontend/src/services/httpClient.ts`。
2. 改造 `apiClient.ts`, `FilePreview.tsx`, `FolderSelector.tsx`, `TaskList.tsx`, `InteractiveQuestion.tsx`, console hooks。
3. EventSource 单独设计 signed stream token 或 cookie session 方案。
4. 增加 lint/test: 禁止裸 `fetch('/api/` 和裸 `new EventSource('/api/`，只允许 allowlist。

### Sprint 4: 后端未挂载模块裁决

目标: 不再用“写了但没挂”污染交付判断。

任务:

1. 新增 `docs/API_ROUTE_SCOPE_DECISION_20260618.md`。
2. 把 56 个未挂载模块分为 ship/defer/delete/internal。
3. 对 `ship` 模块逐个修 import、挂载、权限、测试。
4. 对 `defer` 模块从前端和文档移除宣传。
5. 对重复模块收敛权威实现，如 skill_market/plugin_market 系列。

### Sprint 5: Hosted release 与 Stage3 证据

目标: 把 RC 候选升级为可发布候选。

任务:

1. 修 `.github/workflows/security.yml` high/critical fail-open。
2. 修或禁用 `.github/workflows/deploy.yml` production placeholder。
3. 域名可备案/接入后，跑 Stage3 HTTPS preflight。
4. 填五类 Stage3 evidence refs。
5. 跑 strict final gate。
6. 打 RC tag/release。

## 6. 建议的立即执行顺序

1. 不要先大规模挂载 56 个后端模块。这样会把未经审计的路由暴露出去。
2. 先冻结首版范围，隐藏前端未交付入口。
3. 再加前端 API 合约测试，让缺口变成 CI 可见。
4. 然后逐个决定哪些后端模块真要进入首版。
5. 最后处理 Hosted workflow 和 Stage3 证据。

## 7. 总结

三份报告都抓住了主问题，但 ZCode 和 Codex 对“运行态路由/前端合约”的问题更接近当前真实阻断；Claude 对“核心不是空壳”和“CI 质量门禁信任不足”的提醒也成立，但其部分 CI 判断需要区分 Commercial RC workflow 与普通 legacy workflow。

最终裁决:

- **RC 候选:** 可以继续审计。
- **受控试点:** 可以，但必须隐藏未交付入口并写清能力边界。
- **完整商用 GA:** 现在不可以。
- **最优下一步:** 前端入口降级 + API 合约审计脚本 + 统一认证客户端。
