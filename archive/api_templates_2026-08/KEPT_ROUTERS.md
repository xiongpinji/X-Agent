# Track C 路由大瘦身 — 保留/剔除清单（2026-08-02）

基线：启动挂载 **2429** 条路由（OpenAPI 2119 路径，duplicate operation id 警告 130）。
结果：启动挂载 **941** 条路由（OpenAPI 819 路径，duplicate operation id 警告 **0**）。

> **≤300 目标不可达的说明**：`backend/app/api/agents.py` 单文件定义 **361** 条路由
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
- /api/v1/sso、/api/v1/sso/providers、/api/v1/sso/status（企业 SSO；
  模块文件保留未挂载供 tests/enterprise 使用）

## 五、归档的测试文件
无。所有被 tests/ 引用的 api 模块均按第二节保留（挂载或不挂载），
测试收集 0 error，无需归档任何测试文件。

## 六、其他说明
- audit_enhanced.py 的 `list_audit_logs` 重命名为 `list_audit_logs_enhanced`
  （与 audit.py 的 operation id 冲突，纯命名修复，业务逻辑未动），
  duplicate operation id 警告 130 → 0。
- `backend/app/api/__init__.py` 仅含 docstring，无 re-export，无需清理。
