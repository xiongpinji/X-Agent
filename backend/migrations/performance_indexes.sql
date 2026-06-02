-- Performance optimization indexes for X-Agent
-- Generated: 2026-05-27
-- Purpose: Add missing indexes to improve query performance

-- ============================================================================
-- Memory Table Indexes
-- ============================================================================

-- Composite index for tenant + agent + layer queries
CREATE INDEX IF NOT EXISTS idx_memories_tenant_agent_layer
    ON memories (tenant_id, agent_id, layer)
    WHERE agent_id IS NOT NULL;

-- Composite index for tenant + status + created_at queries
CREATE INDEX IF NOT EXISTS idx_memories_tenant_status_created
    ON memories (tenant_id, status, created_at DESC)
    WHERE status IS NOT NULL;

-- Index for importance-based queries
CREATE INDEX IF NOT EXISTS idx_memories_importance_layer
    ON memories (importance DESC, layer);

-- Index for recent memories (last 30 days)
CREATE INDEX IF NOT EXISTS idx_memories_created_recent
    ON memories (created_at DESC)
    WHERE created_at > NOW() - INTERVAL '30 days';

-- Index for tag-based searches
CREATE INDEX IF NOT EXISTS idx_memories_tags
    ON memories USING GIN (tags);

-- ============================================================================
-- Runs Table Indexes (if exists)
-- ============================================================================

-- Composite index for run queries
CREATE INDEX IF NOT EXISTS idx_runs_tenant_status_created
    ON runs (tenant_id, status, created_at DESC)
    WHERE status IS NOT NULL;

-- Index for user-specific runs
CREATE INDEX IF NOT EXISTS idx_runs_user_created
    ON runs (user_id, created_at DESC);

-- Index for trace lookups
CREATE INDEX IF NOT EXISTS idx_runs_trace_id
    ON runs (trace_id)
    WHERE trace_id IS NOT NULL;

-- ============================================================================
-- Workflow Table Indexes (if exists)
-- ============================================================================

-- Composite index for workflow queries
CREATE INDEX IF NOT EXISTS idx_workflows_tenant_status
    ON workflows (tenant_id, status)
    WHERE status IS NOT NULL;

-- Index for workflow schedule queries
CREATE INDEX IF NOT EXISTS idx_workflows_schedule_next_run
    ON workflows (next_run_at)
    WHERE next_run_at IS NOT NULL;

-- ============================================================================
-- Audit Table Indexes (if exists)
-- ============================================================================

-- Composite index for audit log queries
CREATE INDEX IF NOT EXISTS idx_audit_tenant_timestamp
    ON audit_logs (tenant_id, created_at DESC);

-- Index for action-based audit queries
CREATE INDEX IF NOT EXISTS idx_audit_action_timestamp
    ON audit_logs (action, created_at DESC);

-- ============================================================================
-- Trace Table Indexes (if exists)
-- ============================================================================

-- Composite index for trace queries
CREATE INDEX IF NOT EXISTS idx_traces_tenant_created
    ON traces (tenant_id, created_at DESC);

-- Index for trace status queries
CREATE INDEX IF NOT EXISTS idx_traces_status_created
    ON traces (status, created_at DESC)
    WHERE status IS NOT NULL;

-- ============================================================================
-- Performance Analysis Queries
-- ============================================================================

-- Query to find missing indexes
-- SELECT schemaname, tablename, indexname
-- FROM pg_indexes
-- WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
-- ORDER BY tablename, indexname;

-- Query to find slow queries
-- SELECT query, calls, mean_time, max_time
-- FROM pg_stat_statements
-- WHERE mean_time > 100
-- ORDER BY mean_time DESC
-- LIMIT 20;

-- Query to analyze index usage
-- SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
-- FROM pg_stat_user_indexes
-- ORDER BY idx_scan DESC;

-- ============================================================================
-- Connection Pool Configuration
-- ============================================================================

-- Recommended PostgreSQL configuration for optimal performance:
-- max_connections = 200
-- shared_buffers = 256MB (25% of RAM)
-- effective_cache_size = 1GB (50% of RAM)
-- work_mem = 16MB
-- maintenance_work_mem = 64MB
-- random_page_cost = 1.1
-- effective_io_concurrency = 200
-- wal_buffers = 16MB
-- default_statistics_target = 100

-- ============================================================================
-- Query Optimization Tips
-- ============================================================================

-- 1. Use EXPLAIN ANALYZE to understand query plans
--    EXPLAIN ANALYZE SELECT * FROM memories WHERE tenant_id = 'test' LIMIT 20;

-- 2. Vacuum and analyze tables regularly
--    VACUUM ANALYZE memories;

-- 3. Monitor slow queries with pg_stat_statements
--    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 4. Use prepared statements to avoid query parsing overhead

-- 5. Batch operations when possible to reduce round trips

-- 6. Use connection pooling (PgBouncer, pgpool) for better resource utilization

-- ============================================================================
-- Index Maintenance
-- ============================================================================

-- Reindex fragmented indexes (run periodically)
-- REINDEX INDEX idx_memories_tenant_layer_created;

-- Check index bloat
-- SELECT schemaname, tablename, indexname,
--        pg_size_pretty(pg_relation_size(indexrelid)) as index_size
-- FROM pg_stat_user_indexes
-- ORDER BY pg_relation_size(indexrelid) DESC;

-- ============================================================================
-- Monitoring Queries
-- ============================================================================

-- Monitor cache hit ratio (should be >99%)
-- SELECT
--   sum(heap_blks_read) as heap_read,
--   sum(heap_blks_hit) as heap_hit,
--   sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
-- FROM pg_statio_user_tables;

-- Monitor table sizes
-- SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
-- FROM pg_tables
-- WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
-- ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Monitor active connections
-- SELECT datname, usename, application_name, state, query_start
-- FROM pg_stat_activity
-- WHERE state != 'idle'
-- ORDER BY query_start;
