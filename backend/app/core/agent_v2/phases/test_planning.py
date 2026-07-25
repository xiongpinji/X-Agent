"""Tests for PlanningPhase implementation.

Verifies:
- Plan generation and refinement
- Resume handling
- Subtask alignment
- Plan deduplication
- Complexity metrics
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.core.agent import AgentPlanStep, AgentTrajectory
from backend.app.core.agent_phases import PhaseContext
from backend.app.core.agent_v2.phases.planning import PlanningPhase
from backend.app.core.contracts import (
    ExecutionFrame,
    PlanFrame,
    RunContext,
    TaskFrame,
)


@pytest.fixture
def mock_loop():
    """Create mock AgentLoop."""
    loop = MagicMock()
    loop._plan = AsyncMock(return_value=[
        AgentPlanStep(kind="observe", instruction="Observe context"),
        AgentPlanStep(kind="tool", instruction="Execute tool", tool_name="read_file"),
        AgentPlanStep(kind="final", instruction="Finalize answer"),
    ])
    loop._apply_execution_plan = MagicMock(side_effect=lambda x, _: x)
    loop._dedupe_plan_steps = MagicMock(side_effect=lambda _, x: x)
    loop._align_plan_with_subtasks = MagicMock(side_effect=lambda x, _: x)
    loop._emit_trace = MagicMock()
    loop.run_store = None
    return loop


@pytest.fixture
def mock_context():
    """Create mock RunContext."""
    return RunContext(
        trace_id="test-trace-123",
        tenant_id="test-tenant",
        user_id="test-user",
        request_id="test-request",
        agent_id="test-agent",
    )


@pytest.fixture
def mock_trajectory():
    """Create mock AgentTrajectory."""
    return AgentTrajectory(
        task="Test task",
        goal="Test goal",
        subtasks=["subtask1", "subtask2"],
    )


@pytest.fixture
def phase_context(mock_loop, mock_context, mock_trajectory):
    """Create PhaseContext for testing."""
    return PhaseContext(
        loop=mock_loop,
        context=mock_context,
        task="Test task",
        trajectory=mock_trajectory,
        extra_context={},
        execution_frame=ExecutionFrame(
            trace_id="test-trace-123",
            agent_id="test-agent",
            tenant_id="test-tenant",
            user_id="test-user",
            request_id="test-request",
            task=TaskFrame(
                goal="Test goal",
                description="Test description",
                risk_level="low",
            ),
        ),
        task_frame=TaskFrame(
            goal="Test goal",
            description="Test description",
            risk_level="low",
        ),
        plan_frame=PlanFrame(
            steps=[],
            status="pending",
        ),
        compact_context={
            "draft_plan": {},
            "tool_decision": {},
            "orchestration_recovery_hint": {},
        },
        tool_calls=[],
        observations=[],
    )


@pytest.mark.asyncio
async def test_planning_phase_basic_execution(phase_context):
    """Test basic planning phase execution."""
    phase = PlanningPhase()
    plan = await phase.execute(phase_context)

    assert len(plan) == 3
    assert plan[0].kind == "observe"
    assert plan[1].kind == "tool"
    assert plan[2].kind == "final"


@pytest.mark.asyncio
async def test_planning_phase_initializes_plan_frame(phase_context):
    """Test that plan frame is initialized."""
    phase = PlanningPhase()
    await phase.execute(phase_context)

    assert phase_context.plan_frame.steps is not None
    assert len(phase_context.plan_frame.steps) == 3
    assert phase_context.plan_frame.status == "ready"
    assert phase_context.plan_frame.revision >= 1


@pytest.mark.asyncio
async def test_planning_phase_emits_events(phase_context):
    """Test that planning phase emits trace events."""
    phase = PlanningPhase()
    await phase.execute(phase_context)

    # Should emit task.decomposed and plan.created events
    assert phase_context.loop._emit_trace.call_count >= 2


@pytest.mark.asyncio
async def test_planning_phase_with_resume(phase_context):
    """Test planning phase with resume scenario."""
    phase_context.extra_context["resume_trace_id"] = "previous-trace-123"

    # Mock run store with previous run
    previous_run = MagicMock()
    previous_run.plan = [
        AgentPlanStep(kind="observe", instruction="Observe context"),
    ]
    previous_run.execution_summary = {"status": "partial"}
    previous_run.status.value = "PARTIAL"

    phase_context.loop.run_store = MagicMock()
    phase_context.loop.run_store.get = MagicMock(return_value=previous_run)

    phase = PlanningPhase()
    await phase.execute(phase_context)

    # Should emit resumed event
    phase_context.loop._emit_trace.assert_any_call(
        phase_context.context,
        "agent.resumed",
        resumed_from="previous-trace-123",
        stage=phase_context.trajectory.stage,
    )


@pytest.mark.asyncio
async def test_planning_phase_deduplicates_steps(phase_context):
    """Test that planning phase deduplicates steps."""
    phase_context.loop._dedupe_plan_steps = MagicMock(
        side_effect=lambda _, x: [step for step in x if step.kind != "observe"]
    )

    phase = PlanningPhase()
    await phase.execute(phase_context)

    # Deduplication should be called
    assert phase_context.loop._dedupe_plan_steps.called


@pytest.mark.asyncio
async def test_planning_phase_updates_execution_frame(phase_context):
    """Test that execution frame is updated with plan info."""
    phase = PlanningPhase()
    await phase.execute(phase_context)

    assert phase_context.execution_frame.plan is not None
    assert phase_context.execution_frame.plan.status == "ready"


def test_filter_by_completed_kinds():
    """Test filtering plan by completed kinds."""
    phase = PlanningPhase()
    plan = [
        AgentPlanStep(kind="observe", instruction="Observe"),
        AgentPlanStep(kind="tool", instruction="Tool"),
        AgentPlanStep(kind="final", instruction="Final"),
    ]
    resume_payload = {"completed_kinds": ["observe"]}

    filtered = phase._filter_by_completed_kinds(plan, resume_payload)

    assert len(filtered) == 2
    assert filtered[0].kind == "tool"
    assert filtered[1].kind == "final"


def test_filter_by_completed_labels():
    """Test filtering plan by completed labels."""
    phase = PlanningPhase()
    plan = [
        AgentPlanStep(kind="observe", instruction="Observe context"),
        AgentPlanStep(kind="tool", instruction="Execute tool"),
        AgentPlanStep(kind="final", instruction="Finalize answer"),
    ]
    resume_payload = {"completed_step_labels": ["Observe context"]}

    filtered = phase._filter_by_completed_labels(plan, resume_payload)

    assert len(filtered) == 2
    assert filtered[0].instruction == "Execute tool"
    assert filtered[1].instruction == "Finalize answer"


def test_get_resume_payload_no_run_store():
    """Test get_resume_payload when run_store is None."""
    phase = PlanningPhase()
    loop = MagicMock()
    loop.run_store = None

    payload = phase._get_resume_payload(loop, "trace-123")

    assert payload == {}


def test_get_resume_payload_with_run_store():
    """Test get_resume_payload with valid run store."""
    phase = PlanningPhase()
    loop = MagicMock()

    previous_run = MagicMock()
    previous_run.plan = [
        AgentPlanStep(kind="observe", instruction="Observe"),
        AgentPlanStep(kind="tool", instruction="Tool"),
    ]
    previous_run.execution_summary = {"status": "partial"}
    previous_run.status.value = "PARTIAL"

    loop.run_store = MagicMock()
    loop.run_store.get = MagicMock(return_value=previous_run)

    payload = phase._get_resume_payload(loop, "trace-123")

    assert "completed_kinds" in payload
    assert "completed_step_labels" in payload
    assert len(payload["completed_kinds"]) == 2
    assert payload["previous_status"] == "PARTIAL"


def test_initialize_plan_frame():
    """Test plan frame initialization."""
    phase = PlanningPhase()
    phase_ctx = MagicMock()
    phase_ctx.plan_frame.steps = []

    plan = [
        AgentPlanStep(kind="observe", instruction="Observe"),
        AgentPlanStep(kind="final", instruction="Final"),
    ]

    phase._initialize_plan_frame(phase_ctx, plan)

    assert phase_ctx.plan_frame.steps == ["Observe", "Final"]
    assert phase_ctx.plan_frame.status == "ready"
    assert phase_ctx.plan_frame.revision == 1


def test_finalize_plan_frame():
    """Test plan frame finalization."""
    phase = PlanningPhase()
    phase_ctx = MagicMock()
    phase_ctx.plan_frame = MagicMock()
    phase_ctx.execution_frame = MagicMock()
    phase_ctx.compact_context = {
        "draft_plan": {"steps": 3},
        "tool_decision": {"tool": "read_file"},
        "orchestration_recovery_hint": {"branch": "continue"},
    }

    plan = [
        AgentPlanStep(kind="observe", instruction="Observe"),
        AgentPlanStep(kind="final", instruction="Final"),
    ]

    phase._finalize_plan_frame(phase_ctx, plan)

    assert phase_ctx.plan_frame.steps == ["Observe", "Final"]
    assert phase_ctx.plan_frame.status == "ready"
    phase_ctx.execution_frame.execution_summary.update.assert_called_once()


# Complexity metrics test
def test_planning_phase_complexity():
    """Verify PlanningPhase meets complexity targets.

    Target: <80 lines, cyclomatic complexity <8
    """
    import inspect

    phase = PlanningPhase()

    # Check main execute method
    execute_source = inspect.getsource(phase.execute)
    execute_lines = len(execute_source.split('\n'))

    # Should be under 80 lines
    assert execute_lines < 80, f"execute() has {execute_lines} lines, target <80"

    # Check helper methods are reasonably sized
    for method_name in [
        "_generate_plan",
        "_initialize_plan_frame",
        "_handle_resume",
        "_get_resume_payload",
        "_filter_by_completed_kinds",
        "_filter_by_completed_labels",
        "_finalize_plan_frame",
    ]:
        method = getattr(phase, method_name)
        source = inspect.getsource(method)
        lines = len(source.split('\n'))
        assert lines < 50, f"{method_name}() has {lines} lines, target <50"
