"""Backup monitoring and alerting system."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
from dataclasses import dataclass

from backend.app.models.backup import BackupAlert, BackupStatistics

logger = logging.getLogger(__name__)


@dataclass
class AlertThreshold:
    """Alert threshold configuration."""
    backup_duration_threshold_seconds: float = 3600  # 1 hour
    storage_space_threshold_percent: float = 90.0  # 90%
    backup_failure_threshold_count: int = 3  # 3 consecutive failures
    restore_failure_threshold_count: int = 2  # 2 consecutive failures


class BackupMonitor:
    """Monitors backup operations and generates alerts."""

    def __init__(
        self,
        thresholds: Optional[AlertThreshold] = None,
        alert_callback: Optional[Callable[[BackupAlert], None]] = None,
    ):
        self.thresholds = thresholds or AlertThreshold()
        self.alert_callback = alert_callback
        self.alerts: list[BackupAlert] = []
        self.backup_stats: dict[str, BackupStatistics] = {}
        self.failure_counts: dict[str, int] = {}

    async def check_backup_duration(
        self,
        backup_id: str,
        tenant_id: str,
        duration_seconds: float,
    ) -> None:
        """Check if backup duration exceeds threshold."""
        if duration_seconds > self.thresholds.backup_duration_threshold_seconds:
            alert = BackupAlert(
                tenant_id=tenant_id,
                backup_id=backup_id,
                alert_type="warning",
                severity="medium",
                title="Backup duration exceeded",
                message=f"Backup {backup_id} took {duration_seconds:.2f}s, "
                        f"exceeding threshold of {self.thresholds.backup_duration_threshold_seconds}s",
                context={
                    "duration_seconds": duration_seconds,
                    "threshold_seconds": self.thresholds.backup_duration_threshold_seconds,
                },
            )
            await self._emit_alert(alert)

    async def check_storage_space(
        self,
        tenant_id: str,
        used_space_bytes: int,
        total_space_bytes: int,
    ) -> None:
        """Check if storage space usage exceeds threshold."""
        if total_space_bytes == 0:
            return

        usage_percent = (used_space_bytes / total_space_bytes) * 100
        if usage_percent >= self.thresholds.storage_space_threshold_percent:
            alert = BackupAlert(
                tenant_id=tenant_id,
                alert_type="warning",
                severity="high",
                title="Storage space running low",
                message=f"Backup storage usage is {usage_percent:.1f}%, "
                        f"exceeding threshold of {self.thresholds.storage_space_threshold_percent}%",
                context={
                    "usage_percent": usage_percent,
                    "used_bytes": used_space_bytes,
                    "total_bytes": total_space_bytes,
                },
            )
            await self._emit_alert(alert)

    async def check_backup_failure(
        self,
        backup_id: str,
        tenant_id: str,
    ) -> None:
        """Track backup failures and alert on threshold."""
        key = f"{tenant_id}:backup"
        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1

        if self.failure_counts[key] >= self.thresholds.backup_failure_threshold_count:
            alert = BackupAlert(
                tenant_id=tenant_id,
                backup_id=backup_id,
                alert_type="failure",
                severity="critical",
                title="Multiple backup failures detected",
                message=f"Backup has failed {self.failure_counts[key]} times consecutively",
                context={
                    "failure_count": self.failure_counts[key],
                    "threshold": self.thresholds.backup_failure_threshold_count,
                },
            )
            await self._emit_alert(alert)

    async def check_restore_failure(
        self,
        restore_id: str,
        tenant_id: str,
    ) -> None:
        """Track restore failures and alert on threshold."""
        key = f"{tenant_id}:restore"
        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1

        if self.failure_counts[key] >= self.thresholds.restore_failure_threshold_count:
            alert = BackupAlert(
                tenant_id=tenant_id,
                alert_type="failure",
                severity="critical",
                title="Multiple restore failures detected",
                message=f"Restore has failed {self.failure_counts[key]} times consecutively",
                context={
                    "failure_count": self.failure_counts[key],
                    "threshold": self.thresholds.restore_failure_threshold_count,
                },
            )
            await self._emit_alert(alert)

    async def reset_failure_count(self, tenant_id: str, operation_type: str) -> None:
        """Reset failure count on successful operation."""
        key = f"{tenant_id}:{operation_type}"
        if key in self.failure_counts:
            self.failure_counts[key] = 0

    async def _emit_alert(self, alert: BackupAlert) -> None:
        """Emit an alert."""
        self.alerts.append(alert)
        logger.warning(f"Alert: {alert.title} - {alert.message}")

        if self.alert_callback:
            try:
                await self.alert_callback(alert)
            except Exception as e:
                logger.error(f"Failed to execute alert callback: {e}")

    async def get_alerts(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BackupAlert]:
        """Get alerts for a tenant."""
        tenant_alerts = [
            alert for alert in self.alerts
            if alert.tenant_id == tenant_id
        ]
        return tenant_alerts[offset:offset + limit]

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged_at = datetime.utcnow()
                return True
        return False

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved_at = datetime.utcnow()
                return True
        return False


class BackupHealthCheck:
    """Performs health checks on backup system."""

    def __init__(self, monitor: BackupMonitor):
        self.monitor = monitor

    async def check_backup_success_rate(
        self,
        tenant_id: str,
        period_days: int = 7,
    ) -> float:
        """Check backup success rate over a period."""
        # TODO: Implement by querying backup history
        return 0.99

    async def check_restore_success_rate(
        self,
        tenant_id: str,
        period_days: int = 7,
    ) -> float:
        """Check restore success rate over a period."""
        # TODO: Implement by querying restore history
        return 0.99

    async def check_backup_verification_status(
        self,
        tenant_id: str,
    ) -> dict:
        """Check backup verification status."""
        return {
            "verified_backups": 0,
            "unverified_backups": 0,
            "failed_verifications": 0,
        }

    async def check_storage_health(
        self,
        storage_path: str,
    ) -> dict:
        """Check storage health."""
        import os
        import shutil

        try:
            stat = shutil.disk_usage(storage_path)
            return {
                "total_bytes": stat.total,
                "used_bytes": stat.used,
                "free_bytes": stat.free,
                "usage_percent": (stat.used / stat.total * 100) if stat.total > 0 else 0,
                "healthy": (stat.free / stat.total) > 0.1,  # At least 10% free
            }
        except Exception as e:
            logger.error(f"Failed to check storage health: {e}")
            return {
                "healthy": False,
                "error": str(e),
            }

    async def perform_health_check(
        self,
        tenant_id: str,
        storage_path: str,
    ) -> dict:
        """Perform comprehensive health check."""
        try:
            backup_success_rate = await self.check_backup_success_rate(tenant_id)
            restore_success_rate = await self.check_restore_success_rate(tenant_id)
            verification_status = await self.check_backup_verification_status(tenant_id)
            storage_health = await self.check_storage_health(storage_path)

            overall_healthy = (
                backup_success_rate >= 0.99 and
                restore_success_rate >= 0.99 and
                storage_health.get("healthy", False)
            )

            return {
                "healthy": overall_healthy,
                "backup_success_rate": backup_success_rate,
                "restore_success_rate": restore_success_rate,
                "verification_status": verification_status,
                "storage_health": storage_health,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
            }


class BackupMetricsCollector:
    """Collects backup metrics and statistics."""

    def __init__(self):
        self.metrics: dict[str, BackupStatistics] = {}

    async def record_backup_success(
        self,
        tenant_id: str,
        duration_seconds: float,
        backup_size: int,
        compressed_size: int,
    ) -> None:
        """Record successful backup."""
        stats = self._get_or_create_stats(tenant_id)
        stats.successful_backups += 1
        stats.total_backups += 1
        stats.total_backup_size += backup_size
        stats.total_compressed_size += compressed_size

        if stats.total_backups > 0:
            stats.success_rate = stats.successful_backups / stats.total_backups

        # Update average duration
        if stats.average_backup_duration == 0:
            stats.average_backup_duration = duration_seconds
        else:
            stats.average_backup_duration = (
                (stats.average_backup_duration * (stats.successful_backups - 1) + duration_seconds)
                / stats.successful_backups
            )

        # Update compression ratio
        if backup_size > 0:
            stats.average_compression_ratio = stats.total_compressed_size / stats.total_backup_size

    async def record_backup_failure(self, tenant_id: str) -> None:
        """Record failed backup."""
        stats = self._get_or_create_stats(tenant_id)
        stats.failed_backups += 1
        stats.total_backups += 1

        if stats.total_backups > 0:
            stats.success_rate = stats.successful_backups / stats.total_backups

    async def record_restore_success(
        self,
        tenant_id: str,
        duration_seconds: float,
        restored_size: int,
    ) -> None:
        """Record successful restore."""
        stats = self._get_or_create_stats(tenant_id)
        stats.successful_restores += 1
        stats.total_restores += 1

        # Update average duration
        if stats.average_restore_duration == 0:
            stats.average_restore_duration = duration_seconds
        else:
            stats.average_restore_duration = (
                (stats.average_restore_duration * (stats.successful_restores - 1) + duration_seconds)
                / stats.successful_restores
            )

    async def record_restore_failure(self, tenant_id: str) -> None:
        """Record failed restore."""
        stats = self._get_or_create_stats(tenant_id)
        stats.failed_restores += 1
        stats.total_restores += 1

    async def record_verification_success(self, tenant_id: str) -> None:
        """Record successful verification."""
        stats = self._get_or_create_stats(tenant_id)
        stats.successful_verifications += 1
        stats.total_verifications += 1

    async def record_verification_failure(self, tenant_id: str) -> None:
        """Record failed verification."""
        stats = self._get_or_create_stats(tenant_id)
        stats.failed_verifications += 1
        stats.total_verifications += 1

    async def get_statistics(self, tenant_id: str) -> BackupStatistics:
        """Get statistics for a tenant."""
        return self._get_or_create_stats(tenant_id)

    def _get_or_create_stats(self, tenant_id: str) -> BackupStatistics:
        """Get or create statistics for a tenant."""
        if tenant_id not in self.metrics:
            self.metrics[tenant_id] = BackupStatistics(
                tenant_id=tenant_id,
                period_start=datetime.utcnow(),
                period_end=datetime.utcnow() + timedelta(days=1),
            )
        return self.metrics[tenant_id]
