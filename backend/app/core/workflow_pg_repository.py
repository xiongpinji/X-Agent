"""PostgreSQL-backed workflow storage with ACID guarantees (Phase 2.3)."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowPostgresRepository:
    """PostgreSQL-backed workflow storage replacing JSON file storage.

    Provides ACID guarantees for workflow definitions and runs.
    Requires asyncpg connection pool.
    """

    def __init__(self, pool) -> None:
        self._pool = pool

    async def save_definition(self, workflow_id: str, name: str, description: str,
                              definition: dict[str, Any], tenant_id: str = "default") -> None:
        """Save or update a workflow definition."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO workflow_definitions (id, tenant_id, name, description, definition, version, status, updated_at)
                VALUES ($1, $2, $3, $4, $5::jsonb, 1, 'active', NOW())
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    definition = EXCLUDED.definition,
                    version = workflow_definitions.version + 1,
                    updated_at = NOW()
                """,
                workflow_id, tenant_id, name, description, json.dumps(definition),
            )

    async def load_definition(self, workflow_id: str) -> dict[str, Any] | None:
        """Load a workflow definition by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_definitions WHERE id = $1", workflow_id
            )
        if not row:
            return None
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "name": row["name"],
            "description": row["description"],
            "definition": json.loads(row["definition"]) if row["definition"] else {},
            "version": row["version"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    async def list_definitions(self, tenant_id: str, status: str = "active",
                               limit: int = 50) -> list[dict[str, Any]]:
        """List workflow definitions for a tenant."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM workflow_definitions WHERE tenant_id = $1 AND status = $2 ORDER BY updated_at DESC LIMIT $3",
                tenant_id, status, limit,
            )
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "version": r["version"],
                "status": r["status"],
                "updated_at": r["updated_at"].isoformat(),
            }
            for r in rows
        ]

    async def save_run(self, run_id: str, workflow_id: str, tenant_id: str,
                       status: str = "pending", snapshot: dict[str, Any] | None = None) -> None:
        """Create or update a workflow run."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO workflow_runs (id, workflow_id, tenant_id, status, snapshot, created_at)
                VALUES ($1, $2, $3, $4, $5::jsonb, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    snapshot = EXCLUDED.snapshot
                """,
                run_id, workflow_id, tenant_id, status,
                json.dumps(snapshot or {}),
            )

    async def update_run_status(self, run_id: str, status: str,
                                result: dict[str, Any] | None = None,
                                error: str | None = None) -> None:
        """Update run status and optionally set result/error."""
        completed_at = "NOW()" if status in ("completed", "failed", "cancelled") else "NULL"
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE workflow_runs
                SET status = $2,
                    result = $3::jsonb,
                    error = $4,
                    completed_at = {completed_at}
                WHERE id = $1
                """,
                run_id, status,
                json.dumps(result) if result else None,
                error,
            )

    async def list_runs(self, workflow_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """List runs for a workflow."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM workflow_runs WHERE workflow_id = $1 ORDER BY created_at DESC LIMIT $2",
                workflow_id, limit,
            )
        return [
            {
                "id": r["id"],
                "workflow_id": r["workflow_id"],
                "status": r["status"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                "error": r["error"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get a single run by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_runs WHERE id = $1", run_id
            )
        if not row:
            return None
        return {
            "id": row["id"],
            "workflow_id": row["workflow_id"],
            "tenant_id": row["tenant_id"],
            "status": row["status"],
            "snapshot": json.loads(row["snapshot"]) if row["snapshot"] else {},
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"],
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "created_at": row["created_at"].isoformat(),
        }

    async def delete_definition(self, workflow_id: str) -> bool:
        """Soft-delete a workflow definition."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE workflow_definitions SET status = 'deleted', updated_at = NOW() WHERE id = $1",
                workflow_id,
            )
        return result == "UPDATE 1"
