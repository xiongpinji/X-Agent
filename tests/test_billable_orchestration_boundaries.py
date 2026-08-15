from __future__ import annotations

from hashlib import sha256
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
    ParallelAgentExecutor,
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


def _parallel_run_id(operation_id: str) -> str:
    return "parallel-" + sha256(
        f"tenant-a\0user-a\0{operation_id}".encode()
    ).hexdigest()[:32]


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


@pytest.mark.parametrize("operation_id", [None, "", " " * 3, "x" * 221])
def test_spawn_requires_bounded_operation_id_before_agent_execution(
    monkeypatch,
    operation_id,
) -> None:
    factory_calls = 0
    executor_calls = 0

    def provider_factory(_principal):
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("agent factory must not run")

    class ExecutorMustNotRun:
        async def spawn_agents(self, **_kwargs):
            nonlocal executor_calls
            executor_calls += 1
            raise AssertionError("executor must not run")

    monkeypatch.setattr(
        parallel_agents,
        "build_agent_loop_factory",
        provider_factory,
    )
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[parallel_agents.get_executor] = ExecutorMustNotRun
    payload = {"tasks": [{"goal": "child"}]}
    if operation_id is not None:
        payload["operation_id"] = operation_id

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/parallel/spawn",
            json=payload,
        )

    assert response.status_code == 422
    assert factory_calls == 0
    assert executor_calls == 0


@pytest.mark.parametrize(
    "payload_update",
    [
        {"tasks": []},
        {"tasks": [{"goal": "child"}] * 33},
        {"max_parallel": 0},
        {"max_parallel": 33},
        {"tasks": [{"goal": "child", "timeout_seconds": 0}]},
        {"tasks": [{"goal": "child", "timeout_seconds": 3601}]},
        {"tasks": [{"goal": "child", "max_retries": -1}]},
        {"tasks": [{"goal": "child", "max_retries": 4}]},
        {"tasks": [{"goal": "   "}]},
        {"tasks": [{"goal": "g" * 20_001}]},
        {"tasks": [{"goal": "child", "description": "d" * 20_001}]},
        {"tasks": [{"goal": "child", "constraints": ["c"] * 33}]},
        {"tasks": [{"goal": "child", "constraints": ["c" * 2_001]}]},
        {
            "tasks": [
                {
                    "goal": "child",
                    "metadata": {f"key-{index}": "v" for index in range(65)},
                }
            ]
        },
        {"tasks": [{"goal": "child", "metadata": {"blob": "x" * 65_536}}]},
        {"tasks": [{"goal": "child", "metadata": {"blob": "界" * 22_000}}]},
    ],
)
def test_spawn_rejects_unbounded_work_before_agent_execution(
    monkeypatch,
    payload_update,
) -> None:
    factory_calls = 0
    executor_calls = 0

    def provider_factory(_principal):
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("agent/provider factory must not run")

    class ExecutorMustNotRun:
        async def spawn_agents(self, **_kwargs):
            nonlocal executor_calls
            executor_calls += 1
            raise AssertionError("executor must not run")

    monkeypatch.setattr(
        parallel_agents,
        "build_agent_loop_factory",
        provider_factory,
    )
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[parallel_agents.get_executor] = ExecutorMustNotRun
    payload = {
        "operation_id": "spawn-resource-boundary",
        "tasks": [{"goal": "child"}],
        "aggregate_results": False,
        **payload_update,
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/agents/parallel/spawn", json=payload)

    assert response.status_code == 422
    assert factory_calls == 0
    assert executor_calls == 0


def test_spawn_accepts_documented_resource_boundaries(monkeypatch) -> None:
    executor_calls: list[dict] = []

    class RecordingExecutor:
        async def spawn_agents(self, **kwargs):
            executor_calls.append(kwargs)
            return SimpleNamespace(
                to_dict=lambda: {
                    "batch_id": kwargs["batch_id"],
                    "total_tasks": len(kwargs["tasks"]),
                    "results": [],
                }
            )

    monkeypatch.setattr(
        parallel_agents,
        "build_agent_loop_factory",
        lambda _principal: object(),
    )
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[parallel_agents.get_executor] = RecordingExecutor
    boundary_task = {
        "goal": "g" * 20_000,
        "description": "d" * 20_000,
        "constraints": ["c" * 2_000] * 32,
        "success_criteria": ["s" * 2_000] * 32,
        "dependencies": [f"dependency-{index}" for index in range(32)],
        "metadata": {f"key-{index}": "value" for index in range(64)},
        "timeout_seconds": 1,
        "max_retries": 0,
    }
    tasks = [
        boundary_task,
        {
            "goal": "child",
            "metadata": {"blob": "x" * 65_525},
            "timeout_seconds": 3600,
        },
    ]
    tasks.extend({"goal": f"child-{index}"} for index in range(30))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/parallel/spawn",
            json={
                "operation_id": "spawn-valid-boundary",
                "tasks": tasks,
                "max_parallel": 32,
                "aggregate_results": False,
            },
        )

    assert response.status_code == 200
    assert len(executor_calls) == 1
    assert len(executor_calls[0]["tasks"]) == 32
    assert executor_calls[0]["max_parallel"] == 32
    assert executor_calls[0]["tasks"][0].timeout_seconds == 1
    assert executor_calls[0]["tasks"][1].timeout_seconds == 3600


def test_spawn_passes_stable_batch_and_task_run_context(
    monkeypatch,
) -> None:
    from backend.app import dependencies

    contexts: list[RunContext] = []
    extras: list[dict] = []
    executor_calls: list[dict] = []

    class RecordingLoop:
        async def run(self, context, task, extra_context=None):
            contexts.append(context)
            extras.append(extra_context or {})
            return SimpleNamespace(
                status=SimpleNamespace(value="completed"),
                answer=f"done:{task}",
                iterations=1,
                trace_id=context.trace_id,
                error=None,
            )

    class RecordingExecutor:
        async def spawn_agents(self, **kwargs):
            executor_calls.append(kwargs)
            for index, task in enumerate(kwargs["tasks"]):
                agent = kwargs["agent_factory"](
                    f"agent-{index}",
                    kwargs["isolation"],
                )
                await agent.execute(task)
            batch_id = kwargs["batch_id"]
            return SimpleNamespace(
                to_dict=lambda: {
                    "batch_id": batch_id,
                    "total_tasks": len(kwargs["tasks"]),
                }
            )

    monkeypatch.setattr(dependencies, "get_agent", lambda: RecordingLoop())
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[parallel_agents.get_executor] = RecordingExecutor
    payload = {
        "operation_id": "  spawn-op-1  ",
        "tasks": [{"goal": "alpha"}, {"goal": "beta"}],
        "aggregate_results": False,
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/agents/parallel/spawn", json=payload)
        second = client.post("/api/v1/agents/parallel/spawn", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json()["batch_id"] == second.json()["batch_id"]
    expected_batch = _parallel_run_id("spawn-op-1")
    assert first.json()["batch_id"] == expected_batch
    assert [call["batch_id"] for call in executor_calls] == [
        expected_batch,
        expected_batch,
    ]
    assert [task.id for task in executor_calls[0]["tasks"]] == [
        f"task-0-{expected_batch}",
        f"task-1-{expected_batch}",
    ]
    expected_traces = [
        _parallel_run_id(f"spawn-op-1:{index}")
        for index in range(2)
    ]
    assert [context.trace_id for context in contexts] == expected_traces * 2
    assert [extra["operation_id"] for extra in extras] == [
        "spawn-op-1:0",
        "spawn-op-1:1",
    ] * 2
    assert [extra["run_id"] for extra in extras] == expected_traces * 2


@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (LLMReplayBlockedError("spawn-secret"), 409, "LLM_REPLAY_BLOCKED"),
        (
            LLMReservationPersistenceError("spawn-secret"),
            503,
            "LLM_RESERVATION_PERSISTENCE_FAILED",
        ),
        (
            LLMSubmissionUnknownError("spawn-secret"),
            502,
            "LLM_SUBMISSION_UNKNOWN",
        ),
        (RuntimeError("spawn-secret"), 500, "PARALLEL_SPAWN_FAILED"),
    ],
)
def test_spawn_maps_errors_without_secret_leakage(
    monkeypatch,
    error: Exception,
    status_code: int,
    error_code: str,
    caplog,
) -> None:
    class FailingExecutor:
        async def spawn_agents(self, **_kwargs):
            raise error

    monkeypatch.setattr(
        parallel_agents,
        "build_agent_loop_factory",
        lambda _principal: object(),
    )
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[parallel_agents.get_executor] = FailingExecutor

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/parallel/spawn",
            json={
                "operation_id": "spawn-error-op",
                "tasks": [{"goal": "child"}],
                "aggregate_results": False,
            },
        )

    expected_batch = _parallel_run_id("spawn-error-op")
    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == error_code
    assert "spawn-secret" not in response.text
    assert "spawn-secret" not in caplog.text
    assert expected_batch in caplog.text


def test_spawn_does_not_reclassify_billing_error_during_agent_construction(
    monkeypatch,
) -> None:
    from backend.app import dependencies

    monkeypatch.setattr(
        dependencies,
        "get_agent",
        lambda: (_ for _ in ()).throw(
            LLMSubmissionUnknownError("agent-construction-secret")
        ),
    )
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/parallel/spawn",
            json={
                "operation_id": "spawn-construction-op",
                "tasks": [{"goal": "child"}],
                "aggregate_results": False,
            },
        )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "LLM_SUBMISSION_UNKNOWN"
    assert "agent-construction-secret" not in response.text


def test_spawn_task_failure_does_not_leak_internal_error(
    monkeypatch,
    caplog,
) -> None:
    class FailingAgent:
        async def execute(self, _task):
            raise RuntimeError("spawn-task-secret")

    monkeypatch.setattr(
        parallel_agents,
        "build_agent_loop_factory",
        lambda _principal: lambda _agent_id, _isolation: FailingAgent(),
    )
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[
        parallel_agents.get_executor
    ] = lambda: ParallelAgentExecutor(max_workers=1)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/parallel/spawn",
            json={
                "operation_id": "spawn-task-failure",
                "tasks": [{"goal": "child", "max_retries": 1}],
                "aggregate_results": False,
            },
        )

    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "failed"
    assert response.json()["results"][0]["error"] == "Agent execution failed."
    assert "spawn-task-secret" not in response.text
    assert "spawn-task-secret" not in caplog.text


def test_spawn_real_agent_loop_confirm_failure_replay_calls_provider_once(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app import dependencies
    from backend.app.core.agent.loop import AgentLoop
    from backend.app.core.billing.reservations import SqlUsageReservationStore
    from backend.app.core.hooks import HookManager
    from backend.app.core.llm import BaseLLMBackend, LLMRouter
    from backend.app.core.tracing import TraceStore

    class ConfirmFailsStore(SqlUsageReservationStore):
        async def confirm(self, *args, **kwargs):
            raise OSError("spawn-database-secret")

    class CountingBackend(BaseLLMBackend):
        name = "fake"
        model = "fake-v1"

        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools, *, response_format=None):
            self.calls += 1
            return LLMResponse(
                content="hello",
                model=self.model,
                tokens_used=3,
                cost=0.001,
            )

    store = ConfirmFailsStore(
        f"sqlite:///{(tmp_path / 'usage.db').as_posix()}",
        create_schema=True,
    )
    backend = CountingBackend()
    llm_router = LLMRouter(backends=[backend], reservation_store=store)
    agent_loop = AgentLoop(
        llm_router=llm_router,
        memory=None,
        tools=None,
        tracer=TraceStore(tmp_path / "trace.jsonl"),
        hook_manager=HookManager(),
    )
    monkeypatch.setattr(dependencies, "get_agent", lambda: agent_loop)
    app = FastAPI()
    app.include_router(parallel_agents.router)
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[
        parallel_agents.get_executor
    ] = lambda: ParallelAgentExecutor(max_workers=1)
    payload = {
        "operation_id": "spawn-confirm-failure",
        "tasks": [{"goal": "hello?", "max_retries": 3}],
        "aggregate_results": False,
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/agents/parallel/spawn", json=payload)
        replay = client.post("/api/v1/agents/parallel/spawn", json=payload)

    assert first.status_code == 503
    assert first.json()["detail"]["code"] == "LLM_RESERVATION_PERSISTENCE_FAILED"
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "LLM_REPLAY_BLOCKED"
    assert "spawn-database-secret" not in first.text + replay.text
    assert backend.calls == 1
