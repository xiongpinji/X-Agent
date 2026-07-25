CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    agent_id UUID NULL,
    content TEXT NOT NULL,
    layer INTEGER NOT NULL CHECK (layer BETWEEN 1 AND 10),
    importance DOUBLE PRECISION NOT NULL CHECK (importance >= 0 AND importance <= 1),
    tags TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_tenant_layer_created
    ON memories (tenant_id, layer, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_memories_content_trgm
    ON memories USING gin (content gin_trgm_ops);

CREATE TABLE IF NOT EXISTS trace_events (
    id BIGSERIAL PRIMARY KEY,
    trace_id UUID NOT NULL,
    event TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trace_events_trace_time
    ON trace_events (trace_id, timestamp ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_trace_events_event_time
    ON trace_events (event, timestamp DESC);

-- ============================================================================
-- RBAC tables (Phase 1.6)
-- ============================================================================

CREATE TABLE IF NOT EXISTS rbac_roles (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    permissions JSONB NOT NULL DEFAULT '[]',
    parent_roles TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rbac_user_roles (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    role_id UUID NOT NULL REFERENCES rbac_roles(id) ON DELETE CASCADE,
    assigned_by TEXT NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NULL,
    delegated_to TEXT[] NOT NULL DEFAULT '{}',
    scope JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_rbac_user_roles_user
    ON rbac_user_roles (user_id);

CREATE TABLE IF NOT EXISTS rbac_audit_logs (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    result TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    attributes JSONB NOT NULL DEFAULT '{}',
    ip_address TEXT NULL,
    user_agent TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_rbac_audit_user_time
    ON rbac_audit_logs (user_id, timestamp DESC);

-- ============================================================================
-- Workflow tables (P1-07)
-- 工作流表 DDL 已迁移至独立文件 workflow_store_schema.sql，
-- 与 backend/app/core/workflow_store.py 中的 SQLAlchemy 模型一一对应。
-- 部署时请执行: psql -f backend/migrations/workflow_store_schema.sql
-- ============================================================================
