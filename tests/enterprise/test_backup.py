"""Tests for backup and recovery system."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.models.backup import (
    BackupMetadata,
    BackupType,
    BackupStatus,
    BackupStorageType,
    RestorePoint,
    RestoreStatus,
)
from backend.app.core.backup_storage import LocalBackupStorage
from backend.app.core.backup_encryption import (
    BackupProcessor,
    BackupEncryption,
    BackupCompression,
    BackupIntegrity,
)
from backend.app.core.backup_manager import BackupManager, BackupScheduler
from backend.app.core.backup_monitoring import (
    BackupMonitor,
    BackupHealthCheck,
    BackupMetricsCollector,
    AlertThreshold,
)


class TestBackupEncryption:
    """Test backup encryption."""

    def test_aes256_encryption_decryption(self):
        """Test AES-256-GCM encryption and decryption."""
        encryption = BackupEncryption()
        data = b"Test backup data"

        # Encrypt
        encrypted_data, iv = encryption.encrypt_backup(data)
        assert encrypted_data != data
        assert len(iv) == 12  # 96-bit IV

        # Decrypt
        decrypted_data = encryption.decrypt_backup(encrypted_data, iv)
        assert decrypted_data == data

    def test_backup_processor_compress_encrypt(self):
        """Test backup processor with compression and encryption."""
        processor = BackupProcessor(
            enable_encryption=True,
            enable_compression=True,
        )
        data = b"Test backup data" * 1000

        # Process
        processed_data, metadata = processor.process_backup(data)
        assert processed_data != data
        assert metadata["original_size"] == len(data)
        assert metadata["processed_size"] < len(data)
        assert metadata["compression_ratio"] < 1.0

        # Restore
        iv = bytes.fromhex(metadata["iv"])
        restored_data = processor.restore_backup(processed_data, iv)
        assert restored_data == data

    def test_checksum_calculation(self):
        """Test checksum calculation."""
        data = b"Test data"
        checksum = BackupIntegrity.calculate_checksum(data)
        assert len(checksum) == 64  # SHA-256 hex length

        # Verify checksum
        assert BackupIntegrity.verify_checksum(data, checksum)

        # Verify with wrong checksum
        wrong_checksum = "0" * 64
        assert not BackupIntegrity.verify_checksum(data, wrong_checksum)


class TestBackupStorage:
    """Test backup storage."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create temporary backup storage."""
        return LocalBackupStorage(base_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_upload_download_backup(self, storage):
        """Test uploading and downloading backup."""
        backup_id = "test-backup-001"
        data = b"Test backup data"
        metadata = BackupMetadata(
            backup_id=backup_id,
            tenant_id="tenant-123",
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            total_size=len(data),
            checksum="abc123",
        )

        # Upload
        success = await storage.upload_backup(backup_id, data, metadata)
        assert success

        # Download
        downloaded_data = await storage.download_backup(backup_id)
        assert downloaded_data == data

    @pytest.mark.asyncio
    async def test_delete_backup(self, storage):
        """Test deleting backup."""
        backup_id = "test-backup-002"
        data = b"Test backup data"
        metadata = BackupMetadata(
            backup_id=backup_id,
            tenant_id="tenant-123",
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
        )

        # Upload
        await storage.upload_backup(backup_id, data, metadata)

        # Delete
        success = await storage.delete_backup(backup_id)
        assert success

        # Verify deleted
        downloaded_data = await storage.download_backup(backup_id)
        assert downloaded_data is None

    @pytest.mark.asyncio
    async def test_list_backups(self, storage):
        """Test listing backups."""
        tenant_id = "tenant-123"

        # Upload multiple backups
        for i in range(3):
            backup_id = f"test-backup-{i:03d}"
            data = b"Test backup data"
            metadata = BackupMetadata(
                backup_id=backup_id,
                tenant_id=tenant_id,
                backup_type=BackupType.FULL,
                status=BackupStatus.COMPLETED,
            )
            await storage.upload_backup(backup_id, data, metadata)

        # List backups
        backups = await storage.list_backups(tenant_id, limit=10)
        assert len(backups) == 3


class TestBackupManager:
    """Test backup manager."""

    @pytest.fixture
    def backup_manager(self, tmp_path):
        """Create backup manager with temporary storage."""
        storage = LocalBackupStorage(base_path=str(tmp_path))
        return BackupManager(storage)

    @pytest.mark.asyncio
    async def test_create_backup(self, backup_manager):
        """Test creating a backup."""
        tenant_id = "tenant-123"
        data = b"Test backup data" * 100

        metadata = await backup_manager.create_backup(
            tenant_id=tenant_id,
            data=data,
            backup_type=BackupType.FULL,
            description="Test backup",
        )

        assert metadata is not None
        assert metadata.tenant_id == tenant_id
        assert metadata.status == BackupStatus.COMPLETED
        assert metadata.total_size == len(data)
        assert metadata.compressed_size < len(data)

    @pytest.mark.asyncio
    async def test_restore_backup(self, backup_manager):
        """Test restoring a backup."""
        tenant_id = "tenant-123"
        data = b"Test backup data" * 100

        # Create backup
        metadata = await backup_manager.create_backup(
            tenant_id=tenant_id,
            data=data,
            backup_type=BackupType.FULL,
        )

        # Restore backup
        restore_point = await backup_manager.restore_backup(
            backup_id=metadata.backup_id,
            tenant_id=tenant_id,
        )

        assert restore_point is not None
        assert restore_point.status == RestoreStatus.COMPLETED
        assert restore_point.verification_status == "passed"

    @pytest.mark.asyncio
    async def test_verify_backup(self, backup_manager):
        """Test verifying a backup."""
        tenant_id = "tenant-123"
        data = b"Test backup data" * 100

        # Create backup
        metadata = await backup_manager.create_backup(
            tenant_id=tenant_id,
            data=data,
            backup_type=BackupType.FULL,
        )

        # Verify backup
        verified = await backup_manager.verify_backup(metadata.backup_id)
        assert verified

    @pytest.mark.asyncio
    async def test_delete_backup(self, backup_manager):
        """Test deleting a backup."""
        tenant_id = "tenant-123"
        data = b"Test backup data"

        # Create backup
        metadata = await backup_manager.create_backup(
            tenant_id=tenant_id,
            data=data,
            backup_type=BackupType.FULL,
        )

        # Delete backup
        success = await backup_manager.delete_backup(
            backup_id=metadata.backup_id,
            tenant_id=tenant_id,
        )
        assert success

    @pytest.mark.asyncio
    async def test_list_backups(self, backup_manager):
        """Test listing backups."""
        tenant_id = "tenant-123"

        # Create multiple backups
        for i in range(3):
            data = b"Test backup data" * 100
            await backup_manager.create_backup(
                tenant_id=tenant_id,
                data=data,
                backup_type=BackupType.FULL,
            )

        # List backups
        backups = await backup_manager.list_backups(tenant_id, limit=10)
        assert len(backups) == 3


class TestBackupScheduler:
    """Test backup scheduler."""

    @pytest.fixture
    def scheduler(self, tmp_path):
        """Create backup scheduler."""
        storage = LocalBackupStorage(base_path=str(tmp_path))
        backup_manager = BackupManager(storage)
        return BackupScheduler(backup_manager)

    @pytest.mark.asyncio
    async def test_create_schedule(self, scheduler):
        """Test creating a backup schedule."""
        schedule = await scheduler.create_schedule(
            tenant_id="tenant-123",
            name="Daily Backup",
            backup_type=BackupType.FULL,
            frequency="daily",
            scheduled_time="02:00",
            retention_days=30,
        )

        assert schedule is not None
        assert schedule.name == "Daily Backup"
        assert schedule.frequency == "daily"
        assert schedule.enabled

    @pytest.mark.asyncio
    async def test_delete_schedule(self, scheduler):
        """Test deleting a backup schedule."""
        schedule = await scheduler.create_schedule(
            tenant_id="tenant-123",
            name="Daily Backup",
            backup_type=BackupType.FULL,
            frequency="daily",
        )

        success = await scheduler.delete_schedule(schedule.schedule_id)
        assert success

    @pytest.mark.asyncio
    async def test_list_schedules(self, scheduler):
        """Test listing backup schedules."""
        tenant_id = "tenant-123"

        # Create multiple schedules
        for i in range(3):
            await scheduler.create_schedule(
                tenant_id=tenant_id,
                name=f"Backup {i}",
                backup_type=BackupType.FULL,
                frequency="daily",
            )

        # List schedules
        schedules = await scheduler.list_schedules(tenant_id)
        assert len(schedules) == 3


class TestBackupMonitoring:
    """Test backup monitoring."""

    @pytest.fixture
    def monitor(self):
        """Create backup monitor."""
        return BackupMonitor(thresholds=AlertThreshold())

    @pytest.mark.asyncio
    async def test_check_backup_duration(self, monitor):
        """Test checking backup duration."""
        await monitor.check_backup_duration(
            backup_id="backup-001",
            tenant_id="tenant-123",
            duration_seconds=7200,  # 2 hours, exceeds 1 hour threshold
        )

        alerts = await monitor.get_alerts("tenant-123")
        assert len(alerts) == 1
        assert alerts[0].severity == "medium"

    @pytest.mark.asyncio
    async def test_check_storage_space(self, monitor):
        """Test checking storage space."""
        await monitor.check_storage_space(
            tenant_id="tenant-123",
            used_space_bytes=9000000000,  # 9 GB
            total_space_bytes=10000000000,  # 10 GB (90% usage)
        )

        alerts = await monitor.get_alerts("tenant-123")
        assert len(alerts) == 1
        assert alerts[0].severity == "high"

    @pytest.mark.asyncio
    async def test_check_backup_failure(self, monitor):
        """Test checking backup failures."""
        # Simulate 3 consecutive failures
        for i in range(3):
            await monitor.check_backup_failure(
                backup_id=f"backup-{i:03d}",
                tenant_id="tenant-123",
            )

        alerts = await monitor.get_alerts("tenant-123")
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, monitor):
        """Test acknowledging an alert."""
        await monitor.check_backup_duration(
            backup_id="backup-001",
            tenant_id="tenant-123",
            duration_seconds=7200,
        )

        alerts = await monitor.get_alerts("tenant-123")
        alert_id = alerts[0].alert_id

        success = await monitor.acknowledge_alert(alert_id)
        assert success

        alerts = await monitor.get_alerts("tenant-123")
        assert alerts[0].acknowledged_at is not None


class TestBackupMetrics:
    """Test backup metrics collection."""

    @pytest.fixture
    def collector(self):
        """Create metrics collector."""
        return BackupMetricsCollector()

    @pytest.mark.asyncio
    async def test_record_backup_success(self, collector):
        """Test recording successful backup."""
        await collector.record_backup_success(
            tenant_id="tenant-123",
            duration_seconds=1800,
            backup_size=1073741824,  # 1 GB
            compressed_size=322122547,  # ~300 MB
        )

        stats = await collector.get_statistics("tenant-123")
        assert stats.successful_backups == 1
        assert stats.total_backups == 1
        assert stats.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_record_backup_failure(self, collector):
        """Test recording failed backup."""
        await collector.record_backup_success(
            tenant_id="tenant-123",
            duration_seconds=1800,
            backup_size=1073741824,
            compressed_size=322122547,
        )
        await collector.record_backup_failure("tenant-123")

        stats = await collector.get_statistics("tenant-123")
        assert stats.successful_backups == 1
        assert stats.failed_backups == 1
        assert stats.total_backups == 2
        assert stats.success_rate == 0.5

    @pytest.mark.asyncio
    async def test_record_restore_success(self, collector):
        """Test recording successful restore."""
        await collector.record_restore_success(
            tenant_id="tenant-123",
            duration_seconds=900,
            restored_size=1073741824,
        )

        stats = await collector.get_statistics("tenant-123")
        assert stats.successful_restores == 1
        assert stats.total_restores == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
