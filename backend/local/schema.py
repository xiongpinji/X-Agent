"""
X-Agent Local Database Schema Design

This module defines the complete SQLite schema for local data management,
including metadata, business data, sync management, and encryption.
"""

# ============================================================================
# METADATA & VERSION CONTROL
# ============================================================================

LOCAL_METADATA_TABLE = """
CREATE TABLE IF NOT EXISTS local_metadata (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    local_version INTEGER NOT NULL DEFAULT 1,
    cloud_version INTEGER NOT NULL DEFAULT 0,
    last_modified_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    is_encrypted BOOLEAN DEFAULT FALSE,
    checksum TEXT,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_local_metadata_entity ON local_metadata(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_local_metadata_modified ON local_metadata(last_modified_at);
CREATE INDEX IF NOT EXISTS idx_local_metadata_synced ON local_metadata(last_synced_at);
CREATE INDEX IF NOT EXISTS idx_local_metadata_deleted ON local_metadata(is_deleted);
"""

SYNC_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS sync_state (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    state TEXT NOT NULL,
    last_sync_attempt_at TIMESTAMP,
    last_sync_success_at TIMESTAMP,
    sync_error_count INTEGER DEFAULT 0,
    last_error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    next_retry_at TIMESTAMP,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_sync_state_entity ON sync_state(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_sync_state_state ON sync_state(state);
CREATE INDEX IF NOT EXISTS idx_sync_state_retry ON sync_state(next_retry_at);
"""

CONFLICT_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS conflict_log (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    local_version INTEGER,
    cloud_version INTEGER,
    local_data JSON,
    cloud_data JSON,
    resolution_strategy TEXT,
    resolved_data JSON,
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conflict_log_entity ON conflict_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_conflict_log_type ON conflict_log(conflict_type);
CREATE INDEX IF NOT EXISTS idx_conflict_log_resolved ON conflict_log(resolved_at);
"""

# ============================================================================
# BUSINESS DATA TABLES
# ============================================================================

LOCAL_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS local_memories (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    agent_id TEXT,
    session_id TEXT,
    content TEXT NOT NULL,
    layer INTEGER NOT NULL CHECK(layer >= 1 AND layer <= 10),
    importance REAL NOT NULL DEFAULT 0.5 CHECK(importance >= 0.0 AND importance <= 1.0),
    tags TEXT,
    embedding BLOB,
    scope_owner_agent_id TEXT,
    scope_share_scope TEXT DEFAULT 'private',
    scope_visibility TEXT DEFAULT 'private',
    scope_shared_with TEXT,
    scope_project_id TEXT,
    scope_room_id TEXT,
    scope_task_id TEXT,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    local_version INTEGER NOT NULL DEFAULT 1,
    cloud_version INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_local_memories_tenant ON local_memories(tenant_id);
CREATE INDEX IF NOT EXISTS idx_local_memories_agent ON local_memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_local_memories_session ON local_memories(session_id);
CREATE INDEX IF NOT EXISTS idx_local_memories_layer ON local_memories(layer);
CREATE INDEX IF NOT EXISTS idx_local_memories_importance ON local_memories(importance);
CREATE INDEX IF NOT EXISTS idx_local_memories_created ON local_memories(created_at);
"""

LOCAL_WORKFLOWS_TABLE = """
CREATE TABLE IF NOT EXISTS local_workflows (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    definition JSON NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    tags TEXT,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    local_version INTEGER NOT NULL DEFAULT 1,
    cloud_version INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_local_workflows_tenant ON local_workflows(tenant_id);
CREATE INDEX IF NOT EXISTS idx_local_workflows_status ON local_workflows(status);
CREATE INDEX IF NOT EXISTS idx_local_workflows_created ON local_workflows(created_at);
"""

LOCAL_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS local_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    agent_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    input JSON,
    output JSON,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    local_version INTEGER NOT NULL DEFAULT 1,
    cloud_version INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_local_runs_tenant ON local_runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_local_runs_workflow ON local_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_local_runs_agent ON local_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_local_runs_status ON local_runs(status);
CREATE INDEX IF NOT EXISTS idx_local_runs_created ON local_runs(created_at);
"""

LOCAL_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS local_sessions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    agent_id TEXT,
    title TEXT,
    summary TEXT,
    tags TEXT,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_memory_id TEXT,
    shared BOOLEAN DEFAULT FALSE,
    room_id TEXT,
    project_id TEXT,
    local_version INTEGER NOT NULL DEFAULT 1,
    cloud_version INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_local_sessions_tenant ON local_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_local_sessions_user ON local_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_local_sessions_agent ON local_sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_local_sessions_created ON local_sessions(created_at);
"""

# ============================================================================
# SYNC MANAGEMENT TABLES
# ============================================================================

SYNC_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS sync_queue (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    data JSON NOT NULL,
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status);
CREATE INDEX IF NOT EXISTS idx_sync_queue_priority ON sync_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_sync_queue_created ON sync_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_sync_queue_entity ON sync_queue(entity_type, entity_id);
"""

OFFLINE_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS offline_queue (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    data JSON NOT NULL,
    priority INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_offline_queue_status ON offline_queue(status);
CREATE INDEX IF NOT EXISTS idx_offline_queue_priority ON offline_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_offline_queue_created ON offline_queue(created_at);
"""

SYNC_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS sync_history (
    id TEXT PRIMARY KEY,
    sync_batch_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    direction TEXT NOT NULL,
    status TEXT NOT NULL,
    local_version INTEGER,
    cloud_version INTEGER,
    error_message TEXT,
    duration_ms INTEGER,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sync_history_batch ON sync_history(sync_batch_id);
CREATE INDEX IF NOT EXISTS idx_sync_history_entity ON sync_history(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_sync_history_status ON sync_history(status);
CREATE INDEX IF NOT EXISTS idx_sync_history_created ON sync_history(created_at);
"""

# ============================================================================
# ENCRYPTION & SECURITY TABLES
# ============================================================================

ENCRYPTED_DATA_TABLE = """
CREATE TABLE IF NOT EXISTS encrypted_data (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    data_type TEXT NOT NULL,
    encrypted_content BLOB NOT NULL,
    iv BLOB NOT NULL,
    salt BLOB NOT NULL,
    algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM',
    key_version INTEGER NOT NULL DEFAULT 1,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_encrypted_data_entity ON encrypted_data(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_encrypted_data_type ON encrypted_data(data_type);
"""

ENCRYPTION_KEYS_TABLE = """
CREATE TABLE IF NOT EXISTS encryption_keys (
    id TEXT PRIMARY KEY,
    key_version INTEGER NOT NULL UNIQUE,
    key_material BLOB NOT NULL,
    algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM',
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rotated_at TIMESTAMP,
    expires_at TIMESTAMP,
    metadata JSON
);

CREATE INDEX IF NOT EXISTS idx_encryption_keys_version ON encryption_keys(key_version);
CREATE INDEX IF NOT EXISTS idx_encryption_keys_active ON encryption_keys(is_active);
"""

# ============================================================================
# CACHE & PERFORMANCE TABLES
# ============================================================================

CACHE_INDEX_TABLE = """
CREATE TABLE IF NOT EXISTS cache_index (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    cache_key TEXT NOT NULL UNIQUE,
    cache_value BLOB,
    ttl_seconds INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    hit_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cache_index_entity ON cache_index(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_cache_index_expires ON cache_index(expires_at);
"""

PRELOAD_HINTS_TABLE = """
CREATE TABLE IF NOT EXISTS preload_hints (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,
    priority REAL DEFAULT 0.5,
    metadata JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_preload_hints_priority ON preload_hints(priority DESC);
CREATE INDEX IF NOT EXISTS idx_preload_hints_accessed ON preload_hints(last_accessed_at);
"""

# ============================================================================
# SCHEMA INITIALIZATION
# ============================================================================

ALL_TABLES = [
    LOCAL_METADATA_TABLE,
    SYNC_STATE_TABLE,
    CONFLICT_LOG_TABLE,
    LOCAL_MEMORIES_TABLE,
    LOCAL_WORKFLOWS_TABLE,
    LOCAL_RUNS_TABLE,
    LOCAL_SESSIONS_TABLE,
    SYNC_QUEUE_TABLE,
    OFFLINE_QUEUE_TABLE,
    SYNC_HISTORY_TABLE,
    ENCRYPTED_DATA_TABLE,
    ENCRYPTION_KEYS_TABLE,
    CACHE_INDEX_TABLE,
    PRELOAD_HINTS_TABLE,
]

# ============================================================================
# MIGRATION SCRIPTS
# ============================================================================

MIGRATION_V1_INITIAL = """
-- Initial schema creation
-- Version: 1.0
-- Date: 2026-05-27

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- Create all tables
""" + "\n".join(ALL_TABLES)

# ============================================================================
# UTILITY VIEWS
# ============================================================================

PENDING_SYNC_VIEW = """
CREATE VIEW IF NOT EXISTS pending_sync AS
SELECT
    sq.id,
    sq.entity_type,
    sq.entity_id,
    sq.operation,
    sq.priority,
    sq.retry_count,
    sq.created_at,
    ss.state as sync_state
FROM sync_queue sq
LEFT JOIN sync_state ss ON sq.entity_type = ss.entity_type AND sq.entity_id = ss.entity_id
WHERE sq.status = 'pending'
ORDER BY sq.priority DESC, sq.created_at ASC;
"""

CONFLICTED_ENTITIES_VIEW = """
CREATE VIEW IF NOT EXISTS conflicted_entities AS
SELECT
    cl.entity_type,
    cl.entity_id,
    COUNT(*) as conflict_count,
    MAX(cl.created_at) as latest_conflict,
    GROUP_CONCAT(DISTINCT cl.conflict_type) as conflict_types
FROM conflict_log cl
WHERE cl.resolved_at IS NULL
GROUP BY cl.entity_type, cl.entity_id;
"""

SYNC_PERFORMANCE_VIEW = """
CREATE VIEW IF NOT EXISTS sync_performance AS
SELECT
    DATE(sh.created_at) as sync_date,
    sh.entity_type,
    COUNT(*) as total_operations,
    SUM(CASE WHEN sh.status = 'success' THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN sh.status = 'failed' THEN 1 ELSE 0 END) as failed,
    AVG(sh.duration_ms) as avg_duration_ms,
    MAX(sh.duration_ms) as max_duration_ms
FROM sync_history sh
GROUP BY DATE(sh.created_at), sh.entity_type;
"""

# ============================================================================
# SCHEMA CONSTANTS
# ============================================================================

SCHEMA_VERSION = "1.0"
SCHEMA_DATE = "2026-05-27"

# Entity types
ENTITY_TYPES = {
    "memory": "local_memories",
    "workflow": "local_workflows",
    "run": "local_runs",
    "session": "local_sessions",
}

# Sync operations
SYNC_OPERATIONS = {
    "create": "CREATE",
    "update": "UPDATE",
    "delete": "DELETE",
    "merge": "MERGE",
}

# Sync states
SYNC_STATES = {
    "pending": "PENDING",
    "syncing": "SYNCING",
    "synced": "SYNCED",
    "failed": "FAILED",
    "conflict": "CONFLICT",
}

# Conflict types
CONFLICT_TYPES = {
    "update_conflict": "UPDATE_CONFLICT",
    "delete_conflict": "DELETE_CONFLICT",
    "create_conflict": "CREATE_CONFLICT",
}

# Resolution strategies
RESOLUTION_STRATEGIES = {
    "last_write_wins": "LAST_WRITE_WINS",
    "local_wins": "LOCAL_WINS",
    "cloud_wins": "CLOUD_WINS",
    "manual": "MANUAL",
    "merge": "MERGE",
}
