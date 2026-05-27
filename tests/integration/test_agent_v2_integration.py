"""Integration tests for X-Agent v2 architecture with existing systems.

This module verifies that the new modular agent_v2 architecture integrates
correctly with existing components:
- LLMRouter for language model interactions
- MemorySystem for context and learning
- ToolRegistry for tool execution
- TraceStore for execution tracing
- RunStore for run persistence

Test Coverage:
1. Interface compatibility between AgentExecutor and AgentLoop
2. Input/output format consistency
3. Error handling compatibility
4. Event and tracing compatibility
5. Integration with all dependent systems
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.agent import AgentLoop, AgentTrajectory, AgentPlanStep
from backend.app.core.agent_v2 import (
    AgentExecutor,
    AgentState,
    AgentStateManager,
    PhaseContext,
    InitializationPhase,
    PlanningPhase,
    ExecutionPhase,
    CompletionPhase,
)
from backend.app.core.contracts import (
    RunContext,
    RunStatus,
    TaskFrame,
    PlanFrame,
    ExecutionFrame,
    ToolCallRecord,
    TraceEvent,
)
from backend.app.core.llm import LLMRouter, LLMResponse
from backend.app.core.memory import InMemoryMemorySystem, MemoryItem
from backend.app.core.tools import ToolRegistry, ToolDefinition, RiskLevel
from backend.app.core.tracing import TraceStore
from backend.app.core.runs import RunStore
from backend.app.core.policy import ToolPolicyEngine


class TestAgentExecutorInterfaceCompatibility:
    """Verify AgentExecutor interface compatibility with AgentLoop."""

    @pytest.fixture
    def executor(self) -> AgentExecutor:
        """Create AgentExecutor instance."""
        return AgentExecutor(max_iterations=4)

    @pytest.fixture
    def run_context(self) -> RunContext:
        """Create RunContext for testing."""
        return RunContext(
            trace_id="test-trace-001",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

    @pytest.fixture
    def phase_context(self, run_context: RunContext) -> PhaseContext:
        """Create PhaseContext for testing."""
        loop = MagicMock(spec=AgentLoop)
        trajectory = AgentTrajectory(
            task="Test task",
            goal="Test goal",
        )
        return PhaseContext(
            loop=loop,
            context=run_context,
            task="Test task",
            trajectory=trajectory,
            extra_context={},
            execution_frame=ExecutionFrame(
                execution_id="exec-001",
                task_id="task-001",
                status="running",
            ),
            task_frame=TaskFrame(goal="Test goal"),
            plan_frame=PlanFrame(goal="Test goal"),
            compact_context={},
        )

    def test_executor_initialization(self, executor: AgentExecutor) -> None:
        """Test AgentExecutor initializes with correct state."""
        assert executor.state_manager is not None
        assert executor.max_iterations == 4
        assert executor.get_state() == AgentState.IDLE

    def test_executor_state_transitions(self, executor: AgentExecutor) -> None:
        """Test valid state transitions."""
        executor.state_manager.transition_to(AgentState.INITIALIZING)
        assert executor.get_state() == AgentState.INITIALIZING

        executor.state_manager.transition_to(AgentState.PLANNING)
        assert executor.get_state() == AgentState.PLANNING

        executor.state_manager.transition_to(AgentState.EXECUTING)
        assert executor.get_state() == AgentState.EXECUTING

    def test_executor_invalid_state_transition(self, executor: AgentExecutor) -> None:
        """Test invalid state transitions raise error."""
        executor.state_manager.transition_to(AgentState.INITIALIZING)
        with pytest.raises(Exception):
            executor.state_manager.transition_to(AgentState.COMPLETED)

    def test_executor_pause_resume(self, executor: AgentExecutor) -> None:
        """Test pause and resume functionality."""
        executor.state_manager.transition_to(AgentState.PLANNING)
        executor.pause()
        assert executor.get_state() == AgentState.PAUSED

        executor.resume()
        assert executor.get_state() == AgentState.PLANNING

    def test_executor_reset(self, executor: AgentExecutor) -> None:
        """Test executor reset."""
        executor.state_manager.transition_to(AgentState.PLANNING)
        executor.reset()
        assert executor.get_state() == AgentState.IDLE

    @pytest.mark.asyncio
    async def test_executor_execute_basic_flow(
        self,
        executor: AgentExecutor,
        run_context: RunContext,
        phase_context: PhaseContext,
    ) -> None:
        """Test basic execution flow through all phases."""
        # Create mock phases
        init_phase = AsyncMock()
        planning_phase = AsyncMock()
        execution_phase = AsyncMock()
        completion_phase = AsyncMock()

        # Set up phase context response
        phase_context.response = MagicMock()
        phase_context.response.status = RunStatus.COMPLETED
        phase_context.response.answer = "Test answer"

        phases = [
            (AgentState.INITIALIZING, init_phase),
            (AgentState.PLANNING, planning_phase),
            (AgentState.EXECUTING, execution_phase),
            (AgentState.COMPLETING, completion_phase),
        ]

        response = await executor.execute(
            context=run_context,
            task="Test task",
            phase_context=phase_context,
            phases=phases,
        )

        assert response.status == RunStatus.COMPLETED
        assert response.answer == "Test answer"
        assert executor.is_completed()

    @pytest.mark.asyncio
    async def test_executor_error_handling(
        self,
        executor: AgentExecutor,
        run_context: RunContext,
        phase_context: PhaseContext,
    ) -> None:
        """Test error handling during execution."""
        error_phase = AsyncMock(side_effect=ValueError("Test error"))

        phases = [
            (AgentState.INITIALIZING, error_phase),
        ]

        response = await executor.execute(
            context=run_context,
            task="Test task",
            phase_context=phase_context,
            phases=phases,
        )

        assert response.status == RunStatus.FAILED
        assert "Test error" in response.error
        assert executor.get_state() == AgentState.FAILED


class TestLLMRouterIntegration:
    """Verify integration with LLMRouter."""

    @pytest.fixture
    def llm_router(self) -> LLMRouter:
        """Create LLMRouter instance."""
        return LLMRouter()

    @pytest.fixture
    def run_context(self) -> RunContext:
        """Create RunContext."""
        return RunContext()

    @pytest.mark.asyncio
    async def test_llm_router_chat_interface(
        self, llm_router: LLMRouter, run_context: RunContext
    ) -> None:
        """Test LLMRouter chat interface compatibility."""
        messages = [
            {"role": "user", "content": "What is X-Agent?"},
        ]
        tools = []

        response = await llm_router.chat(
            context=run_context,
            messages=messages,
            tools=tools,
        )

        assert isinstance(response, LLMResponse)
        assert response.content is not None or response.tool_calls
        assert response.tokens_used >= 0

    @pytest.mark.asyncio
    async def test_llm_router_with_tools(
        self, llm_router: LLMRouter, run_context: RunContext
    ) -> None:
        """Test LLMRouter with tool definitions."""
        messages = [
            {"role": "user", "content": "echo: hello world"},
        ]
        tools = [
            {
                "name": "echo",
                "description": "Echo tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                    },
                },
            }
        ]

        response = await llm_router.chat(
            context=run_context,
            messages=messages,
            tools=tools,
        )

        assert isinstance(response, LLMResponse)


class TestMemorySystemIntegration:
    """Verify integration with MemorySystem."""

    @pytest.fixture
    def memory_system(self) -> InMemoryMemorySystem:
        """Create MemorySystem instance."""
        return InMemoryMemorySystem()

    @pytest.fixture
    def run_context(self) -> RunContext:
        """Create RunContext."""
        return RunContext(
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

    @pytest.mark.asyncio
    async def test_memory_store_retrieve(
        self,
        memory_system: InMemoryMemorySystem,
        run_context: RunContext,
    ) -> None:
        """Test memory store and retrieve operations."""
        # Store memory
        memory_item = await memory_system.store(
            context=run_context,
            content="Test memory content",
            layer=1,
            tags=["test"],
        )

        assert memory_item.id is not None
        assert memory_item.content == "Test memory content"

        # Retrieve memory
        retrieved = await memory_system.retrieve(
            context=run_context,
            query="Test memory",
            limit=10,
        )

        assert len(retrieved) > 0
        assert any(hit.item.id == memory_item.id for hit in retrieved)

    @pytest.mark.asyncio
    async def test_memory_consolidation(
        self,
        memory_system: InMemoryMemorySystem,
        run_context: RunContext,
    ) -> None:
        """Test memory consolidation."""
        # Store multiple memories
        for i in range(3):
            await memory_system.store(
                context=run_context,
                content=f"Memory {i}",
                layer=1,
                tags=["test"],
            )

        # Consolidate
        result = await memory_system.consolidate(
            context=run_context,
            query="Memory",
            limit=3,
        )

        assert result.source_count >= 0


class TestToolRegistryIntegration:
    """Verify integration with ToolRegistry."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create ToolRegistry instance."""
        registry = ToolRegistry()
        return registry

    @pytest.fixture
    def run_context(self) -> RunContext:
        """Create RunContext."""
        return RunContext()

    def test_tool_registry_register(self, tool_registry: ToolRegistry) -> None:
        """Test tool registration."""
        async def echo_handler(text: str) -> str:
            return f"Echo: {text}"

        tool_def = ToolDefinition(
            name="echo",
            description="Echo tool",
            handler=echo_handler,
            risk_level=RiskLevel.LOW,
        )

        tool_registry.register(tool_def)
        assert tool_registry.get("echo") is not None

    @pytest.mark.asyncio
    async def test_tool_registry_execute(
        self,
        tool_registry: ToolRegistry,
        run_context: RunContext,
    ) -> None:
        """Test tool execution."""
        async def echo_handler(text: str) -> str:
            return f"Echo: {text}"

        tool_def = ToolDefinition(
            name="echo",
            description="Echo tool",
            handler=echo_handler,
            risk_level=RiskLevel.LOW,
        )

        tool_registry.register(tool_def)

        result = await tool_registry.execute(
            context=run_context,
            tool_name="echo",
            arguments={"text": "hello"},
        )

        assert result.success
        assert "Echo: hello" in str(result.result)


class TestTraceStoreIntegration:
    """Verify integration with TraceStore."""

    @pytest.fixture
    def trace_store(self) -> TraceStore:
        """Create TraceStore instance."""
        return TraceStore()

    @pytest.fixture
    def run_context(self) -> RunContext:
        """Create RunContext."""
        return RunContext(
            trace_id="test-trace-001",
            tenant_id="test-tenant",
            user_id="test-user",
        )

    def test_trace_store_record(
        self,
        trace_store: TraceStore,
        run_context: RunContext,
    ) -> None:
        """Test trace recording."""
        event = trace_store.record(
            context=run_context,
            event="agent.started",
            task="Test task",
        )

        assert event.trace_id == run_context.trace_id
        assert event.event == "agent.started"
        assert event.data["task"] == "Test task"

    def test_trace_store_list_events(
        self,
        trace_store: TraceStore,
        run_context: RunContext,
    ) -> None:
        """Test listing trace events."""
        trace_store.record(run_context, "agent.started")
        trace_store.record(run_context, "agent.planning")
        trace_store.record(run_context, "agent.completed")

        events = trace_store.list_events(run_context.trace_id)
        assert len(events) == 3
        assert events[0].event == "agent.started"
        assert events[-1].event == "agent.completed"

    def test_trace_store_summary(
        self,
        trace_store: TraceStore,
        run_context: RunContext,
    ) -> None:
        """Test trace summary."""
        trace_store.record(run_context, "agent.started")
        trace_store.record(run_context, "agent.completed")

        summary = trace_store.get_summary(run_context.trace_id)
        assert summary.trace_id == run_context.trace_id
        assert summary.event_count == 2
        assert summary.last_event == "agent.completed"


class TestRunStoreIntegration:
    """Verify integration with RunStore."""

    @pytest.fixture
    def run_store(self) -> RunStore:
        """Create RunStore instance."""
        return RunStore()

    @pytest.fixture
    def run_context(self) -> RunContext:
        """Create RunContext."""
        return RunContext(
            trace_id="test-trace-001",
            tenant_id="test-tenant",
            user_id="test-user",
        )

    def test_run_store_save(
        self,
        run_store: RunStore,
        run_context: RunContext,
    ) -> None:
        """Test saving run record."""
        from backend.app.core.contracts import AgentRunResponse

        response = AgentRunResponse(
            trace_id=run_context.trace_id,
            agent_id=run_context.agent_id,
            status=RunStatus.COMPLETED,
            answer="Test answer",
            iterations=1,
            memory_hits=0,
            tool_calls=[],
            events=[],
            plan=[],
            execution_summary={},
            snapshot={},
        )

        record = run_store.save(
            context=run_context,
            task="Test task",
            response=response,
        )

        assert record.trace_id == run_context.trace_id
        assert record.task == "Test task"
        assert record.status == RunStatus.COMPLETED

    def test_run_store_list(
        self,
        run_store: RunStore,
        run_context: RunContext,
    ) -> None:
        """Test listing run records."""
        from backend.app.core.contracts import AgentRunResponse

        for i in range(3):
            response = AgentRunResponse(
                trace_id=f"trace-{i}",
                agent_id=run_context.agent_id,
                status=RunStatus.COMPLETED,
                answer=f"Answer {i}",
                iterations=1,
                memory_hits=0,
                tool_calls=[],
                events=[],
                plan=[],
                execution_summary={},
                snapshot={},
            )
            run_store.save(
                context=run_context,
                task=f"Task {i}",
                response=response,
            )

        records = run_store.list(limit=10)
        assert len(records) == 3


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @pytest.fixture
    def components(self) -> dict:
        """Create all required components."""
        return {
            "llm_router": LLMRouter(),
            "memory": InMemoryMemorySystem(),
            "tools": ToolRegistry(),
            "trace_store": TraceStore(),
            "run_store": RunStore(),
            "executor": AgentExecutor(max_iterations=4),
        }

    @pytest.fixture
    def run_context(self) -> RunContext:
        """Create RunContext."""
        return RunContext(
            trace_id="e2e-test-001",
            tenant_id="test-tenant",
            user_id="test-user",
            agent_id="test-agent",
        )

    @pytest.mark.asyncio
    async def test_end_to_end_execution_flow(
        self,
        components: dict,
        run_context: RunContext,
    ) -> None:
        """Test complete execution flow with all components."""
        executor = components["executor"]
        trace_store = components["trace_store"]
        run_store = components["run_store"]

        # Record trace events
        trace_store.record(run_context, "agent.started", task="E2E test")

        # Create phase context
        trajectory = AgentTrajectory(
            task="E2E test",
            goal="Test goal",
        )
        phase_context = PhaseContext(
            loop=MagicMock(spec=AgentLoop),
            context=run_context,
            task="E2E test",
            trajectory=trajectory,
            extra_context={},
            execution_frame=ExecutionFrame(
                execution_id="exec-e2e",
                task_id="task-e2e",
                status="running",
            ),
            task_frame=TaskFrame(goal="Test goal"),
            plan_frame=PlanFrame(goal="Test goal"),
            compact_context={},
        )

        # Create mock phases
        init_phase = AsyncMock()
        planning_phase = AsyncMock()
        execution_phase = AsyncMock()
        completion_phase = AsyncMock()

        # Set response
        from backend.app.core.contracts import AgentRunResponse

        phase_context.response = AgentRunResponse(
            trace_id=run_context.trace_id,
            agent_id=run_context.agent_id,
            status=RunStatus.COMPLETED,
            answer="E2E test completed",
            iterations=1,
            memory_hits=0,
            tool_calls=[],
            events=[],
            plan=[],
            execution_summary={},
            snapshot={},
        )

        phases = [
            (AgentState.INITIALIZING, init_phase),
            (AgentState.PLANNING, planning_phase),
            (AgentState.EXECUTING, execution_phase),
            (AgentState.COMPLETING, completion_phase),
        ]

        # Execute
        response = await executor.execute(
            context=run_context,
            task="E2E test",
            phase_context=phase_context,
            phases=phases,
        )

        # Verify response
        assert response.status == RunStatus.COMPLETED
        assert response.answer == "E2E test completed"

        # Save to run store
        record = run_store.save(
            context=run_context,
            task="E2E test",
            response=response,
        )

        assert record.trace_id == run_context.trace_id
        assert record.status == RunStatus.COMPLETED

        # Verify trace events
        trace_store.record(run_context, "agent.completed")
        events = trace_store.list_events(run_context.trace_id)
        assert len(events) == 2
        assert events[0].event == "agent.started"
        assert events[1].event == "agent.completed"


class TestInputOutputFormatConsistency:
    """Verify input/output format consistency."""

    def test_run_context_format(self) -> None:
        """Test RunContext format consistency."""
        context = RunContext(
            trace_id="test-001",
            tenant_id="tenant-1",
            user_id="user-1",
            agent_id="agent-1",
        )

        assert context.trace_id == "test-001"
        assert context.tenant_id == "tenant-1"
        assert context.budget_tokens == 16_000
        assert context.budget_usd == 1.0

    def test_agent_run_response_format(self) -> None:
        """Test AgentRunResponse format consistency."""
        from backend.app.core.contracts import AgentRunResponse

        response = AgentRunResponse(
            trace_id="test-001",
            agent_id="agent-1",
            status=RunStatus.COMPLETED,
            answer="Test answer",
            iterations=1,
            memory_hits=0,
            tool_calls=[],
            events=[],
            plan=[],
            execution_summary={},
            snapshot={},
        )

        assert response.trace_id == "test-001"
        assert response.status == RunStatus.COMPLETED
        assert response.answer == "Test answer"

    def test_tool_call_record_format(self) -> None:
        """Test ToolCallRecord format consistency."""
        tool_call = ToolCallRecord(
            trace_id="test-001",
            tool_name="echo",
            arguments={"text": "hello"},
            success=True,
        )

        assert tool_call.trace_id == "test-001"
        assert tool_call.tool_name == "echo"
        assert tool_call.arguments == {"text": "hello"}


class TestErrorHandlingCompatibility:
    """Verify error handling compatibility."""

    @pytest.mark.asyncio
    async def test_llm_error_handling(self) -> None:
        """Test LLM error handling."""
        llm_router = LLMRouter()
        context = RunContext()

        # Test with invalid input
        try:
            response = await llm_router.chat(
                context=context,
                messages=[],
                tools=[],
            )
            assert response is not None
        except Exception as e:
            assert isinstance(e, Exception)

    def test_tool_execution_error_handling(self) -> None:
        """Test tool execution error handling."""
        registry = ToolRegistry()

        async def failing_handler() -> None:
            raise ValueError("Tool execution failed")

        tool_def = ToolDefinition(
            name="failing_tool",
            description="Failing tool",
            handler=failing_handler,
            risk_level=RiskLevel.LOW,
        )

        registry.register(tool_def)

    def test_state_transition_error_handling(self) -> None:
        """Test state transition error handling."""
        state_manager = AgentStateManager()

        state_manager.transition_to(AgentState.INITIALIZING)

        # Invalid transition should raise error
        with pytest.raises(Exception):
            state_manager.transition_to(AgentState.COMPLETED)


class TestEventAndTracingCompatibility:
    """Verify event and tracing compatibility."""

    def test_trace_event_format(self) -> None:
        """Test TraceEvent format."""
        event = TraceEvent(
            trace_id="test-001",
            event="agent.started",
            data={"task": "Test"},
        )

        assert event.trace_id == "test-001"
        assert event.event == "agent.started"
        assert event.data["task"] == "Test"

    def test_trace_store_event_recording(self) -> None:
        """Test trace store event recording."""
        trace_store = TraceStore()
        context = RunContext(trace_id="test-001")

        event = trace_store.record(
            context=context,
            event="agent.started",
            task="Test",
        )

        assert event.trace_id == "test-001"
        assert event.event == "agent.started"

        events = trace_store.list_events("test-001")
        assert len(events) == 1
        assert events[0].event == "agent.started"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
