"""
Result Aggregator - Collects and merges results from multiple agents.

Features:
- Result collection from multiple agents
- Multiple merge strategies (merge, concat, reduce)
- Context merging and conflict resolution
- Result validation
- Deduplication
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
from typing import Any, Callable, Optional
from collections import defaultdict

from pydantic import BaseModel


logger = logging.getLogger(__name__)


class MergeStrategy(StrEnum):
    """Strategies for merging results."""
    MERGE = "merge"  # Deep merge dictionaries
    CONCAT = "concat"  # Concatenate lists
    REDUCE = "reduce"  # Apply reduction function
    FIRST = "first"  # Take first result
    LAST = "last"  # Take last result
    CUSTOM = "custom"  # Use custom function


class ConflictResolution(StrEnum):
    """Strategies for resolving conflicts."""
    KEEP_FIRST = "keep_first"
    KEEP_LAST = "keep_last"
    MERGE_VALUES = "merge_values"
    RAISE_ERROR = "raise_error"
    CUSTOM = "custom"


@dataclass
class AggregationConfig:
    """Configuration for result aggregation."""
    merge_strategy: MergeStrategy = MergeStrategy.MERGE
    conflict_resolution: ConflictResolution = ConflictResolution.KEEP_LAST
    deduplicate: bool = True
    validate_results: bool = True
    merge_contexts: bool = True
    custom_merge_fn: Optional[Callable] = None
    custom_conflict_fn: Optional[Callable] = None
    timeout_seconds: int = 300


@dataclass
class AggregatedResult:
    """Result of aggregating multiple agent results."""
    aggregation_id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    total_results: int = 0
    successful_results: int = 0
    failed_results: int = 0
    merged_output: Any = None
    merged_context: dict[str, Any] = field(default_factory=dict)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    aggregated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "aggregation_id": self.aggregation_id,
            "total_results": self.total_results,
            "successful_results": self.successful_results,
            "failed_results": self.failed_results,
            "merged_output": self.merged_output,
            "merged_context": self.merged_context,
            "conflicts": self.conflicts,
            "errors": self.errors,
            "warnings": self.warnings,
            "aggregated_at": self.aggregated_at.isoformat(),
            "metadata": self.metadata,
        }


class ResultAggregator:
    """
    Aggregates results from multiple agent executions.

    Handles:
    - Collecting results from different agents
    - Merging outputs using various strategies
    - Merging execution contexts
    - Detecting and resolving conflicts
    - Validating aggregated results
    """

    def __init__(self, config: Optional[AggregationConfig] = None):
        """
        Initialize the result aggregator.

        Args:
            config: Aggregation configuration
        """
        self.config = config or AggregationConfig()
        self.results_cache: dict[str, Any] = {}
        self.conflict_log: list[dict[str, Any]] = []

    async def collect_results(
        self,
        results: list[Any],
        config: Optional[AggregationConfig] = None,
    ) -> AggregatedResult:
        """
        Collect and aggregate results from multiple agents.

        Args:
            results: List of results to aggregate
            config: Optional override configuration

        Returns:
            AggregatedResult with merged output and context
        """
        config = config or self.config
        aggregated = AggregatedResult(total_results=len(results))

        if not results:
            logger.warning("No results to aggregate")
            return aggregated

        try:
            # Separate successful and failed results
            successful = [r for r in results if self._is_successful(r)]
            failed = [r for r in results if not self._is_successful(r)]

            aggregated.successful_results = len(successful)
            aggregated.failed_results = len(failed)

            # Validate results if enabled
            if config.validate_results:
                validation_errors = await self._validate_results(successful)
                aggregated.errors.extend(validation_errors)

            # Deduplicate if enabled
            if config.deduplicate:
                successful = await self._deduplicate_results(successful)

            # Merge outputs
            if successful:
                aggregated.merged_output = await self._merge_outputs(
                    successful, config
                )

            # Merge contexts
            if config.merge_contexts:
                aggregated.merged_context = await self._merge_contexts(successful)

            # Detect conflicts
            conflicts = await self._detect_conflicts(successful)
            if conflicts:
                aggregated.conflicts = conflicts
                resolved = await self._resolve_conflicts(conflicts, config)
                aggregated.metadata["conflict_resolution"] = resolved

            # Add failed results info
            if failed:
                aggregated.warnings.append(
                    f"{len(failed)} out of {len(results)} results failed"
                )
                aggregated.metadata["failed_results"] = [
                    self._result_to_dict(r) for r in failed
                ]

        except Exception as e:
            logger.error(f"Error during result aggregation: {e}", exc_info=True)
            aggregated.errors.append(str(e))

        return aggregated

    async def merge_contexts(
        self,
        results: list[Any],
        conflict_resolution: ConflictResolution = ConflictResolution.KEEP_LAST,
    ) -> dict[str, Any]:
        """
        Merge execution contexts from multiple results.

        Args:
            results: List of results with context
            conflict_resolution: How to resolve conflicts

        Returns:
            Merged context dictionary
        """
        merged_context: dict[str, Any] = {}

        for result in results:
            context = self._extract_context(result)
            if not context:
                continue

            for key, value in context.items():
                if key not in merged_context:
                    merged_context[key] = value
                else:
                    # Handle conflict
                    if conflict_resolution == ConflictResolution.KEEP_FIRST:
                        pass  # Keep existing value
                    elif conflict_resolution == ConflictResolution.KEEP_LAST:
                        merged_context[key] = value
                    elif conflict_resolution == ConflictResolution.MERGE_VALUES:
                        merged_context[key] = await self._merge_values(
                            merged_context[key], value
                        )
                    elif conflict_resolution == ConflictResolution.RAISE_ERROR:
                        raise ValueError(
                            f"Context conflict for key '{key}': "
                            f"{merged_context[key]} vs {value}"
                        )

        return merged_context

    async def resolve_conflicts(
        self,
        results: list[Any],
        config: Optional[AggregationConfig] = None,
    ) -> dict[str, Any]:
        """
        Detect and resolve conflicts in results.

        Args:
            results: List of results
            config: Aggregation configuration

        Returns:
            Resolution information
        """
        config = config or self.config
        conflicts = await self._detect_conflicts(results)

        if not conflicts:
            return {"status": "no_conflicts"}

        resolution_info = {
            "status": "conflicts_detected",
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "resolution_strategy": config.conflict_resolution.value,
        }

        if config.custom_conflict_fn:
            try:
                resolution = await self._call_async(
                    config.custom_conflict_fn, conflicts
                )
                resolution_info["custom_resolution"] = resolution
            except Exception as e:
                logger.error(f"Error in custom conflict resolution: {e}")
                resolution_info["error"] = str(e)

        return resolution_info

    async def _merge_outputs(
        self,
        results: list[Any],
        config: AggregationConfig,
    ) -> Any:
        """Merge outputs using configured strategy."""
        if not results:
            return None

        if config.merge_strategy == MergeStrategy.FIRST:
            return self._extract_output(results[0])

        elif config.merge_strategy == MergeStrategy.LAST:
            return self._extract_output(results[-1])

        elif config.merge_strategy == MergeStrategy.CONCAT:
            outputs = [self._extract_output(r) for r in results]
            if all(isinstance(o, list) for o in outputs):
                return [item for sublist in outputs for item in sublist]
            else:
                return outputs

        elif config.merge_strategy == MergeStrategy.MERGE:
            outputs = [self._extract_output(r) for r in results]
            return await self._deep_merge_dicts(outputs)

        elif config.merge_strategy == MergeStrategy.REDUCE:
            outputs = [self._extract_output(r) for r in results]
            return await self._reduce_outputs(outputs)

        elif config.merge_strategy == MergeStrategy.CUSTOM:
            if not config.custom_merge_fn:
                raise ValueError("Custom merge strategy requires custom_merge_fn")
            outputs = [self._extract_output(r) for r in results]
            return await self._call_async(config.custom_merge_fn, outputs)

        else:
            raise ValueError(f"Unknown merge strategy: {config.merge_strategy}")

    async def _merge_contexts(self, results: list[Any]) -> dict[str, Any]:
        """Merge contexts from all results."""
        merged: dict[str, Any] = {}

        for result in results:
            context = self._extract_context(result)
            if context:
                merged = await self._deep_merge_dicts([merged, context])

        return merged

    async def _detect_conflicts(self, results: list[Any]) -> list[dict[str, Any]]:
        """Detect conflicts in results."""
        conflicts: list[dict[str, Any]] = []

        if len(results) < 2:
            return conflicts

        # Compare outputs pairwise
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                output_i = self._extract_output(results[i])
                output_j = self._extract_output(results[j])

                if output_i != output_j:
                    conflicts.append({
                        "type": "output_mismatch",
                        "result_i": i,
                        "result_j": j,
                        "output_i": output_i,
                        "output_j": output_j,
                    })

        return conflicts

    async def _resolve_conflicts(
        self,
        conflicts: list[dict[str, Any]],
        config: AggregationConfig,
    ) -> dict[str, Any]:
        """Resolve detected conflicts."""
        resolution = {
            "strategy": config.conflict_resolution.value,
            "resolved_count": len(conflicts),
        }

        if config.custom_conflict_fn:
            try:
                custom_resolution = await self._call_async(
                    config.custom_conflict_fn, conflicts
                )
                resolution["custom_resolution"] = custom_resolution
            except Exception as e:
                logger.error(f"Error in custom conflict resolution: {e}")
                resolution["error"] = str(e)

        return resolution

    async def _validate_results(self, results: list[Any]) -> list[str]:
        """Validate results."""
        errors: list[str] = []

        for i, result in enumerate(results):
            if result is None:
                errors.append(f"Result {i} is None")
            elif isinstance(result, dict) and "error" in result:
                errors.append(f"Result {i} contains error: {result['error']}")

        return errors

    async def _deduplicate_results(self, results: list[Any]) -> list[Any]:
        """Remove duplicate results."""
        seen: set[str] = set()
        deduplicated: list[Any] = []

        for result in results:
            result_hash = str(hash(str(result)))
            if result_hash not in seen:
                seen.add(result_hash)
                deduplicated.append(result)

        if len(deduplicated) < len(results):
            logger.info(
                f"Deduplicated {len(results) - len(deduplicated)} results"
            )

        return deduplicated

    async def _deep_merge_dicts(self, dicts: list[dict[str, Any]]) -> dict[str, Any]:
        """Deep merge multiple dictionaries."""
        result: dict[str, Any] = {}

        for d in dicts:
            if not isinstance(d, dict):
                continue

            for key, value in d.items():
                if key not in result:
                    result[key] = value
                elif isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = await self._deep_merge_dicts([result[key], value])
                elif isinstance(result[key], list) and isinstance(value, list):
                    result[key].extend(value)
                else:
                    result[key] = value

        return result

    async def _merge_values(self, val1: Any, val2: Any) -> Any:
        """Merge two values intelligently."""
        if isinstance(val1, dict) and isinstance(val2, dict):
            return await self._deep_merge_dicts([val1, val2])
        elif isinstance(val1, list) and isinstance(val2, list):
            return val1 + val2
        elif isinstance(val1, str) and isinstance(val2, str):
            return f"{val1}\n{val2}"
        else:
            return val2  # Keep last value

    async def _reduce_outputs(self, outputs: list[Any]) -> Any:
        """Reduce outputs to a single value."""
        if not outputs:
            return None

        result = outputs[0]
        for output in outputs[1:]:
            if isinstance(result, (int, float)) and isinstance(output, (int, float)):
                result += output
            elif isinstance(result, list) and isinstance(output, list):
                result.extend(output)
            elif isinstance(result, dict) and isinstance(output, dict):
                result = await self._deep_merge_dicts([result, output])

        return result

    def _is_successful(self, result: Any) -> bool:
        """Check if a result is successful."""
        if result is None:
            return False

        if isinstance(result, dict):
            return result.get("status") not in ["failed", "error", "timeout"]

        return True

    def _extract_output(self, result: Any) -> Any:
        """Extract output from a result."""
        if isinstance(result, dict):
            return result.get("output") or result.get("result") or result
        return result

    def _extract_context(self, result: Any) -> dict[str, Any]:
        """Extract context from a result."""
        if isinstance(result, dict):
            return result.get("context", {})
        return {}

    def _result_to_dict(self, result: Any) -> dict[str, Any]:
        """Convert result to dictionary."""
        if isinstance(result, dict):
            return result
        return {"result": result}

    async def _call_async(self, fn: Callable, *args, **kwargs) -> Any:
        """Call function, handling both sync and async."""
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        else:
            return fn(*args, **kwargs)


class ResultAggregatorFactory:
    """Factory for creating result aggregators with common configurations."""

    @staticmethod
    def create_merge_aggregator() -> ResultAggregator:
        """Create aggregator with deep merge strategy."""
        config = AggregationConfig(
            merge_strategy=MergeStrategy.MERGE,
            conflict_resolution=ConflictResolution.MERGE_VALUES,
        )
        return ResultAggregator(config)

    @staticmethod
    def create_concat_aggregator() -> ResultAggregator:
        """Create aggregator with concatenation strategy."""
        config = AggregationConfig(
            merge_strategy=MergeStrategy.CONCAT,
            conflict_resolution=ConflictResolution.KEEP_LAST,
        )
        return ResultAggregator(config)

    @staticmethod
    def create_first_win_aggregator() -> ResultAggregator:
        """Create aggregator that keeps first result."""
        config = AggregationConfig(
            merge_strategy=MergeStrategy.FIRST,
            conflict_resolution=ConflictResolution.KEEP_FIRST,
        )
        return ResultAggregator(config)

    @staticmethod
    def create_last_win_aggregator() -> ResultAggregator:
        """Create aggregator that keeps last result."""
        config = AggregationConfig(
            merge_strategy=MergeStrategy.LAST,
            conflict_resolution=ConflictResolution.KEEP_LAST,
        )
        return ResultAggregator(config)

    @staticmethod
    def create_custom_aggregator(
        merge_fn: Callable,
        conflict_fn: Optional[Callable] = None,
    ) -> ResultAggregator:
        """Create aggregator with custom merge function."""
        config = AggregationConfig(
            merge_strategy=MergeStrategy.CUSTOM,
            custom_merge_fn=merge_fn,
            custom_conflict_fn=conflict_fn,
        )
        return ResultAggregator(config)
