-- Performance Optimization: Add Composite Indexes
-- Date: 2026-05-27
-- Purpose: Improve query performance for memory search, list operations, and vector search

-- Index 1: Composite index for memory search with importance
-- Optimizes: Memory search queries with tenant_id, layer, and importance sorting
CREATE INDEX IF NOT EXISTS idx_memories_tenant_layer_importance_created
    ON memories (tenant_id, layer, importance DESC, created_at DESC);

-- Index 2: Partial index for high-importance memories (hot data)
-- Optimizes: Queries filtering for high-importance memories (importance >= 0.7)
-- Reduces index size by only indexing frequently accessed data
CREATE INDEX IF NOT EXISTS idx_memories_high_importance
    ON memories (tenant_id, created_at DESC)
    WHERE importance >= 0.7;

-- Index 3: Index for vector search with tenant filtering
-- Optimizes: Vector similarity search with tenant isolation
-- Uses IVFFlat for efficient approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS idx_memories_embedding_tenant
    ON memories USING ivfflat (embedding vector_cosine_ops)
    WHERE tenant_id IS NOT NULL;

-- Index 4: Index for audit log queries
-- Optimizes: Audit log filtering by tenant, action, and creation time
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_action_created
    ON audit_logs (tenant_id, action, created_at DESC);

-- Index 5: Index for run queries with status filtering
-- Optimizes: Run list queries with status filtering and time-based sorting
CREATE INDEX IF NOT EXISTS idx_runs_tenant_status_created
    ON runs (tenant_id, status, created_at DESC);

-- Index 6: Index for memory content full-text search
-- Optimizes: Full-text search queries on memory content
-- Uses GIN index for efficient text search
CREATE INDEX IF NOT EXISTS idx_memories_content_fts
    ON memories USING gin (to_tsvector('english', content));

-- Index 7: Index for memory tags search
-- Optimizes: Tag-based filtering in memory queries
CREATE INDEX IF NOT EXISTS idx_memories_tags
    ON memories USING gin (tags);

-- Index 8: Index for agent_id queries
-- Optimizes: Queries filtering by agent_id within tenant
CREATE INDEX IF NOT EXISTS idx_memories_tenant_agent_created
    ON memories (tenant_id, agent_id, created_at DESC);

-- Verification queries to check index creation
-- Run these after migration to verify indexes are created:
/*
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('memories', 'audit_logs', 'runs')
  AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

-- Check index sizes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE tablename IN ('memories', 'audit_logs', 'runs')
ORDER BY pg_relation_size(indexrelid) DESC;

-- Check index usage statistics
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename IN ('memories', 'audit_logs', 'runs')
ORDER BY idx_scan DESC;
*/
