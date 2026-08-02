"""Backup monitoring and health check API endpoints."""

import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.app.core.backup_monitoring import (
    AlertThreshold,
    BackupHealthCheck,
    BackupMetricsCollector,
    BackupMonitor,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backup/monitoring", tags=["backup-monitoring"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Configuration
DEFAULT_BACKUP_STORAGE_PATH = "/data/backups"
ALLOWED_BACKUP_PATHS = ["/data/backups", "/var/backups"]  # Whitelist of allowed paths


def validate_storage_path(path: str) -> Path:
    """Validate and sanitize storage path to prevent path traversal attacks.

    Args:
        path: The storage path to validate

    Returns:
        Validated Path object

    Raises:
        HTTPException: If path is invalid or not in whitelist
    """
    try:
        # Resolve to absolute path and check for path traversal
        resolved_path = Path(path).resolve()

        # Check if path is in whitelist
        is_allowed = any(
            str(resolved_path).startswith(str(Path(allowed).resolve()))
            for allowed in ALLOWED_BACKUP_PATHS
        )

        if not is_allowed:
            logger.warning(f"Attempted access to non-whitelisted path: {path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this storage path is not allowed",
            )

        return resolved_path
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Invalid storage path: {path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid storage path",
        ) from e


@lru_cache(maxsize=1)
def get_monitor() -> BackupMonitor:
    """Get or create backup monitor (thread-safe singleton via lru_cache)."""
    return BackupMonitor(thresholds=AlertThreshold())


@lru_cache(maxsize=1)
def get_health_check() -> BackupHealthCheck:
    """Get or create health check (thread-safe singleton via lru_cache)."""
    monitor = get_monitor()
    return BackupHealthCheck(monitor)


@lru_cache(maxsize=1)
def get_metrics_collector() -> BackupMetricsCollector:
    """Get or create metrics collector (thread-safe singleton via lru_cache)."""
    return BackupMetricsCollector()


# Request/Response Models
class AlertResponse(BaseModel):
    """Response for alert."""
    alert_id: str
    tenant_id: str
    backup_id: str | None
    alert_type: str
    severity: str
    title: str
    message: str
    created_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None


class AlertListResponse(BaseModel):
    """Response for alert list."""
    alerts: list[AlertResponse]
    total: int
    limit: int
    offset: int


class HealthCheckResponse(BaseModel):
    """Response for health check."""
    healthy: bool
    backup_success_rate: float
    restore_success_rate: float
    verification_status: dict
    storage_health: dict
    timestamp: str


class StatisticsResponse(BaseModel):
    """Response for statistics."""
    tenant_id: str
    period_start: datetime
    period_end: datetime
    total_backups: int
    successful_backups: int
    failed_backups: int
    success_rate: float
    total_backup_size: int
    total_compressed_size: int
    average_compression_ratio: float
    average_backup_duration: float
    average_throughput: float
    total_restores: int
    successful_restores: int
    failed_restores: int
    average_restore_duration: float
    total_verifications: int
    successful_verifications: int
    failed_verifications: int
    total_alerts: int
    critical_alerts: int
    unresolved_alerts: int


# API Endpoints

@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    severity: str | None = None,
    *,
    principal: PrincipalDependency,
) -> AlertListResponse:
    """List alerts for the current tenant.

    Requires: backup:read scope
    """
    enforce_scope(principal, "backup:read")

    try:
        monitor = get_monitor()
        alerts = await monitor.get_alerts(
            tenant_id=principal.tenant_id,
            limit=limit,
            offset=offset,
        )

        # Filter by severity if provided
        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return AlertListResponse(
            alerts=[
                AlertResponse(
                    alert_id=a.alert_id,
                    tenant_id=a.tenant_id,
                    backup_id=a.backup_id,
                    alert_type=a.alert_type,
                    severity=a.severity,
                    title=a.title,
                    message=a.message,
                    created_at=a.created_at,
                    acknowledged_at=a.acknowledged_at,
                    resolved_at=a.resolved_at,
                )
                for a in alerts
            ],
            total=len(alerts),
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing alerts: {e!s}",
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Acknowledge an alert.

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")

    try:
        monitor = get_monitor()
        success = await monitor.acknowledge_alert(alert_id)

        if success:
            return {"message": "Alert acknowledged"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error acknowledging alert {alert_id}: {type(e).__name__}: {e}",
            extra={"alert_id": alert_id, "tenant_id": principal.tenant_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge alert. Please try again later.",
        ) from e


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Resolve an alert.

    Requires: backup:write scope
    """
    enforce_scope(principal, "backup:write")

    try:
        monitor = get_monitor()
        success = await monitor.resolve_alert(alert_id)

        if success:
            return {"message": "Alert resolved"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error resolving alert {alert_id}: {type(e).__name__}: {e}",
            extra={"alert_id": alert_id, "tenant_id": principal.tenant_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve alert. Please try again later.",
        ) from e


@router.get("/health", response_model=HealthCheckResponse)
async def get_health_status(
    principal: PrincipalDependency,
    storage_path: str | None = Query(None, description="Storage path for backups"),
) -> HealthCheckResponse:
    """Get backup system health status.

    Requires: backup:read scope
    """
    enforce_scope(principal, "backup:read")

    try:
        # Use provided path or default, then validate
        path_to_check = storage_path or DEFAULT_BACKUP_STORAGE_PATH
        validated_path = validate_storage_path(path_to_check)

        health_check = get_health_check()
        health_status = await health_check.perform_health_check(
            tenant_id=principal.tenant_id,
            storage_path=str(validated_path),
        )

        return HealthCheckResponse(
            healthy=health_status.get("healthy", False),
            backup_success_rate=health_status.get("backup_success_rate", 0.0),
            restore_success_rate=health_status.get("restore_success_rate", 0.0),
            verification_status=health_status.get("verification_status", {}),
            storage_health=health_status.get("storage_health", {}),
            timestamp=health_status.get("timestamp", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting health status: {type(e).__name__}: {e}",
            extra={"tenant_id": principal.tenant_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get health status. Please try again later.",
        ) from e


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    principal: PrincipalDependency,
) -> StatisticsResponse:
    """Get backup statistics for the current tenant.

    Requires: backup:read scope
    """
    enforce_scope(principal, "backup:read")

    try:
        collector = get_metrics_collector()
        stats = await collector.get_statistics(principal.tenant_id)

        return StatisticsResponse(
            tenant_id=stats.tenant_id,
            period_start=stats.period_start,
            period_end=stats.period_end,
            total_backups=stats.total_backups,
            successful_backups=stats.successful_backups,
            failed_backups=stats.failed_backups,
            success_rate=stats.success_rate,
            total_backup_size=stats.total_backup_size,
            total_compressed_size=stats.total_compressed_size,
            average_compression_ratio=stats.average_compression_ratio,
            average_backup_duration=stats.average_backup_duration,
            average_throughput=stats.average_throughput,
            total_restores=stats.total_restores,
            successful_restores=stats.successful_restores,
            failed_restores=stats.failed_restores,
            average_restore_duration=stats.average_restore_duration,
            total_verifications=stats.total_verifications,
            successful_verifications=stats.successful_verifications,
            failed_verifications=stats.failed_verifications,
            total_alerts=stats.total_alerts,
            critical_alerts=stats.critical_alerts,
            unresolved_alerts=stats.unresolved_alerts,
        )
    except Exception as e:
        logger.error(
            f"Error getting statistics: {type(e).__name__}: {e}",
            extra={"tenant_id": principal.tenant_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics. Please try again later.",
        ) from e


@router.get("/dashboard")
async def get_dashboard(
    principal: PrincipalDependency,
    storage_path: str | None = Query(None, description="Storage path for backups"),
) -> dict:
    """Get backup dashboard data.

    Requires: backup:read scope
    """
    enforce_scope(principal, "backup:read")

    try:
        monitor = get_monitor()
        health_check = get_health_check()
        collector = get_metrics_collector()

        # Validate storage path
        path_to_check = storage_path or DEFAULT_BACKUP_STORAGE_PATH
        validated_path = validate_storage_path(path_to_check)

        # Get health status
        health_status = await health_check.perform_health_check(
            tenant_id=principal.tenant_id,
            storage_path=str(validated_path),
        )

        # Get statistics
        stats = await collector.get_statistics(principal.tenant_id)

        # Get recent alerts
        recent_alerts = await monitor.get_alerts(
            tenant_id=principal.tenant_id,
            limit=10,
            offset=0,
        )

        return {
            "health": health_status,
            "statistics": {
                "total_backups": stats.total_backups,
                "successful_backups": stats.successful_backups,
                "failed_backups": stats.failed_backups,
                "success_rate": stats.success_rate,
                "total_backup_size": stats.total_backup_size,
                "average_compression_ratio": stats.average_compression_ratio,
                "average_backup_duration": stats.average_backup_duration,
                "total_restores": stats.total_restores,
                "successful_restores": stats.successful_restores,
                "failed_restores": stats.failed_restores,
            },
            "recent_alerts": [
                {
                    "alert_id": a.alert_id,
                    "severity": a.severity,
                    "title": a.title,
                    "message": a.message,
                    "created_at": a.created_at.isoformat(),
                }
                for a in recent_alerts
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting dashboard: {type(e).__name__}: {e}",
            extra={"tenant_id": principal.tenant_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard. Please try again later.",
        ) from e
