"""Workflow persistence on SQL (Postgres in production, SQLite for tests/dev).

P1-07: moves workflow definitions, run state and schedules off JSON files
onto SQLAlchemy-managed tables. The file-backed ``WorkflowRepository`` /
``WorkflowScheduleStore`` in ``backend.app.core.workflows`` remain as the dev
fallback; this module provides drop-in SQL implementations with the SAME
public interface (they subclass the file stores, so validation and
topological ordering are shared, and every data method is overridden).

Self-contained on purpose: it defines its own ``DeclarativeBase`` so it does
not depend on ``backend.app.models`` (owned by another workstream).

Backend selection:
    XAGENT_WORKFLOW_STORE_BACKEND = db | file | auto   (default: auto)
- ``db``   : SQL store; engine creation failures raise (explicit, no silent
             fallback) so production misconfiguration is loud.
- ``file`` : legacy JSON file store (dev).
- ``auto`` : try SQL first; on failure log a WARNING and fall back to file
             (explicit degradation for local dev without a database).
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import JSON

try:  # JSONB on Postgres, plain JSON elsewhere (SQLite).
    from sqlalchemy.dialects.postgresql import JSONB

    _JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
except ImportError:  # pragma: no cover - sqlalchemy always ships the pg dialect
    _JSON_TYPE = JSON

from backend.app.core.workflows import (
    WorkflowCreateRequest,
    WorkflowDefinition,
    WorkflowNodeResult,
    WorkflowRepository,
    WorkflowRunRecord,
    WorkflowRunStatus,
    WorkflowScheduleRecord,
    WorkflowScheduleStatus,
    WorkflowScheduleStore,
    WorkflowSummary,
    WorkflowUpdateRequest,
)

logger = logging.getLogger(__name__)

WORKFLOW_STORE_BACKEND_ENV = "XAGENT_WORKFLOW_STORE_BACKEND"


class WorkflowStoreBase(DeclarativeBase):
    """Dedicated metadata for the workflow tables (kept independent from the
    shared models package so this module stays self-contained)."""


class WorkflowDefinitionRow(WorkflowStoreBase):
    __tablename__ = "workflow_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    doc: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)

    __table_args__ = (
        Index("idx_workflow_definitions_updated", "updated_at"),
    )


class WorkflowRunRow(WorkflowStoreBase):
    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, default="anonymous")
    resume_cursor: Mapped[int] = mapped_column(nullable=False, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    doc: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)

    __table_args__ = (
        Index("idx_workflow_runs_workflow_started", "workflow_id", "started_at"),
        Index("idx_workflow_runs_status", "status"),
        Index("idx_workflow_runs_tenant", "tenant_id"),
    )


class WorkflowScheduleRow(WorkflowStoreBase):
    __tablename__ = "workflow_schedules"

    schedule_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, default="anonymous")
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    cron: Mapped[str | None] = mapped_column(String(128), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    doc: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)

    __table_args__ = (
        Index("idx_workflow_schedules_due", "status", "run_at"),
        Index("idx_workflow_schedules_tenant", "tenant_id"),
    )


def _as_utc(moment: datetime | None) -> datetime | None:
    """Normalize datetimes read from the DB to tz-aware UTC.

    SQLite drops timezone info on DateTime(timezone=True); naive values would
    crash comparisons against ``datetime.now(UTC)`` in scheduling logic.
    """
    if moment is None:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


def _normalize_record_datetimes(payload: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    normalized = dict(payload)
    for field in fields:
        value = normalized.get(field)
        if isinstance(value, datetime):
            normalized[field] = _as_utc(value)
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            normalized[field] = _as_utc(parsed)
    return normalized


def create_workflow_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create a SYNC SQLAlchemy engine for the workflow stores.

    The workflow store interface is synchronous (it is called from sync code
    paths inside the executor and API), so asyncpg/aiosqlite URLs are
    normalized to their sync driver equivalents:
      postgresql+asyncpg:// -> postgresql+psycopg://
      sqlite+aiosqlite://   -> sqlite://
    """
    url = database_url
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg")
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if "+aiosqlite" in url:
        url = url.replace("+aiosqlite", "")
    engine_kwargs: dict[str, Any] = {"echo": echo, "future": True}
    if url.startswith("sqlite"):
        # Match the async DatabaseManager: contending writers wait instead of
        # failing instantly with "database is locked".
        engine_kwargs["connect_args"] = {"timeout": 30}
    else:
        engine_kwargs["pool_pre_ping"] = True
    return create_engine(url, **engine_kwargs)


def init_workflow_store_schema(engine: Engine) -> None:
    """Create workflow tables if they do not exist yet."""
    WorkflowStoreBase.metadata.create_all(engine)


class SQLWorkflowRepository(WorkflowRepository):
    """SQL-backed workflow definition/run store.

    Public interface is identical to the file-backed ``WorkflowRepository``
    (validation and topological ordering are inherited). JSON file paths are
    disabled; all state lives in SQL rows. The full pydantic document is
    stored per row (``doc``) with hot fields mirrored as queryable columns.
    """

    def __init__(self, engine: Engine | str) -> None:
        super().__init__(definition_path=None, run_path=None)
        if isinstance(engine, str):
            engine = create_workflow_engine(engine)
        self._engine = engine
        init_workflow_store_schema(engine)
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        # Serializes writes for SQLite (single-writer); harmless elsewhere.
        self._write_lock = RLock()

    # -- definitions ------------------------------------------------------
    def upsert_definition(
        self,
        workflow: WorkflowCreateRequest | WorkflowUpdateRequest | WorkflowDefinition,
        workflow_id: str | None = None,
    ) -> WorkflowDefinition:
        existing = self.get_definition(workflow_id) if workflow_id else None
        if isinstance(workflow, WorkflowDefinition):
            definition = workflow.model_copy()
            definition.updated_at = datetime.now(UTC)
        else:
            if existing is None and workflow_id is not None:
                raise KeyError(workflow_id)
            base = existing.model_copy() if existing else WorkflowDefinition(
                id=workflow_id or str(uuid4()),
                name=workflow.name or "workflow",
                description=workflow.description or "",
                nodes=workflow.nodes or [],
                edges=workflow.edges or [],
            )
            if workflow.name is not None:
                base.name = workflow.name
            if workflow.description is not None:
                base.description = workflow.description
            if workflow.nodes is not None:
                base.nodes = workflow.nodes
            if workflow.edges is not None:
                base.edges = workflow.edges
            base.updated_at = datetime.now(UTC)
            definition = base

        self._validate_definition(definition)
        row = WorkflowDefinitionRow(
            id=definition.id,
            name=definition.name,
            description=definition.description,
            created_at=definition.created_at,
            updated_at=definition.updated_at,
            doc=definition.model_dump(mode="json"),
        )
        with self._write_lock, self._session_factory.begin() as session:
            session.merge(row)
        return definition

    def list_definitions(self) -> list[WorkflowDefinition]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(WorkflowDefinitionRow).order_by(WorkflowDefinitionRow.updated_at.desc())
            ).all()
        return [self._row_to_definition(row) for row in rows]

    def get_definition(self, workflow_id: str) -> WorkflowDefinition | None:
        with self._session_factory() as session:
            row = session.get(WorkflowDefinitionRow, workflow_id)
        return self._row_to_definition(row) if row else None

    def delete_definition(self, workflow_id: str) -> bool:
        with self._write_lock, self._session_factory.begin() as session:
            row = session.get(WorkflowDefinitionRow, workflow_id)
            if row is None:
                return False
            session.delete(row)
            return True

    def definition_count(self) -> int:
        from sqlalchemy import func

        with self._session_factory() as session:
            return int(session.scalar(select(func.count(WorkflowDefinitionRow.id))) or 0)

    # -- runs -------------------------------------------------------------
    def record_run(self, run: WorkflowRunRecord) -> WorkflowRunRecord:
        with self._write_lock, self._session_factory.begin() as session:
            session.merge(self._run_to_row(run))
        return run

    def update_run_status(
        self,
        run_id: str,
        status: WorkflowRunStatus,
        *,
        error: str | None = None,
        resume_cursor: int | None = None,
    ) -> WorkflowRunRecord | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        update_payload: dict[str, Any] = {
            "status": status,
            "completed_at": datetime.now(UTC),
            "error": error if error is not None else run.error,
        }
        if resume_cursor is not None:
            update_payload["resume_cursor"] = resume_cursor
        updated = run.model_copy(update=update_payload)
        self.record_run(updated)
        return updated

    def update_run_progress(
        self,
        run_id: str,
        *,
        node_results: list[WorkflowNodeResult],
        resume_cursor: int,
        worker_id: str | None = None,
        heartbeat_at: datetime | None = None,
    ) -> WorkflowRunRecord | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        update_payload: dict[str, Any] = {
            "node_results": list(node_results),
            "resume_cursor": resume_cursor,
            "heartbeat_at": heartbeat_at or datetime.now(UTC),
        }
        if worker_id is not None:
            update_payload["worker_id"] = worker_id
        updated = run.model_copy(update=update_payload)
        self.record_run(updated)
        return updated

    def list_runs(self, workflow_id: str | None = None, limit: int = 20) -> list[WorkflowRunRecord]:
        stmt = select(WorkflowRunRow).order_by(WorkflowRunRow.started_at.desc()).limit(limit)
        if workflow_id is not None:
            stmt = stmt.where(WorkflowRunRow.workflow_id == workflow_id)
        with self._session_factory() as session:
            rows = session.scalars(stmt).all()
        return [self._row_to_run(row) for row in rows]

    def get_run(self, run_id: str) -> WorkflowRunRecord | None:
        with self._session_factory() as session:
            row = session.get(WorkflowRunRow, run_id)
        return self._row_to_run(row) if row else None

    def run_count(self) -> int:
        return self.count_runs()

    def count_runs(self, workflow_id: str | None = None) -> int:
        from sqlalchemy import func

        stmt = select(func.count(WorkflowRunRow.run_id))
        if workflow_id is not None:
            stmt = stmt.where(WorkflowRunRow.workflow_id == workflow_id)
        with self._session_factory() as session:
            return int(session.scalar(stmt) or 0)

    def latest_run_for(self, workflow_id: str) -> WorkflowRunRecord | None:
        runs = self.list_runs(workflow_id=workflow_id, limit=1)
        return runs[0] if runs else None

    def summary_for(self, workflow_id: str) -> WorkflowSummary:
        definition = self.get_definition(workflow_id)
        if definition is None:
            raise KeyError(workflow_id)
        latest_run = self.latest_run_for(workflow_id)
        return WorkflowSummary(
            workflow_id=definition.id,
            name=definition.name,
            description=definition.description,
            node_count=len(definition.nodes),
            edge_count=len(definition.edges),
            latest_run_id=latest_run.run_id if latest_run else None,
            latest_run_status=latest_run.status if latest_run else None,
            created_at=definition.created_at,
            updated_at=definition.updated_at,
            snapshot=self.run_snapshot(workflow_id),
        )

    def run_snapshot(self, workflow_id: str) -> dict[str, Any]:
        runs = self.list_runs(workflow_id=workflow_id, limit=1)
        latest_run = runs[0] if runs else None
        return {
            "workflow_id": workflow_id,
            "run_count": self.count_runs(workflow_id),
            "latest_run_id": latest_run.run_id if latest_run else None,
            "latest_run_status": latest_run.status if latest_run else None,
        }

    # -- row <-> model conversion -----------------------------------------
    @staticmethod
    def _row_to_definition(row: WorkflowDefinitionRow) -> WorkflowDefinition:
        doc = _normalize_record_datetimes(dict(row.doc), ("created_at", "updated_at"))
        return WorkflowDefinition.model_validate(doc)

    @staticmethod
    def _run_to_row(run: WorkflowRunRecord) -> WorkflowRunRow:
        return WorkflowRunRow(
            run_id=run.run_id,
            workflow_id=run.workflow_id,
            status=run.status.value,
            tenant_id=run.tenant_id,
            user_id=run.user_id,
            resume_cursor=run.resume_cursor,
            worker_id=run.worker_id,
            heartbeat_at=run.heartbeat_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            doc=run.model_dump(mode="json"),
        )

    @staticmethod
    def _row_to_run(row: WorkflowRunRow) -> WorkflowRunRecord:
        doc = _normalize_record_datetimes(
            dict(row.doc),
            ("started_at", "completed_at", "heartbeat_at"),
        )
        for result in doc.get("node_results") or []:
            if isinstance(result, dict):
                for field in ("started_at", "completed_at"):
                    value = result.get(field)
                    if isinstance(value, str):
                        result[field] = _as_utc(datetime.fromisoformat(value))
        return WorkflowRunRecord.model_validate(doc)


class SQLWorkflowScheduleStore(WorkflowScheduleStore):
    """SQL-backed schedule store with the file store's interface.

    ``acquire_due`` uses SELECT ... FOR UPDATE SKIP LOCKED on Postgres so
    multiple workers can poll safely; on SQLite the statement degrades to a
    plain SELECT serialized by the module-level write lock.
    """

    def __init__(self, engine: Engine | str) -> None:
        super().__init__(storage_path=None)
        if isinstance(engine, str):
            engine = create_workflow_engine(engine)
        self._engine = engine
        init_workflow_store_schema(engine)
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self._write_lock = RLock()

    def create(
        self,
        *,
        workflow_id: str,
        inputs: dict[str, Any],
        tenant_id: str,
        user_id: str,
        permission_scope: list[str],
        run_at: datetime,
        cron: str | None = None,
    ) -> WorkflowScheduleRecord:
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=UTC)
        record = WorkflowScheduleRecord(
            workflow_id=workflow_id,
            inputs=inputs,
            tenant_id=tenant_id,
            user_id=user_id,
            permission_scope=permission_scope,
            run_at=run_at,
            cron=cron,
            snapshot={
                "workflow_id": workflow_id,
                "input_keys": sorted(inputs.keys()),
                "run_at": run_at.isoformat(),
                "cron": cron,
            },
        )
        with self._write_lock, self._session_factory.begin() as session:
            session.merge(self._record_to_row(record))
        return record

    def list(
        self,
        *,
        status: WorkflowScheduleStatus | None = None,
        workflow_id: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowScheduleRecord]:
        stmt = select(WorkflowScheduleRow).order_by(WorkflowScheduleRow.run_at.desc()).limit(limit)
        if status is not None:
            stmt = stmt.where(WorkflowScheduleRow.status == status.value)
        if workflow_id is not None:
            stmt = stmt.where(WorkflowScheduleRow.workflow_id == workflow_id)
        with self._session_factory() as session:
            rows = session.scalars(stmt).all()
        return [self._row_to_record(row) for row in rows]

    def due(
        self,
        *,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[WorkflowScheduleRecord]:
        moment = _as_utc(now) or datetime.now(UTC)
        stmt = (
            select(WorkflowScheduleRow)
            .where(
                WorkflowScheduleRow.status == WorkflowScheduleStatus.PENDING.value,
                WorkflowScheduleRow.run_at <= moment,
            )
            .order_by(WorkflowScheduleRow.run_at.asc())
            .limit(limit)
        )
        with self._session_factory() as session:
            rows = session.scalars(stmt).all()
        return [self._row_to_record(row) for row in rows]

    def acquire_due(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[WorkflowScheduleRecord]:
        moment = _as_utc(now) or datetime.now(UTC)
        lease_until = moment + timedelta(seconds=lease_seconds)
        acquired: list[WorkflowScheduleRecord] = []
        with self._write_lock, self._session_factory.begin() as session:
            stmt = (
                select(WorkflowScheduleRow)
                .where(
                    WorkflowScheduleRow.status == WorkflowScheduleStatus.PENDING.value,
                    WorkflowScheduleRow.run_at <= moment,
                )
                .order_by(WorkflowScheduleRow.run_at.asc())
                .limit(limit)
            )
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
            rows = session.scalars(stmt).all()
            for row in rows:
                locked_until = _as_utc(row.locked_until)
                if locked_until is not None and locked_until > moment:
                    continue
                record = self._row_to_record(row)
                updated = record.model_copy(
                    update={
                        "locked_by": worker_id,
                        "locked_until": lease_until,
                        "updated_at": moment,
                    }
                )
                session.merge(self._record_to_row(updated))
                acquired.append(updated)
        return acquired

    def get(self, schedule_id: str) -> WorkflowScheduleRecord | None:
        with self._session_factory() as session:
            row = session.get(WorkflowScheduleRow, schedule_id)
        return self._row_to_record(row) if row else None

    def mark(
        self,
        schedule_id: str,
        status: WorkflowScheduleStatus,
        *,
        run_id: str | None = None,
        error: str | None = None,
    ) -> WorkflowScheduleRecord | None:
        with self._write_lock, self._session_factory.begin() as session:
            row = session.get(WorkflowScheduleRow, schedule_id)
            if row is None:
                return None
            record = self._row_to_record(row)
            updated = record.model_copy(
                update={
                    "status": status,
                    "run_id": run_id if run_id is not None else record.run_id,
                    "locked_by": None,
                    "locked_until": None,
                    "error": error,
                    "updated_at": datetime.now(UTC),
                }
            )
            session.merge(self._record_to_row(updated))
            return updated

    def reschedule(
        self,
        schedule_id: str,
        *,
        run_at: datetime,
        run_id: str | None = None,
        error: str | None = None,
    ) -> WorkflowScheduleRecord | None:
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=UTC)
        with self._write_lock, self._session_factory.begin() as session:
            row = session.get(WorkflowScheduleRow, schedule_id)
            if row is None:
                return None
            record = self._row_to_record(row)
            snapshot = dict(record.snapshot)
            snapshot["last_run_at"] = record.run_at.isoformat()
            if error:
                snapshot["last_error"] = error
            else:
                snapshot.pop("last_error", None)
            updated = record.model_copy(
                update={
                    "status": WorkflowScheduleStatus.PENDING,
                    "run_at": run_at,
                    "run_id": run_id if run_id is not None else record.run_id,
                    "locked_by": None,
                    "locked_until": None,
                    "error": error,
                    "updated_at": datetime.now(UTC),
                    "snapshot": snapshot,
                }
            )
            session.merge(self._record_to_row(updated))
            return updated

    def count(self, status: WorkflowScheduleStatus | None = None) -> int:
        from sqlalchemy import func

        stmt = select(func.count(WorkflowScheduleRow.schedule_id))
        if status is not None:
            stmt = stmt.where(WorkflowScheduleRow.status == status.value)
        with self._session_factory() as session:
            return int(session.scalar(stmt) or 0)

    # -- row <-> model conversion -----------------------------------------
    @staticmethod
    def _record_to_row(record: WorkflowScheduleRecord) -> WorkflowScheduleRow:
        return WorkflowScheduleRow(
            schedule_id=record.schedule_id,
            workflow_id=record.workflow_id,
            status=record.status.value,
            tenant_id=record.tenant_id,
            user_id=record.user_id,
            run_at=record.run_at,
            cron=record.cron,
            run_id=record.run_id,
            locked_by=record.locked_by,
            locked_until=record.locked_until,
            created_at=record.created_at,
            updated_at=record.updated_at,
            doc=record.model_dump(mode="json"),
        )

    @staticmethod
    def _row_to_record(row: WorkflowScheduleRow) -> WorkflowScheduleRecord:
        doc = _normalize_record_datetimes(
            dict(row.doc),
            ("run_at", "locked_until", "created_at", "updated_at"),
        )
        return WorkflowScheduleRecord.model_validate(doc)


# ---------------------------------------------------------------------------
# Backend factories
# ---------------------------------------------------------------------------

def _resolve_backend(backend: str | None) -> str:
    resolved = (backend or os.getenv(WORKFLOW_STORE_BACKEND_ENV) or "auto").strip().lower()
    if resolved not in {"db", "file", "auto"}:
        raise ValueError(
            f"Unknown workflow store backend {resolved!r}; expected one of: db, file, auto."
        )
    return resolved


def build_workflow_repository(
    *,
    backend: str | None = None,
    database_url: str | None = None,
    definition_path: str | Path | None = None,
    run_path: str | Path | None = None,
) -> WorkflowRepository:
    """Build the workflow repository for the configured backend.

    db   -> SQLWorkflowRepository (failures raise — explicit).
    file -> file-backed WorkflowRepository (dev fallback).
    auto -> try SQL, fall back to file with a WARNING (explicit degradation).
    """
    resolved = _resolve_backend(backend)
    if resolved == "file" or not database_url:
        if resolved == "db" and not database_url:
            raise RuntimeError(
                "Workflow store backend 'db' requires a database_url; none was provided."
            )
        return WorkflowRepository(definition_path=definition_path, run_path=run_path)
    if resolved == "db":
        return SQLWorkflowRepository(create_workflow_engine(database_url))
    try:
        return SQLWorkflowRepository(create_workflow_engine(database_url))
    except Exception as exc:  # noqa: BLE001 - explicit degradation for dev
        logger.warning(
            "Workflow SQL store unavailable (%s); falling back to JSON file storage. "
            "Set %s=file to silence this, or fix the database configuration.",
            exc,
            WORKFLOW_STORE_BACKEND_ENV,
        )
        return WorkflowRepository(definition_path=definition_path, run_path=run_path)


def build_workflow_schedule_store(
    *,
    backend: str | None = None,
    database_url: str | None = None,
    storage_path: str | Path | None = None,
) -> WorkflowScheduleStore:
    """Build the schedule store for the configured backend (same policy as
    ``build_workflow_repository``)."""
    resolved = _resolve_backend(backend)
    if resolved == "file" or not database_url:
        if resolved == "db" and not database_url:
            raise RuntimeError(
                "Workflow store backend 'db' requires a database_url; none was provided."
            )
        return WorkflowScheduleStore(storage_path=storage_path)
    if resolved == "db":
        return SQLWorkflowScheduleStore(create_workflow_engine(database_url))
    try:
        return SQLWorkflowScheduleStore(create_workflow_engine(database_url))
    except Exception as exc:  # noqa: BLE001 - explicit degradation for dev
        logger.warning(
            "Workflow schedule SQL store unavailable (%s); falling back to JSON file "
            "storage. Set %s=file to silence this, or fix the database configuration.",
            exc,
            WORKFLOW_STORE_BACKEND_ENV,
        )
        return WorkflowScheduleStore(storage_path=storage_path)
