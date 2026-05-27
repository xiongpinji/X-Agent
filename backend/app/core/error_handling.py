"""
Enhanced error handling with retry strategies and circuit breaker pattern.

Implements:
- Unified exception hierarchy
- Retry strategies (exponential backoff, jitter)
- Circuit breaker pattern
- Graceful degradation
- Error tracking and alerting
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ErrorCategory(str, Enum):
    """Error categories."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    INTERNAL = "internal"


@dataclass
class ErrorContext:
    """Context information for an error."""

    error_id: str
    timestamp: float
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    details: dict[str, Any]
    user_id: str | None = None
    tenant_id: str | None = None
    correlation_id: str | None = None
    stack_trace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "details": self.details,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
        }


class XAgentException(Exception):
    """Base exception for X-Agent."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        details: dict[str, Any] | None = None,
        error_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.details = details or {}
        self.error_id = error_id or f"err_{int(time.time() * 1000)}"
        self.timestamp = time.time()

    def to_context(self) -> ErrorContext:
        """Convert to error context."""
        return ErrorContext(
            error_id=self.error_id,
            timestamp=self.timestamp,
            severity=self.severity,
            category=self.category,
            message=self.message,
            details=self.details,
        )


class AuthenticationError(XAgentException):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed", **kwargs) -> None:
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.AUTHENTICATION,
            **kwargs,
        )


class AuthorizationError(XAgentException):
    """Authorization failed."""

    def __init__(self, message: str = "Authorization failed", **kwargs) -> None:
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.AUTHORIZATION,
            **kwargs,
        )


class ValidationError(XAgentException):
    """Validation failed."""

    def __init__(self, message: str = "Validation failed", **kwargs) -> None:
        super().__init__(
            message,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
            **kwargs,
        )


class NotFoundError(XAgentException):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found", **kwargs) -> None:
        super().__init__(
            message,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.NOT_FOUND,
            **kwargs,
        )


class ConflictError(XAgentException):
    """Resource conflict."""

    def __init__(self, message: str = "Resource conflict", **kwargs) -> None:
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.CONFLICT,
            **kwargs,
        )


class RateLimitError(XAgentException):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", **kwargs) -> None:
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.RATE_LIMIT,
            **kwargs,
        )


class TimeoutError(XAgentException):
    """Operation timeout."""

    def __init__(self, message: str = "Operation timeout", **kwargs) -> None:
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.TIMEOUT,
            **kwargs,
        )


class ExternalServiceError(XAgentException):
    """External service error."""

    def __init__(self, message: str = "External service error", **kwargs) -> None:
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.EXTERNAL_SERVICE,
            **kwargs,
        )


class DatabaseError(XAgentException):
    """Database error."""

    def __init__(self, message: str = "Database error", **kwargs) -> None:
        super().__init__(
            message,
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.DATABASE,
            **kwargs,
        )


class RetryStrategy:
    """Base retry strategy."""

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        raise NotImplementedError


class ExponentialBackoffRetry(RetryStrategy):
    """Exponential backoff retry strategy."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ) -> None:
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry."""
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    delay = min(
                        self.initial_delay * (self.exponential_base ** attempt),
                        self.max_delay,
                    )
                    if self.jitter:
                        delay *= random.uniform(0.5, 1.5)

                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)

        raise last_exception


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation
    - OPEN: Failing, reject requests
    - HALF_OPEN: Testing if service recovered
    """

    class State(str, Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = self.State.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function through circuit breaker."""
        async with self._lock:
            if self._state == self.State.OPEN:
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = self.State.HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise ExternalServiceError("Circuit breaker is OPEN")

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            async with self._lock:
                if self._state == self.State.HALF_OPEN:
                    self._success_count += 1
                    if self._success_count >= self.success_threshold:
                        self._state = self.State.CLOSED
                        self._failure_count = 0
                        logger.info("Circuit breaker entering CLOSED state")
                elif self._state == self.State.CLOSED:
                    self._failure_count = 0

            return result

        except Exception as e:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()

                if self._failure_count >= self.failure_threshold:
                    self._state = self.State.OPEN
                    logger.error(f"Circuit breaker entering OPEN state after {self._failure_count} failures")

            raise

    def get_state(self) -> dict[str, Any]:
        """Get circuit breaker state."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
        }


class ErrorTracker:
    """Track and aggregate errors for monitoring and alerting."""

    def __init__(self, max_history: int = 1000) -> None:
        self._errors: list[ErrorContext] = []
        self._max_history = max_history
        self._error_counts: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def record(self, error: XAgentException | Exception) -> None:
        """Record an error."""
        if isinstance(error, XAgentException):
            context = error.to_context()
        else:
            context = ErrorContext(
                error_id=f"err_{int(time.time() * 1000)}",
                timestamp=time.time(),
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.INTERNAL,
                message=str(error),
                details={},
            )

        async with self._lock:
            self._errors.append(context)
            if len(self._errors) > self._max_history:
                self._errors.pop(0)

            key = f"{context.category.value}:{context.severity.value}"
            self._error_counts[key] = self._error_counts.get(key, 0) + 1

    def get_stats(self) -> dict[str, Any]:
        """Get error statistics."""
        return {
            "total_errors": len(self._errors),
            "error_counts": self._error_counts,
            "recent_errors": [e.to_dict() for e in self._errors[-10:]],
        }


# Global instances
_error_tracker: ErrorTracker | None = None


def get_error_tracker() -> ErrorTracker:
    """Get or create the global error tracker."""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker()
    return _error_tracker
