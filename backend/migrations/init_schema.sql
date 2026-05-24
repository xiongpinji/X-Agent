CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    agent_id UUID NULL,
    content TEXT NOT NULL,
    layer INTEGER NOT NULL CHECK (layer BETWEEN 1 AND 4),
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
