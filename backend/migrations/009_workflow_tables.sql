-- 009_workflow_tables.sql
-- Track C / P1-02: Workflow PostgreSQL Migration
-- Creates the canonical workflow tables for production PostgreSQL deployments.
-- These tables support workflow definitions, execution runs, and cron schedules.
--
-- NOTE: The SQLAlchemy models in backend/app/core/workflow_store.py auto-create
-- these tables via create_all() for SQLite/dev. This migration is for explicit
-- Postgres schema management (Alembic / manual apply).

-- ============================================================================
-- workflows: stores workflow definitions (DAG structure as JSONB)
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflows (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    definition  JSONB NOT NULL DEFAULT '{}',
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    tenant_id   VARCHAR(64) NOT NULL DEFAULT 'default',
    created_by  VARCHAR(64) NOT NULL DEFAULT 'anonymous',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workflows_tenant
    ON workflows (tenant_id);
CREATE INDEX IF NOT EXISTS idx_workflows_status
    ON workflows (status);
CREATE INDEX IF NOT EXISTS idx_workflows_updated
    ON workflows (updated_at DESC);

-- ============================================================================
-- workflow_runs: execution history for each workflow run
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow_runs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id  UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    status       VARCHAR(20) NOT NULL DEFAULT 'pending',
    input        JSONB NOT NULL DEFAULT '{}',
    output       JSONB,
    error        TEXT,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    tenant_id    VARCHAR(64) NOT NULL DEFAULT 'default',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow
    ON workflow_runs (workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status
    ON workflow_runs (status);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_tenant
    ON workflow_runs (tenant_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_started
    ON workflow_runs (started_at DESC);

-- ============================================================================
-- workflow_schedules: cron-based recurring execution schedules
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow_schedules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    cron_expression VARCHAR(128) NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    tenant_id       VARCHAR(64) NOT NULL DEFAULT 'default',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workflow_schedules_workflow
    ON workflow_schedules (workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_schedules_enabled
    ON workflow_schedules (enabled, next_run_at);
CREATE INDEX IF NOT EXISTS idx_workflow_schedules_tenant
    ON workflow_schedules (tenant_id);

-- ============================================================================
-- Comments for documentation
-- ============================================================================
COMMENT ON TABLE workflows IS 'Workflow definitions with DAG structure stored as JSONB';
COMMENT ON TABLE workflow_runs IS 'Execution history and state for each workflow run';
COMMENT ON TABLE workflow_schedules IS 'Cron-based recurring execution schedules for workflows';
