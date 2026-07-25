"""Circuit Breaker pattern implementation for X-Agent.

Provides resilience against cascading failures by wrapping external service
calls (LLM APIs, databases, etc.) with circuit breaker logic.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failures exceeded threshold, requests fail immediately
- HALF_OPEN: Testing if service recovered, limited requests allowed

Usage:
    from backend.app.core.resilience import CircuitBreaker, circuit_breaker
    
    # Create a circuit breaker
    breaker = CircuitBreaker(
        name="openai-api",
        failure_threshold=5,
        recovery_timeout=60,
    )
    
    # Use as decorator
    @breaker
    async def call_openai():
        ...
    
    # Or use the global registry
    @circuit_breaker("llm-api")
    async def call_llm():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger("xagent.resilience")

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when circuit is open and request is rejected."""
    
    def __init__(self, breaker_name: str, state: CircuitState):
        self.breaker_name = breaker_name
        self.state = state
        super().__init__(
            f"Circuit breaker '{breaker_name}' is {state.value}. "
            f"Request rejected to prevent cascading failure."
        )


class CircuitBreaker:
    """Circuit breaker for external service calls.
    
    Args:
        name: Unique name for this circuit breaker.
        failure_threshold: Number of failures before opening circuit.
        recovery_timeout: Seconds to wait before trying half-open.
        success_threshold: Successes needed in half-open to close circuit.
        excluded_exceptions: Exception types that don't count as failures.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
        excluded_exceptions: tuple[type[Exception], ...] = (),
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.excluded_exceptions = excluded_exceptions
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._lock = asyncio.Lock()
        
        # Metrics
        self.total_requests = 0
        self.total_failures = 0
        self.total_rejections = 0
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self._state == CircuitState.HALF_OPEN
    
    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_rejections": self.total_rejections,
            "last_failure_time": self._last_failure_time,
        }
    
    async def _check_state_transition(self) -> None:
        """Check if state should transition based on timeouts."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                logger.info(
                    f"Circuit '{self.name}' transitioning OPEN -> HALF_OPEN "
                    f"after {elapsed:.1f}s recovery timeout"
                )
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
    
    async def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function through circuit breaker.
        
        Args:
            func: Async function to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.
            
        Returns:
            Function result.
            
        Raises:
            CircuitBreakerError: If circuit is open.
        """
        async with self._lock:
            await self._check_state_transition()
            
            if self._state == CircuitState.OPEN:
                self.total_rejections += 1
                raise CircuitBreakerError(self.name, self._state)
        
        self.total_requests += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.excluded_exceptions:
            # Don't count excluded exceptions as failures
            raise
        except Exception as e:
            await self._on_failure(e)
            raise
    
    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info(
                        f"Circuit '{self.name}' transitioning HALF_OPEN -> CLOSED "
                        f"after {self._success_count} successes"
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
    
    async def _on_failure(self, error: Exception) -> None:
        """Handle failed call."""
        self.total_failures += 1
        
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                logger.warning(
                    f"Circuit '{self.name}' transitioning HALF_OPEN -> OPEN "
                    f"after failure: {error}"
                )
                self._state = CircuitState.OPEN
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    logger.warning(
                        f"Circuit '{self.name}' transitioning CLOSED -> OPEN "
                        f"after {self._failure_count} failures: {error}"
                    )
                    self._state = CircuitState.OPEN
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Use as decorator."""
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await self.call(func, *args, **kwargs)
        return wrapper
    
    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        **kwargs: Any,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                **kwargs,
            )
        return self._breakers[name]
    
    def get(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name."""
        return self._breakers.get(name)
    
    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all circuit breakers."""
        return {name: breaker.get_metrics() for name, breaker in self._breakers.items()}
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry
_registry = CircuitBreakerRegistry()


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    **kwargs: Any,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to wrap function with circuit breaker.
    
    Args:
        name: Circuit breaker name.
        failure_threshold: Failures before opening.
        recovery_timeout: Seconds before half-open.
        **kwargs: Additional CircuitBreaker arguments.
        
    Returns:
        Decorator function.
    """
    breaker = _registry.get_or_create(
        name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        **kwargs,
    )
    return breaker


def get_circuit_breaker(name: str) -> CircuitBreaker | None:
    """Get circuit breaker by name."""
    return _registry.get(name)


def get_all_circuit_metrics() -> dict[str, dict[str, Any]]:
    """Get metrics for all circuit breakers."""
    return _registry.get_all_metrics()


def reset_all_circuits() -> None:
    """Reset all circuit breakers."""
    _registry.reset_all()


# Pre-configured circuit breakers for common services
llm_circuit = _registry.get_or_create(
    "llm-api",
    failure_threshold=5,
    recovery_timeout=30,
)

database_circuit = _registry.get_or_create(
    "database",
    failure_threshold=3,
    recovery_timeout=10,
)

redis_circuit = _registry.get_or_create(
    "redis",
    failure_threshold=3,
    recovery_timeout=5,
)

qdrant_circuit = _registry.get_or_create(
    "qdrant",
    failure_threshold=5,
    recovery_timeout=30,
)
