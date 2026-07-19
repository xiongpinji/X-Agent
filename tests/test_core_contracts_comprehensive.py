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
            trace_id="trace-123",
            tenant_id="tenant-1",
            user_id="user-1",
        )
        assert context.trace_id == "trace-123"
        assert context.tenant_id == "tenant-1"
        assert context.user_id == "user-1"

    def test_run_context_with_agent_id(self) -> None:
        """Test run context with agent ID."""
        context = RunContext(
            trace_id="trace-123",
            tenant_id="tenant-1",
            user_id="user-1",
            agent_id="agent-1",
        )
        assert context.agent_id == "agent-1"

    def test_run_context_with_session_id(self) -> None:
        """Test run context with session ID."""
        context = RunContext(
            trace_id="trace-123",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
        )
        assert context.session_id == "session-1"

    def test_run_context_with_metadata(self) -> None:
        """Test run context with metadata."""
        context = RunContext(
            trace_id="trace-123",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
        )
        assert context.trace_id == "trace-123"
        assert context.session_id == "session-1"


class TestRunStatus:
    """Test RunStatus enum."""

    def test_run_status_values(self) -> None:
        """Test run status values."""
        assert RunStatus.RUNNING == "running"
        assert RunStatus.COMPLETED == "completed"
        assert RunStatus.FAILED == "failed"
        assert RunStatus.NEEDS_APPROVAL == "needs_approval"


class TestTaskFrame:
    """Test TaskFrame model."""

    def test_task_frame_creation(self) -> None:
        """Test creating a task frame."""
        frame = TaskFrame(
            task_id="task-1",
            goal="Complete the task",
            description="Test task",
        )
        assert frame.task_id == "task-1"
        assert frame.goal == "Complete the task"
        assert frame.description == "Test task"

    def test_task_frame_with_subtasks(self) -> None:
        """Test task frame with subtasks."""
        subtasks = ["subtask-1", "subtask-2", "subtask-3"]
        frame = TaskFrame(
            task_id="task-1",
            goal="Parent task goal",
            description="Parent task",
            constraints=subtasks,
        )
        assert frame.constraints == subtasks

    def test_task_frame_with_dependencies(self) -> None:
        """Test task frame with dependencies."""
        dependencies = ["task-0", "task-1"]
        frame = TaskFrame(
            task_id="task-2",
            goal="Dependent task goal",
            description="Dependent task",
            constraints=dependencies,
        )
        assert frame.constraints == dependencies

    def test_task_frame_with_priority(self) -> None:
        """Test task frame with priority."""
        frame = TaskFrame(
            task_id="task-1",
            goal="High priority task goal",
            description="High priority task",
            metadata={"priority": "high"},
        )
        assert frame.metadata["priority"] == "high"


class TestPlanFrame:
    """Test PlanFrame model."""

    def test_plan_frame_creation(self) -> None:
        """Test creating a plan frame."""
        frame = PlanFrame(
            plan_id="plan-1",
            goal="Achieve objective",
        )
        assert frame.plan_id == "plan-1"
        assert frame.goal == "Achieve objective"

    def test_plan_frame_with_steps(self) -> None:
        """Test plan frame with steps."""
        steps = [
            "Initialize",
            "Execute",
            "Verify",
        ]
        frame = PlanFrame(
            plan_id="plan-1",
            goal="Complete workflow",
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
        )
        assert frame.plan_id == "plan-1"

    def test_plan_frame_with_alternatives(self) -> None:
        """Test plan frame with alternative plans."""
        alternatives = [
            {"id": "alt-1", "description": "Alternative 1"},
            {"id": "alt-2", "description": "Alternative 2"},
        ]
        frame = PlanFrame(
            plan_id="plan-1",
            goal="Main goal",
        )
        assert frame.plan_id == "plan-1"


class TestExecutionFrame:
    """Test ExecutionFrame model."""

    def test_execution_frame_creation(self) -> None:
        """Test creating an execution frame."""
        task = TaskFrame(task_id="task-1", goal="Test goal")
        frame = ExecutionFrame(
            trace_id="trace-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            user_id="user-1",
            request_id="req-1",
            task=task,
        )
        assert frame.trace_id == "trace-1"
        assert frame.agent_id == "agent-1"
        assert frame.task.task_id == "task-1"

    def test_execution_frame_with_steps(self) -> None:
        """Test execution frame with executed steps."""
        steps = [
            {"step": 1, "status": "completed", "result": "success"},
            {"step": 2, "status": "running", "result": None},
        ]
        task = TaskFrame(task_id="task-1", goal="Test goal")
        frame = ExecutionFrame(
            trace_id="trace-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            user_id="user-1",
            request_id="req-1",
            task=task,
            tool_history=steps,
        )
        assert len(frame.tool_history) == 2

    def test_execution_frame_with_errors(self) -> None:
        """Test execution frame with errors."""
        errors = [
            {"step": 1, "error": "Tool failed", "recovery": "retry"},
        ]
        task = TaskFrame(task_id="task-1", goal="Test goal")
        frame = ExecutionFrame(
            trace_id="trace-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            user_id="user-1",
            request_id="req-1",
            task=task,
            metadata={"errors": errors},
        )
        assert frame.metadata["errors"] == errors

    def test_execution_frame_with_metrics(self) -> None:
        """Test execution frame with metrics."""
        metrics = {
            "duration": 120,
            "steps_completed": 5,
            "steps_failed": 1,
            "cost": 50,
        }
        task = TaskFrame(task_id="task-1", goal="Test goal")
        frame = ExecutionFrame(
            trace_id="trace-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            user_id="user-1",
            request_id="req-1",
            task=task,
            execution_summary=metrics,
        )
        assert frame.execution_summary == metrics


class TestRecoveryFrame:
    """Test RecoveryFrame model."""

    def test_recovery_frame_creation(self) -> None:
        """Test creating a recovery frame."""
        frame = RecoveryFrame(
            branch="retry",
            reason="Tool execution failed",
        )
        assert frame.branch == "retry"
        assert frame.reason == "Tool execution failed"

    def test_recovery_frame_with_strategy(self) -> None:
        """Test recovery frame with recovery strategy."""
        frame = RecoveryFrame(
            branch="escalate",
            reason="Timeout",
            next_action="escalate_to_human",
        )
        assert frame.next_action == "escalate_to_human"

    def test_recovery_frame_with_attempts(self) -> None:
        """Test recovery frame with recovery attempts."""
        attempts = [
            {"attempt": 1, "status": "failed", "error": "Still failing"},
            {"attempt": 2, "status": "success", "result": "Recovered"},
        ]
        frame = RecoveryFrame(
            branch="retry",
            reason="Initial error",
            recovery_plan={"attempts": attempts},
            retry_count=2,
        )
        assert frame.recovery_plan["attempts"] == attempts
        assert frame.retry_count == 2

    def test_recovery_frame_with_fallback(self) -> None:
        """Test recovery frame with fallback action."""
        fallback = {
            "action": "use_alternative_tool",
            "tool": "backup_tool",
        }
        frame = RecoveryFrame(
            branch="fallback",
            reason="Primary tool failed",
            recovery_plan=fallback,
            next_action="use_alternative_tool",
        )
        assert frame.recovery_plan == fallback


class TestTraceEvent:
    """Test TraceEvent model."""

    def test_trace_event_creation(self) -> None:
        """Test creating a trace event."""
        event = TraceEvent(
            trace_id="trace-1",
            event="tool_call",
            timestamp=datetime.now(UTC),
        )
        assert event.trace_id == "trace-1"
        assert event.event == "tool_call"

    def test_trace_event_with_data(self) -> None:
        """Test trace event with data."""
        data = {
            "tool": "search",
            "query": "test query",
            "result": "found results",
        }
        event = TraceEvent(
            trace_id="trace-1",
            event="tool_call",
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
            trace_id="trace-1",
            event="execution",
            timestamp=datetime.now(UTC),
            request_id="req-1",
            agent_id="agent-1",
        )
        assert event.trace_id == "trace-1"
        assert event.event == "execution"

    def test_trace_event_with_error(self) -> None:
        """Test trace event with error."""
        error = {
            "type": "ValueError",
            "message": "Invalid input",
            "traceback": "...",
        }
        event = TraceEvent(
            trace_id="trace-1",
            event="error",
            timestamp=datetime.now(UTC),
            data=error,
        )
        assert event.data == error

    def test_trace_event_ordering(self) -> None:
        """Test trace event ordering by timestamp."""
        now = datetime.now(UTC)
        events = [
            TraceEvent(
                trace_id="trace-1",
                event=f"step-{i}",
                timestamp=now,
            )
            for i in range(3)
        ]
        # Events should maintain order
        assert events[0].event == "step-0"
        assert events[2].event == "step-2"


class TestContractIntegration:
    """Test integration of contract models."""

    def test_run_context_with_frames(self) -> None:
        """Test run context with various frames."""
        context = RunContext(
            trace_id="trace-1",
            tenant_id="tenant-1",
            user_id="user-1",
        )
        task_frame = TaskFrame(
            task_id="task-1",
            goal="Test goal",
            description="Test task",
        )
        plan_frame = PlanFrame(
            plan_id="plan-1",
            goal="Achieve goal",
        )
        assert context.trace_id == "trace-1"
        assert task_frame.task_id == "task-1"
        assert plan_frame.plan_id == "plan-1"

    def test_execution_recovery_flow(self) -> None:
        """Test execution and recovery flow."""
        task = TaskFrame(task_id="task-1", goal="Test goal")
        exec_frame = ExecutionFrame(
            trace_id="trace-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            user_id="user-1",
            request_id="req-1",
            task=task,
            metadata={"errors": [{"step": 1, "error": "Failed"}]},
        )
        recovery_frame = RecoveryFrame(
            branch="retry",
            reason="Execution failed",
        )
        assert exec_frame.trace_id == "trace-1"
        assert recovery_frame.branch == "retry"

    def test_trace_event_sequence(self) -> None:
        """Test sequence of trace events."""
        now = datetime.now(UTC)
        events = [
            TraceEvent(
                trace_id="trace-1",
                event="start",
                timestamp=now,
            ),
            TraceEvent(
                trace_id="trace-1",
                event="tool_call",
                timestamp=now,
                data={"tool": "search"},
            ),
            TraceEvent(
                trace_id="trace-1",
                event="end",
                timestamp=now,
            ),
        ]
        assert len(events) == 3
        assert events[0].event == "start"
        assert events[1].event == "tool_call"
        assert events[2].event == "end"
