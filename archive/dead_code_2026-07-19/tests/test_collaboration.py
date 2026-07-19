"""Comprehensive tests for multi-agent collaboration system."""

from __future__ import annotations

import asyncio
import pytest
from datetime import UTC, datetime

from backend.app.core.collaboration.protocol import (
    Message,
    MessageType,
    Request,
    Response,
    Event,
    MessageRouter,
)
from backend.app.core.collaboration.registry import (
    AgentCapability,
    AgentRegistry,
    AgentStatus,
)
from backend.app.core.collaboration.dispatcher import (
    Task,
    TaskDispatcher,
    DispatchStrategy,
    TaskStatus,
)
from backend.app.core.collaboration.state_sync import (
    StateManager,
    LastWriteWinsStrategy,
    MergeStrategy,
)
from backend.app.core.collaboration.aggregator import (
    ResultAggregator,
    AggregationStrategy,
)
from backend.app.core.collaboration.patterns import (
    PipelinePattern,
    MapReducePattern,
    MasterWorkerPattern,
    PatternContext,
)
from backend.app.core.collaboration.monitor import CollaborationMonitor


class TestProtocol:
    """Tests for communication protocol."""

    @pytest.mark.asyncio
    async def test_message_serialization(self) -> None:
        """Test message serialization and deserialization."""
        msg = Request(
            sender_id="agent1",
            receiver_id="agent2",
            action="process",
            parameters={"data": "test"},
        )

        json_str = msg.to_json()
        restored = Message.from_json(json_str)

        assert restored.sender_id == "agent1"
        assert restored.receiver_id == "agent2"

    @pytest.mark.asyncio
    async def test_message_router(self) -> None:
        """Test message routing."""
        router = MessageRouter()

        received_messages = []

        async def handler(msg: Message) -> None:
            received_messages.append(msg)

        await router.register_handler("agent1", handler)

        msg = Request(
            sender_id="agent2",
            receiver_id="agent1",
            action="test",
        )

        await router.send_message(msg, wait_response=False)
        await asyncio.sleep(0.1)

        assert len(received_messages) == 1
        assert received_messages[0].action == "test"

    @pytest.mark.asyncio
    async def test_request_response_pattern(self) -> None:
        """Test request-response communication pattern."""
        router = MessageRouter()

        async def handler(msg: Message) -> None:
            if isinstance(msg, Request):
                await router.send_response(
                    msg,
                    result={"status": "ok"},
                    status="success",
                )

        await router.register_handler("agent1", handler)

        request = Request(
            sender_id="agent2",
            receiver_id="agent1",
            action="test",
        )

        response = await router.send_message(request, wait_response=True, timeout=5.0)

        assert response is not None
        assert response.status == "success"
        assert response.result == {"status": "ok"}


class TestRegistry:
    """Tests for agent registry."""

    @pytest.mark.asyncio
    async def test_agent_registration(self) -> None:
        """Test agent registration."""
        registry = AgentRegistry()

        agent_info = await registry.register_agent(
            name="test_agent",
            agent_type="processor",
            capabilities=[
                AgentCapability(name="process", description="Process data")
            ],
        )

        assert agent_info.name == "test_agent"
        assert len(agent_info.capabilities) == 1

    @pytest.mark.asyncio
    async def test_find_agents_by_capability(self) -> None:
        """Test finding agents by capability."""
        registry = AgentRegistry()

        await registry.register_agent(
            name="agent1",
            agent_type="processor",
            capabilities=[
                AgentCapability(name="analyze", description="Analyze data")
            ],
        )

        await registry.register_agent(
            name="agent2",
            agent_type="processor",
            capabilities=[
                AgentCapability(name="process", description="Process data")
            ],
        )

        agents = await registry.find_agents_for_capability("analyze")
        assert len(agents) == 1
        assert agents[0].name == "agent1"

    @pytest.mark.asyncio
    async def test_agent_load_management(self) -> None:
        """Test agent load management."""
        registry = AgentRegistry()

        agent_info = await registry.register_agent(
            name="test_agent",
            agent_type="processor",
            capabilities=[],
            max_concurrent_tasks=5,
        )

        await registry.update_agent_load(agent_info.agent_id, 3)
        updated_agent = await registry.get_agent(agent_info.agent_id)

        assert updated_agent.current_load == 3
        assert updated_agent.get_load_percentage() == 60.0


class TestDispatcher:
    """Tests for task dispatcher."""

    @pytest.mark.asyncio
    async def test_task_submission(self) -> None:
        """Test task submission."""
        dispatcher = TaskDispatcher()

        task = await dispatcher.submit_task(
            name="test_task",
            action="process",
            parameters={"data": "test"},
        )

        assert task.name == "test_task"
        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_task_dispatch_strategies(self) -> None:
        """Test different dispatch strategies."""
        agents = {
            "agent1": {"load": 2, "capabilities": ["process"]},
            "agent2": {"load": 1, "capabilities": ["process"]},
            "agent3": {"load": 3, "capabilities": ["analyze"]},
        }

        # Test least-loaded strategy
        dispatcher = TaskDispatcher(strategy=DispatchStrategy.LEAST_LOADED)
        agent_id = dispatcher._dispatch_least_loaded(agents)
        assert agent_id == "agent2"

        # Test round-robin strategy
        dispatcher = TaskDispatcher(strategy=DispatchStrategy.ROUND_ROBIN)
        agent_id1 = dispatcher._dispatch_round_robin(agents)
        agent_id2 = dispatcher._dispatch_round_robin(agents)
        assert agent_id1 != agent_id2

    @pytest.mark.asyncio
    async def test_task_priority_queue(self) -> None:
        """Test task priority queue."""
        dispatcher = TaskDispatcher()

        task1 = await dispatcher.submit_task(
            name="low_priority",
            action="process",
            parameters={},
            priority=1,
        )

        task2 = await dispatcher.submit_task(
            name="high_priority",
            action="process",
            parameters={},
            priority=10,
        )

        next_task = await dispatcher.get_next_task()
        assert next_task.task_id == task2.task_id


class TestStateSync:
    """Tests for state synchronization."""

    @pytest.mark.asyncio
    async def test_state_operations(self) -> None:
        """Test basic state operations."""
        manager = StateManager()

        await manager.set_state("key1", "value1")
        value = await manager.get_state("key1")

        assert value == "value1"

    @pytest.mark.asyncio
    async def test_state_sync(self) -> None:
        """Test state synchronization."""
        manager = StateManager()

        await manager.set_state("key1", "local_value")

        remote_state = {"key1": "remote_value", "key2": "new_value"}
        await manager.sync_state("agent1", remote_state)

        state = await manager.get_full_state()
        assert "key2" in state

    @pytest.mark.asyncio
    async def test_conflict_resolution(self) -> None:
        """Test conflict resolution strategies."""
        strategy = LastWriteWinsStrategy()

        local_state = {"key": {"value": "local", "timestamp": 100}}
        remote_state = {"key": {"value": "remote", "timestamp": 200}}

        resolved = await strategy.resolve(local_state, remote_state, "key")
        assert resolved["value"] == "remote"

    @pytest.mark.asyncio
    async def test_state_snapshots(self) -> None:
        """Test state snapshots."""
        manager = StateManager()

        await manager.set_state("key1", "value1")
        snapshot = await manager.create_snapshot("agent1")

        await manager.set_state("key1", "value2")
        await manager.restore_snapshot(snapshot.snapshot_id)

        value = await manager.get_state("key1")
        assert value == "value1"


class TestAggregator:
    """Tests for result aggregation."""

    @pytest.mark.asyncio
    async def test_partial_result_collection(self) -> None:
        """Test collecting partial results."""
        aggregator = ResultAggregator()

        await aggregator.add_partial_result(
            task_id="task1",
            agent_id="agent1",
            data={"result": "data1"},
        )

        await aggregator.add_partial_result(
            task_id="task1",
            agent_id="agent2",
            data={"result": "data2"},
        )

        partial_results = await aggregator.get_partial_results("task1")
        assert len(partial_results) == 2

    @pytest.mark.asyncio
    async def test_merge_aggregation(self) -> None:
        """Test merge aggregation strategy."""
        aggregator = ResultAggregator(strategy=AggregationStrategy.MERGE)

        await aggregator.add_partial_result(
            task_id="task1",
            agent_id="agent1",
            data={"key1": "value1"},
        )

        await aggregator.add_partial_result(
            task_id="task1",
            agent_id="agent2",
            data={"key2": "value2"},
        )

        result = await aggregator.aggregate_results("task1")
        assert result.final_result["key1"] == "value1"
        assert result.final_result["key2"] == "value2"

    @pytest.mark.asyncio
    async def test_concat_aggregation(self) -> None:
        """Test concatenation aggregation strategy."""
        aggregator = ResultAggregator(strategy=AggregationStrategy.CONCAT)

        await aggregator.add_partial_result(
            task_id="task1",
            agent_id="agent1",
            data=[1, 2, 3],
        )

        await aggregator.add_partial_result(
            task_id="task1",
            agent_id="agent2",
            data=[4, 5, 6],
        )

        result = await aggregator.aggregate_results("task1")
        assert len(result.final_result) == 6


class TestPatterns:
    """Tests for collaboration patterns."""

    @pytest.mark.asyncio
    async def test_pipeline_pattern(self) -> None:
        """Test pipeline pattern."""

        class MockAgent:
            def __init__(self, name: str) -> None:
                self.name = name

            async def process(self, data: Any) -> Any:
                return {"processed_by": self.name, "data": data}

        agents = {
            "agent1": MockAgent("agent1"),
            "agent2": MockAgent("agent2"),
        }

        pattern = PipelinePattern(["agent1", "agent2"])
        context = PatternContext(
            pattern_id="test",
            agents=agents,
            initial_data={"input": "test"},
        )

        result = await pattern.execute(context)
        assert "processed_by" in result

    @pytest.mark.asyncio
    async def test_mapreduce_pattern(self) -> None:
        """Test MapReduce pattern."""

        class MockAgent:
            def __init__(self, name: str) -> None:
                self.name = name

            async def process(self, data: Any) -> Any:
                return {self.name: data}

        agents = {
            "agent1": MockAgent("agent1"),
            "agent2": MockAgent("agent2"),
        }

        pattern = MapReducePattern(["agent1", "agent2"])
        context = PatternContext(
            pattern_id="test",
            agents=agents,
            initial_data={"input": "test"},
        )

        result = await pattern.execute(context)
        assert "agent1" in result or "agent2" in result


class TestMonitor:
    """Tests for collaboration monitoring."""

    @pytest.mark.asyncio
    async def test_task_metrics(self) -> None:
        """Test task metrics tracking."""
        monitor = CollaborationMonitor()

        await monitor.start_collaboration()
        metrics = await monitor.start_task("task1", "agent1")

        await asyncio.sleep(0.1)
        await monitor.end_task("task1", status="completed")

        task_metrics = await monitor.get_task_metrics("task1")
        assert task_metrics.status == "completed"
        assert task_metrics.duration > 0

    @pytest.mark.asyncio
    async def test_agent_metrics(self) -> None:
        """Test agent metrics tracking."""
        monitor = CollaborationMonitor()

        await monitor.start_collaboration()

        for i in range(3):
            await monitor.start_task(f"task{i}", "agent1")
            await monitor.end_task(f"task{i}", status="completed")

        agent_metrics = await monitor.get_agent_metrics("agent1")
        assert agent_metrics.total_tasks == 3
        assert agent_metrics.completed_tasks == 3

    @pytest.mark.asyncio
    async def test_performance_summary(self) -> None:
        """Test performance summary."""
        monitor = CollaborationMonitor()

        await monitor.start_collaboration()

        await monitor.start_task("task1", "agent1")
        await monitor.end_task("task1", status="completed")

        await monitor.end_collaboration()

        summary = await monitor.get_performance_summary()
        assert summary["total_tasks"] == 1
        assert summary["completed_tasks"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
