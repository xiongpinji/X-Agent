"""Tests for InitializationPhase."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.app.core.agent_phases import InitializationPhase, PhaseContext
from backend.app.core.contracts import RiskLevel, TaskFrame


class TestInitializationPhase:
    """Test suite for InitializationPhase."""

    @pytest.mark.asyncio
    async def test_initialization_phase_execute(
        self, phase_context: PhaseContext
    ) -> None:
        """Test InitializationPhase.execute()."""
        phase = InitializationPhase()

        # Mock the necessary methods
        phase_context.loop._derive_goal = MagicMock(return_value="Derived goal")
        phase_context.loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.state_manager.create_initial_state = MagicMock(
            return_value={"state": "initial"}
        )
        phase_context.loop.state_manager.attach_execution_frame = MagicMock(
            return_value={"state": "with_frame"}
        )
        phase_context.loop.state_manager.set_recovery_frame = MagicMock(
            return_value={"state": "with_recovery"}
        )
        phase_context.loop.state_manager.attach_plan_frame = MagicMock(
            return_value={"state": "with_plan"}
        )
        phase_context.loop.state_manager.build_initial_recovery = MagicMock(
            return_value=MagicMock(branch="continue")
        )
        phase_context.loop.orchestrator.prepare = MagicMock(
            return_value=(
                MagicMock(metadata={"test": True}),
                MagicMock(name="test_capability", reason="test reason"),
                MagicMock(branch="continue"),
            )
        )
        phase_context.loop.orchestrator.draft_plan = MagicMock(
            return_value=MagicMock(steps=["step1", "step2"], status="draft")
        )
        phase_context.loop.orchestrator.select_tool = MagicMock(
            return_value=MagicMock(tool_name="test_tool", reason="test reason")
        )

        await phase.execute(phase_context)

        # Verify state was created
        phase_context.loop.state_manager.create_initial_state.assert_called_once()

        # Verify execution frame was attached
        phase_context.loop.state_manager.attach_execution_frame.assert_called_once()

        # Verify orchestration was performed
        phase_context.loop.orchestrator.prepare.assert_called_once()
        phase_context.loop.orchestrator.draft_plan.assert_called_once()
        phase_context.loop.orchestrator.select_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_phase_task_frame_creation(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that InitializationPhase creates proper TaskFrame."""
        phase = InitializationPhase()

        phase_context.loop._derive_goal = MagicMock(return_value="Derived goal")
        phase_context.loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.state_manager.create_initial_state = MagicMock(
            return_value={"state": "initial"}
        )
        phase_context.loop.state_manager.attach_execution_frame = MagicMock(
            return_value={"state": "with_frame"}
        )
        phase_context.loop.state_manager.set_recovery_frame = MagicMock(
            return_value={"state": "with_recovery"}
        )
        phase_context.loop.state_manager.attach_plan_frame = MagicMock(
            return_value={"state": "with_plan"}
        )
        phase_context.loop.state_manager.build_initial_recovery = MagicMock(
            return_value=MagicMock(branch="continue")
        )
        phase_context.loop.orchestrator.prepare = MagicMock(
            return_value=(
                MagicMock(metadata={"test": True}),
                MagicMock(name="test_capability", reason="test reason"),
                MagicMock(branch="continue"),
            )
        )
        phase_context.loop.orchestrator.draft_plan = MagicMock(
            return_value=MagicMock(steps=["step1", "step2"], status="draft")
        )
        phase_context.loop.orchestrator.select_tool = MagicMock(
            return_value=MagicMock(tool_name="test_tool", reason="test reason")
        )

        await phase.execute(phase_context)

        # Verify task frame was created
        assert phase_context.task_frame is not None
        assert phase_context.task_frame.goal == "Derived goal"
        assert phase_context.task_frame.risk_level == RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_initialization_phase_execution_frame_creation(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that InitializationPhase creates proper ExecutionFrame."""
        phase = InitializationPhase()

        phase_context.loop._derive_goal = MagicMock(return_value="Derived goal")
        phase_context.loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.state_manager.create_initial_state = MagicMock(
            return_value={"state": "initial"}
        )
        phase_context.loop.state_manager.attach_execution_frame = MagicMock(
            return_value={"state": "with_frame"}
        )
        phase_context.loop.state_manager.set_recovery_frame = MagicMock(
            return_value={"state": "with_recovery"}
        )
        phase_context.loop.state_manager.attach_plan_frame = MagicMock(
            return_value={"state": "with_plan"}
        )
        phase_context.loop.state_manager.build_initial_recovery = MagicMock(
            return_value=MagicMock(branch="continue")
        )
        phase_context.loop.orchestrator.prepare = MagicMock(
            return_value=(
                MagicMock(metadata={"test": True}),
                MagicMock(name="test_capability", reason="test reason"),
                MagicMock(branch="continue"),
            )
        )
        phase_context.loop.orchestrator.draft_plan = MagicMock(
            return_value=MagicMock(steps=["step1", "step2"], status="draft")
        )
        phase_context.loop.orchestrator.select_tool = MagicMock(
            return_value=MagicMock(tool_name="test_tool", reason="test reason")
        )

        await phase.execute(phase_context)

        # Verify execution frame was created
        assert phase_context.execution_frame is not None
        assert phase_context.execution_frame.trace_id == phase_context.context.trace_id
        assert phase_context.execution_frame.agent_id == phase_context.context.agent_id

    @pytest.mark.asyncio
    async def test_initialization_phase_plan_frame_creation(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that InitializationPhase creates proper PlanFrame."""
        phase = InitializationPhase()

        phase_context.loop._derive_goal = MagicMock(return_value="Derived goal")
        phase_context.loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.state_manager.create_initial_state = MagicMock(
            return_value={"state": "initial"}
        )
        phase_context.loop.state_manager.attach_execution_frame = MagicMock(
            return_value={"state": "with_frame"}
        )
        phase_context.loop.state_manager.set_recovery_frame = MagicMock(
            return_value={"state": "with_recovery"}
        )
        phase_context.loop.state_manager.attach_plan_frame = MagicMock(
            return_value={"state": "with_plan"}
        )
        phase_context.loop.state_manager.build_initial_recovery = MagicMock(
            return_value=MagicMock(branch="continue")
        )
        phase_context.loop.orchestrator.prepare = MagicMock(
            return_value=(
                MagicMock(metadata={"test": True}),
                MagicMock(name="test_capability", reason="test reason"),
                MagicMock(branch="continue"),
            )
        )
        phase_context.loop.orchestrator.draft_plan = MagicMock(
            return_value=MagicMock(steps=["step1", "step2"], status="draft")
        )
        phase_context.loop.orchestrator.select_tool = MagicMock(
            return_value=MagicMock(tool_name="test_tool", reason="test reason")
        )

        await phase.execute(phase_context)

        # Verify plan frame was set
        assert phase_context.plan_frame is not None

    @pytest.mark.asyncio
    async def test_initialization_phase_with_session_id(
        self, phase_context: PhaseContext
    ) -> None:
        """Test InitializationPhase with session ID."""
        phase = InitializationPhase()

        phase_context.loop._derive_goal = MagicMock(return_value="Derived goal")
        phase_context.loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.state_manager.create_initial_state = MagicMock(
            return_value={"state": "initial"}
        )
        phase_context.loop.state_manager.attach_execution_frame = MagicMock(
            return_value={"state": "with_frame"}
        )
        phase_context.loop.state_manager.set_recovery_frame = MagicMock(
            return_value={"state": "with_recovery"}
        )
        phase_context.loop.state_manager.attach_plan_frame = MagicMock(
            return_value={"state": "with_plan"}
        )
        phase_context.loop.state_manager.build_initial_recovery = MagicMock(
            return_value=MagicMock(branch="continue")
        )
        phase_context.loop.orchestrator.prepare = MagicMock(
            return_value=(
                MagicMock(metadata={"test": True}),
                MagicMock(name="test_capability", reason="test reason"),
                MagicMock(branch="continue"),
            )
        )
        phase_context.loop.orchestrator.draft_plan = MagicMock(
            return_value=MagicMock(steps=["step1", "step2"], status="draft")
        )
        phase_context.loop.orchestrator.select_tool = MagicMock(
            return_value=MagicMock(tool_name="test_tool", reason="test reason")
        )

        await phase.execute(phase_context)

        # Verify session ID was included in metadata
        assert phase_context.execution_frame.session_id is not None

    @pytest.mark.asyncio
    async def test_initialization_phase_trace_emission(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that InitializationPhase emits traces."""
        phase = InitializationPhase()

        phase_context.loop._derive_goal = MagicMock(return_value="Derived goal")
        phase_context.loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.state_manager.create_initial_state = MagicMock(
            return_value={"state": "initial"}
        )
        phase_context.loop.state_manager.attach_execution_frame = MagicMock(
            return_value={"state": "with_frame"}
        )
        phase_context.loop.state_manager.set_recovery_frame = MagicMock(
            return_value={"state": "with_recovery"}
        )
        phase_context.loop.state_manager.attach_plan_frame = MagicMock(
            return_value={"state": "with_plan"}
        )
        phase_context.loop.state_manager.build_initial_recovery = MagicMock(
            return_value=MagicMock(branch="continue")
        )
        phase_context.loop.orchestrator.prepare = MagicMock(
            return_value=(
                MagicMock(metadata={"test": True}),
                MagicMock(name="test_capability", reason="test reason"),
                MagicMock(branch="continue"),
            )
        )
        phase_context.loop.orchestrator.draft_plan = MagicMock(
            return_value=MagicMock(steps=["step1", "step2"], status="draft")
        )
        phase_context.loop.orchestrator.select_tool = MagicMock(
            return_value=MagicMock(tool_name="test_tool", reason="test reason")
        )

        await phase.execute(phase_context)

        # Verify trace was emitted
        phase_context.loop._emit_trace.assert_called()

    @pytest.mark.asyncio
    async def test_initialization_phase_compact_context_update(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that InitializationPhase updates compact context."""
        phase = InitializationPhase()

        phase_context.loop._derive_goal = MagicMock(return_value="Derived goal")
        phase_context.loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.state_manager.create_initial_state = MagicMock(
            return_value={"state": "initial"}
        )
        phase_context.loop.state_manager.attach_execution_frame = MagicMock(
            return_value={"state": "with_frame"}
        )
        phase_context.loop.state_manager.set_recovery_frame = MagicMock(
            return_value={"state": "with_recovery"}
        )
        phase_context.loop.state_manager.attach_plan_frame = MagicMock(
            return_value={"state": "with_plan"}
        )
        phase_context.loop.state_manager.build_initial_recovery = MagicMock(
            return_value=MagicMock(branch="continue")
        )
        phase_context.loop.orchestrator.prepare = MagicMock(
            return_value=(
                MagicMock(metadata={"test": True}),
                MagicMock(name="test_capability", reason="test reason"),
                MagicMock(branch="continue"),
            )
        )
        phase_context.loop.orchestrator.draft_plan = MagicMock(
            return_value=MagicMock(steps=["step1", "step2"], status="draft")
        )
        phase_context.loop.orchestrator.select_tool = MagicMock(
            return_value=MagicMock(tool_name="test_tool", reason="test reason")
        )

        await phase.execute(phase_context)

        # Verify compact context was updated
        assert "capability_decision" in phase_context.compact_context
        assert "orchestration_recovery_hint" in phase_context.compact_context
        assert "draft_plan" in phase_context.compact_context
        assert "tool_decision" in phase_context.compact_context

    @pytest.mark.asyncio
    async def test_initialization_phase_with_high_risk_task(
        self, phase_context: PhaseContext
    ) -> None:
        """Test InitializationPhase with high-risk task."""
        phase = InitializationPhase()

        # Set high risk level
        phase_context.context.risk_level = RiskLevel.HIGH
        phase_context.compact_context["requires_approval"] = True

        phase_context.loop._derive_goal = MagicMock(return_value="Derived goal")
        phase_context.loop._dump_model = MagicMock(side_effect=lambda x: {"dumped": True})
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.state_manager.create_initial_state = MagicMock(
            return_value={"state": "initial"}
        )
        phase_context.loop.state_manager.attach_execution_frame = MagicMock(
            return_value={"state": "with_frame"}
        )
        phase_context.loop.state_manager.set_recovery_frame = MagicMock(
            return_value={"state": "with_recovery"}
        )
        phase_context.loop.state_manager.attach_plan_frame = MagicMock(
            return_value={"state": "with_plan"}
        )
        phase_context.loop.state_manager.build_initial_recovery = MagicMock(
            return_value=MagicMock(branch="continue")
        )
        phase_context.loop.orchestrator.prepare = MagicMock(
            return_value=(
                MagicMock(metadata={"test": True}),
                MagicMock(name="test_capability", reason="test reason"),
                MagicMock(branch="continue"),
            )
        )
        phase_context.loop.orchestrator.draft_plan = MagicMock(
            return_value=MagicMock(steps=["step1", "step2"], status="draft")
        )
        phase_context.loop.orchestrator.select_tool = MagicMock(
            return_value=MagicMock(tool_name="test_tool", reason="test reason")
        )

        await phase.execute(phase_context)

        # Verify task frame has high risk level
        assert phase_context.task_frame.risk_level == RiskLevel.HIGH
        assert phase_context.task_frame.requires_approval is True
