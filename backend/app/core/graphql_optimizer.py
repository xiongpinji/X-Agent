"""GraphQL Query Optimization

Optimizes GraphQL queries for better performance:
- Query complexity analysis
- Depth limiting
- Field resolution optimization
- Batch loading (DataLoader pattern)
- Query result caching
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("xagent.graphql_perf")


@dataclass
class QueryComplexity:
    """GraphQL query complexity metrics."""
    total_complexity: float
    max_depth: int
    field_count: int
    alias_count: int
    fragment_count: int
    directive_count: int
    is_valid: bool = True
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class QueryComplexityAnalyzer:
    """Analyze GraphQL query complexity."""

    # Complexity limits
    MAX_QUERY_COMPLEXITY = 1000
    MAX_QUERY_DEPTH = 10
    MAX_FIELD_COUNT = 100

    @staticmethod
    def analyze_query(query: str) -> QueryComplexity:
        """Analyze GraphQL query complexity."""
        complexity = QueryComplexity(
            total_complexity=0.0,
            max_depth=0,
            field_count=0,
            alias_count=0,
            fragment_count=0,
            directive_count=0,
        )

        # Parse query structure
        lines = query.split('\n')
        current_depth = 0
        max_depth = 0

        for line in lines:
            stripped = line.strip()

            # Count opening braces (increase depth)
            if '{' in stripped:
                current_depth += stripped.count('{')
                max_depth = max(max_depth, current_depth)

            # Count closing braces (decrease depth)
            if '}' in stripped:
                current_depth -= stripped.count('}')

            # Count fields
            if ':' in stripped and not stripped.startswith('#'):
                complexity.field_count += 1

            # Count aliases
            if ':' in stripped and not stripped.startswith('__'):
                complexity.alias_count += 1

            # Count fragments
            if 'fragment' in stripped.lower():
                complexity.fragment_count += 1

            # Count directives
            if '@' in stripped:
                complexity.directive_count += 1

        complexity.max_depth = max_depth
        complexity.total_complexity = (
            complexity.field_count * 1.0 +
            complexity.max_depth * 10.0 +
            complexity.fragment_count * 5.0
        )

        # Validate complexity
        if complexity.total_complexity > QueryComplexityAnalyzer.MAX_QUERY_COMPLEXITY:
            complexity.is_valid = False
            complexity.warnings.append(
                f"Query complexity {complexity.total_complexity} exceeds limit "
                f"{QueryComplexityAnalyzer.MAX_QUERY_COMPLEXITY}"
            )

        if complexity.max_depth > QueryComplexityAnalyzer.MAX_QUERY_DEPTH:
            complexity.is_valid = False
            complexity.warnings.append(
                f"Query depth {complexity.max_depth} exceeds limit "
                f"{QueryComplexityAnalyzer.MAX_QUERY_DEPTH}"
            )

        if complexity.field_count > QueryComplexityAnalyzer.MAX_FIELD_COUNT:
            complexity.is_valid = False
            complexity.warnings.append(
                f"Field count {complexity.field_count} exceeds limit "
                f"{QueryComplexityAnalyzer.MAX_FIELD_COUNT}"
            )

        return complexity

    @staticmethod
    def suggest_optimizations(query: str) -> list[str]:
        """Suggest query optimizations."""
        suggestions = []

        # Check for SELECT *
        if "{ ... }" in query or "{ __typename" in query:
            suggestions.append("Specify only needed fields instead of using fragments")

        # Check for nested queries
        if query.count('{') > 5:
            suggestions.append("Consider breaking complex query into multiple requests")

        # Check for aliases
        if query.count(':') > 10:
            suggestions.append("Reduce number of field aliases")

        return suggestions


class DataLoader:
    """Batch load data to prevent N+1 queries."""

    def __init__(self, batch_fn: Callable, batch_size: int = 100):
        self.batch_fn = batch_fn
        self.batch_size = batch_size
        self.queue: list[tuple[Any, asyncio.Future]] = []
        self._lock = asyncio.Lock()

    async def load(self, key: Any) -> Any:
        """Load a single item."""
        future: asyncio.Future = asyncio.Future()

        async with self._lock:
            self.queue.append((key, future))

            if len(self.queue) >= self.batch_size:
                await self._flush()

        # Schedule flush if not already scheduled
        asyncio.create_task(self._flush_delayed())

        return await future

    async def load_many(self, keys: list[Any]) -> list[Any]:
        """Load multiple items."""
        futures = []
        for key in keys:
            future = asyncio.Future()
            async with self._lock:
                self.queue.append((key, future))
            futures.append(future)

        await self._flush()
        return await asyncio.gather(*futures)

    async def _flush(self) -> None:
        """Flush pending items."""
        async with self._lock:
            if not self.queue:
                return

            keys = [item[0] for item in self.queue]
            futures = [item[1] for item in self.queue]
            self.queue.clear()

        try:
            results = await self.batch_fn(keys)
            for future, result in zip(futures, results, strict=False):
                if not future.done():
                    future.set_result(result)
        except Exception as e:
            for future in futures:
                if not future.done():
                    future.set_exception(e)

    async def _flush_delayed(self) -> None:
        """Flush after a delay."""
        await asyncio.sleep(0.01)  # 10ms delay
        await self._flush()


class FieldResolutionOptimizer:
    """Optimize field resolution in GraphQL."""

    def __init__(self):
        self.resolution_times: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def record_resolution_time(self, field_name: str, time_ms: float) -> None:
        """Record field resolution time."""
        async with self._lock:
            if field_name not in self.resolution_times:
                self.resolution_times[field_name] = []

            self.resolution_times[field_name].append(time_ms)

            # Keep only recent measurements
            if len(self.resolution_times[field_name]) > 100:
                self.resolution_times[field_name].pop(0)

    async def get_slow_fields(self, threshold_ms: float = 50) -> list[str]:
        """Get fields that are slow to resolve."""
        async with self._lock:
            slow_fields = []
            for field_name, times in self.resolution_times.items():
                avg_time = sum(times) / len(times)
                if avg_time > threshold_ms:
                    slow_fields.append(field_name)

            return slow_fields

    async def get_field_stats(self, field_name: str) -> dict[str, float]:
        """Get statistics for a field."""
        async with self._lock:
            times = self.resolution_times.get(field_name, [])

        if not times:
            return {}

        times_sorted = sorted(times)
        return {
            "avg_time_ms": sum(times) / len(times),
            "p50_time_ms": times_sorted[len(times_sorted) // 2],
            "p95_time_ms": times_sorted[int(len(times_sorted) * 0.95)],
            "p99_time_ms": times_sorted[int(len(times_sorted) * 0.99)],
            "max_time_ms": max(times),
            "min_time_ms": min(times),
            "call_count": len(times),
        }


class QueryResultCache:
    """Cache GraphQL query results."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    def _make_cache_key(self, query: str, variables: dict[str, Any]) -> str:
        """Generate cache key from query and variables."""
        import hashlib
        import json

        key_str = f"{query}:{json.dumps(variables, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get(self, query: str, variables: dict[str, Any]) -> Any | None:
        """Get cached query result."""
        key = self._make_cache_key(query, variables)

        async with self._lock:
            if key not in self.cache:
                return None

            result, expiry = self.cache[key]
            import time
            if time.time() > expiry:
                del self.cache[key]
                return None

            return result

    async def set(self, query: str, variables: dict[str, Any], result: Any) -> None:
        """Cache query result."""
        key = self._make_cache_key(query, variables)

        async with self._lock:
            import time
            expiry = time.time() + self.ttl_seconds
            self.cache[key] = (result, expiry)

            # Evict oldest entry if cache is full
            if len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]

    async def invalidate(self, query_pattern: str | None = None) -> None:
        """Invalidate cache entries."""
        async with self._lock:
            if query_pattern is None:
                self.cache.clear()
            else:
                keys_to_delete = [k for k in self.cache if query_pattern in k]
                for k in keys_to_delete:
                    del self.cache[k]

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            return {
                "cache_size": len(self.cache),
                "max_size": self.max_size,
                "utilization_percent": (len(self.cache) / self.max_size) * 100,
            }


# Global instances
_complexity_analyzer = QueryComplexityAnalyzer()
_field_optimizer = FieldResolutionOptimizer()
_query_cache = QueryResultCache()


async def get_complexity_analyzer() -> QueryComplexityAnalyzer:
    """Get global complexity analyzer."""
    return _complexity_analyzer


async def get_field_optimizer() -> FieldResolutionOptimizer:
    """Get global field optimizer."""
    return _field_optimizer


async def get_query_cache() -> QueryResultCache:
    """Get global query cache."""
    return _query_cache
