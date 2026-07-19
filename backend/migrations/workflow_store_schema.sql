-- P1-07: 工作流存储 Postgres 迁移（definitions / runs / schedules）
-- 与 backend/app/core/workflow_store.py 中的 SQLAlchemy 模型一一对应。
-- doc 列保存完整 pydantic 文档（JSONB），热点字段镜像为可查询列。
-- SQLite/开发环境无需执行本脚本：SQLWorkflowRepository 会自动 create_all。

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id          VARCHAR(36) PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    doc         JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_definitions_updated
    ON workflow_definitions (updated_at DESC);

-- 运行态外置：status / resume_cursor / worker_id / heartbeat_at 支撑崩溃恢复。
-- RUNNING 且无活跃 worker 认领的 run 可被重启的 worker 从 resume_cursor 续跑。
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id        VARCHAR(36) PRIMARY KEY,
    workflow_id   VARCHAR(36) NOT NULL,
    status        VARCHAR(20) NOT NULL,
    tenant_id     VARCHAR(64) NOT NULL,
    user_id       VARCHAR(64) NOT NULL DEFAULT 'anonymous',
    resume_cursor INTEGER NOT NULL DEFAULT 0,
    worker_id     VARCHAR(128),
    heartbeat_at  TIMESTAMPTZ,
    started_at    TIMESTAMPTZ NOT NULL,
    completed_at  TIMESTAMPTZ,
    doc           JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_started
    ON workflow_runs (workflow_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status
    ON workflow_runs (status);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_tenant
    ON workflow_runs (tenant_id);

-- 调度表：cron 非空表示周期调度，run_at 始终为下一次触发时间；
-- 触发后由调度器 reschedule 重排而非进入终态。
CREATE TABLE IF NOT EXISTS workflow_schedules (
    schedule_id  VARCHAR(36) PRIMARY KEY,
    workflow_id  VARCHAR(36) NOT NULL,
    status       VARCHAR(20) NOT NULL,
    tenant_id    VARCHAR(64) NOT NULL,
    user_id      VARCHAR(64) NOT NULL DEFAULT 'anonymous',
    run_at       TIMESTAMPTZ NOT NULL,
    cron         VARCHAR(128),
    run_id       VARCHAR(36),
    locked_by    VARCHAR(128),
    locked_until TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL,
    doc          JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_schedules_due
    ON workflow_schedules (status, run_at);
CREATE INDEX IF NOT EXISTS idx_workflow_schedules_tenant
    ON workflow_schedules (tenant_id);
CREATE INDEX IF NOT EXISTS idx_workflow_schedules_workflow
    ON workflow_schedules (workflow_id);

-- 多 worker 并发领取到期调度的推荐语句（Postgres 行锁）：
--   SELECT * FROM workflow_schedules
--   WHERE status = 'pending' AND run_at <= now()
--   ORDER BY run_at ASC
--   LIMIT :limit
--   FOR UPDATE SKIP LOCKED;
