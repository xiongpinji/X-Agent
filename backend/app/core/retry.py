"""
Intelligent retry mechanism with exponential backoff and jitter.

Features:
- Exponential backoff strategy
- Jitter support to prevent thundering herd
- Configurable retry conditions
- Maximum retry attempts and timeout control
- Async/sync support
- Decorator-based API
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar, overload

from backend.app.core.exceptions import XAgentException

logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class RetryConfig:
    """Retry configuration."""

    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_range: tuple[float, float] = (0.5, 1.5)
    timeout: float | None = None
    retryable_exceptions: tuple[type[Exception], ...] = (XAgentException,)
    retry_condition: Callable[[Exception], bool] | None = None


class RetryStrategy:
    """Base retry strategy."""

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with retry logic."""
        raise NotImplementedError


class ExponentialBackoffRetry(RetryStrategy):
    """Exponential backoff retry strategy."""

    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = config or RetryConfig()

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with exponential backoff retry."""
        last_exception: Exception | None = None
        start_time = time.time()

        for attempt in range(self.config.max_attempts):
            try:
                # Check timeout
                if self.config.timeout:
                    elapsed = time.time() - start_time
                    if elapsed > self.config.timeout:
                        raise TimeoutError(
                            f"Retry timeout exceeded: {elapsed:.2f}s > {self.config.timeout}s"
                        )

                # Execute function
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                # Check if exception is retryable
                if not self._is_retryable(e):
                    raise

                # Check if this is the last attempt
                if attempt >= self.config.max_attempts - 1:
                    logger.error(
                        f"All {self.config.max_attempts} retry attempts failed. "
                        f"Last error: {e}"
                    )
                    raise

                # Calculate delay
                delay = self._calculate_delay(attempt)

                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_attempts} failed. "
                    f"Retrying in {delay:.2f}s. Error: {e}"
                )

                await asyncio.sleep(delay)

        # Should not reach here
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry loop ended unexpectedly")

    def _is_retryable(self, exception: Exception) -> bool:
        """Check if exception is retryable."""
        # Check exception type
        if not isinstance(exception, self.config.retryable_exceptions):
            return False

        # Check custom retry condition
        if self.config.retry_condition:
            return self.config.retry_condition(exception)

        # Check if exception has is_retryable attribute
        if isinstance(exception, XAgentException):
            return exception.is_retryable

        return True

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = min(
            self.config.initial_delay * (self.config.exponential_base ** attempt),
            self.config.max_delay,
        )

        if self.config.jitter:
            jitter_min, jitter_max = self.config.jitter_range
            delay *= random.uniform(jitter_min, jitter_max)

        return delay


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    timeout: float | None = None,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    retry_condition: Callable[[Exception], bool] | None = None,
) -> Callable[[F], F]:
    """Decorator for retrying async/sync functions.

    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add jitter to delays
        timeout: Total timeout for all retries
        retryable_exceptions: Tuple of exception types to retry on
        retry_condition: Custom function to determine if exception is retryable

    Example:
        @retry(max_attempts=3, initial_delay=1.0)
        async def call_api():
            return await api.fetch()
    """
    if retryable_exceptions is None:
        retryable_exceptions = (XAgentException,)

    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        timeout=timeout,
        retryable_exceptions=retryable_exceptions,
        retry_condition=retry_condition,
    )

    def decorator(func: F) -> F:
        strategy = ExponentialBackoffRetry(config)

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await strategy.execute(func, *args, **kwargs)

            return async_wrapper  # type: ignore

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Run async retry in event loop for sync functions
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(
                        strategy.execute(func, *args, **kwargs)
                    )
                finally:
                    loop.close()

            return sync_wrapper  # type: ignore

    return decorator


class RetryableOperation:
    """Context manager for retryable operations."""

    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = config or RetryConfig()
        self.strategy = ExponentialBackoffRetry(self.config)
        self.attempt = 0
        self.last_exception: Exception | None = None

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with retry logic."""
        return await self.strategy.execute(func, *args, **kwargs)

    def __enter__(self) -> RetryableOperation:
        """Enter context manager."""
        self.attempt = 0
        self.last_exception = None
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit context manager."""
        if exc_val is None:
            return False

        self.last_exception = exc_val
        self.attempt += 1

        if self.attempt >= self.config.max_attempts:
            return False

        if not self.strategy._is_retryable(exc_val):
            return False

        logger.warning(
            f"Attempt {self.attempt}/{self.config.max_attempts} failed. "
            f"Error: {exc_val}"
        )

        return True

    async def __aenter__(self) -> RetryableOperation:
        """Async enter context manager."""
        self.attempt = 0
        self.last_exception = None
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Async exit context manager."""
        return self.__exit__(exc_type, exc_val, exc_tb)
