# X-Agent 商用交付深度审计报告

审计日期: 2026-06-18
审计口径: 从当前源码、配置、运行态路由和本地命令结果重新审计；不引用既有审计报告作为证据。
审计重点: 功能完整性、前后端 API 对齐、安全隐患、CI/部署/Secret/发布门禁。

## 1. 总体结论

当前项目已经具备较强的后端安全加固基础和本地门禁基础，但还没有达到可直接商业交付标准。

最主要阻断不是编译或基础安全测试，而是前后端功能合约没有收口: 前端存在大量真实页面调用的 API 在当前 FastAPI 运行态没有挂载，部分后端模块虽然存在但导入失败或未接入 `backend/app/main.py`。这意味着前端生产构建可以成功，但真实用户进入 marketplace、templates、forum、analytics、notifications、部分 streaming/chat/feedback/memory 工具页面时会遇到 404、405 或 401。

建议交付状态评估:

| 维度 | 当前状态 | 商用判断 |
|---|---:|---|
| 后端核心鉴权/RBAC/路径边界 | 本地重点回归通过 | 可作为基础，但仍需外部环境验证 |
| 前端 TypeScript 与生产构建 | 通过 | 编译可交付 |
| 前后端功能合约 | 存在大量缺口 | 阻断商业交付 |
| 部署硬化本地 gate | 通过 | 本地配置较好 |
| Hosted CI / Stage3 / 生产发布 | 仍有 fail-open 与占位部署 | 阻断正式商用发布 |
| 企业 SSO/WebAuthn | SAML/OIDC 核心验证增强；WebAuthn 显式禁用 | SSO 需真实 IdP 联调，WebAuthn 不能宣传可用 |

综合判断: 代码本地门禁成熟度约 75%-80%；商业交付成熟度约 60%-70%。如果目标是单租户/内测演示，可以进入受控试点；如果目标是对外商业客户交付，必须先完成前后端 API 合约收口、真实 E2E、Hosted CI/Stage3 证据和生产部署链路。

## 2. 审计方法与命令证据

本次只使用当前项目文件与实际命令输出。

已执行命令:

```powershell
python scripts/route_auth_audit.py --json
python -m pytest tests/test_security_auth.py tests/test_security_authz.py tests/test_main_api_key_auth.py tests/test_route_auth_audit.py tests/test_saml_signature.py tests/test_workspace_api_auth.py tests/test_file_preview_path_boundary.py tests/test_memory_enhanced_auth.py tests/test_browser_advanced_authz.py tests/test_skill_curator_auth.py tests/test_sessions_skills_issuepr_auth.py tests/test_enterprise_api_auth.py --no-cov -q
$files = @(Get-ChildItem tests -Filter 'test_deployment_*.py' | ForEach-Object { $_.FullName }) + @('tests/test_production_hardening_gate.py'); python -m pytest @files --no-cov -q
cd frontend; npm run type-check
cd frontend; npm run build
python scripts/security_deployment_gate.py
python scripts/production_hardening_gate.py
python -m pytest tests/test_commercial_security_compliance_gate.py tests/test_commercial_stage5_security_evidence_pack.py tests/test_commercial_ga_final_gate.py tests/test_rc_final_gate.py tests/test_rc_single_user_local_gate.py tests/test_commercial_pilot_final_gate.py tests/test_commercial_pilot_readiness.py --no-cov -q
```

结果摘要:

| 命令 | 结果 |
|---|---|
| `route_auth_audit.py --json` | `{"issues": [], "ok": true}` |
| 安全 focused pytest | `119 passed, 1 skipped` |
| 部署 hardening pytest | `44 passed` |
| frontend type-check | 通过 |
| frontend build | 通过，Vite 仅提示 `optimizeDeps.esbuildOptions` deprecated |
| `security_deployment_gate.py` | `OK No deployment-hardening issues found.` |
| `production_hardening_gate.py` | `ready`, findings 0 |
| commercial focused pytest | `132 passed` |

## 3. 功能与前后端对齐

### 3.1 运行态路由与前端调用扫描

从真实加载的 `backend.app.main:app.routes` 提取到:

- 后端运行态 `/api*` 路由数: 370
- 前端源码中提取到的 `/api/v1` 调用点: 224
- 初步未匹配调用点: 115
- HTTP method 不匹配调用点: 12

说明: 115/12 包含部分动态模板字符串的保守误报，例如 `encodeURIComponent(...)` 被静态提取为不完整路径。但下面列出的模块级缺口已经由 `backend/app/main.py` include_router 清单和模块导入结果复核，属于真实交付风险。

### 3.2 P0 功能合约阻断

| 阻断项 | 前端证据 | 后端当前状态 | 影响 |
|---|---|---|---|
| Plugin Market 不可达 | `frontend/src/console/pages/marketplace/PluginMarket.tsx` 调用 `/api/v1/plugin-market/*` | `backend/app/api/plugin_market.py` 存在且可导入，但 `backend/app/main.py` 未挂载 | 插件市场列表、搜索、安装、卸载页面 404 |
| Skill Market 不可达 | `SkillMarket.tsx` / `SkillMarketComplete.tsx` 调用 `/api/v1/skill-market/*` | `backend/app/api/skill_market.py` 导入失败；`skill_market_complete.py` FastAPI response model 构建失败；二者未挂载 | 技能市场核心页面不可用 |
| Templates 不可达 | `TemplateMarketplacePage.tsx`, `TemplateEditor.tsx`, `TemplateInstantiationWizard.tsx` 调用 `/api/v1/templates*` | `backend/app/api/templates.py` 导入失败: `backend.app.core.workflows.template_system` 不可导入；未挂载 | 模板市场、编辑、实例化功能不可用 |
| Forum 不可达 | `frontend/src/components/Forum.tsx` 调用 `/api/v1/forum/*` | `backend/app/api/forum.py` 存在且可导入，但 `main.py` 未挂载 | 社区/论坛功能不可用 |
| Analytics 不可达 | `AnalyticsDashboard.tsx` 调用 `/api/v1/analytics/realtime`, `/costs`, `/performance` | `backend/app/api/analytics.py` 导入失败: 错误引用 `.aggregator` 等模块；未挂载 | 分析仪表盘不可用 |
| Push notification 订阅缺后端 | `pushNotificationManager.ts` 调用 `/api/v1/notifications/subscribe` | 当前运行态未见对应路由 | 推送订阅不可用 |
| Streaming 双路径不一致 | `RealtimeVisualization.tsx` 调用 `/api/v1/streaming/stream/{runId}` | 运行态挂载的是 `/api/v1/agent/stream/{run_id}`；`streaming_enhanced.py` 可导入但未挂载 | 实时可视化组件无法连接预期流 |

### 3.3 P1 API 方法/路径不一致

| 不一致 | 前端 | 后端运行态 | 影响 |
|---|---|---|---|
| Agent runs 单复数路径 | `/api/v1/agent/runs/{runId}` | `/api/v1/agents/runs/{trace_id}` | run 详情/取消等客户端方法失败 |
| Task 更新方法 | `PATCH /api/v1/tasks/{taskId}` | `PUT /api/v1/tasks/{task_id}` | 任务更新 405 |
| Memory search 方法 | `GET /api/v1/memory/search?q=` | `POST /api/v1/memory/search` | 记忆搜索页面/服务失败 |
| Memory update/delete | `PUT/DELETE /api/v1/memory/{id}` | 当前仅见 `GET /api/v1/memory/{memory_id}` | 记忆编辑/删除不可用 |
| Tools detail/update/test | `GET/PUT /api/v1/tools/{id}`, `POST /tools/{id}/test` | 当前运行态主要是 `/api/v1/tools`, `/api/v1/tools/executions*`, `/api/v1/tools/batch*` | 工具详情和测试功能不可用 |
| Chat history/stream | `/api/v1/chat/history`, `/api/v1/chat/stream` | 当前运行态未见 `/api/v1/chat/*` | 聊天历史和旧式流式聊天不可用 |
| Feedback 扩展 API | `/feedback/stats`, `/trends`, `/notifications`, `/export`, `/search` | 当前运行态只有基础 feedback CRUD、analysis、`/stats/summary` | 反馈分析/通知/导出不可用 |

### 3.4 前端认证调用不统一

前端至少存在三类 API 调用方式:

- `frontend/src/services/api.ts`: axios client，会从 `localStorage.auth_token` 写入 `Authorization: Bearer ...`。
- `frontend/src/services/apiClient.ts`: fetch client，默认未统一注入 Authorization。
- 大量组件直接 `fetch('/api/v1/...')` 或 `new EventSource(...)`，没有统一鉴权、401 处理、租户头、CSRF 或 token 刷新逻辑。

由于后端大部分 `/api/v1` 路由已经通过 principal/RBAC 保护，直接 fetch/EventSource 很容易在真实环境中返回 401。即使路由存在，商业用户也会看到局部页面空白、加载失败或静默失败。

建议收口方式:

1. 建立唯一前端 API SDK，禁止页面直接拼 `/api/v1`。
2. 从后端真实 OpenAPI 或 `app.routes` 自动生成前端 contract test。
3. EventSource 鉴权必须有明确方案: cookie session、短期 signed stream token，或后端支持安全 query token；不能依赖浏览器给 EventSource 手动加 Authorization header。
4. CI 中加入“前端调用路径 vs FastAPI 运行态路由”的合约测试，缺口不能只靠人工审计发现。

## 4. 安全审计

### 4.1 已具备的安全基础

本次从当前代码和测试确认:

- 真实 FastAPI 路由鉴权审计通过，未发现已挂载 `/api` 路由缺 principal 的问题。
- 安全 focused tests 覆盖 auth/RBAC/API key route guard/SAML/workspace/file preview/memory enhanced/browser advanced/skill curator/sessions/enterprise，结果 `119 passed, 1 skipped`。
- workspace 与 file preview 路径边界测试通过，说明当前核心路径逃逸防线有测试覆盖。
- `backend/app/api/memory.py` 当前对 memory search fallback、layer/session/detail/export/import 等路径按 `principal.tenant_id` 过滤，未复现明显跨租户泄露。
- `backend/app/core/saml_sso.py` 当前 OIDC `jwt.decode` 使用 `verify_signature=True`，并要求 `exp/iat/sub`；SAML Response 解析会调用真实 XMLDSig helper，失败关闭。
- `backend/app/core/sso/webauthn_provider.py` 和 `backend/app/api/sso.py` 对未实现 WebAuthn 认证/注册选择 501 fail-closed，而不是返回假成功。
- `backend/app/api/browser.py` 对 navigation URL 调用 `is_browser_navigation_url_allowed()`，并对 screenshot path 做 traversal、Windows drive、UNC、绝对路径限制。

### 4.2 仍需处理的安全风险

| 优先级 | 风险 | 当前证据 | 商用影响 | 建议 |
|---|---|---|---|---|
| P0 | 未挂载但存在的 API 模块可能绕过统一安全审计 | `forum.py`, `plugin_market.py`, `templates.py`, `analytics.py`, `skill_market*.py` 没进入运行态路由审计；部分还导入失败 | 一旦后续直接挂载，可能引入未经 route_auth_audit 覆盖的权限/租户缺口 | 修复导入后必须纳入 route auth audit 和 focused tests，不能直接 include_router |
| P0 | 前端直接 fetch 缺鉴权 | 多个页面直接调用受保护 `/api/v1` | 功能失败，或开发者为修复 401 临时放宽后端鉴权 | 统一 API client，不允许页面直连受保护接口 |
| P1 | SAML XMLDSig 使用简化 c14n | `saml_sso.py` 注释明确 simplified c14n，不是完整 xmlsec | 可能与严格 IdP 互通失败；极端 XML canonicalization 场景需谨慎 | 商用企业 SSO 前做真实 Okta/Azure/ADFS 联调；长期引入 xmlsec/signxml 或限定受支持签名 profile |
| P1 | WebAuthn 不可作为商用功能宣传 | API 显式 501，Provider 验证逻辑未实现 | 如果产品文案宣称支持 passkey/WebAuthn，会形成交付缺口 | 保持禁用，直到实现标准 attestation/assertion 验证 |
| P1 | Logging middleware 可配置记录 query/body，未见字段级脱敏 | `StructuredLoggingMiddleware` 在启用 `log_request_body` 时直接记录 body；query 总是写入日志 | 若生产误开启，token/password/query secret 可能进日志 | 接入统一 log sanitizer；对 query/body/header 做默认脱敏；生产禁止 body logging |
| P1 | 通用 security workflow fail-open | `.github/workflows/security.yml` 多处 `continue-on-error: true` 和 `|| true` | hosted security scan 不会阻断合并/发布 | 对 high/critical、secret verified、SAST 阻断条件 fail-closed；保留 artifact 但不能吞失败 |
| P2 | 未挂载 OAuth/MFA/conditional access API 仍含占位逻辑 | `backend/app/api/sso.py` OAuth callback 返回 `"token"`/`"refresh_token"`，但该 router 未挂载 | 当前不可达风险低；未来挂载会变 P0 | 保持不挂载，或先实现真实 token/session 后再挂载 |

## 5. 部署、CI 与发布链路

### 5.1 本地硬化门禁

当前本地部署硬化状态较好:

- `security_deployment_gate.py`: 无 deployment-hardening issues。
- `production_hardening_gate.py`: status `ready`, findings 0。
- deployment hardening pytest: `44 passed`。
- commercial focused pytest: `132 passed`。

这说明本地脚本能识别大量弱口令、latest 镜像、secret contract、生产 hardening 规则，并且当前扫描范围内没有阻断发现。

### 5.2 Hosted CI 与生产发布不足

仍不能认定为商业发布可用:

- `.github/workflows/security.yml` 中 Bandit、pip-audit、safety、TruffleHog、semgrep 多处 fail-open。它能产出报告，但默认不阻断风险进入主干。
- `.github/workflows/deploy.yml` 的 production job 仍有占位部署特征: AWS credentials `continue-on-error: true`，实际 `kubectl set image`、health check 被注释，health check `continue-on-error: true`，release 创建可能早于真实部署验收。
- Stage 3 staging rehearsal workflow 结构更接近真实门禁，包含 release SHA、image digest、secret 检查、dry-run/confirm gate、smoke 和 rollback evidence。但这仍需要 owner/operator 提供真实 GitHub Actions run、staging URL、cloud/secret refs 后才能证明。

商用发布前必须拿到:

1. Hosted Commercial RC Gate 的真实 run URL、head SHA、artifact。
2. Stage3 staging rehearsal 的真实 deploy smoke 与 rollback evidence。
3. 生产 secret store / external secret refs，不记录 secret 值，只记录引用和验收状态。
4. 不可变 image digest、release tag、source bundle checksum、artifact integrity evidence。
5. 真实生产或 staging smoke，不能只看本地 mock provider。

## 6. 商用功能成熟度

### 可进入受控试点的能力

- Auth/RBAC/API key guard 基础能力。
- Workspace 与 file preview 的路径边界基础能力。
- Agent runs、workbench、execution-control、tools-control、memory-control、organization-control、marketplace-control、navigation-control 等 console 控制面中已挂载的 BFF 类接口。
- 前端能完成 TypeScript 检查与生产构建。
- 本地 RC/GA 类 focused tests 可以跑通。

### 不能对客户承诺完整可用的能力

- Plugin Market / Skill Market。
- Template marketplace/editor/instantiation。
- Forum/community。
- Analytics dashboard。
- Push notification subscription。
- WebAuthn/passkey。
- 旧式 chat history / chat stream。
- 部分 memory/tool/feedback CRUD 扩展操作。
- `/api/v1/streaming/*` 路径的 realtime visualization。
- 完整企业 SSO 互通，必须等真实 IdP 验证。

## 7. 完成任务清单

### 第一阶段: 前后端 API 合约收口

- [ ] 决定哪些前端功能属于本次商用范围，非范围功能从导航隐藏或标记 disabled，不能让用户点进 404。
- [ ] 修复并挂载 `plugin_market.py`，或将前端改到当前已挂载的 marketplace-control BFF。
- [ ] 修复 `skill_market.py` / `skill_market_complete.py` 导入和 FastAPI response model 问题，再挂载并补 route auth tests。
- [ ] 修复 `templates.py` 对 `backend.app.core.workflows.template_system` 的错误依赖，或调整到真实模块路径。
- [ ] 挂载或移除 `forum.py` 相关前端入口。
- [ ] 修复 analytics API 模块导入路径，挂载 `/api/v1/analytics`，并保证前端权限 scope 可用。
- [ ] 统一 streaming 路径: 前端改 `/api/v1/agent/stream/*` 或后端挂载 `/api/v1/streaming/*` 兼容层。
- [ ] 统一 memory search 为 POST 或补 GET shim；统一 task update 为 PUT/PATCH 之一。
- [ ] 补齐 feedback 扩展 API 或删减前端功能。
- [ ] 建立 contract test: 前端所有 `/api/v1` 调用必须匹配真实 FastAPI route + method。

### 第二阶段: 前端认证与用户体验收口

- [ ] 移除页面级直接 `fetch('/api/v1/...')`，统一走一个 API client。
- [ ] 为 fetch、axios、EventSource 制定统一鉴权策略。
- [ ] 所有 401/403/404/405 有统一错误态，不允许空白 loading。
- [ ] 对关键商业路径跑浏览器 E2E: 登录、workbench、agent run、stream、workspace mount/file preview、marketplace/templates 若纳入范围。

### 第三阶段: 安全剩余项

- [ ] 未挂载模块修复后纳入 `route_auth_audit.py`，新增 tests 覆盖 401/403/tenant boundary。
- [ ] SAML 做真实 Okta/Azure AD/ADFS 至少一个 IdP 联调，记录证书轮换、metadata、clock skew、logout 行为。
- [ ] WebAuthn 保持禁用或实现完整 attestation/assertion verification 后再开放。
- [ ] Logging middleware 接入默认脱敏，生产配置禁止 query/body 泄密。
- [ ] 对 plugin/skill 安装类功能建立供应链边界: 来源校验、签名、权限 manifest、隔离执行、撤销机制。

### 第四阶段: CI/部署/发布

- [ ] 将 `.github/workflows/security.yml` 高危安全项改为 fail-closed。
- [ ] 将 production deploy 从 echo/comment placeholder 改为真实部署、health check、rollback gate；失败不得 `continue-on-error`。
- [ ] Hosted Commercial RC Gate 真实跑通并保存 artifact。
- [ ] Stage3 staging deploy smoke + rollback 真实跑通。
- [ ] 生产 secret contract 由 owner/operator 提供外部引用并验收。
- [ ] 发布前生成最终 evidence pack，包含 commit SHA、image digest、source bundle checksum、CI run URL、staging smoke、rollback、security scans。

## 8. Go / No-Go

当前结论: No-Go for commercial GA。

允许的下一步: 受控内测或单租户试点，前提是把未完成前端功能隐藏，并明确 WebAuthn、完整 SSO、marketplace/templates/forum/analytics 的可用性边界。

正式商用 GA 的最低完成线:

1. 前端所有可见入口对应真实运行态 API。
2. 所有 API 调用有统一认证和错误处理。
3. 合约测试、后端安全回归、前端 E2E、部署 hardening、commercial gate 在 hosted CI 全部通过。
4. Stage3/owner/operator 外部证据齐全。
5. 生产 deploy/rollback 不再是占位流程。
