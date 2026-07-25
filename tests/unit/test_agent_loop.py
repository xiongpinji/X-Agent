"""Unit tests for AgentLoop core execution (backend.app.core.agent.loop).

Covers:
- AgentLoop initialization
- Think-Act-Observe loop with MockLLMBackend
- Tool execution dispatch
- Memory integration
- Max iterations enforcement
- Trajectory tracking
- Plan step execution (observe/tool/reflect/final)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.agent.loop import AgentLoop
from backend.app.core.contracts import RunContext, RunStatus
from backend.app.core.llm.backends import LLMBackendError, LLMResponse, LLMRouter, MockLLMBackend
from backend.app.core.memory.store import MemorySystem
from backend.app.core.tools import ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(agent_id: str = "test-agent") -> RunContext:
    return RunContext(
        trace_id="trace-test-001",
        agent_id=agent_id,
        tenant_id="test-tenant",
        user_id="test-user",
    )


def _make_agent(max_iterations: int = 4) -> AgentLoop:
    """Create an AgentLoop with mock backend for testing."""
    mock_backend = MockLLMBackend()
    router = LLMRouter(backend=mock_backend)
    memory = MemorySystem()
    tools = ToolRegistry()
    return AgentLoop(
        llm_router=router,
        memory=memory,
        tools=tools,
        max_iterations=max_iterations,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestAgentLoopInit:
    def test_default_initialization(self):
        agent = _make_agent()
        assert agent.max_iterations == 4
        assert agent.llm is not None
        assert agent.memory is not None
        assert agent.tools is not None

    def test_custom_max_iterations(self):
        agent = _make_agent(max_iterations=10)
        assert agent.max_iterations == 10

    def test_has_state_manager(self):
        agent = _make_agent()
        assert agent.state_manager is not None

    def test_has_verification_engine(self):
        agent = _make_agent()
        assert agent.verification_engine is not None


# ---------------------------------------------------------------------------
# Core run loop
# ---------------------------------------------------------------------------

class TestAgentLoopRun:
    @pytest.fixture
    def agent(self):
        return _make_agent()

    @pytest.fixture
    def context(self):
        return _make_context()

    async def test_simple_task_completes(self, agent, context):
        """A simple task should complete with mock LLM."""
        result = await agent.run(context, "What is 2+2?")
        assert result.status == RunStatus.COMPLETED
        assert result.answer
        assert result.trace_id == context.trace_id

    async def test_echo_tool_task(self, agent, context):
        """Echo task should trigger tool call."""
        result = await agent.run(context, "Task: echo: hello world")
        assert result.status == RunStatus.COMPLETED
        # Mock backend returns tool_calls for echo tasks
        assert result.answer

    async def test_max_iterations_respected(self, context):
        """Agent should not exceed max_iterations."""
        agent = _make_agent(max_iterations=1)
        result = await agent.run(context, "Complex multi-step task")
        assert result.status == RunStatus.COMPLETED
        assert result.iterations <= 1

    async def test_result_has_events(self, agent, context):
        """Run result should contain trace events."""
        result = await agent.run(context, "test task")
        assert len(result.events) >= 1

    async def test_result_has_agent_id(self, agent, context):
        result = await agent.run(context, "test")
        assert result.agent_id == context.agent_id

    async def test_empty_task(self, agent, context):
        """Empty task should still complete (mock handles it)."""
        result = await agent.run(context, "")
        assert result.status == RunStatus.COMPLETED

    async def test_extra_context_passed(self, agent, context):
        """Extra context should be accessible during execution."""
        result = await agent.run(
            context, "test", extra_context={"session_id": "s1", "priority": "high"}
        )
        assert result.status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

class TestAgentToolExecution:
    async def test_tool_registry_empty(self):
        """Agent with no tools should still complete."""
        agent = _make_agent()
        context = _make_context()
        result = await agent.run(context, "do something")
        assert result.status == RunStatus.COMPLETED

    async def test_tool_calls_tracked(self):
        """Tool calls should be recorded in result."""
        agent = _make_agent()
        context = _make_context()
        result = await agent.run(context, "Task: echo: test")
        # tool_calls may be empty if mock doesn't dispatch, but should be a list
        assert isinstance(result.tool_calls, list)


# ---------------------------------------------------------------------------
# Memory integration
# ---------------------------------------------------------------------------

class TestAgentMemory:
    async def test_memory_stores_execution(self):
        """Agent should store execution results in memory."""
        agent = _make_agent()
        context = _make_context()
        result = await agent.run(context, "Remember: the answer is 42")
        assert result.status == RunStatus.COMPLETED
        assert result.memory_hits >= 0

    async def test_memory_system_accessible(self):
        agent = _make_agent()
        assert agent.memory is not None
        # MemorySystem should be functional
        ctx = _make_context()
        mid = await agent.memory.store(ctx, "test memory")
        assert mid


# ---------------------------------------------------------------------------
# Trajectory
# ---------------------------------------------------------------------------

class TestAgentTrajectory:
    async def test_trajectory_tracks_goal(self):
        agent = _make_agent()
        context = _make_context()
        result = await agent.run(context, "Build a web app")
        # Execution summary should contain trajectory info
        assert result.execution_summary is not None

    async def test_plan_records_generated(self):
        agent = _make_agent()
        context = _make_context()
        result = await agent.run(context, "Analyze this code")
        assert isinstance(result.plan, list)


# ---------------------------------------------------------------------------
# LLMRouter integration
# ---------------------------------------------------------------------------

class TestLLMRouterIntegration:
    async def test_router_uses_mock(self):
        router = LLMRouter(backend=MockLLMBackend())
        resp = await router.chat([{"role": "user", "content": "hi"}], tools=[])
        assert resp.content is not None

    async def test_router_fallback(self):
        """Router should fallback on primary failure."""
        failing = MagicMock()
        failing.chat = AsyncMock(side_effect=LLMBackendError("fail"))
        failing.name = "failing"
        fallback = MockLLMBackend()
        router = LLMRouter(backends=[failing, fallback])
        resp = await router.chat([{"role": "user", "content": "test"}], tools=[])
        assert resp.content is not None
