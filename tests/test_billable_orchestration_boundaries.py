from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.api import parallel_agents
from backend.app.core.contracts import RunContext
from backend.app.core.llm import (
    LLMReplayBlockedError,
    LLMReservationPersistenceError,
    LLMResponse,
    LLMSubmissionUnknownError,
)
from backend.app.core.parallel_agent_executor import (
    AgentResult,
    ParallelAgentOrchestrator,
)
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal


def _principal() -> Principal:
    return Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
        role="user",
        scopes=["agent:run"],
        authenticated=True,
    )


def _billing_context() -> dict[str, str]:
    return {
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "operation_id": "parallel-op-1",
        "run_id": "parallel-run-1",
        "trace_id": "parallel-run-1",
    }


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/v1/agents/parallel/orchestrator/fan-out",
            {"task": "parent", "subtasks": ["child"]},
        ),
        (
            "/api/v1/agents/parallel/orchestrator/fan-in",
            {"results": [{"status": "completed", "output": "ok"}]},
        ),
        (
            "/api/v1/agents/parallel/orchestrator/pipeline",
            {"stages": ["one"]},
        ),
        (
            "/api/v1/agents/parallel/orchestrator/fan-out",
            {"operation_id": "", "task": "parent", "subtasks": ["child"]},
        ),
        (
            "/api/v1/agents/parallel/orchestrator/fan-out",
            {
                "operation_id": "x" * 221,
                "task": "parent",
                "subtasks": ["child"],
            },
        ),
    ],
)
def test_parallel_orchestrator_requests_require_operation_id_before_provider(
    path: str,
    payload: dict,
) -> None:
    provider_calls = 0

    class ProviderMustNotRun:
        async def execute_fan_out(self, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return []

        async def execute_fan_in(self, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return AgentResult(status="completed", output="ok")

        async def execute_pipeline(self, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return AgentResult(status="completed", output="ok")

    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.include_router(parallel_agents.extended_router)
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=["agent:run"],
        authenticated=True,
    )
    app.dependency_overrides[
        parallel_agents.get_orchestrator
    ] = ProviderMustNotRun

    with TestClient(app) as client:
        response = client.post(path, json=payload)

    assert response.status_code == 422
    assert provider_calls == 0


@pytest.mark.parametrize(
    ("path", "payload", "method_name"),
    [
        (
            "/api/v1/agents/parallel/orchestrator/fan-out",
            {
                "operation_id": "parallel-op-1",
                "task": "parent",
                "subtasks": ["child"],
            },
            "execute_fan_out",
        ),
        (
            "/api/v1/agents/parallel/orchestrator/fan-in",
            {
                "operation_id": "parallel-op-1",
                "results": [{"status": "completed", "output": "ok"}],
            },
            "execute_fan_in",
        ),
        (
            "/api/v1/agents/parallel/orchestrator/pipeline",
            {"operation_id": "parallel-op-1", "stages": ["one"]},
            "execute_pipeline",
        ),
    ],
)
def test_parallel_endpoints_pass_stable_billing_context(
    path: str,
    payload: dict,
    method_name: str,
) -> None:
    calls: list[dict] = []

    class RecordingOrchestrator:
        async def execute_fan_out(self, **kwargs):
            calls.append(kwargs)
            return []

        async def execute_fan_in(self, **kwargs):
            calls.append(kwargs)
            return AgentResult(status="completed", output="ok")

        async def execute_pipeline(self, **kwargs):
            calls.append(kwargs)
            return AgentResult(status="completed", output="ok")

    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.include_router(parallel_agents.extended_router)
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=["agent:run"],
        authenticated=True,
    )
    app.dependency_overrides[
        parallel_agents.get_orchestrator
    ] = RecordingOrchestrator

    with TestClient(app) as client:
        response = client.post(path, json=payload)

    assert response.status_code == 200
    assert len(calls) == 1
    assert method_name in {"execute_fan_out", "execute_fan_in", "execute_pipeline"}
    context = calls[0]["billing_context"]
    assert context["tenant_id"] == "tenant-a"
    assert context["user_id"] == "user-a"
    assert context["operation_id"] == "parallel-op-1"
    assert context["run_id"] == context["trace_id"]
    assert context["run_id"].startswith("parallel-")


def test_parallel_orchestrator_getter_uses_only_billable_router(monkeypatch) -> None:
    from backend.app import dependencies

    billable = object()
    monkeypatch.setattr(parallel_agents, "_orchestrator", None)
    monkeypatch.setattr(dependencies, "get_billable_llm_router", lambda: billable)
    monkeypatch.setattr(
        dependencies,
        "get_llm_router",
        lambda: (_ for _ in ()).throw(AssertionError("internal router used")),
    )

    orchestrator = parallel_agents.get_orchestrator()

    assert orchestrator.llm_router is billable


@pytest.mark.asyncio
async def test_parallel_core_passes_stable_stage_operations_to_llm(
    monkeypatch,
) -> None:
    calls: list[dict] = []

    class NoAgentLoop:
        def __init__(self, **_kwargs):
            raise ImportError("use direct fake router")

    class RecordingRouter:
        async def chat(self, messages, tools, **kwargs):
            calls.append(kwargs)
            return LLMResponse(content="ok", model="fake")

    monkeypatch.setattr("backend.app.core.agent.loop.AgentLoop", NoAgentLoop)
    orchestrator = ParallelAgentOrchestrator(llm_router=RecordingRouter())
    context = _billing_context()

    await orchestrator.execute_fan_out(
        "parent",
        ["child-a", "child-b"],
        billing_context=context,
    )
    await orchestrator.execute_fan_in(
        [
            AgentResult(status="completed", output="one"),
            AgentResult(status="completed", output="two"),
        ],
        billing_context=context,
    )
    await orchestrator.execute_pipeline(
        ["stage-a", "stage-b"],
        billing_context=context,
    )

    assert [call["operation_id"] for call in calls] == [
        "parallel-op-1:fanout:0",
        "parallel-op-1:fanout:1",
        "parallel-op-1:fanin:merge",
        "parallel-op-1:pipeline:0",
        "parallel-op-1:pipeline:1",
    ]
    assert all(call["tenant_id"] == "tenant-a" for call in calls)
    assert all(call["user_id"] == "user-a" for call in calls)
    assert all(call["run_id"] == call["trace_id"] == "parallel-run-1" for call in calls)


@pytest.mark.asyncio
async def test_parallel_core_agent_loop_receives_real_run_context(
    monkeypatch,
) -> None:
    contexts: list[RunContext] = []
    metadata: list[dict] = []

    class RecordingLoop:
        def __init__(self, **_kwargs):
            pass

        async def run(self, context, task, extra_context=None):
            contexts.append(context)
            metadata.append(extra_context or {})
            return SimpleNamespace(answer=f"done:{task}")

    monkeypatch.setattr("backend.app.core.agent.loop.AgentLoop", RecordingLoop)
    orchestrator = ParallelAgentOrchestrator(llm_router=object())

    result = await orchestrator.execute_pipeline(
        ["stage"],
        billing_context=_billing_context(),
    )

    assert result.status == "completed"
    assert result.output == "done:stage"
    assert len(contexts) == 1
    assert isinstance(contexts[0], RunContext)
    assert contexts[0].trace_id == "parallel-run-1"
    assert contexts[0].tenant_id == "tenant-a"
    assert contexts[0].user_id == "user-a"
    assert metadata[0]["operation_id"] == "parallel-op-1:pipeline:0"


@pytest.mark.parametrize("pattern", ["fan_out", "fan_in", "pipeline"])
@pytest.mark.asyncio
async def test_parallel_core_never_swallows_billing_control_errors(
    monkeypatch,
    pattern: str,
) -> None:
    class BillingFailureLoop:
        def __init__(self, **_kwargs):
            pass

        async def run(self, *_args, **_kwargs):
            raise LLMSubmissionUnknownError("provider-secret")

    class BillingFailureRouter:
        def __init__(self):
            self.calls = 0

        async def chat(self, *_args, **_kwargs):
            self.calls += 1
            raise LLMSubmissionUnknownError("provider-secret")

    monkeypatch.setattr(
        "backend.app.core.agent.loop.AgentLoop",
        BillingFailureLoop,
    )
    router = BillingFailureRouter()
    orchestrator = ParallelAgentOrchestrator(llm_router=router)

    with pytest.raises(LLMSubmissionUnknownError):
        if pattern == "fan_out":
            await orchestrator.execute_fan_out(
                "parent",
                ["child"],
                billing_context=_billing_context(),
            )
        elif pattern == "fan_in":
            await orchestrator.execute_fan_in(
                [
                    AgentResult(status="completed", output="one"),
                    AgentResult(status="completed", output="two"),
                ],
                billing_context=_billing_context(),
            )
        else:
            await orchestrator.execute_pipeline(
                ["stage"],
                billing_context=_billing_context(),
            )
    assert router.calls == (1 if pattern == "fan_in" else 0)


@pytest.mark.asyncio
async def test_parallel_core_generic_failures_are_sanitized(
    monkeypatch,
    caplog,
) -> None:
    class GenericFailureLoop:
        def __init__(self, **_kwargs):
            pass

        async def run(self, *_args, **_kwargs):
            raise RuntimeError("parallel-provider-secret")

    class GenericFailureRouter:
        async def chat(self, *_args, **_kwargs):
            raise RuntimeError("parallel-provider-secret")

    monkeypatch.setattr(
        "backend.app.core.agent.loop.AgentLoop",
        GenericFailureLoop,
    )
    orchestrator = ParallelAgentOrchestrator(llm_router=GenericFailureRouter())

    fan_out = await orchestrator.execute_fan_out(
        "parent",
        ["child"],
        billing_context=_billing_context(),
    )
    pipeline = await orchestrator.execute_pipeline(
        ["stage"],
        billing_context=_billing_context(),
    )

    assert fan_out[0].status == "failed"
    assert fan_out[0].error == "Agent execution failed."
    assert pipeline.status == "failed"
    assert pipeline.error == "Pipeline stage execution failed."
    assert "parallel-provider-secret" not in str(fan_out[0].to_dict())
    assert "parallel-provider-secret" not in str(pipeline.to_dict())
    assert "parallel-provider-secret" not in caplog.text


@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (LLMReplayBlockedError("provider-secret"), 409, "LLM_REPLAY_BLOCKED"),
        (
            LLMReservationPersistenceError("provider-secret"),
            503,
            "LLM_RESERVATION_PERSISTENCE_FAILED",
        ),
        (
            LLMSubmissionUnknownError("provider-secret"),
            502,
            "LLM_SUBMISSION_UNKNOWN",
        ),
        (RuntimeError("provider-secret"), 500, "PARALLEL_ORCHESTRATION_FAILED"),
    ],
)
def test_parallel_api_maps_errors_without_secret_leakage(
    error: Exception,
    status_code: int,
    error_code: str,
    caplog,
) -> None:
    class FailingOrchestrator:
        async def execute_fan_out(self, **_kwargs):
            raise error

    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[
        parallel_agents.get_orchestrator
    ] = FailingOrchestrator

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/parallel/orchestrator/fan-out",
            json={
                "operation_id": "parallel-op-1",
                "task": "parent",
                "subtasks": ["child"],
            },
        )

    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == error_code
    assert "provider-secret" not in response.text
    assert "provider-secret" not in caplog.text


@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (LLMReplayBlockedError("ultra-secret"), 409, "LLM_REPLAY_BLOCKED"),
        (
            LLMReservationPersistenceError("ultra-secret"),
            503,
            "LLM_RESERVATION_PERSISTENCE_FAILED",
        ),
        (
            LLMSubmissionUnknownError("ultra-secret"),
            502,
            "LLM_SUBMISSION_UNKNOWN",
        ),
        (RuntimeError("ultra-secret"), 500, "ULTRA_EXECUTION_FAILED"),
    ],
)
def test_ultra_api_maps_errors_without_secret_leakage(
    monkeypatch,
    error: Exception,
    status_code: int,
    error_code: str,
    caplog,
) -> None:
    from backend.app import dependencies
    from backend.app.core.ultra_mode import UltraOrchestrator
    from backend.app.settings import get_settings

    async def fail_execute(self, *_args, **_kwargs):
        raise error

    settings = get_settings()
    monkeypatch.setattr(settings, "ultra_mode_enabled", True)
    monkeypatch.setattr(dependencies, "get_agent", lambda: object())
    monkeypatch.setattr(
        dependencies,
        "get_billable_llm_router",
        lambda: object(),
    )
    monkeypatch.setattr(UltraOrchestrator, "execute", fail_execute)
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/parallel/ultra",
            json={"operation_id": "ultra-op-1", "task": "do work"},
        )

    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == error_code
    assert "ultra-secret" not in response.text
    assert "ultra-secret" not in caplog.text


@pytest.mark.asyncio
async def test_ultra_agent_billing_error_reaches_api_boundary() -> None:
    from backend.app.core.ultra_mode import UltraConfig, UltraOrchestrator

    class DecomposeRouter:
        async def chat(self, *_args, **_kwargs):
            return LLMResponse(
                content='[{"description":"child","focus_area":"safe"}]',
                model="fake",
            )

    async def fail_agent(*_args, **_kwargs):
        raise LLMSubmissionUnknownError("ultra-agent-secret")

    orchestrator = UltraOrchestrator(
        agent_factory=fail_agent,
        llm_router=DecomposeRouter(),
    )

    with pytest.raises(LLMSubmissionUnknownError):
        await orchestrator.execute(
            "parent",
            {
                "tenant_id": "tenant-a",
                "user_id": "user-a",
                "operation_id": "ultra-op-1",
                "run_id": "ultra-run-1",
                "trace_id": "ultra-run-1",
            },
            UltraConfig(max_agents=2),
        )


def _goal_record(status: str = "running") -> dict:
    from backend.app.core.goal_mode import GoalControl

    return {
        "id": "goal-test",
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "objective": "ship safely",
        "status": status,
        "progress": [],
        "output": "",
        "events": [],
        "control": GoalControl(),
        "result": None,
        "attempt_count": 1,
        "active_attempt_id": "goal-test:attempt-1",
        "created_at": 1.0,
        "updated_at": 1.0,
    }


@pytest.mark.parametrize(
    ("error", "expected_status", "error_code"),
    [
        (
            LLMReplayBlockedError("goal-secret"),
            "needs_attention",
            "LLM_REPLAY_BLOCKED",
        ),
        (
            LLMReservationPersistenceError("goal-secret"),
            "needs_attention",
            "LLM_RESERVATION_PERSISTENCE_FAILED",
        ),
        (
            LLMSubmissionUnknownError("goal-secret"),
            "needs_attention",
            "LLM_SUBMISSION_UNKNOWN",
        ),
        (RuntimeError("goal-secret"), "failed", "GOAL_EXECUTION_FAILED"),
    ],
)
@pytest.mark.asyncio
async def test_goal_background_errors_are_sanitized_and_classified(
    monkeypatch,
    error: Exception,
    expected_status: str,
    error_code: str,
    caplog,
) -> None:
    from backend.app.api import goals

    async def fail_goal(*_args, **_kwargs):
        raise error

    goal = _goal_record()
    monkeypatch.setattr(goals, "_orchestrator_wired", True)
    monkeypatch.setattr(goals.goal_orchestrator, "execute_goal", fail_goal)
    monkeypatch.setattr(goals, "_persist", lambda: None)

    await goals._run_goal(goal)

    assert goal["status"] == expected_status
    assert goal["error_code"] == error_code
    assert "goal-secret" not in goal["output"]
    assert "goal-secret" not in str(goal["events"])
    assert "goal-secret" not in caplog.text


@pytest.mark.asyncio
async def test_goal_attempt_context_is_stable_and_failure_can_restart(
    monkeypatch,
) -> None:
    from backend.app.api import goals
    from backend.app.core.goal_mode import GoalResult

    contexts: list[dict] = []

    async def record_goal(*_args, **kwargs):
        contexts.append(kwargs["context"])
        return GoalResult(goal_id="goal-test", status="failed")

    goal = _goal_record(status="failed")
    goal["attempt_count"] = 0
    goal["active_attempt_id"] = None
    principal = _principal()
    monkeypatch.setattr(goals, "_orchestrator_wired", True)
    monkeypatch.setattr(goals.goal_orchestrator, "execute_goal", record_goal)
    monkeypatch.setattr(goals, "_persist", lambda: None)
    monkeypatch.setattr(goals, "_goals", [goal])

    first = await goals.start_goal("goal-test", principal)
    assert first["attempt_count"] == 1
    await goals._tasks["goal-test"]
    assert goal["status"] == "failed"

    second = await goals.start_goal("goal-test", principal)
    assert second["attempt_count"] == 2
    await goals._tasks["goal-test"]

    assert [context["operation_id"] for context in contexts] == [
        "goal-test:attempt-1",
        "goal-test:attempt-2",
    ]
    assert [context["run_id"] for context in contexts] == [
        "goal-test:attempt-1",
        "goal-test:attempt-2",
    ]
    assert all(context["run_id"] == context["trace_id"] for context in contexts)


@pytest.mark.asyncio
async def test_goal_concurrent_start_increments_once_and_attention_blocks_restart(
    monkeypatch,
) -> None:
    import asyncio

    from backend.app.api import goals

    release = asyncio.Event()

    async def blocked_run(_goal):
        await release.wait()

    goal = _goal_record(status="active")
    goal["attempt_count"] = 0
    goal["active_attempt_id"] = None
    principal = _principal()
    monkeypatch.setattr(goals, "_persist", lambda: None)
    monkeypatch.setattr(goals, "_goals", [goal])
    monkeypatch.setattr(goals, "_run_goal", blocked_run)

    async def call_start():
        try:
            return (await goals.start_goal("goal-test", principal))["status"]
        except HTTPException as exc:
            return exc.status_code

    results = await asyncio.gather(call_start(), call_start())
    assert sorted(results, key=str) == [409, "running"]
    assert goal["attempt_count"] == 1
    release.set()
    await goals._tasks["goal-test"]
    goals._tasks.pop("goal-test", None)

    goal["status"] = "needs_attention"
    with pytest.raises(HTTPException) as blocked:
        await goals.start_goal("goal-test", principal)
    assert blocked.value.status_code == 409
    assert goal["attempt_count"] == 1
    with pytest.raises(HTTPException) as false_completion:
        await goals.complete_goal("goal-test", principal)
    assert false_completion.value.status_code == 409
    assert goal["status"] == "needs_attention"


@pytest.mark.parametrize("status", ["failed", "timeout", "cancelled"])
@pytest.mark.asyncio
async def test_goal_ordinary_terminal_statuses_start_a_new_attempt(
    monkeypatch,
    status: str,
) -> None:
    import asyncio

    from backend.app.api import goals

    release = asyncio.Event()

    async def blocked_run(_goal):
        await release.wait()

    goal = _goal_record(status=status)
    goal["attempt_count"] = 3
    goal["active_attempt_id"] = "goal-test:attempt-3"
    monkeypatch.setattr(goals, "_persist", lambda: None)
    monkeypatch.setattr(goals, "_goals", [goal])
    monkeypatch.setattr(goals, "_run_goal", blocked_run)

    response = await goals.start_goal("goal-test", _principal())

    assert response["attempt_count"] == 4
    assert goal["active_attempt_id"] == "goal-test:attempt-4"
    release.set()
    await goals._tasks["goal-test"]
    goals._tasks.pop("goal-test", None)


def test_goal_attempt_and_owner_fields_survive_serialization(
    tmp_path,
) -> None:
    from backend.app.api import goals
    from backend.app.core.goal_store import GoalStore

    goal = _goal_record(status="needs_attention")
    goal["error_code"] = "LLM_SUBMISSION_UNKNOWN"
    snapshot = goals._serialize_goal(goal)
    store = GoalStore(tmp_path / "goals.json")
    store.save([snapshot])
    reloaded = GoalStore(tmp_path / "goals.json").goals[0]

    assert reloaded["tenant_id"] == "tenant-a"
    assert reloaded["user_id"] == "user-a"
    assert reloaded["attempt_count"] == 1
    assert reloaded["active_attempt_id"] == "goal-test:attempt-1"
    assert reloaded["error_code"] == "LLM_SUBMISSION_UNKNOWN"


def test_parallel_replay_after_confirm_failure_does_not_call_provider_twice(
    tmp_path,
    monkeypatch,
) -> None:
    import asyncio

    from backend.app.core.billing.reservations import SqlUsageReservationStore
    from backend.app.core.llm import BaseLLMBackend, LLMRouter

    class ConfirmFailsStore(SqlUsageReservationStore):
        async def confirm(self, *args, **kwargs):
            raise OSError("database-secret")

    class CountingBackend(BaseLLMBackend):
        name = "fake"
        model = "fake-v1"

        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools, *, response_format=None):
            self.calls += 1
            return LLMResponse(
                content="ok",
                model=self.model,
                tokens_used=3,
                cost=0.001,
            )

    class NoAgentLoop:
        def __init__(self, **_kwargs):
            raise ImportError("use direct fake router")

    store = ConfirmFailsStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}",
        create_schema=True,
    )
    backend = CountingBackend()
    orchestrator = ParallelAgentOrchestrator(
        llm_router=LLMRouter(backends=[backend], reservation_store=store)
    )
    monkeypatch.setattr("backend.app.core.agent.loop.AgentLoop", NoAgentLoop)
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[
        parallel_agents.get_orchestrator
    ] = lambda: orchestrator
    payload = {
        "operation_id": "parallel-replay-op",
        "task": "parent",
        "subtasks": ["child"],
    }

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/agents/parallel/orchestrator/fan-out",
            json=payload,
        )
        replay = client.post(
            "/api/v1/agents/parallel/orchestrator/fan-out",
            json=payload,
        )

    assert first.status_code == 503
    assert first.json()["detail"]["code"] == "LLM_RESERVATION_PERSISTENCE_FAILED"
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "LLM_REPLAY_BLOCKED"
    assert "database-secret" not in first.text + replay.text
    assert backend.calls == 1
    reservations = asyncio.run(
        store.list_for_root(
            tenant_id="tenant-a",
            root_operation_id="parallel-replay-op:fanout:0",
        )
    )
    assert len(reservations) == 1
    assert reservations[0].status == "reserved"
