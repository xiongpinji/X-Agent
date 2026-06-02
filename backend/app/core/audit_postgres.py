"""PostgreSQL-based audit log storage with advanced querying and archival support."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Boolean,
    Text,
    JSON,
    Index,
    create_engine,
    select,
    and_,
    or_,
)
from sqlalchemy.orm import declarative_base, Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.audit_enhanced import (
    AuditLogRecord,
    AuditSearchCriteria,
    AuditAnalytics,
    ComplianceReport,
)

Base = declarative_base()


class AuditLogTable(Base):
    """SQLAlchemy model for audit logs."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    actor_id = Column(String(255), nullable=False, index=True)
    actor_type = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(String(255), nullable=True, index=True)
    outcome = Column(String(50), nullable=False, index=True)

    # Timing
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_ms = Column(Integer, default=0)

    # Context
    trace_id = Column(String(255), nullable=True, index=True)
    run_id = Column(String(255), nullable=True, index=True)
    workflow_id = Column(String(255), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)

    # Details
    details = Column(JSON, default={})
    changes = Column(JSON, default=[])
    snapshot_before = Column(JSON, default={})
    snapshot_after = Column(JSON, default={})

    # Security context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Chain verification
    prev_hash = Column(String(64), nullable=True)
    hash = Column(String(64), nullable=False, index=True)
    signature = Column(String(128), nullable=True)

    # Metadata
    audit_level = Column(String(50), default="standard")
    tags = Column(JSON, default=[])

    # Immutability
    archived = Column(Boolean, default=False, index=True)
    archive_timestamp = Column(DateTime(timezone=True), nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_tenant_created", "tenant_id", "created_at"),
        Index("idx_actor_created", "actor_id", "created_at"),
        Index("idx_action_outcome", "action", "outcome"),
        Index("idx_resource_type_id", "resource_type", "resource_id"),
        Index("idx_trace_run_workflow", "trace_id", "run_id", "workflow_id"),
    )


class AuditLogArchiveTable(Base):
    """SQLAlchemy model for archived audit logs."""

    __tablename__ = "audit_logs_archive"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    actor_id = Column(String(255), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(String(255), nullable=True)
    outcome = Column(String(50), nullable=False)

    # Timing
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    archived_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Full record
    record_data = Column(JSON, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_archive_tenant_created", "tenant_id", "created_at"),
        Index("idx_archive_archived_at", "archived_at"),
    )


class AuditLogSignatureTable(Base):
    """SQLAlchemy model for audit log signatures."""

    __tablename__ = "audit_log_signatures"

    id = Column(String(36), primary_key=True)
    audit_log_id = Column(String(36), nullable=False, index=True)
    signature = Column(String(128), nullable=False)
    signed_at = Column(DateTime(timezone=True), nullable=False)
    signer_id = Column(String(255), nullable=True)
    certificate_id = Column(String(255), nullable=True)


class PostgresAuditStore:
    """PostgreSQL-based audit store with advanced querying."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(
            database_url,
            poolclass=NullPool,
            echo=False,
        )
        self._session_factory = sessionmaker(bind=self._engine)
        self._create_tables()

    def _create_tables(self) -> None:
        """Create database tables."""
        Base.metadata.create_all(self._engine)

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
        changes: list[dict[str, Any]] | None = None,
        snapshot_before: dict[str, Any] | None = None,
        snapshot_after: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        duration_ms: int = 0,
        tags: list[str] | None = None,
    ) -> AuditLogRecord:
        """Record an audit event."""
        session = self._session_factory()

        try:
            # Get previous hash
            prev_record = session.query(AuditLogTable).order_by(
                AuditLogTable.created_at.desc()
            ).first()
            prev_hash = prev_record.hash if prev_record else None

            # Create record
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
                tags=tags or [],
                prev_hash=prev_hash,
            )

            record.hash = self._hash_record(record)
            record.signature = self._signature_record(record)

            # Insert into database
            db_record = AuditLogTable(
                id=record.id,
                tenant_id=record.tenant_id,
                actor_id=record.actor_id,
                actor_type=record.actor_type,
                action=record.action,
                resource_type=record.resource_type,
                resource_id=record.resource_id,
                outcome=record.outcome,
                created_at=record.created_at,
                duration_ms=record.duration_ms,
                trace_id=record.trace_id,
                run_id=record.run_id,
                workflow_id=record.workflow_id,
                session_id=record.session_id,
                details=record.details,
                changes=[c.model_dump() for c in record.changes],
                snapshot_before=record.snapshot_before,
                snapshot_after=record.snapshot_after,
                ip_address=record.ip_address,
                user_agent=record.user_agent,
                prev_hash=record.prev_hash,
                hash=record.hash,
                signature=record.signature,
                audit_level=record.audit_level,
                tags=record.tags,
            )

            session.add(db_record)
            session.commit()

            return record

        finally:
            session.close()

    def search(self, criteria: AuditSearchCriteria) -> tuple[list[AuditLogRecord], int]:
        """Advanced search with multiple criteria."""
        session = self._session_factory()

        try:
            query = session.query(AuditLogTable)

            # Apply filters
            if criteria.tenant_id:
                query = query.filter(AuditLogTable.tenant_id == criteria.tenant_id)
            if criteria.actor_id:
                query = query.filter(AuditLogTable.actor_id == criteria.actor_id)
            if criteria.action:
                query = query.filter(AuditLogTable.action == criteria.action)
            if criteria.resource_type:
                query = query.filter(AuditLogTable.resource_type == criteria.resource_type)
            if criteria.resource_id:
                query = query.filter(AuditLogTable.resource_id == criteria.resource_id)
            if criteria.outcome:
                query = query.filter(AuditLogTable.outcome == criteria.outcome)

            # Time range filter
            if criteria.start_time:
                query = query.filter(AuditLogTable.created_at >= criteria.start_time)
            if criteria.end_time:
                query = query.filter(AuditLogTable.created_at <= criteria.end_time)

            # Get total count
            total = query.count()

            # Sort
            if criteria.sort_by == "created_at":
                if criteria.sort_order.lower() == "desc":
                    query = query.order_by(AuditLogTable.created_at.desc())
                else:
                    query = query.order_by(AuditLogTable.created_at.asc())
            elif criteria.sort_by == "duration_ms":
                if criteria.sort_order.lower() == "desc":
                    query = query.order_by(AuditLogTable.duration_ms.desc())
                else:
                    query = query.order_by(AuditLogTable.duration_ms.asc())

            # Pagination
            query = query.offset(criteria.offset).limit(criteria.limit)

            # Convert to records
            records = []
            for row in query.all():
                record = AuditLogRecord(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    actor_id=row.actor_id,
                    actor_type=row.actor_type,
                    action=row.action,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    outcome=row.outcome,
                    created_at=row.created_at,
                    duration_ms=row.duration_ms,
                    trace_id=row.trace_id,
                    run_id=row.run_id,
                    workflow_id=row.workflow_id,
                    session_id=row.session_id,
                    details=row.details,
                    snapshot_before=row.snapshot_before,
                    snapshot_after=row.snapshot_after,
                    ip_address=row.ip_address,
                    user_agent=row.user_agent,
                    prev_hash=row.prev_hash,
                    hash=row.hash,
                    signature=row.signature,
                    audit_level=row.audit_level,
                    tags=row.tags,
                    archived=row.archived,
                    archive_timestamp=row.archive_timestamp,
                )
                records.append(record)

            return records, total

        finally:
            session.close()

    def get_analytics(
        self,
        tenant_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> AuditAnalytics:
        """Generate analytics data."""
        session = self._session_factory()

        try:
            query = session.query(AuditLogTable)

            if tenant_id:
                query = query.filter(AuditLogTable.tenant_id == tenant_id)
            if start_time:
                query = query.filter(AuditLogTable.created_at >= start_time)
            if end_time:
                query = query.filter(AuditLogTable.created_at <= end_time)

            records = query.all()
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

            return analytics

        finally:
            session.close()

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
        session = self._session_factory()

        try:
            query = session.query(AuditLogTable)

            if tenant_id:
                query = query.filter(AuditLogTable.tenant_id == tenant_id)
            if actor_id:
                query = query.filter(AuditLogTable.actor_id == actor_id)
            if action:
                query = query.filter(AuditLogTable.action == action)
            if resource_type:
                query = query.filter(AuditLogTable.resource_type == resource_type)
            if outcome:
                query = query.filter(AuditLogTable.outcome == outcome)

            query = query.order_by(AuditLogTable.created_at.desc())
            query = query.offset(offset).limit(limit)

            records = []
            for row in query.all():
                record = AuditLogRecord(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    actor_id=row.actor_id,
                    actor_type=row.actor_type,
                    action=row.action,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    outcome=row.outcome,
                    created_at=row.created_at,
                    duration_ms=row.duration_ms,
                    trace_id=row.trace_id,
                    run_id=row.run_id,
                    workflow_id=row.workflow_id,
                    session_id=row.session_id,
                    details=row.details,
                    snapshot_before=row.snapshot_before,
                    snapshot_after=row.snapshot_after,
                    ip_address=row.ip_address,
                    user_agent=row.user_agent,
                    prev_hash=row.prev_hash,
                    hash=row.hash,
                    signature=row.signature,
                    audit_level=row.audit_level,
                    tags=row.tags,
                    archived=row.archived,
                    archive_timestamp=row.archive_timestamp,
                )
                records.append(record)

            return records

        finally:
            session.close()

    def count(self) -> int:
        """Get total record count."""
        session = self._session_factory()

        try:
            return session.query(AuditLogTable).count()
        finally:
            session.close()

    def archive_old_records(self, days: int = 90) -> int:
        """Archive records older than specified days."""
        session = self._session_factory()

        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            # Get records to archive
            records_to_archive = session.query(AuditLogTable).filter(
                and_(
                    AuditLogTable.created_at < cutoff_date,
                    AuditLogTable.archived == False,
                )
            ).all()

            # Archive them
            for record in records_to_archive:
                archive_record = AuditLogArchiveTable(
                    id=record.id,
                    tenant_id=record.tenant_id,
                    actor_id=record.actor_id,
                    action=record.action,
                    resource_type=record.resource_type,
                    resource_id=record.resource_id,
                    outcome=record.outcome,
                    created_at=record.created_at,
                    archived_at=datetime.now(UTC),
                    record_data={
                        "id": record.id,
                        "tenant_id": record.tenant_id,
                        "actor_id": record.actor_id,
                        "actor_type": record.actor_type,
                        "action": record.action,
                        "resource_type": record.resource_type,
                        "resource_id": record.resource_id,
                        "outcome": record.outcome,
                        "created_at": record.created_at.isoformat(),
                        "duration_ms": record.duration_ms,
                        "trace_id": record.trace_id,
                        "run_id": record.run_id,
                        "workflow_id": record.workflow_id,
                        "session_id": record.session_id,
                        "details": record.details,
                        "snapshot_before": record.snapshot_before,
                        "snapshot_after": record.snapshot_after,
                        "ip_address": record.ip_address,
                        "user_agent": record.user_agent,
                        "hash": record.hash,
                        "signature": record.signature,
                        "tags": record.tags,
                    },
                )
                session.add(archive_record)
                record.archived = True
                record.archive_timestamp = datetime.now(UTC)

            session.commit()
            return len(records_to_archive)

        finally:
            session.close()

    @staticmethod
    def _hash_record(record: AuditLogRecord) -> str:
        """Generate hash for record."""
        from hashlib import sha256

        payload = record.model_dump(mode="json", exclude={"hash", "signature"})
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _signature_record(record: AuditLogRecord) -> str | None:
        """Generate signature for record."""
        from hashlib import sha256
        from hmac import new as hmac_new

        # In production, use actual HMAC secret from config
        hmac_secret = "default-secret"

        digest = record.hash or PostgresAuditStore._hash_record(record)
        return hmac_new(
            hmac_secret.encode("utf-8"),
            digest.encode("utf-8"),
            sha256,
        ).hexdigest()
