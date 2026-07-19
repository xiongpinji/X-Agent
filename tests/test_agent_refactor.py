"""Tests for AgentLoop refactoring phases."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.core.agent_phases import (
    InitializationPhase,
    PlanningPhase,
    ExecutionPhase,
    CompletionPhase,
    PhaseContext,
)
from backend.app.core.contracts import RunContext, AgentRunResponse, RunStatus


class TestInitializationPhase:
    """Tests for InitializationPhase."""

    @pytest.mark.asyncio
    async def test_initialization_creates_task_frame(self):
        """Test that initialization phase creates task frame."""
        mock_loop = MagicMock()
        mock_loop._derive_goal = MagicMock(return_value="Test goal")
        mock_loop._dump_model = MagicMock(return_value={})
        mock_loop.state_manager = MagicMock()
        mock_loop.orchestrator = MagicMock()
        # orchestrator.prepare returns a 3-tuple (orchestration_context,
        # capability_decision, recovery_hint); a bare MagicMock iterates empty
        # and would raise "not enough values to unpack (expected 3, got 0)".
        mock_loop.orchestrator.prepare = MagicMock(
            return_value=(MagicMock(), MagicMock(), MagicMock())
        )
        mock_loop._emit_trace = MagicMock()

        context = RunContext(
            trace_id="test-trace",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

        trajectory = MagicMock()
        trajectory.task = "Test task"
        trajectory.goal = "Test goal"

        phase_ctx = PhaseContext(
            loop=mock_loop,
            context=context,
            task="Test task",
            trajectory=trajectory,
            extra_context={},
            execution_frame=None,
            task_frame=None,
            plan_frame=None,
            compact_context={},
            tool_calls=[],
            observations=[],
        )

        phase = InitializationPhase()
        await phase.execute(phase_ctx)

        assert phase_ctx.task_frame is not None
        assert phase_ctx.execution_frame is not None
        mock_loop._emit_trace.assert_called()

    @pytest.mark.asyncio
    async def test_initialization_calls_orchestrator(self):
        """Test that initialization calls orchestrator."""
        mock_loop = MagicMock()
        mock_loop._derive_goal = MagicMock(return_value="Test goal")
        mock_loop._dump_model = MagicMock(return_value={})
        mock_loop.state_manager = MagicMock()
        mock_loop.orchestrator = MagicMock()
        # orchestrator.prepare returns a 3-tuple; configure it so unpacking works.
        mock_loop.orchestrator.prepare = MagicMock(
            return_value=(MagicMock(), MagicMock(), MagicMock())
        )
        mock_loop._emit_trace = MagicMock()

        context = RunContext(
            trace_id="test-trace",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

        trajectory = MagicMock()
        trajectory.task = "Test task"
        trajectory.goal = "Test goal"

        phase_ctx = PhaseContext(
            loop=mock_loop,
            context=context,
            task="Test task",
            trajectory=trajectory,
            extra_context={},
            execution_frame=None,
            task_frame=None,
            plan_frame=None,
            compact_context={},
            tool_calls=[],
            observations=[],
        )

        phase = InitializationPhase()
        await phase.execute(phase_ctx)

        mock_loop.orchestrator.prepare.assert_called_once()
        mock_loop.orchestrator.draft_plan.assert_called_once()
        mock_loop.orchestrator.select_tool.assert_called_once()


class TestPlanningPhase:
    """Tests for PlanningPhase."""

    @pytest.mark.asyncio
    async def test_planning_generates_plan(self):
        """Test that planning phase generates plan."""
        mock_loop = MagicMock()
        mock_loop._plan = AsyncMock(return_value=[])
        mock_loop._apply_execution_plan = MagicMock(return_value=[])
        mock_loop._dedupe_plan_steps = MagicMock(return_value=[])
        mock_loop._emit_trace = MagicMock()

        context = RunContext(
            trace_id="test-trace",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

        trajectory = MagicMock()
        trajectory.task = "Test task"
        trajectory.goal = "Test goal"
        trajectory.subtasks = []

        plan_frame = MagicMock()
        plan_frame.steps = []
        plan_frame.status = "pending"
        plan_frame.revision = 0

        phase_ctx = PhaseContext(
            loop=mock_loop,
            context=context,
            task="Test task",
            trajectory=trajectory,
            extra_context={},
            execution_frame=MagicMock(),
            task_frame=MagicMock(),
            plan_frame=plan_frame,
            compact_context={},
            tool_calls=[],
            observations=[],
        )

        phase = PlanningPhase()
        plan = await phase.execute(phase_ctx)

        assert isinstance(plan, list)
        mock_loop._plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_planning_deduplicates_steps(self):
        """Test that planning phase deduplicates steps."""
        mock_loop = MagicMock()
        mock_loop._plan = AsyncMock(return_value=[])
        mock_loop._apply_execution_plan = MagicMock(return_value=[])
        mock_loop._dedupe_plan_steps = MagicMock(return_value=[])
        mock_loop._emit_trace = MagicMock()

        context = RunContext(
            trace_id="test-trace",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

        trajectory = MagicMock()
        trajectory.task = "Test task"
        trajectory.goal = "Test goal"
        trajectory.subtasks = []

        plan_frame = MagicMock()
        plan_frame.steps = []
        plan_frame.status = "pending"
        plan_frame.revision = 0

        phase_ctx = PhaseContext(
            loop=mock_loop,
            context=context,
            task="Test task",
            trajectory=trajectory,
            extra_context={},
            execution_frame=MagicMock(),
            task_frame=MagicMock(),
            plan_frame=plan_frame,
            compact_context={},
            tool_calls=[],
            observations=[],
        )

        phase = PlanningPhase()
        await phase.execute(phase_ctx)

        assert mock_loop._dedupe_plan_steps.call_count >= 1


class TestExecutionPhase:
    """Tests for ExecutionPhase."""

    @pytest.mark.asyncio
    async def test_execution_handles_empty_plan(self):
        """Test that execution phase handles empty plan."""
        mock_loop = MagicMock()
        mock_loop.max_iterations = 4
        mock_loop._should_defer_step = MagicMock(return_value=False)
        mock_loop._finalize_answer = MagicMock(return_value="Test answer")

        context = RunContext(
            trace_id="test-trace",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

        trajectory = MagicMock()
        trajectory.task = "Test task"
        trajectory.goal = "Test goal"
        trajectory.observations = []
        trajectory.tool_results = []
        trajectory.reflections = []
        trajectory.subtask_status = {}

        phase_ctx = PhaseContext(
            loop=mock_loop,
            context=context,
            task="Test task",
            trajectory=trajectory,
            extra_context={},
            execution_frame=MagicMock(),
            task_frame=MagicMock(),
            plan_frame=MagicMock(),
            compact_context={},
            tool_calls=[],
            observations=[],
        )

        phase = ExecutionPhase()
        answer, tool_calls = await phase.execute(phase_ctx, [])

        assert answer == "Test answer"
        assert tool_calls == []

    @pytest.mark.asyncio
    async def test_execution_respects_max_iterations(self):
        """Test that execution phase respects max iterations."""
        mock_loop = MagicMock()
        mock_loop.max_iterations = 2
        mock_loop._should_defer_step = MagicMock(return_value=False)
        mock_loop._finalize_answer = MagicMock(return_value="Test answer")

        context = RunContext(
            trace_id="test-trace",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

        trajectory = MagicMock()
        trajectory.task = "Test task"
        trajectory.goal = "Test goal"
        trajectory.observations = []
        trajectory.tool_results = []
        trajectory.reflections = []
        trajectory.subtask_status = {}

        phase_ctx = PhaseContext(
            loop=mock_loop,
            context=context,
            task="Test task",
            trajectory=trajectory,
            extra_context={},
            execution_frame=MagicMock(),
            task_frame=MagicMock(),
            plan_frame=MagicMock(),
            compact_context={},
            tool_calls=[],
            observations=[],
        )

        # Create mock steps
        mock_step = MagicMock()
        mock_step.kind = "final"
        mock_step.instruction = "Finalize"

        phase = ExecutionPhase()
        answer, tool_calls = await phase.execute(phase_ctx, [mock_step] * 10)

        assert phase_ctx.iteration <= mock_loop.max_iterations


class TestCompletionPhase:
    """Tests for CompletionPhase."""

    @pytest.mark.asyncio
    async def test_completion_builds_response(self):
        """Test that completion phase builds response."""
        mock_loop = MagicMock()
        mock_loop.memory = MagicMock()
        mock_loop.memory.store = AsyncMock(return_value="memory-id")
        mock_loop.memory.count = MagicMock(return_value=10)
        # max_iterations must be an int: CompletionPhase computes
        # min(phase_ctx.iteration, loop.max_iterations); a bare MagicMock here
        # raises "TypeError: '<' not supported between int and MagicMock".
        mock_loop.max_iterations = 4
        mock_loop.tools = MagicMock()
        mock_loop.tools.capability_index = MagicMock(return_value={})
        mock_loop.run_store = None
        mock_loop.runtime_adapter = MagicMock()
        mock_loop.runtime_adapter.build_run_view = MagicMock(return_value=MagicMock())
        mock_loop._record_audit = MagicMock()
        mock_loop._build_execution_summary = MagicMock(return_value={})
        mock_loop._emit_trace = MagicMock()

        context = RunContext(
            trace_id="test-trace",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

        trajectory = MagicMock()
        trajectory.task = "Test task"
        trajectory.goal = "Test goal"
        trajectory.stage = "completed"
        trajectory.observations = []
        trajectory.tool_results = []
        trajectory.reflections = []
        trajectory.subtask_status = {}
        trajectory.current_subtask_index = 0

        execution_frame = MagicMock()
        execution_frame.model_dump = MagicMock(return_value={})

        phase_ctx = PhaseContext(
            loop=mock_loop,
            context=context,
            task="Test task",
            trajectory=trajectory,
            extra_context={},
            execution_frame=execution_frame,
            task_frame=MagicMock(),
            plan_frame=MagicMock(),
            compact_context={},
            tool_calls=[],
            observations=[],
            answer="Test answer",
            iteration=1,
        )

        phase = CompletionPhase()
        result = await phase.execute(phase_ctx)

        assert isinstance(result, AgentRunResponse)
        assert result.status == RunStatus.COMPLETED
        assert result.answer == "Test answer"


class TestPhaseContext:
    """Tests for PhaseContext."""

    def test_phase_context_initialization(self):
        """Test that PhaseContext initializes correctly."""
        mock_loop = MagicMock()
        context = RunContext(
            trace_id="test-trace",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

        phase_ctx = PhaseContext(
            loop=mock_loop,
            context=context,
            task="Test task",
            trajectory=MagicMock(),
            extra_context={},
            execution_frame=None,
            task_frame=None,
            plan_frame=None,
            compact_context={},
            tool_calls=[],
            observations=[],
        )

        assert phase_ctx.loop == mock_loop
        assert phase_ctx.context == context
        assert phase_ctx.task == "Test task"
        assert phase_ctx.answer == ""
        assert phase_ctx.iteration == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
