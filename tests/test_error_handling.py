"""
Tests for unified error handling mechanism.

Tests:
- Exception hierarchy
- Retry strategies
- Circuit breaker
- Error recovery
- Graceful degradation
- Error monitoring
"""

from __future__ import annotations

import asyncio
import pytest

from backend.app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState
from backend.app.core.exceptions import (
    AlreadyExistsError,
    AuthenticationError,
    BusinessError,
    ConfigurationError,
    ConnectionError,
    ErrorCode,
    ErrorSeverity,
    InsufficientResourcesError,
    InvalidInputError,
    InvalidStateError,
    NetworkError,
    NotFoundError,
    OperationNotAllowedError,
    PermissionDeniedError,
    RateLimitError,
    ResourceExhaustedError,
    ServiceUnavailableError,
    SystemError,
    TimeoutError,
    ValidationError,
    XAgentException,
)
from backend.app.core.fallback import (
    CacheFallback,
    DefaultValueFallback,
    DegradationPolicy,
    FeatureFlag,
    FeatureFlagRegistry,
    ServiceDegradation,
)
from backend.app.core.recovery import (
    CompensatingTransaction,
    ErrorIsolation,
    ErrorRecoveryManager,
    RecoveryAction,
    RecoveryContext,
    RecoveryStrategy,
)
from backend.app.core.retry import ExponentialBackoffRetry, RetryConfig, retry


class TestExceptionHierarchy:
    """Test exception hierarchy."""

    def test_base_exception(self):
        """Test base exception."""
        exc = XAgentException("Test error")
        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.severity == ErrorSeverity.MEDIUM
        assert exc.is_retryable is False

    def test_business_error(self):
        """Test business error."""
        exc = BusinessError("Business logic error")
        assert exc.error_code == ErrorCode.BUSINESS_LOGIC_ERROR
        assert exc.severity == ErrorSeverity.MEDIUM

    def test_invalid_state_error(self):
        """Test invalid state error."""
        exc = InvalidStateError("Invalid state")
        assert exc.error_code == ErrorCode.INVALID_STATE

    def test_operation_not_allowed_error(self):
        """Test operation not allowed error."""
        exc = OperationNotAllowedError("Operation not allowed")
        assert exc.error_code == ErrorCode.OPERATION_NOT_ALLOWED

    def test_resource_exhausted_error(self):
        """Test resource exhausted error."""
        exc = ResourceExhaustedError("Resource exhausted")
        assert exc.error_code == ErrorCode.RESOURCE_EXHAUSTED
        assert exc.is_retryable is True

    def test_system_error(self):
        """Test system error."""
        exc = SystemError("System error")
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.severity == ErrorSeverity.HIGH

    def test_network_error(self):
        """Test network error."""
        exc = NetworkError("Network error")
        assert exc.error_code == ErrorCode.CONNECTION_ERROR
        assert exc.is_retryable is True

    def test_connection_error(self):
        """Test connection error."""
        exc = ConnectionError("Connection failed")
        assert exc.error_code == ErrorCode.CONNECTION_ERROR

    def test_timeout_error(self):
        """Test timeout error."""
        exc = TimeoutError("Operation timeout")
        assert exc.error_code == ErrorCode.TIMEOUT_ERROR

    def test_service_unavailable_error(self):
        """Test service unavailable error."""
        exc = ServiceUnavailableError("Service unavailable")
        assert exc.error_code == ErrorCode.SERVICE_UNAVAILABLE

    def test_rate_limit_error(self):
        """Test rate limit error."""
        exc = RateLimitError("Rate limit exceeded")
        assert exc.error_code == ErrorCode.RATE_LIMIT_EXCEEDED

    def test_not_found_error(self):
        """Test not found error."""
        exc = NotFoundError("Resource not found")
        assert exc.error_code == ErrorCode.RESOURCE_NOT_FOUND

    def test_already_exists_error(self):
        """Test already exists error."""
        exc = AlreadyExistsError("Resource already exists")
        assert exc.error_code == ErrorCode.RESOURCE_ALREADY_EXISTS

    def test_insufficient_resources_error(self):
        """Test insufficient resources error."""
        exc = InsufficientResourcesError("Insufficient resources")
        assert exc.error_code == ErrorCode.INSUFFICIENT_RESOURCES
        assert exc.is_retryable is True

    def test_validation_error(self):
        """Test validation error."""
        exc = ValidationError("Validation failed")
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.severity == ErrorSeverity.LOW

    def test_invalid_input_error(self):
        """Test invalid input error."""
        exc = InvalidInputError("Invalid input")
        assert exc.error_code == ErrorCode.INVALID_INPUT

    def test_authentication_error(self):
        """Test authentication error."""
        exc = AuthenticationError("Authentication failed")
        assert exc.error_code == ErrorCode.AUTHENTICATION_FAILED
        assert exc.severity == ErrorSeverity.HIGH

    def test_permission_denied_error(self):
        """Test permission denied error."""
        exc = PermissionDeniedError("Permission denied")
        assert exc.error_code == ErrorCode.PERMISSION_DENIED

    def test_error_context(self):
        """Test error context."""
        exc = XAgentException("Test error", error_code=ErrorCode.VALIDATION_ERROR)
        context = exc.to_context(
            user_id="user123",
            tenant_id="tenant456",
            correlation_id="corr789",
        )
        assert context.error_code == ErrorCode.VALIDATION_ERROR
        assert context.user_id == "user123"
        assert context.tenant_id == "tenant456"
        assert context.correlation_id == "corr789"


class TestRetryStrategy:
    """Test retry strategy."""

    @pytest.mark.asyncio
    async def test_successful_retry(self):
        """Test successful retry."""
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Connection failed")
            return "success"

        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        strategy = ExponentialBackoffRetry(config)
        result = await strategy.execute(failing_func)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self):
        """Test max attempts exceeded."""
        async def always_failing():
            raise NetworkError("Connection failed")

        config = RetryConfig(max_attempts=2, initial_delay=0.01)
        strategy = ExponentialBackoffRetry(config)

        with pytest.raises(NetworkError):
            await strategy.execute(always_failing)

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        """Test non-retryable exception."""
        async def failing_func():
            raise ValidationError("Invalid input")

        config = RetryConfig(
            max_attempts=3,
            retryable_exceptions=(NetworkError,),
        )
        strategy = ExponentialBackoffRetry(config)

        with pytest.raises(ValidationError):
            await strategy.execute(failing_func)

    @pytest.mark.asyncio
    async def test_retry_decorator(self):
        """Test retry decorator."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Connection failed")
            return "success"

        result = await failing_func()
        assert result == "success"
        assert call_count == 2


class TestCircuitBreaker:
    """Test circuit breaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        async def success_func():
            return "success"

        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.metrics.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state(self):
        """Test circuit breaker in open state."""
        async def failing_func():
            raise NetworkError("Connection failed")

        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        # Trigger failures
        for _ in range(2):
            with pytest.raises(NetworkError):
                await breaker.call(failing_func)

        # Circuit should be open
        assert breaker.metrics.state == CircuitBreakerState.OPEN

        # Next call should fail immediately
        with pytest.raises(ServiceUnavailableError):
            await breaker.call(failing_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_state(self):
        """Test circuit breaker in half-open state."""
        call_count = 0

        async def sometimes_failing():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise NetworkError("Connection failed")
            return "success"

        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        breaker = CircuitBreaker("test", config)

        # Trigger failures
        for _ in range(2):
            with pytest.raises(NetworkError):
                await breaker.call(sometimes_failing)

        assert breaker.metrics.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Should transition to half-open and succeed
        result = await breaker.call(sometimes_failing)
        assert result == "success"
        assert breaker.metrics.state == CircuitBreakerState.CLOSED


class TestErrorRecovery:
    """Test error recovery."""

    @pytest.mark.asyncio
    async def test_recovery_context(self):
        """Test recovery context."""
        context = RecoveryContext()
        assert context.attempt_count == 0
        assert context.last_error is None

        exc = NetworkError("Connection failed")
        context.last_error = exc
        context.attempt_count += 1

        assert context.attempt_count == 1
        assert context.last_error == exc

    @pytest.mark.asyncio
    async def test_compensating_transaction(self):
        """Test compensating transaction."""
        operations = []
        compensations = []

        async def op1():
            operations.append("op1")

        async def comp1():
            compensations.append("comp1")

        async def op2():
            operations.append("op2")

        async def comp2():
            compensations.append("comp2")

        transaction = CompensatingTransaction()
        transaction.add_operation(op1, compensation=comp1)
        transaction.add_operation(op2, compensation=comp2)

        results = await transaction.execute()
        assert len(results) == 2
        assert operations == ["op1", "op2"]

    @pytest.mark.asyncio
    async def test_error_isolation(self):
        """Test error isolation."""
        async def failing_func():
            raise NetworkError("Connection failed")

        isolation = ErrorIsolation(isolation_level="operation")
        result = await isolation.isolate(failing_func)
        assert result is None

        errors = await isolation.get_isolated_errors()
        assert len(errors) == 1


class TestGracefulDegradation:
    """Test graceful degradation."""

    @pytest.mark.asyncio
    async def test_service_degradation(self):
        """Test service degradation."""
        config = None
        degradation = ServiceDegradation(config)

        # Cache a value
        await degradation.cache_value("key1", "value1")

        # Retrieve from cache
        result = await degradation.get_degraded_response("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_cache_fallback(self):
        """Test cache fallback."""
        call_count = 0

        async def fetch_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "fresh"
            raise NetworkError("Connection failed")

        fallback = CacheFallback(ttl=1)

        # First call
        result1 = await fallback.get_or_fetch("key1", fetch_func)
        assert result1 == "fresh"

        # Second call should use cache
        result2 = await fallback.get_or_fetch("key1", fetch_func)
        assert result2 == "fresh"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_default_value_fallback(self):
        """Test default value fallback."""
        async def failing_func():
            raise NetworkError("Connection failed")

        fallback = DefaultValueFallback({"key1": "default_value"})
        result = await fallback.get_with_default("key1", failing_func)
        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_feature_flag(self):
        """Test feature flag."""
        flag = FeatureFlag("feature1", enabled=True)

        async def feature_func():
            return "feature_result"

        async def fallback_func():
            return "fallback_result"

        # Feature enabled
        result = await flag.execute_if_enabled(feature_func, fallback=fallback_func)
        assert result == "feature_result"

        # Feature disabled
        await flag.disable()
        result = await flag.execute_if_enabled(feature_func, fallback=fallback_func)
        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_feature_flag_registry(self):
        """Test feature flag registry."""
        registry = FeatureFlagRegistry()

        flag1 = await registry.register("feature1", enabled=True)
        assert flag1.enabled is True

        await registry.disable("feature1")
        flag1_updated = await registry.get("feature1")
        assert flag1_updated.enabled is False

        flags = await registry.get_all_flags()
        assert flags["feature1"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
