"""Database query optimization for X-Agent.

Implements query batching, connection pooling optimization, and query result caching.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger("xagent.db_optimization")


@dataclass
class QueryStats:
    """Query performance statistics."""

    total_queries: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    slow_queries: int = 0
    slow_query_threshold_ms: float = 100.0

    def record_query(self, duration_ms: float) -> None:
        """Record a query execution."""
        self.total_queries += 1
        self.total_time_ms += duration_ms
        self.avg_time_ms = self.total_time_ms / self.total_queries
        if duration_ms > self.slow_query_threshold_ms:
            self.slow_queries += 1


class QueryBatcher:
    """Batch multiple queries for efficient execution."""

    def __init__(self, batch_size: int = 100, batch_timeout_ms: int = 50):
        self._batch_size = batch_size
        self._batch_timeout_ms = batch_timeout_ms
        self._pending_queries: list[tuple[str, dict[str, Any]]] = []
        self._pending_futures: list[asyncio.Future] = []
        self._lock = asyncio.Lock()
        self._batch_task: asyncio.Task | None = None

    async def add_query(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Add a query to the batch."""
        future: asyncio.Future = asyncio.Future()

        async with self._lock:
            self._pending_queries.append((query, params or {}))
            self._pending_futures.append(future)

            # Start batch processing if needed
            if len(self._pending_queries) >= self._batch_size:
                await self._flush_batch()
            elif self._batch_task is None:
                self._batch_task = asyncio.create_task(self._batch_timeout_handler())

        return await future

    async def _batch_timeout_handler(self) -> None:
        """Flush batch after timeout."""
        await asyncio.sleep(self._batch_timeout_ms / 1000.0)
        async with self._lock:
            if self._pending_queries:
                await self._flush_batch()

    async def _flush_batch(self) -> None:
        """Execute all pending queries in batch."""
        if not self._pending_queries:
            return

        queries = self._pending_queries[:]
        futures = self._pending_futures[:]
        self._pending_queries.clear()
        self._pending_futures.clear()
        self._batch_task = None

        # Execute queries in parallel
        results = await asyncio.gather(
            *[self._execute_query(q, p) for q, p in queries],
            return_exceptions=True,
        )

        # Resolve futures
        for future, result in zip(futures, results, strict=False):
            if isinstance(result, Exception):
                future.set_exception(result)
            else:
                future.set_result(result)

    async def _execute_query(self, query: str, params: dict[str, Any]) -> Any:
        """Execute a single query."""
        # This would be implemented with actual database connection
        # For now, return a placeholder
        return None


class ConnectionPoolOptimizer:
    """Optimize database connection pool settings."""

    @staticmethod
    def create_optimized_engine(
        database_url: str,
        pool_size: int = 20,
        max_overflow: int = 40,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        echo: bool = False,
    ):
        """Create SQLAlchemy engine with optimized pool settings.

        Args:
            database_url: Database connection URL
            pool_size: Number of connections to keep in pool
            max_overflow: Maximum overflow connections
            pool_recycle: Recycle connections after N seconds
            pool_pre_ping: Test connections before using
            echo: Log SQL statements

        Returns:
            Configured AsyncEngine
        """
        # 不能给 async engine 显式传同步 QueuePool —— SQLAlchemy 在构造期就会抛
        # "QueuePool cannot be used with asyncio engine"。async engine 的默认池
        # 已是 AsyncAdaptedQueuePool，因此非 sqlite 不显式指定 poolclass、只传并发
        # 参数；sqlite 用 NullPool 且不接受 pool_size/max_overflow。
        is_sqlite = "sqlite" in database_url
        engine_kwargs: dict[str, Any] = {"echo": echo}
        if is_sqlite:
            engine_kwargs["poolclass"] = NullPool
            engine_kwargs["connect_args"] = {
                "timeout": 30,
                "check_same_thread": False,
            }
        else:
            engine_kwargs.update(
                {
                    "pool_size": pool_size,
                    "max_overflow": max_overflow,
                    "pool_recycle": pool_recycle,
                    "pool_pre_ping": pool_pre_ping,
                }
            )

        engine = create_async_engine(database_url, **engine_kwargs)

        return engine


class QueryOptimizer:
    """Optimize query execution."""

    def __init__(self):
        self._stats = QueryStats()
        self._slow_queries: list[tuple[str, float]] = []

    def record_query(self, query: str, duration_ms: float) -> None:
        """Record query execution time."""
        self._stats.record_query(duration_ms)
        if duration_ms > self._stats.slow_query_threshold_ms:
            self._slow_queries.append((query, duration_ms))
            # Keep only last 100 slow queries
            if len(self._slow_queries) > 100:
                self._slow_queries.pop(0)

    def get_stats(self) -> QueryStats:
        """Get query statistics."""
        return self._stats

    def get_slow_queries(self, limit: int = 10) -> list[tuple[str, float]]:
        """Get slowest queries."""
        return sorted(self._slow_queries, key=lambda x: x[1], reverse=True)[:limit]


class IndexOptimizationStrategy:
    """Strategies for database index optimization."""

    # Common index patterns for X-Agent
    RECOMMENDED_INDEXES = {
        "memories": [
            "CREATE INDEX IF NOT EXISTS idx_memories_tenant_layer_created ON memories (tenant_id, layer, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_memories_content_trgm ON memories USING gin (content gin_trgm_ops)",
            "CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories (importance DESC) WHERE importance > 0.7",
            "CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories USING gin (tags)",
        ],
        "runs": [
            "CREATE INDEX IF NOT EXISTS idx_runs_tenant_created ON runs (tenant_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs (status) WHERE status IN ('running', 'pending')",
            "CREATE INDEX IF NOT EXISTS idx_runs_workflow_id ON runs (workflow_id)",
        ],
        "workflows": [
            "CREATE INDEX IF NOT EXISTS idx_workflows_tenant_created ON workflows (tenant_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_workflows_name ON workflows (name) WHERE deleted_at IS NULL",
        ],
        "audit_logs": [
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_created ON audit_logs (tenant_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action) WHERE created_at > NOW() - INTERVAL '30 days'",
        ],
    }

    @staticmethod
    async def apply_indexes(session: AsyncSession, table_name: str) -> None:
        """Apply recommended indexes for a table."""
        indexes = IndexOptimizationStrategy.RECOMMENDED_INDEXES.get(table_name, [])
        for index_sql in indexes:
            try:
                await session.execute(sa.text(index_sql))
                logger.info(f"Applied index: {index_sql[:60]}...")
            except Exception as e:
                logger.warning(f"Failed to apply index: {e}")

    @staticmethod
    async def analyze_table(session: AsyncSession, table_name: str) -> None:
        """Analyze table statistics for query planner."""
        try:
            await session.execute(sa.text(f"ANALYZE {table_name}"))
            logger.info(f"Analyzed table: {table_name}")
        except Exception as e:
            logger.warning(f"Failed to analyze table {table_name}: {e}")


class QueryResultCache:
    """Cache query results with automatic invalidation."""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._ttl_seconds = ttl_seconds
        self._invalidation_rules: dict[str, list[str]] = {}

    def cache_result(self, query_key: str, result: Any) -> None:
        """Cache query result."""
        self._cache[query_key] = (result, datetime.now(UTC))

    def get_cached_result(self, query_key: str) -> Any | None:
        """Get cached query result if not expired."""
        if query_key not in self._cache:
            return None

        result, cached_at = self._cache[query_key]
        if datetime.now(UTC) > cached_at + timedelta(seconds=self._ttl_seconds):
            del self._cache[query_key]
            return None

        return result

    def invalidate(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        keys_to_delete = [k for k in self._cache if pattern in k]
        for key in keys_to_delete:
            del self._cache[key]

    def register_invalidation_rule(self, trigger_query: str, invalidate_patterns: list[str]) -> None:
        """Register cache invalidation rule."""
        self._invalidation_rules[trigger_query] = invalidate_patterns

    def apply_invalidation_rules(self, executed_query: str) -> None:
        """Apply invalidation rules after query execution."""
        patterns = self._invalidation_rules.get(executed_query, [])
        for pattern in patterns:
            self.invalidate(pattern)


class DatabaseOptimizationManager:
    """Centralized database optimization management."""

    def __init__(self, database_url: str):
        self._database_url = database_url
        self._query_optimizer = QueryOptimizer()
        self._query_result_cache = QueryResultCache()
        self._query_batcher = QueryBatcher()

    def get_query_optimizer(self) -> QueryOptimizer:
        """Get query optimizer."""
        return self._query_optimizer

    def get_query_result_cache(self) -> QueryResultCache:
        """Get query result cache."""
        return self._query_result_cache

    def get_query_batcher(self) -> QueryBatcher:
        """Get query batcher."""
        return self._query_batcher

    def get_stats(self) -> dict[str, Any]:
        """Get optimization statistics."""
        return {
            "query_stats": self._query_optimizer.get_stats().__dict__,
            "slow_queries": self._query_optimizer.get_slow_queries(),
            "cache_size": len(self._query_result_cache._cache),
        }
