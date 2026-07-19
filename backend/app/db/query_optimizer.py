"""Database query optimization module for X-Agent.

This module provides query optimization strategies including:
- Index management
- N+1 query prevention
- Query batching
- Result caching
- Complex JOIN optimization
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, UTC
from typing import Any, Callable, TypeVar, Generic

import asyncpg

logger = logging.getLogger(__name__)

T = TypeVar("T")


class QueryOptimizer:
    """Manages database query optimization strategies."""

    # Critical indexes for performance
    PERFORMANCE_INDEXES = [
        # Runs table indexes
        "CREATE INDEX IF NOT EXISTS idx_runs_user_id ON runs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)",
        "CREATE INDEX IF NOT EXISTS idx_runs_tenant_id ON runs(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_runs_tenant_status ON runs(tenant_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_runs_user_created ON runs(user_id, created_at DESC)",

        # Memories table indexes
        "CREATE INDEX IF NOT EXISTS idx_memories_tenant_id ON memories(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_memories_layer ON memories(layer)",
        "CREATE INDEX IF NOT EXISTS idx_memories_tenant_layer ON memories(tenant_id, layer)",
        "CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)",
        "CREATE INDEX IF NOT EXISTS idx_memories_tenant_layer_created ON memories(tenant_id, layer, created_at DESC)",

        # Traces table indexes
        "CREATE INDEX IF NOT EXISTS idx_traces_run_id ON traces(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_traces_tenant_id ON traces(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status)",

        # Audit logs indexes
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON audit_logs(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)",

        # Approvals table indexes
        "CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status)",
        "CREATE INDEX IF NOT EXISTS idx_approvals_tenant_id ON approvals(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_approvals_created_at ON approvals(created_at DESC)",
    ]

    @staticmethod
    async def add_indexes(pool: asyncpg.Pool) -> dict[str, Any]:
        """Add performance-critical indexes to database.

        Args:
            pool: AsyncPG connection pool

        Returns:
            Dictionary with index creation results
        """
        results = {
            "created": [],
            "skipped": [],
            "errors": [],
        }

        for index_sql in QueryOptimizer.PERFORMANCE_INDEXES:
            try:
                await pool.execute(index_sql)
                index_name = index_sql.split("idx_")[1].split(" ")[0] if "idx_" in index_sql else "unknown"
                results["created"].append(index_name)
                logger.info(f"Created index: {index_name}")
            except asyncpg.DuplicateObjectError:
                results["skipped"].append(index_sql)
            except Exception as e:
                results["errors"].append({"sql": index_sql, "error": str(e)})
                logger.error(f"Failed to create index: {e}")

        return results

    @staticmethod
    async def analyze_query_performance(
        pool: asyncpg.Pool,
        query: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze query performance using EXPLAIN.

        Args:
            pool: AsyncPG connection pool
            query: SQL query to analyze
            params: Query parameters

        Returns:
            Query plan and performance metrics
        """
        try:
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
            result = await pool.fetch(explain_query, *(params or []))

            if result:
                plan = json.loads(result[0]["QUERY PLAN"])
                return {
                    "success": True,
                    "plan": plan,
                    "execution_time": plan[0].get("Execution Time", 0),
                    "planning_time": plan[0].get("Planning Time", 0),
                }
        except Exception as e:
            logger.error(f"Failed to analyze query: {e}")

        return {"success": False, "error": str(e)}

    @staticmethod
    def optimize_query_with_prefetch(
        base_query: str,
        relationships: list[str] | None = None,
    ) -> str:
        """Optimize query by adding prefetch hints.

        Args:
            base_query: Base SQL query
            relationships: List of relationships to prefetch

        Returns:
            Optimized query string
        """
        # This is a placeholder for ORM-specific optimization
        # In practice, this would work with SQLAlchemy or similar
        return base_query

    @staticmethod
    async def batch_execute(
        pool: asyncpg.Pool,
        queries: list[tuple[str, list[Any]]],
        batch_size: int = 10,
    ) -> list[Any]:
        """Execute multiple queries in batches.

        Args:
            pool: AsyncPG connection pool
            queries: List of (query, params) tuples
            batch_size: Number of queries per batch

        Returns:
            List of query results
        """
        results = []

        for i in range(0, len(queries), batch_size):
            batch = queries[i : i + batch_size]
            batch_tasks = [
                pool.fetch(query, *params) if params else pool.fetch(query)
                for query, params in batch
            ]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)

        return results

    @staticmethod
    async def detect_n_plus_one(
        pool: asyncpg.Pool,
        query_log: list[dict[str, Any]],
        threshold: int = 5,
    ) -> dict[str, Any]:
        """Detect N+1 query patterns in query logs.

        Args:
            pool: AsyncPG connection pool
            query_log: List of executed queries with timing
            threshold: Minimum number of similar queries to flag

        Returns:
            Dictionary with detected N+1 patterns
        """
        query_patterns = {}

        for log_entry in query_log:
            query = log_entry.get("query", "")
            # Normalize query by removing parameters
            normalized = hashlib.md5(query.encode()).hexdigest()

            if normalized not in query_patterns:
                query_patterns[normalized] = {
                    "count": 0,
                    "total_time": 0,
                    "sample_query": query,
                }

            query_patterns[normalized]["count"] += 1
            query_patterns[normalized]["total_time"] += log_entry.get("duration", 0)

        # Identify N+1 patterns
        n_plus_one_patterns = {
            pattern: info
            for pattern, info in query_patterns.items()
            if info["count"] >= threshold
        }

        return {
            "detected": len(n_plus_one_patterns) > 0,
            "patterns": n_plus_one_patterns,
            "total_queries": len(query_log),
            "unique_patterns": len(query_patterns),
        }


class QueryCache(Generic[T]):
    """Generic query result cache with TTL support."""

    def __init__(self, ttl_seconds: int = 300):
        """Initialize query cache.

        Args:
            ttl_seconds: Time-to-live for cached results
        """
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[T, datetime]] = {}

    def _make_key(self, query: str, params: list[Any] | None = None) -> str:
        """Generate cache key from query and parameters.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Cache key
        """
        key_data = f"{query}:{json.dumps(params or [])}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, query: str, params: list[Any] | None = None) -> T | None:
        """Get cached result if available and not expired.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Cached result or None
        """
        key = self._make_key(query, params)

        if key in self._cache:
            result, timestamp = self._cache[key]
            if datetime.now(UTC) - timestamp < timedelta(seconds=self.ttl_seconds):
                return result
            else:
                del self._cache[key]

        return None

    def set(self, query: str, result: T, params: list[Any] | None = None) -> None:
        """Cache query result.

        Args:
            query: SQL query
            result: Query result to cache
            params: Query parameters
        """
        key = self._make_key(query, params)
        self._cache[key] = (result, datetime.now(UTC))

    def invalidate(self, pattern: str | None = None) -> None:
        """Invalidate cache entries.

        Args:
            pattern: Optional pattern to match keys for selective invalidation
        """
        if pattern is None:
            self._cache.clear()
        else:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        return {
            "size": len(self._cache),
            "ttl_seconds": self.ttl_seconds,
        }


class JoinOptimizer:
    """Optimizes complex JOIN queries."""

    @staticmethod
    def optimize_multi_join(
        base_table: str,
        joins: list[dict[str, str]],
    ) -> str:
        """Generate optimized multi-table JOIN query.

        Args:
            base_table: Base table name
            joins: List of join specifications
                   Each join should have: table, on, type (INNER/LEFT/RIGHT)

        Returns:
            Optimized JOIN query
        """
        query_parts = [f"SELECT * FROM {base_table}"]

        for join in joins:
            join_type = join.get("type", "INNER")
            join_table = join.get("table")
            join_on = join.get("on")

            query_parts.append(f"{join_type} JOIN {join_table} ON {join_on}")

        return " ".join(query_parts)

    @staticmethod
    def suggest_index_for_join(
        join_condition: str,
    ) -> list[str]:
        """Suggest indexes for JOIN optimization.

        Args:
            join_condition: JOIN condition (e.g., "table1.id = table2.table1_id")

        Returns:
            List of suggested index creation statements
        """
        suggestions = []

        # Parse join condition to extract columns
        if "=" in join_condition:
            parts = join_condition.split("=")
            for part in parts:
                part = part.strip()
                if "." in part:
                    table, column = part.split(".")
                    index_name = f"idx_{table}_{column}"
                    suggestions.append(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})")

        return suggestions
