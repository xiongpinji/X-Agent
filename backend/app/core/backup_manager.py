"""Core backup and recovery manager."""

import asyncio
import logging
from datetime import datetime
from uuid import uuid4

from backend.app.core.backup_encryption import BackupProcessor
from backend.app.core.backup_storage import (
    BackupStorageProvider,
)
from backend.app.models.backup import (
    BackupAlert,
    BackupMetadata,
    BackupSchedule,
    BackupStatus,
    BackupStorageType,
    BackupType,
    RestorePoint,
    RestoreStatus,
)

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages backup operations."""

    def __init__(
        self,
        storage_provider: BackupStorageProvider,
        encryption_key: bytes | None = None,
        enable_encryption: bool = True,
        enable_compression: bool = True,
    ):
        self.storage = storage_provider
        self.processor = BackupProcessor(
            encryption_key=encryption_key,
            enable_encryption=enable_encryption,
            enable_compression=enable_compression,
        )
        self.backups: dict[str, BackupMetadata] = {}
        self.alerts: list[BackupAlert] = []

    async def create_backup(
        self,
        tenant_id: str,
        data: bytes,
        backup_type: BackupType = BackupType.FULL,
        description: str = "",
        tags: dict[str, str] | None = None,
    ) -> BackupMetadata | None:
        """Create a new backup."""
        try:
            backup_id = str(uuid4())
            logger.info(f"Creating backup {backup_id} for tenant {tenant_id}")

            # Create metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                tenant_id=tenant_id,
                backup_type=backup_type,
                status=BackupStatus.IN_PROGRESS,
                started_at=datetime.utcnow(),
                description=description,
                tags=tags or {},
            )

            # Process backup (compress and encrypt)
            start_time = datetime.utcnow()
            processed_data, process_metadata = self.processor.process_backup(data)
            duration = (datetime.utcnow() - start_time).total_seconds()

            # Update metadata
            metadata.total_size = process_metadata["original_size"]
            metadata.compressed_size = process_metadata["processed_size"]
            metadata.compression_ratio = process_metadata["compression_ratio"]
            metadata.checksum = process_metadata["checksum"]
            metadata.iv = process_metadata["iv"]
            metadata.duration_seconds = duration
            metadata.throughput_mbps = (
                metadata.total_size / (1024 * 1024 * duration)
                if duration > 0 else 0
            )

            # Upload to storage
            if await self.storage.upload_backup(backup_id, processed_data, metadata):
                metadata.status = BackupStatus.COMPLETED
                metadata.completed_at = datetime.utcnow()
                self.backups[backup_id] = metadata

                # Create success alert
                await self._create_alert(
                    tenant_id=tenant_id,
                    backup_id=backup_id,
                    alert_type="success",
                    severity="info",
                    title="Backup completed successfully",
                    message=f"Backup {backup_id} completed in {duration:.2f}s",
                )

                logger.info(f"Backup {backup_id} created successfully")
                return metadata
            else:
                metadata.status = BackupStatus.FAILED
                await self._create_alert(
                    tenant_id=tenant_id,
                    backup_id=backup_id,
                    alert_type="failure",
                    severity="high",
                    title="Backup failed",
                    message=f"Failed to upload backup {backup_id} to storage",
                )
                logger.error(f"Failed to upload backup {backup_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            await self._create_alert(
                tenant_id=tenant_id,
                alert_type="failure",
                severity="critical",
                title="Backup creation failed",
                message=f"Error: {e!s}",
            )
            return None

    async def restore_backup(
        self,
        backup_id: str,
        tenant_id: str,
    ) -> RestorePoint | None:
        """Restore from a backup."""
        try:
            logger.info(f"Restoring backup {backup_id} for tenant {tenant_id}")

            # Create restore point
            restore_id = str(uuid4())
            restore_point = RestorePoint(
                restore_id=restore_id,
                backup_id=backup_id,
                tenant_id=tenant_id,
                status=RestoreStatus.IN_PROGRESS,
                started_at=datetime.utcnow(),
            )

            # Get backup metadata
            metadata = await self.storage.get_backup_metadata(backup_id)
            if not metadata:
                logger.error(f"Backup {backup_id} not found")
                restore_point.status = RestoreStatus.FAILED
                return restore_point

            # Download backup
            processed_data = await self.storage.download_backup(backup_id)
            if not processed_data:
                logger.error(f"Failed to download backup {backup_id}")
                restore_point.status = RestoreStatus.FAILED
                return restore_point

            # Restore backup (decrypt and decompress)
            start_time = datetime.utcnow()
            try:
                iv_hex = metadata.get("iv", "") if isinstance(metadata, dict) else ""
                iv = bytes.fromhex(iv_hex) if iv_hex else None
                restored_data = self.processor.restore_backup(processed_data, iv)
            except Exception as e:
                logger.error(f"Failed to restore backup data: {e}")
                restore_point.status = RestoreStatus.FAILED
                return restore_point

            duration = (datetime.utcnow() - start_time).total_seconds()

            # Verify integrity
            if not self.processor.integrity.verify_checksum(
                restored_data,
                metadata.get("checksum") if isinstance(metadata, dict) else metadata.checksum,
            ):
                logger.error(f"Backup {backup_id} integrity check failed")
                restore_point.status = RestoreStatus.FAILED
                restore_point.verification_status = "failed"
                restore_point.verification_errors.append("Checksum mismatch")
                return restore_point

            # Update restore point
            restore_point.status = RestoreStatus.COMPLETED
            restore_point.completed_at = datetime.utcnow()
            restore_point.duration_seconds = duration
            restore_point.restored_size = len(restored_data)
            restore_point.verification_status = "passed"

            await self._create_alert(
                tenant_id=tenant_id,
                backup_id=backup_id,
                alert_type="success",
                severity="info",
                title="Restore completed successfully",
                message=f"Restore {restore_id} completed in {duration:.2f}s",
            )

            logger.info(f"Backup {backup_id} restored successfully")
            return restore_point

        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            await self._create_alert(
                tenant_id=tenant_id,
                backup_id=backup_id,
                alert_type="failure",
                severity="critical",
                title="Restore failed",
                message=f"Error: {e!s}",
            )
            return None

    async def verify_backup(
        self,
        backup_id: str,
    ) -> bool:
        """Verify backup integrity."""
        try:
            logger.info(f"Verifying backup {backup_id}")
            return await self.storage.verify_backup_integrity(backup_id)
        except Exception as e:
            logger.error(f"Failed to verify backup {backup_id}: {e}")
            return False

    async def delete_backup(
        self,
        backup_id: str,
        tenant_id: str,
    ) -> bool:
        """Delete a backup."""
        try:
            logger.info(f"Deleting backup {backup_id}")
            if await self.storage.delete_backup(backup_id):
                if backup_id in self.backups:
                    del self.backups[backup_id]
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete backup {backup_id}: {e}")
            return False

    async def list_backups(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BackupMetadata]:
        """List backups for a tenant."""
        try:
            return await self.storage.list_backups(tenant_id, limit, offset)
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    async def cleanup_expired_backups(
        self,
        tenant_id: str,
    ) -> int:
        """Clean up expired backups."""
        try:
            logger.info(f"Cleaning up expired backups for tenant {tenant_id}")
            deleted_count = await self.storage.cleanup_expired_backups(tenant_id)
            logger.info(f"Deleted {deleted_count} expired backups")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup expired backups: {e}")
            return 0

    async def _create_alert(
        self,
        tenant_id: str,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        backup_id: str | None = None,
    ) -> None:
        """Create a backup alert."""
        try:
            alert = BackupAlert(
                tenant_id=tenant_id,
                backup_id=backup_id,
                alert_type=alert_type,
                severity=severity,
                title=title,
                message=message,
            )
            self.alerts.append(alert)
            logger.info(f"Alert created: {title}")
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")


class BackupScheduler:
    """Manages backup schedules."""

    def __init__(self, backup_manager: BackupManager):
        self.backup_manager = backup_manager
        self.schedules: dict[str, BackupSchedule] = {}
        self.running_tasks: dict[str, asyncio.Task] = {}

    async def create_schedule(
        self,
        tenant_id: str,
        name: str,
        backup_type: BackupType = BackupType.FULL,
        frequency: str = "daily",
        scheduled_time: str = "02:00",
        retention_days: int = 30,
        storage_type: BackupStorageType = BackupStorageType.LOCAL,
    ) -> BackupSchedule:
        """Create a backup schedule."""
        try:
            schedule_id = str(uuid4())
            schedule = BackupSchedule(
                schedule_id=schedule_id,
                tenant_id=tenant_id,
                name=name,
                backup_type=backup_type,
                frequency=frequency,
                scheduled_time=scheduled_time,
                retention_days=retention_days,
                storage_type=storage_type,
            )
            self.schedules[schedule_id] = schedule
            logger.info(f"Backup schedule {schedule_id} created")
            return schedule
        except Exception as e:
            logger.error(f"Failed to create backup schedule: {e}")
            raise

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a backup schedule."""
        try:
            if schedule_id in self.schedules:
                del self.schedules[schedule_id]
                if schedule_id in self.running_tasks:
                    self.running_tasks[schedule_id].cancel()
                    del self.running_tasks[schedule_id]
                logger.info(f"Backup schedule {schedule_id} deleted")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete backup schedule: {e}")
            return False

    async def list_schedules(self, tenant_id: str) -> list[BackupSchedule]:
        """List backup schedules for a tenant."""
        try:
            return [
                schedule for schedule in self.schedules.values()
                if schedule.tenant_id == tenant_id
            ]
        except Exception as e:
            logger.error(f"Failed to list backup schedules: {e}")
            return []

    async def start_schedule(self, schedule_id: str) -> bool:
        """Start a backup schedule."""
        try:
            if schedule_id not in self.schedules:
                logger.error(f"Schedule {schedule_id} not found")
                return False

            self.schedules[schedule_id]
            if schedule_id in self.running_tasks:
                logger.warning(f"Schedule {schedule_id} is already running")
                return False

            # Create and start task
            task = asyncio.create_task(self._run_schedule(schedule_id))
            self.running_tasks[schedule_id] = task
            logger.info(f"Backup schedule {schedule_id} started")
            return True
        except Exception as e:
            logger.error(f"Failed to start backup schedule: {e}")
            return False

    async def _run_schedule(self, schedule_id: str) -> None:
        """Run a backup schedule."""
        try:
            self.schedules[schedule_id]
            logger.info(f"Running backup schedule {schedule_id}")

            # NOTE: Requires cron scheduler integration (APScheduler/celery-beat)
            # This would involve:
            # 1. Parsing the cron expression or frequency
            # 2. Waiting until the scheduled time
            # 3. Executing the backup
            # 4. Handling errors and retries
            # 5. Cleaning up expired backups

        except asyncio.CancelledError:
            logger.info(f"Backup schedule {schedule_id} cancelled")
        except Exception as e:
            logger.error(f"Error running backup schedule {schedule_id}: {e}")
