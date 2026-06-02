-- Database Query Optimization
-- Date: 2026-05-27
-- Purpose: Add missing indexes, optimize slow queries, and improve N+1 query patterns

-- ============================================================================
-- PHASE 1: Add Missing Composite Indexes for Common Query Patterns
-- ============================================================================

-- Index for list_runs with tenant + status + created_at filtering
CREATE INDEX IF NOT EXISTS idx_runs_tenant_status_created_desc
    ON runs (tenant_id, status, created_at DESC)
    WHERE status IS NOT NULL;

-- Index for user-specific run queries
CREATE INDEX IF NOT EXISTS idx_runs_user_created_desc
    ON runs (user_id, created_at DESC);

-- Index for trace lookups by run
CREATE INDEX IF NOT EXISTS idx_runs_trace_id_tenant
    ON runs (trace_id, tenant_id)
    WHERE trace_id IS NOT NULL;

-- Index for workflow status queries (latest run per workflow)
CREATE INDEX IF NOT EXISTS idx_runs_workflow_created_desc
    ON runs (workflow_id, created_at DESC)
    WHERE workflow_id IS NOT NULL;

-- ============================================================================
-- PHASE 2: Optimize Memory Search Queries
-- ============================================================================

-- Composite index for memory search with all common filters
CREATE INDEX IF NOT EXISTS idx_memories_tenant_layer_importance_created
    ON memories (tenant_id, layer, importance DESC, created_at DESC);

-- Partial index for high-importance memories (hot data optimization)
CREATE INDEX IF NOT EXISTS idx_memories_high_importance
    ON memories (tenant_id, created_at DESC)
    WHERE importance >= 0.7;

-- Index for agent-specific memory queries
CREATE INDEX IF NOT EXISTS idx_memories_tenant_agent_created
    ON memories (tenant_id, agent_id, created_at DESC)
    WHERE agent_id IS NOT NULL;

-- Full-text search index for memory content
CREATE INDEX IF NOT EXISTS idx_memories_content_fts
    ON memories USING gin (to_tsvector('english', content));

-- ============================================================================
-- PHASE 3: Optimize Workflow Queries
-- ============================================================================

-- Index for workflow status queries
CREATE INDEX IF NOT EXISTS idx_workflows_tenant_status_created
    ON workflows (tenant_id, status, created_at DESC)
    WHERE status IS NOT NULL;

-- Index for workflow schedule queries
CREATE INDEX IF NOT EXISTS idx_workflows_next_run_at
    ON workflows (next_run_at)
    WHERE next_run_at IS NOT NULL;

-- ============================================================================
-- PHASE 4: Optimize Audit Log Queries
-- ============================================================================

-- Composite index for audit log filtering
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_action_created
    ON audit_logs (tenant_id, action, created_at DESC);

-- Index for audit log queries by resource
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_created
    ON audit_logs (resource_type, resource_id, created_at DESC);

-- ============================================================================
-- PHASE 5: Optimize Trace Event Queries
-- ============================================================================

-- Index for trace event queries with time range
CREATE INDEX IF NOT EXISTS idx_trace_events_trace_timestamp
    ON trace_events (trace_id, timestamp DESC);

-- Index for event type queries
CREATE INDEX IF NOT EXISTS idx_trace_events_event_timestamp
    ON trace_events (event, timestamp DESC);

-- ============================================================================
-- PHASE 6: Add Covering Indexes for Common SELECT Patterns
-- ============================================================================

-- Covering index for run list queries (includes all commonly selected columns)
CREATE INDEX IF NOT EXISTS idx_runs_list_covering
    ON runs (tenant_id, created_at DESC)
    INCLUDE (status, user_id, trace_id, workflow_id);

-- Covering index for memory list queries
CREATE INDEX IF NOT EXISTS idx_memories_list_covering
    ON memories (tenant_id, created_at DESC)
    INCLUDE (layer, importance, agent_id);

-- ============================================================================
-- PHASE 7: Optimize Vector Search (if pgvector is enabled)
-- ============================================================================

-- Vector search index with tenant filtering
CREATE INDEX IF NOT EXISTS idx_memories_embedding_tenant
    ON memories USING ivfflat (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL AND tenant_id IS NOT NULL;

-- ============================================================================
-- PHASE 8: Statistics and Query Plan Optimization
-- ============================================================================

-- Increase statistics target for better query planning
ALTER TABLE runs ALTER COLUMN status SET STATISTICS 100;
ALTER TABLE runs ALTER COLUMN tenant_id SET STATISTICS 100;
ALTER TABLE memories ALTER COLUMN tenant_id SET STATISTICS 100;
ALTER TABLE memories ALTER COLUMN layer SET STATISTICS 100;
ALTER TABLE memories ALTER COLUMN importance SET STATISTICS 100;

-- Analyze tables to update statistics
ANALYZE runs;
ANALYZE memories;
ANALYZE workflows;
ANALYZE audit_logs;
ANALYZE trace_events;

-- ============================================================================
-- PHASE 9: Connection Pool Configuration Recommendations
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
-- jit = on (for complex queries)

-- ============================================================================
-- PHASE 10: Monitoring and Maintenance Queries
-- ============================================================================

-- Query to identify slow queries (run periodically)
-- SELECT query, calls, mean_time, max_time, stddev_time
-- FROM pg_stat_statements
-- WHERE mean_time > 100
-- ORDER BY mean_time DESC
-- LIMIT 20;

-- Query to check index usage
-- SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
-- FROM pg_stat_user_indexes
-- ORDER BY idx_scan DESC;

-- Query to find unused indexes
-- SELECT schemaname, tablename, indexname, idx_scan
-- FROM pg_stat_user_indexes
-- WHERE idx_scan = 0
-- ORDER BY pg_relation_size(indexrelid) DESC;

-- Query to check cache hit ratio (should be >99%)
-- SELECT
--   sum(heap_blks_read) as heap_read,
--   sum(heap_blks_hit) as heap_hit,
--   sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
-- FROM pg_statio_user_tables;

-- Query to monitor table sizes
-- SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
-- FROM pg_tables
-- WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
-- ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ============================================================================
-- PHASE 11: Index Maintenance Schedule
-- ============================================================================

-- Reindex fragmented indexes (run weekly)
-- REINDEX INDEX CONCURRENTLY idx_runs_tenant_status_created_desc;
-- REINDEX INDEX CONCURRENTLY idx_memories_tenant_layer_importance_created;

-- Vacuum and analyze (run daily)
-- VACUUM ANALYZE runs;
-- VACUUM ANALYZE memories;
-- VACUUM ANALYZE workflows;
