import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.core.agent import AgentLoop
from backend.app.core.approvals import ApprovalDecisionRequest, ApprovalStore
from backend.app.core.llm import LLMRouter
from backend.app.core.memory import InMemoryMemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry
from backend.app.core.workflows import (
    WorkflowCreateRequest,
    WorkflowEdge,
    WorkflowExecutor,
    WorkflowNode,
    WorkflowNodeResult,
    WorkflowNodeType,
    WorkflowRepository,
    WorkflowRuntimeManager,
    WorkflowScheduler,
    WorkflowScheduleRequest,
    WorkflowScheduleStatus,
    WorkflowScheduleStore,
)
from backend.app.main import app


def _build_workflow_definition() -> WorkflowCreateRequest:
    return WorkflowCreateRequest(
        name="Greeting flow",
        description="Simple input -> transform -> output chain.",
        nodes=[
            WorkflowNode(id="input_1", type=WorkflowNodeType.INPUT, config={"key": "name"}),
            WorkflowNode(
                id="transform_1",
                type=WorkflowNodeType.TRANSFORM,
                config={"template": "Hello {input_name}"},
            ),
            WorkflowNode(
                id="output_1",
                type=WorkflowNodeType.OUTPUT,
                config={"from": "transform_1"},
            ),
        ],
        edges=[
            WorkflowEdge(source="input_1", target="transform_1"),
            WorkflowEdge(source="transform_1", target="output_1"),
        ],
    )


def _build_wait_workflow_definition() -> WorkflowCreateRequest:
    return WorkflowCreateRequest(
        name="Wait flow",
        nodes=[
            WorkflowNode(id="input_1", type=WorkflowNodeType.INPUT, config={"key": "name"}),
            WorkflowNode(id="wait_1", type=WorkflowNodeType.WAIT, config={"delay_ms": 200}),
            WorkflowNode(
                id="output_1",
                type=WorkflowNodeType.OUTPUT,
                config={"from": "input_1"},
            ),
        ],
        edges=[
            WorkflowEdge(source="input_1", target="wait_1"),
            WorkflowEdge(source="wait_1", target="output_1"),
        ],
    )


def _build_recovery_branch_workflow_definition() -> WorkflowCreateRequest:
    return WorkflowCreateRequest(
        name="Recovery branch flow",
        nodes=[
            WorkflowNode(id="agent_1", type=WorkflowNodeType.AGENT, config={"task": "Summarize state"}),
            WorkflowNode(id="wait_1", type=WorkflowNodeType.WAIT, config={"delay_ms": 0}),
            WorkflowNode(
                id="output_1",
                type=WorkflowNodeType.OUTPUT,
                config={"value": "done"},
            ),
        ],
        edges=[
            WorkflowEdge(source="agent_1", target="wait_1", condition="approval_wait"),
            WorkflowEdge(source="agent_1", target="output_1", condition="continue"),
            WorkflowEdge(source="wait_1", target="output_1"),
        ],
    )


def _build_reobserve_branch_workflow_definition() -> WorkflowCreateRequest:
    return WorkflowCreateRequest(
        name="Reobserve branch flow",
        nodes=[
            WorkflowNode(id="agent_1", type=WorkflowNodeType.AGENT, config={"task": "Summarize state"}),
            WorkflowNode(id="wait_1", type=WorkflowNodeType.WAIT, config={"delay_ms": 0}),
            WorkflowNode(
                id="output_1",
                type=WorkflowNodeType.OUTPUT,
                config={"value": "done"},
            ),
        ],
        edges=[
            WorkflowEdge(source="agent_1", target="wait_1", condition="reobserve"),
            WorkflowEdge(source="wait_1", target="output_1"),
        ],
    )


class _StubAgent:
    def __init__(self, summary: dict[str, object], *, approval_pending: bool = True) -> None:
        self._summary = summary
        self._approval_pending = approval_pending
        self.tools = type("_StubTools", (), {"execute": self._execute_tool})()
        self.memory = type("_StubMemory", (), {"snapshot": lambda self: {}, "count": lambda self: 0})()
        self.orchestrator = type("_StubOrchestrator", (), {"prepare": self._prepare})()

    async def _execute_tool(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise AssertionError("tools.execute should not be called in this test")

    def _prepare(self, task_frame, execution_frame, metadata=None):  # noqa: ANN001, ANN002, ANN003
        recovery = type("_Recovery", (), {"model_dump": lambda self, mode="json": {"branch": "continue"}, "branch": "continue"})()
        decision = type("_Decision", (), {"model_dump": lambda self, mode="json": {"name": "agent", "reason": "stub"}, "name": "agent", "reason": "stub"})()
        ctx = type("_Ctx", (), {"metadata": metadata or {}})()
        return ctx, decision, recovery

    async def run(self, context, task, extra_context=None, event_callback=None):  # noqa: ANN001, ANN002, ANN003
        class _Response:
            def __init__(self, summary: dict[str, object], approval_pending: bool) -> None:
                self.trace_id = "trace-approval-wait"
                self.status = "completed"
                self.iterations = int(summary.get("iterations", 1))
                self.tool_calls = []
                self.plan = []
                self.execution_summary = {
                    "current_subtask_index": 0,
                    "subtask_status": {"approval": "pending"} if approval_pending else {"status": "running"},
                    "subtasks": [],
                }
                self.snapshot = {"stub": True}
                self._summary = summary
                self._approval_pending = approval_pending

            def model_dump(self, mode="json"):
                summary = dict(self._summary)
                if self._approval_pending:
                    summary.setdefault("approval_pending", True)
                return {"agent_summary": summary, "trace_id": self.trace_id, "status": self.status, "iterations": self.iterations, "tool_calls": [], "plan": [], "execution_summary": self.execution_summary, "snapshot": self.snapshot}

        return _Response(self._summary, self._approval_pending)


def test_workflow_repository_persists_definitions_and_runs(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    workflow = repository.upsert_definition(_build_workflow_definition())

    reloaded = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )

    assert reloaded.get_definition(workflow.id) is not None
    assert reloaded.definition_count() == 1


async def test_workflow_executor_runs_dag(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    workflow = repository.upsert_definition(_build_workflow_definition())
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(agent=agent, repository=repository)

    run = await executor.execute(workflow.id, {"name": "X-Agent"})

    assert run.workflow_id == workflow.id
    assert run.status.value == "completed"
    assert run.outputs["output_1"] == "Hello X-Agent"
    assert len(run.node_results) == 3
    assert run.snapshot["workflow_id"] == workflow.id
    assert run.snapshot["node_result_count"] == 3


async def test_workflow_executor_records_timeout_and_retry_attempts(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    workflow = repository.upsert_definition(
        WorkflowCreateRequest(
            name="Retry timeout flow",
            nodes=[
                WorkflowNode(
                    id="wait_1",
                    type=WorkflowNodeType.WAIT,
                    config={"delay_ms": 100, "timeout_ms": 10, "max_retries": 1},
                ),
                WorkflowNode(
                    id="output_1",
                    type=WorkflowNodeType.OUTPUT,
                    config={"from": "wait_1"},
                ),
            ],
            edges=[WorkflowEdge(source="wait_1", target="output_1")],
        )
    )
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(agent=agent, repository=repository)

    run = await executor.execute(workflow.id)

    assert run.status.value == "failed"
    assert run.node_results[0].node_id == "wait_1"
    assert run.node_results[0].attempts == 2


async def test_workflow_executor_runs_failure_compensation(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    workflow = repository.upsert_definition(
        WorkflowCreateRequest(
            name="Compensating flow",
            nodes=[
                WorkflowNode(id="input_1", type=WorkflowNodeType.INPUT, config={"key": "name"}),
                WorkflowNode(
                    id="wait_1",
                    type=WorkflowNodeType.WAIT,
                    config={
                        "delay_ms": 100,
                        "timeout_ms": 10,
                        "on_failure": {
                            "type": "transform",
                            "template": "rollback {input_name}",
                        },
                    },
                ),
            ],
            edges=[WorkflowEdge(source="input_1", target="wait_1")],
        )
    )
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(agent=agent, repository=repository)

    run = await executor.execute(workflow.id, {"name": "deploy"})

    assert run.status.value == "failed"
    assert run.node_results[-1].compensated is True
    assert run.node_results[-1].compensation_output == "rollback deploy"


def test_workflow_recovery_hint_prefers_approval_wait_and_reobserve(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(agent=agent, repository=repository)

    approval_hint = executor._workflow_recovery_hint(
        {"last_agent_summary": {"approval_pending": True}},
        error=None,
    )
    reobserve_hint = executor._workflow_recovery_hint(
        {"last_agent_summary": {"iterations": 3}},
        error=None,
    )
    observe_hint = executor._workflow_recovery_hint(
        {"last_agent_summary": {"tool_count": 0}},
        error=None,
    )

    assert approval_hint["branch"] == "approval_wait"
    assert reobserve_hint["branch"] == "reobserve"
    assert observe_hint["branch"] == "observe"


def test_workflow_branch_from_state_prioritizes_recovery_paths() -> None:
    assert WorkflowExecutor._workflow_branch_from_state(
        error=None,
        approval_pending=True,
        recent_failures=0,
        status="running",
        subtask_status="",
        tool_count=1,
        iterations=1,
    ) == "approval_wait"
    assert WorkflowExecutor._workflow_branch_from_state(
        error="boom",
        approval_pending=False,
        recent_failures=0,
        status="running",
        subtask_status="",
        tool_count=1,
        iterations=1,
    ) == "compensation"
    assert WorkflowExecutor._workflow_branch_from_state(
        error=None,
        approval_pending=False,
        recent_failures=1,
        status="running",
        subtask_status="",
        tool_count=1,
        iterations=1,
    ) == "compensation"
    assert WorkflowExecutor._workflow_branch_from_state(
        error=None,
        approval_pending=False,
        recent_failures=0,
        status="blocked",
        subtask_status="waiting",
        tool_count=1,
        iterations=1,
    ) == "compensation"
    assert WorkflowExecutor._workflow_branch_from_state(
        error=None,
        approval_pending=False,
        recent_failures=0,
        status="running",
        subtask_status="",
        tool_count=1,
        iterations=3,
    ) == "reobserve"
    assert WorkflowExecutor._workflow_branch_from_state(
        error=None,
        approval_pending=False,
        recent_failures=0,
        status="running",
        subtask_status="",
        tool_count=0,
        iterations=1,
    ) == "observe"
    assert WorkflowExecutor._workflow_branch_from_state(
        error=None,
        approval_pending=False,
        recent_failures=0,
        status="running",
        subtask_status="",
        tool_count=1,
        iterations=1,
    ) == "continue"


def test_workflow_edge_condition_can_follow_recovery_branch(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(agent=agent, repository=repository)
    edge = WorkflowEdge(source="agent_1", target="wait_1", condition="approval_wait")

    assert executor._evaluate_edge_condition(
        edge,
        {"recovery_hint": {"branch": "approval_wait"}},
        {},
    ) is True
    assert executor._evaluate_edge_condition(
        edge,
        {"recovery_hint": {"branch": "compensation"}},
        {},
    ) is False


def test_workflow_recovery_hint_drives_edge_conditions(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(agent=agent, repository=repository)
    state = {
        "last_agent_summary": {
            "status": "blocked",
            "tool_count": 0,
            "iterations": 4,
            "subtask_status": "waiting",
        },
        "pending_approval_id": "approval-123",
        "node_results": [],
    }
    hint = executor._workflow_recovery_hint(state, error=None)

    assert hint["branch"] == "approval_wait"
    assert executor._evaluate_edge_condition(
        WorkflowEdge(source="a", target="b", condition="approval_wait"),
        {**state, "recovery_hint": hint},
        {},
    ) is True
    assert executor._evaluate_edge_condition(
        WorkflowEdge(source="a", target="b", condition="blocked"),
        {**state, "recovery_hint": hint},
        {},
    ) is True
    assert executor._evaluate_edge_condition(
        WorkflowEdge(source="a", target="b", condition="false"),
        {**state, "recovery_hint": hint},
        {},
    ) is False


async def test_workflow_executor_routes_by_recovery_hint(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    workflow = repository.upsert_definition(_build_recovery_branch_workflow_definition())
    agent = _StubAgent({"status": "blocked", "tool_count": 0, "iterations": 1}, approval_pending=False)
    # 恢复提示路由语义由 sequential 执行器保证；默认 auto 并行模式在成功路径
    # 不维护 state["recovery_hint"]（契约变更，见 final_validation 报告）。
    executor = WorkflowExecutor(agent=agent, repository=repository, parallel_mode="sequential")

    run = await executor.execute(workflow.id, {})

    assert run.status.value == "completed"
    assert run.snapshot["recovery_hint"]["branch"] == "observe"
    assert run.snapshot["last_agent_execution_summary"]
    assert run.snapshot["recovery_hint"]["branch"] == "observe"
    assert run.node_results[-1].node_id == "output_1"


async def test_workflow_executor_uses_default_compensation_route(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    workflow = repository.upsert_definition(
        WorkflowCreateRequest(
            name="Default compensation branch flow",
            nodes=[
                WorkflowNode(id="input_1", type=WorkflowNodeType.INPUT, config={"key": "name"}),
                WorkflowNode(
                    id="wait_1",
                    type=WorkflowNodeType.WAIT,
                    config={"delay_ms": 10, "timeout_ms": 1},
                ),
            ],
            edges=[WorkflowEdge(source="input_1", target="wait_1")],
        )
    )
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(agent=agent, repository=repository)

    run = await executor.execute(workflow.id, {"name": "compensate"})

    assert run.status.value == "failed"
    assert run.node_results[-1].compensated is True
    assert run.node_results[-1].compensation_output == "Workflow node {node_id} compensated under branch {branch}."


async def test_workflow_executor_routes_reobserve_branch(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    workflow = repository.upsert_definition(_build_reobserve_branch_workflow_definition())
    agent = _StubAgent({"status": "running", "tool_count": 1, "iterations": 3}, approval_pending=False)
    executor = WorkflowExecutor(agent=agent, repository=repository, parallel_mode="sequential")

    run = await executor.execute(workflow.id, {})

    assert run.status.value == "completed"
    assert any(result.node_id == "wait_1" for result in run.node_results)
    assert run.snapshot["recovery_hint"]["branch"] == "reobserve"
    assert run.snapshot["last_agent_execution_summary"]
    assert run.snapshot["recovery_hint"]["branch"] == "reobserve"


async def test_workflow_runtime_can_pause_resume_and_cancel(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    workflow = repository.upsert_definition(_build_wait_workflow_definition())
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(agent=agent, repository=repository)
    runtime = WorkflowRuntimeManager(executor=executor, repository=repository)

    running = await runtime.start(workflow.id, {"name": "paused"})
    paused = await runtime.pause_latest(workflow.id)

    assert paused.run_id == running.run_id
    assert paused.status.value == "paused"
    assert paused.snapshot["workflow_id"] == workflow.id

    resumed = await runtime.resume_latest(workflow.id)
    await _wait_for_terminal_status(repository, workflow.id)

    latest = repository.latest_run_for(workflow.id)
    assert resumed.status.value == "running"
    assert latest is not None
    assert latest.status.value == "completed"

    canceling = await runtime.start(workflow.id, {"name": "cancel"})
    canceled = await runtime.cancel_latest(workflow.id)
    await _wait_for_terminal_status(repository, workflow.id)

    assert canceled.run_id == canceling.run_id
    assert repository.get_run(canceling.run_id).status.value == "canceled"


async def test_workflow_scheduler_persists_and_triggers_due_runs(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    workflow = repository.upsert_definition(_build_workflow_definition())
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(agent=agent, repository=repository)
    runtime = WorkflowRuntimeManager(executor=executor, repository=repository)
    store = WorkflowScheduleStore(storage_path=tmp_path / "workflow_schedules.json")
    scheduler = WorkflowScheduler(repository=repository, runtime=runtime, schedule_store=store)

    scheduled = scheduler.schedule(
        workflow.id,
        WorkflowScheduleRequest(inputs={"name": "Scheduled"}, delay_seconds=0),
        tenant_id="tenant-a",
        user_id="scheduler",
        permission_scope=["tools:read", "memory:read", "memory:write", "workflow:run"],
    )
    triggered = await scheduler.run_due()
    await _wait_for_terminal_status(repository, workflow.id)
    reloaded = WorkflowScheduleStore(storage_path=tmp_path / "workflow_schedules.json")

    latest = repository.latest_run_for(workflow.id)
    assert scheduled.status == WorkflowScheduleStatus.PENDING
    assert scheduled.snapshot["workflow_id"] == workflow.id
    assert triggered[0].status == WorkflowScheduleStatus.TRIGGERED
    assert triggered[0].run_id
    assert latest is not None
    assert latest.outputs["output_1"] == "Hello Scheduled"
    assert reloaded.get(scheduled.schedule_id).status == WorkflowScheduleStatus.TRIGGERED


async def test_workflow_approval_node_creates_pending_approval(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    approval_store = ApprovalStore()
    workflow = repository.upsert_definition(
        WorkflowCreateRequest(
            name="Approval flow",
            nodes=[
                WorkflowNode(
                    id="approval_1",
                    type=WorkflowNodeType.APPROVAL,
                    config={
                        "reason": "Deploy requires human approval.",
                        "resource_id": "deploy-prod",
                    },
                ),
                WorkflowNode(
                    id="output_1",
                    type=WorkflowNodeType.OUTPUT,
                    config={"value": "approved"},
                ),
            ],
            edges=[WorkflowEdge(source="approval_1", target="output_1")],
        )
    )
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(
        agent=agent,
        repository=repository,
        approval_store=approval_store,
    )

    run = await executor.execute(workflow.id)
    approvals = approval_store.list()

    assert run.status.value == "needs_approval"
    assert run.outputs["approval_id"] == approvals[0].id
    assert run.node_results[0].status.value == "needs_approval"
    assert approvals[0].resource_type == "workflow"
    assert approvals[0].resource_id == "deploy-prod"


async def test_workflow_can_resume_after_approval_node_is_approved(tmp_path) -> None:
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "workflow_runs.jsonl",
    )
    approval_store = ApprovalStore()
    workflow = repository.upsert_definition(
        WorkflowCreateRequest(
            name="Approval resume flow",
            nodes=[
                WorkflowNode(id="approval_1", type=WorkflowNodeType.APPROVAL),
                WorkflowNode(
                    id="output_1",
                    type=WorkflowNodeType.OUTPUT,
                    config={"value": "resumed"},
                ),
            ],
            edges=[WorkflowEdge(source="approval_1", target="output_1")],
        )
    )
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    executor = WorkflowExecutor(
        agent=agent,
        repository=repository,
        approval_store=approval_store,
    )

    blocked = await executor.execute(workflow.id)
    approval_store.approve(
        blocked.pending_approval_id,
        ApprovalDecisionRequest(decided_by="admin", reason="ok"),
    )
    resumed = await executor.execute(
        workflow.id,
        blocked.inputs,
        approved_approvals={blocked.pending_node_id: blocked.pending_approval_id},
    )

    assert blocked.status.value == "needs_approval"
    assert resumed.status.value == "completed"
    assert resumed.outputs["output_1"] == "resumed"


def test_workflow_schedule_store_acquire_due_uses_lease(tmp_path) -> None:
    store = WorkflowScheduleStore(storage_path=tmp_path / "workflow_schedules.json")
    record = store.create(
        workflow_id="workflow-1",
        inputs={},
        tenant_id="tenant-a",
        user_id="scheduler",
        permission_scope=["workflow:run"],
        run_at=datetime.now(UTC),
    )

    first = store.acquire_due(worker_id="worker-a", lease_seconds=60)
    second = store.acquire_due(worker_id="worker-b", lease_seconds=60)

    assert first[0].schedule_id == record.schedule_id
    assert first[0].locked_by == "worker-a"
    assert second == []


def test_workflow_schedule_store_reacquires_expired_lease(tmp_path) -> None:
    store = WorkflowScheduleStore(storage_path=tmp_path / "workflow_schedules.json")
    now = datetime.now(UTC)
    record = store.create(
        workflow_id="workflow-1",
        inputs={},
        tenant_id="tenant-a",
        user_id="scheduler",
        permission_scope=["workflow:run"],
        run_at=now,
    )

    first = store.acquire_due(worker_id="worker-a", lease_seconds=1, now=now)
    second = store.acquire_due(
        worker_id="worker-b",
        lease_seconds=60,
        now=now + timedelta(seconds=2),
    )

    assert first[0].schedule_id == record.schedule_id
    assert second[0].schedule_id == record.schedule_id
    assert second[0].locked_by == "worker-b"


def test_workflow_api_smoke() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow_payload = _build_workflow_definition().model_dump(mode="json")
    workflow = client.post("/api/v1/workflows", json=workflow_payload).json()

    list_response = client.get("/api/v1/workflows")
    detail_response = client.get(f"/api/v1/workflows/{workflow['id']}")
    status_response = client.get(f"/api/v1/workflows/{workflow['id']}/status")
    run_response = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "Alice"}},
    )
    instances_response = client.get(f"/api/v1/workflows/{workflow['id']}/instances")

    assert list_response.status_code == 200
    assert any(item["workflow_id"] == workflow["id"] for item in list_response.json())
    assert detail_response.status_code == 200
    assert status_response.status_code == 200
    assert status_response.json()["workflow_id"] == workflow["id"]
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "completed"
    assert run_response.json()["outputs"]["output_1"] == "Hello Alice"
    assert instances_response.status_code == 200
    instance_run_ids = {item["run_id"] for item in instances_response.json()}
    assert run_response.json()["run_id"] in instance_run_ids


def test_workflow_api_async_run_returns_running_record() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow_payload = _build_wait_workflow_definition().model_dump(mode="json")
    workflow = client.post("/api/v1/workflows", json=workflow_payload).json()

    response = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "async"}, "async_run": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_workflow_api_schedule_and_run_due() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow_payload = _build_workflow_definition().model_dump(mode="json")
    workflow = client.post("/api/v1/workflows", json=workflow_payload).json()

    scheduled = client.post(
        f"/api/v1/workflows/{workflow['id']}/schedule",
        json={"inputs": {"name": "API Scheduled"}, "delay_seconds": 0},
    )
    due = client.post("/api/v1/workflows/schedules/run-due")
    schedules = client.get("/api/v1/workflows/schedules")

    assert scheduled.status_code == 200
    assert scheduled.json()["status"] == "pending"
    assert due.status_code == 200
    assert any(item["schedule_id"] == scheduled.json()["schedule_id"] for item in due.json())
    assert schedules.status_code == 200
    assert any(
        item["schedule_id"] == scheduled.json()["schedule_id"]
        and item["status"] == "triggered"
        for item in schedules.json()
    )


def test_workflow_api_approval_node_returns_needs_approval() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "API approval flow",
            "nodes": [
                {
                    "id": "approval_1",
                    "type": "approval",
                    "config": {"reason": "Needs review", "resource_id": "api-change"},
                }
            ],
            "edges": [],
        },
    ).json()

    response = client.post(f"/api/v1/workflows/{workflow['id']}/run", json={"inputs": {}})

    assert response.status_code == 200
    assert response.json()["status"] == "needs_approval"
    assert response.json()["outputs"]["approval_id"]


def test_workflow_api_resume_approved_run() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "API resume approval flow",
            "nodes": [
                {"id": "approval_1", "type": "approval", "config": {"reason": "Needs review"}},
                {"id": "output_1", "type": "output", "config": {"value": "resumed"}},
            ],
            "edges": [{"source": "approval_1", "target": "output_1"}],
        },
    ).json()
    blocked = client.post(f"/api/v1/workflows/{workflow['id']}/run", json={"inputs": {}}).json()
    approval_id = blocked["pending_approval_id"]

    # P0-07 职责分离（SoD）: 审批请求的 actor（本测试为 bootstrap-admin）不得自审自批。
    # 换用第二个已认证身份（独立 API key，user_id 不同于发起人）完成审批；
    # decided_by 由服务端强制绑定为审批人 principal，请求体传入值一律忽略。
    approver_key = client.post(
        "/api/v1/security/api-keys",
        json={"name": "workflow-approver", "role": "admin", "user_id": "workflow-approver"},
    ).json()["key"]
    approver = TestClient(app, headers={"x-api-key": approver_key})

    approved = approver.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "ok"},
    )
    resumed = client.post(f"/api/v1/workflows/runs/{blocked['run_id']}/resume-approved", json={"approval_id": approval_id})

    assert approved.status_code == 200
    assert approved.json()["decided_by"] == "workflow-approver"
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"
    assert resumed.json()["outputs"]["output_1"] == "resumed"


def test_workflow_chat_and_templates() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    baseline = client.get("/api/v1/workflows/templates")
    assert baseline.status_code == 200
    # 模板集来自持久化定义，种子数量随版本/环境变化（本次商用重构后由 3 减至 2），
    # 改为验证确定性契约：创建一条定义后模板计数 +1。
    created = client.post("/api/v1/workflows", json={"name": "模板计数探针", "nodes": [], "edges": []})
    assert created.status_code == 200
    templates = client.get("/api/v1/workflows/templates")
    assert templates.status_code == 200
    assert len(templates.json()) == len(baseline.json()) + 1
    client.delete(f"/api/v1/workflows/{created.json()['id']}")
    chat = client.post("/api/v1/workflows/create/chat", json={"request": "定时检查并汇报"})

    assert chat.status_code == 200
    assert chat.json()["name"].startswith("定时检查并汇报")


async def _wait_for_terminal_status(
    repository: WorkflowRepository,
    workflow_id: str,
    attempts: int = 20,
) -> None:
    for _ in range(attempts):
        latest = repository.latest_run_for(workflow_id)
        if latest and latest.status.value in {"completed", "failed", "canceled"}:
            return
        await asyncio.sleep(0.05)
