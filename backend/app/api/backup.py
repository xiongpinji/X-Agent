"""Backup and recovery API endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.app.core.backup_manager import BackupManager, BackupScheduler
from backend.app.core.backup_storage import create_backup_storage
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.models.backup import (
    BackupStorageType,
    BackupType,
)

router = APIRouter(prefix="/api/v1/backup", tags=["backup"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Global backup manager instance
_backup_manager: BackupManager | None = None
_backup_scheduler: BackupScheduler | None = None


def get_backup_manager() -> BackupManager:
    """Get or create backup manager."""
    global _backup_manager
    if _backup_manager is None:
        storage = create_backup_storage(BackupStorageType.LOCAL)
        _backup_manager = BackupManager(storage)
    return _backup_manager


def get_backup_scheduler() -> BackupScheduler:
    """Get or create backup scheduler."""
    global _backup_scheduler
    if _backup_scheduler is None:
        backup_manager = get_backup_manager()
        _backup_scheduler = BackupScheduler(backup_manager)
    return _backup_scheduler


# Request/Response Models
class CreateBackupRequest(BaseModel):
    """Request to create a backup."""
    backup_type: BackupType = BackupType.FULL
    description: str | None = None
    tags: dict[str, str] | None = None


class CreateBackupResponse(BaseModel):
    """Response for backup creation."""
    backup_id: str
    tenant_id: str
    status: str
    created_at: datetime
    message: str


class BackupListResponse(BaseModel):
    """Response for backup list."""
    backups: list[dict]
    total: int
    limit: int
    offset: int


class RestoreBackupRequest(BaseModel):
    """Request to restore from a backup."""
    backup_id: str
    target_tables: list[str] | None = None


class RestoreBackupResponse(BaseModel):
    """Response for backup restore."""
    restore_id: str
    backup_id: str
    status: str
    started_at: datetime
    message: str


class VerifyBackupRequest(BaseModel):
    """Request to verify a backup."""
    backup_id: str


class VerifyBackupResponse(BaseModel):
    """Response for backup verification."""
    backup_id: str
    verified: bool
    message: str


class CreateScheduleRequest(BaseModel):
    """Request to create a backup schedule."""
    name: str
    backup_type: BackupType = BackupType.FULL
    frequency: str = "daily"  # hourly, daily, weekly, monthly
    scheduled_time: str = "02:00"
    retention_days: int = 30
    storage_type: BackupStorageType = BackupStorageType.LOCAL
    notify_on_success: bool = True
    notify_on_failure: bool = True


class CreateScheduleResponse(BaseModel):
    """Response for schedule creation."""
    schedule_id: str
    name: str
    frequency: str
    status: str
    message: str


class BackupStatusResponse(BaseModel):
    """Response for backup status."""
    backup_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    total_size: int
    compressed_size: int
    compression_ratio: float
    checksum: str


# API Endpoints

@router.post("/create", response_model=CreateBackupResponse)
async def create_backup(
    request: CreateBackupRequest,
    principal: PrincipalDependency,
) -> CreateBackupResponse:
    """Create a new backup.

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")

    try:
        backup_manager = get_backup_manager()

        # NOTE: Requires database persistence layer for real backup data
        # For now, using placeholder data
        data = b"placeholder backup data"

        metadata = await backup_manager.create_backup(
            tenant_id=principal.tenant_id,
            data=data,
            backup_type=request.backup_type,
            description=request.description or "",
            tags=request.tags,
        )

        if metadata:
            return CreateBackupResponse(
                backup_id=metadata.backup_id,
                tenant_id=metadata.tenant_id,
                status=metadata.status.value,
                created_at=metadata.created_at,
                message="Backup created successfully",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create backup",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating backup: {e!s}",
        )


@router.get("/list", response_model=BackupListResponse)
async def list_backups(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    *,
    principal: PrincipalDependency,
) -> BackupListResponse:
    """List backups for the current tenant.

    Requires: backup:read scope
    """
    enforce_scope(principal, "backup:read")

    try:
        backup_manager = get_backup_manager()
        backups = await backup_manager.list_backups(
            tenant_id=principal.tenant_id,
            limit=limit,
            offset=offset,
        )

        return BackupListResponse(
            backups=backups,
            total=len(backups),
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing backups: {e!s}",
        )


@router.post("/restore", response_model=RestoreBackupResponse)
async def restore_backup(
    request: RestoreBackupRequest,
    principal: PrincipalDependency,
) -> RestoreBackupResponse:
    """Restore from a backup.

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")

    try:
        backup_manager = get_backup_manager()
        restore_point = await backup_manager.restore_backup(
            backup_id=request.backup_id,
            tenant_id=principal.tenant_id,
        )

        if restore_point:
            return RestoreBackupResponse(
                restore_id=restore_point.restore_id,
                backup_id=restore_point.backup_id,
                status=restore_point.status.value,
                started_at=restore_point.started_at or datetime.utcnow(),
                message="Restore started successfully",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to restore backup",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error restoring backup: {e!s}",
        )


@router.post("/verify", response_model=VerifyBackupResponse)
async def verify_backup(
    request: VerifyBackupRequest,
    principal: PrincipalDependency,
) -> VerifyBackupResponse:
    """Verify backup integrity.

    Requires: backup:read scope
    """
    enforce_scope(principal, "backup:read")

    try:
        backup_manager = get_backup_manager()
        verified = await backup_manager.verify_backup(request.backup_id)

        return VerifyBackupResponse(
            backup_id=request.backup_id,
            verified=verified,
            message="Backup verification completed",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying backup: {e!s}",
        )


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Delete a backup.

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")

    try:
        backup_manager = get_backup_manager()
        success = await backup_manager.delete_backup(
            backup_id=backup_id,
            tenant_id=principal.tenant_id,
        )

        if success:
            return {"message": "Backup deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup not found",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting backup: {e!s}",
        )


@router.get("/{backup_id}/status", response_model=BackupStatusResponse)
async def get_backup_status(
    backup_id: str,
    principal: PrincipalDependency,
) -> BackupStatusResponse:
    """Get backup status.

    Requires: backup:read scope
    """
    enforce_scope(principal, "backup:read")

    try:
        backup_manager = get_backup_manager()
        metadata = await backup_manager.storage.get_backup_metadata(backup_id)

        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup not found",
            )

        # Convert metadata to response
        if isinstance(metadata, dict):
            return BackupStatusResponse(
                backup_id=metadata.get("backup_id", ""),
                status=metadata.get("status", "unknown"),
                created_at=datetime.fromisoformat(metadata.get("created_at", "")),
                completed_at=datetime.fromisoformat(metadata.get("completed_at", "")) if metadata.get("completed_at") else None,
                total_size=metadata.get("total_size", 0),
                compressed_size=metadata.get("compressed_size", 0),
                compression_ratio=metadata.get("compression_ratio", 0.0),
                checksum=metadata.get("checksum", ""),
            )
        else:
            return BackupStatusResponse(
                backup_id=metadata.backup_id,
                status=metadata.status.value,
                created_at=metadata.created_at,
                completed_at=metadata.completed_at,
                total_size=metadata.total_size,
                compressed_size=metadata.compressed_size,
                compression_ratio=metadata.compression_ratio,
                checksum=metadata.checksum,
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting backup status: {e!s}",
        )


# Schedule endpoints

@router.post("/schedule/create", response_model=CreateScheduleResponse)
async def create_backup_schedule(
    request: CreateScheduleRequest,
    principal: PrincipalDependency,
) -> CreateScheduleResponse:
    """Create a backup schedule.

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")

    try:
        scheduler = get_backup_scheduler()
        schedule = await scheduler.create_schedule(
            tenant_id=principal.tenant_id,
            name=request.name,
            backup_type=request.backup_type,
            frequency=request.frequency,
            scheduled_time=request.scheduled_time,
            retention_days=request.retention_days,
            storage_type=request.storage_type,
        )

        return CreateScheduleResponse(
            schedule_id=schedule.schedule_id,
            name=schedule.name,
            frequency=schedule.frequency,
            status="created",
            message="Backup schedule created successfully",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating backup schedule: {e!s}",
        )


@router.get("/schedule/list")
async def list_backup_schedules(
    principal: PrincipalDependency,
) -> dict:
    """List backup schedules for the current tenant.

    Requires: backup:read scope
    """
    enforce_scope(principal, "backup:read")

    try:
        scheduler = get_backup_scheduler()
        schedules = await scheduler.list_schedules(principal.tenant_id)

        return {
            "schedules": [
                {
                    "schedule_id": s.schedule_id,
                    "name": s.name,
                    "frequency": s.frequency,
                    "enabled": s.enabled,
                    "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
                }
                for s in schedules
            ],
            "total": len(schedules),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing backup schedules: {e!s}",
        )


@router.delete("/schedule/{schedule_id}")
async def delete_backup_schedule(
    schedule_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Delete a backup schedule.

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")

    try:
        scheduler = get_backup_scheduler()
        success = await scheduler.delete_schedule(schedule_id)

        if success:
            return {"message": "Backup schedule deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup schedule not found",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting backup schedule: {e!s}",
        )
