"""
Unified Retry Mechanism for X-Agent

Implements comprehensive retry strategies with exponential backoff:
- Exponential backoff with jitter
- Retry budgets to prevent resource exhaustion
- Configurable retry policies per operation
- Detailed metrics and logging
- Automatic retry classification

Features:
- Multiple retry strategies
- Retry budget management
- Backoff calculation
- Retry context tracking
- Thread-safe operations
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from threading import RLock
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy(str, Enum):
    """Retry strategies"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


class RetryableException(Exception):
    """Base class for retryable exceptions"""
    pass


class RetryMetrics(BaseModel):
    """Metrics for retry monitoring"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_retries: int = 0
    successful_retries: int = 0
    failed_retries: int = 0
    budget_exhausted_count: int = 0
    average_retry_count: float = 0.0
    max_retry_count: int = 0
    total_backoff_time: float = 0.0
    last_attempt_time: datetime | None = None
    last_success_time: datetime | None = None
    last_failure_time: datetime | None = None


@dataclass
class RetryConfig:
    """Configuration for retry mechanism"""
    name: str
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: bool = True
    budget_per_minute: int = 100
    retryable_exceptions: tuple[type[Exception], ...] = (RetryableException, TimeoutError)


class RetryBudget:
    """Manages retry budget to prevent resource exhaustion"""

    def __init__(self, budget_per_minute: int = 100):
        self.budget_per_minute = budget_per_minute
        self.budget_window_start = time.time()
        self.budget_used = 0
        self._lock = RLock()

    def can_retry(self) -> bool:
        """Check if retry budget is available"""
        with self._lock:
            current_time = time.time()
            elapsed = current_time - self.budget_window_start

            # Reset budget window if minute has passed
            if elapsed >= 60:
                self.budget_window_start = current_time
                self.budget_used = 0

            return self.budget_used < self.budget_per_minute

    def consume(self) -> bool:
        """Consume one unit of retry budget"""
        with self._lock:
            if self.can_retry():
                self.budget_used += 1
                return True
            return False

    def get_remaining(self) -> int:
        """Get remaining budget"""
        with self._lock:
            current_time = time.time()
            elapsed = current_time - self.budget_window_start

            if elapsed >= 60:
                return self.budget_per_minute

            return max(0, self.budget_per_minute - self.budget_used)


class RetryContext:
    """Context for a single retry operation"""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.attempt_count = 0
        self.retry_count = 0
        self.total_backoff_time = 0.0
        self.last_exception: Optional[Exception] = None
        self.start_time = time.time()

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception is retryable"""
        return isinstance(exception, self.config.retryable_exceptions)

    def get_backoff_delay(self) -> float:
        """Calculate backoff delay for next retry"""
        if self.config.strategy == RetryStrategy.NO_RETRY:
            return 0.0

        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.initial_delay
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.initial_delay * (self.retry_count + 1)
        else:  # EXPONENTIAL_BACKOFF
            delay = self.config.initial_delay * (
                self.config.multiplier ** self.retry_count
            )

        # Cap delay
        delay = min(delay, self.config.max_delay)

        # Add jitter
        if self.config.jitter:
            jitter = random.uniform(0, delay * 0.1)
            delay += jitter

        return delay

    def record_attempt(self, success: bool, exception: Optional[Exception] = None) -> None:
        """Record an attempt"""
        self.attempt_count += 1
        if exception:
            self.last_exception = exception
            if not success:
                self.retry_count += 1

    def get_elapsed_time(self) -> float:
        """Get elapsed time since start"""
        return time.time() - self.start_time


class RetryExecutor:
    """
    Executes operations with retry logic.

    Handles retries with configurable strategies, budgets, and backoff.
    """

    def __init__(self, config: RetryConfig):
        self.config = config
        self.budget = RetryBudget(config.budget_per_minute)
        self._metrics = RetryMetrics()
        self._lock = RLock()

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: Last exception if all retries exhausted
        """
        context = RetryContext(self.config)

        while context.attempt_count <= self.config.max_retries:
            try:
                result = func(*args, **kwargs)
                self._record_success(context)
                return result
            except Exception as e:
                context.record_attempt(False, e)

                if not context.should_retry(e):
                    self._record_failure(context)
                    raise

                if context.retry_count >= self.config.max_retries:
                    self._record_failure(context)
                    logger.error(
                        f"Max retries exhausted for {self.config.name}: {e}"
                    )
                    raise

                if not self.budget.can_retry():
                    self._record_budget_exhausted(context)
                    logger.error(
                        f"Retry budget exhausted for {self.config.name}"
                    )
                    raise

                delay = context.get_backoff_delay()
                context.total_backoff_time += delay

                logger.warning(
                    f"Retry {context.retry_count}/{self.config.max_retries} "
                    f"for {self.config.name} after {delay:.2f}s: {e}"
                )

                time.sleep(delay)
                self.budget.consume()

        self._record_failure(context)
        raise RuntimeError(f"Retry execution failed for {self.config.name}")

    async def execute_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> T:
        """
        Execute async function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: Last exception if all retries exhausted
        """
        context = RetryContext(self.config)

        while context.attempt_count <= self.config.max_retries:
            try:
                result = await func(*args, **kwargs)
                self._record_success(context)
                return result
            except Exception as e:
                context.record_attempt(False, e)

                if not context.should_retry(e):
                    self._record_failure(context)
                    raise

                if context.retry_count >= self.config.max_retries:
                    self._record_failure(context)
                    logger.error(
                        f"Max retries exhausted for {self.config.name}: {e}"
                    )
                    raise

                if not self.budget.can_retry():
                    self._record_budget_exhausted(context)
                    logger.error(
                        f"Retry budget exhausted for {self.config.name}"
                    )
                    raise

                delay = context.get_backoff_delay()
                context.total_backoff_time += delay

                logger.warning(
                    f"Retry {context.retry_count}/{self.config.max_retries} "
                    f"for {self.config.name} after {delay:.2f}s: {e}"
                )

                import asyncio
                await asyncio.sleep(delay)
                self.budget.consume()

        self._record_failure(context)
        raise RuntimeError(f"Retry execution failed for {self.config.name}")

    def _record_success(self, context: RetryContext) -> None:
        """Record successful execution"""
        with self._lock:
            self._metrics.total_attempts += 1
            self._metrics.successful_attempts += 1
            if context.retry_count > 0:
                self._metrics.successful_retries += 1
            self._metrics.last_success_time = datetime.now(UTC)
            self._metrics.total_backoff_time += context.total_backoff_time

    def _record_failure(self, context: RetryContext) -> None:
        """Record failed execution"""
        with self._lock:
            self._metrics.total_attempts += 1
            self._metrics.failed_attempts += 1
            self._metrics.failed_retries += context.retry_count
            self._metrics.last_failure_time = datetime.now(UTC)
            self._metrics.total_backoff_time += context.total_backoff_time
            self._metrics.max_retry_count = max(
                self._metrics.max_retry_count, context.retry_count
            )

    def _record_budget_exhausted(self, context: RetryContext) -> None:
        """Record budget exhaustion"""
        with self._lock:
            self._metrics.budget_exhausted_count += 1
            self._record_failure(context)

    def get_metrics(self) -> RetryMetrics:
        """Get current metrics"""
        with self._lock:
            return self._metrics.model_copy()

    def get_budget_status(self) -> dict[str, Any]:
        """Get retry budget status"""
        return {
            "remaining": self.budget.get_remaining(),
            "total": self.config.budget_per_minute,
            "used": self.budget.budget_used,
        }


class RetryRegistry:
    """Registry for managing retry executors"""

    def __init__(self):
        self._executors: dict[str, RetryExecutor] = {}
        self._lock = RLock()

    def get_or_create(self, config: RetryConfig) -> RetryExecutor:
        """Get or create retry executor"""
        with self._lock:
            if config.name not in self._executors:
                self._executors[config.name] = RetryExecutor(config)
                logger.info(f"Created retry executor: {config.name}")
            return self._executors[config.name]

    def get(self, name: str) -> RetryExecutor | None:
        """Get retry executor by name"""
        with self._lock:
            return self._executors.get(name)

    def get_all_metrics(self) -> dict[str, RetryMetrics]:
        """Get metrics for all executors"""
        with self._lock:
            return {
                name: executor.get_metrics()
                for name, executor in self._executors.items()
            }


# Global registry instance
_retry_registry = RetryRegistry()


def get_retry_registry() -> RetryRegistry:
    """Get global retry registry"""
    return _retry_registry
