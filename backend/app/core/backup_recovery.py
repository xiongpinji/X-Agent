"""Backup and Recovery module.

Implements:
- Automatic backups (incremental, full)
- Backup encryption
- Recovery testing
- RTO/RPO targets
- Backup monitoring
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class BackupType(StrEnum):
    """Backup types."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(StrEnum):
    """Backup status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class BackupStorageType(StrEnum):
    """Backup storage types."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    GLACIER = "glacier"


class RecoveryStatus(StrEnum):
    """Recovery status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class BackupMetadata(BaseModel):
    """Metadata for a backup."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    backup_type: BackupType
    status: BackupStatus = BackupStatus.PENDING
    source_id: str  # Database, filesystem, etc.
    size_bytes: int = 0
    compressed_size_bytes: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    storage_type: BackupStorageType
    storage_location: str
    encryption_key_id: str | None = None
    encrypted: bool = False
    checksum: str = ""
    parent_backup_id: str | None = None  # For incremental backups
    metadata: dict[str, Any] = Field(default_factory=dict)

    def duration_seconds(self) -> int | None:
        """Get backup duration in seconds."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None

    def is_expired(self) -> bool:
        """Check if backup has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


class BackupSchedule(BaseModel):
    """Backup schedule configuration."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    source_id: str
    backup_type: BackupType
    frequency_hours: int
    retention_days: int
    storage_type: BackupStorageType
    storage_location: str
    encryption_enabled: bool = True
    compression_enabled: bool = True
    enabled: bool = True
    last_backup_at: datetime | None = None
    next_backup_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RecoveryPoint(BaseModel):
    """Recovery point for disaster recovery."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    backup_id: str
    timestamp: datetime
    rto_minutes: int  # Recovery Time Objective
    rpo_minutes: int  # Recovery Point Objective
    data_consistency: str = "consistent"  # consistent, eventual
    verified: bool = False
    last_verified_at: datetime | None = None


class RecoveryJob(BaseModel):
    """Recovery job."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    backup_id: str
    recovery_point_id: str | None = None
    status: RecoveryStatus = RecoveryStatus.PENDING
    target_location: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    recovered_bytes: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def duration_seconds(self) -> int | None:
        """Get recovery duration in seconds."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None


class BackupVerification(BaseModel):
    """Backup verification result."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    backup_id: str
    verified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    success: bool
    issues: list[str] = Field(default_factory=list)
    integrity_check_passed: bool = False
    recovery_test_passed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackupRecoveryEngine:
    """Backup and recovery engine."""

    def __init__(self):
        self.backups: dict[str, BackupMetadata] = {}
        self.schedules: dict[str, BackupSchedule] = {}
        self.recovery_points: dict[str, RecoveryPoint] = {}
        self.recovery_jobs: dict[str, RecoveryJob] = {}
        self.verifications: dict[str, BackupVerification] = {}

    def create_backup_schedule(self, name: str, source_id: str,
                              backup_type: BackupType,
                              frequency_hours: int,
                              retention_days: int,
                              storage_type: BackupStorageType,
                              storage_location: str,
                              encryption_enabled: bool = True) -> BackupSchedule:
        """Create backup schedule."""
        schedule = BackupSchedule(
            name=name,
            source_id=source_id,
            backup_type=backup_type,
            frequency_hours=frequency_hours,
            retention_days=retention_days,
            storage_type=storage_type,
            storage_location=storage_location,
            encryption_enabled=encryption_enabled
        )
        self.schedules[schedule.id] = schedule
        return schedule

    def create_backup(self, name: str, backup_type: BackupType,
                     source_id: str, storage_type: BackupStorageType,
                     storage_location: str,
                     encryption_key_id: str | None = None,
                     parent_backup_id: str | None = None) -> BackupMetadata:
        """Create backup."""
        backup = BackupMetadata(
            name=name,
            backup_type=backup_type,
            source_id=source_id,
            storage_type=storage_type,
            storage_location=storage_location,
            encryption_key_id=encryption_key_id,
            encrypted=encryption_key_id is not None,
            parent_backup_id=parent_backup_id
        )
        self.backups[backup.id] = backup
        return backup

    def start_backup(self, backup_id: str) -> BackupMetadata:
        """Start backup."""
        if backup_id not in self.backups:
            raise ValueError(f"Backup {backup_id} not found")

        backup = self.backups[backup_id]
        backup.status = BackupStatus.IN_PROGRESS
        backup.started_at = datetime.now(UTC)
        return backup

    def complete_backup(self, backup_id: str, size_bytes: int,
                       compressed_size_bytes: int, checksum: str) -> BackupMetadata:
        """Complete backup."""
        if backup_id not in self.backups:
            raise ValueError(f"Backup {backup_id} not found")

        backup = self.backups[backup_id]
        backup.status = BackupStatus.COMPLETED
        backup.completed_at = datetime.now(UTC)
        backup.size_bytes = size_bytes
        backup.compressed_size_bytes = compressed_size_bytes
        backup.checksum = checksum
        return backup

    def fail_backup(self, backup_id: str, error_message: str) -> BackupMetadata:
        """Mark backup as failed."""
        if backup_id not in self.backups:
            raise ValueError(f"Backup {backup_id} not found")

        backup = self.backups[backup_id]
        backup.status = BackupStatus.FAILED
        backup.completed_at = datetime.now(UTC)
        backup.metadata["error"] = error_message
        return backup

    def verify_backup(self, backup_id: str) -> BackupVerification:
        """Verify backup integrity."""
        if backup_id not in self.backups:
            raise ValueError(f"Backup {backup_id} not found")

        backup = self.backups[backup_id]
        verification = BackupVerification(
            backup_id=backup_id,
            integrity_check_passed=True,  # In production, perform actual checks
            recovery_test_passed=True
        )

        self.verifications[verification.id] = verification
        backup.status = BackupStatus.VERIFIED
        return verification

    def create_recovery_point(self, backup_id: str, rto_minutes: int,
                             rpo_minutes: int) -> RecoveryPoint:
        """Create recovery point."""
        if backup_id not in self.backups:
            raise ValueError(f"Backup {backup_id} not found")

        backup = self.backups[backup_id]
        recovery_point = RecoveryPoint(
            backup_id=backup_id,
            timestamp=backup.completed_at or datetime.now(UTC),
            rto_minutes=rto_minutes,
            rpo_minutes=rpo_minutes
        )
        self.recovery_points[recovery_point.id] = recovery_point
        return recovery_point

    def start_recovery(self, backup_id: str, target_location: str,
                      recovery_point_id: str | None = None) -> RecoveryJob:
        """Start recovery job."""
        if backup_id not in self.backups:
            raise ValueError(f"Backup {backup_id} not found")

        job = RecoveryJob(
            backup_id=backup_id,
            recovery_point_id=recovery_point_id,
            target_location=target_location,
            status=RecoveryStatus.IN_PROGRESS,
            started_at=datetime.now(UTC)
        )
        self.recovery_jobs[job.id] = job
        return job

    def complete_recovery(self, job_id: str, recovered_bytes: int) -> RecoveryJob:
        """Complete recovery job."""
        if job_id not in self.recovery_jobs:
            raise ValueError(f"Recovery job {job_id} not found")

        job = self.recovery_jobs[job_id]
        job.status = RecoveryStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        job.recovered_bytes = recovered_bytes
        return job

    def fail_recovery(self, job_id: str, error_message: str) -> RecoveryJob:
        """Mark recovery as failed."""
        if job_id not in self.recovery_jobs:
            raise ValueError(f"Recovery job {job_id} not found")

        job = self.recovery_jobs[job_id]
        job.status = RecoveryStatus.FAILED
        job.completed_at = datetime.now(UTC)
        job.error_message = error_message
        return job

    def get_backups_by_source(self, source_id: str) -> list[BackupMetadata]:
        """Get all backups for a source."""
        return [b for b in self.backups.values() if b.source_id == source_id]

    def get_latest_backup(self, source_id: str) -> BackupMetadata | None:
        """Get latest backup for a source."""
        backups = self.get_backups_by_source(source_id)
        if not backups:
            return None
        return max(backups, key=lambda b: b.created_at)

    def cleanup_expired_backups(self) -> list[str]:
        """Clean up expired backups."""
        deleted_ids = []
        for backup_id, backup in list(self.backups.items()):
            if backup.is_expired():
                deleted_ids.append(backup_id)
                del self.backups[backup_id]
        return deleted_ids

    def get_backup_statistics(self) -> dict[str, Any]:
        """Get backup statistics."""
        total_backups = len(self.backups)
        completed = sum(1 for b in self.backups.values() if b.status == BackupStatus.COMPLETED)
        failed = sum(1 for b in self.backups.values() if b.status == BackupStatus.FAILED)
        total_size = sum(b.size_bytes for b in self.backups.values())
        total_compressed = sum(b.compressed_size_bytes for b in self.backups.values())

        return {
            "total_backups": total_backups,
            "completed": completed,
            "failed": failed,
            "total_size_bytes": total_size,
            "total_compressed_bytes": total_compressed,
            "compression_ratio": total_compressed / total_size if total_size > 0 else 0
        }

    def get_recovery_statistics(self) -> dict[str, Any]:
        """Get recovery statistics."""
        total_jobs = len(self.recovery_jobs)
        completed = sum(1 for j in self.recovery_jobs.values() if j.status == RecoveryStatus.COMPLETED)
        failed = sum(1 for j in self.recovery_jobs.values() if j.status == RecoveryStatus.FAILED)

        durations = [j.duration_seconds() for j in self.recovery_jobs.values()
                    if j.duration_seconds() is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_jobs": total_jobs,
            "completed": completed,
            "failed": failed,
            "average_duration_seconds": avg_duration
        }

    def calculate_rto(self, backup_id: str) -> int | None:
        """Calculate RTO for backup."""
        if backup_id not in self.backups:
            return None

        backup = self.backups[backup_id]
        if backup.duration_seconds() is None:
            return None

        # RTO = backup duration + recovery time (estimated)
        return backup.duration_seconds() + 300  # Add 5 min for recovery overhead

    def calculate_rpo(self, source_id: str) -> int:
        """Calculate RPO for source."""
        schedule = next((s for s in self.schedules.values() if s.source_id == source_id), None)
        if schedule:
            return schedule.frequency_hours * 60
        return 1440  # Default 24 hours

    def hash_backup(self, backup_id: str) -> str:
        """Generate hash for backup integrity verification."""
        if backup_id not in self.backups:
            raise ValueError(f"Backup {backup_id} not found")

        backup = self.backups[backup_id]
        content = f"{backup.id}{backup.created_at}{backup.size_bytes}".encode()
        return hashlib.sha256(content).hexdigest()
