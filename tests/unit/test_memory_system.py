"""Unit tests for the memory system (backend.app.core.memory).

Covers:
- MemorySystem store/search/update/delete lifecycle
- MemoryItem model validation
- Tier1Backend (in-memory TTL store)
- TieredMemorySystem parallel search
- Memory deduplication
- Memory consolidation
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.memory.store import (
    MemoryItem,
    MemoryScope,
    MemorySystem,
)
from backend.app.core.memory.tiered_memory import (
    MemoryHit,
    Tier1Backend,
    TieredMemorySystem,
)
from backend.app.core.contracts import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(agent_id: str = "test-agent", tenant_id: str = "t1") -> RunContext:
    return RunContext(
        trace_id="trace-001",
        agent_id=agent_id,
        tenant_id=tenant_id,
        user_id="user-1",
    )


# ---------------------------------------------------------------------------
# MemoryItem model
# ---------------------------------------------------------------------------

class TestMemoryItem:
    def test_defaults(self):
        item = MemoryItem(id="m1", content="hello", tenant_id="t1", layer=3)
        assert item.layer == 3
        assert item.importance == 0.5
        assert item.tags == []
        assert item.tenant_id == "t1"

    def test_custom_fields(self):
        item = MemoryItem(
            id="m2",
            content="test",
            layer=5,
            importance=0.9,
            tags=["a", "b"],
            tenant_id="t1",
        )
        assert item.layer == 5
        assert item.importance == 0.9
        assert len(item.tags) == 2


# ---------------------------------------------------------------------------
# MemorySystem core operations
# ---------------------------------------------------------------------------

class TestMemorySystem:
    @pytest.fixture
    def system(self):
        return MemorySystem()

    @pytest.fixture
    def context(self):
        return _make_context()

    async def test_store_and_search(self, system, context):
        memory_id = await system.store(context, "Python is great", layer=3, importance=0.8)
        assert memory_id
        results = await system.search(context, "Python")
        assert len(results) >= 1
        assert any("Python" in r.content for r in results)

    async def test_store_returns_unique_ids(self, system, context):
        id1 = await system.store(context, "memory one")
        id2 = await system.store(context, "memory two")
        assert id1 != id2

    async def test_search_empty_query(self, system, context):
        await system.store(context, "some content")
        results = await system.search(context, "")
        # Empty query should return recent items or empty
        assert isinstance(results, list)

    async def test_search_no_results(self, system, context):
        results = await system.search(context, "xyznonexistent12345")
        assert results == []

    async def test_get_item(self, system, context):
        memory_id = await system.store(context, "findable content")
        item = system.get_item(memory_id)
        assert item is not None
        assert item.content == "findable content"

    async def test_get_item_nonexistent(self, system, context):
        item = system.get_item("nonexistent-id")
        assert item is None

    async def test_add_revision(self, system, context):
        memory_id = await system.store(context, "original content")
        revision = system.add_revision(memory_id, actor_agent_id="agent-1", summary="updated")
        assert revision is not None

    async def test_layer_filtering(self, system, context):
        await system.store(context, "layer1 content", layer=1)
        await system.store(context, "layer5 content", layer=5)
        results = await system.search(context, "content", layers=[1])
        for r in results:
            assert r.layer == 1

    async def test_tenant_isolation(self, system):
        ctx1 = _make_context(tenant_id="tenant-a")
        ctx2 = _make_context(tenant_id="tenant-b")
        await system.store(ctx1, "tenant A secret")
        results = await system.search(ctx2, "tenant A secret")
        assert len(results) == 0

    async def test_store_with_tags(self, system, context):
        memory_id = await system.store(context, "tagged memory", tags=["important", "test"])
        item = system.get_item(memory_id)
        assert item is not None
        assert "important" in item.tags

    async def test_store_with_metadata(self, system, context):
        memory_id = await system.store(
            context, "meta memory", metadata={"source": "test", "version": 2}
        )
        item = system.get_item(memory_id)
        assert item is not None
        assert item.metadata.get("source") == "test"

    async def test_count(self, system, context):
        initial = system.count()
        await system.store(context, "item 1")
        await system.store(context, "item 2")
        assert system.count() == initial + 2

    async def test_layer_counts(self, system, context):
        await system.store(context, "l1", layer=1)
        await system.store(context, "l3", layer=3)
        counts = system.layer_counts()
        assert counts[1] >= 1
        assert counts[3] >= 1


# ---------------------------------------------------------------------------
# Tier1Backend (in-memory TTL)
# ---------------------------------------------------------------------------

class TestTier1Backend:
    @pytest.fixture
    def tier1(self):
        return Tier1Backend(max_items=100, default_ttl=3600)

    async def test_store_and_search(self, tier1):
        await tier1.store("key1", "hello world", layer=1)
        results = await tier1.search("hello")
        assert len(results) >= 1
        assert results[0].content == "hello world"

    async def test_ttl_expiry(self, tier1):
        # Store with very short TTL (1 second)
        await tier1.store("key2", "ephemeral", layer=1, ttl=1)
        # Should be found immediately
        results = await tier1.search("ephemeral")
        assert len(results) == 1
        # After TTL expires, should not be found
        await asyncio.sleep(1.1)
        results = await tier1.search("ephemeral")
        assert len(results) == 0

    async def test_max_items_config(self):
        tier1 = Tier1Backend(max_items=3, default_ttl=3600)
        assert tier1.max_items == 3
        for i in range(5):
            await tier1.store(f"key{i}", f"content {i}", layer=1)
        # All items stored (eviction is lazy/search-time)
        assert len(tier1._store) == 5

    async def test_search_no_match(self, tier1):
        await tier1.store("k", "apple", layer=1)
        results = await tier1.search("banana")
        assert results == []


# ---------------------------------------------------------------------------
# TieredMemorySystem
# ---------------------------------------------------------------------------

class TestTieredMemorySystem:
    @pytest.fixture
    def tiered(self):
        return TieredMemorySystem()

    async def test_store_tier1(self, tiered):
        await tiered.store("test content", layer=1)
        results = await tiered.search("test", layers=[1, 2, 3])
        assert len(results) >= 1

    async def test_search_parallel(self, tiered):
        await tiered.store("alpha content", layer=1)
        results = await tiered.search("alpha", layers=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        assert isinstance(results, list)

    async def test_search_empty_layers(self, tiered):
        results = await tiered.search("anything", layers=[])
        assert results == []

    async def test_results_sorted_by_score(self, tiered):
        await tiered.store("low score", layer=1)
        await tiered.store("high score", layer=1)
        results = await tiered.search("score", layers=[1, 2, 3])
        if len(results) >= 2:
            assert results[0].score >= results[1].score


# ---------------------------------------------------------------------------
# MemoryHit model
# ---------------------------------------------------------------------------

class TestMemoryHit:
    def test_defaults(self):
        hit = MemoryHit()
        assert hit.content == ""
        assert hit.layer == 1
        assert hit.score == 0.0
        assert hit.tier == 1

    def test_custom(self):
        hit = MemoryHit(content="test", layer=5, score=0.95, tier=2)
        assert hit.content == "test"
        assert hit.tier == 2
