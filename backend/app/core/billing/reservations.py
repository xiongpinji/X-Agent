"""Persistent, idempotent provider-usage reservation state machine."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    and_,
    create_engine,
    event,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.app.core.admin_store import normalize_sync_database_url
from backend.app.settings import PROJECT_ROOT, Settings, get_settings

ReservationStatus = Literal[
    "reserved", "confirmed", "refunded", "submission_unknown"
]
_TERMINAL_STATUSES = {"confirmed", "refunded", "submission_unknown"}
_MONEY_QUANTUM = Decimal("0.00000001")
_MAX_MONEY = Decimal("9999999999.99999999")


def _normalize_money(value: Any, field_name: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{field_name} must be a finite NUMERIC(18,8) value") from exc
    if not amount.is_finite():
        raise ValueError(f"{field_name} must be a finite NUMERIC(18,8) value")
    if amount < 0 or amount > _MAX_MONEY:
        raise ValueError(f"{field_name} must fit non-negative NUMERIC(18,8)")
    if amount.as_tuple().exponent < -8:
        raise ValueError(f"{field_name} must have at most 8 decimal places")
    return amount.quantize(_MONEY_QUANTUM)


class UsageReservationError(RuntimeError):
    """Base error for fail-closed reservation operations."""


class ReservationConflictError(UsageReservationError):
    """The operation ID already exists with different immutable parameters/state."""


class ReservationNotFoundError(UsageReservationError):
    """The scoped reservation does not exist."""


class UsageReservation(BaseModel):
    tenant_id: str
    operation_id: str
    root_operation_id: str
    user_id: str | None = None
    provider: str
    model: str
    request_hash: str
    estimated_cost: Decimal
    actual_cost: Decimal | None = None
    tokens_used: int = 0
    status: ReservationStatus
    run_id: str | None = None
    trace_id: str | None = None
    created_at: float
    updated_at: float
    ledger_entry_count: int = 0
    audit_status: Literal["pending", "delivered"] = "pending"
    created: bool = False


class UsageLedgerEntry(BaseModel):
    id: str
    tenant_id: str
    operation_id: str
    from_status: str
    to_status: str
    actual_cost: Decimal | None = None
    tokens_used: int
    created_at: float


class UsageAuditOutboxEntry(BaseModel):
    id: str
    tenant_id: str
    operation_id: str
    action: str
    status: Literal["pending", "delivering", "delivered"]
    audit_id: str | None = None
    delivery_token: str | None = None
    lease_expires_at: float | None = None
    attempt_count: int
    last_error: str | None = None
    payload: dict[str, Any]


class UsageBillingSummary(BaseModel):
    tenant_id: str
    month: str
    confirmed_cost: Decimal
    confirmed_count: int
    refunded_count: int
    submission_unknown_count: int
    reservation_count: int


class UsageReservationBase(DeclarativeBase):
    pass


class UsageReservationModel(UsageReservationBase):
    __tablename__ = "usage_reservations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operation_id", name="uq_usage_reservation_operation"),
        CheckConstraint(
            "status IN ('reserved', 'confirmed', 'refunded', 'submission_unknown')",
            name="ck_usage_reservation_status",
        ),
        Index("idx_usage_reservations_root", "tenant_id", "root_operation_id"),
        Index("idx_usage_reservations_month", "tenant_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    root_operation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)


class UsageLedgerModel(UsageReservationBase):
    __tablename__ = "usage_reservation_ledger"
    __table_args__ = (
        UniqueConstraint("reservation_id", name="uq_usage_ledger_terminal_transition"),
        CheckConstraint(
            "to_status IN ('confirmed', 'refunded', 'submission_unknown')",
            name="ck_usage_ledger_to_status",
        ),
        Index("idx_usage_ledger_operation", "tenant_id", "operation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reservation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("usage_reservations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)


class UsageAuditOutboxModel(UsageReservationBase):
    __tablename__ = "usage_reservation_audit_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivering', 'delivered')",
            name="ck_usage_audit_outbox_status",
        ),
        Index("idx_usage_audit_outbox_pending", "status", "created_at"),
        Index("idx_usage_audit_outbox_operation", "tenant_id", "operation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    audit_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SqlUsageReservationStore:
    """SQLAlchemy-backed store; blocking driver work is moved off the event loop."""

    def __init__(
        self,
        database_url: str,
        *,
        create_schema: bool,
        audit_store: Any | None = None,
    ) -> None:
        self.sync_url = normalize_sync_database_url(database_url)
        if self.sync_url.startswith("sqlite") and ":memory:" in self.sync_url:
            raise ValueError("usage reservations require persistent storage")
        engine_kwargs: dict[str, Any] = {"future": True}
        if self.sync_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {
                "check_same_thread": False,
                "timeout": 30,
            }
        else:
            engine_kwargs.update(
                pool_size=5,
                max_overflow=10,
                pool_recycle=1800,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 5},
            )
        self.engine: Engine = create_engine(self.sync_url, **engine_kwargs)
        if self.sync_url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._create_schema = create_schema
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()
        self.audit_store = audit_store

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def _ensure_schema(self) -> None:
        if not self._create_schema or self._schema_ready:
            return
        async with self._schema_lock:
            if not self._schema_ready:
                await asyncio.to_thread(UsageReservationBase.metadata.create_all, self.engine)
                self._schema_ready = True

    async def _run(self, operation, /, *args):
        await self._ensure_schema()
        return await asyncio.to_thread(operation, *args)

    async def dispose(self) -> None:
        await asyncio.to_thread(self.engine.dispose)

    async def reserve(
        self,
        *,
        tenant_id: str,
        operation_id: str,
        estimated_cost: Decimal,
        root_operation_id: str | None = None,
        user_id: str | None = None,
        provider: str = "unknown",
        model: str = "unknown",
        run_id: str | None = None,
        trace_id: str | None = None,
        request_payload: dict[str, Any] | None = None,
    ) -> UsageReservation:
        root_id = root_operation_id or operation_id
        estimate = _normalize_money(estimated_cost, "estimated_cost")
        if not tenant_id or not operation_id or not root_id:
            raise ValueError("tenant_id and operation IDs are required")
        estimate_fingerprint = format(estimate, "f")
        fingerprint = _canonical_hash(
            {
                "root_operation_id": root_id,
                "user_id": user_id,
                "provider": provider,
                "model": model,
                "estimated_cost": estimate_fingerprint,
                "run_id": run_id,
                "trace_id": trace_id,
                "request": request_payload or {},
            }
        )
        reservation = await self._run(
            self._reserve,
            tenant_id,
            operation_id,
            root_id,
            user_id,
            provider,
            model,
            estimate,
            run_id,
            trace_id,
            fingerprint,
        )
        await self.deliver_pending()
        refreshed = await self.get(tenant_id=tenant_id, operation_id=operation_id)
        if refreshed is None:  # pragma: no cover - committed row disappearing is storage failure
            raise UsageReservationError("reservation disappeared after commit")
        refreshed.created = reservation.created
        return refreshed

    def _reserve(
        self,
        tenant_id: str,
        operation_id: str,
        root_operation_id: str,
        user_id: str | None,
        provider: str,
        model: str,
        estimated_cost: Decimal,
        run_id: str | None,
        trace_id: str | None,
        request_hash: str,
    ) -> UsageReservation:
        now = time.time()
        model_row = UsageReservationModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            operation_id=operation_id,
            root_operation_id=root_operation_id,
            user_id=user_id,
            provider=provider,
            model=model,
            request_hash=request_hash,
            estimated_cost=estimated_cost,
            actual_cost=None,
            tokens_used=0,
            status="reserved",
            run_id=run_id,
            trace_id=trace_id,
            created_at=now,
            updated_at=now,
        )
        with self._session_factory() as session:
            session.add(model_row)
            self._add_outbox(session, model_row, action="usage.reserved", now=now)
            try:
                session.commit()
                return self._record(session, model_row, created=True)
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(UsageReservationModel).where(
                        UsageReservationModel.tenant_id == tenant_id,
                        UsageReservationModel.operation_id == operation_id,
                    )
                )
                if existing is None:
                    raise
                if existing.request_hash != request_hash:
                    raise ReservationConflictError(
                        "operation_id already exists with different parameters"
                    )
                return self._record(session, existing, created=False)

    async def confirm(
        self,
        operation_id: str,
        *,
        tenant_id: str,
        actual_cost: Decimal,
        tokens_used: int,
    ) -> UsageReservation:
        resolved_cost = _normalize_money(actual_cost, "actual_cost")
        if tokens_used < 0:
            raise ValueError("tokens_used must be non-negative")
        return await self._transition(
            tenant_id,
            operation_id,
            "confirmed",
            resolved_cost,
            int(tokens_used),
            None,
        )

    async def refund(
        self,
        operation_id: str,
        *,
        tenant_id: str,
        reason_code: str | None = None,
    ) -> UsageReservation:
        return await self._transition(
            tenant_id, operation_id, "refunded", Decimal("0"), 0, reason_code
        )

    async def mark_submission_unknown(
        self,
        operation_id: str,
        *,
        tenant_id: str,
        reason_code: str | None = None,
    ) -> UsageReservation:
        return await self._transition(
            tenant_id,
            operation_id,
            "submission_unknown",
            None,
            0,
            reason_code,
        )

    async def _transition(
        self,
        tenant_id: str,
        operation_id: str,
        status: str,
        actual_cost: Decimal | None,
        tokens_used: int,
        reason_code: str | None,
    ) -> UsageReservation:
        if status not in _TERMINAL_STATUSES:
            raise ValueError("invalid terminal status")
        record = await self._run(
            self._transition_sync,
            tenant_id,
            operation_id,
            status,
            actual_cost,
            tokens_used,
            reason_code,
        )
        await self.deliver_pending()
        refreshed = await self.get(tenant_id=tenant_id, operation_id=operation_id)
        return refreshed or record

    def _transition_sync(
        self,
        tenant_id: str,
        operation_id: str,
        status: str,
        actual_cost: Decimal | None,
        tokens_used: int,
        reason_code: str | None,
    ) -> UsageReservation:
        with self._session_factory() as session:
            model = session.scalar(
                select(UsageReservationModel).where(
                    UsageReservationModel.tenant_id == tenant_id,
                    UsageReservationModel.operation_id == operation_id,
                )
            )
            if model is None:
                raise ReservationNotFoundError("reservation not found")
            if model.status != "reserved":
                if self._same_terminal_result(model, status, actual_cost, tokens_used):
                    return self._record(session, model)
                raise ReservationConflictError(
                    f"reservation is already terminal ({model.status})"
                )

            now = time.time()
            result = session.execute(
                update(UsageReservationModel)
                .where(
                    UsageReservationModel.id == model.id,
                    UsageReservationModel.status == "reserved",
                )
                .values(
                    status=status,
                    actual_cost=actual_cost,
                    tokens_used=tokens_used,
                    updated_at=now,
                )
            )
            if result.rowcount != 1:
                session.rollback()
                current = session.scalar(
                    select(UsageReservationModel).where(
                        UsageReservationModel.tenant_id == tenant_id,
                        UsageReservationModel.operation_id == operation_id,
                    )
                )
                if current is not None and self._same_terminal_result(
                    current, status, actual_cost, tokens_used
                ):
                    return self._record(session, current)
                raise ReservationConflictError("concurrent terminal transition conflict")

            session.add(
                UsageLedgerModel(
                    id=str(uuid.uuid4()),
                    reservation_id=model.id,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    from_status="reserved",
                    to_status=status,
                    actual_cost=actual_cost,
                    tokens_used=tokens_used,
                    created_at=now,
                )
            )
            model.status = status
            model.actual_cost = actual_cost
            model.tokens_used = tokens_used
            model.updated_at = now
            self._add_outbox(
                session,
                model,
                action=f"usage.{status}",
                now=now,
                reason_code=reason_code,
            )
            session.commit()
            return self._record(session, model)

    @staticmethod
    def _same_terminal_result(
        model: UsageReservationModel,
        status: str,
        actual_cost: Decimal | None,
        tokens_used: int,
    ) -> bool:
        if model.status != status:
            return False
        if status == "confirmed":
            return (
                Decimal(model.actual_cost or 0) == Decimal(actual_cost or 0)
                and model.tokens_used == tokens_used
            )
        return True

    def _add_outbox(
        self,
        session,
        model: UsageReservationModel,
        *,
        action: str,
        now: float,
        reason_code: str | None = None,
    ) -> None:
        outbox_id = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "event_id": outbox_id,
            "tenant_id": model.tenant_id,
            "user_id": model.user_id,
            "operation_id": model.operation_id,
            "root_operation_id": model.root_operation_id,
            "provider": model.provider,
            "model": model.model,
            "status": model.status,
            "run_id": model.run_id,
            "trace_id": model.trace_id,
        }
        if reason_code:
            payload["reason_code"] = reason_code
        session.add(
            UsageAuditOutboxModel(
                id=outbox_id,
                tenant_id=model.tenant_id,
                operation_id=model.operation_id,
                action=action,
                status="pending",
                audit_id=None,
                delivery_token=None,
                lease_expires_at=None,
                attempt_count=0,
                last_error=None,
                payload=payload,
                created_at=now,
                updated_at=now,
            )
        )

    async def get(
        self, *, tenant_id: str, operation_id: str
    ) -> UsageReservation | None:
        return await self._run(self._get, tenant_id, operation_id)

    def _get(self, tenant_id: str, operation_id: str) -> UsageReservation | None:
        with self._session_factory() as session:
            model = session.scalar(
                select(UsageReservationModel).where(
                    UsageReservationModel.tenant_id == tenant_id,
                    UsageReservationModel.operation_id == operation_id,
                )
            )
            return self._record(session, model) if model else None

    async def list_for_root(
        self, *, tenant_id: str, root_operation_id: str
    ) -> list[UsageReservation]:
        return await self._run(self._list_for_root, tenant_id, root_operation_id)

    def _list_for_root(
        self, tenant_id: str, root_operation_id: str
    ) -> list[UsageReservation]:
        with self._session_factory() as session:
            models = session.scalars(
                select(UsageReservationModel)
                .where(
                    UsageReservationModel.tenant_id == tenant_id,
                    UsageReservationModel.root_operation_id == root_operation_id,
                )
                .order_by(UsageReservationModel.created_at)
            ).all()
            return [self._record(session, item) for item in models]

    async def list_ledger(
        self, *, tenant_id: str, operation_id: str
    ) -> list[UsageLedgerEntry]:
        return await self._run(self._list_ledger, tenant_id, operation_id)

    def _list_ledger(
        self, tenant_id: str, operation_id: str
    ) -> list[UsageLedgerEntry]:
        with self._session_factory() as session:
            entries = session.scalars(
                select(UsageLedgerModel)
                .where(
                    UsageLedgerModel.tenant_id == tenant_id,
                    UsageLedgerModel.operation_id == operation_id,
                )
                .order_by(UsageLedgerModel.created_at)
            ).all()
            return [
                UsageLedgerEntry(
                    id=item.id,
                    tenant_id=item.tenant_id,
                    operation_id=item.operation_id,
                    from_status=item.from_status,
                    to_status=item.to_status,
                    actual_cost=item.actual_cost,
                    tokens_used=item.tokens_used,
                    created_at=item.created_at,
                )
                for item in entries
            ]

    async def list_outbox(
        self,
        *,
        tenant_id: str | None = None,
        operation_id: str | None = None,
        status: str | None = None,
    ) -> list[UsageAuditOutboxEntry]:
        return await self._run(self._list_outbox, tenant_id, operation_id, status)

    def _list_outbox(
        self,
        tenant_id: str | None,
        operation_id: str | None,
        status: str | None,
    ) -> list[UsageAuditOutboxEntry]:
        query = select(UsageAuditOutboxModel)
        if tenant_id is not None:
            query = query.where(UsageAuditOutboxModel.tenant_id == tenant_id)
        if operation_id is not None:
            query = query.where(UsageAuditOutboxModel.operation_id == operation_id)
        if status is not None:
            query = query.where(UsageAuditOutboxModel.status == status)
        with self._session_factory() as session:
            rows = session.scalars(query.order_by(UsageAuditOutboxModel.created_at)).all()
            return [self._outbox_record(row) for row in rows]

    async def deliver_pending(
        self,
        audit_store: Any | None = None,
        *,
        lease_seconds: float = 30.0,
        limit: int = 100,
    ) -> int:
        """Deliver claimed events with at-least-once, stable-event-id semantics."""
        sink = audit_store or self.audit_store
        if sink is None:
            return 0
        if lease_seconds <= 0 or limit <= 0:
            raise ValueError("lease_seconds and limit must be positive")
        delivered = 0
        attempted_ids: set[str] = set()
        for _ in range(limit):
            delivery_token = uuid.uuid4().hex
            entry = await self._run(
                self._claim_next_outbox,
                time.time(),
                time.time() + lease_seconds,
                delivery_token,
                tuple(attempted_ids),
            )
            if entry is None:
                break
            attempted_ids.add(entry.id)
            try:
                record = await asyncio.to_thread(
                    sink.record,
                    action=entry.action,
                    resource_type="usage_reservation",
                    tenant_id=entry.tenant_id,
                    actor_id=str(entry.payload.get("user_id") or "system"),
                    resource_id=entry.operation_id,
                    trace_id=entry.payload.get("trace_id"),
                    run_id=entry.payload.get("run_id"),
                    details=entry.payload,
                )
                audit_id = getattr(record, "id", None)
                if not audit_id:
                    raise UsageReservationError("audit sink returned no record id")
            except Exception as exc:
                await self._run(
                    self._release_outbox_claim,
                    entry.id,
                    delivery_token,
                    exc.__class__.__name__,
                )
                continue
            await self._run(
                self._mark_outbox_delivered,
                entry.id,
                delivery_token,
                str(audit_id),
            )
            delivered += 1
        return delivered

    def _claim_next_outbox(
        self,
        now: float,
        lease_expires_at: float,
        delivery_token: str,
        excluded_ids: tuple[str, ...],
    ) -> UsageAuditOutboxEntry | None:
        available = or_(
            UsageAuditOutboxModel.status == "pending",
            and_(
                UsageAuditOutboxModel.status == "delivering",
                UsageAuditOutboxModel.lease_expires_at <= now,
            ),
        )
        while True:
            with self._session_factory() as session:
                query = (
                    select(UsageAuditOutboxModel.id)
                    .where(available)
                    .order_by(UsageAuditOutboxModel.created_at)
                    .limit(1)
                )
                if excluded_ids:
                    query = query.where(
                        UsageAuditOutboxModel.id.not_in(excluded_ids)
                    )
                outbox_id = session.scalar(query)
                if outbox_id is None:
                    return None
                result = session.execute(
                    update(UsageAuditOutboxModel)
                    .where(
                        UsageAuditOutboxModel.id == outbox_id,
                        available,
                    )
                    .values(
                        status="delivering",
                        delivery_token=delivery_token,
                        lease_expires_at=lease_expires_at,
                        attempt_count=UsageAuditOutboxModel.attempt_count + 1,
                        last_error=None,
                        updated_at=now,
                    )
                )
                session.commit()
                if result.rowcount == 1:
                    claimed = session.get(UsageAuditOutboxModel, outbox_id)
                    if claimed is None:
                        raise UsageReservationError(
                            "claimed audit outbox event disappeared"
                        )
                    return self._outbox_record(claimed)

    def _release_outbox_claim(
        self,
        outbox_id: str,
        delivery_token: str,
        error_code: str,
    ) -> None:
        with self._session_factory() as session:
            result = session.execute(
                update(UsageAuditOutboxModel)
                .where(
                    UsageAuditOutboxModel.id == outbox_id,
                    UsageAuditOutboxModel.status == "delivering",
                    UsageAuditOutboxModel.delivery_token == delivery_token,
                )
                .values(
                    status="pending",
                    delivery_token=None,
                    lease_expires_at=None,
                    last_error=error_code[:128],
                    updated_at=time.time(),
                )
            )
            session.commit()
            if result.rowcount != 1:
                raise UsageReservationError("audit outbox claim ownership was lost")

    def _mark_outbox_delivered(
        self,
        outbox_id: str,
        delivery_token: str,
        audit_id: str,
    ) -> None:
        with self._session_factory() as session:
            result = session.execute(
                update(UsageAuditOutboxModel)
                .where(
                    UsageAuditOutboxModel.id == outbox_id,
                    UsageAuditOutboxModel.status == "delivering",
                    UsageAuditOutboxModel.delivery_token == delivery_token,
                )
                .values(
                    status="delivered",
                    audit_id=audit_id,
                    delivery_token=None,
                    lease_expires_at=None,
                    last_error=None,
                    updated_at=time.time(),
                )
            )
            session.commit()
            if result.rowcount != 1:
                raise UsageReservationError("audit outbox claim ownership was lost")

    async def monthly_summary(
        self, *, tenant_id: str, month: str
    ) -> UsageBillingSummary:
        try:
            start = datetime.strptime(month, "%Y-%m").replace(tzinfo=UTC)
        except ValueError as exc:
            raise ValueError("month must use YYYY-MM") from exc
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return await self._run(
            self._monthly_summary, tenant_id, month, start.timestamp(), end.timestamp()
        )

    def _monthly_summary(
        self, tenant_id: str, month: str, start: float, end: float
    ) -> UsageBillingSummary:
        with self._session_factory() as session:
            rows = session.execute(
                select(
                    UsageReservationModel.status,
                    func.count(UsageReservationModel.id),
                    func.coalesce(func.sum(UsageReservationModel.actual_cost), 0),
                )
                .where(
                    UsageReservationModel.tenant_id == tenant_id,
                    UsageReservationModel.updated_at >= start,
                    UsageReservationModel.updated_at < end,
                )
                .group_by(UsageReservationModel.status)
            ).all()
        counts = {status: int(count) for status, count, _cost in rows}
        confirmed_cost = sum(
            (Decimal(str(cost)) for status, _count, cost in rows if status == "confirmed"),
            Decimal("0"),
        )
        return UsageBillingSummary(
            tenant_id=tenant_id,
            month=month,
            confirmed_cost=confirmed_cost,
            confirmed_count=counts.get("confirmed", 0),
            refunded_count=counts.get("refunded", 0),
            submission_unknown_count=counts.get("submission_unknown", 0),
            reservation_count=sum(counts.values()),
        )

    def _record(
        self,
        session,
        model: UsageReservationModel,
        *,
        created: bool = False,
    ) -> UsageReservation:
        ledger_count = session.scalar(
            select(func.count(UsageLedgerModel.id)).where(
                UsageLedgerModel.reservation_id == model.id
            )
        )
        undelivered_count = session.scalar(
            select(func.count(UsageAuditOutboxModel.id)).where(
                UsageAuditOutboxModel.tenant_id == model.tenant_id,
                UsageAuditOutboxModel.operation_id == model.operation_id,
                UsageAuditOutboxModel.status != "delivered",
            )
        )
        return UsageReservation(
            tenant_id=model.tenant_id,
            operation_id=model.operation_id,
            root_operation_id=model.root_operation_id,
            user_id=model.user_id,
            provider=model.provider,
            model=model.model,
            request_hash=model.request_hash,
            estimated_cost=model.estimated_cost,
            actual_cost=model.actual_cost,
            tokens_used=model.tokens_used,
            status=model.status,
            run_id=model.run_id,
            trace_id=model.trace_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            ledger_entry_count=int(ledger_count or 0),
            audit_status="pending" if undelivered_count else "delivered",
            created=created,
        )

    @staticmethod
    def _outbox_record(model: UsageAuditOutboxModel) -> UsageAuditOutboxEntry:
        return UsageAuditOutboxEntry(
            id=model.id,
            tenant_id=model.tenant_id,
            operation_id=model.operation_id,
            action=model.action,
            status=model.status,
            audit_id=model.audit_id,
            delivery_token=model.delivery_token,
            lease_expires_at=model.lease_expires_at,
            attempt_count=model.attempt_count,
            last_error=model.last_error,
            payload=dict(model.payload or {}),
        )


def create_usage_reservation_store(
    settings: Settings | None = None,
    *,
    audit_store: Any | None = None,
) -> SqlUsageReservationStore:
    resolved = settings or get_settings()
    if resolved.app_mode == "production":
        normalized = normalize_sync_database_url(resolved.database_url).lower()
        if not normalized.startswith("postgresql+psycopg://"):
            raise RuntimeError("production usage reservations require PostgreSQL")
        return SqlUsageReservationStore(
            resolved.database_url,
            create_schema=False,
            audit_store=audit_store,
        )

    configured = resolved.database_url.strip()
    if configured.lower().startswith("sqlite") and ":memory:" not in configured.lower():
        database_url = configured
    else:
        data_dir = Path(PROJECT_ROOT) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{(data_dir / 'usage_reservations.db').as_posix()}"
    return SqlUsageReservationStore(
        database_url,
        create_schema=True,
        audit_store=audit_store,
    )
