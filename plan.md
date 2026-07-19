# P1-07 工作流存储工程师 — 执行计划（已完成）

范围: backend/app/core/workflows.py、backend/app/core/workflow_store*.py、backend/app/workflow_worker.py、backend/app/api/workflow*.py、backend/migrations/(独家)

## Stage 1 — workflows.py 内核增强 ✅
- [x] WorkflowRunRecord 增加 worker_id / heartbeat_at
- [x] WorkflowScheduleRecord / WorkflowScheduleRequest 增加 cron 字段
- [x] cron 解析: next_cron_run()(croniter, 缺失时降级 _MinimalCron 最小 5 段解析器)
- [x] WorkflowRepository.update_run_progress()(拓扑游标语义)
- [x] WorkflowScheduleStore.reschedule()(cron 重排)
- [x] WorkflowExecutor: 逐节点进度持久化 + resume()(崩溃恢复续跑)
- [x] WorkflowRuntimeManager: list/recover_interrupted_runs()
- [x] WorkflowScheduler: cron 校验/计算 + run_due 对 cron 记录重排而非终态

## Stage 2 — workflow_store.py (新建) ✅
- [x] 自包含 SQLAlchemy Base + definitions/runs/schedules 三张表模型
- [x] SQLWorkflowRepository / SQLWorkflowScheduleStore(接口对齐文件实现)
- [x] create_workflow_engine(URL 规范化: asyncpg→psycopg, aiosqlite→sqlite)
- [x] build_workflow_repository / build_workflow_schedule_store 工厂(db/file/auto, 失败显式降级+告警)

## Stage 3 — worker / API / migration / 依赖 ✅
- [x] workflow_worker.py: WorkflowSchedulerService(start/stop, 启动时崩溃恢复, 可被应用启动挂载)
- [x] api/workflows.py: schedule 端点透传 cron + 无效 cron 显式 400
- [x] backend/migrations/workflow_store_schema.sql (PostgreSQL DDL)
- [x] requirements.txt 追加 croniter>=6.0.0(已装 venv 6.2.4)

## Stage 4 — 验证 ✅
- [x] tests/test_workflow_cron.py(23 例: croniter + 降级解析器 + 周期调度行为)
- [x] tests/test_workflow_store_sql.py(17 例: sqlite 验证 SQLAlchemy 模型与 CRUD)
- [x] tests/test_workflow_recovery.py(14 例: kill 模拟→重启恢复; 服务启动恢复; SQL 端到端)
- [x] 既有回归(真实 tests/ 路径, --no-cov): 84 + 76 全过 0 劣化
- [x] E2E 实测: SQL 存储 + cron 周期调度 + SchedulerService 触发重排
- [x] CLI: python -m backend.app.workflow_worker --once exit=0
