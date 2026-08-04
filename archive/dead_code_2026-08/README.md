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
| 技能死线：skills_manager skill_system_v2 skills_marketplace skills_cli skill_review_system skill_dependency_manager skill_search_engine skill_update_manager skill_version_manager skill_chain skill_review skills_registry skills_sandbox skills_executor | backend/app/core/ | 生产零引用；存活技能线为 core/skills/ loader + skill_agent_adapter + skills_core（skills_loader 依赖，保留） |
| 代码能力死线：code_completion context_aware code_generation code_refactoring code_understanding code_formatter | backend/app/core/ | 生产零引用 |
| code_generation_workflow.py | backend/app/workflows/ | 仅测试引用 |
| api/skills.py api/skills_api.py | backend/app/api/ | 死 router，未挂载 |
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

## 待决策（第三波，未动）

- core/cloud_executor.py（main.py 启停接线但无生产者，空转）
- core/collaboration/orchestrator.py + api/multi_agent.py（canonical 但未挂载）
- core/agent_communication_bus.py（router 写好未挂载）
- core/plugin_market/ + api/plugin_ecosystem.py（市场定位）
- skill_market_manager/complete/models、skill_adapter、skill_crawler、skill_evolution、skill_distillation/、skill_curator/ 等技能市场子岛（未逐一验证，疑死链）
- core/llm/ 包内 README/USAGE_GUIDE/INTEGRATION_GUIDE（文档漂移，引用更早归档的 llm/router.py）
- run_command 内联 `_run_in_docker`（tools.py:1664，第 7 套 Docker 沙箱，应并入 DockerSandbox——重构项非归档项）
