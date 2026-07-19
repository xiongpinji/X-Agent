"""
Circuit breaker pattern implementation for fault tolerance.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service failing, requests rejected immediately
- HALF_OPEN: Testing if service recovered, limited requests allowed

Features:
- Automatic state transitions
- Configurable failure thresholds
- Recovery timeout
- Success threshold for half-open state
- Thread-safe operations
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

from backend.app.core.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


class CircuitBreakerState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 2
    half_open_max_calls: int = 1


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics."""

    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    state_change_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "state_change_time": self.state_change_time,
        }


class CircuitBreaker:
    """Circuit breaker for fault tolerance."""

    def __init__(
        self,
        name: str = "default",
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Call function through circuit breaker."""
        async with self._lock:
            await self._check_state()

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            async with self._lock:
                await self._on_success()

            return result

        except Exception as e:
            async with self._lock:
                await self._on_failure()

            raise

    async def _check_state(self) -> None:
        """Check and update circuit breaker state."""
        if self.metrics.state == CircuitBreakerState.OPEN:
            elapsed = time.time() - self.metrics.last_failure_time
            if elapsed > self.config.recovery_timeout:
                self._transition_to_half_open()
            else:
                raise ServiceUnavailableError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Recovery in {self.config.recovery_timeout - elapsed:.1f}s"
                )

    async def _on_success(self) -> None:
        """Handle successful call."""
        self.metrics.total_calls += 1
        self.metrics.total_successes += 1

        if self.metrics.state == CircuitBreakerState.HALF_OPEN:
            self.metrics.success_count += 1
            if self.metrics.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self.metrics.state == CircuitBreakerState.CLOSED:
            self.metrics.failure_count = 0

    async def _on_failure(self) -> None:
        """Handle failed call."""
        self.metrics.total_calls += 1
        self.metrics.total_failures += 1
        self.metrics.failure_count += 1
        self.metrics.last_failure_time = time.time()

        if self.metrics.state == CircuitBreakerState.HALF_OPEN:
            self._transition_to_open()
        elif self.metrics.failure_count >= self.config.failure_threshold:
            self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        if self.metrics.state != CircuitBreakerState.OPEN:
            logger.error(
                f"Circuit breaker '{self.name}' transitioning to OPEN. "
                f"Failures: {self.metrics.failure_count}/{self.config.failure_threshold}"
            )
            self.metrics.state = CircuitBreakerState.OPEN
            self.metrics.state_change_time = time.time()

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
        self.metrics.state = CircuitBreakerState.HALF_OPEN
        self.metrics.success_count = 0
        self.metrics.state_change_time = time.time()

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED")
        self.metrics.state = CircuitBreakerState.CLOSED
        self.metrics.failure_count = 0
        self.metrics.success_count = 0
        self.metrics.state_change_time = time.time()

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get circuit breaker metrics."""
        return self.metrics

    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")
        self.metrics = CircuitBreakerMetrics()


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    async def get(self, name: str) -> CircuitBreaker | None:
        """Get a circuit breaker by name."""
        async with self._lock:
            return self._breakers.get(name)

    async def reset(self, name: str) -> None:
        """Reset a circuit breaker."""
        async with self._lock:
            if name in self._breakers:
                self._breakers[name].reset()

    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        async with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()

    async def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all circuit breakers."""
        async with self._lock:
            return {
                name: breaker.get_metrics().to_dict()
                for name, breaker in self._breakers.items()
            }


# Global circuit breaker registry
_circuit_breaker_registry: CircuitBreakerRegistry | None = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get or create the global circuit breaker registry."""
    global _circuit_breaker_registry
    if _circuit_breaker_registry is None:
        _circuit_breaker_registry = CircuitBreakerRegistry()
    return _circuit_breaker_registry
