"""Result aggregation for combining partial results from multiple agents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AggregationStrategy(str, Enum):
    """Strategy for aggregating results."""

    MERGE = "merge"
    CONCAT = "concat"
    FIRST = "first"
    LAST = "last"
    MAJORITY_VOTE = "majority_vote"
    CUSTOM = "custom"


@dataclass
class PartialResult:
    """Partial result from an agent."""

    result_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    task_id: str = ""
    data: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "success"  # success, error, timeout
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedResult:
    """Final aggregated result from multiple agents."""

    result_id: str = field(default_factory=lambda: str(uuid4()))
    task_id: str = ""
    final_result: Any = None
    partial_results: list[PartialResult] = field(default_factory=list)
    strategy: AggregationStrategy = AggregationStrategy.MERGE
    aggregation_time: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class ResultAggregator:
    """Aggregates results from multiple agents."""

    def __init__(
        self,
        strategy: AggregationStrategy = AggregationStrategy.MERGE,
        custom_aggregator: Optional[Callable] = None,
    ) -> None:
        self._strategy = strategy
        self._custom_aggregator = custom_aggregator
        self._partial_results: dict[str, list[PartialResult]] = {}
        self._aggregated_results: dict[str, AggregatedResult] = {}
        self._lock = asyncio.Lock()

    async def add_partial_result(
        self,
        task_id: str,
        agent_id: str,
        data: Any,
        status: str = "success",
        error: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> PartialResult:
        """Add a partial result from an agent.

        Args:
            task_id: ID of the task
            agent_id: ID of the agent
            data: Result data
            status: Result status
            error: Error message if any
            metadata: Additional metadata

        Returns:
            PartialResult object
        """
        result = PartialResult(
            agent_id=agent_id,
            task_id=task_id,
            data=data,
            status=status,
            error=error,
            metadata=metadata or {},
        )

        async with self._lock:
            if task_id not in self._partial_results:
                self._partial_results[task_id] = []
            self._partial_results[task_id].append(result)

        logger.info(f"Added partial result from agent {agent_id} for task {task_id}")
        return result

    async def aggregate_results(
        self,
        task_id: str,
        timeout: float = 30.0,
    ) -> Optional[AggregatedResult]:
        """Aggregate partial results for a task.

        Args:
            task_id: ID of the task
            timeout: Timeout for waiting for results

        Returns:
            AggregatedResult or None if no results
        """
        start_time = datetime.now(UTC)

        async with self._lock:
            if task_id not in self._partial_results:
                return None

            partial_results = self._partial_results[task_id]

        if not partial_results:
            return None

        if self._strategy == AggregationStrategy.MERGE:
            final_result = await self._aggregate_merge(partial_results)
        elif self._strategy == AggregationStrategy.CONCAT:
            final_result = await self._aggregate_concat(partial_results)
        elif self._strategy == AggregationStrategy.FIRST:
            final_result = await self._aggregate_first(partial_results)
        elif self._strategy == AggregationStrategy.LAST:
            final_result = await self._aggregate_last(partial_results)
        elif self._strategy == AggregationStrategy.MAJORITY_VOTE:
            final_result = await self._aggregate_majority_vote(partial_results)
        elif self._strategy == AggregationStrategy.CUSTOM:
            if self._custom_aggregator:
                final_result = await self._custom_aggregator(partial_results)
            else:
                final_result = await self._aggregate_merge(partial_results)
        else:
            final_result = await self._aggregate_merge(partial_results)

        aggregation_time = (datetime.now(UTC) - start_time).total_seconds()
        success_count = len([r for r in partial_results if r.status == "success"])
        failure_count = len([r for r in partial_results if r.status != "success"])

        aggregated = AggregatedResult(
            task_id=task_id,
            final_result=final_result,
            partial_results=partial_results,
            strategy=self._strategy,
            aggregation_time=aggregation_time,
            success_count=success_count,
            failure_count=failure_count,
        )

        async with self._lock:
            self._aggregated_results[task_id] = aggregated

        logger.info(
            f"Aggregated {len(partial_results)} results for task {task_id} "
            f"({success_count} success, {failure_count} failed)"
        )
        return aggregated

    async def _aggregate_merge(self, partial_results: list[PartialResult]) -> Any:
        """Merge results into a single dictionary."""
        merged = {}
        for result in partial_results:
            if isinstance(result.data, dict):
                merged.update(result.data)
            else:
                merged[result.agent_id] = result.data
        return merged

    async def _aggregate_concat(self, partial_results: list[PartialResult]) -> Any:
        """Concatenate results into a list."""
        concatenated = []
        for result in partial_results:
            if isinstance(result.data, list):
                concatenated.extend(result.data)
            else:
                concatenated.append(result.data)
        return concatenated

    async def _aggregate_first(self, partial_results: list[PartialResult]) -> Any:
        """Return first successful result."""
        for result in partial_results:
            if result.status == "success":
                return result.data
        return None

    async def _aggregate_last(self, partial_results: list[PartialResult]) -> Any:
        """Return last successful result."""
        successful = [r for r in partial_results if r.status == "success"]
        return successful[-1].data if successful else None

    async def _aggregate_majority_vote(self, partial_results: list[PartialResult]) -> Any:
        """Return result with majority vote."""
        from collections import Counter

        successful = [r for r in partial_results if r.status == "success"]
        if not successful:
            return None

        data_list = [r.data for r in successful]
        counter = Counter(str(d) for d in data_list)
        most_common = counter.most_common(1)

        if most_common:
            return most_common[0][0]
        return None

    async def get_aggregated_result(self, task_id: str) -> Optional[AggregatedResult]:
        """Get aggregated result for a task.

        Args:
            task_id: ID of the task

        Returns:
            AggregatedResult or None if not found
        """
        return self._aggregated_results.get(task_id)

    async def get_partial_results(self, task_id: str) -> list[PartialResult]:
        """Get partial results for a task.

        Args:
            task_id: ID of the task

        Returns:
            List of PartialResult objects
        """
        return self._partial_results.get(task_id, [])

    async def clear_results(self, task_id: str) -> None:
        """Clear results for a task.

        Args:
            task_id: ID of the task
        """
        async with self._lock:
            self._partial_results.pop(task_id, None)
            self._aggregated_results.pop(task_id, None)

    async def get_aggregator_stats(self) -> dict[str, Any]:
        """Get aggregator statistics."""
        return {
            "strategy": self._strategy.value,
            "tasks_with_results": len(self._partial_results),
            "aggregated_results": len(self._aggregated_results),
            "total_partial_results": sum(
                len(results) for results in self._partial_results.values()
            ),
        }

    async def wait_for_results(
        self,
        task_id: str,
        expected_count: int,
        timeout: float = 30.0,
    ) -> bool:
        """Wait for expected number of results.

        Args:
            task_id: ID of the task
            expected_count: Expected number of results
            timeout: Timeout in seconds

        Returns:
            True if expected count reached, False if timeout
        """
        start_time = datetime.now(UTC)

        while True:
            async with self._lock:
                if task_id in self._partial_results:
                    if len(self._partial_results[task_id]) >= expected_count:
                        return True

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            if elapsed > timeout:
                return False

            await asyncio.sleep(0.1)
