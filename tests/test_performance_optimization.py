"""
Performance Optimization Tests.

Tests for performance optimization modules.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.db_optimization import (
    DatabaseConnectionPool,
    QueryOptimizer,
    BatchOperationExecutor,
    QueryCache,
)
from backend.app.core.api_optimization import (
    ResponseCompressor,
    EfficientSerializer,
    PaginationHelper,
    ResponseOptimizer,
)
from backend.app.core.cache_optimization import (
    CacheWarmer,
    CacheInvalidationStrategy,
    CacheStatistics,
    MultiLevelCache,
)
from backend.app.core.performance_monitor import (
    APIMetric,
    PerformanceReport,
    PerformanceMonitor,
    PerformanceAlert,
)


# ============================================================================
# Database Optimization Tests
# ============================================================================

class TestDatabaseConnectionPool:
    """Tests for database connection pool."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self) -> None:
        """Test pool initialization."""
        pool = DatabaseConnectionPool(
            database_url="postgresql://localhost/test",
            min_size=5,
            max_size=10,
        )
        assert pool.min_size == 5
        assert pool.max_size == 10

    def test_query_optimizer_indexes(self) -> None:
        """Test query optimizer index generation."""
        pool = MagicMock()
        indexes = QueryOptimizer.add_indexes(pool)

        assert len(indexes) > 0
        assert any("workflows" in idx for idx in indexes)
        assert any("agent_runs" in idx for idx in indexes)
        assert any("memories" in idx for idx in indexes)

    @pytest.mark.asyncio
    async def test_batch_operation_executor(self) -> None:
        """Test batch operation executor."""
        pool = MagicMock()
        pool.execute = AsyncMock()

        executor = BatchOperationExecutor(pool, batch_size=100)

        values = [(f"id_{i}", f"name_{i}") for i in range(250)]
        result = await executor.batch_insert("test_table", ["id", "name"], values)

        assert result == 250
        assert pool.execute.call_count == 3  # 100 + 100 + 50

    def test_query_cache(self) -> None:
        """Test query cache."""
        cache = QueryCache(ttl=60)

        # Test set and get
        cache.set("key1", {"data": "value"})
        result = cache.get("key1")
        assert result == {"data": "value"}

        # Test cache miss
        result = cache.get("nonexistent")
        assert result is None

        # Test invalidation
        cache.set("key2", {"data": "value2"})
        cache.set("key3", {"data": "value3"})
        cache.invalidate("key")
        assert cache.get("key2") is None
        assert cache.get("key3") is None


# ============================================================================
# API Optimization Tests
# ============================================================================

class TestResponseCompression:
    """Tests for response compression."""

    def test_should_compress(self) -> None:
        """Test compression decision."""
        # Should compress large response with gzip support
        assert ResponseCompressor.should_compress(
            b"x" * 2000,
            "gzip, deflate",
        )

        # Should not compress small response
        assert not ResponseCompressor.should_compress(
            b"x" * 500,
            "gzip, deflate",
        )

        # Should not compress without gzip support
        assert not ResponseCompressor.should_compress(
            b"x" * 2000,
            "deflate",
        )

    def test_compress(self) -> None:
        """Test compression."""
        data = b"x" * 1000
        compressed = ResponseCompressor.compress(data)

        assert len(compressed) < len(data)
        assert compressed.startswith(b"\x1f\x8b")  # gzip magic number


class TestEfficientSerializer:
    """Tests for efficient serializer."""

    def test_serialize(self) -> None:
        """Test serialization."""
        obj = {"id": 1, "name": "test", "value": None}
        result = EfficientSerializer.serialize(obj)

        assert isinstance(result, str)
        assert "id" in result
        assert "name" in result

    def test_select_fields(self) -> None:
        """Test field selection."""
        obj = {"id": 1, "name": "test", "email": "test@example.com"}

        # Select specific fields
        result = EfficientSerializer.select_fields(obj, ["id", "name"])
        assert result == {"id": 1, "name": "test"}

        # No fields specified
        result = EfficientSerializer.select_fields(obj, None)
        assert result == obj


class TestPaginationHelper:
    """Tests for pagination helper."""

    def test_paginate(self) -> None:
        """Test pagination."""
        items = list(range(100))

        # First page
        result = PaginationHelper.paginate(items, page=1, page_size=20)
        assert len(result["items"]) == 20
        assert result["pagination"]["page"] == 1
        assert result["pagination"]["total"] == 100
        assert result["pagination"]["total_pages"] == 5
        assert result["pagination"]["has_next"]

        # Last page
        result = PaginationHelper.paginate(items, page=5, page_size=20)
        assert len(result["items"]) == 20
        assert not result["pagination"]["has_next"]

    def test_cursor_paginate(self) -> None:
        """Test cursor-based pagination."""
        items = [{"id": str(i), "name": f"item_{i}"} for i in range(100)]

        # First page
        result = PaginationHelper.cursor_paginate(items, cursor=None, limit=20)
        assert len(result["items"]) == 20
        assert result["pagination"]["has_more"]
        assert result["pagination"]["next_cursor"] is not None

        # Next page
        next_cursor = result["pagination"]["next_cursor"]
        result = PaginationHelper.cursor_paginate(items, cursor=next_cursor, limit=20)
        assert len(result["items"]) == 20


# ============================================================================
# Cache Optimization Tests
# ============================================================================

class TestCacheStatistics:
    """Tests for cache statistics."""

    def test_statistics(self) -> None:
        """Test cache statistics."""
        stats = CacheStatistics()

        # Record operations
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        stats.record_set()
        stats.record_delete()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.sets == 1
        assert stats.deletes == 1
        assert stats.hit_rate() == pytest.approx(66.67, rel=0.01)


class TestMultiLevelCache:
    """Tests for multi-level cache."""

    @pytest.mark.asyncio
    async def test_get_set(self) -> None:
        """Test cache get/set."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)

        # Set value
        await cache.set("key1", {"data": "value"})
        assert "key1" in cache.l1_cache

        # Get value
        result = await cache.get("key1")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        """Test cache delete."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)

        await cache.set("key1", {"data": "value"})
        await cache.delete("key1")

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self) -> None:
        """Test pattern invalidation."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)

        await cache.set("workflow:1", {"data": "value1"})
        await cache.set("workflow:2", {"data": "value2"})
        await cache.set("agent:1", {"data": "value3"})

        await cache.invalidate_pattern("workflow:")

        assert await cache.get("workflow:1") is None
        assert await cache.get("workflow:2") is None
        assert await cache.get("agent:1") == {"data": "value3"}


# ============================================================================
# Performance Monitor Tests
# ============================================================================

class TestPerformanceMonitor:
    """Tests for performance monitor."""

    def test_record_metric(self) -> None:
        """Test metric recording."""
        monitor = PerformanceMonitor()

        metric = APIMetric(
            endpoint="/api/v1/workflows",
            method="GET",
            status_code=200,
            response_time=0.1,
        )
        monitor.record_metric(metric)

        # Metrics are keyed by "METHOD endpoint" so GET/POST to the same path
        # don't collide (matches get_report's lookup key).
        assert "GET /api/v1/workflows" in monitor.metrics
        assert len(monitor.metrics["GET /api/v1/workflows"]) == 1

    def test_get_report(self) -> None:
        """Test report generation."""
        monitor = PerformanceMonitor()

        # Record multiple metrics
        for i in range(100):
            metric = APIMetric(
                endpoint="/api/v1/workflows",
                method="GET",
                status_code=200,
                response_time=0.1 + (i * 0.001),
            )
            monitor.record_metric(metric)

        report = monitor.get_report("/api/v1/workflows", "GET")

        assert report.total_requests == 100
        assert report.successful_requests == 100
        assert report.failed_requests == 0
        assert report.avg_response_time > 0
        assert report.p95_response_time > report.avg_response_time

    def test_performance_alert(self) -> None:
        """Test performance alerts."""
        alert = PerformanceAlert(
            response_time_threshold=0.5,
            error_rate_threshold=5.0,
        )

        report = PerformanceReport(
            endpoint="/api/v1/workflows",
            method="GET",
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            avg_response_time=1.0,
            error_rate=5.0,
        )

        alerts = alert.check_report(report)

        assert len(alerts) > 0
        assert any("response time" in a for a in alerts)


# ============================================================================
# Integration Tests
# ============================================================================

class TestPerformanceOptimizationIntegration:
    """Integration tests for performance optimizations."""

    @pytest.mark.asyncio
    async def test_cache_warming(self) -> None:
        """Test cache warming."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)
        warmer = CacheWarmer(cache)

        async def loader() -> dict[str, str]:
            return {"key1": "value1", "key2": "value2"}

        await warmer.warm_cache("test", loader, ttl=60)

        result = await cache.get("test")
        assert result is not None

    @pytest.mark.asyncio
    async def test_cache_invalidation(self) -> None:
        """Test cache invalidation."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)

        await cache.set("workflow:1", {"data": "value"})
        await cache.set("workflow:2", {"data": "value"})

        await CacheInvalidationStrategy.invalidate_on_update(
            cache,
            "workflow",
            "1",
        )

        assert await cache.get("workflow:1") is None
        assert await cache.get("workflow:2") == {"data": "value"}

    def test_response_optimization_pipeline(self) -> None:
        """Test complete response optimization pipeline."""
        items = [
            {"id": "1", "name": "item1", "email": "item1@example.com"},
            {"id": "2", "name": "item2", "email": "item2@example.com"},
        ]

        # Build optimized response with field selection
        response = ResponseOptimizer.build_list_response(
            items=items,
            total=2,
            page=1,
            page_size=20,
            include_fields=["id", "name"],
        )

        assert len(response["items"]) == 2
        assert "email" not in response["items"][0]
        assert "id" in response["items"][0]
        assert "name" in response["items"][0]
