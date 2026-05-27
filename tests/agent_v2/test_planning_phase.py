"""Tests for PlanningPhase."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.core.agent import AgentPlanStep
from backend.app.core.agent_phases import PlanningPhase, PhaseContext


class TestPlanningPhase:
    """Test suite for PlanningPhase."""

    @pytest.mark.asyncio
    async def test_planning_phase_execute(
        self, phase_context: PhaseContext
    ) -> None:
        """Test PlanningPhase.execute()."""
        phase = PlanningPhase()

        # Create mock plan steps
        plan_steps = [
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
        phase_context.loop._plan = AsyncMock(return_value=plan_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=plan_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=plan_steps)
        phase_context.loop._emit_trace = MagicMock()

        result = await phase.execute(phase_context)

        # Verify plan was generated
        assert result is not None
        assert len(result) == 3
        assert result[0].kind == "tool"
        assert result[1].kind == "observe"
        assert result[2].kind == "reflect"

    @pytest.mark.asyncio
    async def test_planning_phase_plan_frame_update(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that PlanningPhase updates plan frame."""
        phase = PlanningPhase()

        plan_steps = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        phase_context.loop._plan = AsyncMock(return_value=plan_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=plan_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=plan_steps)
        phase_context.loop._emit_trace = MagicMock()

        await phase.execute(phase_context)

        # Verify plan frame was updated
        assert phase_context.plan_frame.steps is not None
        assert len(phase_context.plan_frame.steps) > 0
        assert phase_context.plan_frame.status == "ready"
        assert phase_context.plan_frame.revision > 0

    @pytest.mark.asyncio
    async def test_planning_phase_with_resume(
        self, phase_context: PhaseContext
    ) -> None:
        """Test PlanningPhase with resume context."""
        phase = PlanningPhase()

        # Set resume trace ID
        phase_context.extra_context["resume_trace_id"] = str(uuid4())

        plan_steps = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        phase_context.loop._plan = AsyncMock(return_value=plan_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=plan_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=plan_steps)
        phase_context.loop._emit_trace = MagicMock()

        result = await phase.execute(phase_context)

        # Verify resume trace was emitted
        phase_context.loop._emit_trace.assert_called()
        assert result is not None

    @pytest.mark.asyncio
    async def test_planning_phase_with_subtasks(
        self, phase_context: PhaseContext
    ) -> None:
        """Test PlanningPhase with subtasks."""
        phase = PlanningPhase()

        # Set subtasks
        phase_context.trajectory.subtasks = ["subtask1", "subtask2", "subtask3"]

        plan_steps = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        phase_context.loop._plan = AsyncMock(return_value=plan_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=plan_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=plan_steps)
        phase_context.loop._emit_trace = MagicMock()

        result = await phase.execute(phase_context)

        # Verify subtask decomposition trace was emitted
        phase_context.loop._emit_trace.assert_called()
        assert result is not None

    @pytest.mark.asyncio
    async def test_planning_phase_empty_plan(
        self, phase_context: PhaseContext
    ) -> None:
        """Test PlanningPhase with empty plan."""
        phase = PlanningPhase()

        plan_steps = []

        phase_context.loop._plan = AsyncMock(return_value=plan_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=plan_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=plan_steps)
        phase_context.loop._emit_trace = MagicMock()

        result = await phase.execute(phase_context)

        # Verify empty plan is handled
        assert result == []

    @pytest.mark.asyncio
    async def test_planning_phase_large_plan(
        self, phase_context: PhaseContext
    ) -> None:
        """Test PlanningPhase with large plan."""
        phase = PlanningPhase()

        # Create a large plan
        plan_steps = [
            AgentPlanStep(
                kind="tool" if i % 2 == 0 else "observe",
                instruction=f"Step {i}",
                tool_name=f"tool_{i}" if i % 2 == 0 else None,
            )
            for i in range(50)
        ]

        phase_context.loop._plan = AsyncMock(return_value=plan_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=plan_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=plan_steps)
        phase_context.loop._emit_trace = MagicMock()

        result = await phase.execute(phase_context)

        # Verify large plan is handled
        assert len(result) == 50

    @pytest.mark.asyncio
    async def test_planning_phase_plan_deduplication(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that PlanningPhase deduplicates plan steps."""
        phase = PlanningPhase()

        original_steps = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        deduplicated_steps = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        phase_context.loop._plan = AsyncMock(return_value=original_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=original_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=deduplicated_steps)
        phase_context.loop._emit_trace = MagicMock()

        result = await phase.execute(phase_context)

        # Verify deduplication was called
        phase_context.loop._dedupe_plan_steps.assert_called()

    @pytest.mark.asyncio
    async def test_planning_phase_execution_frame_update(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that PlanningPhase updates execution frame."""
        phase = PlanningPhase()

        plan_steps = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        phase_context.loop._plan = AsyncMock(return_value=plan_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=plan_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=plan_steps)
        phase_context.loop._emit_trace = MagicMock()

        await phase.execute(phase_context)

        # Verify execution frame plan was updated
        assert phase_context.execution_frame.plan is not None

    @pytest.mark.asyncio
    async def test_planning_phase_trace_emission(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that PlanningPhase emits traces."""
        phase = PlanningPhase()

        plan_steps = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        phase_context.loop._plan = AsyncMock(return_value=plan_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=plan_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=plan_steps)
        phase_context.loop._emit_trace = MagicMock()

        await phase.execute(phase_context)

        # Verify trace was emitted
        phase_context.loop._emit_trace.assert_called()

    @pytest.mark.asyncio
    async def test_planning_phase_with_mixed_step_kinds(
        self, phase_context: PhaseContext
    ) -> None:
        """Test PlanningPhase with mixed step kinds."""
        phase = PlanningPhase()

        plan_steps = [
            AgentPlanStep(kind="tool", instruction="Tool step", tool_name="tool_1"),
            AgentPlanStep(kind="observe", instruction="Observe step"),
            AgentPlanStep(kind="reflect", instruction="Reflect step"),
            AgentPlanStep(kind="final", instruction="Final step"),
        ]

        phase_context.loop._plan = AsyncMock(return_value=plan_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=plan_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=plan_steps)
        phase_context.loop._emit_trace = MagicMock()

        result = await phase.execute(phase_context)

        # Verify all step kinds are present
        assert len(result) == 4
        kinds = [step.kind for step in result]
        assert "tool" in kinds
        assert "observe" in kinds
        assert "reflect" in kinds
        assert "final" in kinds

    @pytest.mark.asyncio
    async def test_planning_phase_plan_application(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that PlanningPhase applies execution plan."""
        phase = PlanningPhase()

        original_steps = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1",
                tool_name="tool_1",
            ),
        ]

        applied_steps = [
            AgentPlanStep(
                kind="tool",
                instruction="Execute tool 1 (applied)",
                tool_name="tool_1",
            ),
        ]

        phase_context.loop._plan = AsyncMock(return_value=original_steps)
        phase_context.loop._apply_execution_plan = MagicMock(return_value=applied_steps)
        phase_context.loop._dedupe_plan_steps = MagicMock(return_value=applied_steps)
        phase_context.loop._emit_trace = MagicMock()

        result = await phase.execute(phase_context)

        # Verify execution plan was applied
        phase_context.loop._apply_execution_plan.assert_called()
        assert result[0].instruction == "Execute tool 1 (applied)"
