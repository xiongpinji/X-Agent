"""Fixtures for agent_v2 tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from backend.app.core.agent import AgentLoop, AgentPlanStep, AgentTrajectory
from backend.app.core.agent_phases import PhaseContext
from backend.app.core.agent_state_manager import AgentStateManager
from backend.app.core.agent_runtime_adapter import AgentRuntimeAdapter
from backend.app.core.contracts import (
    ExecutionFrame,
    PlanFrame,
    RecoveryFrame,
    RunContext,
    RiskLevel,
    TaskFrame,
    ToolCallRecord,
    ToolPolicyVerdict,
)
from backend.app.core.orchestrator import Orchestrator
from backend.app.core.repair_loop import RepairLoop
from backend.app.core.verification import VerificationEngine


@pytest.fixture
def run_context() -> RunContext:
    """Create a test RunContext."""
    return RunContext(
        trace_id=str(uuid4()),
        tenant_id="test-tenant",
        user_id="test-user",
        agent_id=str(uuid4()),
        request_id=str(uuid4()),
        session_id=str(uuid4()),
        permission_scope=["tools:read", "memory:read", "memory:write"],
        budget_tokens=16_000,
        budget_usd=1.0,
        risk_level=RiskLevel.LOW,
    )


@pytest.fixture
def task_frame() -> TaskFrame:
    """Create a test TaskFrame."""
    return TaskFrame(
        task_id=str(uuid4()),
        goal="Test goal",
        description="Test task description",
        constraints=["constraint1", "constraint2"],
        risk_level=RiskLevel.LOW,
        success_criteria=["criterion1", "criterion2"],
        fallback_policy="replan",
        requires_approval=False,
        source="agent",
        metadata={"test": True},
    )


@pytest.fixture
def plan_frame() -> PlanFrame:
    """Create a test PlanFrame."""
    return PlanFrame(
        plan_id=str(uuid4()),
        goal="Test plan goal",
        steps=["step1", "step2", "step3"],
        dependencies=["dep1"],
        risks=["risk1"],
        verification_steps=["verify1"],
        rollback_steps=["rollback1"],
        status="draft",
        revision=0,
    )


@pytest.fixture
def execution_frame(task_frame: TaskFrame) -> ExecutionFrame:
    """Create a test ExecutionFrame."""
    return ExecutionFrame(
        trace_id=str(uuid4()),
        agent_id=str(uuid4()),
        tenant_id="test-tenant",
        user_id="test-user",
        request_id=str(uuid4()),
        task=task_frame,
        session_id=str(uuid4()),
        metadata={"test": True},
    )


@pytest.fixture
def recovery_frame() -> RecoveryFrame:
    """Create a test RecoveryFrame."""
    return RecoveryFrame(
        branch="continue",
        reason="Test recovery",
        status_detail="test status",
        error_type="test_error",
        retry_count=0,
        compensation_steps=["comp1"],
        approval_id=None,
        escalation_target=None,
        next_action="continue",
        next_actions=["action1"],
        recovery_plan={"test": True},
        status="active",
        pending_count=0,
        latest_decision="continue",
        resource_type="test",
        resource_id=str(uuid4()),
        remediation="test remediation",
        retryable=False,
        confidence=0.5,
        tool_name="test_tool",
        follow_up=["follow_up1"],
    )


@pytest.fixture
def agent_trajectory() -> AgentTrajectory:
    """Create a test AgentTrajectory."""
    return AgentTrajectory(
        task="Test task",
        goal="Test goal",
        stage="planning",
        subtasks=["subtask1", "subtask2"],
        subtask_status={"subtask1": "pending", "subtask2": "pending"},
        current_subtask_index=0,
        observations=["obs1", "obs2"],
        tool_results=[{"tool": "test", "result": "success"}],
        reflections=["reflection1"],
        steps=[
            AgentPlanStep(
                kind="tool",
                instruction="Execute test tool",
                tool_name="test_tool",
                arguments={"arg1": "value1"},
            )
        ],
    )


@pytest.fixture
def tool_call_record() -> ToolCallRecord:
    """Create a test ToolCallRecord."""
    return ToolCallRecord(
        tool_name="test_tool",
        success=True,
        output={"result": "success"},
        error=None,
        policy=ToolPolicyVerdict(
            allowed=True,
            requires_approval=False,
            sandbox_profile="none",
            reason="Test policy",
            audit_required=True,
        ),
        risk_level=RiskLevel.LOW,
        latency_ms=100.0,
        arguments_preview={"arg1": "value1"},
        trace_id=str(uuid4()),
        request_id=str(uuid4()),
    )


@pytest.fixture
def mock_llm_router() -> MagicMock:
    """Create a mock LLMRouter."""
    mock = MagicMock()
    mock.route = AsyncMock(return_value="Test response")
    return mock


@pytest.fixture
def mock_memory_system() -> MagicMock:
    """Create a mock MemorySystem."""
    mock = MagicMock()
    mock.store = AsyncMock(return_value=str(uuid4()))
    mock.retrieve = AsyncMock(return_value=["memory1", "memory2"])
    mock.count = MagicMock(return_value=10)
    return mock


@pytest.fixture
def mock_tool_registry() -> MagicMock:
    """Create a mock ToolRegistry."""
    mock = MagicMock()
    mock.execute = AsyncMock()
    mock.capability_index = MagicMock(return_value={"test_tool": "test capability"})
    return mock


@pytest.fixture
def mock_tracer() -> MagicMock:
    """Create a mock TraceStore."""
    mock = MagicMock()
    mock.record = MagicMock(return_value=str(uuid4()))
    mock.emit = AsyncMock()
    return mock


@pytest.fixture
def mock_run_store() -> MagicMock:
    """Create a mock RunStore."""
    mock = MagicMock()
    mock.save = MagicMock()
    mock.get = MagicMock(return_value=None)
    return mock


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    """Create a mock Orchestrator."""
    mock = MagicMock(spec=Orchestrator)
    mock.prepare = MagicMock(
        return_value=(
            MagicMock(metadata={"test": True}),
            MagicMock(name="test_capability", reason="test reason"),
            MagicMock(branch="continue"),
        )
    )
    mock.draft_plan = MagicMock(
        return_value=PlanFrame(
            goal="Test plan",
            steps=["step1", "step2"],
            status="draft",
        )
    )
    mock.select_tool = MagicMock(
        return_value=MagicMock(
            tool_name="test_tool",
            reason="test reason",
            risk_level=RiskLevel.LOW,
        )
    )
    return mock


@pytest.fixture
def mock_verification_engine() -> MagicMock:
    """Create a mock VerificationEngine."""
    mock = MagicMock(spec=VerificationEngine)
    mock.verify = MagicMock(return_value=True)
    mock.summarize_run = MagicMock(return_value={"verified": True})
    return mock


@pytest.fixture
def mock_repair_loop() -> MagicMock:
    """Create a mock RepairLoop."""
    mock = MagicMock(spec=RepairLoop)
    mock.analyze = MagicMock(
        return_value=(
            MagicMock(verified=True),
            MagicMock(
                should_retry=False,
                tool_name=None,
                arguments={},
                reason="test",
                error_type="test_error",
                confidence=0.5,
                follow_up=None,
            ),
        )
    )
    return mock


@pytest.fixture
def mock_state_manager() -> MagicMock:
    """Create a mock AgentStateManager."""
    mock = MagicMock(spec=AgentStateManager)
    mock.create_initial_state = MagicMock(return_value={"state": "initial"})
    mock.attach_execution_frame = MagicMock(return_value={"state": "with_frame"})
    mock.set_recovery_frame = MagicMock(return_value={"state": "with_recovery"})
    mock.attach_plan_frame = MagicMock(return_value={"state": "with_plan"})
    mock.build_initial_recovery = MagicMock(
        return_value=RecoveryFrame(branch="continue")
    )
    return mock


@pytest.fixture
def mock_runtime_adapter() -> MagicMock:
    """Create a mock AgentRuntimeAdapter."""
    mock = MagicMock(spec=AgentRuntimeAdapter)
    mock.build_run_view = MagicMock(
        return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
    )
    return mock


@pytest.fixture
def agent_loop(
    mock_llm_router: MagicMock,
    mock_memory_system: MagicMock,
    mock_tool_registry: MagicMock,
    mock_tracer: MagicMock,
    mock_run_store: MagicMock,
    mock_orchestrator: MagicMock,
    mock_verification_engine: MagicMock,
    mock_repair_loop: MagicMock,
) -> AgentLoop:
    """Create a test AgentLoop with mocked dependencies."""
    loop = AgentLoop(
        llm_router=mock_llm_router,
        memory=mock_memory_system,
        tools=mock_tool_registry,
        max_iterations=4,
        tracer=mock_tracer,
        run_store=mock_run_store,
        orchestrator=mock_orchestrator,
        verification_engine=mock_verification_engine,
        repair_loop=mock_repair_loop,
    )
    # Replace state manager and runtime adapter with mocks
    loop.state_manager = MagicMock(spec=AgentStateManager)
    loop.state_manager.create_initial_state = MagicMock(return_value={"state": "initial"})
    loop.state_manager.attach_execution_frame = MagicMock(
        return_value={"state": "with_frame"}
    )
    loop.state_manager.set_recovery_frame = MagicMock(
        return_value={"state": "with_recovery"}
    )
    loop.state_manager.attach_plan_frame = MagicMock(
        return_value={"state": "with_plan"}
    )
    loop.state_manager.build_initial_recovery = MagicMock(
        return_value=RecoveryFrame(branch="continue")
    )
    loop.runtime_adapter = MagicMock(spec=AgentRuntimeAdapter)
    loop.runtime_adapter.build_run_view = MagicMock(
        return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
    )
    return loop


@pytest.fixture
def phase_context(
    agent_loop: AgentLoop,
    run_context: RunContext,
    task_frame: TaskFrame,
    execution_frame: ExecutionFrame,
    plan_frame: PlanFrame,
    agent_trajectory: AgentTrajectory,
) -> PhaseContext:
    """Create a test PhaseContext."""
    return PhaseContext(
        loop=agent_loop,
        context=run_context,
        task="Test task",
        trajectory=agent_trajectory,
        extra_context={"test": True},
        execution_frame=execution_frame,
        task_frame=task_frame,
        plan_frame=plan_frame,
        compact_context={"test": True},
        tool_calls=[],
        observations=[],
        answer="",
        iteration=0,
    )
