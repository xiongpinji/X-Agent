"""
Tests for concurrency control and connection pool management.

Tests:
- Connection pool creation and lifecycle
- Concurrency limiting
- Rate limiting
- Task queue
- Resource monitoring
- Stress testing
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.core.pools import (
    ConnectionPool,
    PoolConfig,
    PostgresPool,
    RedisPool,
    HTTPClientPool,
)
from backend.app.core.concurrency_limiter import (
    ConcurrencyLimiter,
    AdaptiveConcurrencyLimiter,
    RateLimiter,
    PriorityTaskQueue,
    TaskPriority,
)
from backend.app.core.http_client import HTTPClientManager
from backend.app.core.resource_monitor import ResourceMonitor, ResourceAlert
from backend.app.core.concurrency_manager import (
    ConcurrencyManager,
    ConcurrencyConfig,
)


class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test pool initialization."""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return MagicMock()

        config = PoolConfig(min_size=3, max_size=10)
        pool = ConnectionPool(factory, config, name="test_pool")

        await pool.initialize()
        assert call_count == 3
        assert pool.get_stats().total_connections == 3

        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_acquire_release(self):
        """Test acquiring and releasing connections."""
        async def factory():
            return MagicMock()

        config = PoolConfig(min_size=2, max_size=5)
        pool = ConnectionPool(factory, config, name="test_pool")

        await pool.initialize()
        conn1 = await pool.acquire()
        assert pool.get_stats().active_connections == 1

        conn2 = await pool.acquire()
        assert pool.get_stats().active_connections == 2

        await pool.release(conn1)
        assert pool.get_stats().active_connections == 1

        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_max_size_limit(self):
        """Test pool respects max size limit."""
        async def factory():
            return MagicMock()

        config = PoolConfig(min_size=1, max_size=3, timeout=0.1)
        pool = ConnectionPool(factory, config, name="test_pool")

        await pool.initialize()
        conns = []

        # Acquire up to max size
        for _ in range(3):
            conn = await pool.acquire()
            conns.append(conn)

        assert pool.get_stats().total_connections == 3

        # Try to acquire beyond max size should timeout
        with pytest.raises(asyncio.TimeoutError):
            await pool.acquire()

        # Release and try again
        await pool.release(conns[0])
        conn = await pool.acquire()
        assert conn is not None

        await pool.close()


class TestConcurrencyLimiter:
    """Test concurrency limiting."""

    @pytest.mark.asyncio
    async def test_limiter_basic(self):
        """Test basic concurrency limiting."""
        limiter = ConcurrencyLimiter(max_concurrent=2, name="test_limiter")

        await limiter.acquire()
        await limiter.acquire()
        assert limiter.get_stats()["active_tasks"] == 2

        limiter.release()
        assert limiter.get_stats()["active_tasks"] == 1

        limiter.release()
        assert limiter.get_stats()["active_tasks"] == 0

    @pytest.mark.asyncio
    async def test_limiter_context_manager(self):
        """Test limiter as context manager."""
        limiter = ConcurrencyLimiter(max_concurrent=1, name="test_limiter")

        async with limiter:
            assert limiter.get_stats()["active_tasks"] == 1

        assert limiter.get_stats()["active_tasks"] == 0

    @pytest.mark.asyncio
    async def test_adaptive_limiter(self):
        """Test adaptive concurrency limiting."""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=5,
            min_limit=2,
            max_limit=10,
            adjustment_interval=0.1,
            name="test_adaptive",
        )

        await limiter.initialize()

        # Simulate successful tasks
        for _ in range(20):
            await limiter.acquire()
            limiter.release(success=True)

        # Wait for adjustment
        await asyncio.sleep(0.2)

        stats = limiter.get_stats()
        assert stats["success_rate"] > 0.9

        await limiter.close()


class TestRateLimiter:
    """Test rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self):
        """Test basic rate limiting."""
        limiter = RateLimiter(rate=10.0, burst=10, name="test_rate")

        # Should allow up to burst
        for _ in range(10):
            assert await limiter.acquire(1)

        # Should reject beyond burst
        assert not await limiter.acquire(1)

    @pytest.mark.asyncio
    async def test_rate_limiter_refill(self):
        """Test rate limiter token refill."""
        limiter = RateLimiter(rate=10.0, burst=5, name="test_rate")

        # Use all tokens
        for _ in range(5):
            assert await limiter.acquire(1)

        # Should reject
        assert not await limiter.acquire(1)

        # Wait for refill
        await asyncio.sleep(0.2)

        # Should allow again
        assert await limiter.acquire(1)


class TestPriorityTaskQueue:
    """Test priority task queue."""

    @pytest.mark.asyncio
    async def test_queue_basic(self):
        """Test basic queue operations."""
        queue = PriorityTaskQueue(
            max_queue_size=100,
            worker_count=2,
            name="test_queue",
        )

        await queue.start()

        executed = []

        async def task(value):
            executed.append(value)

        await queue.enqueue(lambda: task(1), priority=TaskPriority.NORMAL)
        await queue.enqueue(lambda: task(2), priority=TaskPriority.HIGH)

        await asyncio.sleep(0.5)
        await queue.stop()

        assert len(executed) == 2

    @pytest.mark.asyncio
    async def test_queue_priority(self):
        """Test queue respects priority."""
        queue = PriorityTaskQueue(
            max_queue_size=100,
            worker_count=1,
            name="test_queue",
        )

        await queue.start()

        executed = []
        lock = asyncio.Lock()

        async def task(value):
            async with lock:
                executed.append(value)
            await asyncio.sleep(0.1)

        # Enqueue in order: normal, low, high
        await queue.enqueue(lambda: task(1), priority=TaskPriority.NORMAL)
        await queue.enqueue(lambda: task(2), priority=TaskPriority.LOW)
        await queue.enqueue(lambda: task(3), priority=TaskPriority.HIGH)

        await asyncio.sleep(0.5)
        await queue.stop()

        # All three tasks ran.
        assert set(executed) == {1, 2, 3}
        # The defining invariant of a priority queue: when multiple tasks are
        # waiting, the higher-priority one is popped first.  Tasks 2 (LOW) and 3
        # (HIGH) are always both queued by the time the single worker picks the
        # next item, so HIGH must execute before LOW regardless of whether the
        # worker happened to grab task 1 before the others were enqueued (which
        # is a racy timing detail, not a priority guarantee).
        assert executed.index(3) < executed.index(2)  # HIGH before LOW


class TestResourceMonitor:
    """Test resource monitoring."""

    @pytest.mark.asyncio
    async def test_monitor_initialization(self):
        """Test monitor initialization."""
        monitor = ResourceMonitor(check_interval=0.1)

        await monitor.start()
        assert monitor._running

        await monitor.stop()
        assert not monitor._running

    @pytest.mark.asyncio
    async def test_monitor_alerts(self):
        """Test monitor alert generation."""
        monitor = ResourceMonitor(check_interval=0.1)

        alerts_received = []

        def alert_callback(alert: ResourceAlert):
            alerts_received.append(alert)

        monitor.add_alert_callback(alert_callback)

        # Create mock pool with high utilization
        mock_pool = MagicMock()
        mock_pool.get_stats.return_value = MagicMock(
            total_connections=10,
            active_connections=9,
            idle_connections=1,
            errors=0,
        )

        await monitor.register_pool("test_pool", mock_pool)
        await monitor.start()

        await asyncio.sleep(0.3)
        await monitor.stop()

        # Should have generated alert
        assert len(alerts_received) > 0


class TestHTTPClientManager:
    """Test HTTP client manager."""

    @pytest.mark.asyncio
    async def test_http_client_initialization(self):
        """Test HTTP client initialization."""
        manager = HTTPClientManager(
            max_connections=10,
            timeout=30.0,
        )

        await manager.initialize()
        assert manager._client is not None

        await manager.close()
        assert manager._client is None

    @pytest.mark.asyncio
    async def test_http_client_stats(self):
        """Test HTTP client statistics."""
        manager = HTTPClientManager()

        stats = manager.get_stats()
        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0


class TestConcurrencyManager:
    """Test concurrency manager."""

    @pytest.mark.asyncio
    async def test_manager_initialization(self):
        """Test manager initialization."""
        config = ConcurrencyConfig(
            pool_min_size=2,
            pool_max_size=5,
            default_concurrency_limit=5,
        )

        manager = ConcurrencyManager(config)

        # Initialize without database/redis
        await manager.initialize()
        assert manager._initialized

        await manager.shutdown()
        assert not manager._initialized

    @pytest.mark.asyncio
    async def test_manager_metrics(self):
        """Test manager metrics collection."""
        config = ConcurrencyConfig()
        manager = ConcurrencyManager(config)

        await manager.initialize()

        metrics = manager.get_metrics()
        assert "timestamp" in metrics
        assert "components" in metrics

        await manager.shutdown()


class TestStressScenarios:
    """Stress test scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_pool_access(self):
        """Test concurrent access to pool."""
        async def factory():
            return MagicMock()

        config = PoolConfig(min_size=5, max_size=20)
        pool = ConnectionPool(factory, config, name="stress_pool")

        await pool.initialize()

        async def worker():
            for _ in range(10):
                conn = await pool.acquire()
                await asyncio.sleep(0.01)
                await pool.release(conn)

        # Run 10 concurrent workers
        await asyncio.gather(*[worker() for _ in range(10)])

        stats = pool.get_stats()
        assert stats.total_acquired == 100
        assert stats.total_released == 100

        await pool.close()

    @pytest.mark.asyncio
    async def test_limiter_under_load(self):
        """Test limiter under load."""
        limiter = ConcurrencyLimiter(max_concurrent=5, name="stress_limiter")

        async def task():
            await limiter.acquire()
            try:
                await asyncio.sleep(0.01)
            finally:
                limiter.release(success=True)

        # Run 50 tasks with max 5 concurrent
        await asyncio.gather(*[task() for _ in range(50)])

        stats = limiter.get_stats()
        assert stats["total_tasks"] == 50
        assert stats["successful_tasks"] == 50
        assert stats["peak_active"] <= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
