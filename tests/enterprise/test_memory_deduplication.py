"""
Unit tests for memory deduplication system.

Tests all deduplication strategies, edge cases, and integration scenarios.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, UTC
import numpy as np

from backend.app.core.memory_deduplication_enhanced import (
    Memory,
    MemoryDeduplicatorEnhanced,
    DeduplicationStats,
)
from backend.app.core.memory_deduplication_service import (
    MemoryDeduplicationService,
    MemoryDeduplicationMonitor,
)


class TestMemoryDeduplicatorEnhanced:
    """Test suite for MemoryDeduplicatorEnhanced."""

    @pytest.fixture
    def deduplicator(self):
        """Create a deduplicator instance."""
        return MemoryDeduplicatorEnhanced(
            vector_similarity_threshold=0.95,
            hash_similarity_threshold=0.9,
            time_window_hours=24,
        )

    @pytest.fixture
    def sample_memories(self):
        """Create sample memories for testing."""
        return [
            Memory(
                id="mem_1",
                content="User logged in successfully",
                created_at=datetime.now(UTC),
                importance=0.8,
            ),
            Memory(
                id="mem_2",
                content="User logged in successfully",  # Exact duplicate
                created_at=datetime.now(UTC),
                importance=0.7,
            ),
            Memory(
                id="mem_3",
                content="Database query executed in 45ms",
                created_at=datetime.now(UTC),
                importance=0.6,
            ),
            Memory(
                id="mem_4",
                content="API endpoint returned 200 OK",
                created_at=datetime.now(UTC),
                importance=0.5,
            ),
        ]

    def test_hash_deduplication(self, deduplicator, sample_memories):
        """Test hash-based deduplication."""
        result = deduplicator.deduplicate(sample_memories, strategy="hash")

        assert result.original_count == 4
        assert result.deduplicated_count == 3  # One duplicate removed
        assert len(result.removed_ids) == 1
        assert "mem_2" in result.removed_ids

    def test_vector_deduplication(self, deduplicator, sample_memories):
        """Test vector-based deduplication."""
        result = deduplicator.deduplicate(sample_memories, strategy="vector")

        assert result.original_count == 4
        assert result.deduplicated_count >= 3  # At least one duplicate removed

    def test_combined_deduplication(self, deduplicator, sample_memories):
        """Test combined deduplication strategy."""
        result = deduplicator.deduplicate(sample_memories, strategy="combined")

        assert result.original_count == 4
        assert result.deduplicated_count >= 3

    def test_empty_memories(self, deduplicator):
        """Test deduplication with empty list."""
        result = deduplicator.deduplicate([], strategy="combined")

        assert result.original_count == 0
        assert result.deduplicated_count == 0
        assert len(result.removed_ids) == 0

    def test_single_memory(self, deduplicator):
        """Test deduplication with single memory."""
        memories = [
            Memory(
                id="mem_1",
                content="Single memory",
                created_at=datetime.now(UTC),
            )
        ]

        result = deduplicator.deduplicate(memories, strategy="combined")

        assert result.original_count == 1
        assert result.deduplicated_count == 1
        assert len(result.removed_ids) == 0

    def test_no_duplicates(self, deduplicator):
        """Test deduplication with no duplicates."""
        memories = [
            Memory(
                id="mem_1",
                content="First unique memory",
                created_at=datetime.now(UTC),
            ),
            Memory(
                id="mem_2",
                content="Second unique memory",
                created_at=datetime.now(UTC),
            ),
            Memory(
                id="mem_3",
                content="Third unique memory",
                created_at=datetime.now(UTC),
            ),
        ]

        result = deduplicator.deduplicate(memories, strategy="combined")

        assert result.original_count == 3
        assert result.deduplicated_count == 3
        assert len(result.removed_ids) == 0

    def test_all_duplicates(self, deduplicator):
        """Test deduplication with all duplicates."""
        memories = [
            Memory(
                id=f"mem_{i}",
                content="Same content for all",
                created_at=datetime.now(UTC),
            )
            for i in range(5)
        ]

        result = deduplicator.deduplicate(memories, strategy="hash")

        assert result.original_count == 5
        assert result.deduplicated_count == 1
        assert len(result.removed_ids) == 4

    def test_incremental_deduplication(self, deduplicator):
        """Test incremental deduplication."""
        existing = [
            Memory(
                id="existing_1",
                content="Existing memory",
                created_at=datetime.now(UTC),
            ),
        ]

        new = [
            Memory(
                id="new_1",
                content="Existing memory",  # Duplicate
                created_at=datetime.now(UTC),
            ),
            Memory(
                id="new_2",
                content="New unique memory",
                created_at=datetime.now(UTC),
            ),
        ]

        result = deduplicator.incremental_deduplicate(new, existing)

        assert result.original_count == 2
        assert len(result.removed_ids) >= 1

    def test_batch_deduplication(self, deduplicator):
        """Test batch deduplication."""
        batches = [
            [
                Memory(
                    id=f"batch_{i}_mem_{j}",
                    content=f"Memory {j}",
                    created_at=datetime.now(UTC),
                )
                for j in range(10)
            ]
            for i in range(3)
        ]

        results = deduplicator.batch_deduplicate(batches, strategy="combined")

        assert len(results) == 3
        for result in results:
            assert result.original_count == 10

    def test_memory_score_calculation(self, deduplicator):
        """Test memory score calculation."""
        # Recent, high importance memory
        recent_memory = Memory(
            id="recent",
            content="Recent memory",
            created_at=datetime.now(UTC),
            importance=0.9,
            access_count=50,
        )

        # Old, low importance memory
        old_memory = Memory(
            id="old",
            content="Old memory",
            created_at=datetime.now(UTC) - timedelta(days=30),
            importance=0.1,
            access_count=1,
        )

        recent_score = deduplicator._calculate_memory_score(recent_memory)
        old_score = deduplicator._calculate_memory_score(old_memory)

        assert recent_score > old_score

    def test_best_memory_selection(self, deduplicator):
        """Test selection of best memory from group."""
        memories = [
            Memory(
                id="mem_1",
                content="Same content",
                created_at=datetime.now(UTC) - timedelta(hours=2),
                importance=0.5,
                access_count=10,
            ),
            Memory(
                id="mem_2",
                content="Same content",
                created_at=datetime.now(UTC),
                importance=0.8,
                access_count=50,
            ),
            Memory(
                id="mem_3",
                content="Same content",
                created_at=datetime.now(UTC) - timedelta(hours=1),
                importance=0.6,
                access_count=20,
            ),
        ]

        best = deduplicator._select_best_memory(memories)

        # Should select mem_2 (most recent and important)
        assert best.id == "mem_2"

    def test_statistics_generation(self, deduplicator, sample_memories):
        """Test statistics generation."""
        result = deduplicator.deduplicate(sample_memories, strategy="combined")
        stats = deduplicator.get_deduplication_stats(result)

        assert "original_count" in stats
        assert "deduplicated_count" in stats
        assert "reduction_rate" in stats
        assert "processing_time" in stats
        assert "memory_saved_bytes" in stats

        assert stats["original_count"] == 4
        assert stats["reduction_rate"] >= 0

    def test_cache_statistics(self, deduplicator):
        """Test cache statistics."""
        cache_stats = deduplicator.get_cache_stats()

        assert "cache_size" in cache_stats
        assert "cache_hits" in cache_stats
        assert "cache_misses" in cache_stats
        assert "hit_rate" in cache_stats

    def test_content_hash_calculation(self):
        """Test content hash calculation."""
        memory1 = Memory(id="1", content="Test content")
        memory2 = Memory(id="2", content="Test content")
        memory3 = Memory(id="3", content="Different content")

        assert memory1.content_hash == memory2.content_hash
        assert memory1.content_hash != memory3.content_hash

    def test_similarity_threshold_effect(self):
        """Test effect of similarity threshold."""
        memories = [
            Memory(
                id="mem_1",
                content="The quick brown fox jumps over the lazy dog",
                created_at=datetime.now(UTC),
            ),
            Memory(
                id="mem_2",
                content="The quick brown fox jumps over the lazy dog",
                created_at=datetime.now(UTC),
            ),
        ]

        # Strict threshold
        strict_dedup = MemoryDeduplicatorEnhanced(
            vector_similarity_threshold=0.99
        )
        strict_result = strict_dedup.deduplicate(memories, strategy="vector")

        # Loose threshold
        loose_dedup = MemoryDeduplicatorEnhanced(
            vector_similarity_threshold=0.80
        )
        loose_result = loose_dedup.deduplicate(memories, strategy="vector")

        # Both should find duplicates for identical content
        assert strict_result.deduplicated_count <= loose_result.deduplicated_count


class TestMemoryDeduplicationService:
    """Test suite for MemoryDeduplicationService."""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return MemoryDeduplicationService(
            vector_similarity_threshold=0.95,
            auto_deduplicate=False,  # Disable auto for testing
        )

    @pytest.fixture
    def sample_memories(self):
        """Create sample memories."""
        return [
            Memory(
                id=f"mem_{i}",
                content=f"Memory content {i}",
                created_at=datetime.now(UTC),
                importance=0.5,
            )
            for i in range(10)
        ]

    @pytest.mark.asyncio
    async def test_deduplicate_memories(self, service, sample_memories):
        """Test memory deduplication through service."""
        result = await service.deduplicate_memories(
            sample_memories,
            strategy="combined",
        )

        assert result.original_count == 10
        assert result.deduplicated_count <= 10

    @pytest.mark.asyncio
    async def test_incremental_deduplicate(self, service, sample_memories):
        """Test incremental deduplication through service."""
        new_memories = sample_memories[:5]
        existing_memories = sample_memories[5:]

        result = await service.incremental_deduplicate(
            new_memories,
            existing_memories,
        )

        assert result.original_count == 5

    @pytest.mark.asyncio
    async def test_auto_deduplicate_if_needed(self, service, sample_memories):
        """Test auto deduplication trigger."""
        # 本用例验证"间隔到了才触发",需开启自动去重开关
        # (service fixture 默认关闭,关闭时按设计应始终返回 None)
        service.auto_deduplicate = True

        # First call should not deduplicate (interval not passed)
        result1 = await service.auto_deduplicate_if_needed(sample_memories)
        assert result1 is None

        # Manually set last dedup time to past
        service.last_dedup_time = datetime.now(UTC) - timedelta(hours=2)

        # Second call should deduplicate
        result2 = await service.auto_deduplicate_if_needed(sample_memories)
        assert result2 is not None

    def test_service_statistics(self, service):
        """Test service statistics."""
        stats = service.get_service_stats()

        assert "total_deduplications" in stats
        assert "total_removed" in stats
        assert "total_memory_saved_bytes" in stats
        assert "cache_stats" in stats
        assert "graph_stats" in stats

    def test_export_configuration(self, service):
        """Test configuration export."""
        config = service.export_deduplication_config()

        assert "vector_similarity_threshold" in config
        assert "hash_similarity_threshold" in config
        assert "time_window_hours" in config
        assert "auto_deduplicate" in config


class TestMemoryDeduplicationMonitor:
    """Test suite for MemoryDeduplicationMonitor."""

    @pytest.fixture
    def service_and_monitor(self):
        """Create service and monitor."""
        service = MemoryDeduplicationService()
        monitor = MemoryDeduplicationMonitor(service)
        return service, monitor

    def test_record_deduplication(self, service_and_monitor):
        """Test recording deduplication metrics."""
        service, monitor = service_and_monitor

        from backend.app.core.memory_deduplication_enhanced import DeduplicationResult

        result = DeduplicationResult(
            original_count=100,
            deduplicated_count=90,
            removed_ids=["id_1", "id_2", "id_3", "id_4", "id_5", "id_6", "id_7", "id_8", "id_9", "id_10"],
            stats=DeduplicationStats(
                original_count=100,
                deduplicated_count=90,
                removed_count=10,
                merged_groups=5,
                vector_duplicates=3,
                hash_duplicates=5,
                time_window_duplicates=2,
                processing_time=0.5,
                memory_saved_bytes=5000,
            ),
        )

        monitor.record_deduplication(result)

        assert len(monitor.metrics) == 1
        assert monitor.metrics[0]["original_count"] == 100

    def test_metrics_summary(self, service_and_monitor):
        """Test metrics summary."""
        service, monitor = service_and_monitor

        from backend.app.core.memory_deduplication_enhanced import DeduplicationResult

        # Record multiple deduplications
        for i in range(3):
            result = DeduplicationResult(
                original_count=100,
                deduplicated_count=90,
                removed_ids=[f"id_{j}" for j in range(10)],
                stats=DeduplicationStats(
                    original_count=100,
                    deduplicated_count=90,
                    removed_count=10,
                    merged_groups=5,
                    vector_duplicates=3,
                    hash_duplicates=5,
                    time_window_duplicates=2,
                    processing_time=0.5,
                    memory_saved_bytes=5000,
                ),
            )
            monitor.record_deduplication(result)

        summary = monitor.get_metrics_summary(hours=24)

        assert summary["deduplication_count"] == 3
        assert summary["total_removed"] == 30
        assert summary["avg_reduction_rate"] > 0

    def test_anomaly_detection(self, service_and_monitor):
        """Test anomaly detection."""
        service, monitor = service_and_monitor

        from backend.app.core.memory_deduplication_enhanced import DeduplicationResult

        # Record normal deduplications
        for i in range(5):
            result = DeduplicationResult(
                original_count=100,
                deduplicated_count=90,
                removed_ids=[f"id_{j}" for j in range(10)],
                stats=DeduplicationStats(
                    original_count=100,
                    deduplicated_count=90,
                    removed_count=10,
                    merged_groups=5,
                    vector_duplicates=3,
                    hash_duplicates=5,
                    time_window_duplicates=2,
                    processing_time=0.5,
                    memory_saved_bytes=5000,
                ),
            )
            monitor.record_deduplication(result)

        # Record anomalous deduplication
        anomaly_result = DeduplicationResult(
            original_count=100,
            deduplicated_count=50,  # Much higher reduction
            removed_ids=[f"id_{j}" for j in range(50)],
            stats=DeduplicationStats(
                original_count=100,
                deduplicated_count=50,
                removed_count=50,
                merged_groups=25,
                vector_duplicates=20,
                hash_duplicates=25,
                time_window_duplicates=5,
                processing_time=0.5,
                memory_saved_bytes=25000,
            ),
        )
        monitor.record_deduplication(anomaly_result)

        anomalies = monitor.detect_anomalies()

        # Should detect the anomalous reduction rate
        assert len(anomalies) > 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_very_large_memories(self):
        """Test with very large memory content."""
        deduplicator = MemoryDeduplicatorEnhanced()

        large_content = "x" * 100000  # 100KB content

        memories = [
            Memory(
                id="mem_1",
                content=large_content,
                created_at=datetime.now(UTC),
            ),
            Memory(
                id="mem_2",
                content=large_content,
                created_at=datetime.now(UTC),
            ),
        ]

        result = deduplicator.deduplicate(memories, strategy="hash")

        assert result.deduplicated_count == 1

    def test_special_characters(self):
        """Test with special characters in content."""
        deduplicator = MemoryDeduplicatorEnhanced()

        memories = [
            Memory(
                id="mem_1",
                content="Special chars: !@#$%^&*()_+-=[]{}|;:',.<>?/",
                created_at=datetime.now(UTC),
            ),
            Memory(
                id="mem_2",
                content="Special chars: !@#$%^&*()_+-=[]{}|;:',.<>?/",
                created_at=datetime.now(UTC),
            ),
        ]

        result = deduplicator.deduplicate(memories, strategy="hash")

        assert result.deduplicated_count == 1

    def test_unicode_content(self):
        """Test with unicode content."""
        deduplicator = MemoryDeduplicatorEnhanced()

        memories = [
            Memory(
                id="mem_1",
                content="中文内容测试 🎉 Тест на русском",
                created_at=datetime.now(UTC),
            ),
            Memory(
                id="mem_2",
                content="中文内容测试 🎉 Тест на русском",
                created_at=datetime.now(UTC),
            ),
        ]

        result = deduplicator.deduplicate(memories, strategy="hash")

        assert result.deduplicated_count == 1

    def test_whitespace_variations(self):
        """Test with whitespace variations."""
        deduplicator = MemoryDeduplicatorEnhanced()

        memories = [
            Memory(
                id="mem_1",
                content="Content with   multiple   spaces",
                created_at=datetime.now(UTC),
            ),
            Memory(
                id="mem_2",
                content="Content with multiple spaces",
                created_at=datetime.now(UTC),
            ),
        ]

        result = deduplicator.deduplicate(memories, strategy="hash")

        # Hash-based should not match (different whitespace)
        assert result.deduplicated_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
