"""
Error recovery strategies for resilient operations.

Implements:
- Automatic retry with backoff
- Graceful degradation
- Compensating transactions
- Error isolation
- Recovery state management
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Generic, TypeVar

from backend.app.core.exceptions import XAgentException
from backend.app.core.retry import ExponentialBackoffRetry, RetryConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RecoveryStrategy(StrEnum):
    """Recovery strategies."""

    RETRY = "retry"
    FALLBACK = "fallback"
    COMPENSATE = "compensate"
    ISOLATE = "isolate"
    DEGRADE = "degrade"


@dataclass
class RecoveryAction:
    """Recovery action configuration."""

    strategy: RecoveryStrategy
    handler: Callable[..., Any]
    priority: int = 0
    enabled: bool = True


class RecoveryContext:
    """Context for recovery operations."""

    def __init__(self) -> None:
        self.attempt_count = 0
        self.last_error: Exception | None = None
        self.recovery_actions: list[RecoveryAction] = []
        self.state: dict[str, Any] = {}
        self.compensations: list[Callable[..., Any]] = []

    def add_recovery_action(self, action: RecoveryAction) -> None:
        """Add a recovery action."""
        self.recovery_actions.append(action)
        self.recovery_actions.sort(key=lambda a: a.priority, reverse=True)

    def add_compensation(self, handler: Callable[..., Any]) -> None:
        """Add a compensation handler."""
        self.compensations.append(handler)

    async def execute_compensations(self) -> None:
        """Execute all compensation handlers."""
        for handler in reversed(self.compensations):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                logger.error(f"Compensation handler failed: {e}")


class ErrorRecoveryManager:
    """Manages error recovery strategies."""

    def __init__(self) -> None:
        self._recovery_handlers: dict[type[Exception], list[RecoveryAction]] = {}
        self._lock = asyncio.Lock()

    def register_recovery(
        self,
        exception_type: type[Exception],
        action: RecoveryAction,
    ) -> None:
        """Register a recovery action for an exception type."""
        if exception_type not in self._recovery_handlers:
            self._recovery_handlers[exception_type] = []
        self._recovery_handlers[exception_type].append(action)
        self._recovery_handlers[exception_type].sort(
            key=lambda a: a.priority, reverse=True
        )

    async def recover(
        self,
        exception: Exception,
        context: RecoveryContext | None = None,
    ) -> Any:
        """Attempt to recover from an exception."""
        context = context or RecoveryContext()
        context.last_error = exception
        context.attempt_count += 1

        # Find applicable recovery actions
        handlers = self._recovery_handlers.get(type(exception), [])
        if not handlers:
            handlers = self._recovery_handlers.get(Exception, [])

        for action in handlers:
            if not action.enabled:
                continue

            try:
                logger.info(
                    f"Attempting {action.strategy.value} recovery for {type(exception).__name__}"
                )

                if asyncio.iscoroutinefunction(action.handler):
                    result = await action.handler(exception, context)
                else:
                    result = action.handler(exception, context)

                logger.info(f"Recovery succeeded with strategy: {action.strategy.value}")
                return result

            except Exception as e:
                logger.warning(
                    f"Recovery with {action.strategy.value} failed: {e}"
                )
                continue

        raise exception


class RetryRecovery:
    """Retry-based recovery."""

    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = config or RetryConfig()
        self.strategy = ExponentialBackoffRetry(self.config)

    async def recover(
        self,
        exception: Exception,
        context: RecoveryContext,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Recover by retrying the operation."""
        logger.info(f"Retrying operation after error: {exception}")
        return await self.strategy.execute(func, *args, **kwargs)


class FallbackRecovery:
    """Fallback-based recovery."""

    def __init__(self, fallback_func: Callable[..., Any]) -> None:
        self.fallback_func = fallback_func

    async def recover(
        self,
        exception: Exception,
        context: RecoveryContext,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Recover using fallback function."""
        logger.info(f"Using fallback after error: {exception}")

        if asyncio.iscoroutinefunction(self.fallback_func):
            return await self.fallback_func(*args, **kwargs)
        else:
            return self.fallback_func(*args, **kwargs)


class CompensatingTransaction:
    """Compensating transaction for recovery."""

    def __init__(self) -> None:
        self.operations: list[tuple[Callable[..., Any], tuple, dict]] = []
        self.compensations: list[Callable[..., Any]] = []

    def add_operation(
        self,
        func: Callable[..., Any],
        *args: Any,
        compensation: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Add an operation with optional compensation."""
        self.operations.append((func, args, kwargs))
        if compensation:
            self.compensations.append(compensation)

    async def execute(self) -> list[Any]:
        """Execute all operations."""
        results = []
        executed = 0

        try:
            for func, args, kwargs in self.operations:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                results.append(result)
                executed += 1

            return results

        except Exception as e:
            logger.error(f"Operation failed at step {executed}, compensating...")
            await self._compensate()
            raise

    async def _compensate(self) -> None:
        """Execute compensations in reverse order."""
        for compensation in reversed(self.compensations):
            try:
                if asyncio.iscoroutinefunction(compensation):
                    await compensation()
                else:
                    compensation()
            except Exception as e:
                logger.error(f"Compensation failed: {e}")


class ErrorIsolation:
    """Error isolation for fault containment."""

    def __init__(self, isolation_level: str = "operation") -> None:
        self.isolation_level = isolation_level
        self.isolated_errors: list[Exception] = []
        self._lock = asyncio.Lock()

    async def isolate(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with error isolation."""
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except Exception as e:
            async with self._lock:
                self.isolated_errors.append(e)

            logger.error(
                f"Error isolated at {self.isolation_level} level: {e}"
            )

            # Re-raise or handle based on isolation level
            if self.isolation_level == "operation":
                return None
            elif self.isolation_level == "component":
                raise
            else:
                raise

    async def get_isolated_errors(self) -> list[Exception]:
        """Get isolated errors."""
        async with self._lock:
            return self.isolated_errors.copy()

    async def clear_isolated_errors(self) -> None:
        """Clear isolated errors."""
        async with self._lock:
            self.isolated_errors.clear()


class RecoveryPolicy:
    """Policy for error recovery."""

    def __init__(self) -> None:
        self.retry_recovery = RetryRecovery()
        self.error_recovery_manager = ErrorRecoveryManager()
        self.error_isolation = ErrorIsolation()

    async def apply_recovery(
        self,
        exception: Exception,
        context: RecoveryContext | None = None,
    ) -> Any:
        """Apply recovery policy."""
        context = context or RecoveryContext()

        try:
            return await self.error_recovery_manager.recover(exception, context)
        except Exception as e:
            logger.error(f"Recovery policy failed: {e}")
            raise


# Global recovery policy
_recovery_policy: RecoveryPolicy | None = None


def get_recovery_policy() -> RecoveryPolicy:
    """Get or create the global recovery policy."""
    global _recovery_policy
    if _recovery_policy is None:
        _recovery_policy = RecoveryPolicy()
    return _recovery_policy
