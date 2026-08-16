"""Durable, idempotent HMAC audit chain for commercial deployments."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import RLock

from sqlalchemy import DateTime, Index, String, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import JSON

from backend.app.core.audit import (
    AuditChainVerification,
    AuditEventConflictError,
    AuditLogRecord,
    AuditStore,
)
from backend.app.core.database_urls import normalize_sync_database_url

_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
_SQLITE_LOCK = RLock()
_POSTGRES_LOCK_ID = 732145891


class AuditSqlBase(DeclarativeBase):
    pass


class CommercialAuditEventRow(AuditSqlBase):
    __tablename__ = "commercial_audit_events"
    __table_args__ = (
        Index("idx_commercial_audit_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128))
    run_id: Mapped[str | None] = mapped_column(String(128))
    workflow_id: Mapped[str | None] = mapped_column(String(128))
    details: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)


class SqlAuditStore(AuditStore):
    def __init__(self, database_url: str, *, hmac_secret: str, create_schema: bool) -> None:
        # AuditStore's file-backend constructor loads the legacy core.config
        # settings model. The SQL backend is fully configured here and must not
        # couple production startup to that duplicate settings stack.
        self._records = []
        self._lock = RLock()
        self._last_created_at = None
        self._storage_path = None
        self._hmac_secret = hmac_secret
        self._rotator = None
        self._engine = create_engine(
            normalize_sync_database_url(database_url),
            future=True,
            pool_pre_ping=True,
        )
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)
        self._is_postgres = self._engine.dialect.name == "postgresql"
        if create_schema:
            AuditSqlBase.metadata.create_all(self._engine)

    @staticmethod
    def _content(record: AuditLogRecord) -> dict:
        return {
            "tenant_id": record.tenant_id,
            "actor_id": record.actor_id,
            "action": record.action,
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "outcome": record.outcome,
            "trace_id": record.trace_id,
            "run_id": record.run_id,
            "workflow_id": record.workflow_id,
            "details": record.details,
        }

    @staticmethod
    def _row_to_record(row: CommercialAuditEventRow) -> AuditLogRecord:
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return AuditLogRecord(
            id=row.id,
            tenant_id=row.tenant_id,
            actor_id=row.actor_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            outcome=row.outcome,
            trace_id=row.trace_id,
            run_id=row.run_id,
            workflow_id=row.workflow_id,
            details=row.details,
            created_at=created_at,
            prev_hash=row.prev_hash,
            hash=row.hash,
            signature=row.signature,
            snapshot=row.snapshot,
        )

    def record(
        self,
        *,
        action: str,
        resource_type: str,
        tenant_id: str = "default",
        actor_id: str = "anonymous",
        resource_id: str | None = None,
        outcome: str = "success",
        trace_id: str | None = None,
        run_id: str | None = None,
        workflow_id: str | None = None,
        details: dict | None = None,
        event_id: str | None = None,
    ) -> AuditLogRecord:
        if event_id is not None and not event_id.strip():
            raise ValueError("event_id must not be empty")
        event_content = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "outcome": outcome,
            "trace_id": trace_id,
            "run_id": run_id,
            "workflow_id": workflow_id,
            "details": details or {},
        }
        with _SQLITE_LOCK, self._session_factory.begin() as session:
            if self._is_postgres:
                session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _POSTGRES_LOCK_ID})
            if event_id is not None:
                existing_row = session.get(CommercialAuditEventRow, event_id)
                if existing_row is not None:
                    existing = self._row_to_record(existing_row)
                    if self._content(existing) != event_content:
                        raise AuditEventConflictError(
                            "event_id already exists with different audit content"
                        )
                    return existing

            previous_row = session.scalar(
                select(CommercialAuditEventRow)
                .order_by(
                    CommercialAuditEventRow.created_at.desc(),
                    CommercialAuditEventRow.id.desc(),
                )
                .limit(1)
            )
            created_at = datetime.now(UTC)
            if previous_row is not None:
                previous_at = previous_row.created_at
                if previous_at.tzinfo is None:
                    previous_at = previous_at.replace(tzinfo=UTC)
                if created_at <= previous_at:
                    created_at = previous_at + timedelta(microseconds=1)
            identity = {"id": event_id} if event_id is not None else {}
            record = AuditLogRecord(
                **identity,
                **event_content,
                created_at=created_at,
                prev_hash=previous_row.hash if previous_row is not None else None,
                snapshot={
                    "trace_id": trace_id,
                    "run_id": run_id,
                    "workflow_id": workflow_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "outcome": outcome,
                },
            )
            record.hash = self._hash_record(record)
            record.signature = self._signature_record(record)
            session.add(
                CommercialAuditEventRow(
                    **record.model_dump(
                        exclude={"hash", "signature"},
                    ),
                    hash=record.hash,
                    signature=record.signature,
                )
            )
            return record

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
        statement = select(CommercialAuditEventRow)
        for column, value in (
            (CommercialAuditEventRow.tenant_id, tenant_id),
            (CommercialAuditEventRow.actor_id, actor_id),
            (CommercialAuditEventRow.action, action),
            (CommercialAuditEventRow.resource_type, resource_type),
            (CommercialAuditEventRow.outcome, outcome),
        ):
            if value is not None:
                statement = statement.where(column == value)
        statement = statement.order_by(CommercialAuditEventRow.created_at.desc()).offset(offset).limit(limit)
        with self._session_factory() as session:
            return [self._row_to_record(row) for row in session.scalars(statement).all()]

    def count(self) -> int:
        with self._session_factory() as session:
            return int(session.scalar(select(func.count()).select_from(CommercialAuditEventRow)) or 0)

    def verify_chain(self) -> AuditChainVerification:
        with self._session_factory() as session:
            rows = session.scalars(
                select(CommercialAuditEventRow).order_by(
                    CommercialAuditEventRow.created_at,
                    CommercialAuditEventRow.id,
                )
            ).all()
        return self._verify_records([self._row_to_record(row) for row in rows])

    def verify_chain_across_files(self) -> AuditChainVerification:
        return self.verify_chain()
