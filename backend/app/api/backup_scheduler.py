"""Automated Backup Scheduler API endpoints.

Endpoints:
    POST /api/v1/backup/run              — trigger manual backup
    GET  /api/v1/backup/list             — list backups
    GET  /api/v1/backup/status           — scheduler status
    POST /api/v1/backup/restore/{id}     — restore from backup
    POST /api/v1/backup/verify/{id}      — verify backup integrity
    DELETE /api/v1/backup/cleanup        — cleanup old backups
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.core.backup_scheduler import (
    BackupConfig,
    BackupScheduler,
    get_backup_scheduler,
)
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/backup", tags=["backup-scheduler"])


# ─── Response Models ────────────────────────────────────────────────────────────


class BackupRunResponse(BaseModel):
    """Response for manual backup trigger."""

    backup_id: str
    success: bool
    started_at: str
    completed_at: str | None
    total_size_bytes: int
    components: list[dict]


class BackupListResponse(BaseModel):
    """Response for backup list."""

    backups: list[dict]
    total: int


class BackupStatusResponse(BaseModel):
    """Response for scheduler status."""

    enabled: bool
    running: bool
    schedule_cron: str
    backup_dir: str
    last_run: str | None
    last_success: bool | None
    last_backup_id: str | None
    retention_days: int
    keep_latest: int


class RestoreResponse(BaseModel):
    """Response for restore operation."""

    backup_id: str
    success: bool
    message: str


class VerifyResponse(BaseModel):
    """Response for verify operation."""

    backup_id: str
    valid: bool
    message: str


class CleanupResponse(BaseModel):
    """Response for cleanup operation."""

    removed_count: int
    message: str


# ─── Helpers ────────────────────────────────────────────────────────────────────


def _get_scheduler() -> BackupScheduler:
    """Get scheduler configured from app settings."""
    settings = get_settings()
    config = BackupConfig(
        backup_dir=settings.backup_dir,
        schedule_cron=settings.backup_schedule,
        retention_days=settings.backup_retention_days,
        keep_latest=7,
        compress=True,
        pg_enabled=True,
        pg_dsn=settings.database_url if settings.database_url else "",
        qdrant_enabled=settings.qdrant_snapshot_enabled,
        qdrant_url=settings.qdrant_url,
    )
    return get_backup_scheduler(config)


def _check_enabled() -> None:
    """Raise 403 if backup is not enabled."""
    settings = get_settings()
    if not settings.backup_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Backup is disabled. Set XAGENT_BACKUP_ENABLED=true to enable.",
        )


# ─── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/run", response_model=BackupRunResponse)
async def trigger_backup() -> BackupRunResponse:
    """Trigger a manual backup of all data stores."""
    _check_enabled()
    scheduler = _get_scheduler()

    result = await scheduler.run_backup()

    return BackupRunResponse(
        backup_id=result.backup_id,
        success=result.success,
        started_at=result.started_at,
        completed_at=result.completed_at,
        total_size_bytes=result.total_size_bytes,
        components=[
            {
                "component": c.component,
                "success": c.success,
                "files": c.files,
                "size_bytes": c.size_bytes,
                "duration_seconds": round(c.duration_seconds, 3),
                "error": c.error,
            }
            for c in result.components
        ],
    )


@router.get("/list", response_model=BackupListResponse)
async def list_backups() -> BackupListResponse:
    """List all available backups."""
    _check_enabled()
    scheduler = _get_scheduler()

    backups = scheduler.list_backups()
    return BackupListResponse(
        backups=[
            {
                "backup_id": b.backup_id,
                "created_at": b.created_at,
                "success": b.success,
                "total_size_bytes": b.total_size_bytes,
                "components": b.components,
                "path": b.path,
            }
            for b in backups
        ],
        total=len(backups),
    )


@router.get("/status", response_model=BackupStatusResponse)
async def get_status() -> BackupStatusResponse:
    """Get backup scheduler status."""
    settings = get_settings()
    scheduler = _get_scheduler()
    st = scheduler.status

    return BackupStatusResponse(
        enabled=settings.backup_enabled,
        running=st["running"],
        schedule_cron=st["schedule_cron"],
        backup_dir=st["backup_dir"],
        last_run=st["last_run"],
        last_success=st["last_success"],
        last_backup_id=st["last_backup_id"],
        retention_days=st["retention_days"],
        keep_latest=st["keep_latest"],
    )


@router.post("/restore/{backup_id}", response_model=RestoreResponse)
async def restore_backup(backup_id: str) -> RestoreResponse:
    """Restore from a specific backup."""
    _check_enabled()
    scheduler = _get_scheduler()

    success = await scheduler.restore(backup_id)
    return RestoreResponse(
        backup_id=backup_id,
        success=success,
        message="Restore completed successfully" if success else "Restore failed",
    )


@router.post("/verify/{backup_id}", response_model=VerifyResponse)
async def verify_backup(backup_id: str) -> VerifyResponse:
    """Verify backup integrity."""
    _check_enabled()
    scheduler = _get_scheduler()

    valid = await scheduler.verify_backup(backup_id)
    return VerifyResponse(
        backup_id=backup_id,
        valid=valid,
        message="Backup integrity verified" if valid else "Backup integrity check failed",
    )


@router.delete("/cleanup", response_model=CleanupResponse)
async def cleanup_backups(keep: int = 7) -> CleanupResponse:
    """Remove old backups, keeping N most recent."""
    _check_enabled()
    scheduler = _get_scheduler()

    removed = scheduler.cleanup_old(keep=keep)
    return CleanupResponse(
        removed_count=removed,
        message=f"Removed {removed} old backup(s)",
    )
