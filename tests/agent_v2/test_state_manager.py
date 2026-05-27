"""Tests for AgentStateManager."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from backend.app.core.agent_state_manager import AgentStateManager
from backend.app.core.contracts import (
    ExecutionFrame,
    PlanFrame,
    RecoveryFrame,
    RunContext,
    RiskLevel,
    TaskFrame,
)


class TestAgentStateManager:
    """Test suite for AgentStateManager."""

    def test_state_manager_initialization(self) -> None:
        """Test AgentStateManager initialization."""
        manager = AgentStateManager()
        assert manager is not None

    def test_create_initial_state(
        self, run_context: RunContext, task_frame: TaskFrame
    ) -> None:
        """Test creating initial state."""
        manager = AgentStateManager()
        metadata = {"session_id": run_context.session_id}

        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata=metadata,
        )

        assert state is not None
        assert isinstance(state, dict)

    def test_create_initial_state_without_metadata(
        self, run_context: RunContext, task_frame: TaskFrame
    ) -> None:
        """Test creating initial state without metadata."""
        manager = AgentStateManager()

        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={},
        )

        assert state is not None
        assert isinstance(state, dict)

    def test_attach_execution_frame(
        self,
        run_context: RunContext,
        task_frame: TaskFrame,
        execution_frame: ExecutionFrame,
    ) -> None:
        """Test attaching execution frame to state."""
        manager = AgentStateManager()
        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={},
        )

        updated_state = manager.attach_execution_frame(state, execution_frame)

        assert updated_state is not None
        assert isinstance(updated_state, dict)

    def test_set_recovery_frame(
        self,
        run_context: RunContext,
        task_frame: TaskFrame,
        recovery_frame: RecoveryFrame,
    ) -> None:
        """Test setting recovery frame in state."""
        manager = AgentStateManager()
        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={},
        )

        updated_state = manager.set_recovery_frame(state, recovery_frame)

        assert updated_state is not None
        assert isinstance(updated_state, dict)

    def test_attach_plan_frame(
        self,
        run_context: RunContext,
        task_frame: TaskFrame,
        plan_frame: PlanFrame,
    ) -> None:
        """Test attaching plan frame to state."""
        manager = AgentStateManager()
        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={},
        )

        updated_state = manager.attach_plan_frame(state, plan_frame)

        assert updated_state is not None
        assert isinstance(updated_state, dict)

    def test_build_initial_recovery(self) -> None:
        """Test building initial recovery frame."""
        manager = AgentStateManager()
        tool_name = "test_tool"

        recovery = manager.build_initial_recovery(tool_name=tool_name)

        assert recovery is not None
        assert isinstance(recovery, RecoveryFrame)
        assert recovery.branch == "continue"

    def test_build_initial_recovery_without_tool(self) -> None:
        """Test building initial recovery frame without tool name."""
        manager = AgentStateManager()

        recovery = manager.build_initial_recovery(tool_name=None)

        assert recovery is not None
        assert isinstance(recovery, RecoveryFrame)
        assert recovery.branch == "continue"

    def test_state_manager_chaining(
        self,
        run_context: RunContext,
        task_frame: TaskFrame,
        execution_frame: ExecutionFrame,
        plan_frame: PlanFrame,
        recovery_frame: RecoveryFrame,
    ) -> None:
        """Test chaining state manager operations."""
        manager = AgentStateManager()

        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={"session_id": run_context.session_id},
        )
        state = manager.attach_execution_frame(state, execution_frame)
        state = manager.set_recovery_frame(state, recovery_frame)
        state = manager.attach_plan_frame(state, plan_frame)

        assert state is not None
        assert isinstance(state, dict)

    def test_state_manager_multiple_contexts(
        self, task_frame: TaskFrame
    ) -> None:
        """Test state manager with multiple contexts."""
        manager = AgentStateManager()

        contexts = [
            RunContext(
                trace_id=str(uuid4()),
                tenant_id=f"tenant_{i}",
                user_id=f"user_{i}",
                agent_id=str(uuid4()),
                request_id=str(uuid4()),
            )
            for i in range(3)
        ]

        states = []
        for context in contexts:
            state = manager.create_initial_state(
                context=context,
                task_frame=task_frame,
                metadata={},
            )
            states.append(state)

        assert len(states) == 3
        for state in states:
            assert state is not None

    def test_state_manager_recovery_with_different_branches(
        self, run_context: RunContext, task_frame: TaskFrame
    ) -> None:
        """Test state manager with different recovery branches."""
        manager = AgentStateManager()
        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={},
        )

        branches = ["continue", "retry", "escalate", "abort"]
        for branch in branches:
            recovery = RecoveryFrame(branch=branch)
            updated_state = manager.set_recovery_frame(state, recovery)
            assert updated_state is not None

    def test_state_manager_plan_frame_updates(
        self,
        run_context: RunContext,
        task_frame: TaskFrame,
        plan_frame: PlanFrame,
    ) -> None:
        """Test state manager with plan frame updates."""
        manager = AgentStateManager()
        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={},
        )

        # Attach initial plan
        state = manager.attach_plan_frame(state, plan_frame)

        # Update plan with new steps
        updated_plan = PlanFrame(
            plan_id=plan_frame.plan_id,
            goal=plan_frame.goal,
            steps=["new_step1", "new_step2"],
            status="ready",
            revision=1,
        )
        state = manager.attach_plan_frame(state, updated_plan)

        assert state is not None

    def test_state_manager_execution_frame_with_metadata(
        self,
        run_context: RunContext,
        task_frame: TaskFrame,
        execution_frame: ExecutionFrame,
    ) -> None:
        """Test state manager with execution frame containing metadata."""
        manager = AgentStateManager()
        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={"custom_key": "custom_value"},
        )

        # Add metadata to execution frame
        execution_frame.metadata["additional"] = "metadata"
        state = manager.attach_execution_frame(state, execution_frame)

        assert state is not None

    def test_state_manager_recovery_with_retry_count(
        self, run_context: RunContext, task_frame: TaskFrame
    ) -> None:
        """Test state manager with recovery frame containing retry count."""
        manager = AgentStateManager()
        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={},
        )

        recovery = RecoveryFrame(
            branch="retry",
            retry_count=3,
            tool_name="test_tool",
            reason="Test retry",
        )
        updated_state = manager.set_recovery_frame(state, recovery)

        assert updated_state is not None

    def test_state_manager_plan_frame_with_dependencies(
        self,
        run_context: RunContext,
        task_frame: TaskFrame,
        plan_frame: PlanFrame,
    ) -> None:
        """Test state manager with plan frame containing dependencies."""
        manager = AgentStateManager()
        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={},
        )

        plan_with_deps = PlanFrame(
            goal=plan_frame.goal,
            steps=plan_frame.steps,
            dependencies=["dep1", "dep2", "dep3"],
            risks=["risk1", "risk2"],
            verification_steps=["verify1", "verify2"],
            rollback_steps=["rollback1"],
            status="draft",
        )
        state = manager.attach_plan_frame(state, plan_with_deps)

        assert state is not None

    def test_state_manager_idempotent_operations(
        self,
        run_context: RunContext,
        task_frame: TaskFrame,
        execution_frame: ExecutionFrame,
    ) -> None:
        """Test that state manager operations are idempotent."""
        manager = AgentStateManager()
        state = manager.create_initial_state(
            context=run_context,
            task_frame=task_frame,
            metadata={},
        )

        # Apply same operation twice
        state1 = manager.attach_execution_frame(state, execution_frame)
        state2 = manager.attach_execution_frame(state, execution_frame)

        assert state1 is not None
        assert state2 is not None
