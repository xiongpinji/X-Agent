"""Database optimization configuration and monitoring.

Provides configuration templates and monitoring utilities for database performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DatabaseOptimizationConfig:
    """Database optimization configuration."""

    # Connection pool settings
    max_connections: int = 200
    min_connections: int = 10
    connection_timeout_seconds: int = 30
    idle_timeout_seconds: int = 900

    # Query optimization
    enable_query_cache: bool = True
    query_cache_ttl_seconds: int = 300
    query_cache_max_size: int = 1000
    enable_redis_cache: bool = False
    redis_url: str | None = None

    # N+1 query detection
    enable_query_analysis: bool = True
    n1_detection_threshold: int = 5  # Alert if more than 5 similar queries

    # Index optimization
    enable_index_stats: bool = True
    index_stats_interval_seconds: int = 3600

    # Slow query logging
    slow_query_threshold_ms: float = 100.0
    enable_slow_query_log: bool = True

    # Batch operation settings
    batch_size: int = 100
    batch_timeout_ms: int = 50

    # PostgreSQL tuning
    shared_buffers_mb: int = 256
    effective_cache_size_mb: int = 1024
    work_mem_mb: int = 16
    maintenance_work_mem_mb: int = 64
    random_page_cost: float = 1.1
    effective_io_concurrency: int = 200
    jit_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "connection_pool": {
                "max_connections": self.max_connections,
                "min_connections": self.min_connections,
                "connection_timeout_seconds": self.connection_timeout_seconds,
                "idle_timeout_seconds": self.idle_timeout_seconds,
            },
            "query_optimization": {
                "enable_query_cache": self.enable_query_cache,
                "query_cache_ttl_seconds": self.query_cache_ttl_seconds,
                "query_cache_max_size": self.query_cache_max_size,
                "enable_redis_cache": self.enable_redis_cache,
            },
            "n1_detection": {
                "enable_query_analysis": self.enable_query_analysis,
                "threshold": self.n1_detection_threshold,
            },
            "slow_query_logging": {
                "enabled": self.enable_slow_query_log,
                "threshold_ms": self.slow_query_threshold_ms,
            },
            "batch_operations": {
                "batch_size": self.batch_size,
                "batch_timeout_ms": self.batch_timeout_ms,
            },
            "postgresql_tuning": {
                "shared_buffers_mb": self.shared_buffers_mb,
                "effective_cache_size_mb": self.effective_cache_size_mb,
                "work_mem_mb": self.work_mem_mb,
                "maintenance_work_mem_mb": self.maintenance_work_mem_mb,
                "random_page_cost": self.random_page_cost,
                "effective_io_concurrency": self.effective_io_concurrency,
                "jit_enabled": self.jit_enabled,
            },
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> DatabaseOptimizationConfig:
        """Create from dictionary."""
        return DatabaseOptimizationConfig(
            max_connections=data.get("max_connections", 200),
            min_connections=data.get("min_connections", 10),
            connection_timeout_seconds=data.get("connection_timeout_seconds", 30),
            idle_timeout_seconds=data.get("idle_timeout_seconds", 900),
            enable_query_cache=data.get("enable_query_cache", True),
            query_cache_ttl_seconds=data.get("query_cache_ttl_seconds", 300),
            query_cache_max_size=data.get("query_cache_max_size", 1000),
            enable_redis_cache=data.get("enable_redis_cache", False),
            redis_url=data.get("redis_url"),
            enable_query_analysis=data.get("enable_query_analysis", True),
            n1_detection_threshold=data.get("n1_detection_threshold", 5),
            enable_index_stats=data.get("enable_index_stats", True),
            index_stats_interval_seconds=data.get("index_stats_interval_seconds", 3600),
            slow_query_threshold_ms=data.get("slow_query_threshold_ms", 100.0),
            enable_slow_query_log=data.get("enable_slow_query_log", True),
            batch_size=data.get("batch_size", 100),
            batch_timeout_ms=data.get("batch_timeout_ms", 50),
            shared_buffers_mb=data.get("shared_buffers_mb", 256),
            effective_cache_size_mb=data.get("effective_cache_size_mb", 1024),
            work_mem_mb=data.get("work_mem_mb", 16),
            maintenance_work_mem_mb=data.get("maintenance_work_mem_mb", 64),
            random_page_cost=data.get("random_page_cost", 1.1),
            effective_io_concurrency=data.get("effective_io_concurrency", 200),
            jit_enabled=data.get("jit_enabled", True),
        )


class DatabaseMonitor:
    """Monitor database performance metrics."""

    def __init__(self, pool: Any):
        self.pool = pool
        self.metrics: dict[str, Any] = {}

    async def get_cache_hit_ratio(self) -> float:
        """Get cache hit ratio (should be >99%)."""
        query = """
            SELECT
              sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
            FROM pg_statio_user_tables
        """
        result = await self.pool.fetchval(query)
        return float(result) if result else 0.0

    async def get_table_sizes(self) -> dict[str, str]:
        """Get sizes of all tables."""
        query = """
            SELECT
              tablename,
              pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """
        rows = await self.pool.fetch(query)
        return {row["tablename"]: row["size"] for row in rows}

    async def get_index_stats(self) -> list[dict[str, Any]]:
        """Get index usage statistics."""
        query = """
            SELECT
              schemaname,
              tablename,
              indexname,
              idx_scan,
              idx_tup_read,
              idx_tup_fetch,
              pg_size_pretty(pg_relation_size(indexrelid)) as index_size
            FROM pg_stat_user_indexes
            ORDER BY idx_scan DESC
        """
        rows = await self.pool.fetch(query)
        return [dict(row) for row in rows]

    async def get_unused_indexes(self) -> list[dict[str, Any]]:
        """Find unused indexes."""
        query = """
            SELECT
              schemaname,
              tablename,
              indexname,
              pg_size_pretty(pg_relation_size(indexrelid)) as index_size
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
            ORDER BY pg_relation_size(indexrelid) DESC
        """
        rows = await self.pool.fetch(query)
        return [dict(row) for row in rows]

    async def get_slow_queries(self, threshold_ms: float = 100.0) -> list[dict[str, Any]]:
        """Get slow queries from pg_stat_statements."""
        query = """
            SELECT
              query,
              calls,
              mean_time,
              max_time,
              stddev_time,
              rows
            FROM pg_stat_statements
            WHERE mean_time > $1
            ORDER BY mean_time DESC
            LIMIT 20
        """
        try:
            rows = await self.pool.fetch(query, threshold_ms)
            return [dict(row) for row in rows]
        except Exception:
            # pg_stat_statements extension may not be installed
            return []

    async def get_connection_stats(self) -> dict[str, Any]:
        """Get connection statistics."""
        query = """
            SELECT
              datname,
              usename,
              application_name,
              state,
              COUNT(*) as count
            FROM pg_stat_activity
            GROUP BY datname, usename, application_name, state
        """
        rows = await self.pool.fetch(query)
        return {
            "total_connections": len(rows),
            "by_state": {row["state"]: row["count"] for row in rows},
            "details": [dict(row) for row in rows],
        }

    async def get_missing_indexes(self) -> list[dict[str, Any]]:
        """Identify potentially missing indexes based on sequential scans."""
        query = """
            SELECT
              schemaname,
              tablename,
              seq_scan,
              seq_tup_read,
              idx_scan,
              pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as table_size
            FROM pg_stat_user_tables
            WHERE seq_scan > 1000
              AND idx_scan < seq_scan
            ORDER BY seq_scan DESC
            LIMIT 20
        """
        rows = await self.pool.fetch(query)
        return [dict(row) for row in rows]

    async def get_full_report(self) -> dict[str, Any]:
        """Get comprehensive database performance report."""
        return {
            "cache_hit_ratio": await self.get_cache_hit_ratio(),
            "table_sizes": await self.get_table_sizes(),
            "index_stats": await self.get_index_stats(),
            "unused_indexes": await self.get_unused_indexes(),
            "slow_queries": await self.get_slow_queries(),
            "connection_stats": await self.get_connection_stats(),
            "missing_indexes": await self.get_missing_indexes(),
        }


class QueryPerformanceAnalyzer:
    """Analyze query performance and provide recommendations."""

    @staticmethod
    def analyze_report(report: dict[str, Any]) -> dict[str, Any]:
        """Analyze performance report and provide recommendations."""
        recommendations = []

        # Check cache hit ratio
        cache_ratio = report.get("cache_hit_ratio", 0)
        if cache_ratio < 0.99:
            recommendations.append({
                "severity": "HIGH",
                "issue": "Low cache hit ratio",
                "current": f"{cache_ratio * 100:.2f}%",
                "target": "99%+",
                "action": "Increase shared_buffers or effective_cache_size",
            })

        # Check for unused indexes
        unused = report.get("unused_indexes", [])
        if unused:
            recommendations.append({
                "severity": "MEDIUM",
                "issue": f"Found {len(unused)} unused indexes",
                "action": "Consider dropping unused indexes to reduce maintenance overhead",
                "indexes": [idx["indexname"] for idx in unused[:5]],
            })

        # Check for slow queries
        slow = report.get("slow_queries", [])
        if slow:
            recommendations.append({
                "severity": "HIGH",
                "issue": f"Found {len(slow)} slow queries",
                "action": "Review slow queries and add appropriate indexes",
                "queries": [q["query"][:100] for q in slow[:3]],
            })

        # Check for missing indexes
        missing = report.get("missing_indexes", [])
        if missing:
            recommendations.append({
                "severity": "MEDIUM",
                "issue": f"Found {len(missing)} tables with high sequential scans",
                "action": "Consider adding indexes on frequently scanned columns",
                "tables": [m["tablename"] for m in missing[:5]],
            })

        return {
            "total_recommendations": len(recommendations),
            "recommendations": recommendations,
        }


# PostgreSQL configuration template
POSTGRESQL_CONFIG_TEMPLATE = """
# X-Agent Database Optimization Configuration
# Add these settings to postgresql.conf

# Connection Pool
max_connections = 200
superuser_reserved_connections = 10

# Memory Settings
shared_buffers = 256MB              # 25% of RAM
effective_cache_size = 1GB          # 50% of RAM
work_mem = 16MB                     # shared_buffers / max_connections
maintenance_work_mem = 64MB

# Query Planning
random_page_cost = 1.1              # For SSD
effective_io_concurrency = 200      # For SSD

# WAL Configuration
wal_buffers = 16MB
checkpoint_completion_target = 0.9
wal_compression = on

# Query Optimization
jit = on                            # Enable JIT compilation
jit_above_cost = 100000
jit_inline_above_cost = 500000
jit_optimize_above_cost = 500000

# Statistics
default_statistics_target = 100

# Logging
log_min_duration_statement = 100    # Log queries > 100ms
log_statement = 'mod'               # Log DDL and DML
log_duration = off
log_lock_waits = on

# Extensions
shared_preload_libraries = 'pg_stat_statements'
"""
