"""Error recovery and resilience mechanisms for X-Agent."""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorCategory(Enum):
    """Error classification for routing and recovery."""
    TRANSIENT = "transient"  # Temporary, retry likely to succeed
    RATE_LIMIT = "rate_limit"  # Rate limited, back off
    AUTHENTICATION = "authentication"  # Auth failed, needs intervention
    VALIDATION = "validation"  # Invalid input, won't retry
    RESOURCE = "resource"  # Resource exhausted
    UNKNOWN = "unknown"  # Unknown error


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class ErrorMetrics:
    """Track error metrics for circuit breaker."""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    state_change_time: float = field(default_factory=time.time)


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.initial_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random
            delay *= random.uniform(0.8, 1.2)

        return delay


class CircuitBreaker:
    """Circuit breaker pattern implementation."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.metrics = ErrorMetrics()
        self._lock = asyncio.Lock()

    async def call(self, coro) -> Any:
        """Execute coroutine with circuit breaker protection."""
        async with self._lock:
            if self.metrics.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.metrics.state = CircuitBreakerState.HALF_OPEN
                    logger.info(f"Circuit breaker {self.name} entering HALF_OPEN state")
                else:
                    raise RuntimeError(f"Circuit breaker {self.name} is OPEN")

        try:
            result = await coro
            await self._record_success()
            return result
        except self.expected_exception:
            await self._record_failure()
            raise

    async def _record_success(self) -> None:
        """Record successful call."""
        async with self._lock:
            self.metrics.success_count += 1
            if self.metrics.state == CircuitBreakerState.HALF_OPEN:
                self.metrics.state = CircuitBreakerState.CLOSED
                self.metrics.failure_count = 0
                logger.info(f"Circuit breaker {self.name} recovered to CLOSED state")

    async def _record_failure(self) -> None:
        """Record failed call."""
        async with self._lock:
            self.metrics.failure_count += 1
            self.metrics.last_failure_time = time.time()

            if self.metrics.failure_count >= self.failure_threshold:
                self.metrics.state = CircuitBreakerState.OPEN
                self.metrics.state_change_time = time.time()
                logger.error(
                    f"Circuit breaker {self.name} opened after "
                    f"{self.metrics.failure_count} failures"
                )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.metrics.last_failure_time is None:
            return True
        elapsed = time.time() - self.metrics.last_failure_time
        return elapsed >= self.recovery_timeout


def classify_error(exc: Exception) -> ErrorCategory:
    """Classify error for appropriate recovery strategy."""
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__

    if "rate" in exc_str or "429" in exc_str or "quota" in exc_str:
        return ErrorCategory.RATE_LIMIT
    elif "auth" in exc_str or "401" in exc_str or "403" in exc_str:
        return ErrorCategory.AUTHENTICATION
    elif "timeout" in exc_str or "connection" in exc_str or "temporary" in exc_str:
        return ErrorCategory.TRANSIENT
    elif "validation" in exc_str or "invalid" in exc_str or "400" in exc_str:
        return ErrorCategory.VALIDATION
    elif "resource" in exc_str or "memory" in exc_str or "disk" in exc_str:
        return ErrorCategory.RESOURCE
    elif exc_type in ("TimeoutError", "ConnectionError", "OSError"):
        return ErrorCategory.TRANSIENT

    return ErrorCategory.UNKNOWN


async def retry_with_backoff(
    coro_func: Callable[..., Any],
    *args,
    policy: RetryPolicy | None = None,
    on_retry: Callable[[int, Exception], None] | None = None,
    **kwargs,
) -> Any:
    """Retry a coroutine with exponential backoff."""
    policy = policy or RetryPolicy()

    for attempt in range(policy.max_attempts):
        try:
            return await coro_func(*args, **kwargs)
        except Exception as exc:
            if attempt == policy.max_attempts - 1:
                raise

            category = classify_error(exc)
            if category == ErrorCategory.VALIDATION or category == ErrorCategory.AUTHENTICATION:
                raise

            delay = policy.get_delay(attempt)
            if on_retry:
                on_retry(attempt + 1, exc)

            logger.warning(
                f"Attempt {attempt + 1} failed ({category.value}): {exc}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

    raise RuntimeError("Retry exhausted")


def with_retry(
    policy: RetryPolicy | None = None,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> Callable:
    """Decorator for automatic retry with backoff."""
    def decorator(func: Callable[..., Any]) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await retry_with_backoff(
                func,
                *args,
                policy=policy,
                on_retry=on_retry,
                **kwargs,
            )
        return wrapper
    return decorator


def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> Callable:
    """Decorator for circuit breaker protection."""
    breaker = CircuitBreaker(name, failure_threshold, recovery_timeout)

    def decorator(func: Callable[..., Any]) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            coro = func(*args, **kwargs)
            return await breaker.call(coro)
        return wrapper
    return decorator


@dataclass
class CompensationAction:
    """Action to compensate for a failed step."""
    name: str
    action: Callable[..., Any]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)

    async def execute(self) -> None:
        """Execute compensation action."""
        try:
            if asyncio.iscoroutinefunction(self.action):
                await self.action(*self.args, **self.kwargs)
            else:
                self.action(*self.args, **self.kwargs)
            logger.info(f"Compensation action '{self.name}' executed successfully")
        except Exception as exc:
            logger.error(f"Compensation action '{self.name}' failed: {exc}")


class CompensationChain:
    """Manage compensation actions for workflow rollback."""

    def __init__(self) -> None:
        self.actions: list[CompensationAction] = []

    def add(
        self,
        name: str,
        action: Callable[..., Any],
        *args,
        **kwargs,
    ) -> None:
        """Add compensation action."""
        self.actions.append(CompensationAction(name, action, args, kwargs))

    async def execute_all(self) -> None:
        """Execute all compensation actions in reverse order."""
        logger.info(f"Executing {len(self.actions)} compensation actions")
        for action in reversed(self.actions):
            await action.execute()

    def clear(self) -> None:
        """Clear all compensation actions."""
        self.actions.clear()


class GracefulDegradation:
    """Graceful degradation strategy."""

    def __init__(self) -> None:
        self.degraded_services: set[str] = set()
        self._lock = asyncio.Lock()

    async def mark_degraded(self, service: str) -> None:
        """Mark a service as degraded."""
        async with self._lock:
            self.degraded_services.add(service)
            logger.warning(f"Service '{service}' marked as degraded")

    async def mark_recovered(self, service: str) -> None:
        """Mark a service as recovered."""
        async with self._lock:
            self.degraded_services.discard(service)
            logger.info(f"Service '{service}' recovered")

    async def is_degraded(self, service: str) -> bool:
        """Check if service is degraded."""
        async with self._lock:
            return service in self.degraded_services

    async def get_status(self) -> dict[str, Any]:
        """Get degradation status."""
        async with self._lock:
            return {
                "degraded_services": list(self.degraded_services),
                "count": len(self.degraded_services),
            }


# Global instances
circuit_breakers: dict[str, CircuitBreaker] = {}
degradation = GracefulDegradation()


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create circuit breaker."""
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(name)
    return circuit_breakers[name]
