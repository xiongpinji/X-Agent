"""Parallel tool execution engine with dependency analysis and result caching."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.app.core.parallel.dependency_analyzer import (
    ToolDependencyAnalyzer,
    DependencyGraph,
    ExecutionPlan,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Represents a single tool invocation."""

    tool_name: str
    arguments: dict[str, Any]
    call_id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex[:8])
    timeout_seconds: float = 30.0
    retry_count: int = 0
    max_retries: int = 3


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
class BatchExecutionStats:
    """Statistics for batch execution."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    cached_calls: int = 0
    total_latency_ms: float = 0.0
    execution_layers: int = 0
    parallelism_factor: float = 1.0


class ToolResultCache:
    """Simple in-memory cache for tool results."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        """Initialize the cache.

        Args:
            max_size: Maximum number of cached results
            ttl_seconds: Time-to-live for cached results in seconds
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl_seconds:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        if len(self._cache) >= self._max_size:
            # Remove oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        self._cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()


class ParallelToolExecutor:
    """Executes multiple tool calls in parallel with dependency awareness."""

    def __init__(
        self,
        tool_registry: Any,
        cache: Optional[ToolResultCache] = None,
        max_concurrent: int = 10,
        default_timeout: float = 30.0,
    ) -> None:
        """Initialize the parallel executor.

        Args:
            tool_registry: The tool registry for executing tools
            cache: Optional result cache for caching tool outputs
            max_concurrent: Maximum concurrent tool executions
            default_timeout: Default timeout for tool execution in seconds
        """
        self._registry = tool_registry
        self._cache = cache or ToolResultCache()
        self._max_concurrent = max_concurrent
        self._default_timeout = default_timeout
        self._analyzer = ToolDependencyAnalyzer()
        self._stats = BatchExecutionStats()

    async def execute_batch(
        self,
        tool_calls: list[ToolCall],
        context: Any = None,
        allow_partial_failure: bool = True,
    ) -> list[ToolResult]:
        """Execute multiple tool calls in parallel.

        Args:
            tool_calls: List of tool calls to execute
            context: Execution context
            allow_partial_failure: If False, stop on first failure

        Returns:
            List of tool results in the same order as input
        """
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

    async def execute_with_dependencies(
        self,
        tool_calls: list[ToolCall],
        context: Any = None,
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
            logger.info(f"Executing layer {layer_idx} with {len(layer.nodes)} tasks")

            # Execute all tasks in this layer in parallel
            layer_results = await self._execute_layer(layer.nodes, context, allow_partial_failure)
            results.update(layer_results)

            # Check for failures
            if not allow_partial_failure:
                for result in layer_results.values():
                    if not result.success:
                        raise RuntimeError(f"Task {result.call_id} failed: {result.error}")

        self._stats.execution_layers = len(plan.layers)
        self._stats.total_latency_ms = (time.perf_counter() - started) * 1000
        self._stats.parallelism_factor = self._calculate_parallelism_factor(
            len(tool_calls), self._stats.total_latency_ms
        )

        return results

    async def _execute_parallel(
        self,
        tool_calls: list[ToolCall],
        context: Any,
        allow_partial_failure: bool,
    ) -> list[ToolResult]:
        """Execute tool calls in parallel without dependency analysis.

        Args:
            tool_calls: List of tool calls to execute
            context: Execution context
            allow_partial_failure: If False, stop on first failure

        Returns:
            List of tool results
        """
        semaphore = asyncio.Semaphore(self._max_concurrent)

        # 批内去重：相同 cache_key 的调用只执行一次，后续调用复用结果并标记 cached=True
        # 这避免了并发 gather 导致的缓存竞态（两个相同调用同时 miss 缓存）
        cache_key_to_index: dict[str, int] = {}
        unique_indices: list[int] = []
        duplicate_map: dict[int, int] = {}  # duplicate_index -> first_index

        for i, call in enumerate(tool_calls):
            key = self._get_cache_key(call)
            if key in cache_key_to_index:
                duplicate_map[i] = cache_key_to_index[key]
            else:
                cache_key_to_index[key] = i
                unique_indices.append(i)

        async def execute_with_semaphore(call: ToolCall) -> ToolResult:
            async with semaphore:
                return await self._execute_single(call, context)

        # 只执行去重后的唯一调用
        unique_calls = [tool_calls[i] for i in unique_indices]
        unique_tasks = [execute_with_semaphore(call) for call in unique_calls]
        unique_results = await asyncio.gather(*unique_tasks, return_exceptions=False)

        # 构建 index -> result 映射
        index_to_result: dict[int, ToolResult] = {}
        for idx, result in zip(unique_indices, unique_results):
            index_to_result[idx] = result

        # 组装最终结果列表，重复调用复用首次结果并标记 cached=True
        results: list[ToolResult] = []
        for i, call in enumerate(tool_calls):
            if i in index_to_result:
                results.append(index_to_result[i])
            else:
                first_idx = duplicate_map[i]
                first_result = index_to_result[first_idx]
                # 复制结果但更新 call_id 并标记为缓存命中
                cached_result = ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    success=first_result.success,
                    output=first_result.output,
                    error=first_result.error,
                    latency_ms=0.0,
                    cached=True,
                    retry_attempt=0,
                )
                results.append(cached_result)

        # Update stats
        for result in results:
            if result.success:
                self._stats.successful_calls += 1
                if result.cached:
                    self._stats.cached_calls += 1
            else:
                self._stats.failed_calls += 1

        return results

    async def _execute_layer(
        self,
        nodes: list[Any],
        context: Any,
        allow_partial_failure: bool,
    ) -> dict[str, ToolResult]:
        """Execute all nodes in a layer in parallel.

        Args:
            nodes: List of DAG nodes to execute
            context: Execution context
            allow_partial_failure: If False, stop on first failure

        Returns:
            Dictionary mapping call_id to ToolResult
        """
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def execute_node(node: Any) -> tuple[str, ToolResult]:
            async with semaphore:
                call = ToolCall(
                    tool_name=node.task_name,
                    arguments=node.arguments,
                    call_id=node.node_id,
                    timeout_seconds=node.timeout_seconds,
                    retry_count=node.retry_count,
                    max_retries=node.max_retries,
                )
                result = await self._execute_single(call, context)
                return node.node_id, result

        tasks = [execute_node(node) for node in nodes]
        results_list = await asyncio.gather(*tasks, return_exceptions=False)

        results = dict(results_list)

        # Update stats
        for result in results.values():
            if result.success:
                self._stats.successful_calls += 1
                if result.cached:
                    self._stats.cached_calls += 1
            else:
                self._stats.failed_calls += 1

        return results

    async def _execute_single(
        self,
        call: ToolCall,
        context: Any,
    ) -> ToolResult:
        """Execute a single tool call with retry logic.

        Args:
            call: Tool call to execute
            context: Execution context

        Returns:
            ToolResult with execution result
        """
        # Check cache
        cache_key = self._get_cache_key(call)
        cached_output = self._cache.get(cache_key)
        if cached_output is not None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=True,
                output=cached_output,
                cached=True,
                latency_ms=0.0,
            )

        # Execute with retries
        last_error = None
        for attempt in range(call.max_retries + 1):
            try:
                started = time.perf_counter()

                # Execute tool
                output = await self._call_tool(call, context)

                latency_ms = (time.perf_counter() - started) * 1000

                # Cache result
                self._cache.set(cache_key, output)

                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    success=True,
                    output=output,
                    latency_ms=latency_ms,
                    retry_attempt=attempt,
                )

            except asyncio.TimeoutError:
                last_error = f"Timeout after {call.timeout_seconds}s"
                logger.warning(f"Tool {call.tool_name} timed out (attempt {attempt + 1})")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Tool {call.tool_name} failed: {e} (attempt {attempt + 1})")

            # Wait before retry
            if attempt < call.max_retries:
                backoff = 2 ** attempt  # Exponential backoff
                await asyncio.sleep(backoff)

        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            success=False,
            error=last_error,
            retry_attempt=call.max_retries,
        )

    async def _call_tool(self, call: ToolCall, context: Any) -> Any:
        """Call a tool with timeout.

        Args:
            call: Tool call to execute
            context: Execution context

        Returns:
            Tool output

        Raises:
            asyncio.TimeoutError: If tool execution times out
            Exception: If tool execution fails
        """
        # Get tool from registry
        tool = self._registry.get_tool(call.tool_name)
        if not tool:
            raise ValueError(f"Tool {call.tool_name} not found in registry")

        # Execute with timeout
        try:
            if asyncio.iscoroutinefunction(tool.execute):
                output = await asyncio.wait_for(
                    tool.execute(call.arguments, context),
                    timeout=call.timeout_seconds,
                )
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                output = await asyncio.wait_for(
                    loop.run_in_executor(None, tool.execute, call.arguments, context),
                    timeout=call.timeout_seconds,
                )
            return output
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Tool {call.tool_name} timed out")

    def _get_cache_key(self, call: ToolCall) -> str:
        """Generate a cache key for a tool call.

        Args:
            call: Tool call

        Returns:
            Cache key
        """
        key_data = f"{call.tool_name}:{json.dumps(call.arguments, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _calculate_parallelism_factor(self, total_tasks: int, total_time_ms: float) -> float:
        """Calculate the parallelism factor.

        Args:
            total_tasks: Total number of tasks
            total_time_ms: Total execution time in milliseconds

        Returns:
            Parallelism factor (1.0 = sequential, N = perfect parallelism)
        """
        if total_time_ms == 0 or total_tasks == 0:
            return 1.0

        # Assume average task time is 1000ms
        avg_task_time_ms = 1000.0
        sequential_time = total_tasks * avg_task_time_ms
        parallelism = sequential_time / total_time_ms

        return min(parallelism, float(total_tasks))

    def get_stats(self) -> BatchExecutionStats:
        """Get execution statistics.

        Returns:
            BatchExecutionStats
        """
        return self._stats
