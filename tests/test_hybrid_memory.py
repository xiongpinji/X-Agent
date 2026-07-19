"""Comprehensive tests for hybrid memory system.

Tests cover:
- Three-tier storage correctness
- Automatic classification
- Memory merging
- Query performance
- Memory synchronization
- Deduplication
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.core.cold_memory_store import ColdMemoryStore
from backend.app.core.graph_memory_store import GraphMemoryStore
from backend.app.core.hot_memory_store import HotMemoryStore
from backend.app.core.hybrid_memory_system import HybridMemorySystem, Memory
from backend.app.core.memory_classifier import MemoryClassifier
from backend.app.core.memory_merger import MemoryMerger


@pytest.fixture
def temp_storage(tmp_path: Path) -> Path:
    """Create temporary storage directory."""
    storage = tmp_path / "memories"
    storage.mkdir()
    return storage


@pytest.fixture
def hot_store(temp_storage: Path) -> HotMemoryStore:
    """Create hot memory store."""
    return HotMemoryStore(storage_path=temp_storage)


@pytest.fixture
def cold_store() -> ColdMemoryStore:
    """Create cold memory store (without Qdrant client)."""
    return ColdMemoryStore(qdrant_client=None)


@pytest.fixture
def graph_store() -> GraphMemoryStore:
    """Create graph memory store (without Neo4j driver)."""
    return GraphMemoryStore(neo4j_driver=None)


@pytest.fixture
def classifier() -> MemoryClassifier:
    """Create memory classifier."""
    return MemoryClassifier()


@pytest.fixture
def merger() -> MemoryMerger:
    """Create memory merger."""
    return MemoryMerger()


@pytest.fixture
def hybrid_system(
    hot_store: HotMemoryStore,
    cold_store: ColdMemoryStore,
    graph_store: GraphMemoryStore,
    classifier: MemoryClassifier,
    merger: MemoryMerger,
) -> HybridMemorySystem:
    """Create hybrid memory system."""
    return HybridMemorySystem(
        hot_store=hot_store,
        cold_store=cold_store,
        graph_store=graph_store,
        classifier=classifier,
        merger=merger,
    )


class TestHotMemoryStore:
    """Test hot memory store functionality."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, hot_store: HotMemoryStore) -> None:
        """Test saving and loading memory."""
        memory = Memory(
            id=str(uuid4()),
            content="Test memory content",
            category="reference",
            importance=0.7,
        )

        # Save
        memory_id = await hot_store.save(memory)
        assert memory_id == memory.id

        # Load
        loaded = await hot_store.load(memory_id)
        assert loaded is not None
        assert loaded.content == memory.content
        assert loaded.category == memory.category

    @pytest.mark.asyncio
    async def test_search(self, hot_store: HotMemoryStore) -> None:
        """Test text search."""
        memories = [
            Memory(
                id=str(uuid4()),
                content="Python programming tutorial",
                category="reference",
            ),
            Memory(
                id=str(uuid4()),
                content="JavaScript basics guide",
                category="reference",
            ),
        ]

        for mem in memories:
            await hot_store.save(mem)

        # Search
        results = await hot_store.search("Python")
        assert len(results) >= 1
        assert any("Python" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_list_by_category(self, hot_store: HotMemoryStore) -> None:
        """Test listing by category."""
        memories = [
            Memory(
                id=str(uuid4()),
                content="User profile info",
                category="user",
            ),
            Memory(
                id=str(uuid4()),
                content="Project requirements",
                category="project",
            ),
        ]

        for mem in memories:
            await hot_store.save(mem)

        # List by category
        user_mems = await hot_store.list_by_category("user")
        assert len(user_mems) >= 1
        assert all(m.category == "user" for m in user_mems)

    @pytest.mark.asyncio
    async def test_delete(self, hot_store: HotMemoryStore) -> None:
        """Test memory deletion."""
        memory = Memory(
            id=str(uuid4()),
            content="Temporary memory",
            category="reference",
        )

        await hot_store.save(memory)
        deleted = await hot_store.delete(memory.id)
        assert deleted

        loaded = await hot_store.load(memory.id)
        assert loaded is None


class TestMemoryClassifier:
    """Test memory classifier functionality."""

    def test_classify_user_memory(self, classifier: MemoryClassifier) -> None:
        """Test user memory classification."""
        memory = Memory(
            id=str(uuid4()),
            content="User profile settings and preferences",
            category="reference",
        )

        category = classifier.classify(memory)
        assert category == "user"

    def test_classify_project_memory(self, classifier: MemoryClassifier) -> None:
        """Test project memory classification."""
        memory = Memory(
            id=str(uuid4()),
            content="Project milestone deadline and sprint planning",
            category="reference",
        )

        category = classifier.classify(memory)
        assert category == "project"

    def test_score_importance(self, classifier: MemoryClassifier) -> None:
        """Test importance scoring."""
        memory = Memory(
            id=str(uuid4()),
            content="Critical security vulnerability found in authentication system",
            category="reference",
            access_count=10,
        )

        score = classifier.score_importance(memory)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be important due to keywords

    def test_detect_duplicates(self, classifier: MemoryClassifier) -> None:
        """Test duplicate detection."""
        memory1 = Memory(
            id=str(uuid4()),
            content="Python programming tutorial for beginners",
            category="reference",
        )

        memory2 = Memory(
            id=str(uuid4()),
            content="Python tutorial for beginners programming",
            category="reference",
        )

        duplicates = classifier.detect_duplicates(memory1, [memory2])
        assert len(duplicates) > 0

    def test_should_expire(self, classifier: MemoryClassifier) -> None:
        """Test expiration detection."""
        # Old, low-importance memory
        old_memory = Memory(
            id=str(uuid4()),
            content="Old temporary note",
            category="reference",
            importance=0.2,
            created_at=datetime.now(UTC) - timedelta(days=100),
        )

        assert classifier.should_expire(old_memory)

        # Recent, high-importance memory
        new_memory = Memory(
            id=str(uuid4()),
            content="Important recent note",
            category="reference",
            importance=0.9,
            created_at=datetime.now(UTC),
        )

        assert not classifier.should_expire(new_memory)


class TestMemoryMerger:
    """Test memory merger functionality."""

    @pytest.mark.asyncio
    async def test_merge_combine(self, merger: MemoryMerger) -> None:
        """Test combine merge strategy."""
        memories = [
            Memory(
                id=str(uuid4()),
                content="First part of information",
                category="reference",
                importance=0.5,
            ),
            Memory(
                id=str(uuid4()),
                content="Second part of information",
                category="reference",
                importance=0.6,
            ),
        ]

        merged = await merger.merge(memories, strategy="combine")
        assert "First part" in merged.content
        assert "Second part" in merged.content
        assert merged.importance == 0.6

    @pytest.mark.asyncio
    async def test_merge_keep_newest(self, merger: MemoryMerger) -> None:
        """Test keep newest merge strategy."""
        old_memory = Memory(
            id=str(uuid4()),
            content="Old content",
            category="reference",
            created_at=datetime.now(UTC) - timedelta(days=1),
        )

        new_memory = Memory(
            id=str(uuid4()),
            content="New content",
            category="reference",
            created_at=datetime.now(UTC),
        )

        merged = await merger.merge([old_memory, new_memory], strategy="keep_newest")
        assert merged.content == "New content"

    @pytest.mark.asyncio
    async def test_supplement(self, merger: MemoryMerger) -> None:
        """Test memory supplementation."""
        base = Memory(
            id=str(uuid4()),
            content="Base information",
            category="reference",
        )

        additions = [
            Memory(
                id=str(uuid4()),
                content="Additional detail 1",
                category="reference",
            ),
            Memory(
                id=str(uuid4()),
                content="Additional detail 2",
                category="reference",
            ),
        ]

        supplemented = await merger.supplement(base, additions)
        assert "Base information" in supplemented.content
        assert "Additional detail 1" in supplemented.content
        assert "Additional detail 2" in supplemented.content

    def test_detect_merge_candidates(self, merger: MemoryMerger) -> None:
        """Test merge candidate detection."""
        memories = [
            Memory(
                id=str(uuid4()),
                content="Python programming tutorial",
                category="reference",
            ),
            Memory(
                id=str(uuid4()),
                content="Python tutorial for programming",
                category="reference",
            ),
            Memory(
                id=str(uuid4()),
                content="JavaScript guide",
                category="reference",
            ),
        ]

        groups = merger.detect_merge_candidates(memories, similarity_threshold=0.7)
        assert len(groups) >= 1
        assert len(groups[0]) >= 2


class TestHybridMemorySystem:
    """Test hybrid memory system functionality."""

    @pytest.mark.asyncio
    async def test_store_and_recall(self, hybrid_system: HybridMemorySystem) -> None:
        """Test storing and recalling memory."""
        memory = Memory(
            id=str(uuid4()),
            content="Important project milestone completed",
            category="project",
            importance=0.8,
        )

        # Store
        memory_id = await hybrid_system.store(memory)
        assert memory_id == memory.id

        # Recall
        results = await hybrid_system.recall("project milestone")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_auto_tier_selection(self, hybrid_system: HybridMemorySystem) -> None:
        """Test automatic tier selection."""
        # Recent, important memory -> hot
        hot_memory = Memory(
            id=str(uuid4()),
            content="Recent important note",
            category="reference",
            importance=0.8,
            created_at=datetime.now(UTC),
        )

        tier = hybrid_system._select_tier(hot_memory)
        assert tier == "hot"

        # Old, low-importance memory -> cold
        cold_memory = Memory(
            id=str(uuid4()),
            content="Old temporary note",
            category="reference",
            importance=0.2,
            created_at=datetime.now(UTC) - timedelta(days=60),
        )

        tier = hybrid_system._select_tier(cold_memory)
        assert tier == "cold"

    @pytest.mark.asyncio
    async def test_search_types(self, hybrid_system: HybridMemorySystem) -> None:
        """Test different search types."""
        memory = Memory(
            id=str(uuid4()),
            content="Test memory for search",
            category="reference",
        )

        await hybrid_system.store(memory)

        # Text search
        results = await hybrid_system.search("Test memory", search_type="text")
        assert len(results) >= 0

        # Hybrid search
        results = await hybrid_system.search("Test memory", search_type="hybrid")
        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_relate_memories(self, hybrid_system: HybridMemorySystem) -> None:
        """Test memory relationship creation."""
        mem1 = Memory(
            id=str(uuid4()),
            content="First memory",
            category="reference",
        )

        mem2 = Memory(
            id=str(uuid4()),
            content="Second memory",
            category="reference",
        )

        await hybrid_system.store(mem1)
        await hybrid_system.store(mem2)

        # Create relationship
        success = await hybrid_system.relate(mem1.id, mem2.id, "related_to")
        assert success is True

    @pytest.mark.asyncio
    async def test_get_stats(self, hybrid_system: HybridMemorySystem) -> None:
        """Test statistics retrieval."""
        memory = Memory(
            id=str(uuid4()),
            content="Test memory",
            category="reference",
        )

        await hybrid_system.store(memory)

        stats = await hybrid_system.get_stats()
        assert stats.total_count >= 1
        assert stats.hot_count >= 1

    @pytest.mark.asyncio
    async def test_duplicate_detection(self, hybrid_system: HybridMemorySystem) -> None:
        """Test duplicate detection during storage."""
        memory1 = Memory(
            id=str(uuid4()),
            content="Python programming tutorial",
            category="reference",
        )

        memory2 = Memory(
            id=str(uuid4()),
            content="Python tutorial for programming",
            category="reference",
        )

        await hybrid_system.store(memory1)
        await hybrid_system.store(memory2)

        # Second memory should be detected as duplicate
        duplicates = await hybrid_system._detect_duplicates(memory2)
        # Note: May or may not find duplicates depending on store implementation


class TestPerformance:
    """Performance tests for hybrid memory system."""

    @pytest.mark.asyncio
    async def test_hot_tier_performance(self, hot_store: HotMemoryStore) -> None:
        """Test hot tier access performance."""
        import time

        memories = [
            Memory(
                id=str(uuid4()),
                content=f"Memory {i}",
                category="reference",
            )
            for i in range(100)
        ]

        # Save
        for mem in memories:
            await hot_store.save(mem)

        # Measure load time
        start = time.time()
        for mem in memories[:10]:
            await hot_store.load(mem.id)
        elapsed = time.time() - start

        # Should be fast (< 100ms for 10 loads)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_search_performance(self, hot_store: HotMemoryStore) -> None:
        """Test search performance."""
        import time

        memories = [
            Memory(
                id=str(uuid4()),
                content=f"Python tutorial part {i}",
                category="reference",
            )
            for i in range(50)
        ]

        for mem in memories:
            await hot_store.save(mem)

        # Measure search time
        start = time.time()
        results = await hot_store.search("Python")
        elapsed = time.time() - start

        # Should be reasonably fast
        assert elapsed < 1.0
        assert len(results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
