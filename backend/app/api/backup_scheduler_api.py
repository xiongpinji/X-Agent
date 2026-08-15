"""Secured API for real file/database backup scheduling operations."""

from __future__ import annotations

import asyncio
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel

from backend.app.core.backup_scheduler import (
    BackupConfig,
    BackupScheduler,
    get_backup_scheduler,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.settings import get_settings

router = APIRouter(
    prefix="/api/v1/backup/scheduler",
    tags=["backup-scheduler"],
)
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
BackupId = Annotated[str, Path(pattern=r"^\d{8}_\d{6}$")]

_backup_lock = asyncio.Lock()


class BackupRunResponse(BaseModel):
    backup_id: str
    success: bool
    started_at: str
    completed_at: str | None
    total_size_bytes: int
    components: list[dict[str, object]]


class BackupListResponse(BaseModel):
    backups: list[dict[str, object]]
    total: int


class BackupStatusResponse(BaseModel):
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
    backup_id: str
    success: bool
    message: str


class VerifyResponse(BaseModel):
    backup_id: str
    valid: bool
    message: str


class CleanupResponse(BaseModel):
    removed_count: int
    message: str


def _postgres_dsn(database_url: str) -> str:
    return database_url.replace("+asyncpg", "").replace("+psycopg", "")


def _uses_postgres(settings: object) -> bool:
    return any(
        (
            getattr(settings, "memory_backend", "") == "postgres",
            getattr(settings, "trace_backend", "") == "postgres",
            getattr(settings, "admin_store_backend", "") == "postgres",
            getattr(settings, "workflow_store_backend", "") == "db",
        )
    )


def _file_store_dirs(settings: object) -> list[str]:
    configured_paths = (
        "admin_store_path",
        "memory_store_path",
        "trace_store_path",
        "run_store_path",
        "workflow_store_path",
        "workflow_run_store_path",
        "workflow_schedule_store_path",
    )
    directories = ["data"]
    for setting_name in configured_paths:
        path = getattr(settings, setting_name, None)
        if path:
            directories.append(str(FilePath(path).parent))
    return list(dict.fromkeys(directories))


def _get_scheduler() -> BackupScheduler:
    settings = get_settings()
    postgres_enabled = _uses_postgres(settings)
    config = BackupConfig(
        backup_dir=settings.backup_dir,
        schedule_cron=settings.backup_schedule,
        retention_days=settings.backup_retention_days,
        keep_latest=7,
        compress=True,
        pg_enabled=postgres_enabled,
        pg_dsn=_postgres_dsn(settings.database_url) if postgres_enabled else "",
        qdrant_enabled=(
            settings.qdrant_snapshot_enabled
            or settings.memory_backend == "qdrant"
        ),
        qdrant_url=settings.qdrant_url,
        file_store_dirs=_file_store_dirs(settings),
    )
    return get_backup_scheduler(config)


def _check_enabled() -> None:
    if not get_settings().backup_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Backup is disabled. Set XAGENT_BACKUP_ENABLED=true to enable."
            ),
        )


@router.post("/run", response_model=BackupRunResponse)
async def trigger_backup(principal: PrincipalDependency) -> BackupRunResponse:
    enforce_scope(principal, "backup:write")
    _check_enabled()
    if _backup_lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A backup run is already in progress.",
        )

    async with _backup_lock:
        result = await _get_scheduler().run_backup()

    return BackupRunResponse(
        backup_id=result.backup_id,
        success=result.success,
        started_at=result.started_at,
        completed_at=result.completed_at,
        total_size_bytes=result.total_size_bytes,
        components=[
            {
                "component": component.component,
                "success": component.success,
                "files": component.files,
                "size_bytes": component.size_bytes,
                "duration_seconds": round(component.duration_seconds, 3),
                "error": component.error,
            }
            for component in result.components
        ],
    )


@router.get("/list", response_model=BackupListResponse)
async def list_backups(principal: PrincipalDependency) -> BackupListResponse:
    enforce_scope(principal, "backup:read")
    _check_enabled()
    backups = _get_scheduler().list_backups()
    return BackupListResponse(
        backups=[
            {
                "backup_id": backup.backup_id,
                "created_at": backup.created_at,
                "success": backup.success,
                "total_size_bytes": backup.total_size_bytes,
                "components": backup.components,
                "path": backup.path,
            }
            for backup in backups
        ],
        total=len(backups),
    )


@router.get("/status", response_model=BackupStatusResponse)
async def get_status(principal: PrincipalDependency) -> BackupStatusResponse:
    enforce_scope(principal, "backup:read")
    settings = get_settings()
    scheduler_status = _get_scheduler().status
    return BackupStatusResponse(
        enabled=settings.backup_enabled,
        **scheduler_status,
    )


@router.post("/restore/{backup_id}", response_model=RestoreResponse)
async def restore_backup(
    backup_id: BackupId,
    principal: PrincipalDependency,
) -> RestoreResponse:
    enforce_scope(principal, "backup:write")
    _check_enabled()
    success = await _get_scheduler().restore(backup_id)
    return RestoreResponse(
        backup_id=backup_id,
        success=success,
        message="Restore completed successfully" if success else "Restore failed",
    )


@router.post("/verify/{backup_id}", response_model=VerifyResponse)
async def verify_backup(
    backup_id: BackupId,
    principal: PrincipalDependency,
) -> VerifyResponse:
    enforce_scope(principal, "backup:read")
    _check_enabled()
    valid = await _get_scheduler().verify_backup(backup_id)
    return VerifyResponse(
        backup_id=backup_id,
        valid=valid,
        message=(
            "Backup integrity verified"
            if valid
            else "Backup integrity check failed"
        ),
    )


@router.delete("/cleanup", response_model=CleanupResponse)
async def cleanup_backups(
    principal: PrincipalDependency,
    keep: Annotated[int, Query(ge=1, le=365)] = 7,
) -> CleanupResponse:
    enforce_scope(principal, "backup:write")
    _check_enabled()
    removed = _get_scheduler().cleanup_old(keep=keep)
    return CleanupResponse(
        removed_count=removed,
        message=f"Removed {removed} old backup(s)",
    )
