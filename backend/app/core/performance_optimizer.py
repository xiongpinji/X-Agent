"""Performance optimization utilities for X-Agent.

Includes LLM optimization, async utilities, and performance monitoring.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, List, Optional
from datetime import datetime, UTC


@dataclass
class PerformanceMetric:
    """Performance metric record."""

    name: str
    duration_ms: float
    timestamp: datetime
    tags: dict[str, str]


class PerformanceMonitor:
    """Performance monitoring system."""

    def __init__(self, window_size: int = 1000):
        self.metrics: List[PerformanceMetric] = []
        self.window_size = window_size

    def record_metric(self, name: str, duration_ms: float, **tags) -> None:
        """Record performance metric."""
        metric = PerformanceMetric(
            name=name,
            duration_ms=duration_ms,
            timestamp=datetime.now(UTC),
            tags=tags
        )
        self.metrics.append(metric)

        # Maintain window size
        if len(self.metrics) > self.window_size:
            self.metrics.pop(0)

    def get_percentile(self, percentile: float) -> float:
        """Calculate percentile response time."""
        if not self.metrics:
            return 0

        sorted_metrics = sorted(self.metrics, key=lambda m: m.duration_ms)
        index = int(len(sorted_metrics) * percentile / 100)
        return sorted_metrics[index].duration_ms

    def get_metrics_by_name(self, name: str) -> List[PerformanceMetric]:
        """Get metrics by name."""
        return [m for m in self.metrics if m.name == name]

    def generate_report(self) -> dict[str, Any]:
        """Generate performance report."""
        if not self.metrics:
            return {
                'total_requests': 0,
                'avg_response_time_ms': 0,
                'p50_response_time_ms': 0,
                'p95_response_time_ms': 0,
                'p99_response_time_ms': 0,
                'throughput_rps': 0
            }

        durations = [m.duration_ms for m in self.metrics]
        avg_duration = sum(durations) / len(durations)

        # Calculate throughput
        time_span = (self.metrics[-1].timestamp - self.metrics[0].timestamp).total_seconds()
        throughput = len(self.metrics) / time_span if time_span > 0 else 0

        return {
            'total_requests': len(self.metrics),
            'avg_response_time_ms': avg_duration,
            'p50_response_time_ms': self.get_percentile(50),
            'p95_response_time_ms': self.get_percentile(95),
            'p99_response_time_ms': self.get_percentile(99),
            'throughput_rps': throughput
        }


class AsyncOptimizer:
    """Async execution optimizer."""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers

    async def run_concurrent(
        self,
        tasks: List[Callable],
        max_concurrent: int = 5
    ) -> List[Any]:
        """Run tasks concurrently with limit."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_task(task):
            async with semaphore:
                if asyncio.iscoroutinefunction(task):
                    return await task()
                return task()

        return await asyncio.gather(*[bounded_task(task) for task in tasks])

    async def run_with_timeout(
        self,
        coro,
        timeout: float = 30.0
    ) -> Any:
        """Run coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task exceeded {timeout}s timeout")

    async def batch_async_operations(
        self,
        items: List[Any],
        operation: Callable,
        batch_size: int = 10
    ) -> List[Any]:
        """Batch async operations."""
        results = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[operation(item) for item in batch]
            )
            results.extend(batch_results)
        return results


class LLMOptimizer:
    """LLM call optimizer."""

    def __init__(self, llm_router: Any, cache_manager: Any):
        self.llm = llm_router
        self.cache = cache_manager

    def optimize_prompt(self, prompt: str) -> str:
        """Optimize prompt length."""
        # Remove redundant whitespace
        prompt = ' '.join(prompt.split())

        # Remove duplicate lines
        lines = prompt.split('\n')
        unique_lines = []
        for line in lines:
            if line not in unique_lines:
                unique_lines.append(line)

        return '\n'.join(unique_lines)

    async def call_with_cache(self, request: dict[str, Any]) -> Optional[Any]:
        """Call LLM with caching."""
        import hashlib
        import json

        # Generate cache key
        content = json.dumps(request, sort_keys=True)
        cache_key = f"llm:{hashlib.md5(content.encode()).hexdigest()}"

        # Check cache
        if cached := await self.cache.get(cache_key):
            return cached

        # Execute call
        response = await self.llm.call(request)

        # Cache result
        await self.cache.set(cache_key, response, ttl=3600)
        return response

    async def batch_requests(
        self,
        requests: List[dict[str, Any]],
        batch_size: int = 5
    ) -> List[Any]:
        """Batch LLM requests."""
        results = []

        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[self.call_with_cache(req) for req in batch]
            )
            results.extend(batch_results)

        return results


def monitor_performance(monitor: PerformanceMonitor, name: Optional[str] = None):
    """Performance monitoring decorator."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start) * 1000
                monitor.record_metric(name or func.__name__, duration_ms)

        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start) * 1000
                monitor.record_metric(name or func.__name__, duration_ms)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
