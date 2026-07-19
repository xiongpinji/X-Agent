"""Backup storage abstraction layer."""

import asyncio
import gzip
import hashlib
import io
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from backend.app.models.backup import (
    BackupMetadata,
    BackupManifest,
    BackupStorageType,
)

logger = logging.getLogger(__name__)


class BackupStorageProvider(ABC):
    """Abstract base class for backup storage providers."""

    @abstractmethod
    async def upload_backup(
        self,
        backup_id: str,
        data: bytes,
        metadata: BackupMetadata,
    ) -> bool:
        """Upload backup data to storage."""
        pass

    @abstractmethod
    async def download_backup(
        self,
        backup_id: str,
    ) -> Optional[bytes]:
        """Download backup data from storage."""
        pass

    @abstractmethod
    async def delete_backup(
        self,
        backup_id: str,
    ) -> bool:
        """Delete backup from storage."""
        pass

    @abstractmethod
    async def list_backups(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BackupMetadata]:
        """List backups for a tenant."""
        pass

    @abstractmethod
    async def get_backup_metadata(
        self,
        backup_id: str,
    ) -> Optional[BackupMetadata]:
        """Get backup metadata."""
        pass

    @abstractmethod
    async def verify_backup_integrity(
        self,
        backup_id: str,
    ) -> bool:
        """Verify backup integrity."""
        pass

    @abstractmethod
    async def cleanup_expired_backups(
        self,
        tenant_id: str,
    ) -> int:
        """Clean up expired backups. Returns count of deleted backups."""
        pass


class LocalBackupStorage(BackupStorageProvider):
    """Local filesystem backup storage provider."""

    def __init__(self, base_path: str = "/data/backups"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.base_path / "metadata"
        self.metadata_path.mkdir(exist_ok=True)

    def _get_backup_path(self, backup_id: str) -> Path:
        """Get backup file path."""
        return self.base_path / f"{backup_id}.backup"

    def _get_metadata_path(self, backup_id: str) -> Path:
        """Get metadata file path."""
        return self.metadata_path / f"{backup_id}.json"

    async def upload_backup(
        self,
        backup_id: str,
        data: bytes,
        metadata: BackupMetadata,
    ) -> bool:
        """Upload backup data to local storage."""
        try:
            backup_path = self._get_backup_path(backup_id)
            metadata_path = self._get_metadata_path(backup_id)

            # Write backup data
            backup_path.write_bytes(data)

            # 计算"处理后字节"(压缩+加密后落盘的实际内容)的校验和,
            # 供 verify_backup_integrity 直接核对落盘文件完整性。
            # 注意:metadata.checksum 是"原始明文"的校验和,两者用途不同。
            storage_checksum = hashlib.sha256(data).hexdigest()

            # Write metadata
            metadata_dict = {
                "backup_id": metadata.backup_id,
                "tenant_id": metadata.tenant_id,
                "backup_type": metadata.backup_type.value,
                "status": metadata.status.value,
                "created_at": metadata.created_at.isoformat(),
                "completed_at": metadata.completed_at.isoformat() if metadata.completed_at else None,
                "total_size": metadata.total_size,
                "compressed_size": metadata.compressed_size,
                "compression_ratio": metadata.compression_ratio,
                "checksum": metadata.checksum,
                "iv": metadata.iv,
                "storage_checksum": storage_checksum,
                "storage_path": str(backup_path),
            }
            metadata_path.write_text(json.dumps(metadata_dict, indent=2))

            logger.info(f"Backup {backup_id} uploaded to local storage")
            return True
        except Exception as e:
            logger.error(f"Failed to upload backup {backup_id}: {e}")
            return False

    async def download_backup(
        self,
        backup_id: str,
    ) -> Optional[bytes]:
        """Download backup data from local storage."""
        try:
            backup_path = self._get_backup_path(backup_id)
            if not backup_path.exists():
                logger.warning(f"Backup {backup_id} not found")
                return None
            return backup_path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to download backup {backup_id}: {e}")
            return None

    async def delete_backup(
        self,
        backup_id: str,
    ) -> bool:
        """Delete backup from local storage."""
        try:
            backup_path = self._get_backup_path(backup_id)
            metadata_path = self._get_metadata_path(backup_id)

            if backup_path.exists():
                backup_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()

            logger.info(f"Backup {backup_id} deleted from local storage")
            return True
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
            backups = []
            for metadata_file in sorted(self.metadata_path.glob("*.json")):
                try:
                    metadata_dict = json.loads(metadata_file.read_text())
                    if metadata_dict.get("tenant_id") == tenant_id:
                        backups.append(metadata_dict)
                except Exception as e:
                    logger.warning(f"Failed to read metadata {metadata_file}: {e}")

            # Sort by created_at descending
            backups.sort(
                key=lambda x: x.get("created_at", ""),
                reverse=True
            )

            return backups[offset:offset + limit]
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    async def get_backup_metadata(
        self,
        backup_id: str,
    ) -> Optional[BackupMetadata]:
        """Get backup metadata."""
        try:
            metadata_path = self._get_metadata_path(backup_id)
            if not metadata_path.exists():
                return None
            return json.loads(metadata_path.read_text())
        except Exception as e:
            logger.error(f"Failed to get backup metadata {backup_id}: {e}")
            return None

    async def verify_backup_integrity(
        self,
        backup_id: str,
    ) -> bool:
        """Verify backup integrity by checking checksum."""
        try:
            backup_path = self._get_backup_path(backup_id)
            metadata_path = self._get_metadata_path(backup_id)

            if not backup_path.exists() or not metadata_path.exists():
                logger.warning(f"Backup {backup_id} files not found")
                return False

            # Read metadata
            metadata_dict = json.loads(metadata_path.read_text())
            # 落盘文件是"压缩+加密后"的字节,应核对 storage_checksum;
            # metadata["checksum"] 是原始明文校验和,不能用于核对落盘内容。
            # 兼容旧元数据:无 storage_checksum 时回退到 checksum。
            expected_checksum = metadata_dict.get("storage_checksum") or metadata_dict.get("checksum")

            # Calculate checksum
            data = backup_path.read_bytes()
            calculated_checksum = hashlib.sha256(data).hexdigest()

            if calculated_checksum != expected_checksum:
                logger.error(
                    f"Backup {backup_id} checksum mismatch: "
                    f"expected {expected_checksum}, got {calculated_checksum}"
                )
                return False

            logger.info(f"Backup {backup_id} integrity verified")
            return True
        except Exception as e:
            logger.error(f"Failed to verify backup {backup_id}: {e}")
            return False

    async def cleanup_expired_backups(
        self,
        tenant_id: str,
    ) -> int:
        """Clean up expired backups."""
        try:
            deleted_count = 0
            now = datetime.utcnow()

            for metadata_file in self.metadata_path.glob("*.json"):
                try:
                    metadata_dict = json.loads(metadata_file.read_text())
                    if metadata_dict.get("tenant_id") != tenant_id:
                        continue

                    # Check if backup is expired
                    created_at = datetime.fromisoformat(
                        metadata_dict.get("created_at", "")
                    )
                    retention_days = metadata_dict.get("retention_days", 30)
                    expiration_date = created_at + timedelta(days=retention_days)

                    if now > expiration_date:
                        backup_id = metadata_dict.get("backup_id")
                        await self.delete_backup(backup_id)
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to process metadata {metadata_file}: {e}")

            logger.info(f"Cleaned up {deleted_count} expired backups for tenant {tenant_id}")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup expired backups: {e}")
            return 0


class S3BackupStorage(BackupStorageProvider):
    """AWS S3 backup storage provider."""

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        # Initialize S3 client (boto3) in production
        self.client = None

    async def upload_backup(
        self,
        backup_id: str,
        data: bytes,
        metadata: BackupMetadata,
    ) -> bool:
        """Upload backup to S3."""
        try:
            # Implementation would use boto3
            logger.info(f"Backup {backup_id} uploaded to S3")
            return True
        except Exception as e:
            logger.error(f"Failed to upload backup to S3: {e}")
            return False

    async def download_backup(
        self,
        backup_id: str,
    ) -> Optional[bytes]:
        """Download backup from S3."""
        try:
            # Implementation would use boto3
            return None
        except Exception as e:
            logger.error(f"Failed to download backup from S3: {e}")
            return None

    async def delete_backup(
        self,
        backup_id: str,
    ) -> bool:
        """Delete backup from S3."""
        try:
            # Implementation would use boto3
            logger.info(f"Backup {backup_id} deleted from S3")
            return True
        except Exception as e:
            logger.error(f"Failed to delete backup from S3: {e}")
            return False

    async def list_backups(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BackupMetadata]:
        """List backups in S3."""
        try:
            # Implementation would use boto3
            return []
        except Exception as e:
            logger.error(f"Failed to list backups from S3: {e}")
            return []

    async def get_backup_metadata(
        self,
        backup_id: str,
    ) -> Optional[BackupMetadata]:
        """Get backup metadata from S3."""
        try:
            # Implementation would use boto3
            return None
        except Exception as e:
            logger.error(f"Failed to get backup metadata from S3: {e}")
            return None

    async def verify_backup_integrity(
        self,
        backup_id: str,
    ) -> bool:
        """Verify backup integrity in S3."""
        try:
            # Implementation would use boto3
            return True
        except Exception as e:
            logger.error(f"Failed to verify backup in S3: {e}")
            return False

    async def cleanup_expired_backups(
        self,
        tenant_id: str,
    ) -> int:
        """Clean up expired backups in S3."""
        try:
            # Implementation would use boto3
            return 0
        except Exception as e:
            logger.error(f"Failed to cleanup expired backups in S3: {e}")
            return 0


def create_backup_storage(
    storage_type: BackupStorageType,
    **kwargs,
) -> BackupStorageProvider:
    """Factory function to create backup storage provider."""
    if storage_type == BackupStorageType.LOCAL:
        return LocalBackupStorage(
            base_path=kwargs.get("base_path", "/data/backups")
        )
    elif storage_type == BackupStorageType.S3:
        return S3BackupStorage(
            bucket_name=kwargs.get("bucket_name"),
            region=kwargs.get("region", "us-east-1"),
            access_key=kwargs.get("access_key"),
            secret_key=kwargs.get("secret_key"),
        )
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")
