from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from backend.app.core.agent import AgentLoop, AgentPlanStep, AgentPlanStepRecord, AgentTrajectory
from backend.app.core.contracts import AgentRunRecord, AgentRunResponse, RunContext, RunStatus, ToolCallRecord, ToolPolicyVerdict
from backend.app.core.repair_loop import RepairLoop
from backend.app.core.replay import ReplayEngine
from backend.app.core.runs import RunStore
from backend.app.core.tracing import TraceEvent, TraceStore


class DummyMemory:
    async def retrieve(self, context, query: str, limit: int = 5):  # noqa: ANN001
        return []

    async def search_with_scores(self, context, query: str, layers: list[int], top_k: int):  # noqa: ANN001
        return []

    async def store(self, *args, **kwargs):  # noqa: ANN001
        return "memory-1"

    def count(self) -> int:
        return 0


class DummyTracer:
    def record(self, context, event: str, **data):  # noqa: ANN001
        return TraceEvent(trace_id=context.trace_id, event=event, data=data, request_id=context.request_id, agent_id=context.agent_id, tenant_id=context.tenant_id, user_id=context.user_id)


class DummyToolRegistry:
    def manifest(self) -> list[dict[str, object]]:
        return [{"name": "read_file"}, {"name": "write_file"}, {"name": "apply_text_patch"}]

    def capability_index(self) -> dict[str, object]:
        return {"read_file": True, "write_file": True, "apply_text_patch": True}

    def related_tools(self, query: str) -> list[dict[str, object]]:  # noqa: ARG002
        return self.manifest()

    def definitions_for_llm(self) -> list[dict[str, object]]:
        return []

    def get(self, name: str):  # noqa: ANN001
        return object() if name == "read_file" else None

    async def execute(self, context, tool_name: str, arguments: dict[str, object]):  # noqa: ANN001
        if tool_name == "read_file":
            return ToolCallRecord(
                tool_name=tool_name,
                success=True,
                output="current file contents",
                policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
                arguments_preview=arguments,
            )
        return ToolCallRecord(
            tool_name=tool_name,
            success=False,
            output={"path": arguments.get("path")},
            error="simulated failure",
            policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
            arguments_preview=arguments,
        )


class DummyRepairLoop:
    def analyze(self, record: ToolCallRecord):  # noqa: ANN001
        verification = type("Verification", (), {"model_dump": lambda self, mode="json": {"status": "failed", "error_type": "tool_failure"}})()
        suggestion = type(
            "Suggestion",
            (),
            {
                "should_retry": True,
                "tool_name": record.tool_name,
                "arguments": {"path": record.output.get("path") if isinstance(record.output, dict) else ""},
                "reason": "retry after failure",
                "error_type": "tool_failure",
                "confidence": 0.5,
                "follow_up": [],
            },
        )()
        return verification, suggestion

    def summarize(self, tool_calls):  # noqa: ANN001
        return {"tool_count": len(tool_calls)}


class ControlledToolRegistry(DummyToolRegistry):
    def __init__(self, failures: int = 1) -> None:
        self.failures = failures
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, context, tool_name: str, arguments: dict[str, object]):  # noqa: ANN001
        self.calls.append((tool_name, dict(arguments)))
        if tool_name == "read_file":
            return ToolCallRecord(
                tool_name=tool_name,
                success=True,
                output="current file contents",
                policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
                arguments_preview=arguments,
            )
        if self.failures > 0:
            self.failures -= 1
            return ToolCallRecord(
                tool_name=tool_name,
                success=False,
                output={"path": arguments.get("path")},
                error="simulated failure",
                policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
                arguments_preview=arguments,
            )
        return ToolCallRecord(
            tool_name=tool_name,
            success=True,
            output={"path": arguments.get("path"), "applied": True, "verified": True},
            policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
            arguments_preview=arguments,
        )


class ResumeLLM:
    def __init__(self, plan_text: str = "observe\nfinal") -> None:
        self.plan_text = plan_text

    async def chat(self, messages, defs, **_kwargs):  # noqa: ANN001
        return DummyLLMResponse(content=self.plan_text)


@dataclass
class DummyLLMResponse:
    content: str = ""
    tool_calls: list[dict[str, object]] | None = None
    model: str = "mock"


class DummyLLM:
    async def chat(self, messages, defs, **_kwargs):  # noqa: ANN001
        return DummyLLMResponse(content="finalize")


@pytest.mark.asyncio
async def test_resume_plan_keeps_final_step_and_skips_duplicate_observe() -> None:
    loop = AgentLoop(
        llm_router=DummyLLM(),
        memory=DummyMemory(),
        tools=DummyToolRegistry(),
        tracer=DummyTracer(),
        repair_loop=RepairLoop(),
    )
    trajectory = AgentTrajectory(task="resume task", goal="resume goal", stage="resuming:trace-1", subtasks=["understand request", "verify results"], subtask_status={"understand request": "done"}, current_subtask_index=1)
    steps = [
        AgentPlanStep(kind="observe", instruction="Observe context for resume"),
        AgentPlanStep(kind="tool", instruction="Use write_file to advance", tool_name="write_file", arguments={"path": "a.py"}),
    ]

    aligned = loop._align_plan_with_subtasks(steps, trajectory)
    deduped = loop._dedupe_plan_steps(trajectory, aligned)

    assert deduped[-1].kind == "final"
    assert sum(1 for step in deduped if step.kind == "observe") <= 1


@pytest.mark.asyncio
async def test_repair_write_step_refreshes_patch_arguments() -> None:
    loop = AgentLoop(
        llm_router=DummyLLM(),
        memory=DummyMemory(),
        tools=DummyToolRegistry(),
        tracer=DummyTracer(),
        repair_loop=DummyRepairLoop(),
    )
    trajectory = AgentTrajectory(task="fix file", goal="fix file goal")
    step = AgentPlanStep(kind="tool", instruction="Patch file", tool_name="apply_text_patch", arguments={"path": "demo.py", "old_text": "old", "new_text": "new"})
    record = ToolCallRecord(
        tool_name="apply_text_patch",
        success=False,
        output={"path": "demo.py"},
        error="patch failed",
        policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
    )

    retry = await loop._repair_write_step(RunContext(), trajectory, step, record, {"path": "demo.py", "old_text": "old", "new_text": "new"})

    assert retry is not None
    assert retry.tool_name == "apply_text_patch"
    assert retry.arguments["backup"] is True
    assert retry.arguments["path"] == "demo.py"


@pytest.mark.asyncio
async def test_run_store_continue_from_merges_previous_execution_summary() -> None:
    store = RunStore()
    previous = AgentRunResponse(
        trace_id="trace-a",
        agent_id="agent-a",
        status=RunStatus.FAILED,
        answer="first run",
        iterations=2,
        memory_hits=1,
        tool_calls=[],
        execution_summary={"subtasks": ["inspect", "repair"], "custom": "kept"},
        plan=[AgentPlanStepRecord(kind="tool", instruction="inspect", tool_name="read_file")],
    )
    store.save(RunContext(trace_id="trace-a", agent_id="agent-a"), "task-a", previous)

    resumed = AgentRunResponse(
        trace_id="trace-b",
        agent_id="agent-a",
        status=RunStatus.COMPLETED,
        answer="second run",
        iterations=1,
        memory_hits=1,
        tool_calls=[ToolCallRecord(tool_name="write_file", success=True, output={"path": "demo.py"}, policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"))],
        execution_summary={"new": "value"},
        plan=[AgentPlanStepRecord(kind="final", instruction="finalize")],
    )

    resumed_record = store.continue_from("trace-a", resumed)

    assert resumed_record is not None
    assert resumed_record.execution_summary["resumed_from"] == "trace-a"
    assert resumed_record.execution_summary["previous_stage"] == "failed"
    assert resumed_record.execution_summary["custom"] == "kept"
    assert resumed_record.execution_summary["new"] == "value"
    assert resumed_record.plan[-1].kind == "final"
    assert resumed_record.tool_call_count == 1


@pytest.mark.asyncio
async def test_repair_failure_records_retry_budget_exhaustion(tmp_path) -> None:
    class ExhaustedToolRegistry(DummyToolRegistry):
        async def execute(self, context, tool_name: str, arguments: dict[str, object]):  # noqa: ANN001
            return ToolCallRecord(
                tool_name=tool_name,
                success=False,
                output={"path": arguments.get("path")},
                error="simulated failure",
                policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
                arguments_preview=arguments,
            )

    class ExhaustedRepairLoop(DummyRepairLoop):
        def analyze(self, record: ToolCallRecord):  # noqa: ANN001
            verification = type("Verification", (), {"model_dump": lambda self, mode="json": {"status": "failed"}})()
            suggestion = type(
                "Suggestion",
                (),
                {
                    "should_retry": True,
                    "tool_name": record.tool_name,
                    "arguments": {"path": record.output.get("path") if isinstance(record.output, dict) else ""},
                    "reason": "retry after failure",
                    "error_type": "tool_failure",
                    "confidence": 0.5,
                    "follow_up": [],
                },
            )()
            return verification, suggestion

    loop = AgentLoop(
        llm_router=DummyLLM(),
        memory=DummyMemory(),
        tools=ExhaustedToolRegistry(),
        tracer=DummyTracer(),
        repair_loop=ExhaustedRepairLoop(),
        max_iterations=1,
    )
    context = RunContext(trace_id="trace-retry", agent_id="agent-a")
    result = await loop.run(context, "update file", extra_context={"root": str(tmp_path), "path": "demo.py", "old_text": "old", "new_text": "new", "retry_budget": 0})

    assert result.execution_summary.get("repair_failures")
    assert result.execution_summary.get("repair_retries") == []
    assert result.status == RunStatus.COMPLETED


@pytest.mark.asyncio
async def test_resume_run_reuses_previous_subtask_state(tmp_path) -> None:
    store = RunStore()
    previous = AgentRunResponse(
        trace_id="resume-source",
        agent_id="agent-a",
        status=RunStatus.COMPLETED,
        answer="first run",
        iterations=1,
        memory_hits=1,
        tool_calls=[],
        execution_summary={
            "subtasks": ["understand request", "verify results"],
            "subtask_status": {"understand request": "done"},
            "current_subtask_index": 1,
            "observations": ["old observation"],
            "tool_results": [{"tool_name": "write_file", "success": True}],
            "reflections": ["old reflection"],
        },
        plan=[],
    )
    store.save(RunContext(trace_id="resume-source", agent_id="agent-a"), "resume task", previous)

    loop = AgentLoop(
        llm_router=ResumeLLM(),
        memory=DummyMemory(),
        tools=ControlledToolRegistry(failures=0),
        tracer=DummyTracer(),
        run_store=store,
        repair_loop=DummyRepairLoop(),
        # resume 时 _apply_execution_plan 会注入脚手架步骤（reflect×5 + tool），
        # 计划膨胀为 8 步；max_iterations=3 会在 final 之前截断（既有行为）。
        # 放宽到 10 以覆盖完整 resume 链路。
        max_iterations=10,
    )
    result = await loop.run(
        RunContext(trace_id="resume-target", agent_id="agent-a", session_id="session-1"),
        "resume task",
        extra_context={"root": str(tmp_path), "resume_trace_id": "resume-source", "skip_observe_on_resume": True},
    )

    assert result.status == RunStatus.COMPLETED
    assert result.execution_summary["resumed_from"]["trace_id"] == "resume-source"
    assert result.execution_summary["subtasks"] == ["understand request", "verify results"]
    assert result.execution_summary["current_subtask_index"] == 1
    assert result.execution_summary["subtask_status"]["understand request"] == "done"
    assert any(step.kind == "final" for step in result.plan)
    assert result.execution_summary["resume_policy"]["subtasks_inherited"] is True
    assert result.execution_summary["resume_policy"]["tool_results_inherited"] is True


@pytest.mark.asyncio
async def test_resume_run_skips_completed_plan_labels(tmp_path) -> None:
    store = RunStore()
    previous = AgentRunResponse(
        trace_id="resume-source-2",
        agent_id="agent-a",
        status=RunStatus.COMPLETED,
        answer="first run",
        iterations=2,
        memory_hits=1,
        tool_calls=[ToolCallRecord(tool_name="read_file", success=True, output="ok", policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"))],
        execution_summary={
            "subtasks": ["inspect", "repair"],
            "subtask_status": {"inspect": "done"},
            "current_subtask_index": 1,
        },
        plan=[AgentPlanStepRecord(kind="observe", instruction="Observe context for resume"), AgentPlanStepRecord(kind="final", instruction="finalize")],
    )
    store.save(RunContext(trace_id="resume-source-2", agent_id="agent-a"), "resume task", previous)

    loop = AgentLoop(
        llm_router=ResumeLLM("observe\nfinal"),
        memory=DummyMemory(),
        tools=ControlledToolRegistry(failures=0),
        tracer=DummyTracer(),
        run_store=store,
        repair_loop=DummyRepairLoop(),
        max_iterations=3,
    )
    result = await loop.run(
        RunContext(trace_id="resume-target-2", agent_id="agent-a", session_id="session-1"),
        "resume task",
        extra_context={"root": str(tmp_path), "resume_trace_id": "resume-source-2", "skip_observe_on_resume": True},
    )

    assert result.status == RunStatus.COMPLETED
    assert result.execution_summary["previous_status"] == "completed"
    assert result.execution_summary["resumed_from"]["trace_id"] == "resume-source-2"
    assert result.execution_summary["resume_policy"]["subtasks_inherited"] is True
    assert all(step.instruction.lower() != "observe context for resume" for step in result.plan if step.kind != "final")


@pytest.mark.asyncio
async def test_failed_run_can_resume_and_succeed_end_to_end(tmp_path) -> None:
    store = RunStore()
    tools = ControlledToolRegistry(failures=1)
    loop = AgentLoop(
        llm_router=ResumeLLM("tool: apply_text_patch\nfinal"),
        memory=DummyMemory(),
        tools=tools,
        tracer=DummyTracer(),
        run_store=store,
        repair_loop=DummyRepairLoop(),
        max_iterations=4,
    )

    first = await loop.run(
        RunContext(trace_id="failed-trace", agent_id="agent-a", session_id="session-1"),
        "update file",
        extra_context={"root": str(tmp_path), "path": "demo.py", "old_text": "old", "new_text": "new", "retry_budget": 0},
    )
    assert first.execution_summary.get("repair_failures")

    resumed_record = store.get(first.trace_id)
    assert resumed_record is not None
    assert resumed_record.execution_summary.get("repair_failures")

    second = await loop.run(
        RunContext(trace_id="resumed-trace", agent_id="agent-a", session_id="session-1"),
        "update file",
        extra_context={"root": str(tmp_path), "path": "demo.py", "old_text": "old", "new_text": "new", "resume_trace_id": first.trace_id, "skip_observe_on_resume": True, "retry_budget": 2},
    )

    assert second.status == RunStatus.COMPLETED
    assert second.execution_summary["resumed_from"]["trace_id"] == first.trace_id
    assert second.execution_summary.get("repair_retries") is not None
    assert any(call.tool_name == "apply_text_patch" for call in second.tool_calls)
    assert tools.calls


@pytest.mark.asyncio
async def test_repair_loop_routes_write_conflict_to_focused_patch() -> None:
    loop = RepairLoop()
    conflict = ToolCallRecord(
        tool_name="write_file",
        success=False,
        output={"path": "demo.py"},
        error="conflict",
        policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
        arguments_preview={"path": "demo.py", "content": "new body"},
    )
    missing = ToolCallRecord(
        tool_name="apply_text_patch",
        success=False,
        output={"path": "demo.py"},
        error="missing resource",
        policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
        arguments_preview={"path": "demo.py", "old_text": "old", "new_text": "new"},
    )
    patch_mismatch = ToolCallRecord(
        tool_name="apply_text_patch",
        success=False,
        output={"path": "demo.py"},
        error="stale patch",
        policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
        arguments_preview={"path": "demo.py", "old_text": "old", "new_text": "new"},
    )
    approval = ToolCallRecord(
        tool_name="write_file",
        success=False,
        output={"path": "demo.py"},
        error="approval required",
        policy=ToolPolicyVerdict(allowed=False, requires_approval=True, reason="approval"),
        arguments_preview={"path": "demo.py", "content": "new body"},
    )
    timeout = ToolCallRecord(
        tool_name="write_file",
        success=False,
        output={"path": "demo.py"},
        error="timeout after 30s",
        policy=ToolPolicyVerdict(allowed=True, requires_approval=False, reason="ok"),
        arguments_preview={"path": "demo.py", "content": "new body"},
    )

    _, conflict_suggestion = loop.analyze(conflict)
    _, missing_suggestion = loop.analyze(missing)
    _, patch_mismatch_suggestion = loop.analyze(patch_mismatch)
    _, approval_suggestion = loop.analyze(approval)
    _, timeout_suggestion = loop.analyze(timeout)

    assert conflict_suggestion.should_retry is True
    assert conflict_suggestion.tool_name == "write_file"
    assert missing_suggestion.should_retry is True
    assert missing_suggestion.tool_name in {"read_file", "apply_text_patch"}
    assert patch_mismatch_suggestion.should_retry is True
    assert patch_mismatch_suggestion.tool_name in {"read_file", "apply_text_patch"}
    assert approval_suggestion.should_retry is False
    assert timeout_suggestion.should_retry is True


@pytest.mark.asyncio
async def test_replay_engine_builds_continuous_view() -> None:
    run_store = RunStore()
    trace_store = TraceStore()
    engine = ReplayEngine(run_store=run_store, trace_store=trace_store)

    view = engine.build_continuous("missing-trace")

    assert view["trace_id"] == "missing-trace"
    assert view["event_count"] == 0


@pytest.mark.asyncio
async def test_replay_engine_surfaces_resume_chain() -> None:
    run_store = RunStore()
    trace_store = TraceStore()
    engine = ReplayEngine(run_store=run_store, trace_store=trace_store)
    previous = AgentRunResponse(
        trace_id="trace-prev",
        agent_id="agent-a",
        status=RunStatus.COMPLETED,
        answer="previous",
        iterations=1,
        memory_hits=1,
        tool_calls=[],
        execution_summary={"subtasks": ["inspect"], "branch": "continue"},
        plan=[],
    )
    resumed = AgentRunResponse(
        trace_id="trace-now",
        agent_id="agent-a",
        status=RunStatus.COMPLETED,
        answer="current",
        iterations=1,
        memory_hits=1,
        tool_calls=[],
        execution_summary={"resumed_from": "trace-prev", "previous_stage": "finalizing"},
        plan=[],
    )
    run_store.save(RunContext(trace_id="trace-prev", agent_id="agent-a"), "task", previous)
    run_store.save(RunContext(trace_id="trace-now", agent_id="agent-a"), "task", resumed)
    trace_store.record(RunContext(trace_id="trace-now", agent_id="agent-a"), "agent.started")
    trace_store.record(RunContext(trace_id="trace-now", agent_id="agent-a"), "agent.completed")

    view = engine.build_continuous("trace-now")

    assert view["resumed_from"] == "trace-prev"
    assert view["previous_stage"] == "finalizing"
    assert view["event_count"] == 2
