"""Parallel tool execution engine with dependency analysis and result caching."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from backend.app.core.contracts import RunContext, ToolCallRecord, RiskLevel
from backend.app.core.tool_dependency_analyzer import (
    ToolDependencyAnalyzer,
    DependencyGraph,
    ExecutionPlan,
    ExecutionLayer,
)
from backend.app.core.tool_result_cache import ToolResultCache


@dataclass
class ToolCall:
    """Represents a single tool invocation."""

    tool_name: str
    arguments: dict[str, Any]
    call_id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex[:8])
    timeout_seconds: float = 30.0
    retry_count: int = 0


@dataclass
class ToolResult:
    """Result of a tool execution."""

    call_id: str
    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    cached: bool = False
    retry_attempt: int = 0


@dataclass
class ToolExecutionResult:
    """Lightweight tool result for the migration-adapter execution API.

    Distinct from :class:`ToolResult` (which carries call-id/latency/cache
    bookkeeping for the dependency-aware engine). This shape matches what the
    migration adapter and migration test-suite expect from
    :meth:`ParallelToolExecutor.execute_batch`/``execute_sequential`` when those
    are invoked in *migration mode* (tuple tool-calls + an executor callable).
    """

    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None


@dataclass
class BatchExecutionStats:
    """Statistics for batch execution."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    cached_calls: int = 0
    total_latency_ms: float = 0.0
    execution_layers: int = 0
    parallelism_factor: float = 1.0


class ParallelToolExecutor:
    """Executes multiple tool calls in parallel with dependency awareness."""

    def __init__(
        self,
        tool_registry: Any = None,
        cache: ToolResultCache | None = None,
        max_concurrent: int = 10,
        default_timeout: float = 30.0,
        max_parallel: int | None = None,
        timeout: float | None = None,
    ) -> None:
        """Initialize the parallel executor.

        Args:
            tool_registry: The tool registry for executing tools. Optional in
                *migration mode* (where the executor function is passed directly
                to ``execute_batch``/``execute_sequential``).
            cache: Optional result cache for caching tool outputs
            max_concurrent: Maximum concurrent tool executions
            default_timeout: Default timeout for tool execution in seconds
            max_parallel: Alias for ``max_concurrent`` (migration API). Takes
                precedence when provided.
            timeout: Alias for ``default_timeout`` (migration API). Takes
                precedence when provided.
        """
        if max_parallel is not None:
            max_concurrent = max_parallel
        if timeout is not None:
            default_timeout = timeout

        self._registry = tool_registry
        self._cache = cache or ToolResultCache()
        self._max_concurrent = max_concurrent
        self._default_timeout = default_timeout
        self._analyzer = ToolDependencyAnalyzer()
        self._stats = BatchExecutionStats()

    async def execute_batch(
        self,
        tool_calls: list[ToolCall],
        context: RunContext,
        allow_partial_failure: bool = True,
    ) -> list[ToolResult]:
        """Execute multiple tool calls in parallel.

        Two calling conventions are supported:

        * **Engine mode** (default): ``tool_calls`` are :class:`ToolCall`
          objects and ``allow_partial_failure`` is a bool. Tools are executed
          through ``self._registry`` with dependency-free parallelism.
        * **Migration mode**: ``tool_calls`` are ``(name, arguments)`` tuples
          and the third positional argument is an *executor callable*
          ``async fn(context, name, arguments)``. Returns
          :class:`ToolExecutionResult` objects. Used by the migration adapter.

        Args:
            tool_calls: List of tool calls (ToolCall objects or (name, args) tuples)
            context: Execution context
            allow_partial_failure: bool flag, or — in migration mode — the
                executor callable passed positionally.

        Returns:
            List of tool results in the same order as input.
        """
        # Migration mode is unambiguous: the discriminator slot holds a callable
        # (a bool is never callable, and engine callers never pass a function).
        if callable(allow_partial_failure):
            return await self._execute_batch_migration(
                tool_calls, context, allow_partial_failure
            )

        if not tool_calls:
            return []

        started = time.perf_counter()
        self._stats = BatchExecutionStats(total_calls=len(tool_calls))

        # All calls are independent, execute in parallel
        results = await self._execute_parallel(tool_calls, context, allow_partial_failure)

        self._stats.total_latency_ms = (time.perf_counter() - started) * 1000
        self._stats.parallelism_factor = self._calculate_parallelism_factor(
            len(tool_calls), self._stats.total_latency_ms
        )

        return results

    # ------------------------------------------------------------------ #
    # Migration-mode execution API (tuple calls + explicit executor fn)
    # ------------------------------------------------------------------ #
    async def _execute_one_migration(
        self,
        executor_fn: Any,
        context: RunContext,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Run a single (name, args) call through ``executor_fn`` safely."""
        try:
            if asyncio.iscoroutinefunction(executor_fn):
                output = await executor_fn(context, name, arguments)
            else:
                output = executor_fn(context, name, arguments)
            return ToolExecutionResult(tool_name=name, success=True, output=output)
        except Exception as exc:  # pragma: no cover - defensive
            return ToolExecutionResult(tool_name=name, success=False, error=str(exc))

    async def _execute_batch_migration(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
        context: RunContext,
        executor_fn: Any,
    ) -> list[ToolExecutionResult]:
        """Execute ``(name, args)`` tuples in parallel via ``executor_fn``.

        Concurrency is bounded by ``self._max_concurrent``. Results preserve
        input order.
        """
        if not tool_calls:
            return []

        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def run(call: tuple[str, dict[str, Any]]) -> ToolExecutionResult:
            name, arguments = call
            async with semaphore:
                return await self._execute_one_migration(
                    executor_fn, context, name, arguments
                )

        return list(await asyncio.gather(*(run(c) for c in tool_calls)))

    async def execute_sequential(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
        context: RunContext,
        executor_fn: Any,
    ) -> list[ToolExecutionResult]:
        """Execute ``(name, args)`` tuples one at a time via ``executor_fn``.

        Migration-mode counterpart to :meth:`execute_batch`. Preserves order
        and never runs calls concurrently.
        """
        results: list[ToolExecutionResult] = []
        for name, arguments in tool_calls:
            results.append(
                await self._execute_one_migration(
                    executor_fn, context, name, arguments
                )
            )
        return results

    @staticmethod
    def get_execution_summary(
        results: list[ToolExecutionResult],
    ) -> dict[str, Any]:
        """Summarise a list of migration-mode results.

        Args:
            results: Results from :meth:`execute_batch`/:meth:`execute_sequential`.

        Returns:
            Dict with ``total_tools``, ``successful``, ``failed`` and
            ``success_rate`` (0.0 when there are no results).
        """
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        return {
            "total_tools": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total) if total else 0.0,
        }

    async def execute_with_dependencies(
        self,
        tool_calls: list[ToolCall],
        context: RunContext,
        allow_partial_failure: bool = True,
    ) -> dict[str, ToolResult]:
        """Execute tool calls considering dependencies between them.

        Args:
            tool_calls: List of tool calls to execute
            context: Execution context
            allow_partial_failure: If False, stop on first failure

        Returns:
            Dictionary mapping call_id to ToolResult
        """
        if not tool_calls:
            return {}

        started = time.perf_counter()
        self._stats = BatchExecutionStats(total_calls=len(tool_calls))

        # Analyze dependencies
        graph = self._analyzer.analyze_dependencies(tool_calls)
        plan = self._analyzer.build_execution_plan(graph)

        # Check for cycles
        cycles = self._analyzer.detect_cycles(graph)
        if cycles:
            raise ValueError(f"Circular dependencies detected: {cycles}")

        # Execute layer by layer
        results: dict[str, ToolResult] = {}
        for layer_idx, layer in enumerate(plan.layers):
            layer_results = await self._execute_layer(
                layer, tool_calls, context, results, allow_partial_failure
            )
            results.update(layer_results)
            self._stats.execution_layers = layer_idx + 1

            if not allow_partial_failure and any(not r.success for r in layer_results.values()):
                break

        self._stats.total_latency_ms = (time.perf_counter() - started) * 1000
        self._stats.parallelism_factor = self._analyzer.calculate_parallelism(plan)

        return results

    async def _execute_parallel(
        self,
        tool_calls: list[ToolCall],
        context: RunContext,
        allow_partial_failure: bool,
    ) -> list[ToolResult]:
        """Execute tool calls in parallel without dependency analysis."""
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def execute_with_semaphore(call: ToolCall) -> ToolResult:
            async with semaphore:
                return await self._execute_single(call, context)

        tasks = [execute_with_semaphore(call) for call in tool_calls]

        if allow_partial_failure:
            results = await asyncio.gather(*tasks, return_exceptions=False)
        else:
            results = await asyncio.gather(*tasks)

        # Update stats
        for result in results:
            if result.success:
                self._stats.successful_calls += 1
            else:
                self._stats.failed_calls += 1
            if result.cached:
                self._stats.cached_calls += 1

        return results

    async def _execute_layer(
        self,
        layer: ExecutionLayer,
        all_calls: list[ToolCall],
        context: RunContext,
        previous_results: dict[str, ToolResult],
        allow_partial_failure: bool,
    ) -> dict[str, ToolResult]:
        """Execute a single layer of the execution plan."""
        # Get calls for this layer
        layer_calls = [call for call in all_calls if call.call_id in layer.call_ids]

        # Resolve dependencies for each call
        resolved_calls = []
        for call in layer_calls:
            resolved_call = self._resolve_call_dependencies(call, previous_results)
            resolved_calls.append(resolved_call)

        # Execute in parallel
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def execute_with_semaphore(call: ToolCall) -> tuple[str, ToolResult]:
            async with semaphore:
                result = await self._execute_single(call, context)
                return (call.call_id, result)

        tasks = [execute_with_semaphore(call) for call in resolved_calls]

        if allow_partial_failure:
            task_results = await asyncio.gather(*tasks, return_exceptions=False)
        else:
            task_results = await asyncio.gather(*tasks)

        # Convert to dict and update stats
        results = {}
        for call_id, result in task_results:
            results[call_id] = result
            if result.success:
                self._stats.successful_calls += 1
            else:
                self._stats.failed_calls += 1
            if result.cached:
                self._stats.cached_calls += 1

        return results

    async def _execute_single(self, call: ToolCall, context: RunContext) -> ToolResult:
        """Execute a single tool call with caching and retry logic."""
        started = time.perf_counter()

        # Try cache first
        cached_result = await self._cache.get(call.tool_name, call.arguments)
        if cached_result is not None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=True,
                output=cached_result,
                latency_ms=(time.perf_counter() - started) * 1000,
                cached=True,
            )

        # Execute with retry logic
        last_error = None
        for attempt in range(call.retry_count + 1):
            try:
                # Execute tool
                record = await self._registry.execute(context, call.tool_name, call.arguments)

                latency_ms = (time.perf_counter() - started) * 1000

                if record.success:
                    # Cache successful result
                    await self._cache.set(
                        call.tool_name, call.arguments, record.output, ttl=300
                    )

                    return ToolResult(
                        call_id=call.call_id,
                        tool_name=call.tool_name,
                        success=True,
                        output=record.output,
                        latency_ms=latency_ms,
                        retry_attempt=attempt,
                    )
                else:
                    last_error = record.error
                    if attempt < call.retry_count:
                        # Exponential backoff
                        await asyncio.sleep(0.1 * (2 ** attempt))
                        continue

                    return ToolResult(
                        call_id=call.call_id,
                        tool_name=call.tool_name,
                        success=False,
                        error=record.error,
                        latency_ms=latency_ms,
                        retry_attempt=attempt,
                    )

            except asyncio.TimeoutError:
                last_error = f"Tool execution timeout after {call.timeout_seconds}s"
                if attempt < call.retry_count:
                    await asyncio.sleep(0.1 * (2 ** attempt))
                    continue

                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    success=False,
                    error=last_error,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    retry_attempt=attempt,
                )

            except Exception as exc:
                last_error = str(exc)
                if attempt < call.retry_count:
                    await asyncio.sleep(0.1 * (2 ** attempt))
                    continue

                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    success=False,
                    error=last_error,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    retry_attempt=attempt,
                )

        # Should not reach here
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            success=False,
            error=last_error or "Unknown error",
            latency_ms=(time.perf_counter() - started) * 1000,
            retry_attempt=call.retry_count,
        )

    def _resolve_call_dependencies(
        self, call: ToolCall, previous_results: dict[str, ToolResult]
    ) -> ToolCall:
        """Resolve variable references in call arguments using previous results."""
        resolved_args = {}

        for key, value in call.arguments.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # Parse reference like ${call_id.output}
                ref = value[2:-1]  # Remove ${ and }
                if "." in ref:
                    call_id, attr = ref.split(".", 1)
                    if call_id in previous_results:
                        result = previous_results[call_id]
                        if attr == "output" and result.success:
                            resolved_args[key] = result.output
                        elif attr == "error":
                            resolved_args[key] = result.error
                        else:
                            resolved_args[key] = value
                    else:
                        resolved_args[key] = value
                else:
                    resolved_args[key] = value
            else:
                resolved_args[key] = value

        return ToolCall(
            tool_name=call.tool_name,
            arguments=resolved_args,
            call_id=call.call_id,
            timeout_seconds=call.timeout_seconds,
            retry_count=call.retry_count,
        )

    def _calculate_parallelism_factor(self, call_count: int, total_latency_ms: float) -> float:
        """Calculate parallelism factor (speedup ratio)."""
        if call_count <= 1 or total_latency_ms == 0:
            return 1.0

        # Estimate: if perfectly parallel, total time would be ~max_single_time
        # Actual speedup = (call_count * avg_time) / total_time
        # We approximate avg_time as total_latency / call_count
        avg_time = total_latency_ms / call_count
        estimated_serial_time = avg_time * call_count
        speedup = estimated_serial_time / total_latency_ms if total_latency_ms > 0 else 1.0

        return min(speedup, float(call_count))

    def get_stats(self) -> BatchExecutionStats:
        """Get execution statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._stats = BatchExecutionStats()
