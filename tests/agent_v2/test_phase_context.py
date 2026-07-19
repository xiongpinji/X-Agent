"""Tests for PhaseContext."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.core.agent_phases import PhaseContext
from backend.app.core.contracts import (
    ExecutionFrame,
    PlanFrame,
    TaskFrame,
)


class TestPhaseContext:
    """Test suite for PhaseContext."""

    def test_phase_context_initialization(self, phase_context: PhaseContext) -> None:
        """Test PhaseContext initialization."""
        assert phase_context.loop is not None
        assert phase_context.context is not None
        assert phase_context.task == "Test task"
        assert phase_context.trajectory is not None
        assert phase_context.extra_context == {"test": True}
        assert phase_context.execution_frame is not None
        assert phase_context.task_frame is not None
        assert phase_context.plan_frame is not None
        assert phase_context.compact_context == {"test": True}
        assert phase_context.tool_calls == []
        assert phase_context.observations == []
        assert phase_context.answer == ""
        assert phase_context.iteration == 0

    def test_phase_context_with_custom_values(
        self,
        agent_loop,
        run_context,
        task_frame,
        execution_frame,
        plan_frame,
        agent_trajectory,
    ) -> None:
        """Test PhaseContext with custom values."""
        custom_tool_calls = [{"tool": "test", "result": "success"}]
        custom_observations = ["obs1", "obs2"]
        custom_answer = "Test answer"
        custom_iteration = 5

        phase_ctx = PhaseContext(
            loop=agent_loop,
            context=run_context,
            task="Custom task",
            trajectory=agent_trajectory,
            extra_context={"custom": True},
            execution_frame=execution_frame,
            task_frame=task_frame,
            plan_frame=plan_frame,
            compact_context={"custom": True},
            tool_calls=custom_tool_calls,
            observations=custom_observations,
            answer=custom_answer,
            iteration=custom_iteration,
        )

        assert phase_ctx.task == "Custom task"
        assert phase_ctx.extra_context == {"custom": True}
        assert phase_ctx.tool_calls == custom_tool_calls
        assert phase_ctx.observations == custom_observations
        assert phase_ctx.answer == custom_answer
        assert phase_ctx.iteration == custom_iteration

    def test_phase_context_mutation(self, phase_context: PhaseContext) -> None:
        """Test PhaseContext mutation."""
        # Modify fields
        phase_context.answer = "Updated answer"
        phase_context.iteration = 3
        phase_context.observations.append("new_observation")
        phase_context.tool_calls.append({"tool": "new_tool"})

        assert phase_context.answer == "Updated answer"
        assert phase_context.iteration == 3
        assert "new_observation" in phase_context.observations
        assert {"tool": "new_tool"} in phase_context.tool_calls

    def test_phase_context_execution_frame_access(
        self, phase_context: PhaseContext
    ) -> None:
        """Test accessing execution frame through phase context."""
        assert phase_context.execution_frame.trace_id is not None
        assert phase_context.execution_frame.agent_id is not None
        assert phase_context.execution_frame.tenant_id == "test-tenant"
        assert phase_context.execution_frame.user_id == "test-user"
        assert phase_context.execution_frame.task is not None

    def test_phase_context_task_frame_access(
        self, phase_context: PhaseContext
    ) -> None:
        """Test accessing task frame through phase context."""
        assert phase_context.task_frame.goal == "Test goal"
        assert phase_context.task_frame.description == "Test task description"
        assert phase_context.task_frame.risk_level.value == "low"
        assert phase_context.task_frame.requires_approval is False

    def test_phase_context_plan_frame_access(
        self, phase_context: PhaseContext
    ) -> None:
        """Test accessing plan frame through phase context."""
        assert phase_context.plan_frame.goal == "Test plan goal"
        assert len(phase_context.plan_frame.steps) == 3
        assert phase_context.plan_frame.status == "draft"
        assert phase_context.plan_frame.revision == 0

    def test_phase_context_trajectory_access(
        self, phase_context: PhaseContext
    ) -> None:
        """Test accessing trajectory through phase context."""
        assert phase_context.trajectory.task == "Test task"
        assert phase_context.trajectory.goal == "Test goal"
        assert phase_context.trajectory.stage == "planning"
        assert len(phase_context.trajectory.subtasks) == 2

    def test_phase_context_loop_access(self, phase_context: PhaseContext) -> None:
        """Test accessing loop through phase context."""
        assert phase_context.loop is not None
        assert phase_context.loop.max_iterations == 4
        assert phase_context.loop.state_manager is not None
        assert phase_context.loop.runtime_adapter is not None

    def test_phase_context_context_access(self, phase_context: PhaseContext) -> None:
        """Test accessing run context through phase context."""
        assert phase_context.context.trace_id is not None
        assert phase_context.context.tenant_id == "test-tenant"
        assert phase_context.context.user_id == "test-user"
        assert phase_context.context.session_id is not None

    def test_phase_context_empty_collections(
        self,
        agent_loop,
        run_context,
        task_frame,
        execution_frame,
        plan_frame,
        agent_trajectory,
    ) -> None:
        """Test PhaseContext with empty collections."""
        phase_ctx = PhaseContext(
            loop=agent_loop,
            context=run_context,
            task="Test task",
            trajectory=agent_trajectory,
            extra_context={},
            execution_frame=execution_frame,
            task_frame=task_frame,
            plan_frame=plan_frame,
            compact_context={},
            tool_calls=[],
            observations=[],
            answer="",
            iteration=0,
        )

        assert phase_ctx.extra_context == {}
        assert phase_ctx.compact_context == {}
        assert phase_ctx.tool_calls == []
        assert phase_ctx.observations == []

    def test_phase_context_large_collections(
        self,
        agent_loop,
        run_context,
        task_frame,
        execution_frame,
        plan_frame,
        agent_trajectory,
    ) -> None:
        """Test PhaseContext with large collections."""
        large_observations = [f"obs_{i}" for i in range(100)]
        large_tool_calls = [{"tool": f"tool_{i}", "result": "success"} for i in range(50)]

        phase_ctx = PhaseContext(
            loop=agent_loop,
            context=run_context,
            task="Test task",
            trajectory=agent_trajectory,
            extra_context={},
            execution_frame=execution_frame,
            task_frame=task_frame,
            plan_frame=plan_frame,
            compact_context={},
            tool_calls=large_tool_calls,
            observations=large_observations,
            answer="",
            iteration=0,
        )

        assert len(phase_ctx.observations) == 100
        assert len(phase_ctx.tool_calls) == 50
        assert phase_ctx.observations[0] == "obs_0"
        assert phase_ctx.tool_calls[0]["tool"] == "tool_0"

    def test_phase_context_nested_metadata(
        self,
        agent_loop,
        run_context,
        task_frame,
        execution_frame,
        plan_frame,
        agent_trajectory,
    ) -> None:
        """Test PhaseContext with nested metadata."""
        nested_context = {
            "level1": {
                "level2": {
                    "level3": "value",
                    "list": [1, 2, 3],
                }
            },
            "array": [{"key": "value"}],
        }

        phase_ctx = PhaseContext(
            loop=agent_loop,
            context=run_context,
            task="Test task",
            trajectory=agent_trajectory,
            extra_context=nested_context,
            execution_frame=execution_frame,
            task_frame=task_frame,
            plan_frame=plan_frame,
            compact_context=nested_context,
            tool_calls=[],
            observations=[],
            answer="",
            iteration=0,
        )

        assert phase_ctx.extra_context["level1"]["level2"]["level3"] == "value"
        assert phase_ctx.compact_context["array"][0]["key"] == "value"
