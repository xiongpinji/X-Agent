"""
X-Agent Sync API Integration

Provides REST API endpoints for local-cloud synchronization.
"""

from __future__ import annotations

from typing import Annotated, Optional
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_principal, enforce_scope
from backend.app.core.security import Principal
from backend.local.database import LocalDatabase, DatabaseConfig
from backend.local.config import ConfigManager
from backend.local.sync_client import SyncClient, ConflictResolutionStrategy

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ============================================================================
# MODELS
# ============================================================================


class SyncEnqueueRequest(BaseModel):
    """Request to enqueue a sync operation."""
    entity_type: str = Field(..., description="Type of entity")
    entity_id: str = Field(..., description="Entity ID")
    operation: str = Field(..., description="Operation type: CREATE, UPDATE, DELETE")
    data: dict = Field(default_factory=dict, description="Operation data")
    priority: int = Field(default=0, description="Priority level")


class SyncStatusResponse(BaseModel):
    """Sync operation status."""
    queue_id: str
    entity_type: str
    entity_id: str
    operation: str
    status: str
    created_at: datetime
    updated_at: datetime
    retry_count: int
    error_message: Optional[str] = None


class ConflictResolveRequest(BaseModel):
    """Request to resolve a conflict."""
    resolution_strategy: str = Field(..., description="Resolution strategy")
    resolved_data: dict = Field(..., description="Resolved data")


class ConflictResponse(BaseModel):
    """Conflict information."""
    id: str
    entity_type: str
    entity_id: str
    conflict_type: str
    local_version: int
    cloud_version: int
    local_data: dict
    cloud_data: dict
    resolved_at: Optional[datetime] = None
    resolution_strategy: Optional[str] = None


class SyncStatsResponse(BaseModel):
    """Sync statistics."""
    pending_syncs: int
    failed_syncs: int
    unresolved_conflicts: int
    offline_operations: int
    last_sync_time: Optional[datetime] = None
    database_size_mb: float


class SyncHistoryResponse(BaseModel):
    """Sync history entry."""
    id: str
    sync_batch_id: str
    entity_type: str
    entity_id: str
    operation: str
    direction: str
    status: str
    duration_ms: int
    created_at: datetime


class OfflineModeResponse(BaseModel):
    """Offline mode status."""
    enabled: bool
    pending_operations: int
    last_sync_time: Optional[datetime] = None


# ============================================================================
# DEPENDENCIES
# ============================================================================


def get_local_database() -> LocalDatabase:
    """Get local database instance."""
    config = ConfigManager.get_config()
    db_config = DatabaseConfig(
        db_path=config.db_path,
        timeout=config.db_timeout,
        enable_wal=config.db_enable_wal,
        enable_foreign_keys=config.db_enable_foreign_keys,
    )
    db = LocalDatabase(db_config)
    db.initialize()
    return db


def get_sync_client(db: LocalDatabase = Depends(get_local_database)) -> SyncClient:
    """Get sync client instance."""
    # TODO: Inject cloud API client
    # For now, return a basic instance
    return SyncClient(db, None)


LocalDatabaseDependency = Annotated[LocalDatabase, Depends(get_local_database)]
SyncClientDependency = Annotated[SyncClient, Depends(get_sync_client)]

# ============================================================================
# SYNC OPERATIONS
# ============================================================================


@router.post("/enqueue")
async def enqueue_sync(
    request: SyncEnqueueRequest,
    db: LocalDatabaseDependency,
    principal: PrincipalDependency,
) -> dict:
    """Enqueue a sync operation.

    Args:
        request: Sync operation request
        db: Local database
        principal: Current principal

    Returns:
        Queue entry ID
    """
    enforce_scope(principal, "sync:write")

    try:
        queue_id = db.enqueue_sync(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            operation=request.operation,
            data=request.data,
            priority=request.priority,
        )

        return {
            "queue_id": queue_id,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue sync: {str(e)}")


@router.get("/status/{queue_id}")
async def get_sync_status(
    queue_id: str,
    db: LocalDatabaseDependency,
    principal: PrincipalDependency,
) -> SyncStatusResponse:
    """Get sync operation status.

    Args:
        queue_id: Queue entry ID
        db: Local database
        principal: Current principal

    Returns:
        Sync status
    """
    enforce_scope(principal, "sync:read")

    try:
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, entity_type, entity_id, operation, status,
                   created_at, updated_at, retry_count, error_message
            FROM sync_queue
            WHERE id = ?
        """, (queue_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Sync operation not found")

        return SyncStatusResponse(
            queue_id=row[0],
            entity_type=row[1],
            entity_id=row[2],
            operation=row[3],
            status=row[4],
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
            retry_count=row[7],
            error_message=row[8],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


@router.post("/trigger")
async def trigger_sync(
    db: LocalDatabaseDependency,
    sync_client: SyncClientDependency,
    principal: PrincipalDependency,
) -> dict:
    """Manually trigger synchronization.

    Args:
        db: Local database
        sync_client: Sync client
        principal: Current principal

    Returns:
        Batch ID
    """
    enforce_scope(principal, "sync:admin")

    try:
        # TODO: Implement actual sync trigger
        # batch = await sync_client.sync()

        return {
            "batch_id": "batch_123",
            "status": "started",
            "started_at": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger sync: {str(e)}")


# ============================================================================
# CONFLICT MANAGEMENT
# ============================================================================


@router.get("/conflicts")
async def list_conflicts(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    *,
    db: LocalDatabaseDependency,
    principal: PrincipalDependency,
) -> list[ConflictResponse]:
    """List unresolved conflicts.

    Args:
        entity_type: Filter by entity type
        limit: Maximum number of conflicts
        db: Local database
        principal: Current principal

    Returns:
        List of conflicts
    """
    enforce_scope(principal, "sync:read")

    try:
        conflicts = db.get_unresolved_conflicts(entity_type=entity_type)

        return [
            ConflictResponse(
                id=c["id"],
                entity_type=c["entity_type"],
                entity_id=c["entity_id"],
                conflict_type=c["conflict_type"],
                local_version=c["local_version"],
                cloud_version=c["cloud_version"],
                local_data=c["local_data"],
                cloud_data=c["cloud_data"],
                resolved_at=c.get("resolved_at"),
                resolution_strategy=c.get("resolution_strategy"),
            )
            for c in conflicts[:limit]
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list conflicts: {str(e)}")


@router.get("/conflicts/{conflict_id}")
async def get_conflict(
    conflict_id: str,
    db: LocalDatabaseDependency,
    principal: PrincipalDependency,
) -> ConflictResponse:
    """Get conflict details.

    Args:
        conflict_id: Conflict ID
        db: Local database
        principal: Current principal

    Returns:
        Conflict details
    """
    enforce_scope(principal, "sync:read")

    try:
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, entity_type, entity_id, conflict_type,
                   local_version, cloud_version, local_data, cloud_data,
                   resolved_at, resolution_strategy
            FROM conflict_log
            WHERE id = ?
        """, (conflict_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conflict not found")

        return ConflictResponse(
            id=row[0],
            entity_type=row[1],
            entity_id=row[2],
            conflict_type=row[3],
            local_version=row[4],
            cloud_version=row[5],
            local_data=row[6],
            cloud_data=row[7],
            resolved_at=row[8],
            resolution_strategy=row[9],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conflict: {str(e)}")


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str,
    request: ConflictResolveRequest,
    db: LocalDatabaseDependency,
    principal: PrincipalDependency,
) -> dict:
    """Resolve a conflict.

    Args:
        conflict_id: Conflict ID
        request: Resolution request
        db: Local database
        principal: Current principal

    Returns:
        Resolution result
    """
    enforce_scope(principal, "sync:write")

    try:
        db.resolve_conflict(
            conflict_id=conflict_id,
            resolution_strategy=request.resolution_strategy,
            resolved_data=request.resolved_data,
            resolved_by=principal.user_id,
        )

        return {
            "conflict_id": conflict_id,
            "status": "resolved",
            "resolved_at": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve conflict: {str(e)}")


# ============================================================================
# OFFLINE MODE
# ============================================================================


@router.post("/offline/enable")
async def enable_offline_mode(
    sync_client: SyncClientDependency,
    principal: PrincipalDependency,
) -> OfflineModeResponse:
    """Enable offline mode.

    Args:
        sync_client: Sync client
        principal: Current principal

    Returns:
        Offline mode status
    """
    enforce_scope(principal, "sync:admin")

    try:
        sync_client.set_offline_mode(True)

        return OfflineModeResponse(
            enabled=True,
            pending_operations=0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable offline mode: {str(e)}")


@router.post("/offline/disable")
async def disable_offline_mode(
    sync_client: SyncClientDependency,
    principal: PrincipalDependency,
) -> OfflineModeResponse:
    """Disable offline mode.

    Args:
        sync_client: Sync client
        principal: Current principal

    Returns:
        Offline mode status
    """
    enforce_scope(principal, "sync:admin")

    try:
        sync_client.set_offline_mode(False)

        return OfflineModeResponse(
            enabled=False,
            pending_operations=0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disable offline mode: {str(e)}")


@router.get("/offline/status")
async def get_offline_status(
    db: LocalDatabaseDependency,
    principal: PrincipalDependency,
) -> OfflineModeResponse:
    """Get offline mode status.

    Args:
        db: Local database
        principal: Current principal

    Returns:
        Offline mode status
    """
    enforce_scope(principal, "sync:read")

    try:
        offline_ops = db.get_offline_operations()

        return OfflineModeResponse(
            enabled=len(offline_ops) > 0,
            pending_operations=len(offline_ops),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get offline status: {str(e)}")


# ============================================================================
# MONITORING & STATISTICS
# ============================================================================


@router.get("/stats")
async def get_sync_stats(
    db: LocalDatabaseDependency,
    principal: PrincipalDependency,
) -> SyncStatsResponse:
    """Get sync statistics.

    Args:
        db: Local database
        principal: Current principal

    Returns:
        Sync statistics
    """
    enforce_scope(principal, "sync:read")

    try:
        stats = db.get_sync_stats()
        size_info = db.get_database_size()

        return SyncStatsResponse(
            pending_syncs=stats["pending_syncs"],
            failed_syncs=stats["failed_syncs"],
            unresolved_conflicts=stats["unresolved_conflicts"],
            offline_operations=stats["offline_operations"],
            database_size_mb=size_info["database_size_mb"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync stats: {str(e)}")


@router.get("/history")
async def get_sync_history(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    *,
    db: LocalDatabaseDependency,
    principal: PrincipalDependency,
) -> list[SyncHistoryResponse]:
    """Get sync history.

    Args:
        entity_type: Filter by entity type
        limit: Maximum number of records
        db: Local database
        principal: Current principal

    Returns:
        Sync history
    """
    enforce_scope(principal, "sync:read")

    try:
        history = db.get_sync_history(entity_type=entity_type, limit=limit)

        return [
            SyncHistoryResponse(
                id=h["id"],
                sync_batch_id=h["sync_batch_id"],
                entity_type=h["entity_type"],
                entity_id=h["entity_id"],
                operation=h["operation"],
                direction=h["direction"],
                status=h["status"],
                duration_ms=h["duration_ms"],
                created_at=datetime.fromisoformat(h["created_at"]),
            )
            for h in history
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync history: {str(e)}")


@router.get("/health")
async def get_sync_health(
    db: LocalDatabaseDependency,
    principal: PrincipalDependency,
) -> dict:
    """Get sync system health status.

    Args:
        db: Local database
        principal: Current principal

    Returns:
        Health status
    """
    enforce_scope(principal, "sync:read")

    try:
        stats = db.get_sync_stats()

        # Calculate health score
        health_score = 100

        # Deduct for pending syncs
        if stats["pending_syncs"] > 100:
            health_score -= 10

        # Deduct for failed syncs
        if stats["failed_syncs"] > 10:
            health_score -= 20

        # Deduct for conflicts
        if stats["unresolved_conflicts"] > 5:
            health_score -= 15

        status = "healthy" if health_score >= 80 else "degraded" if health_score >= 50 else "unhealthy"

        return {
            "status": status,
            "health_score": health_score,
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync health: {str(e)}")
