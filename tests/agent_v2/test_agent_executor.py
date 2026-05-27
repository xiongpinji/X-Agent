"""Integration tests for AgentExecutor (full agent execution flow)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.core.agent import AgentLoop, AgentPlanStep
from backend.app.core.contracts import (
    AgentRunRequest,
    RunContext,
    RunStatus,
    RiskLevel,
)


class TestAgentExecutor:
    """Integration test suite for full agent execution flow."""

    @pytest.mark.asyncio
    async def test_agent_full_execution_flow(
        self, agent_loop: AgentLoop, run_context: RunContext
    ) -> None:
        """Test full agent execution flow."""
        task = "Test task"
        extra_context = {"test": True}

        # Mock all necessary methods
        agent_loop._compress_context = MagicMock(return_value={"test": True})
        agent_loop._derive_goal = MagicMock(return_value="Test goal")
        agent_loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        agent_loop._decompose_task = MagicMock(return_value=["subtask1", "subtask2"])
        agent_loop._emit_trace = MagicMock(return_value=str(uuid4()))
        agent_loop._plan = AsyncMock(
            return_value=[
                AgentPlanStep(
                    kind="tool",
                    instruction="Execute tool",
                    tool_name="test_tool",
                ),
                AgentPlanStep(kind="reflect", instruction="Reflect"),
                AgentPlanStep(kind="final", instruction="Finalize"),
            ]
        )
        agent_loop._apply_execution_plan = MagicMock(
            side_effect=lambda x, **kwargs: x
        )
        agent_loop._dedupe_plan_steps = MagicMock(side_effect=lambda x, y: y)
        agent_loop._should_defer_step = MagicMock(return_value=False)
        agent_loop._build_tool_context = MagicMock(return_value={})
        agent_loop.tools.execute = AsyncMock(
            return_value=MagicMock(
                tool_name="test_tool",
                success=True,
                output={"result": "success"},
                policy=MagicMock(allowed=True, reason="Test"),
                risk_level=RiskLevel.LOW,
            )
        )
        agent_loop._stringify = MagicMock(return_value="Tool result")
        agent_loop._record_audit = MagicMock()
        agent_loop._mark_subtask_progress = MagicMock()
        agent_loop._verify_write_result = AsyncMock(return_value=None)
        agent_loop._repair_write_step = AsyncMock(return_value=None)
        agent_loop._maybe_replan_after_failure = MagicMock()
        agent_loop.repair_loop.analyze = MagicMock(
            return_value=(
                MagicMock(verified=True),
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
        agent_loop._check_mainline = MagicMock()
        agent_loop._reflect = MagicMock(return_value="Reflection")
        agent_loop._finalize_answer = MagicMock(return_value="Final answer")
        agent_loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        agent_loop.memory.store = AsyncMock(return_value=str(uuid4()))
        agent_loop.memory.count = MagicMock(return_value=10)

        # Execute agent
        result = await agent_loop.run(run_context, task, extra_context)

        # Verify result
        assert result is not None
        assert result.status == RunStatus.COMPLETED
        assert result.answer == "Final answer"
        assert result.trace_id == run_context.trace_id

    @pytest.mark.asyncio
    async def test_agent_execution_with_multiple_iterations(
        self, agent_loop: AgentLoop, run_context: RunContext
    ) -> None:
        """Test agent execution with multiple iterations."""
        task = "Multi-step task"

        agent_loop._compress_context = MagicMock(return_value={})
        agent_loop._derive_goal = MagicMock(return_value="Multi-step goal")
        agent_loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        agent_loop._decompose_task = MagicMock(return_value=[])
        agent_loop._emit_trace = MagicMock(return_value=str(uuid4()))
        agent_loop._plan = AsyncMock(
            return_value=[
                AgentPlanStep(
                    kind="tool",
                    instruction=f"Step {i}",
                    tool_name=f"tool_{i}",
                )
                for i in range(3)
            ]
        )
        agent_loop._apply_execution_plan = MagicMock(
            side_effect=lambda x, **kwargs: x
        )
        agent_loop._dedupe_plan_steps = MagicMock(side_effect=lambda x, y: y)
        agent_loop._should_defer_step = MagicMock(return_value=False)
        agent_loop._build_tool_context = MagicMock(return_value={})
        agent_loop.tools.execute = AsyncMock(
            return_value=MagicMock(
                tool_name="test_tool",
                success=True,
                output={"result": "success"},
                policy=MagicMock(allowed=True, reason="Test"),
                risk_level=RiskLevel.LOW,
            )
        )
        agent_loop._stringify = MagicMock(return_value="Tool result")
        agent_loop._record_audit = MagicMock()
        agent_loop._mark_subtask_progress = MagicMock()
        agent_loop._verify_write_result = AsyncMock(return_value=None)
        agent_loop._repair_write_step = AsyncMock(return_value=None)
        agent_loop._maybe_replan_after_failure = MagicMock()
        agent_loop.repair_loop.analyze = MagicMock(
            return_value=(
                MagicMock(verified=True),
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
        agent_loop._check_mainline = MagicMock()
        agent_loop._reflect = MagicMock(return_value="Reflection")
        agent_loop._finalize_answer = MagicMock(return_value="Final answer")
        agent_loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        agent_loop.memory.store = AsyncMock(return_value=str(uuid4()))
        agent_loop.memory.count = MagicMock(return_value=10)

        result = await agent_loop.run(run_context, task)

        # Verify multiple iterations
        assert result.iterations >= 1

    @pytest.mark.asyncio
    async def test_agent_execution_with_tool_failure_and_recovery(
        self, agent_loop: AgentLoop, run_context: RunContext
    ) -> None:
        """Test agent execution with tool failure and recovery."""
        task = "Task with potential failure"

        agent_loop._compress_context = MagicMock(return_value={})
        agent_loop._derive_goal = MagicMock(return_value="Goal")
        agent_loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        agent_loop._decompose_task = MagicMock(return_value=[])
        agent_loop._emit_trace = MagicMock(return_value=str(uuid4()))

        # First call fails, second succeeds
        agent_loop._plan = AsyncMock(
            return_value=[
                AgentPlanStep(
                    kind="tool",
                    instruction="Execute tool",
                    tool_name="test_tool",
                ),
                AgentPlanStep(kind="final", instruction="Finalize"),
            ]
        )
        agent_loop._apply_execution_plan = MagicMock(
            side_effect=lambda x, **kwargs: x
        )
        agent_loop._dedupe_plan_steps = MagicMock(side_effect=lambda x, y: y)
        agent_loop._should_defer_step = MagicMock(return_value=False)
        agent_loop._build_tool_context = MagicMock(return_value={})

        # Simulate tool failure then success
        agent_loop.tools.execute = AsyncMock(
            side_effect=[
                MagicMock(
                    tool_name="test_tool",
                    success=False,
                    output=None,
                    error="Tool failed",
                    policy=MagicMock(allowed=True, reason="Test"),
                    risk_level=RiskLevel.LOW,
                ),
                MagicMock(
                    tool_name="test_tool",
                    success=True,
                    output={"result": "success"},
                    policy=MagicMock(allowed=True, reason="Test"),
                    risk_level=RiskLevel.LOW,
                ),
            ]
        )
        agent_loop._stringify = MagicMock(return_value="Tool result")
        agent_loop._record_audit = MagicMock()
        agent_loop._mark_subtask_progress = MagicMock()
        agent_loop._verify_write_result = AsyncMock(return_value=None)
        agent_loop._repair_write_step = AsyncMock(return_value=None)
        agent_loop._maybe_replan_after_failure = MagicMock()
        agent_loop.repair_loop.analyze = MagicMock(
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
        agent_loop._check_mainline = MagicMock()
        agent_loop._reflect = MagicMock(return_value="Reflection")
        agent_loop._finalize_answer = MagicMock(return_value="Final answer")
        agent_loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        agent_loop.memory.store = AsyncMock(return_value=str(uuid4()))
        agent_loop.memory.count = MagicMock(return_value=10)

        result = await agent_loop.run(run_context, task)

        # Verify result despite failure
        assert result is not None
        assert result.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_agent_execution_respects_max_iterations(
        self, agent_loop: AgentLoop, run_context: RunContext
    ) -> None:
        """Test that agent execution respects max iterations."""
        task = "Long task"
        agent_loop.max_iterations = 2

        agent_loop._compress_context = MagicMock(return_value={})
        agent_loop._derive_goal = MagicMock(return_value="Goal")
        agent_loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        agent_loop._decompose_task = MagicMock(return_value=[])
        agent_loop._emit_trace = MagicMock(return_value=str(uuid4()))

        # Create plan with more steps than max_iterations
        agent_loop._plan = AsyncMock(
            return_value=[
                AgentPlanStep(
                    kind="tool",
                    instruction=f"Step {i}",
                    tool_name=f"tool_{i}",
                )
                for i in range(10)
            ]
        )
        agent_loop._apply_execution_plan = MagicMock(
            side_effect=lambda x, **kwargs: x
        )
        agent_loop._dedupe_plan_steps = MagicMock(side_effect=lambda x, y: y)
        agent_loop._should_defer_step = MagicMock(return_value=False)
        agent_loop._build_tool_context = MagicMock(return_value={})
        agent_loop.tools.execute = AsyncMock(
            return_value=MagicMock(
                tool_name="test_tool",
                success=True,
                output={"result": "success"},
                policy=MagicMock(allowed=True, reason="Test"),
                risk_level=RiskLevel.LOW,
            )
        )
        agent_loop._stringify = MagicMock(return_value="Tool result")
        agent_loop._record_audit = MagicMock()
        agent_loop._mark_subtask_progress = MagicMock()
        agent_loop._verify_write_result = AsyncMock(return_value=None)
        agent_loop._repair_write_step = AsyncMock(return_value=None)
        agent_loop._maybe_replan_after_failure = MagicMock()
        agent_loop.repair_loop.analyze = MagicMock(
            return_value=(
                MagicMock(verified=True),
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
        agent_loop._check_mainline = MagicMock()
        agent_loop._reflect = MagicMock(return_value="Reflection")
        agent_loop._finalize_answer = MagicMock(return_value="Final answer")
        agent_loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        agent_loop.memory.store = AsyncMock(return_value=str(uuid4()))
        agent_loop.memory.count = MagicMock(return_value=10)

        result = await agent_loop.run(run_context, task)

        # Verify max iterations was respected
        assert result.iterations <= agent_loop.max_iterations

    @pytest.mark.asyncio
    async def test_agent_execution_with_session_id(
        self, agent_loop: AgentLoop, run_context: RunContext
    ) -> None:
        """Test agent execution with session ID."""
        task = "Task with session"
        run_context.session_id = str(uuid4())

        agent_loop._compress_context = MagicMock(return_value={})
        agent_loop._derive_goal = MagicMock(return_value="Goal")
        agent_loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        agent_loop._decompose_task = MagicMock(return_value=[])
        agent_loop._emit_trace = MagicMock(return_value=str(uuid4()))
        agent_loop._plan = AsyncMock(
            return_value=[
                AgentPlanStep(kind="final", instruction="Finalize"),
            ]
        )
        agent_loop._apply_execution_plan = MagicMock(
            side_effect=lambda x, **kwargs: x
        )
        agent_loop._dedupe_plan_steps = MagicMock(side_effect=lambda x, y: y)
        agent_loop._should_defer_step = MagicMock(return_value=False)
        agent_loop._finalize_answer = MagicMock(return_value="Final answer")
        agent_loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        agent_loop.memory.store = AsyncMock(return_value=str(uuid4()))
        agent_loop.memory.count = MagicMock(return_value=10)

        result = await agent_loop.run(run_context, task)

        # Verify session ID is preserved
        assert result.execution_summary.get("session_id") == run_context.session_id

    @pytest.mark.asyncio
    async def test_agent_execution_with_high_risk_task(
        self, agent_loop: AgentLoop, run_context: RunContext
    ) -> None:
        """Test agent execution with high-risk task."""
        task = "High-risk task"
        run_context.risk_level = RiskLevel.HIGH

        agent_loop._compress_context = MagicMock(return_value={})
        agent_loop._derive_goal = MagicMock(return_value="Goal")
        agent_loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        agent_loop._decompose_task = MagicMock(return_value=[])
        agent_loop._emit_trace = MagicMock(return_value=str(uuid4()))
        agent_loop._plan = AsyncMock(
            return_value=[
                AgentPlanStep(kind="final", instruction="Finalize"),
            ]
        )
        agent_loop._apply_execution_plan = MagicMock(
            side_effect=lambda x, **kwargs: x
        )
        agent_loop._dedupe_plan_steps = MagicMock(side_effect=lambda x, y: y)
        agent_loop._should_defer_step = MagicMock(return_value=False)
        agent_loop._finalize_answer = MagicMock(return_value="Final answer")
        agent_loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        agent_loop.memory.store = AsyncMock(return_value=str(uuid4()))
        agent_loop.memory.count = MagicMock(return_value=10)

        result = await agent_loop.run(run_context, task)

        # Verify high-risk task was handled
        assert result is not None
        assert result.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_agent_execution_trace_recording(
        self, agent_loop: AgentLoop, run_context: RunContext
    ) -> None:
        """Test that agent execution records traces."""
        task = "Task with tracing"

        agent_loop._compress_context = MagicMock(return_value={})
        agent_loop._derive_goal = MagicMock(return_value="Goal")
        agent_loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        agent_loop._decompose_task = MagicMock(return_value=[])
        agent_loop._emit_trace = MagicMock(return_value=str(uuid4()))
        agent_loop._plan = AsyncMock(
            return_value=[
                AgentPlanStep(kind="final", instruction="Finalize"),
            ]
        )
        agent_loop._apply_execution_plan = MagicMock(
            side_effect=lambda x, **kwargs: x
        )
        agent_loop._dedupe_plan_steps = MagicMock(side_effect=lambda x, y: y)
        agent_loop._should_defer_step = MagicMock(return_value=False)
        agent_loop._finalize_answer = MagicMock(return_value="Final answer")
        agent_loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        agent_loop.memory.store = AsyncMock(return_value=str(uuid4()))
        agent_loop.memory.count = MagicMock(return_value=10)

        await agent_loop.run(run_context, task)

        # Verify traces were emitted
        agent_loop._emit_trace.assert_called()
