"""
Circuit Breaker Pattern Implementation for X-Agent

Implements the circuit breaker pattern to prevent cascading failures:
- CLOSED: Normal operation, requests pass through
- OPEN: Failure threshold exceeded, requests fail fast
- HALF_OPEN: Testing if service recovered, limited requests allowed

Features:
- Configurable failure thresholds and recovery timeouts
- Automatic state transitions
- Per-service circuit breaker instances
- Detailed metrics and logging
- Thread-safe operations
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from threading import RLock
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerMetrics(BaseModel):
    """Metrics for circuit breaker monitoring"""
    state: CircuitBreakerState
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    state_change_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    name: str
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: int = 60
    half_open_max_requests: int = 3
    expected_exception: type[Exception] = Exception


class CircuitBreakerException(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker implementation for fault tolerance.

    Prevents cascading failures by failing fast when a service is unavailable.
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.metrics = CircuitBreakerMetrics(state=CircuitBreakerState.CLOSED)
        self._lock = RLock()
        self._last_failure_time: float | None = None
        self._half_open_requests = 0

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self.metrics.rejected_requests += 1
                    logger.warning(
                        f"Circuit breaker {self.config.name} is OPEN, rejecting request"
                    )
                    raise CircuitBreakerException(
                        f"Circuit breaker {self.config.name} is open"
                    )

            if self.state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_requests >= self.config.half_open_max_requests:
                    self.metrics.rejected_requests += 1
                    logger.warning(
                        f"Circuit breaker {self.config.name} half-open max requests exceeded"
                    )
                    raise CircuitBreakerException(
                        f"Circuit breaker {self.config.name} half-open limit exceeded"
                    )
                self._half_open_requests += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise

    async def call_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> T:
        """Execute async function with circuit breaker protection."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self.metrics.rejected_requests += 1
                    logger.warning(
                        f"Circuit breaker {self.config.name} is OPEN, rejecting async request"
                    )
                    raise CircuitBreakerException(
                        f"Circuit breaker {self.config.name} is open"
                    )

            if self.state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_requests >= self.config.half_open_max_requests:
                    self.metrics.rejected_requests += 1
                    logger.warning(
                        f"Circuit breaker {self.config.name} half-open max requests exceeded"
                    )
                    raise CircuitBreakerException(
                        f"Circuit breaker {self.config.name} half-open limit exceeded"
                    )
                self._half_open_requests += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful request"""
        with self._lock:
            self.metrics.successful_requests += 1
            self.metrics.last_success_time = datetime.now(UTC)
            self.metrics.consecutive_failures = 0

            if self.state == CircuitBreakerState.HALF_OPEN:
                self.metrics.consecutive_successes += 1
                if self.metrics.consecutive_successes >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self.state == CircuitBreakerState.CLOSED:
                self.metrics.consecutive_successes += 1

    def _on_failure(self) -> None:
        """Handle failed request"""
        with self._lock:
            self.metrics.failed_requests += 1
            self.metrics.last_failure_time = datetime.now(UTC)
            self._last_failure_time = time.time()
            self.metrics.consecutive_successes = 0

            if self.state == CircuitBreakerState.HALF_OPEN:
                self.metrics.consecutive_failures += 1
                self._transition_to_open()
            elif self.state == CircuitBreakerState.CLOSED:
                self.metrics.consecutive_failures += 1
                if self.metrics.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to_open()

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self._last_failure_time is None:
            return True
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.timeout

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state"""
        self.state = CircuitBreakerState.CLOSED
        self.metrics.state = CircuitBreakerState.CLOSED
        self.metrics.state_change_time = datetime.now(UTC)
        self.metrics.consecutive_failures = 0
        self.metrics.consecutive_successes = 0
        self._half_open_requests = 0
        logger.info(f"Circuit breaker {self.config.name} transitioned to CLOSED")

    def _transition_to_open(self) -> None:
        """Transition to OPEN state"""
        self.state = CircuitBreakerState.OPEN
        self.metrics.state = CircuitBreakerState.OPEN
        self.metrics.state_change_time = datetime.now(UTC)
        self._half_open_requests = 0
        logger.warning(f"Circuit breaker {self.config.name} transitioned to OPEN")

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state"""
        self.state = CircuitBreakerState.HALF_OPEN
        self.metrics.state = CircuitBreakerState.HALF_OPEN
        self.metrics.state_change_time = datetime.now(UTC)
        self.metrics.consecutive_failures = 0
        self.metrics.consecutive_successes = 0
        self._half_open_requests = 0
        logger.info(f"Circuit breaker {self.config.name} transitioned to HALF_OPEN")

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current metrics"""
        with self._lock:
            return self.metrics.model_copy()

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state"""
        with self._lock:
            self._transition_to_closed()
            self.metrics.total_requests = 0
            self.metrics.successful_requests = 0
            self.metrics.failed_requests = 0
            self.metrics.rejected_requests = 0
            self._last_failure_time = None
            logger.info(f"Circuit breaker {self.config.name} manually reset")


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = RLock()

    def get_or_create(
        self, config: CircuitBreakerConfig
    ) -> CircuitBreaker:
        """Get or create circuit breaker"""
        with self._lock:
            if config.name not in self._breakers:
                self._breakers[config.name] = CircuitBreaker(config)
                logger.info(f"Created circuit breaker: {config.name}")
            return self._breakers[config.name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name"""
        with self._lock:
            return self._breakers.get(name)

    def get_all_metrics(self) -> dict[str, CircuitBreakerMetrics]:
        """Get metrics for all circuit breakers"""
        with self._lock:
            return {
                name: breaker.get_metrics()
                for name, breaker in self._breakers.items()
            }

    def reset_all(self) -> None:
        """Reset all circuit breakers"""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
            logger.info("All circuit breakers reset")


# Global registry instance
_circuit_breaker_registry = CircuitBreakerRegistry()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get global circuit breaker registry"""
    return _circuit_breaker_registry
