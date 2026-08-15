from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event, Lock
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import OperationalError

from backend.app.core.billing.reservations import (
    ReservationConflictError,
    SqlUsageReservationStore,
    UsageAuditOutboxModel,
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


@pytest.mark.asyncio
async def test_internal_and_billable_router_dependencies_are_explicitly_separate(
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
    cached_get_billable_router = dependencies.get_billable_llm_router
    cached_get_router.cache_clear()
    cached_get_billable_router.cache_clear()
    dependencies.get_agent.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    monkeypatch.setattr(dependencies, "get_usage_reservation_store", lambda: store)
    internal_router = dependencies.get_llm_router()
    assert internal_router.reservation_store is None
    assert (
        await internal_router.chat([{"role": "user", "content": "internal"}], [])
    ).content
    billable_router = dependencies.get_billable_llm_router()
    assert billable_router.reservation_store is store

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            self.llm = kwargs["llm_router"]

    monkeypatch.setattr(agent_package, "AgentLoop", FakeAgent)
    monkeypatch.setattr(
        dependencies, "get_billable_llm_router", lambda: billable_router
    )
    monkeypatch.setattr(dependencies, "get_runtime_tool_registry", object)
    monkeypatch.setattr(dependencies, "get_memory", object)
    monkeypatch.setattr(dependencies, "get_trace_store", object)
    monkeypatch.setattr(dependencies, "get_run_store", object)
    monkeypatch.setattr(dependencies, "get_agent_context_manager", object)
    monkeypatch.setattr(dependencies, "get_unified_memory", object)
    agent = dependencies.get_agent()
    assert agent.llm is billable_router
    dependencies.get_agent.cache_clear()
    cached_get_router.cache_clear()
    cached_get_billable_router.cache_clear()


@pytest.mark.asyncio
async def test_concurrent_outbox_delivery_claims_each_event_once(tmp_path) -> None:
    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}", create_schema=True
    )
    await store.reserve(
        tenant_id="tenant-a",
        operation_id="op-claim",
        estimated_cost=Decimal("0.01"),
    )

    class BlockingAudit:
        def __init__(self) -> None:
            self.calls = 0
            self.event_ids: list[str] = []
            self.started = Event()
            self.release = Event()
            self.lock = Lock()

        def record(self, **kwargs):
            with self.lock:
                self.calls += 1
                self.event_ids.append(kwargs["details"]["event_id"])
            self.started.set()
            self.release.wait(timeout=2)
            return SimpleNamespace(id="audit-claim")

    audit = BlockingAudit()
    first = asyncio.create_task(store.deliver_pending(audit))
    assert await asyncio.to_thread(audit.started.wait, 1)
    second = asyncio.create_task(store.deliver_pending(audit))
    await asyncio.sleep(0.05)
    audit.release.set()
    await asyncio.wait_for(asyncio.gather(first, second), timeout=2)

    assert audit.calls == 1
    assert len(set(audit.event_ids)) == 1
    outbox = await store.list_outbox(operation_id="op-claim")
    assert outbox[0].status == "delivered"


@pytest.mark.asyncio
async def test_expired_delivery_lease_retries_with_the_same_event_id(tmp_path) -> None:
    class MarkFailsOnceStore(SqlUsageReservationStore):
        fail_mark = True

        def _mark_outbox_delivered(self, *args):
            if self.fail_mark:
                self.fail_mark = False
                raise OSError("commit interrupted")
            return super()._mark_outbox_delivered(*args)

    store = MarkFailsOnceStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}", create_schema=True
    )
    await store.reserve(
        tenant_id="tenant-a",
        operation_id="op-lease",
        estimated_cost=Decimal("0.01"),
    )

    class Audit:
        def __init__(self) -> None:
            self.event_ids: list[str] = []

        def record(self, **kwargs):
            self.event_ids.append(kwargs["details"]["event_id"])
            return SimpleNamespace(id=f"audit-{len(self.event_ids)}")

    audit = Audit()
    with pytest.raises(OSError, match="commit interrupted"):
        await store.deliver_pending(audit, lease_seconds=0.01)
    interrupted = await store.list_outbox(operation_id="op-lease")
    assert interrupted[0].status == "delivering"
    await asyncio.sleep(0.02)
    assert await store.deliver_pending(audit, lease_seconds=0.01) == 1
    assert audit.event_ids == [interrupted[0].id, interrupted[0].id]


@pytest.mark.asyncio
async def test_outbox_retry_is_idempotent_in_real_audit_store(tmp_path, monkeypatch) -> None:
    from backend.app.core.audit import AuditStore

    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}",
        create_schema=True,
    )
    await store.reserve(
        tenant_id="tenant-a",
        user_id="user-a",
        operation_id="op-audit-idempotent",
        root_operation_id="root-audit-idempotent",
        provider="mock",
        model="mock-v1",
        estimated_cost=Decimal("0.001"),
    )
    await store.confirm(
        tenant_id="tenant-a",
        operation_id="op-audit-idempotent",
        actual_cost=Decimal("0.001"),
        tokens_used=3,
    )
    audit = AuditStore(storage_path=tmp_path / "audit.jsonl")
    real_mark = store._mark_outbox_delivered
    mark_calls = 0

    def fail_first_mark(*args, **kwargs):
        nonlocal mark_calls
        mark_calls += 1
        if mark_calls == 1:
            raise OSError("simulated mark crash")
        return real_mark(*args, **kwargs)

    monkeypatch.setattr(store, "_mark_outbox_delivered", fail_first_mark)
    with pytest.raises(OSError, match="mark crash"):
        await store.deliver_pending(audit, lease_seconds=0.01)
    assert audit.count() == 1

    await asyncio.sleep(0.02)
    assert await store.deliver_pending(audit, lease_seconds=0.01) == 2
    assert audit.count() == 2
    records = audit.list(resource_type="usage_reservation")
    assert {record.action for record in records} == {
        "usage.reserved",
        "usage.confirmed",
    }
    outbox = await store.list_outbox(operation_id="op-audit-idempotent")
    assert {record.id for record in records} == {entry.id for entry in outbox}
    assert all(entry.status == "delivered" for entry in outbox)


@pytest.mark.asyncio
async def test_cancelled_delivery_keeps_lease_for_same_event_retry(tmp_path) -> None:
    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}", create_schema=True
    )
    await store.reserve(
        tenant_id="tenant-a",
        operation_id="op-delivery-cancel",
        estimated_cost=Decimal("0.01"),
    )

    class BlockingAudit:
        def __init__(self) -> None:
            self.event_ids: list[str] = []
            self.started = Event()
            self.release = Event()

        def record(self, **kwargs):
            self.event_ids.append(kwargs["details"]["event_id"])
            self.started.set()
            self.release.wait(timeout=2)
            return SimpleNamespace(id="audit-after-cancel")

    audit = BlockingAudit()
    delivery = asyncio.create_task(
        store.deliver_pending(audit, lease_seconds=0.01)
    )
    assert await asyncio.to_thread(audit.started.wait, 1)
    delivery.cancel()
    with pytest.raises(asyncio.CancelledError):
        await delivery
    leased = await store.list_outbox(operation_id="op-delivery-cancel")
    assert leased[0].status == "delivering"
    audit.release.set()
    await asyncio.sleep(0.02)
    assert await store.deliver_pending(audit, lease_seconds=0.01) == 1
    assert audit.event_ids == [leased[0].id, leased[0].id]


def test_outbox_json_uses_postgresql_jsonb_variant() -> None:
    column_type = UsageAuditOutboxModel.__table__.c.payload.type
    assert isinstance(column_type.dialect_impl(postgresql.dialect()), JSONB)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "amount",
    ["NaN", "Infinity", "10000000000", "0.000000001"],
)
async def test_reserve_rejects_nonrepresentable_money_before_commit(
    tmp_path, amount
) -> None:
    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / f'{amount}.db').as_posix()}", create_schema=True
    )
    with pytest.raises(ValueError, match="estimated_cost"):
        await store.reserve(
            tenant_id="tenant-a",
            operation_id="invalid-money",
            estimated_cost=Decimal(amount),
        )
    assert await store.get(tenant_id="tenant-a", operation_id="invalid-money") is None


@pytest.mark.asyncio
async def test_confirm_rejects_nonrepresentable_money_and_stays_reserved(tmp_path) -> None:
    store = SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}", create_schema=True
    )
    await store.reserve(
        tenant_id="tenant-a",
        operation_id="invalid-confirm",
        estimated_cost=Decimal("0.01"),
    )
    with pytest.raises(ValueError, match="actual_cost"):
        await store.confirm(
            "invalid-confirm",
            tenant_id="tenant-a",
            actual_cost=Decimal("NaN"),
            tokens_used=1,
        )
    current = await store.get(tenant_id="tenant-a", operation_id="invalid-confirm")
    assert current is not None and current.status == "reserved"


@pytest.mark.asyncio
async def test_structured_endpoint_explicitly_uses_billable_router(monkeypatch) -> None:
    from backend.app import dependencies
    from backend.app.api import agents
    from backend.app.core.llm import LLMResponse

    class BillableRouter:
        calls: list[dict] = []

        async def chat(self, messages, tools, **kwargs):
            self.calls.append(kwargs)
            return LLMResponse(content='{"ok":true}', model="fake")

    billable = BillableRouter()
    monkeypatch.setattr(
        dependencies,
        "get_billable_llm_router",
        lambda: billable,
        raising=False,
    )

    def internal_router_must_not_be_used():
        raise AssertionError("structured endpoint used the internal router")

    monkeypatch.setattr(dependencies, "get_llm_router", internal_router_must_not_be_used)
    principal = Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=["agent:run"],
        authenticated=True,
    )
    payload = await agents.run_structured_output(
        {
            "operation_id": "structured-op-1",
            "prompt": "return ok",
            "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
        },
        principal,
    )
    assert payload["status"] == "completed"
    assert len(billable.calls) == 1
    assert billable.calls[0]["operation_id"] == "structured-op-1:strict"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation_id", [None, "", "x" * 249])
async def test_structured_endpoint_requires_bounded_operation_id_before_provider(
    monkeypatch,
    operation_id,
) -> None:
    from backend.app import dependencies
    from backend.app.api import agents
    from backend.app.api.errors import XAgentAPIError

    class ProviderMustNotRun:
        calls = 0

        async def chat(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("provider must not run")

    router = ProviderMustNotRun()
    monkeypatch.setattr(dependencies, "get_billable_llm_router", lambda: router)
    principal = Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=["agent:run"],
        authenticated=True,
    )
    request = {
        "prompt": "return ok",
        "schema": {"type": "object"},
    }
    if operation_id is not None:
        request["operation_id"] = operation_id

    with pytest.raises(XAgentAPIError) as caught:
        await agents.run_structured_output(request, principal)

    assert caught.value.status_code == 422
    assert caught.value.code.value == "validation_error"
    assert caught.value.message == "operation_id is required and must be at most 248 characters."
    assert router.calls == 0


@pytest.mark.asyncio
async def test_structured_endpoint_failure_is_sanitized(monkeypatch) -> None:
    from backend.app import dependencies
    from backend.app.api import agents
    from backend.app.api.errors import XAgentAPIError

    class FailingRouter:
        async def chat(self, *_args, **_kwargs):
            raise RuntimeError("database-password-should-not-leak")

    monkeypatch.setattr(dependencies, "get_billable_llm_router", lambda: FailingRouter())
    principal = Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=["agent:run"],
        authenticated=True,
    )

    with pytest.raises(XAgentAPIError) as caught:
        await agents.run_structured_output(
            {
                "operation_id": "structured-safe-error",
                "prompt": "return ok",
                "schema": {"type": "object"},
            },
            principal,
        )

    assert caught.value.status_code == 502
    assert caught.value.message == "Structured output generation failed."
    assert caught.value.details == {"error_code": "STRUCTURED_OUTPUT_FAILED"}


@pytest.mark.asyncio
async def test_structured_endpoint_replay_after_confirm_failure_does_not_call_provider(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app import dependencies
    from backend.app.api import agents
    from backend.app.api.errors import XAgentAPIError
    from backend.app.core.llm import BaseLLMBackend, LLMResponse, LLMRouter

    class ConfirmFailsStore(SqlUsageReservationStore):
        async def confirm(self, *args, **kwargs):
            raise OSError("database unavailable")

    class CountingBackend(BaseLLMBackend):
        name = "fake"
        model = "fake-v1"

        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools, *, response_format=None):
            self.calls += 1
            return LLMResponse(
                content='{"ok":true}',
                model=self.model,
                tokens_used=3,
                cost=0.001,
            )

    store = ConfirmFailsStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}",
        create_schema=True,
    )
    backend = CountingBackend()
    router = LLMRouter(backends=[backend], reservation_store=store)
    monkeypatch.setattr(dependencies, "get_billable_llm_router", lambda: router)
    principal = Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=["agent:run"],
        authenticated=True,
    )
    request = {
        "operation_id": "structured-confirm-failure",
        "prompt": "return ok",
        "schema": {"type": "object"},
    }

    with pytest.raises(XAgentAPIError) as first:
        await agents.run_structured_output(request, principal)
    with pytest.raises(XAgentAPIError) as replay:
        await agents.run_structured_output(request, principal)

    assert first.value.status_code == 502
    assert replay.value.status_code == 409
    assert replay.value.code.value == "resource_conflict"
    assert replay.value.message == "Structured operation cannot be replayed."
    assert replay.value.details == {"error_code": "STRUCTURED_OPERATION_CONFLICT"}
    assert backend.calls == 1


@pytest.mark.parametrize("operation_id", [None, "", "x" * 221])
def test_ultra_request_requires_bounded_operation_id_before_provider(
    operation_id,
    monkeypatch,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app import dependencies
    from backend.app.api.parallel_agents import router
    from backend.app.dependencies import get_current_principal

    class ProviderMustNotRun:
        calls = 0

        async def chat(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("provider must not run")

    provider = ProviderMustNotRun()
    monkeypatch.setattr(dependencies, "get_billable_llm_router", lambda: provider)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=["agent:run"],
        authenticated=True,
    )
    request = {"task": "ship safely"}
    if operation_id is not None:
        request["operation_id"] = operation_id

    with TestClient(app) as client:
        response = client.post("/api/v1/agents/parallel/ultra", json=request)

    assert response.status_code == 422
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_ultra_endpoint_uses_billable_router_with_stable_stage_correlation(
    monkeypatch,
) -> None:
    from backend.app import dependencies
    from backend.app.api import parallel_agents
    from backend.app.api.parallel_agents import UltraRequest
    from backend.app.core.llm import LLMResponse
    from backend.app.settings import get_settings

    settings = get_settings()

    class RecordingRouter:
        def __init__(self):
            self.calls = []

        async def chat(self, messages, tools, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return LLMResponse(
                    content=(
                        '[{"description":"one","focus_area":"a"},'
                        '{"description":"two","focus_area":"b"}]'
                    ),
                    model="fake",
                )
            return LLMResponse(content="merged", model="fake")

    class RecordingAgent:
        def __init__(self):
            self.contexts = []

        async def run(self, context, task, metadata):
            self.contexts.append(context)
            return SimpleNamespace(answer=f"done:{task}")

    router = RecordingRouter()
    agent = RecordingAgent()
    monkeypatch.setattr(dependencies, "get_billable_llm_router", lambda: router)
    monkeypatch.setattr(dependencies, "get_agent", lambda: agent)
    monkeypatch.setattr(
        dependencies,
        "get_llm_router",
        lambda: (_ for _ in ()).throw(AssertionError("internal router used")),
    )
    monkeypatch.setattr(settings, "ultra_mode_enabled", True)
    monkeypatch.setattr(settings, "ultra_max_agents", 4)
    principal = Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        role="user",
        scopes=["agent:run"],
        authenticated=True,
    )

    result = await parallel_agents.ultra_execute(
        UltraRequest(task="one;two", operation_id="ultra-operation-1"),
        principal,
    )

    assert result["status"] == "completed"
    assert [call["operation_id"] for call in router.calls] == [
        "ultra-operation-1:decompose",
        "ultra-operation-1:merge",
    ]
    correlation = {
        key: router.calls[0][key]
        for key in ("tenant_id", "user_id", "run_id", "trace_id")
    }
    assert correlation["tenant_id"] == "tenant-a"
    assert correlation["user_id"] == "user-a"
    assert correlation["run_id"] == correlation["trace_id"]
    assert router.calls[1] | correlation == router.calls[1]
    assert len(agent.contexts) == 2
    assert all(context.trace_id == correlation["trace_id"] for context in agent.contexts)
    assert all(context.tenant_id == "tenant-a" for context in agent.contexts)


def test_goals_resources_are_owner_scoped(tmp_path, monkeypatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.api import goals
    from backend.app.dependencies import get_current_principal

    tenant_a = Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=["agent:read", "agent:run"],
        authenticated=True,
    )
    tenant_b = Principal(
        tenant_id="tenant-b",
        user_id="user-b",
        role="user",
        scopes=["agent:read", "agent:run"],
        authenticated=True,
    )
    other_user = Principal(
        tenant_id="tenant-a",
        user_id="user-b",
        role="user",
        scopes=["agent:read", "agent:run"],
        authenticated=True,
    )
    monkeypatch.setattr(goals._store, "_path", tmp_path / "goals.json")
    goals._goals.clear()
    app = FastAPI()
    app.include_router(goals.router)
    app.dependency_overrides[get_current_principal] = lambda: tenant_a

    with TestClient(app) as client:
        created = client.post("/api/v1/goals", json={"objective": "private goal"})
        assert created.status_code == 200
        goal_id = created.json()["id"]
        assert goals._goals[0]["tenant_id"] == "tenant-a"
        assert goals._goals[0]["user_id"] == "user-a"

        for foreign in (tenant_b, other_user):
            app.dependency_overrides[get_current_principal] = (
                lambda foreign=foreign: foreign
            )
            assert client.get("/api/v1/goals").json() == []
            assert client.get(f"/api/v1/goals/{goal_id}").status_code == 404
            assert client.post(f"/api/v1/goals/{goal_id}/start").status_code == 404
            assert client.post(f"/api/v1/goals/{goal_id}/complete").status_code == 404
            assert client.post(f"/api/v1/goals/{goal_id}/pause").status_code == 404
            assert client.post(f"/api/v1/goals/{goal_id}/resume").status_code == 404
            assert client.post(f"/api/v1/goals/{goal_id}/cancel").status_code == 404
            assert client.get(f"/api/v1/goals/{goal_id}/history").status_code == 404
    goals._goals.clear()


def test_goal_api_wires_only_billable_router(monkeypatch) -> None:
    from backend.app import dependencies
    from backend.app.api import goals

    billable = object()
    agent = object()
    monkeypatch.setattr(goals, "_orchestrator_wired", False)
    monkeypatch.setattr(goals.goal_orchestrator, "llm_router", None)
    monkeypatch.setattr(goals.goal_orchestrator, "agent_loop", None)
    monkeypatch.setattr(dependencies, "get_billable_llm_router", lambda: billable)
    monkeypatch.setattr(dependencies, "get_agent", lambda: agent)
    monkeypatch.setattr(
        dependencies,
        "get_llm_router",
        lambda: (_ for _ in ()).throw(AssertionError("internal router used")),
    )

    goals._wire_orchestrator()

    assert goals.goal_orchestrator.llm_router is billable
    assert goals.goal_orchestrator.agent_loop is agent


@pytest.mark.asyncio
async def test_goal_decompose_uses_stable_owner_correlation_and_propagates_billing_errors() -> None:
    from backend.app.core.goal_mode import GoalModeOrchestrator
    from backend.app.core.llm import LLMReplayBlockedError, LLMResponse

    context = {
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "goal_id": "goal-1",
        "run_id": "goal-1",
        "trace_id": "goal-1",
    }

    class RecordingRouter:
        calls = []

        async def chat(self, messages, tools, **kwargs):
            self.calls.append(kwargs)
            return LLMResponse(content='["step one"]', model="fake")

    router = RecordingRouter()
    result = await GoalModeOrchestrator(llm_router=router).execute_goal(
        "ship",
        context=context,
        goal_id="goal-1",
    )
    assert result.status == "completed"
    assert router.calls == [{
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "run_id": "goal-1",
        "trace_id": "goal-1",
        "operation_id": "goal-1:decompose",
    }]

    class ReplayRouter:
        async def chat(self, messages, tools, **kwargs):
            raise LLMReplayBlockedError("must not downgrade")

    with pytest.raises(LLMReplayBlockedError):
        await GoalModeOrchestrator(llm_router=ReplayRouter()).execute_goal(
            "ship",
            context=context,
            goal_id="goal-1",
        )
