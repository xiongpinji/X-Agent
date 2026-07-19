"""Backup system configuration."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BackupConfig:
    """Backup system configuration."""

    # Storage configuration
    storage_type: str = os.getenv("BACKUP_STORAGE_TYPE", "local")
    storage_path: str = os.getenv("BACKUP_STORAGE_PATH", "/data/backups")

    # S3 configuration
    s3_bucket: str = os.getenv("BACKUP_S3_BUCKET", "")
    s3_region: str = os.getenv("BACKUP_S3_REGION", "us-east-1")
    s3_access_key: Optional[str] = os.getenv("BACKUP_S3_ACCESS_KEY")
    s3_secret_key: Optional[str] = os.getenv("BACKUP_S3_SECRET_KEY")

    # Encryption configuration
    encryption_enabled: bool = os.getenv("BACKUP_ENCRYPTION_ENABLED", "true").lower() == "true"
    encryption_algorithm: str = os.getenv("BACKUP_ENCRYPTION_ALGORITHM", "AES-256-GCM")
    encryption_key: Optional[str] = os.getenv("BACKUP_ENCRYPTION_KEY")

    # Compression configuration
    compression_enabled: bool = os.getenv("BACKUP_COMPRESSION_ENABLED", "true").lower() == "true"
    compression_algorithm: str = os.getenv("BACKUP_COMPRESSION_ALGORITHM", "gzip")
    compression_level: int = int(os.getenv("BACKUP_COMPRESSION_LEVEL", "9"))

    # Backup schedule configuration
    backup_frequency: str = os.getenv("BACKUP_FREQUENCY", "daily")
    backup_time: str = os.getenv("BACKUP_TIME", "02:00")
    backup_timezone: str = os.getenv("BACKUP_TIMEZONE", "UTC")

    # Retention configuration
    retention_days: int = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
    retention_count: int = int(os.getenv("BACKUP_RETENTION_COUNT", "10"))

    # Monitoring configuration
    monitoring_enabled: bool = os.getenv("BACKUP_MONITORING_ENABLED", "true").lower() == "true"
    alert_email: str = os.getenv("BACKUP_ALERT_EMAIL", "")
    backup_duration_threshold: int = int(os.getenv("BACKUP_DURATION_THRESHOLD", "3600"))
    storage_space_threshold: float = float(os.getenv("BACKUP_STORAGE_SPACE_THRESHOLD", "90.0"))

    # Performance configuration
    parallel_threads: int = int(os.getenv("BACKUP_PARALLEL_THREADS", "4"))
    chunk_size: int = int(os.getenv("BACKUP_CHUNK_SIZE", "10485760"))  # 10 MB

    # Verification configuration
    verify_after_backup: bool = os.getenv("BACKUP_VERIFY_AFTER_BACKUP", "true").lower() == "true"
    verify_algorithm: str = os.getenv("BACKUP_VERIFY_ALGORITHM", "SHA-256")

    # 3-2-1 backup rule configuration
    enable_321_rule: bool = os.getenv("BACKUP_ENABLE_321_RULE", "true").lower() == "true"
    local_copies: int = int(os.getenv("BACKUP_LOCAL_COPIES", "2"))
    cloud_copies: int = int(os.getenv("BACKUP_CLOUD_COPIES", "1"))
    offsite_copies: int = int(os.getenv("BACKUP_OFFSITE_COPIES", "1"))


def get_backup_config() -> BackupConfig:
    """Get backup configuration."""
    return BackupConfig()
