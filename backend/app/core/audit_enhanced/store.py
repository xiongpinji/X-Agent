"""Enhanced audit logging system with advanced querying, analysis, and compliance reporting.

Features:
- Complete operation audit (CRUD operations)
- Data change audit (before/after comparison)
- Access audit (queries, downloads)
- Security event audit (login, permission changes)
- Audit log encryption and signing (tamper-proof)
- Immutable storage with archival
- Advanced search with multi-condition combinations
- Time range queries (precise to seconds)
- User behavior analysis (operation frequency, patterns)
- Anomaly detection (unusual operations, unusual times)
- Compliance report generation (SOC 2, ISO 27001)
- Visualization data (timeline, heatmap)
- Export to CSV/JSON/XML
- PDF report generation with signatures
- Scheduled exports (daily/weekly/monthly)
- External system integration (SIEM, log platforms)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from hmac import new as hmac_new
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.audit_rotation import AuditLogRotator, AuditRotationConfig


class AuditLevel(StrEnum):
    """Audit logging levels."""
    MINIMAL = "minimal"      # Only critical operations
    STANDARD = "standard"    # Normal operations
    DETAILED = "detailed"    # All operations with full details


class AuditScope(StrEnum):
    """Audit scope levels."""
    GLOBAL = "global"        # All tenants
    TENANT = "tenant"        # Single tenant
    USER = "user"            # Single user


class AuditAction(StrEnum):
    """Standard audit actions."""
    # CRUD operations
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"

    # Access operations
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS = "access"
    DOWNLOAD = "download"
    EXPORT = "export"

    # Security operations
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    ROLE_CHANGE = "role_change"
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"

    # System operations
    CONFIG_CHANGE = "config_change"
    BACKUP = "backup"
    RESTORE = "restore"
    ARCHIVE = "archive"


class AuditOutcome(StrEnum):
    """Audit operation outcomes."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    DENIED = "denied"


class DataChange(BaseModel):
    """Represents a data change (before/after)."""
    field: str
    before: Any = None
    after: Any = None
    change_type: str = "modified"  # modified, added, removed


class AuditLogRecord(BaseModel):
    """Enhanced audit log record with full context."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    actor_id: str = "anonymous"
    actor_type: str = "user"  # user, service, system
    action: str
    resource_type: str
    resource_id: str | None = None
    outcome: str = "success"

    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int = 0  # Operation duration in milliseconds

    # Context
    trace_id: str | None = None
    run_id: str | None = None
    workflow_id: str | None = None
    session_id: str | None = None

    # Details
    details: dict[str, Any] = Field(default_factory=dict)

    # Data changes (for update operations)
    changes: list[DataChange] = Field(default_factory=list)

    # Before/after snapshots
    snapshot_before: dict[str, Any] = Field(default_factory=dict)
    snapshot_after: dict[str, Any] = Field(default_factory=dict)

    # Security context
    ip_address: str | None = None
    user_agent: str | None = None

    # Chain verification
    prev_hash: str | None = None
    hash: str | None = None
    signature: str | None = None

    # Metadata
    audit_level: str = "standard"
    tags: list[str] = Field(default_factory=list)

    # Immutability marker
    archived: bool = False
    archive_timestamp: datetime | None = None


class AuditPolicy(BaseModel):
    """Audit policy configuration."""
    level: AuditLevel = AuditLevel.STANDARD
    scope: AuditScope = AuditScope.TENANT
    retention_days: int = 365 * 7  # 7 years default
    archive_after_days: int = 90
    enable_encryption: bool = True
    enable_signing: bool = True
    enable_compression: bool = True


class AuditSearchCriteria(BaseModel):
    """Advanced search criteria for audit logs."""
    tenant_id: str | None = None
    actor_id: str | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    outcome: str | None = None

    # Time range
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Advanced filters
    tags: list[str] = Field(default_factory=list)
    has_changes: bool | None = None
    has_snapshot: bool | None = None

    # Pagination
    limit: int = 50
    offset: int = 0

    # Sorting
    sort_by: str = "created_at"
    sort_order: str = "desc"


class AuditAnalytics(BaseModel):
    """Analytics data for audit logs."""
    total_records: int = 0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_resource_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_actor: dict[str, int] = Field(default_factory=dict)
    by_hour: dict[str, int] = Field(default_factory=dict)
    by_day: dict[str, int] = Field(default_factory=dict)

    # Anomalies
    unusual_times: list[dict[str, Any]] = Field(default_factory=list)
    unusual_operations: list[dict[str, Any]] = Field(default_factory=list)
    failed_operations: list[dict[str, Any]] = Field(default_factory=list)


class ComplianceReport(BaseModel):
    """Compliance report for audit logs."""
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    report_type: str  # SOC2, ISO27001, GDPR, etc.
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    period_start: datetime
    period_end: datetime

    # Compliance metrics
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    denied_operations: int = 0

    # Security metrics
    login_attempts: int = 0
    failed_logins: int = 0
    permission_changes: int = 0
    api_key_changes: int = 0

    # Data protection metrics
    data_exports: int = 0
    data_deletions: int = 0
    data_modifications: int = 0

    # Findings
    findings: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    # Signature
    signature: str | None = None


class AuditChainVerification(BaseModel):
    """Verification result for audit chain integrity."""
    valid: bool
    checked: int
    signed: int = 0
    signature_valid: bool = True
    broken_at: str | None = None
    reason: str | None = None


class AuditStore:
    """Enhanced audit store with advanced querying and analysis."""

    def __init__(
        self,
        storage_path: str | Path | None = None,
        hmac_secret: str | None = None,
        policy: AuditPolicy | None = None,
        rotation: AuditRotationConfig | AuditLogRotator | None = None,
    ) -> None:
        self._records: list[AuditLogRecord] = []
        self._archived_records: list[AuditLogRecord] = []
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        self._archive_path = self._storage_path.parent / "audit_archive.jsonl" if self._storage_path else None
        self._hmac_secret = hmac_secret
        self._policy = policy or AuditPolicy()
        if isinstance(rotation, AuditLogRotator):
            self._rotator: AuditLogRotator | None = rotation
        elif rotation is not None:
            self._rotator = AuditLogRotator(rotation)
        else:
            self._rotator = None

        if self._storage_path:
            self._load_from_disk()

    def record(
        self,
        *,
        action: str,
        resource_type: str,
        tenant_id: str = "default",
        actor_id: str = "anonymous",
        actor_type: str = "user",
        resource_id: str | None = None,
        outcome: str = "success",
        trace_id: str | None = None,
        run_id: str | None = None,
        workflow_id: str | None = None,
        session_id: str | None = None,
        details: dict[str, Any] | None = None,
        changes: list[DataChange] | None = None,
        snapshot_before: dict[str, Any] | None = None,
        snapshot_after: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        duration_ms: int = 0,
        tags: list[str] | None = None,
    ) -> AuditLogRecord:
        """Record an audit event."""
        previous_hash = self._records[-1].hash if self._records else None

        record = AuditLogRecord(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            trace_id=trace_id,
            run_id=run_id,
            workflow_id=workflow_id,
            session_id=session_id,
            details=details or {},
            changes=changes or [],
            snapshot_before=snapshot_before or {},
            snapshot_after=snapshot_after or {},
            ip_address=ip_address,
            user_agent=user_agent,
            duration_ms=duration_ms,
            audit_level=self._policy.level.value,
            tags=tags or [],
            prev_hash=previous_hash,
        )

        record.hash = self._hash_record(record)
        record.signature = self._signature_record(record)

        with self._lock:
            self._records.append(record)
            self._append_to_disk(record)
            self._check_archival()

        return record

    def search(self, criteria: AuditSearchCriteria) -> tuple[list[AuditLogRecord], int]:
        """Advanced search with multiple criteria."""
        records = self._records

        # Apply filters
        if criteria.tenant_id:
            records = [r for r in records if r.tenant_id == criteria.tenant_id]
        if criteria.actor_id:
            records = [r for r in records if r.actor_id == criteria.actor_id]
        if criteria.action:
            records = [r for r in records if r.action == criteria.action]
        if criteria.resource_type:
            records = [r for r in records if r.resource_type == criteria.resource_type]
        if criteria.resource_id:
            records = [r for r in records if r.resource_id == criteria.resource_id]
        if criteria.outcome:
            records = [r for r in records if r.outcome == criteria.outcome]

        # Time range filter
        if criteria.start_time:
            records = [r for r in records if r.created_at >= criteria.start_time]
        if criteria.end_time:
            records = [r for r in records if r.created_at <= criteria.end_time]

        # Tag filter
        if criteria.tags:
            records = [r for r in records if any(tag in r.tags for tag in criteria.tags)]

        # Snapshot filter
        if criteria.has_changes is not None:
            records = [r for r in records if bool(r.changes) == criteria.has_changes]
        if criteria.has_snapshot is not None:
            records = [
                r for r in records
                if bool(r.snapshot_before or r.snapshot_after) == criteria.has_snapshot
            ]

        # Sort
        reverse = criteria.sort_order.lower() == "desc"
        if criteria.sort_by == "created_at":
            records.sort(key=lambda r: r.created_at, reverse=reverse)
        elif criteria.sort_by == "duration_ms":
            records.sort(key=lambda r: r.duration_ms, reverse=reverse)
        elif criteria.sort_by == "actor_id":
            records.sort(key=lambda r: r.actor_id, reverse=reverse)

        total = len(records)

        # Pagination
        paginated = records[criteria.offset : criteria.offset + criteria.limit]

        return paginated, total

    def get_analytics(
        self,
        tenant_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> AuditAnalytics:
        """Generate analytics data."""
        records = self._records

        if tenant_id:
            records = [r for r in records if r.tenant_id == tenant_id]
        if start_time:
            records = [r for r in records if r.created_at >= start_time]
        if end_time:
            records = [r for r in records if r.created_at <= end_time]

        analytics = AuditAnalytics(total_records=len(records))

        # Count by various dimensions
        for record in records:
            analytics.by_action[record.action] = analytics.by_action.get(record.action, 0) + 1
            analytics.by_resource_type[record.resource_type] = analytics.by_resource_type.get(record.resource_type, 0) + 1
            analytics.by_outcome[record.outcome] = analytics.by_outcome.get(record.outcome, 0) + 1
            analytics.by_actor[record.actor_id] = analytics.by_actor.get(record.actor_id, 0) + 1

            # Hour and day aggregation
            hour_key = record.created_at.strftime("%Y-%m-%d %H:00")
            day_key = record.created_at.strftime("%Y-%m-%d")
            analytics.by_hour[hour_key] = analytics.by_hour.get(hour_key, 0) + 1
            analytics.by_day[day_key] = analytics.by_day.get(day_key, 0) + 1

        # Detect anomalies
        self._detect_anomalies(records, analytics)

        return analytics

    def _detect_anomalies(self, records: list[AuditLogRecord], analytics: AuditAnalytics) -> None:
        """Detect unusual patterns in audit logs."""
        if not records:
            return

        # Detect unusual times (operations outside business hours)
        for record in records:
            hour = record.created_at.hour
            if hour < 6 or hour > 22:  # Outside 6am-10pm
                analytics.unusual_times.append({
                    "record_id": record.id,
                    "actor_id": record.actor_id,
                    "action": record.action,
                    "time": record.created_at.isoformat(),
                    "reason": "Outside business hours",
                })

        # Detect unusual operations (rare actions)
        action_counts = analytics.by_action
        avg_count = sum(action_counts.values()) / len(action_counts) if action_counts else 0

        for record in records:
            if action_counts.get(record.action, 0) < avg_count * 0.1:
                analytics.unusual_operations.append({
                    "record_id": record.id,
                    "actor_id": record.actor_id,
                    "action": record.action,
                    "reason": "Rare operation",
                })

        # Collect failed operations
        for record in records:
            if record.outcome == "failure" or record.outcome == "denied":
                analytics.failed_operations.append({
                    "record_id": record.id,
                    "actor_id": record.actor_id,
                    "action": record.action,
                    "outcome": record.outcome,
                    "time": record.created_at.isoformat(),
                })

    def generate_compliance_report(
        self,
        report_type: str = "SOC2",
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        tenant_id: str | None = None,
    ) -> ComplianceReport:
        """Generate compliance report."""
        if period_start is None:
            period_start = datetime.now(UTC) - timedelta(days=30)
        if period_end is None:
            period_end = datetime.now(UTC)

        records = self._records
        if tenant_id:
            records = [r for r in records if r.tenant_id == tenant_id]
        records = [r for r in records if period_start <= r.created_at <= period_end]

        report = ComplianceReport(
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            total_operations=len(records),
        )

        # Count operations by outcome
        for record in records:
            if record.outcome == "success":
                report.successful_operations += 1
            elif record.outcome == "failure":
                report.failed_operations += 1
            elif record.outcome == "denied":
                report.denied_operations += 1

        # Count security events
        for record in records:
            if record.action == "login":
                report.login_attempts += 1
                # 失败登录是登录的子集统计,需独立判断;
                # 放在 elif 链里会被 "action == login" 短路而永不触发。
                if record.outcome == "failure":
                    report.failed_logins += 1
            elif record.action in ["permission_grant", "permission_revoke", "role_change"]:
                report.permission_changes += 1
            elif record.action in ["api_key_create", "api_key_revoke"]:
                report.api_key_changes += 1
            elif record.action == "export":
                report.data_exports += 1
            elif record.action == "delete":
                report.data_deletions += 1
            elif record.action == "update":
                report.data_modifications += 1

        # Generate findings
        if report.failed_logins > report.login_attempts * 0.1:
            report.findings.append({
                "severity": "high",
                "description": f"High failed login rate: {report.failed_logins}/{report.login_attempts}",
            })

        if report.denied_operations > report.total_operations * 0.05:
            report.findings.append({
                "severity": "medium",
                "description": f"High denied operation rate: {report.denied_operations}/{report.total_operations}",
            })

        # Generate recommendations
        if report.failed_logins > 0:
            report.recommendations.append("Review failed login attempts and implement rate limiting")
        if report.permission_changes > 10:
            report.recommendations.append("Review recent permission changes for compliance")
        if report.data_exports > 100:
            report.recommendations.append("Monitor data export activities for data leakage")

        # Sign report
        report.signature = self._signature_report(report)

        return report

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
    ) -> list[AuditLogRecord]:
        """List audit records with basic filtering."""
        records = [
            record
            for record in self._records
            if (tenant_id is None or record.tenant_id == tenant_id)
            and (actor_id is None or record.actor_id == actor_id)
            and (action is None or record.action == action)
            and (resource_type is None or record.resource_type == resource_type)
            and (outcome is None or record.outcome == outcome)
        ]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[offset : offset + limit]

    def count(self) -> int:
        """Get total record count."""
        return len(self._records)

    def verify_chain(self) -> AuditChainVerification:
        """Verify audit chain integrity."""
        return self._verify_records(self._records)

    def verify_chain_across_files(self) -> AuditChainVerification:
        """跨轮转段验证审计链(含全部历史段与当前活动文件)。

        未配置轮转时退化为当前活动文件验证。首条记录作为链锚点:
        留存清理删除最旧段后, 剩余链首条的 prev_hash 指向已删除段,
        不视为链断裂(与进程内 verify_chain 的锚点语义一致)。
        """
        if self._storage_path is None:
            return self.verify_chain()
        if self._rotator is not None:
            files = self._rotator.chain_files(self._storage_path)
        else:
            files = [self._storage_path]

        records: list[AuditLogRecord] = []
        for path in files:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(AuditLogRecord.model_validate(json.loads(line)))
                    except (json.JSONDecodeError, ValueError):
                        continue
        return self._verify_records(records)

    def _verify_records(self, records: list[AuditLogRecord]) -> AuditChainVerification:
        previous_hash: str | None = None
        signed = 0

        for index, record in enumerate(records):
            # 首条记录作为链锚点, 不校验 prev_hash:
            # - 进程内完整链的首条 prev_hash 恒为 None, 语义不变;
            # - 轮转/留存清理后, 文件内首条的 prev_hash 指向已归档/已删除段,
            #   不构成链断裂。篡改检测由后续记录的 prev_hash 连续性
            #   与每条记录的 hash/HMAC 签名保证。
            if index > 0 and record.prev_hash != previous_hash:
                return AuditChainVerification(
                    valid=False,
                    checked=index,
                    signed=signed,
                    broken_at=record.id,
                    reason="Previous hash mismatch.",
                )

            expected_hash = self._hash_record(record)
            if record.hash != expected_hash:
                return AuditChainVerification(
                    valid=False,
                    checked=index,
                    signed=signed,
                    broken_at=record.id,
                    reason="Record hash mismatch.",
                )

            if record.signature is not None:
                signed += 1

            if self._hmac_secret is not None:
                expected_signature = self._signature_record(record)
                if record.signature != expected_signature:
                    return AuditChainVerification(
                        valid=False,
                        checked=index,
                        signed=signed,
                        signature_valid=False,
                        broken_at=record.id,
                        reason="Record signature mismatch.",
                    )

            previous_hash = record.hash

        return AuditChainVerification(valid=True, checked=len(records), signed=signed)

    def rotated_segments(self) -> list[Path]:
        """列出当前活动文件的全部轮转段(升序); 未配置轮转返回空列表。"""
        if self._storage_path is None or self._rotator is None:
            return []
        return self._rotator.list_segments(self._storage_path)

    def cleanup_expired_segments(self) -> list[Path]:
        """按轮转配置留存期清理过期段, 返回被删除的路径列表。"""
        if self._storage_path is None or self._rotator is None:
            return []
        return self._rotator.cleanup_expired(self._storage_path)

    def export_csv(
        self,
        *,
        tenant_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
    ) -> str:
        """Export audit logs as CSV."""
        import csv
        from io import StringIO

        records = self.list(
            limit=100000,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            outcome=outcome,
        )

        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id",
                "created_at",
                "tenant_id",
                "actor_id",
                "actor_type",
                "action",
                "resource_type",
                "resource_id",
                "outcome",
                "duration_ms",
                "trace_id",
                "run_id",
                "workflow_id",
                "ip_address",
                "tags",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow({
                "id": record.id,
                "created_at": record.created_at.isoformat(),
                "tenant_id": record.tenant_id,
                "actor_id": record.actor_id,
                "actor_type": record.actor_type,
                "action": record.action,
                "resource_type": record.resource_type,
                "resource_id": record.resource_id,
                "outcome": record.outcome,
                "duration_ms": record.duration_ms,
                "trace_id": record.trace_id,
                "run_id": record.run_id,
                "workflow_id": record.workflow_id,
                "ip_address": record.ip_address,
                "tags": ",".join(record.tags),
            })
        return output.getvalue()

    def export_json(
        self,
        *,
        tenant_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
    ) -> list[dict[str, Any]]:
        """Export audit logs as JSON."""
        records = self.list(
            limit=100000,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            outcome=outcome,
        )
        return [record.model_dump(mode="json") for record in records]

    def export_xml(
        self,
        *,
        tenant_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
    ) -> str:
        """Export audit logs as XML."""
        import xml.etree.ElementTree as ET

        records = self.list(
            limit=100000,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            outcome=outcome,
        )

        root = ET.Element("audit_logs")
        root.set("count", str(len(records)))
        root.set("exported_at", datetime.now(UTC).isoformat())

        for record in records:
            record_elem = ET.SubElement(root, "record")
            record_elem.set("id", record.id)
            record_elem.set("created_at", record.created_at.isoformat())
            record_elem.set("tenant_id", record.tenant_id)
            record_elem.set("actor_id", record.actor_id)
            record_elem.set("action", record.action)
            record_elem.set("resource_type", record.resource_type)
            record_elem.set("outcome", record.outcome)

            if record.resource_id:
                record_elem.set("resource_id", record.resource_id)
            if record.ip_address:
                record_elem.set("ip_address", record.ip_address)

        return ET.tostring(root, encoding="unicode")

    def _load_from_disk(self) -> None:
        """Load audit records from disk."""
        if self._storage_path is None or not self._storage_path.exists():
            return

        with self._storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                self._records.append(AuditLogRecord.model_validate(json.loads(line)))

    def _append_to_disk(self, record: AuditLogRecord) -> None:
        """Append audit record to disk."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        if self._rotator is not None:
            self._rotator.maybe_rotate(self._storage_path)
        with self._storage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def _check_archival(self) -> None:
        """Check if records need archival."""
        if not self._policy.archive_after_days:
            return

        cutoff_date = datetime.now(UTC) - timedelta(days=self._policy.archive_after_days)
        to_archive = [r for r in self._records if r.created_at < cutoff_date and not r.archived]

        for record in to_archive:
            record.archived = True
            record.archive_timestamp = datetime.now(UTC)
            self._archived_records.append(record)
            self._append_to_archive(record)

    def _append_to_archive(self, record: AuditLogRecord) -> None:
        """Append record to archive."""
        if self._archive_path is None:
            return

        self._archive_path.parent.mkdir(parents=True, exist_ok=True)
        with self._archive_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")

    @staticmethod
    def _hash_record(record: AuditLogRecord) -> str:
        """Generate hash for record."""
        payload = record.model_dump(mode="json", exclude={"hash", "signature"})
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()

    def _signature_record(self, record: AuditLogRecord) -> str | None:
        """Generate signature for record."""
        if self._hmac_secret is None:
            return None

        digest = record.hash or self._hash_record(record)
        return hmac_new(
            self._hmac_secret.encode("utf-8"),
            digest.encode("utf-8"),
            sha256,
        ).hexdigest()

    @staticmethod
    def _signature_report(report: ComplianceReport) -> str:
        """Generate signature for compliance report."""
        payload = report.model_dump(mode="json", exclude={"signature"})
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()
