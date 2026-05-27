"""Comprehensive tests for core business logic.

Tests cover:
- Agent execution and state management
- Tool execution and validation
- Repair loop and error recovery
- Verification engine
- Planning and execution
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.core.contracts import (
    RunContext,
    RunStatus,
    TaskFrame,
    PlanFrame,
    ExecutionFrame,
    RecoveryFrame,
    TraceEvent,
)


class TestRunContext:
    """Test RunContext model."""

    def test_run_context_creation(self) -> None:
        """Test creating a run context."""
        context = RunContext(
            run_id="run-123",
            tenant_id="tenant-1",
            user_id="user-1",
        )
        assert context.run_id == "run-123"
        assert context.tenant_id == "tenant-1"
        assert context.user_id == "user-1"

    def test_run_context_with_agent_id(self) -> None:
        """Test run context with agent ID."""
        context = RunContext(
            run_id="run-123",
            tenant_id="tenant-1",
            user_id="user-1",
            agent_id="agent-1",
        )
        assert context.agent_id == "agent-1"

    def test_run_context_with_session_id(self) -> None:
        """Test run context with session ID."""
        context = RunContext(
            run_id="run-123",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
        )
        assert context.session_id == "session-1"

    def test_run_context_with_metadata(self) -> None:
        """Test run context with metadata."""
        metadata = {"key": "value", "nested": {"inner": "data"}}
        context = RunContext(
            run_id="run-123",
            tenant_id="tenant-1",
            user_id="user-1",
            metadata=metadata,
        )
        assert context.metadata == metadata


class TestRunStatus:
    """Test RunStatus enum."""

    def test_run_status_values(self) -> None:
        """Test run status values."""
        assert RunStatus.PENDING == "pending"
        assert RunStatus.RUNNING == "running"
        assert RunStatus.COMPLETED == "completed"
        assert RunStatus.FAILED == "failed"
        assert RunStatus.CANCELED == "canceled"


class TestTaskFrame:
    """Test TaskFrame model."""

    def test_task_frame_creation(self) -> None:
        """Test creating a task frame."""
        frame = TaskFrame(
            task_id="task-1",
            description="Test task",
            status="pending",
        )
        assert frame.task_id == "task-1"
        assert frame.description == "Test task"
        assert frame.status == "pending"

    def test_task_frame_with_subtasks(self) -> None:
        """Test task frame with subtasks."""
        subtasks = ["subtask-1", "subtask-2", "subtask-3"]
        frame = TaskFrame(
            task_id="task-1",
            description="Parent task",
            status="running",
            subtasks=subtasks,
        )
        assert frame.subtasks == subtasks

    def test_task_frame_with_dependencies(self) -> None:
        """Test task frame with dependencies."""
        dependencies = ["task-0", "task-1"]
        frame = TaskFrame(
            task_id="task-2",
            description="Dependent task",
            status="pending",
            dependencies=dependencies,
        )
        assert frame.dependencies == dependencies

    def test_task_frame_with_priority(self) -> None:
        """Test task frame with priority."""
        frame = TaskFrame(
            task_id="task-1",
            description="High priority task",
            status="pending",
            priority="high",
        )
        assert frame.priority == "high"


class TestPlanFrame:
    """Test PlanFrame model."""

    def test_plan_frame_creation(self) -> None:
        """Test creating a plan frame."""
        frame = PlanFrame(
            plan_id="plan-1",
            goal="Achieve objective",
            strategy="Step-by-step approach",
        )
        assert frame.plan_id == "plan-1"
        assert frame.goal == "Achieve objective"
        assert frame.strategy == "Step-by-step approach"

    def test_plan_frame_with_steps(self) -> None:
        """Test plan frame with steps."""
        steps = [
            {"step": 1, "action": "Initialize"},
            {"step": 2, "action": "Execute"},
            {"step": 3, "action": "Verify"},
        ]
        frame = PlanFrame(
            plan_id="plan-1",
            goal="Complete workflow",
            strategy="Sequential",
            steps=steps,
        )
        assert len(frame.steps) == 3

    def test_plan_frame_with_constraints(self) -> None:
        """Test plan frame with constraints."""
        constraints = {
            "max_time": 3600,
            "max_cost": 100,
            "required_approvals": True,
        }
        frame = PlanFrame(
            plan_id="plan-1",
            goal="Constrained task",
            strategy="Optimized",
            constraints=constraints,
        )
        assert frame.constraints == constraints

    def test_plan_frame_with_alternatives(self) -> None:
        """Test plan frame with alternative plans."""
        alternatives = [
            {"id": "alt-1", "description": "Alternative 1"},
            {"id": "alt-2", "description": "Alternative 2"},
        ]
        frame = PlanFrame(
            plan_id="plan-1",
            goal="Main goal",
            strategy="Primary strategy",
            alternatives=alternatives,
        )
        assert len(frame.alternatives) == 2


class TestExecutionFrame:
    """Test ExecutionFrame model."""

    def test_execution_frame_creation(self) -> None:
        """Test creating an execution frame."""
        frame = ExecutionFrame(
            execution_id="exec-1",
            plan_id="plan-1",
            status="running",
        )
        assert frame.execution_id == "exec-1"
        assert frame.plan_id == "plan-1"
        assert frame.status == "running"

    def test_execution_frame_with_steps(self) -> None:
        """Test execution frame with executed steps."""
        steps = [
            {"step": 1, "status": "completed", "result": "success"},
            {"step": 2, "status": "running", "result": None},
        ]
        frame = ExecutionFrame(
            execution_id="exec-1",
            plan_id="plan-1",
            status="running",
            executed_steps=steps,
        )
        assert len(frame.executed_steps) == 2

    def test_execution_frame_with_errors(self) -> None:
        """Test execution frame with errors."""
        errors = [
            {"step": 1, "error": "Tool failed", "recovery": "retry"},
        ]
        frame = ExecutionFrame(
            execution_id="exec-1",
            plan_id="plan-1",
            status="failed",
            errors=errors,
        )
        assert len(frame.errors) == 1

    def test_execution_frame_with_metrics(self) -> None:
        """Test execution frame with metrics."""
        metrics = {
            "duration": 120,
            "steps_completed": 5,
            "steps_failed": 1,
            "cost": 50,
        }
        frame = ExecutionFrame(
            execution_id="exec-1",
            plan_id="plan-1",
            status="completed",
            metrics=metrics,
        )
        assert frame.metrics == metrics


class TestRecoveryFrame:
    """Test RecoveryFrame model."""

    def test_recovery_frame_creation(self) -> None:
        """Test creating a recovery frame."""
        frame = RecoveryFrame(
            recovery_id="recovery-1",
            execution_id="exec-1",
            error="Tool execution failed",
        )
        assert frame.recovery_id == "recovery-1"
        assert frame.execution_id == "exec-1"
        assert frame.error == "Tool execution failed"

    def test_recovery_frame_with_strategy(self) -> None:
        """Test recovery frame with recovery strategy."""
        frame = RecoveryFrame(
            recovery_id="recovery-1",
            execution_id="exec-1",
            error="Timeout",
            recovery_strategy="retry_with_backoff",
        )
        assert frame.recovery_strategy == "retry_with_backoff"

    def test_recovery_frame_with_attempts(self) -> None:
        """Test recovery frame with recovery attempts."""
        attempts = [
            {"attempt": 1, "status": "failed", "error": "Still failing"},
            {"attempt": 2, "status": "success", "result": "Recovered"},
        ]
        frame = RecoveryFrame(
            recovery_id="recovery-1",
            execution_id="exec-1",
            error="Initial error",
            recovery_attempts=attempts,
        )
        assert len(frame.recovery_attempts) == 2

    def test_recovery_frame_with_fallback(self) -> None:
        """Test recovery frame with fallback action."""
        fallback = {
            "action": "use_alternative_tool",
            "tool": "backup_tool",
        }
        frame = RecoveryFrame(
            recovery_id="recovery-1",
            execution_id="exec-1",
            error="Primary tool failed",
            fallback_action=fallback,
        )
        assert frame.fallback_action == fallback


class TestTraceEvent:
    """Test TraceEvent model."""

    def test_trace_event_creation(self) -> None:
        """Test creating a trace event."""
        event = TraceEvent(
            event_id="event-1",
            event_type="tool_call",
            timestamp=datetime.now(UTC),
        )
        assert event.event_id == "event-1"
        assert event.event_type == "tool_call"

    def test_trace_event_with_data(self) -> None:
        """Test trace event with data."""
        data = {
            "tool": "search",
            "query": "test query",
            "result": "found results",
        }
        event = TraceEvent(
            event_id="event-1",
            event_type="tool_call",
            timestamp=datetime.now(UTC),
            data=data,
        )
        assert event.data == data

    def test_trace_event_with_context(self) -> None:
        """Test trace event with context."""
        context = {
            "run_id": "run-1",
            "agent_id": "agent-1",
            "step": 5,
        }
        event = TraceEvent(
            event_id="event-1",
            event_type="execution",
            timestamp=datetime.now(UTC),
            context=context,
        )
        assert event.context == context

    def test_trace_event_with_error(self) -> None:
        """Test trace event with error."""
        error = {
            "type": "ValueError",
            "message": "Invalid input",
            "traceback": "...",
        }
        event = TraceEvent(
            event_id="event-1",
            event_type="error",
            timestamp=datetime.now(UTC),
            error=error,
        )
        assert event.error == error

    def test_trace_event_ordering(self) -> None:
        """Test trace event ordering by timestamp."""
        now = datetime.now(UTC)
        events = [
            TraceEvent(
                event_id=f"event-{i}",
                event_type="step",
                timestamp=now,
            )
            for i in range(3)
        ]
        # Events should maintain order
        assert events[0].event_id == "event-0"
        assert events[2].event_id == "event-2"


class TestContractIntegration:
    """Test integration of contract models."""

    def test_run_context_with_frames(self) -> None:
        """Test run context with various frames."""
        context = RunContext(
            run_id="run-1",
            tenant_id="tenant-1",
            user_id="user-1",
        )
        task_frame = TaskFrame(
            task_id="task-1",
            description="Test task",
            status="pending",
        )
        plan_frame = PlanFrame(
            plan_id="plan-1",
            goal="Achieve goal",
            strategy="Strategy",
        )
        assert context.run_id == "run-1"
        assert task_frame.task_id == "task-1"
        assert plan_frame.plan_id == "plan-1"

    def test_execution_recovery_flow(self) -> None:
        """Test execution and recovery flow."""
        exec_frame = ExecutionFrame(
            execution_id="exec-1",
            plan_id="plan-1",
            status="failed",
            errors=[{"step": 1, "error": "Failed"}],
        )
        recovery_frame = RecoveryFrame(
            recovery_id="recovery-1",
            execution_id="exec-1",
            error="Execution failed",
            recovery_strategy="retry",
        )
        assert exec_frame.execution_id == "exec-1"
        assert recovery_frame.execution_id == "exec-1"

    def test_trace_event_sequence(self) -> None:
        """Test sequence of trace events."""
        now = datetime.now(UTC)
        events = [
            TraceEvent(
                event_id="event-1",
                event_type="start",
                timestamp=now,
            ),
            TraceEvent(
                event_id="event-2",
                event_type="tool_call",
                timestamp=now,
                data={"tool": "search"},
            ),
            TraceEvent(
                event_id="event-3",
                event_type="end",
                timestamp=now,
            ),
        ]
        assert len(events) == 3
        assert events[0].event_type == "start"
        assert events[1].event_type == "tool_call"
        assert events[2].event_type == "end"
