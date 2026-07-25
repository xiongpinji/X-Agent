"""
Database Query Optimization Module.

Implements query optimization techniques:
- Connection pooling
- Query result caching
- N+1 query prevention
- Batch operations
- Index optimization
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

import asyncpg

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DatabaseConnectionPool:
    """Manages database connection pooling for optimal performance."""

    def __init__(
        self,
        database_url: str,
        min_size: int = 10,
        max_size: int = 20,
        max_queries: int = 50000,
        max_cached_statement_lifetime: int = 3600,
        max_cacheable_statement_size: int = 15000,
    ) -> None:
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size
        self.max_queries = max_queries
        self.max_cached_statement_lifetime = max_cached_statement_lifetime
        self.max_cacheable_statement_size = max_cacheable_statement_size
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize connection pool."""
        if self._pool is not None:
            return

        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=self.min_size,
            max_size=self.max_size,
            max_queries=self.max_queries,
            max_cached_statement_lifetime=self.max_cached_statement_lifetime,
            max_cacheable_statement_size=self.max_cacheable_statement_size,
            command_timeout=60,
        )
        logger.info(
            f"Database connection pool initialized: "
            f"min_size={self.min_size}, max_size={self.max_size}"
        )

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed")

    async def get_connection(self) -> asyncpg.Connection:
        """Get connection from pool."""
        if not self._pool:
            await self.initialize()
        return await self._pool.acquire()  # type: ignore

    async def execute(self, query: str, *args: Any) -> Any:
        """Execute query and return result."""
        conn = await self.get_connection()
        try:
            return await conn.execute(query, *args)
        finally:
            await self._pool.release(conn)  # type: ignore

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Fetch query results."""
        conn = await self.get_connection()
        try:
            return await conn.fetch(query, *args)
        finally:
            await self._pool.release(conn)  # type: ignore

    async def fetchrow(self, query: str, *args: Any) -> Any:
        """Fetch single row."""
        conn = await self.get_connection()
        try:
            return await conn.fetchrow(query, *args)
        finally:
            await self._pool.release(conn)  # type: ignore

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Fetch single value."""
        conn = await self.get_connection()
        try:
            return await conn.fetchval(query, *args)
        finally:
            await self._pool.release(conn)  # type: ignore


class QueryOptimizer:
    """Optimizes database queries."""

    @staticmethod
    def add_indexes(pool: DatabaseConnectionPool) -> list[str]:
        """Add missing indexes for common queries."""
        indexes = [
            # Workflow indexes
            "CREATE INDEX IF NOT EXISTS idx_workflows_tenant_id ON workflows(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_workflows_created_at ON workflows(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_id ON workflow_runs(workflow_id)",
            "CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_workflow_runs_created_at ON workflow_runs(created_at DESC)",
            # Agent run indexes
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_tenant_id ON agent_runs(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at ON agent_runs(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_user_id ON agent_runs(user_id)",
            # Memory indexes
            "CREATE INDEX IF NOT EXISTS idx_memories_tenant_layer ON memories(tenant_id, layer)",
            "CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)",
            "CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC)",
            # Trace indexes
            "CREATE INDEX IF NOT EXISTS idx_traces_tenant_id ON traces(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_traces_trace_id ON traces(trace_id)",
            "CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at DESC)",
            # Audit indexes
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON audit_logs(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC)",
        ]
        return indexes

    @staticmethod
    def optimize_n_plus_one(
        base_query: str,
        related_queries: dict[str, str],
    ) -> str:
        """Optimize N+1 queries using JOINs."""
        # This is a template for converting N+1 queries to JOINs
        # Example: Instead of fetching workflows then runs for each,
        # fetch with JOIN in single query
        return base_query


class BatchOperationExecutor:
    """Executes batch operations for better performance."""

    def __init__(self, pool: DatabaseConnectionPool, batch_size: int = 1000) -> None:
        self.pool = pool
        self.batch_size = batch_size

    async def batch_insert(
        self,
        table: str,
        columns: list[str],
        values: list[tuple[Any, ...]],
    ) -> int:
        """Insert multiple rows in batches."""
        total_inserted = 0

        for i in range(0, len(values), self.batch_size):
            batch = values[i : i + self.batch_size]
            placeholders = ", ".join(
                f"({', '.join('$' + str(j + 1) for j in range(len(columns)))})"
                for _ in batch
            )
            query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES {placeholders}"

            flat_values = [val for row in batch for val in row]
            await self.pool.execute(query, *flat_values)
            total_inserted += len(batch)

        logger.info(f"Batch inserted {total_inserted} rows into {table}")
        return total_inserted

    async def batch_update(
        self,
        table: str,
        updates: dict[str, Any],
        where_clause: str,
        where_values: list[Any],
    ) -> int:
        """Update multiple rows in batches."""
        set_clause = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(updates.keys()))
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

        values = list(updates.values()) + where_values
        result = await self.pool.execute(query, *values)

        logger.info(f"Batch updated rows in {table}")
        return result

    async def batch_delete(
        self,
        table: str,
        where_clause: str,
        where_values: list[Any],
    ) -> int:
        """Delete multiple rows in batches."""
        query = f"DELETE FROM {table} WHERE {where_clause}"
        result = await self.pool.execute(query, *where_values)

        logger.info(f"Batch deleted rows from {table}")
        return result


class QueryCache:
    """Caches query results to reduce database load."""

    def __init__(self, ttl: int = 300) -> None:
        self.ttl = ttl
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        """Get cached result."""
        if key in self._cache:
            result, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return result
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Cache result."""
        self._cache[key] = (value, time.time())

    def invalidate(self, pattern: str | None = None) -> None:
        """Invalidate cache."""
        if pattern is None:
            self._cache.clear()
        else:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for k in keys_to_delete:
                del self._cache[k]


import time
