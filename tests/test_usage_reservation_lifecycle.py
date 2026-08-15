from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from backend.app.core.billing.reservations import (
    ReservationConflictError,
    SqlUsageReservationStore,
    create_usage_reservation_store,
)
from backend.app.core.security import Principal


@pytest.mark.asyncio
async def test_reserve_confirm_is_idempotent_and_persistent(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'usage.db').as_posix()}"
    store = SqlUsageReservationStore(database_url, create_schema=True)

    reserved = await store.reserve(
        tenant_id="tenant-a",
        operation_id="op-1",
        root_operation_id="root-1",
        provider="mock",
        model="mock-v1",
        estimated_cost=Decimal("0.01"),
        run_id="run-1",
        trace_id="trace-1",
    )
    assert reserved.status == "reserved"

    confirmed = await store.confirm(
        tenant_id="tenant-a",
        operation_id="op-1",
        actual_cost=Decimal("0.008"),
        tokens_used=17,
    )
    repeated = await store.confirm(
        tenant_id="tenant-a",
        operation_id="op-1",
        actual_cost=Decimal("0.008"),
        tokens_used=17,
    )

    assert confirmed.status == "confirmed"
    assert repeated.status == "confirmed"
    assert repeated.ledger_entry_count == 1
    ledger = await store.list_ledger(tenant_id="tenant-a", operation_id="op-1")
    assert [entry.to_status for entry in ledger] == ["confirmed"]
    outbox = await store.list_outbox(tenant_id="tenant-a", operation_id="op-1")
    assert [entry.action for entry in outbox] == ["usage.reserved", "usage.confirmed"]
    assert all(entry.payload["event_id"] == entry.id for entry in outbox)

    restarted = SqlUsageReservationStore(database_url, create_schema=True)
    persisted = await restarted.get(tenant_id="tenant-a", operation_id="op-1")
    assert persisted is not None
    assert persisted.status == "confirmed"
    assert persisted.actual_cost == Decimal("0.008")
    assert persisted.tokens_used == 17


class FlakyAuditStore:
    def __init__(self) -> None:
        self.calls = 0

    def record(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            raise OSError("audit unavailable")
        return SimpleNamespace(id=f"audit-{self.calls}")


@pytest.mark.asyncio
async def test_audit_delivery_failure_stays_pending_and_can_be_retried(tmp_path) -> None:
    audit = FlakyAuditStore()
    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}",
        create_schema=True,
        audit_store=audit,
    )
    reservation = await store.reserve(
        tenant_id="tenant-a",
        operation_id="op-audit",
        estimated_cost=Decimal("0.01"),
    )

    assert reservation.audit_status == "pending"
    pending = await store.list_outbox(
        tenant_id="tenant-a", operation_id="op-audit"
    )
    assert pending[0].status == "pending"
    assert pending[0].attempt_count == 1
    assert pending[0].last_error == "OSError"

    assert await store.deliver_pending() == 1
    delivered = await store.list_outbox(
        tenant_id="tenant-a", operation_id="op-audit"
    )
    assert delivered[0].status == "delivered"
    assert delivered[0].audit_id == "audit-2"


@pytest.mark.asyncio
async def test_competing_terminal_transitions_commit_exactly_one_ledger_entry(tmp_path) -> None:
    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}", create_schema=True
    )
    await store.reserve(
        tenant_id="tenant-a",
        operation_id="op-race",
        estimated_cost=Decimal("0.01"),
    )

    results = await __import__("asyncio").gather(
        store.confirm(
            "op-race",
            tenant_id="tenant-a",
            actual_cost=Decimal("0.005"),
            tokens_used=5,
        ),
        store.refund("op-race", tenant_id="tenant-a"),
        store.mark_submission_unknown("op-race", tenant_id="tenant-a"),
        return_exceptions=True,
    )

    assert sum(not isinstance(item, Exception) for item in results) == 1
    assert sum(isinstance(item, ReservationConflictError) for item in results) == 2
    ledger = await store.list_ledger(tenant_id="tenant-a", operation_id="op-race")
    assert len(ledger) == 1


@pytest.mark.asyncio
async def test_create_schema_false_never_auto_creates_missing_tables(tmp_path) -> None:
    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'missing.db').as_posix()}", create_schema=False
    )
    with pytest.raises(OperationalError):
        await store.get(tenant_id="tenant-a", operation_id="missing")


def test_production_factory_rejects_non_postgresql_without_fallback() -> None:
    settings = SimpleNamespace(
        app_mode="production", database_url="sqlite:///must-not-fallback.db"
    )
    with pytest.raises(RuntimeError, match="require PostgreSQL"):
        create_usage_reservation_store(settings)


@pytest.mark.asyncio
async def test_monthly_billing_uses_confirmed_cost_and_never_claims_paid(
    tmp_path, monkeypatch
) -> None:
    from backend.app.api import tenants

    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}", create_schema=True
    )
    for operation_id in ("confirmed", "refunded", "unknown"):
        await store.reserve(
            tenant_id="tenant-a",
            operation_id=operation_id,
            estimated_cost=Decimal("0.01"),
        )
    await store.confirm(
        "confirmed",
        tenant_id="tenant-a",
        actual_cost=Decimal("0.008"),
        tokens_used=8,
    )
    await store.refund("refunded", tenant_id="tenant-a")
    await store.mark_submission_unknown("unknown", tenant_id="tenant-a")
    monkeypatch.setattr(
        tenants.tenant_store,
        "get",
        lambda tenant_id: SimpleNamespace(id=tenant_id, plan="pro"),
    )
    principal = Principal(
        tenant_id="tenant-a",
        user_id="admin-a",
        role="admin",
        scopes=["security:manage"],
        authenticated=True,
    )

    payload = await tenants.get_tenant_billing(
        "tenant-a",
        principal,
        store,
        month=datetime.now(UTC).strftime("%Y-%m"),
    )

    assert payload["billing"]["usage_amount"] == 0.008
    assert payload["billing"]["confirmed_count"] == 1
    assert payload["billing"]["refunded_count"] == 1
    assert payload["billing"]["submission_unknown_count"] == 1
    assert payload["billing"]["status"] == "unsettled"

    other = await store.monthly_summary(
        tenant_id="tenant-b", month=datetime.now(UTC).strftime("%Y-%m")
    )
    assert other.reservation_count == 0


def test_default_agent_and_router_dependency_share_reservation_store(
    tmp_path, monkeypatch
) -> None:
    from backend.app import dependencies
    from backend.app.core import agent as agent_package

    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}", create_schema=True
    )
    settings = SimpleNamespace(
        llm_backend="mock",
        llm_fallback_order="mock",
        openai_api_key=None,
        openai_model="mock",
        openai_base_url=None,
        deepseek_api_key=None,
        deepseek_model="mock",
        deepseek_base_url="http://invalid.local",
        max_iterations=2,
    )
    cached_get_router = dependencies.get_llm_router
    cached_get_router.cache_clear()
    dependencies.get_agent.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    monkeypatch.setattr(dependencies, "get_usage_reservation_store", lambda: store)
    router = dependencies.get_llm_router()
    assert router.reservation_store is store

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            self.llm = kwargs["llm_router"]

    monkeypatch.setattr(agent_package, "AgentLoop", FakeAgent)
    monkeypatch.setattr(dependencies, "get_llm_router", lambda: router)
    monkeypatch.setattr(dependencies, "get_runtime_tool_registry", object)
    monkeypatch.setattr(dependencies, "get_memory", object)
    monkeypatch.setattr(dependencies, "get_trace_store", object)
    monkeypatch.setattr(dependencies, "get_run_store", object)
    monkeypatch.setattr(dependencies, "get_agent_context_manager", object)
    monkeypatch.setattr(dependencies, "get_unified_memory", object)
    agent = dependencies.get_agent()
    assert agent.llm is router
    dependencies.get_agent.cache_clear()
    cached_get_router.cache_clear()
