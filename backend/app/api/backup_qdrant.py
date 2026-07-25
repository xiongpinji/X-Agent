"""Qdrant snapshot/backup API endpoints for disaster recovery."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.app.core.qdrant_snapshot import (
    QdrantSnapshotError,
    QdrantSnapshotManager,
    QdrantUnavailableError,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/backup/qdrant", tags=["backup-qdrant"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_snapshot_manager() -> QdrantSnapshotManager:
    """Build a QdrantSnapshotManager from current settings."""
    settings = get_settings()
    return QdrantSnapshotManager(
        qdrant_url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or "",
    )


def _ensure_enabled() -> None:
    """Raise 503 if the snapshot feature is disabled."""
    settings = get_settings()
    if not settings.qdrant_snapshot_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qdrant snapshot feature is disabled. Set XAGENT_QDRANT_SNAPSHOT_ENABLED=true to enable.",
        )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SnapshotRequest(BaseModel):
    """Request to create a snapshot for a specific collection (or all)."""
    collection_name: str | None = None  # None → full backup of all collections


class SnapshotResponse(BaseModel):
    collection: str
    snapshot_name: str
    creation_time: str
    size: int
    checksum: str


class FullBackupResponse(BaseModel):
    timestamp: str
    collections_backed_up: int
    collections_failed: int
    snapshots: list[dict]
    errors: list[dict]


class SnapshotListResponse(BaseModel):
    collection: str
    snapshots: list[dict]
    total: int


class RestoreRequest(BaseModel):
    """Request to restore a collection from a snapshot."""
    collection_name: str
    snapshot_name: str


class RestoreResponse(BaseModel):
    collection_name: str
    snapshot_name: str
    restored: bool
    message: str


class CleanupRequest(BaseModel):
    """Request to clean up old snapshots."""
    keep_latest: int | None = None  # None → use settings default


class CleanupResponse(BaseModel):
    deleted_count: int
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/snapshot")
async def create_snapshot(
    request: SnapshotRequest,
    principal: PrincipalDependency,
) -> SnapshotResponse | FullBackupResponse:
    """Trigger a Qdrant snapshot (single collection or full backup).

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")
    _ensure_enabled()
    manager = _get_snapshot_manager()

    try:
        if request.collection_name:
            info = await manager.create_snapshot(request.collection_name)
            return SnapshotResponse(**info)
        else:
            summary = await manager.create_full_backup()
            return FullBackupResponse(**summary)
    except QdrantUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Qdrant is not available: {exc}",
        ) from exc
    except QdrantSnapshotError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Snapshot failed: {exc}",
        ) from exc


@router.get("/snapshots", response_model=SnapshotListResponse)
async def list_snapshots(
    collection_name: str,
    principal: PrincipalDependency,
) -> SnapshotListResponse:
    """List available snapshots for a collection.

    Requires: backup:read scope
    """
    enforce_scope(principal, "backup:read")
    _ensure_enabled()
    manager = _get_snapshot_manager()

    try:
        snapshots = await manager.list_snapshots(collection_name)
        return SnapshotListResponse(
            collection=collection_name,
            snapshots=snapshots,
            total=len(snapshots),
        )
    except QdrantUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Qdrant is not available: {exc}",
        ) from exc
    except QdrantSnapshotError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list snapshots: {exc}",
        ) from exc


@router.post("/restore", response_model=RestoreResponse)
async def restore_snapshot(
    request: RestoreRequest,
    principal: PrincipalDependency,
) -> RestoreResponse:
    """Restore a collection from a snapshot.

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")
    _ensure_enabled()
    manager = _get_snapshot_manager()

    try:
        restored = await manager.restore_snapshot(request.collection_name, request.snapshot_name)
        return RestoreResponse(
            collection_name=request.collection_name,
            snapshot_name=request.snapshot_name,
            restored=restored,
            message="Collection restored successfully",
        )
    except QdrantUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Qdrant is not available: {exc}",
        ) from exc
    except QdrantSnapshotError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {exc}",
        ) from exc


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_snapshots(
    request: CleanupRequest,
    principal: PrincipalDependency,
) -> CleanupResponse:
    """Clean up old snapshots, keeping N most recent per collection.

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")
    _ensure_enabled()
    manager = _get_snapshot_manager()

    settings = get_settings()
    keep = request.keep_latest if request.keep_latest is not None else settings.qdrant_snapshot_keep

    try:
        deleted = await manager.cleanup_old_snapshots(keep_latest=keep)
        return CleanupResponse(
            deleted_count=deleted,
            message=f"Deleted {deleted} old snapshot(s), keeping {keep} most recent per collection",
        )
    except QdrantUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Qdrant is not available: {exc}",
        ) from exc
    except QdrantSnapshotError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {exc}",
        ) from exc
