"""
N+1 Query Optimization for X-Agent.

Implements batch loading and eager loading strategies to eliminate
N+1 query problems in API endpoints.

Performance Target: 25% reduction in API response time
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
K = TypeVar("K")


@dataclass
class BatchLoadConfig:
    """Configuration for batch loading."""

    batch_size: int = 100
    cache_ttl_seconds: int = 300
    enable_caching: bool = True


class DataLoader(Generic[K, T]):
    """
    DataLoader for batch loading related data.

    Inspired by graphql-core's DataLoader, this prevents N+1 queries
    by batching multiple requests into a single database query.
    """

    def __init__(
        self,
        batch_fn: Callable[[list[K]], Any],
        config: BatchLoadConfig | None = None,
    ) -> None:
        self.batch_fn = batch_fn
        self.config = config or BatchLoadConfig()
        self._queue: list[tuple[K, Any]] = []
        self._cache: dict[K, T] = {}
        self._processing = False

    async def load(self, key: K) -> T:
        """Load a single item, batching with other concurrent requests."""
        # Check cache first
        if self.config.enable_caching and key in self._cache:
            return self._cache[key]

        # Add to queue
        future = asyncio.Future()
        self._queue.append((key, future))

        # Process batch if queue is full or this is the first item
        if len(self._queue) >= self.config.batch_size or len(self._queue) == 1:
            await self._process_batch()

        return await future

    async def load_many(self, keys: list[K]) -> list[T]:
        """Load multiple items."""
        return await asyncio.gather(*[self.load(key) for key in keys])

    async def _process_batch(self) -> None:
        """Process queued batch requests."""
        if self._processing or not self._queue:
            return

        self._processing = True
        try:
            # Extract keys and futures
            queue = self._queue[:]
            self._queue = []

            keys = [key for key, _ in queue]
            futures = [future for _, future in queue]

            # Batch load
            try:
                results = await self.batch_fn(keys)
                result_map = dict(zip(keys, results, strict=False))

                # Resolve futures and cache
                for key, future in zip(keys, futures, strict=False):
                    result = result_map.get(key)
                    if self.config.enable_caching:
                        self._cache[key] = result
                    if not future.done():
                        future.set_result(result)
            except Exception as e:
                logger.error(f"Batch loading failed: {e}")
                for future in futures:
                    if not future.done():
                        future.set_exception(e)
        finally:
            self._processing = False

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()


class BatchQueryOptimizer:
    """Optimizes queries by batching related data loads."""

    @staticmethod
    async def batch_load_workflow_runs(
        workflow_ids: list[str],
        repository: Any,
    ) -> dict[str, list[Any]]:
        """Batch load runs for multiple workflows.

        Instead of:
            for workflow_id in workflow_ids:
                runs = repository.get_runs(workflow_id)  # N queries

        Use:
            runs_by_workflow = await batch_load_workflow_runs(workflow_ids, repository)
        """
        # Single query to get all runs
        all_runs = repository.get_runs_for_workflows(workflow_ids)

        # Group by workflow_id
        runs_by_workflow: dict[str, list[Any]] = defaultdict(list)
        for run in all_runs:
            runs_by_workflow[run.workflow_id].append(run)

        return dict(runs_by_workflow)

    @staticmethod
    async def batch_load_workflow_stats(
        workflow_ids: list[str],
        repository: Any,
    ) -> dict[str, dict[str, Any]]:
        """Batch load statistics for multiple workflows.

        Combines:
        - Latest run
        - Run count
        - Status
        """
        stats = {}

        # Single query for all latest runs
        latest_runs = repository.get_latest_runs_for_workflows(workflow_ids)
        latest_by_workflow = {run.workflow_id: run for run in latest_runs}

        # Single query for all run counts
        run_counts = repository.count_runs_for_workflows(workflow_ids)

        for workflow_id in workflow_ids:
            stats[workflow_id] = {
                "latest_run": latest_by_workflow.get(workflow_id),
                "run_count": run_counts.get(workflow_id, 0),
                "status": (
                    latest_by_workflow.get(workflow_id).status
                    if workflow_id in latest_by_workflow
                    else "draft"
                ),
            }

        return stats

    @staticmethod
    async def batch_load_memory_items(
        tenant_ids: list[str],
        memory_system: Any,
        layers: list[int] | None = None,
    ) -> dict[str, list[Any]]:
        """Batch load memory items for multiple tenants."""
        items_by_tenant: dict[str, list[Any]] = defaultdict(list)

        # Single query to get all items
        all_items = memory_system.search_for_tenants(tenant_ids, layers=layers)

        for item in all_items:
            items_by_tenant[item.tenant_id].append(item)

        return dict(items_by_tenant)


class EagerLoadingStrategy:
    """Strategies for eager loading related data."""

    @staticmethod
    def with_runs(workflows: list[Any], repository: Any) -> list[Any]:
        """Eager load runs for workflows."""
        workflow_ids = [w.id for w in workflows]
        runs_by_workflow = asyncio.run(
            BatchQueryOptimizer.batch_load_workflow_runs(workflow_ids, repository)
        )

        for workflow in workflows:
            workflow.runs = runs_by_workflow.get(workflow.id, [])

        return workflows

    @staticmethod
    def with_stats(workflows: list[Any], repository: Any) -> list[Any]:
        """Eager load statistics for workflows."""
        workflow_ids = [w.id for w in workflows]
        stats = asyncio.run(
            BatchQueryOptimizer.batch_load_workflow_stats(workflow_ids, repository)
        )

        for workflow in workflows:
            workflow.stats = stats.get(workflow.id, {})

        return workflows


class N1QueryDetector:
    """Detects potential N+1 query patterns."""

    def __init__(self) -> None:
        self.query_log: list[dict[str, Any]] = []
        self.suspicious_patterns: list[dict[str, Any]] = []

    def log_query(
        self,
        query: str,
        duration_ms: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log a query execution."""
        self.query_log.append(
            {
                "query": query,
                "duration_ms": duration_ms,
                "context": context or {},
            }
        )

    def detect_patterns(self) -> list[dict[str, Any]]:
        """Detect N+1 query patterns."""
        self.suspicious_patterns = []

        # Group queries by type
        query_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for log_entry in self.query_log:
            query_type = self._extract_query_type(log_entry["query"])
            query_groups[query_type].append(log_entry)

        # Find patterns
        for query_type, queries in query_groups.items():
            if len(queries) > 5:  # Threshold for N+1 detection
                total_time = sum(q["duration_ms"] for q in queries)
                self.suspicious_patterns.append(
                    {
                        "query_type": query_type,
                        "count": len(queries),
                        "total_time_ms": total_time,
                        "avg_time_ms": total_time / len(queries),
                        "severity": "high" if len(queries) > 20 else "medium",
                    }
                )

        return self.suspicious_patterns

    @staticmethod
    def _extract_query_type(query: str) -> str:
        """Extract query type from SQL."""
        # Simple extraction - in production, use proper SQL parsing
        if "SELECT" in query.upper():
            # Extract table name
            parts = query.upper().split("FROM")
            if len(parts) > 1:
                table = parts[1].strip().split()[0]
                return f"SELECT_{table}"
        return "UNKNOWN"

    def get_report(self) -> str:
        """Generate N+1 detection report."""
        patterns = self.detect_patterns()
        if not patterns:
            return "No N+1 query patterns detected."

        report = ["N+1 QUERY DETECTION REPORT", "=" * 60]
        for pattern in patterns:
            report.append(f"\nQuery Type: {pattern['query_type']}")
            report.append(f"  Count: {pattern['count']}")
            report.append(f"  Total Time: {pattern['total_time_ms']:.2f}ms")
            report.append(f"  Avg Time: {pattern['avg_time_ms']:.2f}ms")
            report.append(f"  Severity: {pattern['severity']}")

        return "\n".join(report)


import asyncio
