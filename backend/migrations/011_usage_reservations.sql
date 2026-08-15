-- 011_usage_reservations.sql
-- Durable, tenant-isolated provider usage reservations and audit outbox.

CREATE TABLE IF NOT EXISTS usage_reservations (
    id                VARCHAR(36) PRIMARY KEY,
    tenant_id         VARCHAR(64) NOT NULL,
    operation_id      VARCHAR(255) NOT NULL,
    root_operation_id VARCHAR(255) NOT NULL,
    user_id           VARCHAR(64),
    provider          VARCHAR(64) NOT NULL,
    model             VARCHAR(128) NOT NULL,
    request_hash      VARCHAR(64) NOT NULL,
    estimated_cost    NUMERIC(18, 8) NOT NULL,
    actual_cost       NUMERIC(18, 8),
    tokens_used       INTEGER NOT NULL DEFAULT 0,
    status            VARCHAR(32) NOT NULL CHECK (
        status IN ('reserved', 'confirmed', 'refunded', 'submission_unknown')
    ),
    run_id             VARCHAR(128),
    trace_id           VARCHAR(128),
    created_at         DOUBLE PRECISION NOT NULL,
    updated_at         DOUBLE PRECISION NOT NULL,
    CONSTRAINT uq_usage_reservation_operation UNIQUE (tenant_id, operation_id)
);

CREATE INDEX IF NOT EXISTS idx_usage_reservations_root
    ON usage_reservations (tenant_id, root_operation_id);
CREATE INDEX IF NOT EXISTS idx_usage_reservations_month
    ON usage_reservations (tenant_id, updated_at);

CREATE TABLE IF NOT EXISTS usage_reservation_ledger (
    id             VARCHAR(36) PRIMARY KEY,
    reservation_id VARCHAR(36) NOT NULL REFERENCES usage_reservations(id) ON DELETE CASCADE,
    tenant_id      VARCHAR(64) NOT NULL,
    operation_id   VARCHAR(255) NOT NULL,
    from_status    VARCHAR(32) NOT NULL,
    to_status      VARCHAR(32) NOT NULL CHECK (
        to_status IN ('confirmed', 'refunded', 'submission_unknown')
    ),
    actual_cost    NUMERIC(18, 8),
    tokens_used    INTEGER NOT NULL DEFAULT 0,
    created_at     DOUBLE PRECISION NOT NULL,
    CONSTRAINT uq_usage_ledger_terminal_transition UNIQUE (reservation_id)
);

CREATE INDEX IF NOT EXISTS idx_usage_ledger_operation
    ON usage_reservation_ledger (tenant_id, operation_id, created_at);

CREATE TABLE IF NOT EXISTS usage_reservation_audit_outbox (
    id            VARCHAR(36) PRIMARY KEY,
    tenant_id     VARCHAR(64) NOT NULL,
    operation_id  VARCHAR(255) NOT NULL,
    action        VARCHAR(64) NOT NULL,
    status        VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'delivering', 'delivered')),
    audit_id      VARCHAR(64),
    delivery_token VARCHAR(64),
    lease_expires_at DOUBLE PRECISION,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error    VARCHAR(128),
    payload       JSONB NOT NULL,
    created_at    DOUBLE PRECISION NOT NULL,
    updated_at    DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_audit_outbox_pending
    ON usage_reservation_audit_outbox (status, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_audit_outbox_operation
    ON usage_reservation_audit_outbox (tenant_id, operation_id);
