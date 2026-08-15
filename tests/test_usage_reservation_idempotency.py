from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from backend.app.core.billing.reservations import (
    ReservationConflictError,
    SqlUsageReservationStore,
)
from backend.app.core.llm import (
    AnthropicBackend,
    BaseLLMBackend,
    LLMBackendError,
    LLMReplayBlockedError,
    LLMReservationPersistenceError,
    LLMResponse,
    LLMRouter,
    LLMSubmissionUnknownError,
    OpenAIBackend,
)


class FakeBackend(BaseLLMBackend):
    def __init__(self, name: str, result: LLMResponse | Exception) -> None:
        self.name = name
        self.model = f"{name}-v1"
        self.result = result
        self.calls = 0

    async def chat(self, messages, tools, *, response_format=None) -> LLMResponse:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _store(tmp_path) -> SqlUsageReservationStore:
    return SqlUsageReservationStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}",
        create_schema=True,
    )


@pytest.mark.asyncio
async def test_concurrent_reserve_is_idempotent_but_parameter_drift_conflicts(tmp_path) -> None:
    store = _store(tmp_path)
    kwargs = {
        "tenant_id": "tenant-a",
        "operation_id": "op-1",
        "root_operation_id": "root-1",
        "provider": "mock",
        "model": "mock-v1",
        "estimated_cost": Decimal("0.01"),
    }

    first, second = await asyncio.gather(store.reserve(**kwargs), store.reserve(**kwargs))
    assert {first.created, second.created} == {False, True}

    with pytest.raises(ReservationConflictError):
        await store.reserve(**{**kwargs, "model": "different"})
    assert await store.get(tenant_id="tenant-b", operation_id="op-1") is None


@pytest.mark.asyncio
async def test_router_refunds_explicit_failure_before_fallback_and_confirms_success(tmp_path) -> None:
    store = _store(tmp_path)
    failed = FakeBackend("first", LLMBackendError("explicit rejection"))
    succeeded = FakeBackend(
        "second",
        LLMResponse(content="ok", tokens_used=11, cost=0.004, model="second-v1"),
    )
    router = LLMRouter(backends=[failed, succeeded], reservation_store=store)

    response = await router.chat(
        [{"role": "user", "content": "hello"}],
        [],
        tenant_id="tenant-a",
        user_id="user-a",
        operation_id="chat-1",
        run_id="run-1",
        trace_id="trace-1",
    )

    assert response.content == "ok"
    attempts = await store.list_for_root(tenant_id="tenant-a", root_operation_id="chat-1")
    assert [item.status for item in attempts] == ["refunded", "confirmed"]
    assert all(item.run_id == "run-1" for item in attempts)
    assert all(item.trace_id == "trace-1" for item in attempts)
    assert failed.calls == 1
    assert succeeded.calls == 1


@pytest.mark.asyncio
async def test_router_marks_ambiguous_submission_unknown_without_fallback(tmp_path) -> None:
    store = _store(tmp_path)
    ambiguous = FakeBackend("first", LLMSubmissionUnknownError("socket closed"))
    fallback = FakeBackend("second", LLMResponse(content="must not run"))
    router = LLMRouter(backends=[ambiguous, fallback], reservation_store=store)

    with pytest.raises(LLMSubmissionUnknownError):
        await router.chat(
            [{"role": "user", "content": "hello"}],
            [],
            tenant_id="tenant-a",
            user_id="user-a",
            operation_id="chat-unknown",
            run_id="run-2",
            trace_id="trace-2",
        )

    attempts = await store.list_for_root(
        tenant_id="tenant-a", root_operation_id="chat-unknown"
    )
    assert [item.status for item in attempts] == ["submission_unknown"]
    assert ambiguous.calls == 1
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_openai_uses_hard_output_limit_and_never_retries_timeout() -> None:
    class FakeCompletions:
        def __init__(self, result) -> None:
            self.result = result
            self.calls: list[dict] = []

        async def create(self, **kwargs):
            self.calls.append(kwargs)
            if isinstance(self.result, Exception):
                raise self.result
            return self.result

    success_api = FakeCompletions(SimpleResponse())
    backend = OpenAIBackend("fake-key", "fake-model", max_output_tokens=321)
    backend._client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": success_api})()},
    )()
    await backend.chat([{"role": "user", "content": "hello"}], [])
    assert success_api.calls[0]["max_tokens"] == 321

    timeout_api = FakeCompletions(TimeoutError("ambiguous"))
    backend._client = type(
        "Client",
        (),
        {"chat": type("Chat", (), {"completions": timeout_api})()},
    )()
    with pytest.raises(LLMSubmissionUnknownError):
        await backend.chat([{"role": "user", "content": "hello"}], [])
    assert len(timeout_api.calls) == 1


@pytest.mark.asyncio
async def test_anthropic_timeout_is_unknown_and_router_does_not_fallback(tmp_path) -> None:
    class FakeMessages:
        def __init__(self) -> None:
            self.calls = 0

        async def create(self, **_kwargs):
            self.calls += 1
            raise TimeoutError("ambiguous")

    messages_api = FakeMessages()
    anthropic = AnthropicBackend("fake-key", "fake-model")
    anthropic._client = type("Client", (), {"messages": messages_api})()
    fallback = FakeBackend("fallback", LLMResponse(content="must not run"))
    store = _store(tmp_path)
    router = LLMRouter(backends=[anthropic, fallback], reservation_store=store)

    with pytest.raises(LLMSubmissionUnknownError):
        await router.chat(
            [{"role": "user", "content": "hello"}],
            [],
            tenant_id="tenant-a",
            operation_id="chat-anthropic-timeout",
        )
    attempts = await store.list_for_root(
        tenant_id="tenant-a", root_operation_id="chat-anthropic-timeout"
    )
    assert [item.status for item in attempts] == ["submission_unknown"]
    assert messages_api.calls == 1
    assert fallback.calls == 0


class SimpleResponse:
    choices = []
    usage = None


@pytest.mark.asyncio
async def test_existing_reserved_attempt_blocks_provider_replay(tmp_path) -> None:
    store = _store(tmp_path)
    backend = FakeBackend("mock", LLMResponse(content="must not run"))
    router = LLMRouter(backends=[backend], reservation_store=store)
    operation_id = router.provider_attempt_id("chat-replay", 0, backend)
    await store.reserve(
        tenant_id="tenant-a",
        operation_id=operation_id,
        root_operation_id="chat-replay",
        provider=backend.name,
        model=backend.model,
        estimated_cost=Decimal("0"),
        request_payload={"messages": [{"role": "user", "content": "hello"}], "tools": []},
    )

    with pytest.raises(LLMReplayBlockedError):
        await router.chat(
            [{"role": "user", "content": "hello"}],
            [],
            tenant_id="tenant-a",
            operation_id="chat-replay",
        )
    assert backend.calls == 0


@pytest.mark.asyncio
async def test_database_failure_after_provider_success_prevents_replay(tmp_path) -> None:
    class ConfirmFailsStore(SqlUsageReservationStore):
        async def confirm(self, *args, **kwargs):
            raise OSError("database unavailable")

    store = ConfirmFailsStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}", create_schema=True
    )
    backend = FakeBackend(
        "mock", LLMResponse(content="accepted", tokens_used=3, cost=0.001)
    )
    router = LLMRouter(backends=[backend], reservation_store=store)
    request = {
        "tenant_id": "tenant-a",
        "operation_id": "chat-db-failure",
    }

    with pytest.raises(
        LLMReservationPersistenceError,
        match="settlement could not be persisted",
    ):
        await router.chat([{"role": "user", "content": "hello"}], [], **request)
    with pytest.raises(LLMReplayBlockedError):
        await router.chat([{"role": "user", "content": "hello"}], [], **request)
    assert backend.calls == 1


@pytest.mark.asyncio
async def test_raw_timeout_is_unknown_and_never_falls_back(tmp_path) -> None:
    store = _store(tmp_path)
    ambiguous = FakeBackend("first", TimeoutError("timed out"))
    fallback = FakeBackend("second", LLMResponse(content="must not run"))
    router = LLMRouter(backends=[ambiguous, fallback], reservation_store=store)

    with pytest.raises(LLMSubmissionUnknownError):
        await router.chat(
            [{"role": "user", "content": "hello"}],
            [],
            tenant_id="tenant-a",
            operation_id="chat-timeout",
        )
    attempts = await store.list_for_root(
        tenant_id="tenant-a", root_operation_id="chat-timeout"
    )
    assert [item.status for item in attempts] == ["submission_unknown"]
    assert fallback.calls == 0
