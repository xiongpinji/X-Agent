# 死代码归档（2026-08-04，Phase 1 收敛第一+二波）

> 依据：三路全仓引用分析（explore 子代理）+ 逐项人工复核（backend/cli/tests grep 验证零生产引用）。
> 保护网：ruff `backend/ --select F,E9` 全绿、全量 pytest 收集无错误、全量测试跑通验证。
> 归档目录保留原相对路径，可整体回迁。

## REMOVED（生产树移出）

### 第一波（零生产引用 + 零测试依赖）
| 项 | 原路径 | 说明 |
|---|---|---|
| code_sandbox.py | backend/app/core/ | 零 import；仅 agent_spawner 错误提示字符串提及 |
| workflow_pg_repository.py | backend/app/core/ | 全仓零引用（workflow_store 自带 SQL 实现） |
| workflow_engine.py | backend/app/api/ | 假数据 stub router，从未挂载 |
| dependencies_refactored.py | backend/app/ | 死 DI 接线，全仓零引用 |
| container_config.py | backend/app/core/ | 仅被 dependencies_refactored 引用（级联死亡） |
| llm_resilience.py | backend/app/core/ | 仅 2 份 md 文档引用 |
| plugins/（2 模板+指南） | backend/app/ | 插件模板，零引用 |
| plugin_crawler.py | backend/app/services/ | 零生产引用 |
| plugin_system/ plugin_cache/ plugin_reviews/ plugin_updates/ | 仓根 | 空目录（仅空子目录），直接删除 |

### 第二波（零生产引用，测试随迁/拆分）
| 项 | 原路径 | 说明 |
|---|---|---|
| execution/ 整包（5 文件 ~1260 行） | backend/app/core/ | P0-18 AST 黑名单沙箱所在包；execute_code 已走 core/sandbox 包 |
| llm/adapters/（4 适配器 630 行） | backend/app/core/llm/ | 零调用零测试；`llm/__init__.py` 已同步移除导出 |
| llm/fallback.py monitor.py prompt_optimizer.py streaming.py | backend/app/core/llm/ | 仅 `llm/__init__.py` 再导出 + test_llm_enhanced |
| llm_manager.py llm_api.py llm_ab_testing.py llm_cache.py llm_deduplicator.py llm_evaluation.py llm_monitoring.py（~3228 行） | backend/app/core/ | 审计"LLMManager 未进主循环"残留簇，生产零接线 |
| prompt_engineering.py | backend/app/core/ | 仅被 llm 簇引用（级联） |
| db_cache.py memory_cache.py performance_cache.py query_cache.py（883 行） | backend/app/core/ | 缓存死线；存活缓存为 core/cache.py、config/cache.py、tool_result_cache.py、sandbox/container_cache.py、services/search/cache.py |
| performance_optimization_integration.py optimized_stores.py performance_config.py | backend/app/core/ | 缓存死链级联 |
| search/（整目录）+ api/search.py | backend/app/core/、backend/app/api/ | search_cache 死链；router 未挂载；存活搜索为 services/search/ |
| tool_sandbox.py | backend/app/core/ | 仅 test_security_hardening 一个类引用（已拆分随迁） |
| 技能死线：skill_system_v2 skills_cli skill_review_system skill_dependency_manager skill_search_engine skill_update_manager skill_version_manager skill_chain skill_review | backend/app/core/ | 生产零引用；存活技能线为 core/skills/ loader + skill_agent_adapter + skills_core（skills_loader 依赖，保留） |
| 代码能力死线：code_completion context_aware code_generation code_refactoring code_understanding code_formatter | backend/app/core/ | 生产零引用 |
| code_generation_workflow.py | backend/app/workflows/ | 仅测试引用 |
| api/skills.py api/skills_api.py | backend/app/api/ | ~~死 router~~ **已回迁**：test_skill_runtime_p1_11.py 证实其为 P1-11 维护中的可挂载 router（含租户解析/路由顺序测试），连同依赖链 skills_manager/skills_executor/skills_marketplace/skills_registry/skills_sandbox 一并回迁 |
| api/plugin_market.py | backend/app/api/ | 未挂载，仅测试引用 |
| translation_service.py | backend/app/services/ | 零引用 |

### 随迁测试
- 整体随迁：test_code_execution.py、test_sandbox_pooling.py、test_llm_manager_integration.py、test_llm_framework.py、test_search.py、test_code_capabilities.py、test_code_generation_quality.py、test_skill_market_advanced.py、test_skill_system_v2.py、test_skills_system.py、unit/test_skill_code_batch6.py、test_plugin_market.py、test_marketplace_comprehensive.py
- 拆分随迁（死代码类）：test_llm_enhanced_dead.py（fallback/streaming/prompt_optimizer/monitor 四类）、test_cache_dead_caches.py（db/llm/memory cache 三类）、test_cache_benchmarks_dead.py、unit/test_services_batch7_context_aware.py、test_security_hardening_tool_sandbox.py

## KEPT（保留，生产接线或活配置路径）

- **LLM**：core/llm/backends.py（唯一正主）、llm_settings、quota、cost_optimizer、profiles、anthropic/ollama_backend；flag-gated 保留 smart_router+selector（XAGENT_LLM_ROUTING_MODE=smart）、moa（XAGENT_MOA_ENABLED）
- **Workflow**：core/workflows.py、workflow_store.py、workflow_worker.py、api/workflows.py
- **沙箱**：core/sandbox/ 全部 9 模块、task_queue、api/sandbox_tasks、core/pipelines/、code_executor.py（已接线 API）
- **ToolRegistry**：core/tools.py（运行时）、core/tool_registry.py（ToolCatalog）
- **协作**：collaboration/store+delegation、agent_spawner、parallel_agent_executor、api/collaboration、api/parallel_agents
- **技能活线**：core/skills/、skills_loader、skill_agent_adapter、skills_core
- **缓存活线**：core/cache.py、config/cache.py、tool_result_cache、sandbox/container_cache、services/search/cache

## 回迁记录（归档后验证修正）

全量测试发现 11 个新失败，根因两类：
1. **api/skills_api.py 误判**：P1-11 技能运行时测试（test_skill_runtime_p1_11.py，19 个用例）主动挂载该 router 并测试租户隔离/路由顺序——属维护中代码。已连同依赖链（skills_manager/skills_executor/skills_marketplace/skills_registry/skills_sandbox）及其测试 test_skills_system.py 一并回迁。
2. **冒烟测试引用**：tests/unit/test_tail_batch8_part{1,3} 的 TestCodeCompletion（import code_completion）、part3 的 TestApiSearch（import api.search）为机械冒烟类，测试对象确为死代码——冒烟类随迁归档，模块不回迁。

修正后全量测试回归固有失败基线（run16 终验：`28 failed, 7052 passed`，27 项与 run12 基线完全一致，1 项为阈值敏感互换 test_hybrid_memory::test_search_performance——单跑 3.06s 通过，非回归）。

终验前另补 4 处慢测试超时标记（test_api_extended / test_api_error_scenarios 的 rapid/concurrent requests，全量 CPU 争抢下可超 30s 默认超时）。

## 待决策（第三波，未动）

- ~~core/cloud_executor.py~~ **已归档（第三波）**：main.py 启停接线已摘除，全仓无生产者的空转实现
- core/collaboration/orchestrator.py + api/multi_agent.py：**保留不挂载**（决策见下）
- ~~core/agent_communication_bus.py~~ **保留（实活）**：无独立 router，被已挂载的 api/parallel_agents.py 与 parallel_execution_engine 使用
- ~~core/plugin_market/ + api/plugin_ecosystem.py~~ **已归档（第三波，市场类）**：零生产引用；测试 test_multi_agent_plugin_audit.py 已拆分（orchestrator/audit 部分保留）
- ~~技能市场子岛~~ **已归档（第三波）**：skill_market_manager/complete/models、skill_adapter、skill_crawler、skill_evolution、skill_development_tools（死链验证：skill_market_models→skill_adapter→skill_market_manager→零引用）；保留 skill_curator/（api 存活）、skill_distillation/（main.py 引用）
- core/llm/ 包内 README/USAGE_GUIDE/INTEGRATION_GUIDE（文档漂移，引用更早归档的 llm/router.py）
- run_command 内联 `_run_in_docker`（tools.py:1664，第 7 套 Docker 沙箱，应并入 DockerSandbox——重构项非归档项）

## 第三波决策记录（2026-08-04）

| 项 | 决策 | 理由 |
|---|---|---|
| cloud_executor.py（665 行） | 归档 | 有启停接线但零生产者，永远空转；main.py 两处调用已摘除 |
| orchestrator + api/multi_agent.py（617 行） | **保留不挂载** | canonical P2-01 且有测试（test_multi_agent + plugin_audit 拆分后保留部分）；G3 路由预算 300/300 零余量，挂载 4 条路由即破门禁——挂载留待路由预算评审。**2026-08-05 批次 E-lite 更新**：`_delegate_subtask` 假实现已真实化（接 CollaborationDelegator，真实子 AgentLoop + failure_policy 裁决），api 已补鉴权与租户注入，达可挂载状态；仍不挂载原因不变（路由预算），tests/test_orchestrator_real_delegation.py 背书 |
| agent_communication_bus.py（608 行） | 保留 | 实活：被已挂载的 parallel_agents / parallel_execution_engine 引用（探查报告“未挂载 router”为误判） |
| plugin_market/ + plugin_ecosystem.py（903 行） | 归档 | 市场功能非当前交付面，零生产引用 |
| 技能市场子岛（7 模块） | 归档 | 死链验证零外部引用；skill_curator/skill_distillation 实活保留 |

第三波终验（run17）：`27 failed, 7020 passed, 247 skipped in 1:05:47`，无挂死一次跑完；
失败清单与固有基线完全一致（少 1 个阈值敏感 flake），零新增回归。

## P1-01 系统 B 遗留归档（2026-08-04，第四波单项）

| 项 | 原路径 | 说明 |
|---|---|---|
| mcp.py（843 行） | backend/app/api/ | MCP「系统 B」：历史遗留 HTTP API，`initialize_mcp_system()` 从未接线、端点运行时不可用；曾经 `main.py` `_KEPT_ROUTER_MODULES` 动态清单挂载（本次已同步移除该条目，否则启动 ModuleNotFoundError）；归档前验证全生产树零显式 import；其依赖（MCPToolAdapter / file/search/browser 工具 / MCPClient / MCPConfig）均被系统 A 或测试使用，不受影响；决策记录见 `docs/developer/reports/MCP_IMPLEMENTATION_STATUS.md` |
| skills.py（~220 行） | backend/app/api/ | 第二套技能管理 API（/api/v1/skills，无测试背书），与 P1-11 管理平面 skills_api.py 重复；裁决挂载 skills_api（测试齐全），本文件归档消除重复；import 冒烟类（tests/unit/test_tail_batch8_part2 TestApiSkills）已同步移除 |

## P1-09 批次 A：协作幽灵模块归档（2026-08-04）

| 项 | 原路径 | 说明 |
|---|---|---|
| task_dispatcher.py（438 行） | backend/app/core/ | 零生产调用方（唯一引用：test_feature_enhancements 的 TestTaskDispatcher 类 + demo 脚本）；测试类已拆分随迁 tests/test_task_dispatcher.py |
| agent_coordinator.py（446 行） | backend/app/core/ | 零生产调用方（collaboration 收敛图原注 "used by api/agents_v2.py" 为过时叙事）；测试随 test_multi_agent.py 拆分归档 |
| parallel_executor.py（350 行） | backend/app/core/ | 零生产调用方（canonical 为 parallel_agent_executor.py）；测试同上拆分 |
| agent_recovery.py（432 行） | backend/app/core/ | 零生产调用方；测试同上拆分 + 两处 import 冒烟类移除 |
| demo_feature_enhancements.py（437 行） | scripts/ | task_dispatcher 演示脚本，随主模块归档 |

- 测试拆分：tests/test_multi_agent.py 保留 agent_spawner 存活面 6 用例，幽灵模块 10 用例归档为 tests/test_multi_agent_ghost_modules.py（记录用，不参与收集）。
- **未动**：advanced_features.py（含 MultiAgentCoordinator）——被 deprecated 的 parallel_execution_engine.py 引用（TaskScheduler），随批次 C 对 engine 的裁决一并处理。

## P1-09 批次 C：通信协议落地 + deprecated 簇归档（2026-08-04）

**裁决**：`core/agent_communication_bus.py` 为唯一 agent 间通信面，其 messages
send/broadcast/publish/stats 4 端点从 extended_router 移入 api/parallel_agents.py
主 router 挂载（鉴权 agent:run 已有；路由 295/300）。

| 项 | 原路径 | 说明 |
|---|---|---|
| parallel_execution_engine.py（825 行） | backend/app/core/ | deprecated 旧并行引擎；与 benchmark 互引闭环，零生产引用（仅测试/benchmark）；测试 test_parallel_execution_engine.py 随迁 |
| parallel_execution_benchmark.py（436 行） | backend/app/core/ | 旧引擎基准模块，随 engine 归档 |
| advanced_features.py（461 行） | backend/app/core/ | MultiAgentCoordinator/TaskScheduler/AdaptivePlanner/LearningEngine；唯一生产引用方为 engine（TaskScheduler），级联归档；测试 test_capability_improvements.py 随迁 |

- 测试拆分：tests/unit/test_services_batch7.py 移除 10 个 engine 冒烟类（其余 i18n/workflow/desktop 等类保留）；tests/unit/test_tail_batch8_part2.py 移除 advanced_features 冒烟类。 |
