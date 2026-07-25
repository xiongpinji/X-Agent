"""Error handling optimization for X-Agent.

Implements efficient error handling, recovery strategies, and error metrics tracking.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypeVar

logger = logging.getLogger("xagent.error_handling")

T = TypeVar("T")


class ErrorSeverity(StrEnum):
    """Error severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ErrorMetrics:
    """Error tracking metrics."""

    total_errors: int = 0
    errors_by_type: dict[str, int] = field(default_factory=dict)
    errors_by_severity: dict[str, int] = field(default_factory=dict)
    avg_recovery_time_ms: float = 0.0
    recovery_success_rate: float = 0.0
    last_error_time: datetime | None = None

    def record_error(self, error_type: str, severity: ErrorSeverity) -> None:
        """Record an error."""
        self.total_errors += 1
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        self.errors_by_severity[severity.value] = self.errors_by_severity.get(severity.value, 0) + 1
        self.last_error_time = datetime.now(UTC)


class RetryStrategy:
    """Retry strategy with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay_ms: int = 100,
        max_delay_ms: int = 10000,
        backoff_multiplier: float = 2.0,
    ):
        self._max_retries = max_retries
        self._initial_delay_ms = initial_delay_ms
        self._max_delay_ms = max_delay_ms
        self._backoff_multiplier = backoff_multiplier

    async def execute_with_retry(
        self,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        delay_ms = self._initial_delay_ms

        for attempt in range(self._max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self._max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay_ms}ms: {e}",
                    )
                    await asyncio.sleep(delay_ms / 1000.0)
                    delay_ms = min(
                        int(delay_ms * self._backoff_multiplier),
                        self._max_delay_ms,
                    )
                else:
                    logger.error(f"All {self._max_retries + 1} attempts failed: {e}")

        raise last_exception


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        expected_exception: type[Exception] = Exception,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout_seconds = recovery_timeout_seconds
        self._expected_exception = expected_exception
        self._failure_count = 0
        self._last_failure_time: datetime | None = None
        self._state = "closed"  # closed, open, half_open

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Call function through circuit breaker."""
        if self._state == "open":
            if self._should_attempt_reset():
                self._state = "half_open"
            else:
                raise RuntimeError("Circuit breaker is open")

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self._on_success()
            return result
        except self._expected_exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call."""
        self._failure_count = 0
        self._state = "closed"

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now(UTC)
        if self._failure_count >= self._failure_threshold:
            self._state = "open"
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures",
            )

    def _should_attempt_reset(self) -> bool:
        """Check if should attempt reset."""
        if self._last_failure_time is None:
            return False
        elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
        return elapsed >= self._recovery_timeout_seconds

    def get_state(self) -> str:
        """Get circuit breaker state."""
        return self._state


class BulkheadPattern:
    """Bulkhead pattern for resource isolation."""

    def __init__(self, max_concurrent: int = 10, queue_size: int = 100):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_size = queue_size
        self._pending_count = 0

    async def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute function with bulkhead isolation."""
        if self._pending_count >= self._queue_size:
            raise RuntimeError("Bulkhead queue is full")

        self._pending_count += 1
        try:
            async with self._semaphore:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
        finally:
            self._pending_count -= 1

    def get_stats(self) -> dict[str, int]:
        """Get bulkhead statistics."""
        return {
            "pending": self._pending_count,
            "queue_size": self._queue_size,
        }


class ErrorRecoveryManager:
    """Centralized error recovery management."""

    def __init__(self):
        self._metrics = ErrorMetrics()
        self._retry_strategy = RetryStrategy()
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._bulkheads: dict[str, BulkheadPattern] = {}

    def get_retry_strategy(self) -> RetryStrategy:
        """Get retry strategy."""
        return self._retry_strategy

    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create circuit breaker."""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker()
        return self._circuit_breakers[name]

    def get_bulkhead(self, name: str, max_concurrent: int = 10) -> BulkheadPattern:
        """Get or create bulkhead."""
        if name not in self._bulkheads:
            self._bulkheads[name] = BulkheadPattern(max_concurrent=max_concurrent)
        return self._bulkheads[name]

    def record_error(
        self,
        error_type: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ) -> None:
        """Record an error."""
        self._metrics.record_error(error_type, severity)

    def get_metrics(self) -> ErrorMetrics:
        """Get error metrics."""
        return self._metrics

    def get_stats(self) -> dict[str, Any]:
        """Get error recovery statistics."""
        return {
            "metrics": {
                "total_errors": self._metrics.total_errors,
                "errors_by_type": self._metrics.errors_by_type,
                "errors_by_severity": self._metrics.errors_by_severity,
                "last_error_time": self._metrics.last_error_time.isoformat()
                if self._metrics.last_error_time
                else None,
            },
            "circuit_breakers": {
                name: cb.get_state() for name, cb in self._circuit_breakers.items()
            },
            "bulkheads": {
                name: bh.get_stats() for name, bh in self._bulkheads.items()
            },
        }


class ErrorHandler:
    """Unified error handler with recovery strategies."""

    def __init__(self, recovery_manager: ErrorRecoveryManager | None = None):
        self._recovery_manager = recovery_manager or ErrorRecoveryManager()

    async def handle_with_recovery(
        self,
        func: Callable,
        error_type: str = "unknown",
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        use_retry: bool = True,
        use_circuit_breaker: bool = False,
        use_bulkhead: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Handle function execution with recovery strategies."""
        try:
            if use_circuit_breaker:
                cb = self._recovery_manager.get_circuit_breaker(error_type)
                if use_retry:
                    return await cb.call(
                        self._recovery_manager.get_retry_strategy().execute_with_retry,
                        func,
                        *args,
                        **kwargs,
                    )
                else:
                    return await cb.call(func, *args, **kwargs)
            elif use_retry:
                return await self._recovery_manager.get_retry_strategy().execute_with_retry(
                    func,
                    *args,
                    **kwargs,
                )
            else:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
        except Exception as e:
            self._recovery_manager.record_error(error_type, severity)
            logger.error(f"Error in {error_type}: {e}", exc_info=True)
            raise
