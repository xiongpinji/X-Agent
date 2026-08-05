"""
Integration Tests for Parallel Execution Engine

Tests:
- Tool DAG execution with dependencies
- Multi-agent coordination
- Inter-agent communication
- Error handling and recovery
- Concurrency and thread safety
- Performance under load
"""

import asyncio
import pytest
from typing import Any, Dict, List

from backend.app.core.parallel_execution_engine import (
    ParallelToolExecutor,
    ParallelAgentExecutor,
    AgentCommunicationBus,
    TaskScheduler,
    ExecutionMonitor,
    ToolDefinition,
    ToolCall,
    Message,
    PriorityLevel,
    ExecutionStatus,
    DAGBuilder,
)


class TestDAGBuilder:
    """Test DAG construction and analysis."""

    def test_dag_construction(self):
        """Test basic DAG construction."""
        dag = DAGBuilder()

        # Add nodes
        call1 = ToolCall(tool_id="1", tool_name="tool1")
        call2 = ToolCall(tool_id="2", tool_name="tool2", depends_on=["1"])
        call3 = ToolCall(tool_id="3", tool_name="tool3", depends_on=["1"])

        dag.add_node(call1)
        dag.add_node(call2)
        dag.add_node(call3)

        # Add edges
        dag.add_edge("1", "2")
        dag.add_edge("1", "3")

        assert len(dag.nodes) == 3
        assert len(dag.edges["1"]) == 2

    def test_topological_sort(self):
        """Test topological sorting."""
        dag = DAGBuilder()

        call1 = ToolCall(tool_id="1", tool_name="tool1")
        call2 = ToolCall(tool_id="2", tool_name="tool2", depends_on=["1"])
        call3 = ToolCall(tool_id="3", tool_name="tool3", depends_on=["2"])

        dag.build_from_calls([call1, call2, call3])

        order = dag.get_execution_order()
        assert order == ["1", "2", "3"]

    def test_cycle_detection(self):
        """Test cycle detection."""
        dag = DAGBuilder()

        call1 = ToolCall(tool_id="1", tool_name="tool1", depends_on=["3"])
        call2 = ToolCall(tool_id="2", tool_name="tool2", depends_on=["1"])
        call3 = ToolCall(tool_id="3", tool_name="tool3", depends_on=["2"])

        dag.build_from_calls([call1, call2, call3])

        assert dag.has_cycle()

    def test_ready_nodes(self):
        """Test ready node detection."""
        dag = DAGBuilder()

        call1 = ToolCall(tool_id="1", tool_name="tool1")
        call2 = ToolCall(tool_id="2", tool_name="tool2", depends_on=["1"])
        call3 = ToolCall(tool_id="3", tool_name="tool3", depends_on=["1"])

        dag.build_from_calls([call1, call2, call3])

        # Initially only node 1 is ready
        ready = dag.get_ready_nodes(set())
        assert "1" in ready
        assert "2" not in ready
        assert "3" not in ready

        # After completing node 1, nodes 2 and 3 are ready
        ready = dag.get_ready_nodes({"1"})
        assert "2" in ready
        assert "3" in ready


class TestParallelToolExecutor:
    """Test parallel tool execution."""

    @pytest.mark.asyncio
    async def test_simple_tool_execution(self):
        """Test simple tool execution."""
        executor = ParallelToolExecutor(max_concurrent=5)

        async def simple_tool(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 2

        executor.register_tool(ToolDefinition(
            name="simple_tool",
            handler=simple_tool,
        ))

        tool_calls = [
            ToolCall(
                tool_id=f"call_{i}",
                tool_name="simple_tool",
                arguments={"value": i},
            )
            for i in range(5)
        ]

        results = await executor.execute_tools(tool_calls)

        assert len(results) == 5
        for i in range(5):
            assert results[f"call_{i}"] == i * 2

    @pytest.mark.asyncio
    async def test_tool_with_dependencies(self):
        """Test tool execution with dependencies."""
        executor = ParallelToolExecutor(max_concurrent=5)

        async def tool_a() -> int:
            await asyncio.sleep(0.01)
            return 10

        async def tool_b(value: int) -> int:
            await asyncio.sleep(0.01)
            return value + 5

        executor.register_tool(ToolDefinition(name="tool_a", handler=tool_a))
        executor.register_tool(ToolDefinition(name="tool_b", handler=tool_b))

        tool_calls = [
            ToolCall(tool_id="a", tool_name="tool_a", arguments={}),
            ToolCall(
                tool_id="b",
                tool_name="tool_b",
                arguments={"value": 0},  # Will be overridden
                depends_on=["a"],
            ),
        ]

        results = await executor.execute_tools(tool_calls)

        assert results["a"] == 10
        assert results["b"] == 15

    @pytest.mark.asyncio
    async def test_tool_timeout(self):
        """Test tool timeout handling."""
        executor = ParallelToolExecutor(max_concurrent=5)

        async def slow_tool() -> None:
            await asyncio.sleep(10)

        executor.register_tool(ToolDefinition(
            name="slow_tool",
            handler=slow_tool,
            timeout_seconds=0.1,
        ))

        tool_calls = [
            ToolCall(tool_id="slow", tool_name="slow_tool", arguments={})
        ]

        with pytest.raises(asyncio.TimeoutError):
            await executor.execute_tools(tool_calls)

    @pytest.mark.asyncio
    async def test_tool_retry(self):
        """Test tool retry logic."""
        executor = ParallelToolExecutor(max_concurrent=5)

        call_count = 0

        async def flaky_tool() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("First call fails")
            return "success"

        executor.register_tool(ToolDefinition(
            name="flaky_tool",
            handler=flaky_tool,
            retry_count=2,
        ))

        tool_calls = [
            ToolCall(tool_id="flaky", tool_name="flaky_tool", arguments={})
        ]

        results = await executor.execute_tools(tool_calls)
        assert results["flaky"] == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        """Test metrics collection."""
        executor = ParallelToolExecutor(max_concurrent=5)

        async def metric_tool() -> str:
            await asyncio.sleep(0.05)
            return "done"

        executor.register_tool(ToolDefinition(
            name="metric_tool",
            handler=metric_tool,
        ))

        tool_calls = [
            ToolCall(tool_id="m1", tool_name="metric_tool", arguments={})
        ]

        await executor.execute_tools(tool_calls)

        metrics = executor.get_metrics()
        assert "m1" in metrics
        assert metrics["m1"].status == ExecutionStatus.COMPLETED
        assert metrics["m1"].duration_ms > 0


class TestParallelAgentExecutor:
    """Test parallel agent execution."""

    class MockAgent:
        def __init__(self, agent_id: str, delay: float = 0.01):
            self.agent_id = agent_id
            self.delay = delay

        async def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
            await asyncio.sleep(self.delay)
            return {
                "agent_id": self.agent_id,
                "task": task,
                "context": context,
            }

    @pytest.mark.asyncio
    async def test_single_agent_execution(self):
        """Test single agent execution."""
        executor = ParallelAgentExecutor(max_agents=10)

        agent = self.MockAgent("agent_1")
        executor.register_agent("agent_1", agent)

        results = await executor.execute_agents(
            agent_ids=["agent_1"],
            task="test task",
            context={"key": "value"},
        )

        assert "agent_1" in results
        assert results["agent_1"]["agent_id"] == "agent_1"

    @pytest.mark.asyncio
    async def test_multiple_agents_execution(self):
        """Test multiple agents execution."""
        executor = ParallelAgentExecutor(max_agents=10)

        agents = [self.MockAgent(f"agent_{i}") for i in range(5)]
        for agent in agents:
            executor.register_agent(agent.agent_id, agent)

        results = await executor.execute_agents(
            agent_ids=[agent.agent_id for agent in agents],
            task="test task",
            context={},
        )

        assert len(results) == 5
        for i in range(5):
            assert f"agent_{i}" in results

    @pytest.mark.asyncio
    async def test_agent_metrics(self):
        """Test agent metrics collection."""
        executor = ParallelAgentExecutor(max_agents=10)

        agent = self.MockAgent("agent_1", delay=0.05)
        executor.register_agent("agent_1", agent)

        await executor.execute_agents(
            agent_ids=["agent_1"],
            task="test",
            context={},
        )

        metrics = executor.get_agent_metrics()
        assert "agent_1" in metrics
        assert metrics["agent_1"]["tasks_completed"] == 1


class TestAgentCommunicationBus:
    """Test inter-agent communication."""

    @pytest.mark.asyncio
    async def test_send_receive_message(self):
        """Test message sending and receiving."""
        bus = AgentCommunicationBus()

        message = Message(
            sender_id="agent_1",
            recipient_id="agent_2",
            message_type="data",
            payload={"data": "test"},
        )

        sent = await bus.send_message(message)
        assert sent

        received = await bus.receive_message("agent_2", timeout_seconds=1.0)
        assert received is not None
        assert received.payload["data"] == "test"

    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """Test message broadcasting."""
        bus = AgentCommunicationBus()

        message = Message(
            sender_id="coordinator",
            recipient_id="",
            message_type="task",
            payload={"task": "work"},
        )

        sent_count = await bus.broadcast_message(
            message,
            ["agent_1", "agent_2", "agent_3"],
        )

        assert sent_count == 3

        # Each agent should receive the message
        for agent_id in ["agent_1", "agent_2", "agent_3"]:
            received = await bus.receive_message(agent_id, timeout_seconds=1.0)
            assert received is not None

    @pytest.mark.asyncio
    async def test_message_timeout(self):
        """Test message receive timeout."""
        bus = AgentCommunicationBus()

        received = await bus.receive_message("agent_1", timeout_seconds=0.1)
        assert received is None

    @pytest.mark.asyncio
    async def test_message_history(self):
        """Test message history tracking."""
        bus = AgentCommunicationBus()

        for i in range(5):
            message = Message(
                sender_id="agent_1",
                recipient_id="agent_2",
                payload={"index": i},
            )
            await bus.send_message(message)

        history = bus.get_message_history("agent_2", limit=10)
        assert len(history) == 5


class TestTaskScheduler:
    """Test task scheduling."""

    @pytest.mark.asyncio
    async def test_priority_scheduling(self):
        """Test priority-based scheduling."""
        scheduler = TaskScheduler(max_concurrent=1)

        execution_order = []

        async def task(task_id: str):
            execution_order.append(task_id)
            await asyncio.sleep(0.01)

        # Schedule tasks with different priorities
        await scheduler.schedule_task("low", task("low"), priority=PriorityLevel.LOW)
        await scheduler.schedule_task("high", task("high"), priority=PriorityLevel.HIGH)
        await scheduler.schedule_task("normal", task("normal"), priority=PriorityLevel.NORMAL)

        # Run scheduler
        scheduler_task = asyncio.create_task(scheduler.run_scheduler())
        await asyncio.sleep(0.2)
        scheduler_task.cancel()

        # High priority should execute first
        assert execution_order[0] == "high"

    @pytest.mark.asyncio
    async def test_scheduler_stats(self):
        """Test scheduler statistics."""
        scheduler = TaskScheduler(max_concurrent=2)

        async def task():
            await asyncio.sleep(0.01)

        await scheduler.schedule_task("task_1", task())
        await scheduler.schedule_task("task_2", task())

        stats = scheduler.get_stats()
        assert stats["queue_size"] == 2
        assert stats["max_concurrent"] == 2


class TestExecutionMonitor:
    """Test execution monitoring."""

    def test_metrics_recording(self):
        """Test metrics recording."""
        monitor = ExecutionMonitor()

        monitor.record_execution(
            execution_id="exec_1",
            duration_ms=100.0,
            status=ExecutionStatus.COMPLETED,
        )

        history = monitor.get_execution_history(limit=10)
        assert len(history) == 1
        assert history[0]["duration_ms"] == 100.0

    def test_performance_stats(self):
        """Test performance statistics."""
        monitor = ExecutionMonitor()

        for i in range(10):
            monitor.record_execution(
                execution_id=f"exec_{i}",
                duration_ms=100.0 + i * 10,
                status=ExecutionStatus.COMPLETED,
            )

        stats = monitor.get_performance_stats()
        assert stats["total_executions"] == 10
        assert stats["avg_duration_ms"] > 100
        assert stats["p95_duration_ms"] > stats["p50_duration_ms"]


class TestIntegration:
    """Integration tests combining multiple components."""

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test end-to-end workflow."""
        tool_executor = ParallelToolExecutor(max_concurrent=5)
        monitor = ExecutionMonitor()

        async def extract() -> Dict[str, Any]:
            await asyncio.sleep(0.05)
            return {"data": "extracted"}

        async def transform(data: Dict[str, Any]) -> Dict[str, Any]:
            await asyncio.sleep(0.05)
            return {"data": "transformed"}

        async def load(data: Dict[str, Any]) -> Dict[str, Any]:
            await asyncio.sleep(0.05)
            return {"data": "loaded"}

        tool_executor.register_tool(ToolDefinition(name="extract", handler=extract))
        tool_executor.register_tool(ToolDefinition(name="transform", handler=transform))
        tool_executor.register_tool(ToolDefinition(name="load", handler=load))

        tool_calls = [
            ToolCall(tool_id="extract", tool_name="extract", arguments={}),
            ToolCall(
                tool_id="transform",
                tool_name="transform",
                arguments={},
                depends_on=["extract"],
            ),
            ToolCall(
                tool_id="load",
                tool_name="load",
                arguments={},
                depends_on=["transform"],
            ),
        ]

        import time
        start = time.time()
        results = await tool_executor.execute_tools(tool_calls)
        duration = (time.time() - start) * 1000

        monitor.record_execution(
            execution_id="workflow",
            duration_ms=duration,
            status=ExecutionStatus.COMPLETED,
        )

        assert "extract" in results
        assert "transform" in results
        assert "load" in results

        stats = monitor.get_performance_stats()
        assert stats["total_executions"] == 1


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
