"""Tests for ExecutionPhase."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.core.agent import AgentPlanStep
from backend.app.core.agent_phases import ExecutionPhase, PhaseContext
from backend.app.core.contracts import RiskLevel, ToolCallRecord, ToolPolicyVerdict


class TestExecutionPhase:
    """Test suite for ExecutionPhase."""

    @pytest.mark.asyncio
    async def test_execution_phase_execute(
        self, phase_context: PhaseContext
    ) -> None:
        """Test ExecutionPhase.execute()."""
        phase = ExecutionPhase()

        plan = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
                arguments={"arg1": "value1"},
            ),
            AgentPlanStep(
                kind="observe",
                instruction="Observe results",
            ),
            AgentPlanStep(
                kind="reflect",
                instruction="Reflect on results",
            ),
        ]

        # Mock the necessary methods
        phase_context.loop._should_defer_step = MagicMock(return_value=False)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._observe = AsyncMock(return_value="Observation result")
        phase_context.loop._build_tool_context = MagicMock(return_value={})
        phase_context.loop.tools.execute = AsyncMock(
            return_value=ToolCallRecord(
                tool_name="tool_1",
                success=True,
                output={"result": "success"},
                policy=ToolPolicyVerdict(
                    allowed=True,
                    reason="Test",
                    audit_required=True,
                ),
                risk_level=RiskLevel.LOW,
            )
        )
        phase_context.loop._stringify = MagicMock(return_value="Tool result")
        phase_context.loop._record_audit = MagicMock()
        phase_context.loop._mark_subtask_progress = MagicMock()
        phase_context.loop._reflect = MagicMock(return_value="Reflection")
        phase_context.loop._check_mainline = MagicMock()
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify execution completed
        assert answer is not None
        assert isinstance(tool_calls, list)

    @pytest.mark.asyncio
    async def test_execution_phase_tool_execution(
        self, phase_context: PhaseContext
    ) -> None:
        """Test ExecutionPhase tool execution."""
        phase = ExecutionPhase()

        plan = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
                arguments={"arg1": "value1"},
            ),
        ]

        tool_record = ToolCallRecord(
            tool_name="tool_1",
            success=True,
            output={"result": "success"},
            policy=ToolPolicyVerdict(
                allowed=True,
                reason="Test",
                audit_required=True,
            ),
            risk_level=RiskLevel.LOW,
        )

        phase_context.loop._should_defer_step = MagicMock(return_value=False)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._build_tool_context = MagicMock(return_value={})
        phase_context.loop.tools.execute = AsyncMock(return_value=tool_record)
        phase_context.loop._stringify = MagicMock(return_value="Tool result")
        phase_context.loop._record_audit = MagicMock()
        phase_context.loop._mark_subtask_progress = MagicMock()
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify tool was executed
        phase_context.loop.tools.execute.assert_called()
        assert len(tool_calls) > 0

    @pytest.mark.asyncio
    async def test_execution_phase_observation(
        self, phase_context: PhaseContext
    ) -> None:
        """Test ExecutionPhase observation step."""
        phase = ExecutionPhase()

        plan = [
            AgentPlanStep(
                kind="observe",
                instruction="Observe results",
            ),
        ]

        phase_context.loop._should_defer_step = MagicMock(return_value=False)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._observe = AsyncMock(return_value="Observation result")
        phase_context.loop._mark_subtask_progress = MagicMock()
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify observation was recorded
        phase_context.loop._observe.assert_called()
        assert "Observation result" in phase_context.trajectory.observations

    @pytest.mark.asyncio
    async def test_execution_phase_reflection(
        self, phase_context: PhaseContext
    ) -> None:
        """Test ExecutionPhase reflection step."""
        phase = ExecutionPhase()

        plan = [
            AgentPlanStep(
                kind="reflect",
                instruction="Reflect on results",
            ),
        ]

        phase_context.loop._should_defer_step = MagicMock(return_value=False)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._check_mainline = MagicMock()
        phase_context.loop._reflect = MagicMock(return_value="Reflection result")
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify reflection was recorded
        phase_context.loop._reflect.assert_called()
        assert "Reflection result" in phase_context.trajectory.reflections

    @pytest.mark.asyncio
    async def test_execution_phase_final_step(
        self, phase_context: PhaseContext
    ) -> None:
        """Test ExecutionPhase final step."""
        phase = ExecutionPhase()

        plan = [
            AgentPlanStep(
                kind="final",
                instruction="Finalize answer",
            ),
        ]

        phase_context.loop._should_defer_step = MagicMock(return_value=False)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._mark_subtask_progress = MagicMock()
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify final answer was generated
        assert answer == "Final answer"

    @pytest.mark.asyncio
    async def test_execution_phase_max_iterations(
        self, phase_context: PhaseContext
    ) -> None:
        """Test ExecutionPhase respects max iterations."""
        phase = ExecutionPhase()

        # Create plan with more steps than max_iterations
        plan = [
            AgentPlanStep(
                kind="tool",
                instruction=f"Execute tool {i}",
                tool_name=f"tool_{i}",
            )
            for i in range(10)
        ]

        phase_context.loop.max_iterations = 4
        phase_context.loop._should_defer_step = MagicMock(return_value=False)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._build_tool_context = MagicMock(return_value={})
        phase_context.loop.tools.execute = AsyncMock(
            return_value=ToolCallRecord(
                tool_name="tool_1",
                success=True,
                output={"result": "success"},
                policy=ToolPolicyVerdict(
                    allowed=True,
                    reason="Test",
                    audit_required=True,
                ),
                risk_level=RiskLevel.LOW,
            )
        )
        phase_context.loop._stringify = MagicMock(return_value="Tool result")
        phase_context.loop._record_audit = MagicMock()
        phase_context.loop._mark_subtask_progress = MagicMock()
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify max iterations was respected
        assert phase_context.iteration <= phase_context.loop.max_iterations

    @pytest.mark.asyncio
    async def test_execution_phase_deferred_steps(
        self, phase_context: PhaseContext
    ) -> None:
        """Test ExecutionPhase with deferred steps."""
        phase = ExecutionPhase()

        plan = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        phase_context.loop._should_defer_step = MagicMock(return_value=True)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify deferred step was handled
        assert answer is not None

    @pytest.mark.asyncio
    async def test_execution_phase_tool_failure(
        self, phase_context: PhaseContext
    ) -> None:
        """Test ExecutionPhase with tool failure."""
        phase = ExecutionPhase()

        plan = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
                arguments={"arg1": "value1"},
            ),
        ]

        failed_record = ToolCallRecord(
            tool_name="tool_1",
            success=False,
            output=None,
            error="Tool execution failed",
            policy=ToolPolicyVerdict(
                allowed=True,
                reason="Test",
                audit_required=True,
            ),
            risk_level=RiskLevel.LOW,
        )

        phase_context.loop._should_defer_step = MagicMock(return_value=False)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._build_tool_context = MagicMock(return_value={})
        phase_context.loop.tools.execute = AsyncMock(return_value=failed_record)
        phase_context.loop._record_audit = MagicMock()
        phase_context.loop._mark_subtask_progress = MagicMock()
        phase_context.loop.repair_loop.analyze = MagicMock(
            return_value=(
                MagicMock(verified=False),
                MagicMock(
                    should_retry=False,
                    tool_name=None,
                    arguments={},
                    reason="Test",
                    error_type="test_error",
                    confidence=0.5,
                    follow_up=None,
                ),
            )
        )
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify tool failure was handled
        assert len(tool_calls) > 0
        assert tool_calls[0].success is False

    @pytest.mark.asyncio
    async def test_execution_phase_empty_plan(
        self, phase_context: PhaseContext
    ) -> None:
        """Test ExecutionPhase with empty plan."""
        phase = ExecutionPhase()

        plan = []

        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify empty plan is handled
        assert answer == "Final answer"
        assert tool_calls == []

    @pytest.mark.asyncio
    async def test_execution_phase_context_update(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that ExecutionPhase updates phase context."""
        phase = ExecutionPhase()

        plan = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        tool_record = ToolCallRecord(
            tool_name="tool_1",
            success=True,
            output={"result": "success"},
            policy=ToolPolicyVerdict(
                allowed=True,
                reason="Test",
                audit_required=True,
            ),
            risk_level=RiskLevel.LOW,
        )

        phase_context.loop._should_defer_step = MagicMock(return_value=False)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._build_tool_context = MagicMock(return_value={})
        phase_context.loop.tools.execute = AsyncMock(return_value=tool_record)
        phase_context.loop._stringify = MagicMock(return_value="Tool result")
        phase_context.loop._record_audit = MagicMock()
        phase_context.loop._mark_subtask_progress = MagicMock()
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        answer, tool_calls = await phase.execute(phase_context, plan)

        # Verify phase context was updated
        assert phase_context.answer == "Final answer"
        assert phase_context.tool_calls == tool_calls
        assert len(phase_context.observations) > 0

    @pytest.mark.asyncio
    async def test_execution_phase_trajectory_update(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that ExecutionPhase updates trajectory."""
        phase = ExecutionPhase()

        plan = [
            AgentPlanStep(
                kind="observe",
                instruction="Observe results",
            ),
        ]

        phase_context.loop._should_defer_step = MagicMock(return_value=False)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop._observe = AsyncMock(return_value="Observation result")
        phase_context.loop._mark_subtask_progress = MagicMock()
        phase_context.loop._finalize_answer = MagicMock(return_value="Final answer")

        await phase.execute(phase_context, plan)

        # Verify trajectory was updated
        assert len(phase_context.trajectory.observations) > 0
        assert phase_context.trajectory.stage != "planning"
