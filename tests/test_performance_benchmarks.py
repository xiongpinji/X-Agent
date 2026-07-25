"""Performance benchmarks for Phase 3 features."""

import asyncio
import time
import pytest
from typing import List

# P1-09: agent_collaboration 已归档至 archive/dead_code_2026-07-20/
pytest.importorskip(
    "backend.app.core.agent_collaboration",
    reason="agent_collaboration archived (P1-09)",
)

from backend.app.core.memory_fusion import Memory, MemoryFusion
from backend.app.core.agent_collaboration import AgentCollaboration, AgentMessage, MessageType
from backend.app.services.browser.enhanced_automation import EnhancedBrowserAutomation
from backend.app.core.advanced_repair_loop import AdvancedRepairLoop


class BenchmarkMemoryFusion:
    """Benchmarks for memory fusion system."""

    @pytest.mark.asyncio
    async def test_add_memory_performance(self, benchmark):
        """Benchmark memory addition."""
        fusion = MemoryFusion()

        async def add_memories():
            for i in range(100):
                memory = Memory(id=f"mem_{i}", content=f"Memory content {i}")
                await fusion.add_memory(memory)

        # Run benchmark
        result = benchmark(asyncio.run, add_memories)

    @pytest.mark.asyncio
    async def test_deduplicate_performance(self, benchmark):
        """Benchmark deduplication."""
        fusion = MemoryFusion()

        # Prepare memories
        memories = []
        for i in range(100):
            memory = Memory(id=f"mem_{i}", content=f"Memory content {i}")
            await fusion.add_memory(memory)
            memories.append(memory)

        async def deduplicate():
            return await fusion.deduplicate(memories)

        # Run benchmark
        result = benchmark(asyncio.run, deduplicate)

    @pytest.mark.asyncio
    async def test_compress_performance(self, benchmark):
        """Benchmark compression."""
        fusion = MemoryFusion()

        # Prepare memories
        memories = []
        for i in range(100):
            memory = Memory(id=f"mem_{i}", content=f"Memory content {i}", importance=0.5)
            await fusion.add_memory(memory)
            memories.append(memory)

        async def compress():
            return await fusion.compress_memories(memories)

        # Run benchmark
        result = benchmark(asyncio.run, compress)

    @pytest.mark.asyncio
    async def test_associate_performance(self, benchmark):
        """Benchmark memory association."""
        fusion = MemoryFusion()

        # Prepare memories
        for i in range(100):
            memory = Memory(id=f"mem_{i}", content=f"Memory content {i}")
            await fusion.add_memory(memory)

        query = Memory(id="query", content="Memory content 50")

        async def associate():
            return await fusion.associate_memories(query)

        # Run benchmark
        result = benchmark(asyncio.run, associate)


class BenchmarkAgentCollaboration:
    """Benchmarks for agent collaboration system."""

    @pytest.mark.asyncio
    async def test_message_send_performance(self, benchmark):
        """Benchmark message sending."""
        from unittest.mock import AsyncMock, patch

        collab = AgentCollaboration()

        with patch("redis.asyncio.from_url", new_callable=AsyncMock):
            collab.redis = AsyncMock()
            collab.redis.lpush = AsyncMock()
            collab.redis.expire = AsyncMock()
            collab.redis.publish = AsyncMock()

            async def send_messages():
                for i in range(100):
                    message = AgentMessage(
                        from_agent="agent_1",
                        to_agent="agent_2",
                        message_type=MessageType.TASK_REQUEST,
                        payload={"task": f"task_{i}"},
                    )
                    await collab.send_message(message)

            # Run benchmark
            result = benchmark(asyncio.run, send_messages)

    @pytest.mark.asyncio
    async def test_agent_registration_performance(self, benchmark):
        """Benchmark agent registration."""
        from unittest.mock import AsyncMock, patch

        collab = AgentCollaboration()

        with patch("redis.asyncio.from_url", new_callable=AsyncMock):
            collab.redis = AsyncMock()
            collab.redis.hset = AsyncMock()
            collab.redis.delete = AsyncMock()

            async def register_agents():
                for i in range(50):
                    await collab.register_agent(f"agent_{i}", capacity=10)

            # Run benchmark
            result = benchmark(asyncio.run, register_agents)


class BenchmarkBrowserAutomation:
    """Benchmarks for browser automation."""

    @pytest.mark.asyncio
    async def test_session_creation_performance(self, benchmark):
        """Benchmark session creation."""
        from unittest.mock import AsyncMock

        automation = EnhancedBrowserAutomation()

        async def create_sessions():
            for i in range(10):
                mock_browser = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()

                await automation.create_session(
                    f"session_{i}",
                    mock_browser,
                    mock_context,
                    mock_page,
                )

        # Run benchmark
        result = benchmark(asyncio.run, create_sessions)

    @pytest.mark.asyncio
    async def test_element_finding_performance(self, benchmark):
        """Benchmark element finding."""
        from unittest.mock import AsyncMock, Mock

        automation = EnhancedBrowserAutomation()

        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_page.locator = Mock(return_value=mock_locator)

        session = await automation.create_session(
            "session_1",
            AsyncMock(),
            AsyncMock(),
            mock_page,
        )

        async def find_elements():
            for i in range(100):
                await automation.find_element(
                    "session_1",
                    f".selector_{i}",
                )

        # Run benchmark
        result = benchmark(asyncio.run, find_elements)


class BenchmarkRepairLoop:
    """Benchmarks for repair loop."""

    @pytest.mark.asyncio
    async def test_failure_analysis_performance(self, benchmark):
        """Benchmark failure analysis."""
        repair = AdvancedRepairLoop()

        async def analyze_failures():
            for i in range(100):
                error = Exception(f"Error {i}")
                await repair.analyze_failure(error)

        # Run benchmark
        result = benchmark(asyncio.run, analyze_failures)

    @pytest.mark.asyncio
    async def test_repair_suggestion_performance(self, benchmark):
        """Benchmark repair suggestion."""
        from backend.app.core.advanced_repair_loop import FailureRecord, FailureCategory

        repair = AdvancedRepairLoop()

        async def suggest_repairs():
            for i in range(100):
                failure = FailureRecord(
                    id=f"failure_{i}",
                    error_message=f"Error {i}",
                    error_type="TimeoutError",
                    category=FailureCategory.TIMEOUT,
                )
                await repair.suggest_repair(failure)

        # Run benchmark
        result = benchmark(asyncio.run, suggest_repairs)


# Performance test functions

@pytest.mark.asyncio
async def test_memory_fusion_throughput():
    """Test memory fusion throughput."""
    fusion = MemoryFusion()

    start_time = time.time()
    memory_count = 1000

    for i in range(memory_count):
        memory = Memory(id=f"mem_{i}", content=f"Memory {i}")
        await fusion.add_memory(memory)

    elapsed = time.time() - start_time
    throughput = memory_count / elapsed

    print(f"\nMemory Fusion Throughput: {throughput:.2f} memories/sec")
    # Conservative floor: under 16-worker xdist contention raw throughput
    # varies widely; assert the path completes at a sane rate, not a CI-specific peak.
    assert throughput > 10, f"Throughput too low: {throughput}"


@pytest.mark.asyncio
async def test_deduplication_performance():
    """Test deduplication performance."""
    fusion = MemoryFusion()

    # Create similar memories
    memories = []
    for i in range(100):
        memory = Memory(
            id=f"mem_{i}",
            content="The quick brown fox jumps over the lazy dog" if i % 2 == 0 else "The quick brown fox jumps over a lazy dog",
        )
        await fusion.add_memory(memory)
        memories.append(memory)

    start_time = time.time()
    unique = await fusion.deduplicate(memories)
    elapsed = time.time() - start_time

    print(f"\nDeduplication Time: {elapsed:.3f}s for {len(memories)} memories")
    print(f"Reduction: {len(memories)} -> {len(unique)}")
    assert elapsed < 5.0, f"Deduplication too slow: {elapsed}s"


@pytest.mark.asyncio
async def test_agent_task_assignment_performance():
    """Test agent task assignment performance."""
    from unittest.mock import AsyncMock, patch

    collab = AgentCollaboration()

    with patch("redis.asyncio.from_url", new_callable=AsyncMock):
        collab.redis = AsyncMock()
        collab.redis.hset = AsyncMock()
        collab.redis.delete = AsyncMock()
        collab.redis.lpush = AsyncMock()
        collab.redis.expire = AsyncMock()
        collab.redis.publish = AsyncMock()
        collab.redis.hgetall = AsyncMock(return_value={})

        # Register agents
        for i in range(10):
            await collab.register_agent(f"agent_{i}", capacity=10)

        start_time = time.time()
        task_count = 100

        for i in range(task_count):
            await collab.assign_task({"task_id": i}, priority=i % 3)

        elapsed = time.time() - start_time
        throughput = task_count / elapsed

        print(f"\nTask Assignment Throughput: {throughput:.2f} tasks/sec")
        assert throughput > 10, f"Throughput too low: {throughput}"


@pytest.mark.asyncio
async def test_repair_loop_performance():
    """Test repair loop performance."""
    from backend.app.core.advanced_repair_loop import FailureRecord, FailureCategory

    repair = AdvancedRepairLoop(learning_enabled=True)

    start_time = time.time()
    failure_count = 100

    for i in range(failure_count):
        failure = FailureRecord(
            id=f"failure_{i}",
            error_message=f"Error {i}",
            error_type="TimeoutError" if i % 2 == 0 else "ConnectionError",
            category=FailureCategory.TIMEOUT if i % 2 == 0 else FailureCategory.TRANSIENT,
        )
        await repair.suggest_repair(failure)

    elapsed = time.time() - start_time
    throughput = failure_count / elapsed

    print(f"\nRepair Suggestion Throughput: {throughput:.2f} failures/sec")
    assert throughput > 10, f"Throughput too low: {throughput}"


# Stress tests

@pytest.mark.asyncio
async def test_memory_fusion_stress():
    """Stress test memory fusion with large dataset."""
    fusion = MemoryFusion()

    # Add 10000 memories
    for i in range(10000):
        memory = Memory(
            id=f"mem_{i}",
            content=f"Memory content {i % 100}",  # Repeat content to test deduplication
            importance=0.5 + (i % 10) * 0.05,
        )
        await fusion.add_memory(memory)

    stats = fusion.get_memory_stats()
    print(f"\nMemory Fusion Stress Test Stats: {stats}")
    assert stats["total_memories"] == 10000


@pytest.mark.asyncio
async def test_agent_collaboration_stress():
    """Stress test agent collaboration with many agents."""
    from unittest.mock import AsyncMock, patch

    collab = AgentCollaboration()

    with patch("redis.asyncio.from_url", new_callable=AsyncMock):
        _store: dict[str, dict[str, str]] = {}

        async def _hset(key, field, value):
            _store.setdefault(key, {})[field] = value

        async def _hgetall(key):
            return _store.get(key, {})

        collab.redis = AsyncMock()
        collab.redis.hset = AsyncMock(side_effect=_hset)
        collab.redis.hgetall = AsyncMock(side_effect=_hgetall)
        collab.redis.delete = AsyncMock()

        # Register 100 agents
        for i in range(100):
            await collab.register_agent(f"agent_{i}", capacity=10)

        stats = await collab.get_agent_stats()
        print(f"\nAgent Collaboration Stress Test Stats: {stats}")
        assert stats["total_agents"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
