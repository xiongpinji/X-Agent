"""Extended test coverage for agent module."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock, patch

from backend.app.core.agent import AgentLoop, AgentTrajectory, AgentPlanStep
from backend.app.core.contracts import RunContext, RunStatus, ToolCallRecord, ToolPolicyVerdict, RiskLevel
from backend.app.core.llm import LLMRouter
from backend.app.core.memory import InMemoryMemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry
from backend.app.core.verification import VerificationEngine
from backend.app.core.repair_loop import RepairLoop


class TestAgentTrajectory:
    """Test AgentTrajectory dataclass."""

    def test_trajectory_creation(self) -> None:
        """Test creating agent trajectory."""
        trajectory = AgentTrajectory(
            task="Summarize the document",
            goal="Extract key points",
        )

        assert trajectory.task == "Summarize the document"
        assert trajectory.goal == "Extract key points"
        assert trajectory.stage == "planning"
        assert trajectory.subtasks == []
        assert trajectory.observations == []
        assert trajectory.tool_results == []
        assert trajectory.reflections == []
        assert trajectory.steps == []
        assert trajectory.current_subtask_index == 0

    def test_trajectory_with_subtasks(self) -> None:
        """Test trajectory with subtasks."""
        trajectory = AgentTrajectory(
            task="Build a system",
            goal="Complete implementation",
            subtasks=["Design", "Implement", "Test"],
        )

        assert len(trajectory.subtasks) == 3
        assert trajectory.subtasks[0] == "Design"

    def test_trajectory_stage_progression(self) -> None:
        """Test trajectory stage progression."""
        trajectory = AgentTrajectory(task="Test", goal="Test", stage="execution")
        assert trajectory.stage == "execution"

        trajectory.stage = "reflection"
        assert trajectory.stage == "reflection"


class TestAgentPlanStep:
    """Test AgentPlanStep dataclass."""

    def test_plan_step_creation(self) -> None:
        """Test creating plan step."""
        step = AgentPlanStep(
            kind="tool_call",
            instruction="Read the file",
            tool_name="read_file",
            arguments={"path": "test.py"},
        )

        assert step.kind == "tool_call"
        assert step.instruction == "Read the file"
        assert step.tool_name == "read_file"
        assert step.arguments == {"path": "test.py"}

    def test_plan_step_without_tool(self) -> None:
        """Test plan step without tool."""
        step = AgentPlanStep(
            kind="think",
            instruction="Analyze the problem",
        )

        assert step.kind == "think"
        assert step.tool_name is None
        assert step.arguments == {}


class TestAgentLoopInitialization:
    """Test AgentLoop initialization."""

    def test_agent_loop_creation(self) -> None:
        """Test creating agent loop."""
        memory = InMemoryMemorySystem()
        tools = build_default_tool_registry(ToolPolicyEngine())
        llm = LLMRouter()

        agent = AgentLoop(
            llm_router=llm,
            memory=memory,
            tools=tools,
        )

        assert agent.llm == llm
        assert agent.memory == memory
        assert agent.tools == tools
        assert agent.max_iterations == 4

    def test_agent_loop_custom_iterations(self) -> None:
        """Test agent loop with custom max iterations."""
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=InMemoryMemorySystem(),
            tools=build_default_tool_registry(ToolPolicyEngine()),
            max_iterations=10,
        )

        assert agent.max_iterations == 10

    def test_agent_loop_with_verification_engine(self) -> None:
        """Test agent loop with custom verification engine."""
        verification_engine = VerificationEngine()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=InMemoryMemorySystem(),
            tools=build_default_tool_registry(ToolPolicyEngine()),
            verification_engine=verification_engine,
        )

        assert agent.verification_engine == verification_engine

    def test_agent_loop_with_repair_loop(self) -> None:
        """Test agent loop with custom repair loop."""
        repair_loop = RepairLoop()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=InMemoryMemorySystem(),
            tools=build_default_tool_registry(ToolPolicyEngine()),
            repair_loop=repair_loop,
        )

        assert agent.repair_loop == repair_loop


class TestAgentLoopRecoveryFrame:
    """Test agent loop recovery frame building."""

    def test_build_initial_recovery_frame(self) -> None:
        """Test building initial recovery frame."""
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=InMemoryMemorySystem(),
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        frame = agent._build_initial_recovery_frame()

        assert frame.branch == "continue"
        assert frame.retryable is False
        assert frame.confidence == 0.5
        assert frame.tool_name is None
        assert "continue planning" in frame.follow_up

    def test_build_initial_recovery_frame_with_tool(self) -> None:
        """Test building initial recovery frame with tool name."""
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=InMemoryMemorySystem(),
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        frame = agent._build_initial_recovery_frame(tool_name="read_file")

        assert frame.tool_name == "read_file"


class TestAgentLoopIntegration:
    """Integration tests for agent loop."""

    @pytest.mark.asyncio
    async def test_agent_run_basic(self) -> None:
        """Test basic agent run."""
        memory = InMemoryMemorySystem()
        context = RunContext()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        result = await agent.run(context, "介绍一下 X-Agent")

        assert result.status == RunStatus.COMPLETED
        assert result.answer is not None
        assert len(result.events) > 0

    @pytest.mark.asyncio
    async def test_agent_run_with_permission_scope(self) -> None:
        """Test agent run with permission scope."""
        memory = InMemoryMemorySystem()
        context = RunContext(permission_scope=["tools:read"])
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        result = await agent.run(context, "echo: hello")

        assert result.status == RunStatus.COMPLETED
        assert len(result.tool_calls) > 0

    @pytest.mark.asyncio
    async def test_agent_run_execution_summary(self) -> None:
        """Test agent run execution summary."""
        memory = InMemoryMemorySystem()
        context = RunContext()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        result = await agent.run(context, "test query")

        assert "branch" in result.execution_summary
        assert "workflow_state" in result.execution_summary
        assert result.execution_summary["branch"] == "continue"

    @pytest.mark.asyncio
    async def test_agent_run_snapshot(self) -> None:
        """Test agent run snapshot."""
        memory = InMemoryMemorySystem()
        context = RunContext()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        result = await agent.run(context, "test query")

        assert result.snapshot is not None
        assert "execution_summary" in result.snapshot
        assert "execution_frame" in result.snapshot
        assert result.snapshot["count"] >= 1
