"""
Performance benchmark suite for X-Agent.
Tests critical operations and establishes performance baselines.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional
import statistics


@dataclass
class BenchmarkResult:
    """Benchmark test result."""
    name: str
    iterations: int
    total_time: float
    min_time: float
    max_time: float
    mean_time: float
    median_time: float
    stddev_time: float
    ops_per_sec: float

    def __str__(self) -> str:
        return (
            f"{self.name}:\n"
            f"  Iterations: {self.iterations}\n"
            f"  Total Time: {self.total_time:.3f}s\n"
            f"  Min: {self.min_time*1000:.3f}ms\n"
            f"  Max: {self.max_time*1000:.3f}ms\n"
            f"  Mean: {self.mean_time*1000:.3f}ms\n"
            f"  Median: {self.median_time*1000:.3f}ms\n"
            f"  StdDev: {self.stddev_time*1000:.3f}ms\n"
            f"  Ops/sec: {self.ops_per_sec:.2f}"
        )


class Benchmark:
    """Benchmark runner."""

    @staticmethod
    async def run_async(
        func: Callable,
        iterations: int = 100,
        warmup: int = 10,
        name: Optional[str] = None,
    ) -> BenchmarkResult:
        """Run async benchmark."""
        name = name or func.__name__

        # Warmup
        for _ in range(warmup):
            await func()

        # Measure
        times = []
        start = time.time()

        for _ in range(iterations):
            iter_start = time.time()
            await func()
            iter_time = time.time() - iter_start
            times.append(iter_time)

        total_time = time.time() - start

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            min_time=min(times),
            max_time=max(times),
            mean_time=statistics.mean(times),
            median_time=statistics.median(times),
            stddev_time=statistics.stdev(times) if len(times) > 1 else 0,
            ops_per_sec=iterations / total_time,
        )

    @staticmethod
    def run_sync(
        func: Callable,
        iterations: int = 100,
        warmup: int = 10,
        name: Optional[str] = None,
    ) -> BenchmarkResult:
        """Run sync benchmark."""
        name = name or func.__name__

        # Warmup
        for _ in range(warmup):
            func()

        # Measure
        times = []
        start = time.time()

        for _ in range(iterations):
            iter_start = time.time()
            func()
            iter_time = time.time() - iter_start
            times.append(iter_time)

        total_time = time.time() - start

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            min_time=min(times),
            max_time=max(times),
            mean_time=statistics.mean(times),
            median_time=statistics.median(times),
            stddev_time=statistics.stdev(times) if len(times) > 1 else 0,
            ops_per_sec=iterations / total_time,
        )


class BenchmarkSuite:
    """Collection of benchmarks."""

    def __init__(self):
        self.results: list[BenchmarkResult] = []
        self.baselines: dict[str, float] = {}

    async def add_async_benchmark(
        self,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10,
        name: Optional[str] = None,
    ) -> BenchmarkResult:
        """Add async benchmark."""
        result = await Benchmark.run_async(func, iterations, warmup, name)
        self.results.append(result)
        return result

    def add_sync_benchmark(
        self,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10,
        name: Optional[str] = None,
    ) -> BenchmarkResult:
        """Add sync benchmark."""
        result = Benchmark.run_sync(func, iterations, warmup, name)
        self.results.append(result)
        return result

    def set_baseline(self, name: str, ops_per_sec: float) -> None:
        """Set performance baseline."""
        self.baselines[name] = ops_per_sec

    def check_regression(self, name: str, threshold: float = 0.1) -> tuple[bool, str]:
        """Check for performance regression."""
        result = next((r for r in self.results if r.name == name), None)
        if not result:
            return False, f"No result found for {name}"

        baseline = self.baselines.get(name)
        if baseline is None:
            return True, f"No baseline for {name}"

        regression = (baseline - result.ops_per_sec) / baseline
        if regression > threshold:
            return False, (
                f"Performance regression for {name}: "
                f"{regression*100:.1f}% slower than baseline"
            )

        return True, f"Performance OK for {name}"

    def get_summary(self) -> str:
        """Get benchmark summary."""
        lines = ["Benchmark Results:", "=" * 60]

        for result in self.results:
            lines.append(str(result))
            lines.append("-" * 60)

        return "\n".join(lines)


# ============================================================================
# Benchmark Tests
# ============================================================================

class TaskExecutionBenchmark:
    """Benchmark task execution performance."""

    @staticmethod
    async def simple_task() -> None:
        """Simple task execution."""
        await asyncio.sleep(0.001)

    @staticmethod
    async def complex_task() -> None:
        """Complex task with multiple steps."""
        for _ in range(10):
            await asyncio.sleep(0.0001)


class ToolCallBenchmark:
    """Benchmark tool invocation latency."""

    @staticmethod
    async def tool_call() -> None:
        """Simulate tool call."""
        await asyncio.sleep(0.005)

    @staticmethod
    async def tool_call_with_args() -> None:
        """Tool call with arguments."""
        args = {"key": "value", "number": 42}
        await asyncio.sleep(0.005)


class MemoryRetrievalBenchmark:
    """Benchmark memory retrieval speed."""

    def __init__(self):
        self.memory = {f"key_{i}": f"value_{i}" for i in range(1000)}

    def retrieve_memory(self) -> None:
        """Retrieve memory item."""
        _ = self.memory.get("key_500")

    async def async_retrieve_memory(self) -> None:
        """Async memory retrieval."""
        await asyncio.sleep(0.0001)
        _ = self.memory.get("key_500")


class APIResponseBenchmark:
    """Benchmark API response time."""

    @staticmethod
    async def api_call() -> dict[str, Any]:
        """Simulate API call."""
        await asyncio.sleep(0.01)
        return {"status": "ok", "data": [1, 2, 3]}

    @staticmethod
    async def api_call_with_processing() -> dict[str, Any]:
        """API call with response processing."""
        await asyncio.sleep(0.01)
        data = {"status": "ok", "data": list(range(100))}
        # Simulate processing
        processed = [x * 2 for x in data["data"]]
        return {"status": "ok", "data": processed}


class CacheBenchmark:
    """Benchmark caching performance."""

    def __init__(self):
        self.cache = {}

    def cache_hit(self) -> None:
        """Cache hit."""
        self.cache["key"] = "value"
        _ = self.cache.get("key")

    def cache_miss(self) -> None:
        """Cache miss."""
        _ = self.cache.get("nonexistent")

    async def async_cache_hit(self) -> None:
        """Async cache hit."""
        self.cache["key"] = "value"
        _ = self.cache.get("key")


async def run_all_benchmarks() -> BenchmarkSuite:
    """Run all benchmarks."""
    suite = BenchmarkSuite()

    # Task execution benchmarks
    print("Running task execution benchmarks...")
    await suite.add_async_benchmark(
        TaskExecutionBenchmark.simple_task,
        iterations=1000,
        name="simple_task_execution"
    )
    await suite.add_async_benchmark(
        TaskExecutionBenchmark.complex_task,
        iterations=100,
        name="complex_task_execution"
    )

    # Tool call benchmarks
    print("Running tool call benchmarks...")
    await suite.add_async_benchmark(
        ToolCallBenchmark.tool_call,
        iterations=500,
        name="tool_call_latency"
    )
    await suite.add_async_benchmark(
        ToolCallBenchmark.tool_call_with_args,
        iterations=500,
        name="tool_call_with_args_latency"
    )

    # Memory retrieval benchmarks
    print("Running memory retrieval benchmarks...")
    mem_bench = MemoryRetrievalBenchmark()
    suite.add_sync_benchmark(
        mem_bench.retrieve_memory,
        iterations=10000,
        name="memory_retrieval"
    )
    await suite.add_async_benchmark(
        mem_bench.async_retrieve_memory,
        iterations=1000,
        name="async_memory_retrieval"
    )

    # API response benchmarks
    print("Running API response benchmarks...")
    await suite.add_async_benchmark(
        APIResponseBenchmark.api_call,
        iterations=100,
        name="api_response_time"
    )
    await suite.add_async_benchmark(
        APIResponseBenchmark.api_call_with_processing,
        iterations=100,
        name="api_response_with_processing"
    )

    # Cache benchmarks
    print("Running cache benchmarks...")
    cache_bench = CacheBenchmark()
    suite.add_sync_benchmark(
        cache_bench.cache_hit,
        iterations=10000,
        name="cache_hit"
    )
    suite.add_sync_benchmark(
        cache_bench.cache_miss,
        iterations=10000,
        name="cache_miss"
    )
    await suite.add_async_benchmark(
        cache_bench.async_cache_hit,
        iterations=1000,
        name="async_cache_hit"
    )

    # Set baselines
    suite.set_baseline("simple_task_execution", 1000)
    suite.set_baseline("tool_call_latency", 200)
    suite.set_baseline("memory_retrieval", 100000)
    suite.set_baseline("api_response_time", 100)
    suite.set_baseline("cache_hit", 100000)

    return suite


if __name__ == "__main__":
    suite = asyncio.run(run_all_benchmarks())
    print(suite.get_summary())
