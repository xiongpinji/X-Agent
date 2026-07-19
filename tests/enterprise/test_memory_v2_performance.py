"""Memory V2 - Performance Tests and Benchmarks"""

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from backend.app.core.memory_v2_system import (
    MemoryCategory,
    MemoryTier,
    MemoryV2Item,
    MemoryV2System,
)
from backend.app.core.memory_v2_skill import SkillMemoryLayer, SkillExample
from backend.app.core.memory_v2_nudge import NudgeMemoryLayer, NudgeConfig


pytestmark = pytest.mark.skipif(
    os.environ.get("XAGENT_PERFORMANCE_TESTS") != "1",
    reason="performance tests are opt-in: set XAGENT_PERFORMANCE_TESTS=1",
)


class TestMemoryV2Performance:
    """Performance tests for Memory V2 system."""

    @pytest.fixture
    def memory_system(self):
        """Create memory system instance."""
        return MemoryV2System()

    @pytest.fixture
    def skill_layer(self):
        """Create skill memory layer."""
        return SkillMemoryLayer()

    @pytest.fixture
    def nudge_layer(self):
        """Create nudge memory layer."""
        return NudgeMemoryLayer()

    @pytest.mark.asyncio
    async def test_store_performance(self, memory_system):
        """Test memory storage performance."""

        tenant_id = "test-tenant"
        iterations = 1000

        start_time = time.time()

        for i in range(iterations):
            await memory_system.store(
                content=f"Test memory {i}",
                tenant_id=tenant_id,
                category=MemoryCategory.REFERENCE,
            )

        elapsed = time.time() - start_time
        avg_time_ms = (elapsed / iterations) * 1000

        print(f"\nStore Performance:")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Average per item: {avg_time_ms:.2f}ms")
        print(f"  Throughput: {iterations / elapsed:.0f} items/sec")

        # Performance target: <5ms per item
        assert avg_time_ms < 5.0, f"Store too slow: {avg_time_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_retrieve_performance(self, memory_system):
        """Test memory retrieval performance."""

        tenant_id = "test-tenant"
        memory_ids = []

        # Store test data
        for i in range(100):
            memory_id = await memory_system.store(
                content=f"Test memory {i}",
                tenant_id=tenant_id,
            )
            memory_ids.append(memory_id)

        # Measure retrieval
        iterations = 1000
        start_time = time.time()

        for i in range(iterations):
            memory_id = memory_ids[i % len(memory_ids)]
            await memory_system.retrieve(memory_id, tenant_id)

        elapsed = time.time() - start_time
        avg_time_ms = (elapsed / iterations) * 1000

        print(f"\nRetrieve Performance:")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Average per item: {avg_time_ms:.2f}ms")
        print(f"  Throughput: {iterations / elapsed:.0f} items/sec")

        # Performance target: <2ms per item
        assert avg_time_ms < 2.0, f"Retrieve too slow: {avg_time_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_search_performance(self, memory_system):
        """Test memory search performance."""

        tenant_id = "test-tenant"

        # Store test data
        for i in range(500):
            await memory_system.store(
                content=f"Memory about Python programming {i}",
                tenant_id=tenant_id,
                tags=["python", "programming"],
            )

        # Measure search
        iterations = 100
        start_time = time.time()

        for i in range(iterations):
            await memory_system.search(
                query="Python programming",
                tenant_id=tenant_id,
                limit=10,
            )

        elapsed = time.time() - start_time
        avg_time_ms = (elapsed / iterations) * 1000

        print(f"\nSearch Performance:")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Average per search: {avg_time_ms:.2f}ms")
        print(f"  Throughput: {iterations / elapsed:.0f} searches/sec")

        # Performance target: <50ms per search
        assert avg_time_ms < 50.0, f"Search too slow: {avg_time_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_consolidation_performance(self, memory_system, nudge_layer):
        """Test consolidation performance."""

        tenant_id = "test-tenant"
        nudge_layer.memory_system = memory_system

        # Store test data
        for i in range(200):
            await memory_system.store(
                content=f"Test memory {i}",
                tenant_id=tenant_id,
                importance=0.5 + (i % 10) * 0.05,
            )

        # Measure consolidation
        start_time = time.time()
        result = await nudge_layer.consolidate(tenant_id, batch_size=50)
        elapsed = time.time() - start_time

        print(f"\nConsolidation Performance:")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Consolidated: {result.get('consolidated', 0)} items")
        print(f"  Time per item: {(elapsed / result.get('consolidated', 1)) * 1000:.2f}ms")

        # Performance target: <100ms for 50 items
        assert elapsed < 1.0, f"Consolidation too slow: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_deduplication_performance(self, memory_system, nudge_layer):
        """Test deduplication performance."""

        tenant_id = "test-tenant"
        nudge_layer.memory_system = memory_system

        # Store test data with duplicates
        for i in range(100):
            content = f"Test memory {i % 10}"  # Create duplicates
            await memory_system.store(
                content=content,
                tenant_id=tenant_id,
            )

        # Measure deduplication
        start_time = time.time()
        result = await nudge_layer.deduplicate(tenant_id)
        elapsed = time.time() - start_time

        print(f"\nDeduplication Performance:")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Deduplicated: {result.get('deduplicated', 0)} items")

        # Performance target: <500ms for 100 items
        assert elapsed < 0.5, f"Deduplication too slow: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_skill_generation_performance(self, skill_layer):
        """Test skill memory generation performance."""

        iterations = 100
        start_time = time.time()

        for i in range(iterations):
            execution_result = {
                "description": f"Test skill {i}",
                "parameters": {"param1": "value1"},
                "returns": {"result": "value"},
                "examples": [
                    {
                        "title": "Example 1",
                        "input": {"x": 1},
                        "output": {"y": 2},
                    }
                ],
            }

            await skill_layer.generate_from_execution(
                agent_id="agent-1",
                execution_result=execution_result,
                skill_name=f"skill_{i}",
            )

        elapsed = time.time() - start_time
        avg_time_ms = (elapsed / iterations) * 1000

        print(f"\nSkill Generation Performance:")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Average per skill: {avg_time_ms:.2f}ms")

        # Performance target: <10ms per skill
        assert avg_time_ms < 10.0, f"Skill generation too slow: {avg_time_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_cache_hit_rate(self, memory_system):
        """Test cache hit rate."""

        tenant_id = "test-tenant"
        memory_ids = []

        # Store test data
        for i in range(50):
            memory_id = await memory_system.store(
                content=f"Test memory {i}",
                tenant_id=tenant_id,
            )
            memory_ids.append(memory_id)

        # Warm up cache
        for memory_id in memory_ids[:10]:
            await memory_system.retrieve(memory_id, tenant_id)

        # Measure cache hits
        cache_hits = 0
        cache_misses = 0

        for i in range(1000):
            memory_id = memory_ids[i % len(memory_ids)]
            result = await memory_system.retrieve(memory_id, tenant_id)

            if memory_id in memory_system._cache:
                cache_hits += 1
            else:
                cache_misses += 1

        hit_rate = cache_hits / (cache_hits + cache_misses)

        print(f"\nCache Performance:")
        print(f"  Cache hits: {cache_hits}")
        print(f"  Cache misses: {cache_misses}")
        print(f"  Hit rate: {hit_rate * 100:.1f}%")

        # Performance target: >80% hit rate
        assert hit_rate > 0.8, f"Cache hit rate too low: {hit_rate * 100:.1f}%"

    @pytest.mark.asyncio
    async def test_memory_scaling(self, memory_system):
        """Test memory system scaling with large datasets."""

        tenant_id = "test-tenant"
        sizes = [100, 500, 1000, 5000]

        print(f"\nMemory Scaling Test:")

        for size in sizes:
            # Clear previous data
            memory_system._memories.clear()
            memory_system._tier_index = {tier: [] for tier in MemoryTier}

            # Store data
            start_time = time.time()
            for i in range(size):
                await memory_system.store(
                    content=f"Test memory {i}",
                    tenant_id=tenant_id,
                )
            store_time = time.time() - start_time

            # Search
            start_time = time.time()
            results = await memory_system.search(
                query="Test memory",
                tenant_id=tenant_id,
                limit=10,
            )
            search_time = time.time() - start_time

            print(f"  Size: {size}")
            print(f"    Store time: {store_time:.2f}s")
            print(f"    Search time: {search_time * 1000:.2f}ms")
            print(f"    Results: {len(results)}")

    def test_importance_scoring(self, memory_system):
        """Test importance scoring algorithm."""

        memory = MemoryV2Item(
            tenant_id="test",
            content="Test content",
            access_count=50,
            last_accessed=datetime.now(UTC),
            metadata={
                "starred": True,
                "total_executions": 10,
                "successful_executions": 9,
            },
        )

        # Calculate importance
        importance = asyncio.run(memory_system._calculate_importance(memory))

        print(f"\nImportance Scoring:")
        print(f"  Access count: {memory.access_count}")
        print(f"  Starred: {memory.metadata.get('starred')}")
        print(f"  Success rate: {9/10}")
        print(f"  Calculated importance: {importance:.2f}")

        # Should be relatively high
        assert importance > 0.5, f"Importance too low: {importance:.2f}"

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, memory_system):
        """Test concurrent memory operations."""

        tenant_id = "test-tenant"

        async def store_task(i):
            return await memory_system.store(
                content=f"Concurrent memory {i}",
                tenant_id=tenant_id,
            )

        async def retrieve_task(memory_id):
            return await memory_system.retrieve(memory_id, tenant_id)

        # Store concurrently
        start_time = time.time()
        store_tasks = [store_task(i) for i in range(100)]
        memory_ids = await asyncio.gather(*store_tasks)
        store_time = time.time() - start_time

        # Retrieve concurrently
        start_time = time.time()
        retrieve_tasks = [retrieve_task(mid) for mid in memory_ids]
        results = await asyncio.gather(*retrieve_tasks)
        retrieve_time = time.time() - start_time

        print(f"\nConcurrent Operations:")
        print(f"  Concurrent stores (100): {store_time:.2f}s")
        print(f"  Concurrent retrieves (100): {retrieve_time:.2f}s")
        print(f"  Successful retrieves: {len([r for r in results if r])}")

        assert len([r for r in results if r]) == 100


class TestMemoryV2Integration:
    """Integration tests for Memory V2 system."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow: store, search, consolidate, deduplicate."""

        memory_system = MemoryV2System()
        skill_layer = SkillMemoryLayer()
        nudge_layer = NudgeMemoryLayer()
        nudge_layer.memory_system = memory_system

        tenant_id = "test-tenant"

        # 1. Store memories
        memory_ids = []
        for i in range(50):
            memory_id = await memory_system.store(
                content=f"Memory about Python {i}",
                tenant_id=tenant_id,
                category=MemoryCategory.REFERENCE,
                importance=0.5 + (i % 10) * 0.05,
            )
            memory_ids.append(memory_id)

        # 2. Search
        results = await memory_system.search(
            query="Python",
            tenant_id=tenant_id,
            limit=10,
        )
        assert len(results) > 0

        # 3. Generate skill
        skill = await skill_layer.generate_from_execution(
            agent_id="agent-1",
            execution_result={
                "description": "Python programming skill",
                "parameters": {"code": "str"},
                "returns": {"result": "str"},
            },
            skill_name="python_skill",
        )
        assert skill is not None

        # 4. Consolidate
        consolidation_result = await nudge_layer.consolidate(tenant_id)
        assert consolidation_result["consolidated"] > 0

        # 5. Deduplicate
        dedup_result = await nudge_layer.deduplicate(tenant_id)
        assert "deduplicated" in dedup_result

        print(f"\nFull Workflow Test:")
        print(f"  Stored: {len(memory_ids)} memories")
        print(f"  Search results: {len(results)}")
        print(f"  Consolidated: {consolidation_result['consolidated']}")
        print(f"  Deduplicated: {dedup_result.get('deduplicated', 0)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
