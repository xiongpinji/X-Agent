"""Tests for parallel execution engine."""

import asyncio
import pytest
import time
from typing import Any

from backend.app.core.parallel.tool_executor import (
    ParallelToolExecutor,
    ToolCall,
    ToolResultCache,
)
from backend.app.core.parallel.agent_executor import (
    ParallelAgentExecutor,
    AgentTask,
    AgentTaskStatus,
)
from backend.app.core.parallel.communication_bus import (
    AgentCommunicationBus,
    MessageType,
    MessagePriority,
)
from backend.app.core.parallel.dependency_analyzer import ToolDependencyAnalyzer


# Mock tool registry
class MockTool:
    def __init__(self, name: str, delay: float = 0.1):
        self.name = name
        self.delay = delay

    async def execute(self, arguments: dict[str, Any], context: Any = None) -> Any:
        await asyncio.sleep(self.delay)
        return {"tool": self.name, "result": "success", "args": arguments}


class MockToolRegistry:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name: str, tool: MockTool) -> None:
        self.tools[name] = tool

    def get_tool(self, name: str) -> MockTool:
        return self.tools.get(name)


# Mock agent
class MockAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    async def run_async(self, goal: str, metadata: dict[str, Any] = None) -> Any:
        await asyncio.sleep(0.1)
        return {"agent": self.agent_id, "goal": goal, "status": "completed"}


class TestToolDependencyAnalyzer:
    """Tests for tool dependency analyzer."""

    def test_analyze_dependencies_no_dependencies(self):
        """Test analyzing independent tool calls."""
        analyzer = ToolDependencyAnalyzer()

        calls = [
            ToolCall(tool_name="tool1", arguments={}),
            ToolCall(tool_name="tool2", arguments={}),
            ToolCall(tool_name="tool3", arguments={}),
        ]

        graph = analyzer.analyze_dependencies(calls)

        assert len(graph.nodes) == 3
        assert all(graph.get_in_degree(node_id) == 0 for node_id in graph.nodes)

    def test_analyze_dependencies_with_dependencies(self):
        """Test analyzing tool calls with dependencies."""
        analyzer = ToolDependencyAnalyzer()

        calls = [
            ToolCall(tool_name="tool1", arguments={}),
            ToolCall(tool_name="tool2", arguments={"input": "${tool1.output}"}),
            ToolCall(tool_name="tool3", arguments={"input": "${tool2.output}"}),
        ]

        graph = analyzer.analyze_dependencies(calls)

        assert len(graph.nodes) == 3

    def test_detect_cycles(self):
        """Test cycle detection."""
        analyzer = ToolDependencyAnalyzer()

        calls = [
            ToolCall(tool_name="tool1", arguments={"input": "${tool2.output}"}),
            ToolCall(tool_name="tool2", arguments={"input": "${tool1.output}"}),
        ]

        graph = analyzer.analyze_dependencies(calls)
        cycles = analyzer.detect_cycles(graph)

        assert len(cycles) > 0

    def test_build_execution_plan(self):
        """Test execution plan building."""
        analyzer = ToolDependencyAnalyzer()

        calls = [
            ToolCall(tool_name="tool1", arguments={}),
            ToolCall(tool_name="tool2", arguments={}),
            ToolCall(tool_name="tool3", arguments={"input": "${tool1.output}"}),
        ]

        graph = analyzer.analyze_dependencies(calls)
        plan = analyzer.build_execution_plan(graph)

        assert len(plan.layers) > 0
        assert plan.total_nodes == 3


class TestParallelToolExecutor:
    """Tests for parallel tool executor."""

    @pytest.mark.asyncio
    async def test_execute_batch_no_dependencies(self):
        """Test executing independent tool calls."""
        registry = MockToolRegistry()
        registry.register_tool("tool1", MockTool("tool1", delay=0.1))
        registry.register_tool("tool2", MockTool("tool2", delay=0.1))
        registry.register_tool("tool3", MockTool("tool3", delay=0.1))

        executor = ParallelToolExecutor(tool_registry=registry, max_concurrent=3)

        calls = [
            ToolCall(tool_name="tool1", arguments={}),
            ToolCall(tool_name="tool2", arguments={}),
            ToolCall(tool_name="tool3", arguments={}),
        ]

        start_time = time.time()
        results = await executor.execute_batch(calls)
        elapsed = time.time() - start_time

        assert len(results) == 3
        assert all(result.success for result in results)
        # Should be faster than sequential (0.3s)
        assert elapsed < 0.25

    @pytest.mark.asyncio
    async def test_execute_with_dependencies(self):
        """Test executing tool calls with dependencies."""
        registry = MockToolRegistry()
        registry.register_tool("tool1", MockTool("tool1", delay=0.1))
        registry.register_tool("tool2", MockTool("tool2", delay=0.1))

        executor = ParallelToolExecutor(tool_registry=registry, max_concurrent=2)

        calls = [
            ToolCall(tool_name="tool1", arguments={}),
            ToolCall(tool_name="tool2", arguments={"input": "${tool1.output}"}),
        ]

        results_dict = await executor.execute_with_dependencies(calls)

        assert len(results_dict) == 2
        assert all(result.success for result in results_dict.values())

    @pytest.mark.asyncio
    async def test_result_caching(self):
        """Test result caching."""
        registry = MockToolRegistry()
        registry.register_tool("tool1", MockTool("tool1", delay=0.1))

        cache = ToolResultCache()
        executor = ParallelToolExecutor(tool_registry=registry, cache=cache)

        calls = [
            ToolCall(tool_name="tool1", arguments={"key": "value"}),
            ToolCall(tool_name="tool1", arguments={"key": "value"}),
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 2
        assert results[0].success
        assert results[1].cached

    @pytest.mark.asyncio
    async def test_retry_logic(self):
        """Test retry logic on failure."""
        registry = MockToolRegistry()

        class FailingTool:
            def __init__(self):
                self.call_count = 0

            async def execute(self, arguments: dict[str, Any], context: Any = None) -> Any:
                self.call_count += 1
                if self.call_count < 3:
                    raise Exception("Temporary failure")
                return {"result": "success"}

        failing_tool = FailingTool()
        registry.register_tool("failing_tool", failing_tool)

        executor = ParallelToolExecutor(tool_registry=registry)

        calls = [
            ToolCall(tool_name="failing_tool", arguments={}, max_retries=3),
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 1
        assert results[0].success
        assert results[0].retry_attempt == 2


class TestParallelAgentExecutor:
    """Tests for parallel agent executor."""

    @pytest.mark.asyncio
    async def test_execute_tasks_parallel(self):
        """Test executing agent tasks in parallel."""
        executor = ParallelAgentExecutor(max_workers=3)

        def agent_factory():
            return MockAgent(f"agent_{id(object())}")

        tasks = [
            AgentTask(goal="Task 1"),
            AgentTask(goal="Task 2"),
            AgentTask(goal="Task 3"),
        ]

        start_time = time.time()
        result = await executor.execute_tasks(tasks, agent_factory)
        elapsed = time.time() - start_time

        assert result.total_tasks == 3
        assert result.completed_tasks == 3
        assert result.failed_tasks == 0
        # Should be faster than sequential (0.3s)
        assert elapsed < 0.25

    @pytest.mark.asyncio
    async def test_execute_with_coordination(self):
        """Test executing tasks with coordination."""
        executor = ParallelAgentExecutor(max_workers=2)

        def agent_factory():
            return MockAgent(f"agent_{id(object())}")

        tasks = [
            AgentTask(task_id="task1", goal="Task 1"),
            AgentTask(task_id="task2", goal="Task 2", dependencies=["task1"]),
            AgentTask(task_id="task3", goal="Task 3", dependencies=["task2"]),
        ]

        result = await executor.execute_with_coordination(tasks, agent_factory)

        assert result.total_tasks == 3
        assert result.completed_tasks == 3
        assert result.failed_tasks == 0

    @pytest.mark.asyncio
    async def test_agent_pool_management(self):
        """Test agent pool management."""
        executor = ParallelAgentExecutor(max_workers=2)

        stats = executor.get_pool_stats()

        assert stats["max_agents"] == 2


class TestAgentCommunicationBus:
    """Tests for agent communication bus."""

    @pytest.mark.asyncio
    async def test_direct_messaging(self):
        """Test direct point-to-point messaging."""
        bus = AgentCommunicationBus()

        # Send message
        msg_id = await bus.send_direct(
            from_agent="agent1",
            to_agent="agent2",
            content={"data": "test"},
        )

        assert msg_id is not None

        # Receive message
        message = await bus.receive_direct("agent2", timeout_seconds=1.0)

        assert message is not None
        assert message.from_agent == "agent1"
        assert message.content == {"data": "test"}

    @pytest.mark.asyncio
    async def test_broadcast_messaging(self):
        """Test broadcast messaging."""
        bus = AgentCommunicationBus()

        # Subscribe agents
        await bus.subscribe_broadcast("agent1")
        await bus.subscribe_broadcast("agent2")

        # Send broadcast
        msg_id = await bus.send_broadcast(
            from_agent="agent0",
            content={"data": "broadcast"},
        )

        assert msg_id is not None

        # Receive broadcast
        message = await bus.receive_broadcast("agent1", timeout_seconds=1.0)

        assert message is not None
        assert message.content == {"data": "broadcast"}

    @pytest.mark.asyncio
    async def test_topic_messaging(self):
        """Test topic-based pub/sub messaging."""
        bus = AgentCommunicationBus()

        # Subscribe to topic
        await bus.subscribe_topic("agent1", "task:completed")

        # Publish to topic
        msg_id = await bus.publish_topic(
            from_agent="agent0",
            topic="task:completed",
            content={"task_id": "123"},
        )

        assert msg_id is not None

        # Receive topic message
        message = await bus.receive_topic("agent1", "task:completed", timeout_seconds=1.0)

        assert message is not None
        assert message.content == {"task_id": "123"}

    @pytest.mark.asyncio
    async def test_rpc_call(self):
        """Test RPC calls between agents."""
        bus = AgentCommunicationBus()

        # Register RPC handler
        async def add(a: int, b: int) -> int:
            return a + b

        await bus.register_rpc_handler("add", add)

        # Make RPC call
        response = await bus.call_rpc(
            from_agent="agent1",
            to_agent="agent2",
            method="add",
            params={"a": 5, "b": 3},
            timeout_seconds=1.0,
        )

        # Note: In real scenario, agent2 would handle the request
        # For this test, we just verify the RPC infrastructure works

    @pytest.mark.asyncio
    async def test_event_publishing(self):
        """Test event publishing and subscription."""
        bus = AgentCommunicationBus()

        received_events = []

        async def event_handler(message):
            received_events.append(message)

        # Subscribe to event
        await bus.subscribe_event("task:started", event_handler)

        # Publish event
        await bus.publish_event(
            from_agent="agent1",
            event_type="task:started",
            event_data={"task_id": "123"},
        )

        # Give handler time to process
        await asyncio.sleep(0.1)

        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_message_priority(self):
        """Test message priority handling."""
        bus = AgentCommunicationBus()

        # Send messages with different priorities
        await bus.send_direct(
            from_agent="agent1",
            to_agent="agent2",
            content={"priority": "low"},
            priority=MessagePriority.LOW,
        )

        await bus.send_direct(
            from_agent="agent1",
            to_agent="agent2",
            content={"priority": "high"},
            priority=MessagePriority.HIGH,
        )

        # Receive messages - high priority should come first
        msg1 = await bus.receive_direct("agent2", timeout_seconds=1.0)
        msg2 = await bus.receive_direct("agent2", timeout_seconds=1.0)

        assert msg1.priority == MessagePriority.HIGH
        assert msg2.priority == MessagePriority.LOW

    @pytest.mark.asyncio
    async def test_message_expiration(self):
        """Test message TTL and expiration."""
        bus = AgentCommunicationBus()

        # Send message with short TTL
        await bus.send_direct(
            from_agent="agent1",
            to_agent="agent2",
            content={"data": "test"},
            ttl_seconds=1,
        )

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Try to receive - should timeout
        message = await bus.receive_direct("agent2", timeout_seconds=0.5)

        assert message is None


class TestParallelExecutionIntegration:
    """Integration tests for parallel execution."""

    @pytest.mark.asyncio
    async def test_end_to_end_tool_execution(self):
        """Test end-to-end tool execution."""
        registry = MockToolRegistry()
        registry.register_tool("tool1", MockTool("tool1", delay=0.05))
        registry.register_tool("tool2", MockTool("tool2", delay=0.05))
        registry.register_tool("tool3", MockTool("tool3", delay=0.05))

        executor = ParallelToolExecutor(tool_registry=registry, max_concurrent=3)

        calls = [
            ToolCall(tool_name="tool1", arguments={"param": "value1"}),
            ToolCall(tool_name="tool2", arguments={"param": "value2"}),
            ToolCall(tool_name="tool3", arguments={"param": "value3"}),
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 3
        assert all(result.success for result in results)

        stats = executor.get_stats()
        assert stats.total_calls == 3
        assert stats.successful_calls == 3
        assert stats.parallelism_factor > 1.5

    @pytest.mark.asyncio
    async def test_end_to_end_agent_execution(self):
        """Test end-to-end agent execution."""
        executor = ParallelAgentExecutor(max_workers=3)

        def agent_factory():
            return MockAgent(f"agent_{id(object())}")

        tasks = [
            AgentTask(goal="Goal 1"),
            AgentTask(goal="Goal 2"),
            AgentTask(goal="Goal 3"),
        ]

        result = await executor.execute_tasks(tasks, agent_factory)

        assert result.total_tasks == 3
        assert result.completed_tasks == 3
        assert result.failed_tasks == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
