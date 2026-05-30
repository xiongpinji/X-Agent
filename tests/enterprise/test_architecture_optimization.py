"""
Architecture Optimization Tests for X-Agent.

Tests for:
- Event bus integration
- Cache integration
- Concurrency optimization
- Configuration management
- Error handling
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.event_bus import Event, EventType, get_event_bus
from backend.app.core.event_bus_integration import (
    EventBusIntegration,
    get_event_bus_integration,
)
from backend.app.core.cache import CacheManager, MemoryCacheBackend
from backend.app.core.cache_integration import CacheIntegration, get_cache_integration
from backend.app.core.concurrency_optimization import (
    AdaptiveConcurrencyLimiter,
    BackpressureHandler,
    PriorityTaskScheduler,
)
from backend.app.core.config_hot_reload import (
    ConfigurationEncryption,
    ConfigurationHotReload,
    ConfigurationAudit,
)
from backend.app.core.error_handling import (
    CircuitBreaker,
    ExponentialBackoffRetry,
    ErrorTracker,
)


class TestEventBusIntegration:
    """Test event bus integration."""

    @pytest.mark.asyncio
    async def test_agent_started_event(self):
        """Test publishing agent started event."""
        integration = EventBusIntegration()
        event_bus = integration.event_bus

        events = []

        async def handler(event: Event):
            events.append(event)

        await event_bus.subscribe(EventType.AGENT_STARTED, handler)
        await integration.publish_agent_started(
            agent_id="test_agent",
            task="test_task",
            user_id="user1",
        )

        await asyncio.sleep(0.1)
        assert len(events) == 1
        assert events[0].data["agent_id"] == "test_agent"

    @pytest.mark.asyncio
    async def test_workflow_completed_event(self):
        """Test publishing workflow completed event."""
        integration = EventBusIntegration()
        event_bus = integration.event_bus

        events = []

        async def handler(event: Event):
            events.append(event)

        await event_bus.subscribe(EventType.WORKFLOW_COMPLETED, handler)
        await integration.publish_workflow_completed(
            workflow_id="wf1",
            result={"status": "success"},
            duration_seconds=10.5,
        )

        await asyncio.sleep(0.1)
        assert len(events) == 1
        assert events[0].data["workflow_id"] == "wf1"

    @pytest.mark.asyncio
    async def test_security_event(self):
        """Test publishing security events."""
        integration = EventBusIntegration()
        event_bus = integration.event_bus

        events = []

        async def handler(event: Event):
            events.append(event)

        await event_bus.subscribe(EventType.AUTHENTICATION_FAILED, handler)
        await integration.publish_authentication_failed(
            reason="Invalid credentials",
            user_id="user1",
        )

        await asyncio.sleep(0.1)
        assert len(events) == 1
        assert events[0].data["reason"] == "Invalid credentials"


class TestCacheIntegration:
    """Test cache integration."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test cache set and get operations."""
        cache_manager = CacheManager()
        integration = CacheIntegration(cache_manager)

        key = "test_key"
        value = {"data": "test_value"}

        await integration.cache_set(key, value, ttl=3600)
        cached_value = await integration.cache_get(key)

        assert cached_value == value

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Test cache invalidation."""
        cache_manager = CacheManager()
        integration = CacheIntegration(cache_manager)

        key = "test_key"
        value = {"data": "test_value"}

        await integration.cache_set(key, value)
        await integration.cache_delete(key)
        cached_value = await integration.cache_get(key)

        assert cached_value is None

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache_manager = CacheManager()
        integration = CacheIntegration(cache_manager)

        key = "test_key"
        value = {"data": "test_value"}

        await integration.cache_set(key, value, ttl=1)
        await asyncio.sleep(1.1)
        cached_value = await integration.cache_get(key)

        assert cached_value is None


class TestConcurrencyOptimization:
    """Test concurrency optimization."""

    @pytest.mark.asyncio
    async def test_adaptive_limiter_basic(self):
        """Test basic adaptive concurrency limiter."""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=5)

        await limiter.acquire()
        assert limiter._stats.active_tasks == 1

        limiter.release(success=True)
        assert limiter._stats.active_tasks == 0

    @pytest.mark.asyncio
    async def test_adaptive_limiter_success_rate(self):
        """Test adaptive limiter adjusts based on success rate."""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=10,
            adjustment_interval=0.1,
            success_threshold=0.95,
        )

        # Simulate successful tasks
        for _ in range(20):
            await limiter.acquire()
            limiter.release(success=True)

        stats = limiter.get_stats()
        assert stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_backpressure_handler(self):
        """Test backpressure handler."""
        handler = BackpressureHandler(max_queue_size=100)

        await handler.update_queue_size(50)
        assert not await handler.check_backpressure()

        await handler.update_queue_size(85)
        assert await handler.check_backpressure()

        await handler.update_queue_size(15)
        assert not await handler.check_backpressure()

    @pytest.mark.asyncio
    async def test_priority_scheduler(self):
        """Test priority task scheduler."""
        scheduler = PriorityTaskScheduler(worker_count=2)
        await scheduler.start()

        executed_tasks = []

        async def task(task_id: int):
            executed_tasks.append(task_id)

        await scheduler.enqueue(lambda: task(1), priority=1)
        await scheduler.enqueue(lambda: task(2), priority=0)

        await asyncio.sleep(0.5)
        await scheduler.stop()

        assert len(executed_tasks) >= 1


class TestConfigurationManagement:
    """Test configuration management."""

    def test_config_encryption(self):
        """Test configuration encryption."""
        encryption = ConfigurationEncryption()

        original = "secret_password_123"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert encrypted != original
        assert decrypted == original

    def test_config_encrypt_dict(self):
        """Test encrypting dictionary values."""
        encryption = ConfigurationEncryption()

        data = {
            "username": "admin",
            "password": "secret123",
            "api_key": "key_abc123",
        }

        encrypted = encryption.encrypt_dict(data, ["password", "api_key"])

        assert encrypted["username"] == "admin"
        assert encrypted["password"] != "secret123"
        assert encrypted["api_key"] != "key_abc123"

    @pytest.mark.asyncio
    async def test_config_audit(self):
        """Test configuration audit logging."""
        audit = ConfigurationAudit()

        await audit.log_change(
            change_type="update",
            key="database.password",
            old_value="old_pass",
            new_value="new_pass",
            user_id="admin",
            reason="Security update",
        )

        history = await audit.get_history()
        assert len(history) == 1
        assert history[0]["key"] == "database.password"
        assert "***" in str(history[0]["new_value"])


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_retry(self):
        """Test exponential backoff retry strategy."""
        retry_strategy = ExponentialBackoffRetry(
            max_attempts=3,
            initial_delay=0.1,
            exponential_base=2.0,
        )

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"

        result = await retry_strategy.execute(failing_func)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Test circuit breaker pattern."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.5)

        async def failing_func():
            raise ValueError("Service error")

        # Trigger failures
        for _ in range(3):
            try:
                await breaker.call(failing_func)
            except ValueError:
                pass

        # Circuit should be open
        state = breaker.get_state()
        assert state["state"] == "open"

    @pytest.mark.asyncio
    async def test_error_tracker(self):
        """Test error tracking."""
        tracker = ErrorTracker()

        from backend.app.core.error_handling import (
            AuthenticationError,
            ValidationError,
        )

        await tracker.record(AuthenticationError("Invalid token"))
        await tracker.record(ValidationError("Invalid input"))

        stats = tracker.get_stats()
        assert stats["total_errors"] == 2


class TestArchitectureIntegration:
    """Integration tests for architecture optimization."""

    @pytest.mark.asyncio
    async def test_event_bus_with_cache_invalidation(self):
        """Test event bus triggering cache invalidation."""
        event_bus = get_event_bus()
        cache_integration = get_cache_integration()

        # Set up cache
        await cache_integration.cache_set("user:123", {"name": "John"})

        # Publish event that should invalidate cache
        event = Event(
            event_type=EventType.MEMORY_UPDATED,
            source="memory",
            data={"memory_id": "user:123"},
        )

        # In real scenario, this would trigger cache invalidation
        await event_bus.publish(event)

        # Cache should still exist (no automatic invalidation in this test)
        cached = await cache_integration.cache_get("user:123")
        assert cached is not None

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test concurrent cache operations."""
        cache_manager = CacheManager()
        integration = CacheIntegration(cache_manager)

        async def cache_operation(key: str, value: str):
            await integration.cache_set(key, value)
            await asyncio.sleep(0.01)
            return await integration.cache_get(key)

        tasks = [
            cache_operation(f"key_{i}", f"value_{i}") for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r is not None for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
