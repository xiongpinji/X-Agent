"""Data models for backup and recovery system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class BackupType(str, Enum):
    """Backup type enumeration."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(str, Enum):
    """Backup status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    ARCHIVED = "archived"


class BackupStorageType(str, Enum):
    """Backup storage type enumeration."""
    LOCAL = "local"
    S3 = "s3"
    OSS = "oss"
    AZURE_BLOB = "azure_blob"
    GCS = "gcs"


class RestoreStatus(str, Enum):
    """Restore status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class BackupMetadata:
    """Backup metadata."""
    backup_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    backup_type: BackupType = BackupType.FULL
    status: BackupStatus = BackupStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None

    # Data information
    total_size: int = 0  # bytes
    compressed_size: int = 0  # bytes
    compression_ratio: float = 0.0
    table_count: int = 0
    record_count: int = 0

    # Encryption and verification
    encryption_algorithm: str = "AES-256-GCM"
    encryption_key_id: str = ""
    iv: str = ""  # AES-GCM 初始化向量(hex 编码),解密时必需
    checksum: str = ""  # SHA-256 hash(原始明文数据)
    checksum_algorithm: str = "SHA-256"

    # Storage information
    storage_type: BackupStorageType = BackupStorageType.LOCAL
    storage_path: str = ""
    storage_location: str = ""  # S3 bucket, OSS bucket, etc.

    # Retention policy
    retention_days: int = 30
    expiration_date: Optional[datetime] = None
    is_locked: bool = False  # Immutable backup

    # Backup chain
    parent_backup_id: Optional[str] = None  # For incremental backups
    base_backup_id: Optional[str] = None  # For differential backups

    # Performance metrics
    duration_seconds: float = 0.0
    throughput_mbps: float = 0.0

    # Additional metadata
    description: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupManifest:
    """Backup manifest containing table and data information."""
    backup_id: str
    tables: list[str] = field(default_factory=list)
    table_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    table_row_counts: dict[str, int] = field(default_factory=dict)
    table_sizes: dict[str, int] = field(default_factory=dict)
    incremental_changes: dict[str, dict[str, Any]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RestorePoint:
    """Point-in-time restore point."""
    restore_id: str = field(default_factory=lambda: str(uuid4()))
    backup_id: str = ""
    tenant_id: str = ""
    restore_type: str = "full"  # full, selective, pitr
    status: RestoreStatus = RestoreStatus.PENDING

    # Restore configuration
    target_time: Optional[datetime] = None  # For PITR
    target_tables: list[str] = field(default_factory=list)  # For selective restore
    target_tenant_id: Optional[str] = None  # For cross-tenant restore

    # Restore progress
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Performance metrics
    duration_seconds: float = 0.0
    restored_records: int = 0
    restored_size: int = 0

    # Verification
    verification_status: str = "pending"  # pending, in_progress, passed, failed
    verification_errors: list[str] = field(default_factory=list)

    # Additional metadata
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupSchedule:
    """Backup schedule configuration."""
    schedule_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    name: str = ""

    # Schedule configuration
    enabled: bool = True
    backup_type: BackupType = BackupType.FULL
    frequency: str = "daily"  # hourly, daily, weekly, monthly
    cron_expression: str = ""  # For custom schedules

    # Timing
    scheduled_time: str = "02:00"  # HH:MM format
    timezone: str = "UTC"

    # Retention policy
    retention_days: int = 30
    retention_count: int = 10

    # Storage configuration
    storage_type: BackupStorageType = BackupStorageType.LOCAL
    storage_location: str = ""

    # Encryption
    encryption_enabled: bool = True
    encryption_algorithm: str = "AES-256-GCM"

    # Compression
    compression_enabled: bool = True
    compression_algorithm: str = "gzip"

    # Notification
    notify_on_success: bool = True
    notify_on_failure: bool = True
    notification_emails: list[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None


@dataclass
class BackupAlert:
    """Backup alert/event."""
    alert_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    backup_id: Optional[str] = None

    # Alert information
    alert_type: str = ""  # success, failure, warning, info
    severity: str = "info"  # critical, high, medium, low, info
    title: str = ""
    message: str = ""

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    # Additional context
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupStatistics:
    """Backup statistics and metrics."""
    tenant_id: str = ""
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)

    # Backup statistics
    total_backups: int = 0
    successful_backups: int = 0
    failed_backups: int = 0
    success_rate: float = 0.0

    # Storage statistics
    total_backup_size: int = 0  # bytes
    total_compressed_size: int = 0  # bytes
    average_compression_ratio: float = 0.0

    # Performance statistics
    average_backup_duration: float = 0.0  # seconds
    average_throughput: float = 0.0  # MB/s

    # Restore statistics
    total_restores: int = 0
    successful_restores: int = 0
    failed_restores: int = 0
    average_restore_duration: float = 0.0

    # Verification statistics
    total_verifications: int = 0
    successful_verifications: int = 0
    failed_verifications: int = 0

    # Alerts
    total_alerts: int = 0
    critical_alerts: int = 0
    unresolved_alerts: int = 0
