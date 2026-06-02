"""Optimized database query layer for API endpoints.

Replaces inefficient query patterns with batch loading and caching.
"""

from __future__ import annotations

from typing import Any, Optional
from backend.app.core.query_cache import cached_query, get_query_cache, CacheConfig, init_query_cache
from backend.app.core.query_optimizer import get_query_optimizer, track_query


class OptimizedRunStore:
    """Optimized run store with batch loading and caching."""

    def __init__(self, base_store: Any):
        self.base_store = base_store
        self._cache = get_query_cache()

    @cached_query("runs:list", ttl_seconds=60, key_kwargs=["tenant_id", "limit"])
    async def list_runs_by_tenant(
        self,
        tenant_id: str,
        limit: int = 20,
        status: str | None = None,
        user_id: str | None = None,
    ) -> list[Any]:
        """List runs with efficient filtering.

        BEFORE: N+1 queries - fetch all runs, then filter in Python
        AFTER: Single query with WHERE clause
        """
        # Build query with all filters at database level
        query = "SELECT * FROM runs WHERE tenant_id = $1"
        params = [tenant_id]

        if status:
            query += " AND status = $2"
            params.append(status)

        if user_id:
            query += f" AND user_id = ${len(params) + 1}"
            params.append(user_id)

        query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)

        # Execute single query instead of fetching all then filtering
        return await self.base_store.fetch(query, *params)

    @cached_query("runs:by_workflow", ttl_seconds=120, key_kwargs=["workflow_id"])
    async def list_runs_by_workflow(
        self,
        workflow_id: str,
        limit: int = 100,
    ) -> list[Any]:
        """List runs for a workflow.

        BEFORE: N+1 - fetch workflow, then fetch all runs
        AFTER: Single indexed query
        """
        query = """
            SELECT * FROM runs
            WHERE workflow_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        return await self.base_store.fetch(query, workflow_id, limit)

    @cached_query("runs:latest_by_workflow", ttl_seconds=300, key_kwargs=["workflow_id"])
    async def get_latest_run_for_workflow(self, workflow_id: str) -> Any | None:
        """Get latest run for workflow.

        BEFORE: N+1 - loop through workflows, fetch latest run each time
        AFTER: Single indexed query per workflow
        """
        query = """
            SELECT * FROM runs
            WHERE workflow_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """
        return await self.base_store.fetchrow(query, workflow_id)

    async def batch_get_latest_runs(
        self, workflow_ids: list[str]
    ) -> dict[str, Any]:
        """Get latest run for multiple workflows in one query.

        BEFORE: N queries (one per workflow)
        AFTER: Single query with window function
        """
        if not workflow_ids:
            return {}

        placeholders = ",".join(f"${i+1}" for i in range(len(workflow_ids)))
        query = f"""
            SELECT DISTINCT ON (workflow_id)
                workflow_id, *
            FROM runs
            WHERE workflow_id IN ({placeholders})
            ORDER BY workflow_id, created_at DESC
        """
        rows = await self.base_store.fetch(query, *workflow_ids)
        return {row["workflow_id"]: row for row in rows}

    async def count_runs_by_workflow(
        self, workflow_ids: list[str]
    ) -> dict[str, int]:
        """Count runs for multiple workflows in one query.

        BEFORE: N queries (one COUNT per workflow)
        AFTER: Single GROUP BY query
        """
        if not workflow_ids:
            return {}

        placeholders = ",".join(f"${i+1}" for i in range(len(workflow_ids)))
        query = f"""
            SELECT workflow_id, COUNT(*) as count
            FROM runs
            WHERE workflow_id IN ({placeholders})
            GROUP BY workflow_id
        """
        rows = await self.base_store.fetch(query, *workflow_ids)
        return {row["workflow_id"]: row["count"] for row in rows}


class OptimizedMemoryStore:
    """Optimized memory store with efficient search and caching."""

    def __init__(self, base_store: Any):
        self.base_store = base_store
        self._cache = get_query_cache()

    @cached_query("memories:search", ttl_seconds=300, key_kwargs=["tenant_id", "layer"])
    async def search_memories(
        self,
        tenant_id: str,
        query: str = "",
        layers: list[int] | None = None,
        top_k: int = 5,
    ) -> list[Any]:
        """Search memories with efficient indexing.

        BEFORE: Full table scan with ILIKE
        AFTER: Uses composite index (tenant_id, layer, importance, created_at)
        """
        layers = layers or [1, 2, 3, 4]

        if query:
            # Use full-text search index
            sql = """
                SELECT * FROM memories
                WHERE tenant_id = $1
                  AND layer = ANY($2::int[])
                  AND (
                    to_tsvector('english', content) @@ plainto_tsquery('english', $3)
                    OR tags @> ARRAY[$3]
                  )
                ORDER BY importance DESC, created_at DESC
                LIMIT $4
            """
            return await self.base_store.fetch(sql, tenant_id, layers, query, top_k)
        else:
            # Use composite index for recent memories
            sql = """
                SELECT * FROM memories
                WHERE tenant_id = $1
                  AND layer = ANY($2::int[])
                ORDER BY importance DESC, created_at DESC
                LIMIT $3
            """
            return await self.base_store.fetch(sql, tenant_id, layers, top_k)

    @cached_query("memories:by_agent", ttl_seconds=300, key_kwargs=["tenant_id", "agent_id"])
    async def get_agent_memories(
        self,
        tenant_id: str,
        agent_id: str,
        layers: list[int] | None = None,
    ) -> list[Any]:
        """Get memories for specific agent.

        Uses index: idx_memories_tenant_agent_created
        """
        layers = layers or [1, 2, 3, 4]
        sql = """
            SELECT * FROM memories
            WHERE tenant_id = $1
              AND agent_id = $2
              AND layer = ANY($3::int[])
            ORDER BY created_at DESC
        """
        return await self.base_store.fetch(sql, tenant_id, agent_id, layers)

    async def batch_get_agent_memories(
        self,
        tenant_id: str,
        agent_ids: list[str],
        layers: list[int] | None = None,
    ) -> dict[str, list[Any]]:
        """Get memories for multiple agents in one query.

        BEFORE: N queries (one per agent)
        AFTER: Single query with GROUP BY
        """
        if not agent_ids:
            return {}

        layers = layers or [1, 2, 3, 4]
        placeholders = ",".join(f"${i+2}" for i in range(len(agent_ids)))

        sql = f"""
            SELECT * FROM memories
            WHERE tenant_id = $1
              AND agent_id IN ({placeholders})
              AND layer = ANY(${{len(agent_ids) + 2}}::int[])
            ORDER BY agent_id, created_at DESC
        """

        rows = await self.base_store.fetch(
            sql, tenant_id, *agent_ids, layers
        )

        result: dict[str, list[Any]] = {aid: [] for aid in agent_ids}
        for row in rows:
            result[row["agent_id"]].append(row)
        return result

    async def get_high_importance_memories(
        self,
        tenant_id: str,
        importance_threshold: float = 0.7,
        limit: int = 100,
    ) -> list[Any]:
        """Get high-importance memories using partial index.

        Uses index: idx_memories_high_importance
        Much faster than filtering all memories
        """
        sql = """
            SELECT * FROM memories
            WHERE tenant_id = $1
              AND importance >= $2
            ORDER BY created_at DESC
            LIMIT $3
        """
        return await self.base_store.fetch(sql, tenant_id, importance_threshold, limit)


class OptimizedWorkflowStore:
    """Optimized workflow store with batch operations."""

    def __init__(self, base_store: Any):
        self.base_store = base_store
        self._cache = get_query_cache()

    @cached_query("workflows:list", ttl_seconds=300, key_kwargs=["tenant_id"])
    async def list_workflows(self, tenant_id: str) -> list[Any]:
        """List workflows for tenant.

        Uses index: idx_workflows_tenant_status_created
        """
        sql = """
            SELECT * FROM workflows
            WHERE tenant_id = $1
            ORDER BY created_at DESC
        """
        return await self.base_store.fetch(sql, tenant_id)

    async def batch_get_workflow_stats(
        self, workflow_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Get stats for multiple workflows in one query.

        BEFORE: N queries (one per workflow)
        AFTER: Single query with aggregation
        """
        if not workflow_ids:
            return {}

        placeholders = ",".join(f"${i+1}" for i in range(len(workflow_ids)))
        sql = f"""
            SELECT
                workflow_id,
                COUNT(*) as run_count,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
                MAX(created_at) as last_run_at
            FROM runs
            WHERE workflow_id IN ({placeholders})
            GROUP BY workflow_id
        """
        rows = await self.base_store.fetch(sql, *workflow_ids)
        return {row["workflow_id"]: dict(row) for row in rows}


class OptimizedAuditStore:
    """Optimized audit log store."""

    def __init__(self, base_store: Any):
        self.base_store = base_store
        self._cache = get_query_cache()

    @cached_query("audit:list", ttl_seconds=600, key_kwargs=["tenant_id"])
    async def list_audit_logs(
        self,
        tenant_id: str,
        action: str | None = None,
        limit: int = 100,
    ) -> list[Any]:
        """List audit logs with efficient filtering.

        Uses index: idx_audit_logs_tenant_action_created
        """
        sql = "SELECT * FROM audit_logs WHERE tenant_id = $1"
        params = [tenant_id]

        if action:
            sql += " AND action = $2"
            params.append(action)

        sql += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)

        return await self.base_store.fetch(sql, *params)


def init_optimized_stores(base_stores: dict[str, Any]) -> dict[str, Any]:
    """Initialize optimized store wrappers."""
    return {
        "runs": OptimizedRunStore(base_stores.get("runs")),
        "memories": OptimizedMemoryStore(base_stores.get("memories")),
        "workflows": OptimizedWorkflowStore(base_stores.get("workflows")),
        "audit": OptimizedAuditStore(base_stores.get("audit")),
    }
