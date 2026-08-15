-- 010_chat_history_tables.sql
-- Production PostgreSQL schema for durable, tenant-isolated chat history.
-- Development/test SQLite schemas are created by SQLAlchemy; production must
-- apply this migration before the API is allowed to serve chat history.

CREATE TABLE IF NOT EXISTS chat_sessions (
    id            VARCHAR(64) PRIMARY KEY,
    tenant_id     VARCHAR(64) NOT NULL,
    user_id       VARCHAR(64) NOT NULL,
    title         VARCHAR(255) NOT NULL DEFAULT '',
    agent_id      VARCHAR(64) NOT NULL DEFAULT 'default',
    created_at    DOUBLE PRECISION NOT NULL,
    updated_at    DOUBLE PRECISION NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_principal_updated
    ON chat_sessions (tenant_id, user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    tenant_id  VARCHAR(64) NOT NULL,
    user_id    VARCHAR(64) NOT NULL,
    role       VARCHAR(20) NOT NULL,
    content    TEXT NOT NULL,
    timestamp  DOUBLE PRECISION NOT NULL,
    metadata   JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_principal_session_time
    ON chat_messages (tenant_id, user_id, session_id, timestamp);

COMMENT ON TABLE chat_sessions IS 'Tenant and user scoped persistent chat sessions';
COMMENT ON TABLE chat_messages IS 'Persistent messages owned by a tenant scoped chat session';
