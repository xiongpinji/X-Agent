"""
Tests for multi-agent functionality.

Tests agent spawning, communication, coordination, and recovery.
"""

import pytest
import asyncio
from datetime import datetime, UTC

from backend.app.core.agent_spawner import (
    agent_spawner,
    AgentStatus,
    IsolationLevel,
)
from backend.app.core.agent_coordinator import (
    agent_coordinator,
    CoordinationStrategy,
)
from backend.app.core.parallel_executor import (
    parallel_executor,
    Task,
    TaskStatus,
)
from backend.app.core.agent_recovery import (
    agent_recovery,
    RecoveryStrategy,
    FailureType,
)


@pytest.mark.asyncio
async def test_spawn_agent():
    """Test spawning a single agent."""
    agent_id = await agent_spawner.spawn_agent(
        agent_type="test",
        task="test task",
        context={"key": "value"},
    )

    assert agent_id.startswith("agent_")
    assert agent_id in agent_spawner.agents

    status = await agent_spawner.get_agent_status(agent_id)
    assert status is not None
    assert status["agent_id"] == agent_id
    assert status["status"] in ["initializing", "ready", "running"]


@pytest.mark.asyncio
async def test_spawn_multiple_agents():
    """Test spawning multiple agents."""
    agent_ids = []

    for i in range(3):
        agent_id = await agent_spawner.spawn_agent(
            agent_type="test",
            task=f"task {i}",
            context={"index": i},
        )
        agent_ids.append(agent_id)

    assert len(agent_ids) == 3
    assert len(set(agent_ids)) == 3  # All unique

    agents = await agent_spawner.list_agents()
    assert len(agents) >= 3


@pytest.mark.asyncio
async def test_terminate_agent():
    """Test terminating an agent."""
    agent_id = await agent_spawner.spawn_agent(
        agent_type="test",
        task="test task",
        context={},
    )

    success = await agent_spawner.terminate_agent(agent_id)
    assert success

    status = await agent_spawner.get_agent_status(agent_id)
    assert status["status"] == "terminated"


@pytest.mark.asyncio
async def test_agent_max_concurrent_limit():
    """Test max concurrent agents limit."""
    spawner = agent_spawner.__class__(max_concurrent_agents=2)

    # Spawn 2 agents
    agent_id_1 = await spawner.spawn_agent(
        agent_type="test",
        task="task 1",
        context={},
    )
    agent_id_2 = await spawner.spawn_agent(
        agent_type="test",
        task="task 2",
        context={},
    )

    # Third should fail
    with pytest.raises(RuntimeError):
        await spawner.spawn_agent(
            agent_type="test",
            task="task 3",
            context={},
        )


@pytest.mark.asyncio
async def test_parallel_task_execution():
    """Test parallel task execution."""
    async def dummy_task_1():
        await asyncio.sleep(0.01)
        return "result 1"

    async def dummy_task_2():
        await asyncio.sleep(0.01)
        return "result 2"

    async def dummy_task_3():
        await asyncio.sleep(0.01)
        return "result 3"

    tasks = [
        Task(task_id="task_1", name="task 1", coroutine=dummy_task_1),
        Task(task_id="task_2", name="task 2", coroutine=dummy_task_2),
        Task(task_id="task_3", name="task 3", coroutine=dummy_task_3),
    ]

    results = await parallel_executor.execute_parallel(tasks, max_concurrent=2)

    assert len(results) == 3
    assert all(r.status == TaskStatus.COMPLETED for r in results)
    assert results[0].result == "result 1"


@pytest.mark.asyncio
async def test_task_with_dependencies():
    """Test task execution with dependencies."""
    async def task_a():
        return "A"

    async def task_b():
        return "B"

    async def task_c():
        return "C"

    tasks = [
        Task(task_id="a", name="task A", coroutine=task_a),
        Task(task_id="b", name="task B", coroutine=task_b),
        Task(task_id="c", name="task C", coroutine=task_c),
    ]

    dependencies = {
        "b": ["a"],  # B depends on A
        "c": ["a", "b"],  # C depends on A and B
    }

    results = await parallel_executor.execute_with_dependencies(
        tasks,
        dependencies,
    )

    assert len(results) == 3
    assert all(r.status == TaskStatus.COMPLETED for r in results)


@pytest.mark.asyncio
async def test_task_retry():
    """Test task retry on failure."""
    attempt_count = 0

    async def failing_task():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise ValueError("First attempt fails")
        return "success"

    task = Task(
        task_id="retry_task",
        name="retry task",
        coroutine=failing_task,
        retry_count=2,
    )

    results = await parallel_executor.execute_parallel([task])

    assert len(results) == 1
    assert results[0].status == TaskStatus.COMPLETED
    assert results[0].attempts == 2


class _StubCodeIndex:
    """空调用代码索引：协调策略测试不关心代码索引内容。"""

    def index(self, root=".", limit=2000):
        return {"root": str(root), "count": 0, "files": []}

    def related_files(self, query, limit=10):
        return []

    def impact_hints(self, path, limit=10):
        return []

    def test_files_for(self, query, limit=10):
        return []


@pytest.fixture
def stub_code_index(monkeypatch):
    # 真实 code_index.index(".") 会 rglob 整个项目根（含 venv/.git）并 sorted 全量物化，
    # 实测 >120s，触发 pytest-timeout(thread) 崩掉整个会话。协调测试只需打桩。
    monkeypatch.setattr(
        "backend.app.core.agent.loop.code_index", _StubCodeIndex()
    )


@pytest.mark.asyncio
async def test_agent_coordinator_parallel(stub_code_index):
    """Test agent coordination with parallel strategy."""
    # Create mock agents
    class MockAgent:
        def __init__(self, agent_id):
            self.agent_id = agent_id

    agents = [MockAgent(f"agent_{i}") for i in range(3)]

    result = await agent_coordinator.coordinate_agents(
        agents,
        strategy=CoordinationStrategy.PARALLEL,
        task="test task",
    )

    assert result.strategy == CoordinationStrategy.PARALLEL
    assert len(result.agent_results) == 3


@pytest.mark.asyncio
async def test_agent_coordinator_sequential(stub_code_index):
    """Test agent coordination with sequential strategy."""
    class MockAgent:
        def __init__(self, agent_id):
            self.agent_id = agent_id

    agents = [MockAgent(f"agent_{i}") for i in range(3)]

    result = await agent_coordinator.coordinate_agents(
        agents,
        strategy=CoordinationStrategy.SEQUENTIAL,
        task="test task",
    )

    assert result.strategy == CoordinationStrategy.SEQUENTIAL
    assert len(result.agent_results) == 3


@pytest.mark.asyncio
async def test_agent_recovery_retry():
    """Test agent recovery with retry strategy."""
    class MockAgent:
        def __init__(self):
            self.status = "failed"
            self.error = "Test error"

    agent = MockAgent()
    agent_recovery.register_agent("test_agent", agent)

    success = await agent_recovery.recover_agent(
        "test_agent",
        strategy=RecoveryStrategy.RETRY,
        max_retries=1,
    )

    # Should attempt recovery
    assert isinstance(success, bool)


@pytest.mark.asyncio
async def test_agent_failure_detection():
    """Test agent failure detection."""
    class MockAgent:
        def __init__(self):
            self.status = "failed"
            self.error = "Test error"

    agent = MockAgent()
    agent_recovery.register_agent("test_agent", agent)

    failure = await agent_recovery.detect_failure("test_agent", agent)

    assert failure is not None
    assert failure.failure_type == FailureType.CRASH


@pytest.mark.asyncio
async def test_agent_spawner_stats():
    """Test agent spawner statistics."""
    stats = agent_spawner.get_stats()

    assert "total_agents" in stats
    assert "active_agents" in stats
    assert "status_breakdown" in stats
    assert "max_concurrent" in stats


@pytest.mark.asyncio
async def test_parallel_executor_stats():
    """Test parallel executor statistics."""
    async def dummy_task():
        return "result"

    tasks = [
        Task(task_id="task_1", name="task 1", coroutine=dummy_task),
        Task(task_id="task_2", name="task 2", coroutine=dummy_task),
    ]

    results = await parallel_executor.execute_parallel(tasks)
    stats = parallel_executor.get_execution_stats(results)

    assert stats["total_tasks"] == 2
    assert stats["completed"] == 2
    assert stats["failed"] == 0
    assert stats["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_agent_cleanup():
    """Test cleanup of completed agents."""
    agent_id = await agent_spawner.spawn_agent(
        agent_type="test",
        task="test task",
        context={},
    )

    # Wait for completion
    await asyncio.sleep(0.2)

    # Cleanup
    cleaned = await agent_spawner.cleanup_completed_agents(max_age_seconds=0)

    assert cleaned >= 0


@pytest.mark.asyncio
async def test_coordination_history(stub_code_index):
    """Test coordination history tracking."""
    class MockAgent:
        def __init__(self, agent_id):
            self.agent_id = agent_id

    agents = [MockAgent(f"agent_{i}") for i in range(2)]

    await agent_coordinator.coordinate_agents(
        agents,
        strategy=CoordinationStrategy.PARALLEL,
    )

    history = agent_coordinator.get_coordination_history(limit=10)

    assert len(history) >= 1


@pytest.mark.asyncio
async def test_recovery_stats():
    """Test recovery statistics."""
    stats = agent_recovery.get_recovery_stats()

    assert "total_failures" in stats
    assert "monitored_agents" in stats
    assert "failure_types" in stats
