"""Full-coverage unit tests for backend.app.core.performance_optimization.

Covers:
- CacheEntry: is_expired
- ResponseCache: get, set, invalidate, get_stats
- cached_response decorator
- QueryOptimizer: record_query, get_percentile, get_stats
- BatchLoader: load, load_many, _process_batch, clear_cache
- MultiLayerCache: get, set, get_stats
- PoolStats dataclass
- OptimizedConnectionPool: initialize, acquire, release, close, get_stats
- AdaptiveRateLimiter: acquire, adjust_limit
- MemoryOptimizer: get_memory_usage_mb, optimize, get_stats
- PerformanceMetrics: meets_targets
- PerformanceMonitor: record_metrics, get_current_metrics, generate_report
"""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip entire module if psutil is not installed
pytest.importorskip("psutil", reason="psutil not installed")

from backend.app.core.performance_optimization import (
    AdaptiveRateLimiter,
    BatchLoader,
    CacheEntry,
    MemoryOptimizer,
    MultiLayerCache,
    OptimizedConnectionPool,
    PerformanceMetrics,
    PerformanceMonitor,
    PoolStats,
    QueryOptimizer,
    ResponseCache,
    cached_response,
)


# ---------------------------------------------------------------------------
# CacheEntry
# ---------------------------------------------------------------------------

class TestCacheEntry:
    def test_is_expired_false(self):
        entry = CacheEntry(value="v", created_at=datetime.now(UTC), ttl_seconds=100)
        assert entry.is_expired() is False

    def test_is_expired_true(self):
        entry = CacheEntry(
            value="v",
            created_at=datetime.now(UTC) - timedelta(seconds=200),
            ttl_seconds=100,
        )
        assert entry.is_expired() is True


# ---------------------------------------------------------------------------
# ResponseCache
# ---------------------------------------------------------------------------

class TestResponseCache:
    async def test_get_set(self):
        cache = ResponseCache()
        assert await cache.get("key") is None
        await cache.set("key", {"data": 1})
        assert await cache.get("key") == {"data": 1}

    async def test_get_expired(self):
        cache = ResponseCache()
        await cache.set("key", "val", ttl_seconds=0)
        # Manually expire
        cache.cache["key"].created_at = datetime.now(UTC) - timedelta(seconds=1)
        assert await cache.get("key") is None

    async def test_set_evicts_lru(self):
        cache = ResponseCache(max_size_mb=0)  # 0 bytes max
        cache.max_size_bytes = 1  # force tiny limit
        await cache.set("a", "x" * 100)
        await cache.set("b", "y" * 100)
        # "a" should be evicted (lower hit_count)
        assert await cache.get("a") is None

    async def test_invalidate(self):
        cache = ResponseCache()
        await cache.set("user:1", "a")
        await cache.set("user:2", "b")
        await cache.set("session:1", "c")
        count = await cache.invalidate("user:")
        assert count == 2
        assert await cache.get("user:1") is None
        assert await cache.get("session:1") == "c"

    async def test_invalidate_no_match(self):
        cache = ResponseCache()
        await cache.set("key", "val")
        count = await cache.invalidate("nonexistent")
        assert count == 0

    def test_get_stats(self):
        cache = ResponseCache()
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0
        assert stats["entries"] == 0

    async def test_get_stats_with_data(self):
        cache = ResponseCache()
        await cache.set("k", "v")
        await cache.get("k")  # hit
        await cache.get("missing")  # miss
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0


# ---------------------------------------------------------------------------
# cached_response decorator
# ---------------------------------------------------------------------------

class TestCachedResponseDecorator:
    async def test_basic_caching(self):
        call_count = {"n": 0}

        @cached_response(ttl_seconds=60)
        async def compute(x: int) -> int:
            call_count["n"] += 1
            return x * 2

        result1 = await compute(5)
        assert result1 == 10
        assert call_count["n"] == 1

        result2 = await compute(5)
        assert result2 == 10
        assert call_count["n"] == 1  # cached

    async def test_custom_key_builder(self):
        @cached_response(ttl_seconds=60, key_builder=lambda x: f"key-{x}")
        async def fetch(x: int) -> str:
            return f"result-{x}"

        r1 = await fetch(1)
        assert r1 == "result-1"
        r2 = await fetch(1)
        assert r2 == "result-1"

    async def test_different_args_not_cached(self):
        call_count = {"n": 0}

        @cached_response(ttl_seconds=60)
        async def compute(x: int) -> int:
            call_count["n"] += 1
            return x * 3

        await compute(1)
        await compute(2)
        assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# QueryOptimizer
# ---------------------------------------------------------------------------

class TestQueryOptimizer:
    def test_record_query(self):
        opt = QueryOptimizer()
        opt.record_query("SELECT 1", 10.0)
        opt.record_query("SELECT 2", 60.0)
        assert len(opt.query_times) == 2
        assert len(opt.slow_queries) == 1  # 60 > 50 threshold

    def test_slow_queries_capped_at_100(self):
        opt = QueryOptimizer()
        for i in range(150):
            opt.record_query(f"q{i}", 100.0)
        assert len(opt.slow_queries) == 100

    def test_get_percentile_empty(self):
        opt = QueryOptimizer()
        assert opt.get_percentile(50) == 0.0

    def test_get_percentile(self):
        opt = QueryOptimizer()
        for i in range(1, 101):
            opt.record_query(f"q{i}", float(i))
        # index = int(100 * 50/100) = 50 -> sorted_times[50] = 51
        assert opt.get_percentile(50) == 51.0
        assert opt.get_percentile(95) == 96.0

    def test_get_stats_empty(self):
        opt = QueryOptimizer()
        stats = opt.get_stats()
        assert stats["avg_ms"] == 0
        assert stats["slow_queries"] == 0

    def test_get_stats_with_data(self):
        opt = QueryOptimizer()
        opt.record_query("q1", 10.0)
        opt.record_query("q2", 20.0)
        opt.record_query("q3", 60.0)
        stats = opt.get_stats()
        assert stats["avg_ms"] == 30.0
        assert stats["slow_queries"] == 1
        assert stats["total_queries"] == 3


# ---------------------------------------------------------------------------
# BatchLoader
# ---------------------------------------------------------------------------

class TestBatchLoader:
    async def test_load_single(self):
        async def batch_fn(keys):
            return [f"value-{k}" for k in keys]

        loader = BatchLoader(batch_fn, batch_size=10)
        result = await loader.load("key1")
        assert result == "value-key1"

    async def test_load_cached(self):
        call_count = {"n": 0}

        async def batch_fn(keys):
            call_count["n"] += 1
            return [f"v-{k}" for k in keys]

        loader = BatchLoader(batch_fn, batch_size=10)
        r1 = await loader.load("k")
        r2 = await loader.load("k")  # cached
        assert r1 == r2
        assert call_count["n"] == 1

    async def test_load_many(self):
        async def batch_fn(keys):
            return [k.upper() for k in keys]

        loader = BatchLoader(batch_fn, batch_size=10)
        results = await loader.load_many(["a", "b", "c"])
        assert results == ["A", "B", "C"]

    async def test_batch_fn_error(self):
        async def failing_fn(keys):
            raise ValueError("db error")

        loader = BatchLoader(failing_fn, batch_size=10)
        with pytest.raises(ValueError, match="db error"):
            await loader.load("key")

    def test_clear_cache(self):
        async def batch_fn(keys):
            return keys

        loader = BatchLoader(batch_fn)
        loader._cache["k"] = "v"
        loader.clear_cache()
        assert len(loader._cache) == 0


# ---------------------------------------------------------------------------
# MultiLayerCache
# ---------------------------------------------------------------------------

class TestMultiLayerCache:
    async def test_get_set_l1_only(self):
        cache = MultiLayerCache()
        assert await cache.get("key") is None
        await cache.set("key", {"data": 1})
        assert await cache.get("key") == {"data": 1}
        assert cache.l1_hits == 1

    async def test_l2_hit(self):
        import json
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps({"x": 1}))
        cache = MultiLayerCache(redis_client=mock_redis)
        result = await cache.get("key")
        assert result == {"x": 1}
        assert cache.l2_hits == 1

    async def test_l2_miss(self):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache = MultiLayerCache(redis_client=mock_redis)
        result = await cache.get("key")
        assert result is None
        assert cache.misses == 1

    async def test_l2_error(self):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("redis down"))
        cache = MultiLayerCache(redis_client=mock_redis)
        result = await cache.get("key")
        assert result is None
        assert cache.misses == 1

    async def test_set_writes_to_l2(self):
        import json
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        cache = MultiLayerCache(redis_client=mock_redis)
        await cache.set("key", {"v": 1}, ttl_seconds=60)
        mock_redis.setex.assert_called_once()
        # Verify L1 also has it
        assert await cache.get("key") == {"v": 1}

    async def test_set_l2_error(self):
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=Exception("write fail"))
        cache = MultiLayerCache(redis_client=mock_redis)
        await cache.set("key", "val")  # should not raise
        assert await cache.get("key") == "val"

    def test_get_stats(self):
        cache = MultiLayerCache()
        stats = cache.get_stats()
        assert stats["l1_hits"] == 0
        assert stats["l2_hits"] == 0
        assert stats["misses"] == 0
        assert stats["total_hit_rate"] == 0


# ---------------------------------------------------------------------------
# PoolStats
# ---------------------------------------------------------------------------

class TestPoolStats:
    def test_defaults(self):
        stats = PoolStats()
        assert stats.total_connections == 0
        assert stats.errors == 0


# ---------------------------------------------------------------------------
# OptimizedConnectionPool
# ---------------------------------------------------------------------------

class TestOptimizedConnectionPool:
    async def _make_pool(self, min_size=2, max_size=5):
        counter = {"n": 0}

        async def factory():
            counter["n"] += 1
            return f"conn-{counter['n']}"

        return OptimizedConnectionPool(factory, min_size=min_size, max_size=max_size)

    async def test_initialize(self):
        pool = await self._make_pool(min_size=3)
        await pool.initialize()
        assert pool.get_stats().total_connections == 3
        await pool.close()

    async def test_initialize_idempotent(self):
        pool = await self._make_pool()
        await pool.initialize()
        await pool.initialize()
        assert pool.get_stats().total_connections == 2
        await pool.close()

    async def test_acquire_release(self):
        pool = await self._make_pool()
        conn = await pool.acquire()
        assert conn is not None
        stats = pool.get_stats()
        assert stats.active_connections == 1
        await pool.release(conn)
        assert pool.get_stats().active_connections == 0
        await pool.close()

    async def test_acquire_creates_new(self):
        pool = await self._make_pool(min_size=1, max_size=5)
        c1 = await pool.acquire()
        c2 = await pool.acquire()
        assert c1 != c2
        await pool.release(c1)
        await pool.release(c2)
        await pool.close()

    async def test_acquire_timeout(self):
        pool = await self._make_pool(min_size=1, max_size=1)
        pool._timeout = 0.1
        conn = await pool.acquire()
        with pytest.raises(TimeoutError):
            await pool.acquire()
        await pool.release(conn)
        await pool.close()

    async def test_acquire_factory_error(self):
        call_count = {"n": 0}

        async def factory():
            call_count["n"] += 1
            if call_count["n"] > 1:
                raise ConnectionError("fail")
            return "conn-1"

        pool = OptimizedConnectionPool(factory, min_size=1, max_size=3)
        c1 = await pool.acquire()
        await pool.release(c1)
        c2 = await pool.acquire()
        # Next acquire tries to create new -> fails
        with pytest.raises(ConnectionError):
            await pool.acquire()
        await pool.release(c2)
        await pool.close()

    async def test_close_with_async_close(self):
        async def factory():
            mock = AsyncMock()
            mock.close = AsyncMock()
            return mock

        pool = OptimizedConnectionPool(factory, min_size=1)
        await pool.initialize()
        await pool.close()
        assert pool._initialized is False

    async def test_close_with_sync_close(self):
        async def factory():
            mock = MagicMock()
            mock.close = MagicMock()
            return mock

        pool = OptimizedConnectionPool(factory, min_size=1)
        await pool.initialize()
        await pool.close()

    async def test_close_without_close_method(self):
        async def factory():
            return object()

        pool = OptimizedConnectionPool(factory, min_size=1)
        await pool.initialize()
        await pool.close()  # should not raise

    async def test_init_factory_error(self):
        async def factory():
            raise ConnectionError("cannot connect")

        pool = OptimizedConnectionPool(factory, min_size=3)
        await pool.initialize()
        assert pool.get_stats().errors == 3
        assert pool.get_stats().total_connections == 0


# ---------------------------------------------------------------------------
# AdaptiveRateLimiter
# ---------------------------------------------------------------------------

class TestAdaptiveRateLimiter:
    async def test_acquire_under_limit(self):
        limiter = AdaptiveRateLimiter(base_rps=100)
        await limiter.acquire()
        assert len(limiter.request_times) == 1

    async def test_acquire_over_limit_waits(self):
        limiter = AdaptiveRateLimiter(base_rps=2, window_seconds=0.1)
        await limiter.acquire()
        await limiter.acquire()
        # Third should wait
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        assert elapsed >= 0.05  # waited some time

    def test_adjust_limit_high_load(self):
        limiter = AdaptiveRateLimiter(base_rps=1000)
        limiter.adjust_limit(cpu_percent=90, memory_percent=50)
        assert limiter.current_limit == 800  # 1000 * 0.8

    def test_adjust_limit_low_load(self):
        limiter = AdaptiveRateLimiter(base_rps=1000)
        limiter.current_limit = 1000
        limiter.adjust_limit(cpu_percent=10, memory_percent=10)
        assert limiter.current_limit == 1200  # 1000 * 1.2

    def test_adjust_limit_medium_load(self):
        limiter = AdaptiveRateLimiter(base_rps=1000)
        limiter.current_limit = 1000
        limiter.adjust_limit(cpu_percent=50, memory_percent=50)
        assert limiter.current_limit == 1000  # unchanged

    def test_adjust_limit_min_cap(self):
        limiter = AdaptiveRateLimiter(base_rps=1000)
        limiter.current_limit = 100
        limiter.adjust_limit(cpu_percent=95, memory_percent=95)
        assert limiter.current_limit == 100  # min cap

    def test_adjust_limit_max_cap(self):
        limiter = AdaptiveRateLimiter(base_rps=1000)
        limiter.current_limit = 2000
        limiter.adjust_limit(cpu_percent=10, memory_percent=10)
        assert limiter.current_limit == 2000  # max cap = base_rps * 2


# ---------------------------------------------------------------------------
# MemoryOptimizer
# ---------------------------------------------------------------------------

class TestMemoryOptimizer:
    def test_get_memory_usage_mb(self):
        opt = MemoryOptimizer()
        mb = opt.get_memory_usage_mb()
        assert mb > 0

    def test_optimize(self):
        opt = MemoryOptimizer()
        result = opt.optimize()
        assert "before_mb" in result
        assert "after_mb" in result
        assert "freed_mb" in result
        assert result["gc_count"] == 1

    def test_optimize_samples_capped(self):
        opt = MemoryOptimizer()
        opt.memory_samples = [100.0] * 1000
        opt.optimize()
        assert len(opt.memory_samples) == 1000  # capped, not 1001

    def test_get_stats(self):
        opt = MemoryOptimizer(target_memory_mb=1000)
        stats = opt.get_stats()
        assert stats["target_mb"] == 1000
        assert stats["current_mb"] > 0
        assert "utilization_percent" in stats
        assert stats["gc_count"] == 0
        assert stats["avg_memory_mb"] == 0  # no samples


# ---------------------------------------------------------------------------
# PerformanceMetrics
# ---------------------------------------------------------------------------

class TestPerformanceMetrics:
    def test_meets_targets_true(self):
        m = PerformanceMetrics(
            api_response_time_p95_ms=50,
            database_query_time_p95_ms=20,
            cache_hit_rate_percent=95,
            concurrent_requests_rps=2000,
            memory_usage_mb=200,
        )
        assert m.meets_targets() is True

    def test_meets_targets_false(self):
        m = PerformanceMetrics(
            api_response_time_p95_ms=150,
            database_query_time_p95_ms=60,
            cache_hit_rate_percent=80,
            concurrent_requests_rps=500,
            memory_usage_mb=600,
        )
        assert m.meets_targets() is False


# ---------------------------------------------------------------------------
# PerformanceMonitor
# ---------------------------------------------------------------------------

class TestPerformanceMonitor:
    def test_record_metrics(self):
        mon = PerformanceMonitor()
        m = PerformanceMetrics(api_response_time_p95_ms=50)
        mon.record_metrics(m)
        assert len(mon.metrics_history) == 1

    def test_record_metrics_capped(self):
        mon = PerformanceMonitor()
        mon.metrics_history = [PerformanceMetrics()] * 1000
        mon.record_metrics(PerformanceMetrics())
        assert len(mon.metrics_history) == 1000

    def test_get_current_metrics(self):
        mon = PerformanceMonitor()
        metrics = mon.get_current_metrics()
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.memory_usage_mb > 0

    def test_generate_report_empty(self):
        mon = PerformanceMonitor()
        report = mon.generate_report()
        assert "暂无性能数据" in report

    def test_generate_report_with_data_meets_targets(self):
        mon = PerformanceMonitor()
        m = PerformanceMetrics(
            api_response_time_p95_ms=50,
            database_query_time_p95_ms=20,
            cache_hit_rate_percent=95,
            concurrent_requests_rps=2000,
            memory_usage_mb=200,
        )
        mon.record_metrics(m)
        mon.query_optimizer.record_query("SELECT 1", 10.0)
        report = mon.generate_report()
        assert "所有性能目标已达成" in report
        assert "数据库查询统计" in report

    def test_generate_report_not_meeting_targets(self):
        mon = PerformanceMonitor()
        m = PerformanceMetrics(
            api_response_time_p95_ms=150,
            database_query_time_p95_ms=60,
            cache_hit_rate_percent=80,
            concurrent_requests_rps=500,
            memory_usage_mb=600,
        )
        mon.record_metrics(m)
        report = mon.generate_report()
        assert "API响应时间未达成" in report
        assert "数据库查询时间未达成" in report
        assert "缓存命中率未达成" in report
        assert "并发处理未达成" in report
        assert "内存使用未达成" in report
