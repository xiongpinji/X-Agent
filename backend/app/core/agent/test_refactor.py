"""
Tests for refactored AgentLoop components.

Validates that each component works correctly in isolation and integration.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from backend.app.core.contracts import RunContext, TaskFrame
from backend.app.core.agent.executor import ToolExecutor, ToolExecutionConfig
from backend.app.core.agent.planner import TaskPlanner
from backend.app.core.agent.memory_manager import MemoryManager
from backend.app.core.agent.state_manager import StateManager, ExecutionState
from backend.app.core.agent.coordinator import AgentCoordinator


@pytest.fixture
def mock_context():
    """Create mock RunContext."""
    return RunContext(
        trace_id="test-trace-123",
        tenant_id="test-tenant",
        user_id="test-user",
        request_id="test-request",
        agent_id="test-agent",
    )


@pytest.fixture
def mock_task_frame():
    """Create mock TaskFrame."""
    return TaskFrame(
        goal="Test goal",
        description="Test description",
        risk_level="low",
        requires_approval=False,
        metadata={},
    )


class TestToolExecutor:
    """Tests for ToolExecutor component."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_context):
        """Test successful tool execution."""
        mock_tools = AsyncMock()
        mock_record = Mock()
        mock_record.success = True
        mock_record.output = {"result": "success"}
        mock_record.error = None
        mock_record.latency_ms = 100
        mock_tools.execute.return_value = mock_record

        executor = ToolExecutor(mock_tools)
        result = await executor.execute(mock_context, "test_tool", {"arg": "value"})

        assert result.success is True
        assert result.output == {"result": "success"}
        assert result.latency_ms == 100

    @pytest.mark.asyncio
    async def test_execute_failure(self, mock_context):
        """Test failed tool execution."""
        mock_tools = AsyncMock()
        mock_record = Mock()
        mock_record.success = False
        mock_record.output = None
        mock_record.error = "Tool failed"
        mock_record.latency_ms = 50
        mock_tools.execute.return_value = mock_record

        executor = ToolExecutor(mock_tools)
        result = await executor.execute(mock_context, "test_tool", {"arg": "value"})

        assert result.success is False
        assert result.error == "Tool failed"

    def test_execution_history(self, mock_context):
        """Test execution history tracking."""
        mock_tools = AsyncMock()
        executor = ToolExecutor(mock_tools)

        # Simulate executions
        executor._execution_history.append({
            "tool_name": "tool1",
            "success": True,
            "latency_ms": 100,
            "error": None,
        })
        executor._execution_history.append({
            "tool_name": "tool2",
            "success": False,
            "latency_ms": 50,
            "error": "Failed",
        })

        history = executor.get_execution_history()
        assert len(history) == 2
        assert executor.get_success_rate() == 0.5
        assert executor.get_average_latency() == 75.0


class TestTaskPlanner:
    """Tests for TaskPlanner component."""

    def test_decompose_task(self):
        """Test task decomposition."""
        mock_llm = Mock()
        mock_tools = Mock()
        planner = TaskPlanner(mock_llm, mock_tools)

        subtasks = planner.decompose(
            "Fix the bug in the authentication module",
            {"root": "/project"},
        )

        assert len(subtasks) > 0
        assert any("fix" in s.lower() or "patch" in s.lower() for s in subtasks)

    def test_analyze_task(self):
        """Test task analysis."""
        mock_llm = Mock()
        mock_tools = Mock()
        planner = TaskPlanner(mock_llm, mock_tools)

        profile = planner.analyze_task(
            "Write a new feature for user authentication",
            {"root": "/project"},
        )

        assert profile.mode in {"edit", "analyze", "search", "summarize", "general"}
        assert profile.intent in {"code_change", "analysis", "summary", "discovery", "automation", "general"}
        assert 0 <= profile.complexity <= 1.0
        assert 0 <= profile.urgency <= 1.0

    def test_infer_mode(self):
        """Test task mode inference."""
        mock_llm = Mock()
        mock_tools = Mock()
        planner = TaskPlanner(mock_llm, mock_tools)

        assert planner._infer_mode("Write a new file", {}) == "edit"
        assert planner._infer_mode("Analyze the code", {}) == "analyze"
        assert planner._infer_mode("Summarize the results", {}) == "summarize"
        assert planner._infer_mode("Search for files", {}) == "search"


class TestMemoryManager:
    """Tests for MemoryManager component."""

    @pytest.mark.asyncio
    async def test_store_memory(self, mock_context):
        """Test memory storage."""
        mock_memory = AsyncMock()
        mock_memory.store.return_value = "memory-123"

        manager = MemoryManager(mock_memory)
        memory_id = await manager.store(
            mock_context,
            "Test content",
            layer=3,
            importance=0.5,
            tags=["test"],
        )

        assert memory_id == "memory-123"
        mock_memory.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_memory(self, mock_context):
        """Test memory retrieval."""
        mock_memory = AsyncMock()
        mock_memory.retrieve.return_value = [
            {"id": "mem-1", "content": "Test content 1"},
            {"id": "mem-2", "content": "Test content 2"},
        ]

        manager = MemoryManager(mock_memory)
        results = await manager.retrieve(mock_context, "test query", limit=5)

        assert len(results) == 2
        assert results[0]["id"] == "mem-1"

    def test_cache_clearing(self, mock_context):
        """Test cache clearing."""
        mock_memory = Mock()
        manager = MemoryManager(mock_memory)

        # Add to cache
        manager._retrieval_cache["query:5"] = [{"id": "mem-1"}]
        assert len(manager._retrieval_cache) > 0

        # Clear cache
        manager.clear_cache()
        assert len(manager._retrieval_cache) == 0


class TestStateManager:
    """Tests for StateManager component."""

    def test_create_initial_state(self, mock_context, mock_task_frame):
        """Test initial state creation."""
        manager = StateManager()
        state = manager.create_initial_state(
            mock_context,
            mock_task_frame,
            metadata={"test": "value"},
        )

        assert state.context == mock_context
        assert state.task_frame == mock_task_frame
        assert state.metadata["test"] == "value"
        assert state.iterations == 0

    def test_update_state(self, mock_context, mock_task_frame):
        """Test state updates."""
        manager = StateManager()
        state = manager.create_initial_state(mock_context, mock_task_frame)

        updated = manager.update_state(state, iterations=5)
        assert updated.iterations == 5

    def test_state_history(self, mock_context, mock_task_frame):
        """Test state history tracking."""
        manager = StateManager()
        state1 = manager.create_initial_state(mock_context, mock_task_frame)
        state2 = manager.update_state(state1, iterations=1)
        state3 = manager.update_state(state2, iterations=2)

        history = manager.get_state_history()
        assert len(history) == 3
        assert history[-1].iterations == 2

    def test_recovery_frame(self, mock_context, mock_task_frame):
        """Test recovery frame management."""
        from backend.app.core.contracts import RecoveryFrame

        manager = StateManager()
        state = manager.create_initial_state(mock_context, mock_task_frame)

        recovery = RecoveryFrame(
            branch="continue",
            retryable=True,
            confidence=0.8,
        )

        updated = manager.set_recovery_frame(state, recovery)
        assert updated.recovery_frame == recovery
        assert updated.recovery_frame.confidence == 0.8


class TestAgentCoordinator:
    """Tests for AgentCoordinator component."""

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self):
        """Test coordinator initialization."""
        mock_executor = Mock()
        mock_planner = Mock()
        mock_memory = Mock()
        mock_state = Mock()

        coordinator = AgentCoordinator(
            mock_executor,
            mock_planner,
            mock_memory,
            mock_state,
            max_iterations=4,
        )

        assert coordinator.executor == mock_executor
        assert coordinator.planner == mock_planner
        assert coordinator.memory == mock_memory
        assert coordinator.state == mock_state
        assert coordinator.max_iterations == 4

    def test_finalize_answer(self):
        """Test answer finalization."""
        mock_executor = Mock()
        mock_planner = Mock()
        mock_memory = Mock()
        mock_state = Mock()

        coordinator = AgentCoordinator(
            mock_executor,
            mock_planner,
            mock_memory,
            mock_state,
        )

        # Test with reflections
        answer = coordinator._finalize_answer(
            "task",
            "goal",
            ["obs1", "obs2"],
            ["reflection1", "reflection2"],
        )
        assert answer == "reflection2"

        # Test with observations only
        answer = coordinator._finalize_answer(
            "task",
            "goal",
            ["obs1", "obs2"],
            [],
        )
        assert "goal" in answer

        # Test with nothing
        answer = coordinator._finalize_answer("task", "goal", [], [])
        assert "goal" in answer


class TestComponentIntegration:
    """Integration tests for refactored components."""

    def test_components_work_together(self, mock_context, mock_task_frame):
        """Test that components can work together."""
        mock_executor = Mock()
        mock_planner = Mock()
        mock_memory = Mock()
        mock_state = StateManager()

        coordinator = AgentCoordinator(
            mock_executor,
            mock_planner,
            mock_memory,
            mock_state,
        )

        # Create state
        state = mock_state.create_initial_state(mock_context, mock_task_frame)
        assert state is not None

        # Update state
        updated = mock_state.update_state(state, iterations=1)
        assert updated.iterations == 1

        # Get history
        history = mock_state.get_state_history()
        assert len(history) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
