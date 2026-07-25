"""Analytics data collector."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from typing import Any

from .models import (
    APICallMetric,
    ErrorMetric,
    PerformanceMetric,
    TokenUsageMetric,
    ToolUsageMetric,
)


class AnalyticsCollector:
    """Collects analytics data from various sources."""

    def __init__(self, buffer_size: int = 10000, flush_interval_seconds: int = 60):
        """Initialize the collector.

        Args:
            buffer_size: Maximum number of metrics to buffer before flushing
            flush_interval_seconds: Interval for automatic flushing
        """
        self.buffer_size = buffer_size
        self.flush_interval_seconds = flush_interval_seconds
        self.metrics_buffer: list[Any] = []
        self.lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the collector."""
        self._flush_task = asyncio.create_task(self._auto_flush())

    async def stop(self) -> None:
        """Stop the collector."""
        if self._flush_task:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task

    async def record_api_call(
        self,
        tenant_id: str,
        user_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        request_size_bytes: int = 0,
        response_size_bytes: int = 0,
        error_message: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record an API call metric.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            endpoint: API endpoint
            method: HTTP method
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
            request_size_bytes: Request size in bytes
            response_size_bytes: Response size in bytes
            error_message: Error message if applicable
            tags: Additional tags
        """
        metric = APICallMetric(
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            request_size_bytes=request_size_bytes,
            response_size_bytes=response_size_bytes,
            error_message=error_message,
            tags=tags or {},
        )
        await self._add_metric(metric)

    async def record_token_usage(
        self,
        tenant_id: str,
        user_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record token usage metric.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_usd: Cost in USD
            tags: Additional tags
        """
        metric = TokenUsageMetric(
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            user_id=user_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost_usd,
            tags=tags or {},
        )
        await self._add_metric(metric)

    async def record_tool_usage(
        self,
        tenant_id: str,
        user_id: str,
        tool_name: str,
        tool_type: str,
        execution_time_ms: float,
        success: bool,
        error_message: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record tool usage metric.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            tool_name: Tool name
            tool_type: Tool type
            execution_time_ms: Execution time in milliseconds
            success: Whether execution was successful
            error_message: Error message if applicable
            tags: Additional tags
        """
        metric = ToolUsageMetric(
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            user_id=user_id,
            tool_name=tool_name,
            tool_type=tool_type,
            execution_time_ms=execution_time_ms,
            success=success,
            error_message=error_message,
            tags=tags or {},
        )
        await self._add_metric(metric)

    async def record_error(
        self,
        tenant_id: str,
        user_id: str,
        error_type: str,
        error_message: str,
        endpoint: str | None = None,
        stack_trace: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record error metric.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            error_type: Type of error
            error_message: Error message
            endpoint: API endpoint if applicable
            stack_trace: Stack trace if applicable
            tags: Additional tags
        """
        metric = ErrorMetric(
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            user_id=user_id,
            error_type=error_type,
            error_message=error_message,
            endpoint=endpoint,
            stack_trace=stack_trace,
            tags=tags or {},
        )
        await self._add_metric(metric)

    async def record_performance(
        self,
        tenant_id: str,
        metric_name: str,
        value: float,
        unit: str,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record performance metric.

        Args:
            tenant_id: Tenant identifier
            metric_name: Metric name
            value: Metric value
            unit: Unit of measurement
            tags: Additional tags
        """
        metric = PerformanceMetric(
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            metric_name=metric_name,
            value=value,
            unit=unit,
            tags=tags or {},
        )
        await self._add_metric(metric)

    async def flush(self) -> list[Any]:
        """Flush buffered metrics.

        Returns:
            List of flushed metrics
        """
        async with self.lock:
            metrics = self.metrics_buffer.copy()
            self.metrics_buffer.clear()
            return metrics

    async def _add_metric(self, metric: Any) -> None:
        """Add metric to buffer.

        Args:
            metric: Metric to add
        """
        async with self.lock:
            self.metrics_buffer.append(metric)
            if len(self.metrics_buffer) >= self.buffer_size:
                # Trigger flush in background
                asyncio.create_task(self.flush())

    async def _auto_flush(self) -> None:
        """Automatically flush metrics at regular intervals."""
        while True:
            try:
                await asyncio.sleep(self.flush_interval_seconds)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error during auto-flush: {e}")
