"""Error Handling for Workflows

Implements error handling constructs:
- Try/Catch/Finally blocks
- Retry policies with backoff
- Compensation strategies
- Error notifications
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Callable, Awaitable
from uuid import uuid4


class RetryStrategy(StrEnum):
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"


class CompensationType(StrEnum):
    ROLLBACK = "rollback"
    RETRY = "retry"
    SKIP = "skip"
    ALERT = "alert"
    FALLBACK = "fallback"


@dataclass
class RetryPolicy:
    """Retry policy configuration"""
    max_attempts: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 30000
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    jitter: bool = True

    def get_delay(self, attempt: int) -> int:
        """Calculate delay for attempt"""
        if attempt <= 0:
            return 0

        if self.strategy == RetryStrategy.FIXED:
            delay = self.initial_delay_ms
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.initial_delay_ms * attempt
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = int(self.initial_delay_ms * (self.backoff_multiplier ** (attempt - 1)))
        elif self.strategy == RetryStrategy.FIBONACCI:
            delay = self._fibonacci_delay(attempt)
        else:
            delay = self.initial_delay_ms

        # Cap at max delay
        delay = min(delay, self.max_delay_ms)

        # Add jitter
        if self.jitter:
            import random
            jitter_amount = int(delay * 0.1)
            delay += random.randint(-jitter_amount, jitter_amount)

        return max(0, delay)

    @staticmethod
    def _fibonacci_delay(attempt: int) -> int:
        """Calculate Fibonacci-based delay"""
        a, b = 1, 1
        for _ in range(attempt - 1):
            a, b = b, a + b
        return a * 100


@dataclass
class CompensationStrategy:
    """Compensation strategy for error recovery"""
    type: CompensationType = CompensationType.ROLLBACK
    action: str = ""
    fallback_value: Any = None
    notify_channels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorContext:
    """Context for error handling"""
    error: Exception
    attempt: int
    max_attempts: int
    node_id: str
    workflow_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_retryable(self) -> bool:
        """Check if error is retryable"""
        # Transient errors are retryable
        transient_errors = (
            TimeoutError,
            ConnectionError,
            asyncio.TimeoutError,
        )
        return isinstance(self.error, transient_errors)

    def should_retry(self) -> bool:
        """Check if should retry"""
        return self.is_retryable() and self.attempt < self.max_attempts


@dataclass
class ErrorHandler:
    """Handles errors in workflow execution"""
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    compensation_strategy: CompensationStrategy = field(default_factory=CompensationStrategy)
    error_handlers: dict[str, Callable[[ErrorContext], Awaitable[Any]]] = field(default_factory=dict)
    error_history: list[ErrorContext] = field(default_factory=list)

    async def handle_error(
        self,
        error: Exception,
        node_id: str,
        workflow_id: str,
        attempt: int,
        executor: Callable[[], Awaitable[Any]] | None = None,
    ) -> Any:
        """Handle error with retry and compensation"""
        context = ErrorContext(
            error=error,
            attempt=attempt,
            max_attempts=self.retry_policy.max_attempts,
            node_id=node_id,
            workflow_id=workflow_id,
        )
        self.error_history.append(context)

        # Check for custom error handler
        error_type = type(error).__name__
        if error_type in self.error_handlers:
            handler = self.error_handlers[error_type]
            return await handler(context)

        # Check if should retry
        if context.should_retry() and executor:
            delay_ms = self.retry_policy.get_delay(attempt)
            await asyncio.sleep(delay_ms / 1000)
            return None  # Signal to retry

        # Apply compensation strategy
        return await self._apply_compensation(context)

    async def _apply_compensation(self, context: ErrorContext) -> Any:
        """Apply compensation strategy"""
        strategy = self.compensation_strategy

        if strategy.type == CompensationType.ROLLBACK:
            return await self._rollback(context)
        elif strategy.type == CompensationType.RETRY:
            return None  # Signal to retry
        elif strategy.type == CompensationType.SKIP:
            return {"skipped": True, "reason": str(context.error)}
        elif strategy.type == CompensationType.ALERT:
            await self._send_alert(context)
            raise context.error
        elif strategy.type == CompensationType.FALLBACK:
            return strategy.fallback_value

        raise context.error

    async def _rollback(self, context: ErrorContext) -> Any:
        """Execute rollback"""
        return {
            "rolled_back": True,
            "error": str(context.error),
            "node_id": context.node_id,
            "timestamp": context.timestamp.isoformat(),
        }

    async def _send_alert(self, context: ErrorContext) -> None:
        """Send error alert"""
        for channel in self.compensation_strategy.notify_channels:
            # Placeholder for notification logic
            pass

    def register_error_handler(
        self,
        error_type: str,
        handler: Callable[[ErrorContext], Awaitable[Any]],
    ) -> None:
        """Register custom error handler"""
        self.error_handlers[error_type] = handler

    def get_error_summary(self) -> dict[str, Any]:
        """Get summary of errors"""
        return {
            "total_errors": len(self.error_history),
            "errors_by_type": self._group_errors_by_type(),
            "recent_errors": [
                {
                    "error": str(e.error),
                    "node_id": e.node_id,
                    "attempt": e.attempt,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in self.error_history[-10:]
            ],
        }

    def _group_errors_by_type(self) -> dict[str, int]:
        """Group errors by type"""
        result = {}
        for context in self.error_history:
            error_type = type(context.error).__name__
            result[error_type] = result.get(error_type, 0) + 1
        return result


class TryCatchFinally:
    """Try/Catch/Finally block for workflows"""

    def __init__(
        self,
        try_fn: Callable[[], Awaitable[Any]],
        catch_fn: Callable[[Exception], Awaitable[Any]] | None = None,
        finally_fn: Callable[[], Awaitable[None]] | None = None,
    ):
        self.try_fn = try_fn
        self.catch_fn = catch_fn
        self.finally_fn = finally_fn
        self.result: Any = None
        self.error: Exception | None = None

    async def execute(self) -> Any:
        """Execute try/catch/finally"""
        try:
            self.result = await self.try_fn()
            return self.result
        except Exception as e:
            self.error = e
            if self.catch_fn:
                return await self.catch_fn(e)
            raise
        finally:
            if self.finally_fn:
                await self.finally_fn()


class ErrorNotifier:
    """Notifies about errors"""

    def __init__(self):
        self.channels: dict[str, Callable[[dict[str, Any]], Awaitable[None]]] = {}
        self.notification_history: list[dict[str, Any]] = []

    def register_channel(
        self,
        channel_name: str,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Register notification channel"""
        self.channels[channel_name] = handler

    async def notify(
        self,
        error: Exception,
        node_id: str,
        workflow_id: str,
        channels: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Send error notification"""
        notification = {
            "id": str(uuid4()),
            "error": str(error),
            "error_type": type(error).__name__,
            "node_id": node_id,
            "workflow_id": workflow_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": metadata or {},
        }
        self.notification_history.append(notification)

        channels = channels or list(self.channels.keys())
        for channel in channels:
            if channel in self.channels:
                try:
                    await self.channels[channel](notification)
                except Exception:
                    pass  # Silently fail notification

    async def notify_slack(self, message: dict[str, Any]) -> None:
        """Send Slack notification"""
        # Placeholder for Slack integration
        pass

    async def notify_email(self, message: dict[str, Any]) -> None:
        """Send email notification"""
        # Placeholder for email integration
        pass

    async def notify_webhook(self, message: dict[str, Any]) -> None:
        """Send webhook notification"""
        # Placeholder for webhook integration
        pass

    def get_notification_summary(self) -> dict[str, Any]:
        """Get notification summary"""
        return {
            "total_notifications": len(self.notification_history),
            "by_channel": self._group_by_channel(),
            "recent": self.notification_history[-10:],
        }

    def _group_by_channel(self) -> dict[str, int]:
        """Group notifications by channel"""
        result = {}
        for channel in self.channels:
            result[channel] = 0
        return result
