"""SQL-backed agent run registry for multi-instance deployments."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, create_engine, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import JSON

from backend.app.core.contracts import AgentRunRecord
from backend.app.core.database_urls import normalize_sync_database_url
from backend.app.core.runs import RunStore

_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class RunStoreBase(DeclarativeBase):
    pass


class AgentRunRecordRow(RunStoreBase):
    __tablename__ = "agent_run_records"
    __table_args__ = (
        Index("idx_agent_run_records_tenant_completed", "tenant_id", "completed_at"),
    )

    trace_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    doc: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)


class SqlRunStore(RunStore):
    def __init__(self, database_url: str, *, create_schema: bool) -> None:
        super().__init__(storage_path=None)
        self._engine = create_engine(
            normalize_sync_database_url(database_url),
            future=True,
            pool_pre_ping=True,
        )
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)
        if create_schema:
            RunStoreBase.metadata.create_all(self._engine)

    def _append_to_disk(self, record: AgentRunRecord) -> None:
        with self._session_factory.begin() as session:
            session.merge(
                AgentRunRecordRow(
                    trace_id=record.trace_id,
                    tenant_id=record.tenant_id,
                    user_id=record.user_id,
                    agent_id=record.agent_id,
                    status=record.status.value,
                    task=record.task,
                    created_at=record.created_at,
                    completed_at=record.completed_at,
                    doc=record.model_dump(mode="json"),
                )
            )

    def get(self, trace_id: str) -> AgentRunRecord | None:
        with self._session_factory() as session:
            row = session.get(AgentRunRecordRow, trace_id)
            return AgentRunRecord.model_validate(row.doc) if row is not None else None

    def list(self, limit: int = 20) -> list[AgentRunRecord]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(AgentRunRecordRow)
                .order_by(AgentRunRecordRow.completed_at.desc())
                .limit(limit)
            ).all()
            return [AgentRunRecord.model_validate(row.doc) for row in rows]

    def count(self) -> int:
        with self._session_factory() as session:
            return int(session.scalar(select(func.count()).select_from(AgentRunRecordRow)) or 0)
