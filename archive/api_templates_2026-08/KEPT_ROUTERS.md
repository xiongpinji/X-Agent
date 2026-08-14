# Track C 路由大瘦身 — 保留/剔除清单

## C2（2026-08-03）：硬门禁 ≤300 达成

C1 结果 941 → **C2 结果 300**（OpenAPI 272 路径，dup operation id 0，探针全 200）。

### C2 切割手法
- **agents.py 361→22**：同文件拆 `router`（挂载）/ `extended_router`（不挂载），handler 本体
  未动。保留：CRUD（POST/GET ""、GET/PUT/DELETE /{agent_id}、pause/resume/cancel）、
  POST /run、/run/stream、/git/status、/model-routing、/performance、/stats、
  /runs、/runs/{trace_id} 及 timeline/progress/reasoning/plan/replay/correlation。
  其余 339 个装饰端点（alert-rules/anomaly/canary/chaos/costs/defects/marketplace/
  whatif/reputation/...）全部移入 extended_router。
- **同法拆分**：collaboration 17→13（裁 shared-context/agents-discover/dashboard，
  correlation 与 memory-sync 因 tests/unit/test_api_batch3_part2 恢复）、
  security 12→12（裁 posture/secret-scan/audit-chain 后因 test_api_integration_mnr 恢复，
  净裁 0——保留 9 基础端点+3 契约端点）、evolution 15→4（/summary /stats /skills /trigger，
  frontend evolutionOps.ts 实际调用面；self-evolution/* 8 端点摘除为前端死调用）、
  memory 14→9（裁 export/import/sessions/layers×2）、parallel_agents 14→9
  （裁 messages/* 与 orchestrator/pipeline）、sso.auth_router 15→5（保留 MFA/会话管理，
  裁 LDAP/WebAuthn/conditional-access/oauth）、users 7→4、tenants 7→5、
  tenant_isolation 6→3（/quotas /usage /rbac-matrix，test_api_integration_mnr 对齐）、
  health 5→1（/live）、runs 8→3（/start 与 status/detail/timeline/correlation 摘除，
  重复面裁决给 agents，POST /{trace_id}/replay 因 tests/test_api.py 保留）、
  workbench 2→1（裁 /tasks）。
- **整模块摘除挂载（文件保留）**：browser_advanced、plugin_ecosystem、backup、
  backup_qdrant、memory_advanced、audit_enhanced、compliance_center、gdpr、tenant_quota、
  checkpoints、skills_api、artifacts、search、knowledge_graph、questions、work_mode、
  sessions、chat_history、tasks_ui、feedback、workspace、notifications、file_preview、
  api_keys（/api/v1/api-keys 零引用，security.py 的 /security/api-keys 覆盖前端）、
  streaming_enhanced、workflow_engine、tools_control、memory_control、execution_control、
  navigation_control、organization_control、migration、multi_agent、env_setup、dispatch。
- **恢复挂载（测试契约）**：feishu（test_security.py 签名测试）、execution
  （test_execution_draft_blocks_traversal_root）、desktop（test_api_browser_desktop_memory）、
  workbench（test_chat_entrypoint_contract）、tenants/users/tenant_isolation（拆分后）。
- **归档测试（3 个文件 → archive/api_templates_2026-08/tests/）**：
  test_feedback_endpoints.py、test_feedback_integration.py（feedback 域摘除）、
  test_notifications_api.py（notifications 摘除）。

### C2 前端死调用新增记录（不动前端代码）
/api/v1/evolution/self-evolution/*（evolutionOps.ts 8 处调用）、/api/v1/checkpoints*、
/api/skills*（SkillMarket 页面）、/api/v1/artifacts、/api/v1/search、/api/v1/knowledge-graph、
/api/v1/questions*、/api/v1/work/*、/api/v1/chat/history、/api/v1/tasks、/api/v1/feedback*、
/api/v1/workspace/*、/api/v1/notifications/*、/api/v1/files/*、/api/v1/backup*、
/api/v1/browser/advanced、/api/v1/plugin-ecosystem、/api/v1/audit/*、/api/v1/compliance、
/api/v1/gdpr、/api/v1/tenant/quota|usage、/api/v1/execution-control/*、/api/v1/memory-control/*、
/api/v1/tools-control/*、/api/v1/navigation-control/*、/api/v1/organization-control/*。

---

## C1（2026-08-02）

基线：启动挂载 **2429** 条路由（OpenAPI 2119 路径，duplicate operation id 警告 130）。
C1 结果：941 条路由（OpenAPI 819 路径，dup 0）。

> **C1 阶段 ≤300 目标曾不可达的说明**（C2 已通过 agents.py 拆分解决）：`backend/app/api/agents.py` 单文件定义 **361** 条路由
> （12077 行，含 runs 详情/plan/reasoning/replay/estimate/compare/deadline/tags 等
> 大量辅助端点）。agents 是编码 agent 的核心保留域，仅挂载它就已经超过 300。
> 要达到 ≤300 必须拆分/裁剪 agents.py 内部端点，这超出本 Phase「只做挂载层收敛、
> 不改路由业务逻辑」的范围，留待后续 Phase 决策。

## 一、保留并挂载的模块（77 个，`backend/app/main.py::_KEPT_ROUTER_MODULES`，
另加 sso.auth_router 与 backend.plugins.router）

### 编码 agent 核心（任务书明确保留域）
- **agent 运行**：agents、runs、streaming、streaming_enhanced、dispatch、execution、
  execution_control、verification、replay、planning、goals、work_mode
- **工具与执行环境**：tools、tools_batch、tools_control、code_execution、sandbox_tasks、
  code_review（B 轨刚恢复，/diff /pr /file）、issue_to_pr、env_setup
- **工作流**：workflows、workflow_engine
- **记忆**：memory、memory_advanced、memory_enhanced（保留 B1 的 /stats 与
  {memory_id} 顺序修复，挂载顺序 memory → memory_advanced → memory_enhanced）、memory_control
- **治理与安全基础**：approvals、audit（/api/v1/audit-logs）、audit_enhanced（/api/v1/audit）、
  auth、api_keys、security、tenants、tenant_quota、tenant_isolation
- **可观测**：health、metrics、traces
- **集成**：mcp、channels（Slack/Telegram 等 webhook，CSRF 豁免路径引用）、feishu
- **协作**：collaboration、multi_agent、parallel_agents
- **agent 支撑面**：checkpoints、search、knowledge_graph、browser、browser_advanced、
  artifacts、skills_api（skill 运行时挂载的那套 /api/skills）、skill_curator
  （tests/test_skill_curator_api 经主 app 调用）、skill_sediment、
  plugin_ecosystem、evolution（自进化主线）、questions
- **auth 补充**：sso.py 的 auth_router（/api/v1/auth 下 MFA/会话管理/WebAuthn，
  前端登录与安全页面对齐；oidc_router /api/v1/sso 不挂载）
- **main.py 直接路由**（不动）：/、/health、/ready、/metrics、/api-key/status、
  /api/v1/entry、/api/v1/csrf-token、/chat、SPA fallback；hooks 无独立 router
  （启动时从 .xagent/hooks.json 加载，见 startup_event）
- **插件运行时**：backend.plugins.router（/api/v1/plugins，P1-12 主循环接线）

### 前端/测试对齐保留（非明确保留域，但前端 console 或测试真实调用）
- sessions（/api/sessions，tests/test_agent_context_integration）
- messages（/api/v1/messages，3 个测试文件 + 前端 /messages/stream）
- chat_history（前端 /api/v1/chat/history）
- tasks_ui（前端 /api/v1/tasks）
- feedback（tests/unit/test_api_batch3_part2 + 前端 /feedback/stats/summary）
- sync（tests/test_sync_api_integration 用主 app + 前端大量调用）
- workspace、users、desktop、notifications、file_preview（前端调用）
- backup、backup_qdrant（tests/unit/test_api_batch4、tests/test_qdrant_snapshot + 前端 /backup/*）
- navigation_control、organization_control（前端 console 控制面）
- migration、overview、workbench（console 页面，各 1-2 端点）
- ops（/api/v1/ops/summary 仅 1 端点，tests/test_api_contracts 契约 + 前端对齐；
  运维域中唯一保留）
- compliance_center（/api/v1/compliance，前端调用；同前缀 compliance.py 归档）
- gdpr（前端调用，商用合规基础）

## 二、保留文件但不挂载（测试直接 import，路由面零增加）
- analytics、i18n、integrations、media、scheduler、skills、webhooks、compliance
  （tests/unit/test_tail_batch8_part2/part3 的 test_module_imports 逐一 import）
- agent.py — tests/unit/test_api_batch3_part1 import 其 helper（_context_from_principal 等）；
  其 /api/v1/agent 前缀由 streaming.py 服务
- files_v2.py — tests/test_security_fixes、test_api_batch3_part2 import 其 helper；
  /api/v1/files 前缀由 file_preview.py 服务（前端对齐）
- forum.py、enterprise.py — tests/unit/test_api_batch4 自构子 app 引用
- mobile.py — tests/test_mobile.py import
- sso.py、scim.py — tests/enterprise/ 自构子 app 引用（主 app 不再挂载，
  /api/v1/auth 前缀冲突裁决给 auth.py）
- plugin_market.py — tests/test_plugin_market、test_marketplace_comprehensive import
- helper 文件：errors、pagination、recovery_helpers、linked_summary、workflow_*（15 个）

## 三、归档（277 个对象：275 文件 + auth_api/ + v2/），按域一行理由
- smart_*（agriculture/building/city/education/healthcare/manufacturing/retail）、
  quantum_computing、space_computing、bioinformatics、autonomous_driving_sim、
  fintech_risk、supply_chain_visibility、energy_management、green_computing：
  与编码 agent 无关的行业模板域
- mesh_*（19 个）、service_mesh、intelligent_service_mesh：服务网格模板域
- data_*（governance/lineage/mesh/lakehouse/quality/... 24 个）：数据治理/数据平台模板域
- distributed_*（20 个）、dist_transaction、cluster_federation：分布式系统模板域
- billing、billing_engine、metering_billing、subscriptions、cost_*、cloud_cost、
  platform_cost_management、quota_management：计费/订阅/成本域（core/billing_init
  惰性引用 api.billing，仅函数内 import，不影响）
- dev_marketplace、marketplace_control、plugin_marketplace、skill_market*（4 个）、
  skills.py（死文件，与 skill_marketplace 同前缀 /api/v1/skills）：市场域
- forum_search、personalization、recommendations_advanced、partners、media、vision、
  voice_interaction、multimodal、i18n、translation_management、white_label、
  creative_studio、ai_writing、smart_contracts、smart_contract_management：非编码模板域
- enterprise_*（audit/cluster/features/im/migration/sso）、org：企业模板域（auth 基础保留）
- ops_*、aiops、intelligent_alerting、alert_*、anomaly_detection、
  incident_*、failure_prediction、event_*、chaos_*、resilience_engineering、
  disaster_recovery、dr_status、backup_scheduler、backup_monitoring：运维/AIOps 模板域
  （ops.py 因契约测试保留；analytics.py 因 tail_batch8 import 测试保留文件不挂载）
- intelligent_*（data_*/search/scheduler/release_pipeline/service_governance/
  document_processing）、feature_*、experiments、ab_testing、finetuning、
  federated_learning、nl_programming、prompt_engineering、test_generation、
  test_orchestration、lsp、code_completion：ML 平台/智能模板域（未被测试/前端引用）
- api_gateway、api_lifecycle、api_orchestration、api_testing、api_versioning、
  api_documentation、message_gateway、message_bus、message_queue、stream_processing、
  event_bus、scheduler、task_scheduler、intelligent_scheduler：网关/消息/调度模板域
- compliance、compliance_engine（同前缀裁决给 compliance_center）、contract_*、
  gdpr 之外的 privacy_engineering、reg_reporting、identity_governance、key_rotation、
  jwt_key_rotation、secret_management、security_scanning、cloud_native_security、
  ai_security、ai_ethics、ai_model_governance：治理合规模板域
- audit_enterprise、audit_export_api、audit_rotation_api、audit_trail、distributed_audit：
  审计扩展模板（audit/audit_enhanced 已保留）
- code_review_engine（与 code_review 同前缀 /api/v1/code-review，裁决给刚恢复的
  code_review.py）、code_review_ai：重复实现
- skill_evolution（与 evolution 同前缀 /api/v1/evolution，测试/前端对齐 evolution.py）、
  skill_curator：技能演化侧线（未引用）
- agents_v2、v2/、auth_api/：实验性 v2/独立 auth 应用，从未挂载且未被引用
- search_api（与 search 同前缀，裁决给端点更全的 search.py）、artifacts_api
  （与 artifacts 同前缀，裁决给覆盖 CRUD/render/search/stats 的 artifacts.py）
- 37+ 死路由文件（有 router 但从未挂载且未被 tests/backend 引用）一并归档：
  health_checks、evidence、webhooks、scheduler、translation_management、
  recommendations_advanced、subscriptions、vision、media、partners、personalization、
  i18n、jwt_key_rotation、backup_monitoring、enterprise_*、plugin_marketplace、
  skill_market* 等（见 git mv 记录）
- 其余未列举文件：容量/配置/缓存/发布/弹性/可观测管道等模板域
  （capacity_*、config_*、cache_*、release_*、elastic_scaling、load_*、log_*、
  metric_*、observability_*、platform_*、perf_tuning、db_autonomy、dep_*、
  dependency_*、env_orchestration、mobile 已保留文件除外、cloud_tasks、
  automations、change_*、form_engine、doc_*、ticket_routing、id_generator、
  link_analysis、trace_enhanced、trace_storage、tracing_enhanced、multi_region、
  multi_cloud_management、digital_twin、edge_computing、file 处理重复实现等）

## 四、前端死调用记录（不动前端代码，仅记录）
前端 `frontend/src/` 仍调用以下已归档域端点（属无编码核心链路的死调用）：
- /api/v1/analytics/*（analytics 运维模板域）
- /api/v1/ops、/api/v1/ops/summary（ops 运维模板域）
- /api/v1/billing（计费域）
- /api/v1/forum/*（forum 域；模块文件保留未挂载，主 app 不可达）
- /api/v1/plugin-market/、/api/v1/skill-market/（市场域）
- /api/v1/marketplace-control/*（市场域控制面）
- ~~/api/v1/sso、/api/v1/sso/providers、/api/v1/sso/status（企业 SSO）~~
  **2026-08-05 已正式挂载**（P1-02，G3 预算 300→330 评审通过）；
  同批挂载 /scim/v2（SCIM 2.0，11 路由）

## 五、归档的测试文件
无。所有被 tests/ 引用的 api 模块均按第二节保留（挂载或不挂载），
测试收集 0 error，无需归档任何测试文件。

## 六、其他说明
- audit_enhanced.py 的 `list_audit_logs` 重命名为 `list_audit_logs_enhanced`
  （与 audit.py 的 operation id 冲突，纯命名修复，业务逻辑未动），
  duplicate operation id 警告 130 → 0。
- `backend/app/api/__init__.py` 仅含 docstring，无 re-export，无需清理。


---

## 2026-08-05 补记：G3 预算 300 → 330

P1-02（真 SSO + SCIM，B7 级企业要求）挂载评审：oidc_router（7 路由）+
SCIM（11 路由）为合规必需，300 预算无法容纳。决策（用户批准）：
**G3 预算正式调整为 330**（为 multi_agent 挂载 +4 等后续项预留余量）。
挂载后实测 APIRoute 323（sso 7 + scim 11 + 其他 305）≤ 330。
同批 P1-14 sessions(+10)、P1-11 skills_api(+11)、批次 C messages(+4)、
批次 D discover(+1) 已在前期会话中挂载并计入当前总数。

---

## 2026-08-14 恢复登记

**背景**：8 月初"路由瘦身"（2429→332）将一批有前端页面的后端路由摘除挂载，
导致 10 个 UI 页面后端 404（用户实测巡检确认）。owner 决策：用户体验优先，
恢复这些能力；330 路由预算为文档级治理（非 CI 硬门禁），恢复后在此登记偏差。

**恢复的 12 个模块**（均在 `backend/app/main.py` `_KEPT_ROUTER_MODULES` 重新挂载）：

| 模块 | 前缀 | 说明 |
| --- | --- | --- |
| mcp | /api/v1/mcp | P1-01 MCP 官方 SDK 管理 API（17 端点）；自 archive/dead_code_2026-08 恢复，并修复 /tools/execute 构造 ToolCallInput 缺必填 tool_id 的 bug |
| checkpoints | /api/v1/checkpoints | P2-09 断点续跑；恢复前修复 tenant 直信问题（本地 get_principal 直接信任 request.state 并回落匿名 default 租户 → 统一走 dependencies.get_current_principal 标准鉴权链） |
| backup | /api/v1/backup | 备份管理 |
| backup_qdrant | /api/v1/backup/qdrant | Qdrant 备份 |
| chat_history | /api/v1/chat | 聊天历史 |
| tasks_ui | /api/v1/tasks | 任务 UI |
| work_mode | /api/v1/work | 工作模式/会话 |
| sessions | /api/sessions | P1-14 会话管理（此前已挂载，本次复核确认） |
| gdpr | /api/v1/gdpr | GDPR 合规 |
| analytics | /api/v1/analytics | 实时分析 |
| forum | /api/v1/forum | 论坛 |
| forum_search | /api/v1/forum/search | 论坛搜索；自 archive/api_templates_2026-08 恢复文件 |

**恢复原因**：上述路由均有前端页面直接依赖，摘除后对应 UI 页面后端 404，
影响可用性；owner 决策恢复（用户体验优先）。

**路由预算偏差**：恢复后实测 APIRoute 总数 **431**（恢复前 323，净增约 108，
含 SPA fallback），超出 G3 预算 330 约 101。偏差性质：文档级治理预算，
非 CI 硬门禁；后续如恢复硬门禁需重新评审预算或拆分 extended_router。

**同批附带修复**：sync 403 —— `sync:read/write/admin` 三个 scope 此前不在任何
角色的 ROLE_SCOPES 中，bootstrap key（admin 全 scope）访问 /api/v1/sync/stats
返回 403。已将 sync:read/write/admin 加入 admin、sync:read/write 加入
developer 的 ROLE_SCOPES；bootstrap key 访问 /api/v1/sync/stats 实测 200。
