# 前后端核心能力对齐审计报告

- 审计日期: 2026-07-26
- 审计方式: 后端路由通过 `./venv/Scripts/python.exe` 从项目根 `from backend.app.main import app, _register_all_routers` 注册后枚举 `app.routes`(共 **543** 条 HTTP 路由,与声明的 549 基本一致,差异为 HEAD/OPTIONS/WS 口径);前端端点通过静态扫描 `frontend/src/services/*.ts`、`frontend/src/pages/*.tsx`、`frontend/src/components/**`、`frontend/src/console/**`、`frontend/console.html`、`frontend/chat.html` 获得。
- 关键结构事实:
  - React 主应用路由表(`frontend/src/App.tsx:60-81`)仅 13 条:`/login / /chat /tasks /tools /memory /workflows /workflows/:id/edit /agents /settings /goals /review /evolution /agents/:id/workspace`。
  - `frontend/src/console/` 下 40+ 个页面(execution-control、memory-control、tools-control、marketplace-control、organization-control、navigation-control、PluginMarket、SkillMarket、templates、MeetingRooms 等)**未在任何地方被 import,整个子应用无入口**(grep 全仓无 `ConsoleShell` 引用)。
  - `FeedbackDashboard.tsx`、`AnalyticsDashboard.tsx`、`Forum.tsx`、`RealtimeVisualization.tsx` 同样未被路由或引用,是孤儿组件。
  - `console.html`(静态,后端 `/console` 提供)实际可用,覆盖 memory/org/evolution/agents runs;`chat.html` 覆盖 agents run/runs、memory、audit-logs、security/api-keys、tools。

---

## 清单 A:有后端能力、无前端入口(按能力域)

> "入口"指 React 主应用路由/组件或两个静态控制台之一实际调用该域端点。证据路径为后端路由文件。

| # | 能力域 | 后端证据 | 路由规模 | 前端现状 | 优先级 | 建议复用端点组 |
|---|--------|----------|---------|----------|--------|----------------|
| A1 | 聊天历史持久化 | `api/chat_history.py` GET/POST `/api/v1/chat/history`、DELETE、`/{session_id}/messages` | 5 | ChatPage 未接;`api.ts:507` 注释误称"后端无此端点" | **P0** | `/api/v1/chat/history` 整组 |
| A2 | 工作流调度/暂停/恢复/实例 | `api/workflows.py` `/workflows/schedules*`(5)、`/{id}/pause|resume|cancel`、`/{id}/instances`、`/workflows/templates` | 10+ | WorkflowsPage 仅 list/run | **P0** | `/api/v1/workflows/schedules` + `/{id}/pause|resume` |
| A3 | 运行回放与时间线 | `api/runs.py` GET `/runs`、`/runs/start`、`/{trace_id}/replay|timeline|correlation|status|detail` | 7 | 仅 console.html 读 runs 列表;React 无 | **P0** | `/api/v1/runs` 整组(可复用孤儿 ExecutionPanel/ProgressIndicator) |
| A4 | 断点恢复(checkpoints) | `api/checkpoints.py` GET `/checkpoints`、`/{trace_id}`、DELETE、POST `/{trace_id}/resume` | 4 | 无 | **P0** | `/api/v1/checkpoints` 整组,挂在 AgentWorkspace |
| A5 | API Key 管理(路径漂移) | `api/security.py` `/security/api-keys` CRUD+revoke+expiring-soon | 8 | SettingsPage 调用了错误的 `/api-keys`(见 B2) | **P0** | `/api/v1/security/api-keys` |
| A6 | MCP 服务器/工具管理 | `api/mcp.py` `/mcp/servers|tools|status|health|permissions`、client-manager 5 个、`/mcp/audit-logs` | 17 | 无 | **P0** | `/api/v1/mcp/servers` + `/mcp/tools` + client-manager |
| A7 | 审批流(approvals) | `api/approvals.py` 列表/详情 + approve/reject/execute | 6 | 无 | P1 | `/api/v1/approvals` 整组 |
| A8 | 审计日志 | `api/audit*.py` `/audit-logs`(list/export csv+json/verify/summary)、audit-enterprise 5、rotation 2 | 12 | chat.html 仅读列表;React 无 | P1 | `/api/v1/audit-logs` + `/audit-enterprise/analytics` |
| A9 | 备份与恢复 | `api/backup*.py` run/restore/verify/list/status + qdrant 快照 3 + cleanup | 9 | 无 | P1 | `/api/v1/backup` 整组 |
| A10 | 协作房间/委派 | `api/collaboration.py` rooms CRUD/members/messages/memory-sync + delegations | 12 | 孤儿 console `MeetingRoomsPage.tsx`(未挂载) | P1 | `/api/v1/collaboration/rooms` 整组 |
| A11 | 多智能体编排 | `api/agents.py` `/agents/parallel/spawn|ultra|orchestrator/*|messages/*`(12)、`multi-agent/decompose|execute|executions`(4) | 16 | ChatPage 调用漂移的 `/agents/parallel`(B4) | P1 | `/agents/parallel/ultra` + `/multi-agent/executions` |
| A12 | Agent 生命周期控制 | `api/agents.py` `/{id}/pause|resume|cancel`、`/agents/runs/{trace_id}/timeline|correlation` | 6+ | AgentsPage 仅 CRUD | P1 | `/api/v1/agents/{id}/pause|resume|cancel` |
| A13 | 记忆高级能力 | `api/memory*.py` enhanced store/recall/search/relate/merge/sync/stats(8)、layers(2)、consolidate、import/export | 13 | MemoryPage 仅 search/CRUD;console.html 用 count/layers/consolidate | P1 | `/api/v1/memory/enhanced/*` + `/memory/import|export` |
| A14 | 组织/部门/企业内 Agent | `api/org.py` organizations/departments/agents CRUD + memory 视图 | 13 | 仅 console.html;孤儿 `Organization*Page.tsx` | P1 | `/api/v1/org/*` 整组 |
| A15 | 租户/计费/配额 | `api/tenants.py`+`billing.py`+`tenant_quota.py` tenants CRUD、`/{id}/billing|usage`、`/tenant/quota|usage` | 9 | 无 | P1 | `/api/v1/tenants` + `/api/v1/tenant/quota` |
| A16 | 用户管理(管理员) | `api/users.py` 用户 CRUD、role、activity | 7 | SettingsPage 仅个人资料(且漂移) | P1 | `/api/v1/users` 整组 |
| A17 | 认证高级面 | `api/auth.py`+`sso.py` MFA setup/verify、WebAuthn 4、LDAP 2、SSO OIDC/SAML 6、conditional-access、sessions revoke | 20+ | LoginPage 仅 login/register | P1 | `/api/v1/auth/mfa/*` + `/api/v1/sso/providers` |
| A18 | 技能市场/沉淀 | `api/skills*.py` `/api/skills` 市场 11、`/skill-sediment` 6、`/skill-curator` 2 | 19 | 孤儿 `SkillMarket*.tsx` 且路径漂移(B9) | P1 | `/api/skills` + `/api/v1/skill-sediment/skills` |
| A19 | 插件生态 | `api/plugin_marketplace.py` 等 `/plugin-ecosystem/plugins` 9 + `/plugins` 管理 8 | 17 | 孤儿 `PluginMarket.tsx` 且路径漂移(B8) | P1 | `/api/v1/plugin-ecosystem/plugins` + `/api/v1/plugins` |
| A20 | 沙箱任务 | `api/sandbox_tasks.py` tasks list/create/detail + github webhook | 4 | 无 | P1 | `/api/v1/sandbox/tasks` |
| A21 | 代码评审完整流 | `api/code_review.py` `/engine/diff|file|pr`、`/pr`、`/diff`、`/{id}/approve`、GET 列表/详情 | 9 | CodeReviewPage 仅 POST `/code-review/file` | P1 | `/api/v1/code-review` 列表 + `/{review_id}/approve` |
| A22 | 追踪/可观测 | `api/traces.py` traces list/debug/replay/correlation(6)、`/metrics/prometheus|summary|metrics`、`/ops/summary` | 10 | 孤儿 `AnalyticsDashboard.tsx` | P1 | `/api/v1/traces` + `/api/v1/metrics/summary` |
| A23 | 集成/飞书 | `api/integrations.py`+`feishu.py` providers CRUD/send、feishu configure/events/send/status | 8 | 无 | P1 | `/api/v1/integrations` 整组 |
| A24 | GDPR/合规 | `api/gdpr.py` erase/export/pii scan/mask/residency/deletions(7)、`compliance.py` SOC2/incidents/changes(13) | 20 | 无 | P2(合规上线前升 P1) | `/api/v1/gdpr/*`、`/api/v1/compliance/*` |
| A25 | 离线同步 | `api/sync.py` enqueue/conflicts/resolve/history/offline/stats | 11 | 无 | P2 | `/api/v1/sync/*` |
| A26 | 工作台会话 | `api/work_mode.py` `/work/sessions` CRUD+pause/resume/tick(7)、`/api/sessions` 8 | 15 | 无 | P2 | `/api/v1/work/sessions` |
| A27 | 浏览器/桌面自动化 | `api/browser*.py` sessions 10 + advanced 14、`desktop.py` 5 | 29 | 无 | P2 | `/api/v1/browser/sessions` |
| A28 | 进化自进化循环 | `api/evolution.py` self-evolution cycle/distill/evaluate/optimize/record(5)+trigger | 7 | EvolutionPage 仅 stats/skills/summary | P2 | `/api/v1/evolution/self-evolution/*` |
| A29 | 草稿类端点 | `execution/draft`、`planning/draft`、`overview/draft`、`replay/draft`、`verification/draft` | 5 | 无 | P2 | 各 `/draft` |
| A30 | DR/移动端/SCIM/webhook | `dr_status.py` 3、`mobile` 5、SCIM 10、telegram webhook | 18+ | 机器/运维接口,可不建 UI | P2/N/A | — |
| A31 | console 管理面(*-control) | `execution-control`(4)、`memory-control`(4)、`tools-control`(4)、`marketplace-control`(4)、`navigation-control`(3)、`organization-control`(4) | 23 | 后端与 console 页齐备,但 console 子应用未挂载 → 管理面实际不可达 | **P1** | 挂载 `src/console` 即可全部点亮 |

---

## 清单 B:前端调用但后端不存在的漂移端点

| # | 前端调用(证据) | 后端实际情况(证据) | 影响面 | 优先级 |
|---|----------------|--------------------|--------|--------|
| B1 | `PUT /api/v1/users/me`(`services/api.ts:610`,SettingsPage) | 后端为 `PUT /api/v1/auth/me`(`api/auth.py:570 update_me`) | 个人资料保存必失败 | **P0** |
| B2 | `POST/DELETE /api/v1/api-keys[/{id}]`(`api.ts:615,621`,SettingsPage) | 后端为 `/api/v1/security/api-keys`(`api/security.py`;chat.html 用的是正确路径) | API Key 创建/吊销必失败 | **P0** |
| B3 | `POST /api/v1/agent/run`(`api.ts:583`,AgentWorkspace) | 后端只有 `/api/v1/agents/run` 与 `/agent/run/stream` | Agent 工作台运行必失败 | **P0** |
| B4 | `POST /api/v1/agents/parallel`(`api.ts:595`,ChatPage) | 后端为 `/agents/parallel/ultra`(及 spawn/orchestrator) | ChatPage 并行模式必失败 | **P0** |
| B5 | `GET /api/v1/metrics`(`api.ts:604`,Dashboard) | 后端为 `/api/v1/metrics/summary|metrics|prometheus` 及根 `/metrics` | Dashboard 指标卡失败 | **P0** |
| B6 | `GET /api/v1/feedback/stats`(`services/feedback.ts:143`) | 后端为 `/api/v1/feedback/stats/summary`(`api/feedback.py:445`,字段 `by_status/by_type` 蛇形命名) | FeedbackDashboard 统计失败 | P1 |
| B7 | `/api/v1/feedback/trends|sentiment-analysis|category-distribution|search|export`、`/{id}/resolve`、`/notifications` CRUD+test、PUT/DELETE `/{id}`(`feedback.ts:135-226`) | 后端 feedback 仅 GET `/`、GET/PATCH `/{id}`、GET `/{id}/analysis`、GET `/stats/summary`、POST `/` | FeedbackDashboard 大半功能失败(组件本身也是孤儿) | P1 |
| B8 | `/api/v1/plugin-market/*` 6 个(`console/pages/marketplace/PluginMarket.tsx`) | 后端注册的是 `/api/v1/plugin-ecosystem/plugins*` | 插件市场页全灭(且未挂载) | P1 |
| B9 | `/api/v1/skill-market/*` 10 个(`console/pages/marketplace/SkillMarket*.tsx`) | 后端为 `/api/skills*`(市场)与 `/api/v1/skill-sediment/*` | 技能市场页全灭(且未挂载) | P1 |
| B10 | `/api/v1/templates/*` 9 个(`console/pages/templates/*`) | 路由表无 `/templates` 注册(`api/` 下亦无 templates router 被 include) | 模板市场页全灭(且未挂载) | P1 |
| B11 | `/api/v1/analytics/costs|performance|realtime`(`components/AnalyticsDashboard.tsx`) | 无 analytics 路由注册(`api/analytics.py` 未被 include) | 组件孤儿 + 端点缺失 | P2 |
| B12 | `/api/v1/forum/*` 9 个(`components/Forum.tsx`) | `api/forum.py` 存在但未被 main.py include | 组件孤儿 + 端点缺失 | P2 |
| B13 | `POST /api/v1/notifications/subscribe`(`utils/pushNotificationManager.ts:228`)、`WS /api/v1/notifications/ws`(`services/websocketClient.ts:28`) | 后端仅 `GET /api/v1/notifications/status`,无 subscribe/ws | 推送/通知中心静默失败 | P1 |
| B14 | `/api/v1/streaming/stream/{...}`(`components/streaming/RealtimeVisualization.tsx`) | `api/streaming*.py` 未被 include,路由表无 `/streaming` | 组件孤儿 + 端点缺失 | P2 |

---

## 清单 C:两端都有但语义/字段失配

| # | 端点 | 失配内容(证据) | 优先级 |
|---|------|----------------|--------|
| C1 | `POST /api/v1/chat/history` 等 5 个 | 后端齐备,但 `api.ts:507` 注释"backend has no GET /chat/history… coming soon",ChatPage 历史持久化被注释禁用 —— **能力被前端自我关闭** | **P0** |
| C2 | `PUT/DELETE /api/v1/memory/{id}` | 后端已有(`main.py` 路由表),`api.ts:438` 注释仍称"backend has no PUT/DELETE",MemoryPage 编辑/删除入口被禁用 | P1 |
| C3 | `PUT /api/v1/tools/{name}`、`POST /tools/{name}/test` | 后端已有,`api.ts:460` 注释陈旧,ToolsPage 开关/测试被禁用 | P1 |
| C4 | `POST /api/v1/feedback/stats/summary` | 路径漂移(B6)叠加命名失配:前端 `FeedbackStats` 用驼峰 `byType/byStatus/avgResolutionTime`,后端 `FeedbackStatsResponse` 为蛇形 `by_type/by_status`(`api/feedback.py:95-100`),即使改对路径仍需适配层 | P1 |
| C5 | `POST /api/v1/agents/parallel/ultra` | 修正 B4 路径后字段仍需核对:前端发 `{tasks:[{goal,description}], max_parallel}`(`api.ts:591-599`),ultra 端点请求体未在前端适配 | P1(待验证) |
| C6 | `PUT /api/v1/auth/me` | 修正 B1 路径后字段待核对:前端发 `{display_name, email}`(`api.ts:609`),后端 `update_me`(`api/auth.py:570`)返回 dict,字段集未确认 | P1(待验证) |

---

## 补齐优先级汇总(按用户价值排序)

**P0 — 核心工作流断档(功能在主界面可见但必失败/被禁用)**
1. B1+B2: SettingsPage 个人资料与 API Key 全部写操作失败 → 改路径至 `/auth/me`、`/security/api-keys`。
2. B3+B4: AgentWorkspace 运行、ChatPage 并行模式失败 → 改至 `/agents/run`、`/agents/parallel/ultra`。
3. B5: Dashboard 指标失败 → 改至 `/metrics/summary`。
4. A1/C1: ChatPage 历史持久化被注释禁用,后端 `/chat/history` 齐备 → 启用即可。
5. A2/A3/A4: 工作流调度/运行回放/断点恢复无 UI → 复用 `/workflows/schedules`、`/runs`、`/checkpoints` 端点组。

**P1 — 重要管理面缺失**
- 挂载孤儿 console 子应用(A31,一次路由挂载点亮 23 条 *-control 端点与 6 大管理页);
- MCP 管理页(A6)、审批流(A7)、审计(A8)、备份(A9)、协作(A10)、租户计费(A15)、用户管理(A16)、MFA/SSO(A17);
- 修正 B6-B10、B13 漂移路径;启用 C2/C3 被注释能力。

**P2 — 锦上添花**
- GDPR/合规(A24)、同步(A25)、浏览器/桌面自动化(A27)、自进化控制台(A28)、analytics/forum/streaming 孤儿组件(B11/B12/B14,或删或接)。

---

## 附:前端页面 → 端点映射(证据)

| 页面(路由) | 服务方法 | 实际端点 |
|---|---|---|
| Dashboard `/` | getMetrics/listAgents/listTasks/listTools | `/metrics`(漂移 B5)、`/agents`、`/tasks`、`/tools` |
| ChatPage `/chat` | sendMessage/getWorkbenchBootstrap/runParallelAgents | `/workflows/create/chat`、`/workbench`、`/agents/parallel`(漂移 B4) |
| TasksPage `/tasks` | listTasks/createTask/deleteTask | `/tasks` CRUD |
| AgentsPage `/agents` | agents CRUD | `/agents` CRUD |
| AgentWorkspacePage `/agents/:id/workspace` | getAgentDetail/runAgentTask + InteractiveQuestion/FilePreview/FolderSelector | `/agents/{id}`、`/agent/run`(漂移 B3)、`/questions/*`、`/files/*`、`/workspace/mounts` |
| MemoryPage `/memory` | listMemories/searchMemories/createMemory | `/memory/search`、`/memory`(C2 编辑被禁) |
| ToolsPage `/tools` | listTools | `/tools`(C3 开关被禁) |
| WorkflowsPage `/workflows` | listWorkflows/runWorkflow/listWorkflowRuns | `/workflows`、`/workflows/{id}/run`、`/workflows/runs` |
| WorkflowEditorPage | listWorkflows/runWorkflow | 同上(编辑器实际只读列表) |
| CodeReviewPage `/review` | postCodeReview | `/code-review/file` |
| GoalModePage `/goals` | getGoals/createGoal | `/goals` |
| EvolutionPage `/evolution` | getEvolutionStats/getEvolutionSkills | `/evolution/stats`、`/evolution/skills` |
| SettingsPage `/settings` | updateProfile/createApiKey/deleteApiKey | `/users/me`、`/api-keys`(均漂移 B1/B2) |
| LoginPage `/login` | login/register/refresh/logout | `/auth/login|register|refresh|logout` |
| FeedbackDashboard(孤儿) | feedbackService 12 方法 | `/feedback/*`(B6/B7 大量漂移) |
| console.html(静态) | — | `/memory/count|search|consolidate|layers`、`/org/*`、`/evolution/summary|reflections|learnings|capabilities`、`/agents/runs` |
| chat.html(静态) | — | `/agents/run`、`/agents/runs`、`/memory/search|layers|consolidate`、`/audit-logs`、`/security/api-keys`、`/tools` |
| src/console/*(孤儿子应用) | — | `*-control` 23 端点(后端存在)+ plugin-market/skill-market/templates(漂移 B8-B10) |
