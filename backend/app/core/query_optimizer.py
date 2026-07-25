"""N+1 Query Optimization Module

Provides utilities to detect and fix N+1 query patterns:
1. Batch loading for related entities
2. Query result prefetching
3. Lazy loading with caching
4. Query analysis and reporting
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")


@dataclass
class QueryMetrics:
    """Metrics for a single query."""

    query_id: str
    query_type: str
    execution_time_ms: float
    row_count: int
    timestamp: float = field(default_factory=time.time)
    parent_query_id: str | None = None
    is_duplicate: bool = False


@dataclass
class N1QueryPattern:
    """Detected N+1 query pattern."""

    parent_query: QueryMetrics
    child_queries: list[QueryMetrics]
    total_time_ms: float
    estimated_savings_ms: float
    pattern_type: str  # "list_then_detail", "list_then_count", etc.


class QueryAnalyzer:
    """Analyzes query patterns to detect N+1 issues."""

    def __init__(self):
        self.queries: list[QueryMetrics] = []
        self.query_stack: list[str] = []
        self.patterns: list[N1QueryPattern] = []

    def start_query(self, query_id: str, query_type: str) -> None:
        """Mark start of a query."""
        self.query_stack.append(query_id)

    def end_query(
        self,
        query_id: str,
        query_type: str,
        execution_time_ms: float,
        row_count: int,
    ) -> None:
        """Mark end of a query."""
        parent_id = self.query_stack[-2] if len(self.query_stack) > 1 else None
        metric = QueryMetrics(
            query_id=query_id,
            query_type=query_type,
            execution_time_ms=execution_time_ms,
            row_count=row_count,
            parent_query_id=parent_id,
        )
        self.queries.append(metric)
        if self.query_stack and self.query_stack[-1] == query_id:
            self.query_stack.pop()

    def analyze(self) -> list[N1QueryPattern]:
        """Analyze queries for N+1 patterns."""
        patterns = []

        # Group queries by parent
        by_parent: dict[str | None, list[QueryMetrics]] = defaultdict(list)
        for query in self.queries:
            by_parent[query.parent_query_id].append(query)

        # Find N+1 patterns
        for parent_id, child_queries in by_parent.items():
            if parent_id is None or len(child_queries) < 2:
                continue

            # Find parent query
            parent = next(
                (q for q in self.queries if q.query_id == parent_id), None
            )
            if not parent:
                continue

            # Check if children are similar (same query type)
            child_types = [q.query_type for q in child_queries]
            if len(set(child_types)) == 1:
                # Likely N+1 pattern
                total_child_time = sum(q.execution_time_ms for q in child_queries)
                # Estimate savings if batched (assume 80% reduction)
                estimated_savings = total_child_time * 0.8

                pattern = N1QueryPattern(
                    parent_query=parent,
                    child_queries=child_queries,
                    total_time_ms=parent.execution_time_ms + total_child_time,
                    estimated_savings_ms=estimated_savings,
                    pattern_type="list_then_detail",
                )
                patterns.append(pattern)

        self.patterns = patterns
        return patterns

    def report(self) -> dict[str, Any]:
        """Generate analysis report."""
        patterns = self.analyze()
        total_queries = len(self.queries)
        total_time = sum(q.execution_time_ms for q in self.queries)
        total_savings = sum(p.estimated_savings_ms for p in patterns)

        return {
            "total_queries": total_queries,
            "total_time_ms": total_time,
            "n1_patterns_found": len(patterns),
            "estimated_savings_ms": total_savings,
            "estimated_improvement_percent": (
                (total_savings / total_time * 100) if total_time > 0 else 0
            ),
            "patterns": [
                {
                    "type": p.pattern_type,
                    "parent_query": p.parent_query.query_type,
                    "child_query_count": len(p.child_queries),
                    "total_time_ms": p.total_time_ms,
                    "estimated_savings_ms": p.estimated_savings_ms,
                }
                for p in patterns
            ],
        }


class BatchLoader(Generic[K, T]):
    """Batch loader for preventing N+1 queries."""

    def __init__(
        self,
        batch_fn: Callable[[list[K]], dict[K, T]],
        batch_size: int = 100,
    ):
        self.batch_fn = batch_fn
        self.batch_size = batch_size
        self.queue: list[tuple[K, asyncio.Future[T]]] = []
        self.scheduled = False

    async def load(self, key: K) -> T:
        """Load a single item, batching with others."""
        future: asyncio.Future[T] = asyncio.Future()
        self.queue.append((key, future))

        if not self.scheduled:
            self.scheduled = True
            asyncio.create_task(self._process_batch())

        return await future

    async def _process_batch(self) -> None:
        """Process queued items in batch."""
        await asyncio.sleep(0)  # Yield to allow more items to queue

        while self.queue:
            batch = self.queue[: self.batch_size]
            self.queue = self.queue[self.batch_size :]

            keys = [k for k, _ in batch]
            try:
                results = await self._execute_batch(keys)
                for key, future in batch:
                    if not future.done():
                        future.set_result(results.get(key))
            except Exception as e:
                for _, future in batch:
                    if not future.done():
                        future.set_exception(e)

        self.scheduled = False

    async def _execute_batch(self, keys: list[K]) -> dict[K, T]:
        """Execute batch function."""
        if asyncio.iscoroutinefunction(self.batch_fn):
            return await self.batch_fn(keys)
        else:
            return self.batch_fn(keys)


class PrefetchCache:
    """Prefetch and cache related data to avoid N+1 queries."""

    def __init__(self):
        self.cache: dict[str, Any] = {}
        self.prefetch_rules: dict[str, list[str]] = {}

    def register_prefetch_rule(
        self, entity_type: str, related_types: list[str]
    ) -> None:
        """Register which related entities to prefetch."""
        self.prefetch_rules[entity_type] = related_types

    async def prefetch(
        self,
        entity_type: str,
        entity_ids: list[str],
        loader_fn: Callable[[str, list[str]], Any],
    ) -> dict[str, Any]:
        """Prefetch related entities."""
        related_types = self.prefetch_rules.get(entity_type, [])
        results = {}

        for related_type in related_types:
            cache_key = f"{entity_type}:{related_type}"
            if cache_key not in self.cache:
                self.cache[cache_key] = await loader_fn(related_type, entity_ids)
            results[related_type] = self.cache[cache_key]

        return results

    def clear(self) -> None:
        """Clear prefetch cache."""
        self.cache.clear()


class QueryOptimizer:
    """Main query optimization coordinator."""

    def __init__(self):
        self.analyzer = QueryAnalyzer()
        self.batch_loaders: dict[str, BatchLoader[Any, Any]] = {}
        self.prefetch_cache = PrefetchCache()
        self.enabled = False

    def enable(self) -> None:
        """Enable query optimization tracking."""
        self.enabled = True

    def disable(self) -> None:
        """Disable query optimization tracking."""
        self.enabled = False

    def register_batch_loader(
        self,
        name: str,
        batch_fn: Callable[[list[Any]], dict[Any, Any]],
        batch_size: int = 100,
    ) -> None:
        """Register a batch loader."""
        self.batch_loaders[name] = BatchLoader(batch_fn, batch_size)

    async def load_batch(self, loader_name: str, key: Any) -> Any:
        """Load using registered batch loader."""
        if loader_name not in self.batch_loaders:
            raise ValueError(f"Unknown batch loader: {loader_name}")
        return await self.batch_loaders[loader_name].load(key)

    def get_report(self) -> dict[str, Any]:
        """Get optimization report."""
        return self.analyzer.report()

    def reset(self) -> None:
        """Reset analyzer state."""
        self.analyzer = QueryAnalyzer()
        self.prefetch_cache.clear()


# Global optimizer instance
_query_optimizer: QueryOptimizer | None = None


def get_query_optimizer() -> QueryOptimizer:
    """Get global query optimizer instance."""
    global _query_optimizer
    if _query_optimizer is None:
        _query_optimizer = QueryOptimizer()
    return _query_optimizer


def track_query(query_type: str):
    """Decorator to track query execution."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            optimizer = get_query_optimizer()
            if not optimizer.enabled:
                return await func(*args, **kwargs)

            query_id = f"{query_type}:{id(func)}"
            optimizer.analyzer.start_query(query_id, query_type)

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                row_count = (
                    len(result) if isinstance(result, (list, tuple)) else 1
                )
                optimizer.analyzer.end_query(
                    query_id, query_type, execution_time, row_count
                )
                return result
            except Exception:
                optimizer.analyzer.end_query(query_id, query_type, 0, 0)
                raise

        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            optimizer = get_query_optimizer()
            if not optimizer.enabled:
                return func(*args, **kwargs)

            query_id = f"{query_type}:{id(func)}"
            optimizer.analyzer.start_query(query_id, query_type)

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                row_count = (
                    len(result) if isinstance(result, (list, tuple)) else 1
                )
                optimizer.analyzer.end_query(
                    query_id, query_type, execution_time, row_count
                )
                return result
            except Exception:
                optimizer.analyzer.end_query(query_id, query_type, 0, 0)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
