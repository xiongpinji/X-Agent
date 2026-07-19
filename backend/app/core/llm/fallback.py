"""Fallback strategies for LLM routing and error handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
import asyncio


class FallbackStrategy(Enum):
    """Fallback strategies for handling LLM failures."""

    SEQUENTIAL = "sequential"  # Try backends in order
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # Retry with exponential backoff
    CIRCUIT_BREAKER = "circuit_breaker"  # Stop trying after threshold
    DEGRADED_MODE = "degraded_mode"  # Use simpler/cheaper model
    CACHE_FALLBACK = "cache_fallback"  # Return cached response
    QUEUE_RETRY = "queue_retry"  # Queue for later retry


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""

    strategy: FallbackStrategy = FallbackStrategy.SEQUENTIAL
    max_retries: int = 3
    initial_retry_delay_ms: int = 100
    max_retry_delay_ms: int = 5000
    backoff_multiplier: float = 2.0
    circuit_breaker_threshold: int = 5  # Failures before opening circuit
    circuit_breaker_timeout_s: int = 60  # Time before trying again
    degradation_models: list[str] = field(default_factory=list)  # Models to use in degraded mode
    timeout_ms: int = 30000


@dataclass
class ErrorContext:
    """Context about an error for fallback decision."""

    error_type: str  # "timeout", "rate_limit", "api_error", "unknown"
    error_message: str
    model: str
    provider: str
    timestamp: datetime
    retry_count: int = 0
    is_transient: bool = False  # Can be retried


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures."""

    def __init__(self, threshold: int = 5, timeout_s: int = 60):
        """Initialize circuit breaker."""
        self.threshold = threshold
        self.timeout_s = timeout_s
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half_open

    def record_success(self) -> None:
        """Record a successful call."""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.threshold:
            self.state = "open"

    def is_available(self) -> bool:
        """Check if circuit is available."""
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed > self.timeout_s:
                    self.state = "half_open"
                    return True
            return False

        # half_open state
        return True

    def get_state(self) -> str:
        """Get current circuit state."""
        return self.state


class FallbackManager:
    """Manage fallback strategies for LLM routing."""

    def __init__(self, config: FallbackConfig):
        """Initialize fallback manager."""
        self.config = config
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.error_history: list[ErrorContext] = []
        self.retry_queue: list[dict[str, Any]] = []

    def get_circuit_breaker(self, model: str) -> CircuitBreaker:
        """Get or create circuit breaker for a model."""
        if model not in self.circuit_breakers:
            self.circuit_breakers[model] = CircuitBreaker(
                threshold=self.config.circuit_breaker_threshold,
                timeout_s=self.config.circuit_breaker_timeout_s,
            )
        return self.circuit_breakers[model]

    def should_retry(self, error: ErrorContext) -> bool:
        """Determine if a request should be retried."""
        if error.retry_count >= self.config.max_retries:
            return False

        if not error.is_transient:
            return False

        # Check circuit breaker
        cb = self.get_circuit_breaker(error.model)
        if not cb.is_available():
            return False

        return True

    def get_retry_delay_ms(self, retry_count: int) -> int:
        """Calculate retry delay with exponential backoff."""
        if self.config.strategy != FallbackStrategy.EXPONENTIAL_BACKOFF:
            return self.config.initial_retry_delay_ms

        delay = self.config.initial_retry_delay_ms * (
            self.config.backoff_multiplier ** retry_count
        )
        return min(int(delay), self.config.max_retry_delay_ms)

    def get_fallback_model(self, failed_model: str) -> Optional[str]:
        """Get a fallback model to try."""
        if not self.config.degradation_models:
            return None

        # Return first available degradation model
        for model in self.config.degradation_models:
            cb = self.get_circuit_breaker(model)
            if cb.is_available():
                return model

        return None

    def record_error(self, error: ErrorContext) -> None:
        """Record an error for analysis."""
        self.error_history.append(error)

        # Keep only last 1000 errors
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-1000:]

        # Update circuit breaker
        cb = self.get_circuit_breaker(error.model)
        cb.record_failure()

    def record_success(self, model: str) -> None:
        """Record a successful call."""
        cb = self.get_circuit_breaker(model)
        cb.record_success()

    def classify_error(self, error: Exception) -> ErrorContext:
        """Classify an error for fallback decision."""
        error_str = str(error).lower()

        if "timeout" in error_str or "timed out" in error_str:
            error_type = "timeout"
            is_transient = True
        elif "rate" in error_str or "429" in error_str:
            error_type = "rate_limit"
            is_transient = True
        elif "api" in error_str or "500" in error_str or "503" in error_str:
            error_type = "api_error"
            is_transient = True
        else:
            error_type = "unknown"
            is_transient = False

        return ErrorContext(
            error_type=error_type,
            error_message=str(error),
            model="unknown",
            provider="unknown",
            timestamp=datetime.now(),
            is_transient=is_transient,
        )

    async def execute_with_fallback(
        self,
        primary_fn: Callable[[], Awaitable[Any]],
        fallback_fns: list[Callable[[], Awaitable[Any]]],
        model_name: str = "unknown",
    ) -> Any:
        """Execute a function with fallback options."""
        all_fns = [primary_fn] + fallback_fns
        last_error: Optional[Exception] = None

        for attempt, fn in enumerate(all_fns):
            try:
                result = await asyncio.wait_for(
                    fn(),
                    timeout=self.config.timeout_ms / 1000.0
                )
                self.record_success(model_name)
                return result

            except asyncio.TimeoutError as e:
                last_error = e
                error = self.classify_error(e)
                error.model = model_name
                error.retry_count = attempt

                if self.should_retry(error):
                    delay = self.get_retry_delay_ms(attempt)
                    await asyncio.sleep(delay / 1000.0)
                    continue

                self.record_error(error)

            except Exception as e:
                last_error = e
                error = self.classify_error(e)
                error.model = model_name
                error.retry_count = attempt

                if self.should_retry(error):
                    delay = self.get_retry_delay_ms(attempt)
                    await asyncio.sleep(delay / 1000.0)
                    continue

                self.record_error(error)

        raise last_error or RuntimeError("All fallback options exhausted")

    def get_error_stats(self, hours: int = 24) -> dict[str, Any]:
        """Get error statistics."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_errors = [e for e in self.error_history if e.timestamp > cutoff]

        if not recent_errors:
            return {
                "total_errors": 0,
                "errors_by_type": {},
                "errors_by_model": {},
                "transient_errors": 0,
            }

        errors_by_type = {}
        errors_by_model = {}
        transient_count = 0

        for error in recent_errors:
            errors_by_type[error.error_type] = errors_by_type.get(error.error_type, 0) + 1
            errors_by_model[error.model] = errors_by_model.get(error.model, 0) + 1
            if error.is_transient:
                transient_count += 1

        return {
            "total_errors": len(recent_errors),
            "errors_by_type": errors_by_type,
            "errors_by_model": errors_by_model,
            "transient_errors": transient_count,
            "transient_error_rate": transient_count / len(recent_errors) if recent_errors else 0,
        }

    def get_circuit_breaker_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {
            model: {
                "state": cb.state,
                "failure_count": cb.failure_count,
                "available": cb.is_available(),
            }
            for model, cb in self.circuit_breakers.items()
        }
