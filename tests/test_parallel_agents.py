"""
Test suite for parallel agent execution functionality.

Tests:
- Parallel execution correctness
- Isolation effectiveness
- Communication mechanisms
- Result aggregation
- Error handling
- Performance benchmarks
"""

import asyncio
import pytest
import time
from typing import Any

from backend.app.core.parallel_agent_executor import (
    ParallelAgentExecutor,
    AgentTask,
    IsolationMode,
    AgentTaskStatus,
)
from backend.app.core.agent_communication_bus import (
    AgentCommunicationBus,
    Message,
    MessagePriority,
    MessageType,
)
from backend.app.core.result_aggregator import (
    ResultAggregator,
    AggregationConfig,
    MergeStrategy,
    ConflictResolution,
)


# Test Fixtures

class _MockAgent:
    """满足 P0 后 agent_factory 契约的 mock agent。

    spawn_agents 已移除内置模拟执行(旧假成功契约), 调用方必须显式注入
    agent_factory(agent_id, isolation) -> 带 async execute(task) 的 agent。
    """

    def __init__(self, agent_id: str, isolation: IsolationMode) -> None:
        self.agent_id = agent_id
        self.isolation = isolation

    async def execute(self, task: AgentTask) -> dict[str, Any]:
        await asyncio.sleep(0)  # 让出事件循环, 保持并行调度语义
        return {"goal": task.goal, "agent_id": self.agent_id}


@pytest.fixture
def executor():
    """Create a parallel agent executor."""
    return ParallelAgentExecutor(max_workers=3)


@pytest.fixture
def mock_agent_factory():
    """spawn_agents 新契约必需的 mock agent_factory。"""
    return lambda agent_id, isolation: _MockAgent(agent_id, isolation)


@pytest.fixture
def bus():
    """Create a communication bus."""
    return AgentCommunicationBus(enable_persistence=True)


@pytest.fixture
def aggregator():
    """Create a result aggregator."""
    return ResultAggregator()


@pytest.fixture
def sample_tasks():
    """Create sample tasks for testing."""
    return [
        AgentTask(
            goal="Task 1",
            description="First task",
            timeout_seconds=10,
        ),
        AgentTask(
            goal="Task 2",
            description="Second task",
            timeout_seconds=10,
        ),
        AgentTask(
            goal="Task 3",
            description="Third task",
            timeout_seconds=10,
        ),
    ]


# Parallel Executor Tests

class TestParallelAgentExecutor:
    """Tests for ParallelAgentExecutor."""

    @pytest.mark.asyncio
    async def test_spawn_agents_basic(self, executor, sample_tasks, mock_agent_factory):
        """Test basic agent spawning."""
        result = await executor.spawn_agents(
            tasks=sample_tasks,
            isolation=IsolationMode.THREAD,
            max_parallel=2,
            agent_factory=mock_agent_factory,
        )

        assert result.batch_id is not None
        assert result.total_tasks == 3
        assert len(result.results) == 3
        assert result.total_duration_seconds > 0

    @pytest.mark.asyncio
    async def test_spawn_agents_with_timeout(self, executor, mock_agent_factory):
        """Test agent spawning with timeout."""
        tasks = [
            AgentTask(
                goal="Timeout task",
                timeout_seconds=1,
            )
        ]

        result = await executor.spawn_agents(
            tasks=tasks,
            isolation=IsolationMode.THREAD,
            agent_factory=mock_agent_factory,
        )

        assert result.total_tasks == 1
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_spawn_agents_thread_isolation(self, executor, sample_tasks, mock_agent_factory):
        """Test thread isolation mode."""
        result = await executor.spawn_agents(
            tasks=sample_tasks,
            isolation=IsolationMode.THREAD,
            max_parallel=3,
            agent_factory=mock_agent_factory,
        )

        assert result.total_tasks == 3
        assert result.metadata["isolation_mode"] == "thread"

    @pytest.mark.asyncio
    async def test_spawn_agents_process_isolation(self, executor, sample_tasks, mock_agent_factory):
        """Test process isolation mode."""
        result = await executor.spawn_agents(
            tasks=sample_tasks,
            isolation=IsolationMode.PROCESS,
            max_parallel=2,
            agent_factory=mock_agent_factory,
        )

        assert result.total_tasks == 3
        assert result.metadata["isolation_mode"] == "process"

    @pytest.mark.asyncio
    async def test_get_batch_status(self, executor, sample_tasks, mock_agent_factory):
        """Test getting batch status."""
        result = await executor.spawn_agents(
            tasks=sample_tasks,
            isolation=IsolationMode.THREAD,
            agent_factory=mock_agent_factory,
        )

        status = await executor.get_batch_status(result.batch_id)
        assert status["batch_id"] == result.batch_id
        assert status["total_tasks"] == 3
        assert status["is_active"] is False

    @pytest.mark.asyncio
    async def test_get_batch_results(self, executor, sample_tasks, mock_agent_factory):
        """Test getting batch results."""
        result = await executor.spawn_agents(
            tasks=sample_tasks,
            isolation=IsolationMode.THREAD,
            agent_factory=mock_agent_factory,
        )

        results = await executor.get_batch_results(result.batch_id)
        assert len(results) == 3
        assert all(r.task_id for r in results)

    @pytest.mark.asyncio
    async def test_cancel_batch(self, executor, sample_tasks, mock_agent_factory):
        """Test batch cancellation."""
        result = await executor.spawn_agents(
            tasks=sample_tasks,
            isolation=IsolationMode.THREAD,
            agent_factory=mock_agent_factory,
        )

        cancelled = await executor.cancel_batch(result.batch_id)
        assert cancelled is True

    @pytest.mark.asyncio
    async def test_empty_tasks_error(self, executor):
        """Test error handling for empty tasks."""
        with pytest.raises(ValueError):
            await executor.spawn_agents(tasks=[])

    @pytest.mark.asyncio
    async def test_invalid_isolation_mode(self, executor, sample_tasks):
        """Test error handling for invalid isolation mode."""
        with pytest.raises(ValueError):
            await executor.spawn_agents(
                tasks=sample_tasks,
                isolation="invalid_mode",
            )

    @pytest.mark.asyncio
    async def test_parallel_execution_speedup(self, executor, mock_agent_factory):
        """Test that parallel execution is faster than sequential."""
        # Create tasks that take time
        tasks = [
            AgentTask(goal=f"Task {i}", timeout_seconds=5)
            for i in range(3)
        ]

        start = time.time()
        result = await executor.spawn_agents(
            tasks=tasks,
            isolation=IsolationMode.THREAD,
            max_parallel=3,
            agent_factory=mock_agent_factory,
        )
        parallel_time = time.time() - start

        # Parallel execution should be faster than 3x single task time
        assert parallel_time < 3.0  # Rough estimate


# Communication Bus Tests

class TestAgentCommunicationBus:
    """Tests for AgentCommunicationBus."""

    @pytest.mark.asyncio
    async def test_send_direct_message(self, bus):
        """Test sending direct messages."""
        message_id = await bus.send_message(
            from_agent="agent1",
            to_agent="agent2",
            content={"data": "test"},
        )

        assert message_id is not None
        assert len(message_id) > 0

    @pytest.mark.asyncio
    async def test_receive_message(self, bus):
        """Test receiving messages."""
        await bus.send_message(
            from_agent="agent1",
            to_agent="agent2",
            content={"data": "test"},
        )

        message = await bus.receive_message("agent2")
        assert message is not None
        assert message.from_agent == "agent1"
        assert message.to_agent == "agent2"
        assert message.content == {"data": "test"}

    @pytest.mark.asyncio
    async def test_broadcast_message(self, bus):
        """Test broadcasting messages."""
        message_id = await bus.broadcast(
            from_agent="agent1",
            content={"broadcast": "data"},
        )

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_receive_broadcast(self, bus):
        """Test receiving broadcast messages."""
        await bus.broadcast(
            from_agent="agent1",
            content={"broadcast": "data"},
        )

        message = await bus.receive_broadcast()
        assert message is not None
        assert message.message_type == MessageType.BROADCAST

    @pytest.mark.asyncio
    async def test_publish_to_topic(self, bus):
        """Test publishing to topics."""
        message_id = await bus.publish(
            topic="test_topic",
            content={"topic": "data"},
        )

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_subscribe_to_topic(self, bus):
        """Test topic subscription."""
        await bus.subscribe(
            agent_id="agent1",
            topic="test_topic",
        )

        subscribers = await bus.get_subscribers("test_topic")
        assert "agent1" in subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe_from_topic(self, bus):
        """Test topic unsubscription."""
        await bus.subscribe(agent_id="agent1", topic="test_topic")
        await bus.unsubscribe(agent_id="agent1", topic="test_topic")

        subscribers = await bus.get_subscribers("test_topic")
        assert "agent1" not in subscribers

    @pytest.mark.asyncio
    async def test_message_priority(self, bus):
        """Test message priority handling."""
        # Send low priority message
        await bus.send_message(
            from_agent="agent1",
            to_agent="agent2",
            content={"priority": "low"},
            priority=MessagePriority.LOW,
        )

        # Send high priority message
        await bus.send_message(
            from_agent="agent1",
            to_agent="agent2",
            content={"priority": "high"},
            priority=MessagePriority.HIGH,
        )

        # High priority should be received first
        message1 = await bus.receive_message("agent2")
        assert message1.priority == MessagePriority.HIGH

    @pytest.mark.asyncio
    async def test_message_ttl(self, bus):
        """Test message time-to-live."""
        await bus.send_message(
            from_agent="agent1",
            to_agent="agent2",
            content={"data": "test"},
            ttl_seconds=1,
        )

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Clear expired messages
        removed = await bus.clear_expired_messages()
        assert removed > 0

    @pytest.mark.asyncio
    async def test_get_stats(self, bus):
        """Test getting bus statistics."""
        await bus.send_message(
            from_agent="agent1",
            to_agent="agent2",
            content={"data": "test"},
        )

        stats = await bus.get_stats()
        assert stats["total_messages"] > 0
        assert "delivered_messages" in stats

    @pytest.mark.asyncio
    async def test_message_history(self, bus):
        """Test message history."""
        await bus.send_message(
            from_agent="agent1",
            to_agent="agent2",
            content={"data": "test"},
        )

        history = await bus.get_message_history(limit=10)
        assert len(history) > 0


# Result Aggregator Tests

class TestResultAggregator:
    """Tests for ResultAggregator."""

    @pytest.mark.asyncio
    async def test_collect_results_empty(self, aggregator):
        """Test collecting empty results."""
        result = await aggregator.collect_results([])
        assert result.total_results == 0

    @pytest.mark.asyncio
    async def test_collect_results_merge_strategy(self, aggregator):
        """Test merge strategy."""
        results = [
            {"output": {"a": 1}},
            {"output": {"b": 2}},
        ]

        config = AggregationConfig(
            merge_strategy=MergeStrategy.MERGE,
        )

        aggregated = await aggregator.collect_results(results, config)
        assert aggregated.successful_results == 2
        assert aggregated.merged_output == {"a": 1, "b": 2}

    @pytest.mark.asyncio
    async def test_collect_results_concat_strategy(self, aggregator):
        """Test concatenation strategy."""
        results = [
            {"output": [1, 2]},
            {"output": [3, 4]},
        ]

        config = AggregationConfig(
            merge_strategy=MergeStrategy.CONCAT,
        )

        aggregated = await aggregator.collect_results(results, config)
        assert aggregated.merged_output == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_collect_results_first_strategy(self, aggregator):
        """Test first-win strategy."""
        results = [
            {"output": "first"},
            {"output": "second"},
        ]

        config = AggregationConfig(
            merge_strategy=MergeStrategy.FIRST,
        )

        aggregated = await aggregator.collect_results(results, config)
        assert aggregated.merged_output == "first"

    @pytest.mark.asyncio
    async def test_collect_results_last_strategy(self, aggregator):
        """Test last-win strategy."""
        results = [
            {"output": "first"},
            {"output": "second"},
        ]

        config = AggregationConfig(
            merge_strategy=MergeStrategy.LAST,
        )

        aggregated = await aggregator.collect_results(results, config)
        assert aggregated.merged_output == "second"

    @pytest.mark.asyncio
    async def test_merge_contexts(self, aggregator):
        """Test context merging."""
        results = [
            {"context": {"key1": "value1"}},
            {"context": {"key2": "value2"}},
        ]

        merged = await aggregator.merge_contexts(results)
        assert merged == {"key1": "value1", "key2": "value2"}

    @pytest.mark.asyncio
    async def test_detect_conflicts(self, aggregator):
        """Test conflict detection."""
        results = [
            {"output": "value1"},
            {"output": "value2"},
        ]

        conflicts = await aggregator._detect_conflicts(results)
        assert len(conflicts) > 0

    @pytest.mark.asyncio
    async def test_deduplicate_results(self, aggregator):
        """Test result deduplication."""
        results = [
            {"output": "same"},
            {"output": "same"},
            {"output": "different"},
        ]

        deduplicated = await aggregator._deduplicate_results(results)
        assert len(deduplicated) == 2

    @pytest.mark.asyncio
    async def test_validate_results(self, aggregator):
        """Test result validation."""
        results = [
            {"output": "valid"},
            None,
            {"error": "invalid"},
        ]

        errors = await aggregator._validate_results(results)
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_aggregator_factory_merge(self):
        """Test aggregator factory for merge."""
        from backend.app.core.result_aggregator import ResultAggregatorFactory

        aggregator = ResultAggregatorFactory.create_merge_aggregator()
        assert aggregator.config.merge_strategy == MergeStrategy.MERGE

    @pytest.mark.asyncio
    async def test_aggregator_factory_concat(self):
        """Test aggregator factory for concat."""
        from backend.app.core.result_aggregator import ResultAggregatorFactory

        aggregator = ResultAggregatorFactory.create_concat_aggregator()
        assert aggregator.config.merge_strategy == MergeStrategy.CONCAT


# Integration Tests

class TestParallelAgentIntegration:
    """Integration tests for parallel agent execution."""

    @pytest.mark.asyncio
    async def test_end_to_end_execution(self, executor, aggregator, mock_agent_factory):
        """Test end-to-end parallel execution with aggregation."""
        tasks = [
            AgentTask(goal=f"Task {i}", timeout_seconds=5)
            for i in range(3)
        ]

        result = await executor.spawn_agents(
            tasks=tasks,
            isolation=IsolationMode.THREAD,
            max_parallel=3,
            agent_factory=mock_agent_factory,
        )

        assert result.total_tasks == 3
        assert len(result.results) == 3

        # Aggregate results
        config = AggregationConfig(
            merge_strategy=MergeStrategy.MERGE,
        )
        aggregated = await aggregator.collect_results(
            [r.to_dict() for r in result.results],
            config=config,
        )

        assert aggregated.total_results == 3

    @pytest.mark.asyncio
    async def test_communication_during_execution(self, executor, bus):
        """Test inter-agent communication during execution."""
        # Subscribe to topic
        await bus.subscribe(agent_id="agent1", topic="results")

        # Publish message
        await bus.publish(
            topic="results",
            content={"result": "data"},
        )

        # Receive message
        message = await bus.receive_topic_message("results")
        assert message is not None
        assert message.content == {"result": "data"}


# Performance Tests

class TestPerformance:
    """Performance benchmarks."""

    @pytest.mark.asyncio
    async def test_parallel_vs_sequential_performance(self, executor, mock_agent_factory):
        """Benchmark parallel vs sequential execution."""
        tasks = [
            AgentTask(goal=f"Task {i}", timeout_seconds=5)
            for i in range(3)
        ]

        start = time.time()
        result = await executor.spawn_agents(
            tasks=tasks,
            isolation=IsolationMode.THREAD,
            max_parallel=3,
            agent_factory=mock_agent_factory,
        )
        parallel_time = time.time() - start

        # Parallel should be significantly faster
        assert parallel_time < 10.0

    @pytest.mark.asyncio
    async def test_message_throughput(self, bus):
        """Test message throughput."""
        start = time.time()

        for i in range(100):
            await bus.send_message(
                from_agent="agent1",
                to_agent="agent2",
                content={"index": i},
            )

        elapsed = time.time() - start
        throughput = 100 / elapsed

        # Should handle at least 10 messages per second
        assert throughput > 10

    @pytest.mark.asyncio
    async def test_aggregation_performance(self, aggregator):
        """Test aggregation performance."""
        results = [
            {"output": {"key": f"value{i}"}}
            for i in range(100)
        ]

        start = time.time()
        aggregated = await aggregator.collect_results(results)
        elapsed = time.time() - start

        # Should complete in reasonable time
        assert elapsed < 5.0
        assert aggregated.total_results == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
