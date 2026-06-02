"""
Comprehensive tests for stability enhancement modules.

Tests circuit breaker, degradation, distributed lock, and retry mechanisms.
"""

import pytest
import time
from unittest.mock import Mock, patch

from backend.app.core.stability_circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerException,
    get_circuit_breaker_registry,
)
from backend.app.core.stability_degradation import (
    DegradationStrategy,
    DegradationLevel,
    FeatureStatus,
    FeatureConfig,
    get_degradation_strategy,
)
from backend.app.core.stability_distributed_lock import (
    DistributedLock,
    DistributedLockConfig,
    get_lock_manager,
)
from backend.app.core.stability_retry import (
    RetryExecutor,
    RetryConfig,
    RetryStrategy,
    RetryableException,
    get_retry_registry,
)


class TestCircuitBreaker:
    """Tests for circuit breaker"""

    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in CLOSED state"""
        config = CircuitBreakerConfig(name="test_breaker")
        breaker = CircuitBreaker(config)

        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.metrics.consecutive_failures == 0

    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures"""
        config = CircuitBreakerConfig(
            name="test_breaker",
            failure_threshold=3,
        )
        breaker = CircuitBreaker(config)

        def failing_func():
            raise Exception("Test failure")

        # Trigger failures
        for i in range(3):
            with pytest.raises(Exception):
                breaker.call(failing_func)

        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.metrics.failed_requests == 3

    def test_circuit_breaker_rejects_when_open(self):
        """Test circuit breaker rejects requests when open"""
        config = CircuitBreakerConfig(
            name="test_breaker",
            failure_threshold=1,
            timeout=1,
        )
        breaker = CircuitBreaker(config)

        def failing_func():
            raise Exception("Test failure")

        # Open the circuit
        with pytest.raises(Exception):
            breaker.call(failing_func)

        # Should reject immediately
        with pytest.raises(CircuitBreakerException):
            breaker.call(lambda: "success")

        assert breaker.metrics.rejected_requests == 1

    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery through HALF_OPEN state"""
        config = CircuitBreakerConfig(
            name="test_breaker",
            failure_threshold=1,
            success_threshold=1,
            timeout=0,
        )
        breaker = CircuitBreaker(config)

        # Open circuit
        with pytest.raises(Exception):
            breaker.call(lambda: 1 / 0)

        assert breaker.state == CircuitBreakerState.OPEN

        # Attempt recovery
        result = breaker.call(lambda: "success")
        assert result == "success"
        assert breaker.state == CircuitBreakerState.CLOSED


class TestDegradation:
    """Tests for degradation strategy"""

    def test_feature_registration(self):
        """Test feature registration"""
        strategy = DegradationStrategy()
        config = FeatureConfig(name="test_feature", critical=False)

        strategy.register_feature(config)
        assert strategy.is_feature_enabled("test_feature")

    def test_feature_disable(self):
        """Test feature disabling"""
        strategy = DegradationStrategy()
        config = FeatureConfig(name="test_feature", critical=False)

        strategy.register_feature(config)
        strategy.disable_feature("test_feature")

        assert not strategy.is_feature_enabled("test_feature")
        assert strategy.get_feature_status("test_feature") == FeatureStatus.DISABLED

    def test_degradation_level_change(self):
        """Test degradation level changes"""
        strategy = DegradationStrategy()

        assert strategy.get_degradation_level() == DegradationLevel.NORMAL

        strategy.set_degradation_level(DegradationLevel.DEGRADED)
        assert strategy.get_degradation_level() == DegradationLevel.DEGRADED

        strategy.set_degradation_level(DegradationLevel.SEVERELY_DEGRADED)
        assert strategy.is_read_only_mode()

    def test_cache_operations(self):
        """Test caching functionality"""
        strategy = DegradationStrategy()

        strategy.cache_result("key1", "value1", ttl=10)
        assert strategy.get_cached_result("key1") == "value1"

        strategy.clear_cache()
        assert strategy.get_cached_result("key1") is None


class TestDistributedLock:
    """Tests for distributed lock"""

    def test_lock_acquisition(self):
        """Test lock acquisition"""
        config = DistributedLockConfig(name="test_lock")
        lock = DistributedLock(config)

        assert lock.acquire()
        assert lock.is_locked

    def test_lock_release(self):
        """Test lock release"""
        config = DistributedLockConfig(name="test_lock")
        lock = DistributedLock(config)

        lock.acquire()
        assert lock.release()
        assert not lock.is_locked

    def test_lock_context_manager(self):
        """Test lock as context manager"""
        config = DistributedLockConfig(name="test_lock")
        lock = DistributedLock(config)

        with lock:
            assert lock.is_locked

        assert not lock.is_locked

    def test_lock_metrics(self):
        """Test lock metrics"""
        config = DistributedLockConfig(name="test_lock")
        lock = DistributedLock(config)

        lock.acquire()
        metrics = lock.get_metrics()

        assert metrics.successful_acquisitions == 1
        assert metrics.active_locks == 1

        lock.release()
        metrics = lock.get_metrics()
        assert metrics.total_releases == 1


class TestRetry:
    """Tests for retry mechanism"""

    def test_retry_success_on_first_attempt(self):
        """Test successful execution on first attempt"""
        config = RetryConfig(name="test_retry", max_retries=3)
        executor = RetryExecutor(config)

        result = executor.execute(lambda: "success")
        assert result == "success"
        assert executor.get_metrics().successful_attempts == 1

    def test_retry_with_exponential_backoff(self):
        """Test retry with exponential backoff"""
        config = RetryConfig(
            name="test_retry",
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_retries=2,
            initial_delay=0.01,
            multiplier=2.0,
            jitter=False,
        )
        executor = RetryExecutor(config)

        attempt_count = 0

        def failing_then_success():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise RetryableException("Temporary failure")
            return "success"

        start_time = time.time()
        result = executor.execute(failing_then_success)
        elapsed = time.time() - start_time

        assert result == "success"
        assert attempt_count == 3
        # Should have backoff delays: 0.01 + 0.02 = 0.03
        assert elapsed >= 0.03

    def test_retry_max_retries_exceeded(self):
        """Test max retries exceeded"""
        config = RetryConfig(
            name="test_retry",
            max_retries=2,
            initial_delay=0.001,
        )
        executor = RetryExecutor(config)

        def always_fails():
            raise RetryableException("Always fails")

        with pytest.raises(RetryableException):
            executor.execute(always_fails)

        metrics = executor.get_metrics()
        assert metrics.failed_attempts == 1
        assert metrics.failed_retries == 2

    def test_retry_budget_exhaustion(self):
        """Test retry budget exhaustion"""
        config = RetryConfig(
            name="test_retry",
            max_retries=100,
            budget_per_minute=2,
            initial_delay=0.001,
        )
        executor = RetryExecutor(config)

        def always_fails():
            raise RetryableException("Always fails")

        with pytest.raises(RetryableException):
            executor.execute(always_fails)

        metrics = executor.get_metrics()
        assert metrics.budget_exhausted_count == 1

    def test_retry_non_retryable_exception(self):
        """Test non-retryable exception"""
        config = RetryConfig(
            name="test_retry",
            max_retries=3,
            retryable_exceptions=(RetryableException,),
        )
        executor = RetryExecutor(config)

        def raises_value_error():
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            executor.execute(raises_value_error)

        metrics = executor.get_metrics()
        assert metrics.failed_attempts == 1
        assert metrics.failed_retries == 0


class TestIntegration:
    """Integration tests for stability modules"""

    def test_circuit_breaker_registry(self):
        """Test circuit breaker registry"""
        registry = get_circuit_breaker_registry()

        config1 = CircuitBreakerConfig(name="breaker1")
        config2 = CircuitBreakerConfig(name="breaker2")

        breaker1 = registry.get_or_create(config1)
        breaker2 = registry.get_or_create(config2)

        assert breaker1 is not breaker2
        assert registry.get("breaker1") is breaker1

    def test_degradation_strategy_singleton(self):
        """Test degradation strategy singleton"""
        strategy1 = get_degradation_strategy()
        strategy2 = get_degradation_strategy()

        assert strategy1 is strategy2

    def test_lock_manager(self):
        """Test lock manager"""
        manager = get_lock_manager()

        config1 = DistributedLockConfig(name="lock1")
        config2 = DistributedLockConfig(name="lock2")

        lock1 = manager.get_or_create(config1)
        lock2 = manager.get_or_create(config2)

        assert lock1 is not lock2
        assert manager.get("lock1") is lock1

    def test_retry_registry(self):
        """Test retry registry"""
        registry = get_retry_registry()

        config1 = RetryConfig(name="retry1")
        config2 = RetryConfig(name="retry2")

        executor1 = registry.get_or_create(config1)
        executor2 = registry.get_or_create(config2)

        assert executor1 is not executor2
        assert registry.get("retry1") is executor1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
