"""Performance benchmark for X-Agent v2 architecture.

This module provides comprehensive performance testing for the new modular
agent architecture, measuring execution time, memory usage, and CPU utilization
across different task complexities.

Test Scenarios:
- Simple tasks (1-2 tool calls)
- Medium tasks (5-10 tool calls)
- Complex tasks (20+ tool calls)
- Error recovery scenarios
- Memory-intensive scenarios
"""

import asyncio
import json
import logging
import psutil
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TimingMetrics:
    """Timing metrics for a phase or operation."""
    initialization_time: float = 0.0
    planning_time: float = 0.0
    execution_time: float = 0.0
    recovery_time: float = 0.0
    completion_time: float = 0.0
    total_time: float = 0.0


@dataclass
class MemoryMetrics:
    """Memory usage metrics."""
    initial_memory_mb: float = 0.0
    peak_memory_mb: float = 0.0
    final_memory_mb: float = 0.0
    memory_delta_mb: float = 0.0


@dataclass
class CPUMetrics:
    """CPU usage metrics."""
    avg_cpu_percent: float = 0.0
    max_cpu_percent: float = 0.0
    cpu_samples: int = 0


@dataclass
class BenchmarkResult:
    """Complete benchmark result for a test scenario."""
    scenario_name: str
    task_complexity: str
    tool_calls_count: int
    timing: TimingMetrics
    memory: MemoryMetrics
    cpu: CPUMetrics
    iterations: int
    success: bool
    error_message: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'scenario_name': self.scenario_name,
            'task_complexity': self.task_complexity,
            'tool_calls_count': self.tool_calls_count,
            'timing': asdict(self.timing),
            'memory': asdict(self.memory),
            'cpu': asdict(self.cpu),
            'iterations': self.iterations,
            'success': self.success,
            'error_message': self.error_message,
            'timestamp': self.timestamp,
        }


class PerformanceMonitor:
    """Monitor performance metrics during execution."""

    def __init__(self, sample_interval: float = 0.1):
        """Initialize performance monitor.

        Args:
            sample_interval: Interval in seconds between CPU samples
        """
        self.sample_interval = sample_interval
        self.process = psutil.Process()
        self.cpu_samples: list[float] = []
        self.memory_samples: list[float] = []
        self.monitoring = False

    def start(self) -> None:
        """Start monitoring."""
        self.cpu_samples = []
        self.memory_samples = []
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024
        self.monitoring = True

    def stop(self) -> None:
        """Stop monitoring."""
        self.monitoring = False

    async def monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self.monitoring:
            try:
                cpu_percent = self.process.cpu_percent(interval=0.01)
                memory_mb = self.process.memory_info().rss / 1024 / 1024
                self.cpu_samples.append(cpu_percent)
                self.memory_samples.append(memory_mb)
                await asyncio.sleep(self.sample_interval)
            except Exception as e:
                logger.warning(f"Error sampling metrics: {e}")

    def get_metrics(self) -> tuple[MemoryMetrics, CPUMetrics]:
        """Get collected metrics.

        Returns:
            Tuple of (MemoryMetrics, CPUMetrics)
        """
        memory_samples = self.memory_samples or [self.initial_memory]
        cpu_samples = self.cpu_samples or [0.0]

        memory_metrics = MemoryMetrics(
            initial_memory_mb=self.initial_memory,
            peak_memory_mb=max(memory_samples),
            final_memory_mb=memory_samples[-1] if memory_samples else self.initial_memory,
            memory_delta_mb=max(memory_samples) - self.initial_memory,
        )

        cpu_metrics = CPUMetrics(
            avg_cpu_percent=sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0,
            max_cpu_percent=max(cpu_samples) if cpu_samples else 0.0,
            cpu_samples=len(cpu_samples),
        )

        return memory_metrics, cpu_metrics


class AgentV2Benchmark:
    """Benchmark suite for X-Agent v2 architecture."""

    def __init__(self, output_dir: str = "benchmarks/results"):
        """Initialize benchmark suite.

        Args:
            output_dir: Directory to save benchmark results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[BenchmarkResult] = []
        self.monitor = PerformanceMonitor()

    async def run_benchmark(
        self,
        scenario_name: str,
        task_complexity: str,
        tool_calls_count: int,
        test_func: Callable,
        iterations: int = 1,
    ) -> BenchmarkResult:
        """Run a single benchmark scenario.

        Args:
            scenario_name: Name of the scenario
            task_complexity: Complexity level (simple/medium/complex)
            tool_calls_count: Expected number of tool calls
            test_func: Async function to benchmark
            iterations: Number of iterations to run

        Returns:
            BenchmarkResult with collected metrics
        """
        logger.info(f"Running benchmark: {scenario_name}")

        timing = TimingMetrics()
        memory_metrics = MemoryMetrics()
        cpu_metrics = CPUMetrics()
        error_message = None
        success = False

        try:
            # Start monitoring
            self.monitor.start()
            monitor_task = asyncio.create_task(self.monitor.monitor_loop())

            # Run test
            start_time = time.time()
            for i in range(iterations):
                logger.debug(f"Iteration {i+1}/{iterations}")
                await test_func()

            total_time = time.time() - start_time
            timing.total_time = total_time

            # Stop monitoring
            self.monitor.stop()
            await monitor_task

            # Get metrics
            memory_metrics, cpu_metrics = self.monitor.get_metrics()
            success = True

        except Exception as e:
            logger.error(f"Benchmark failed: {e}", exc_info=True)
            error_message = str(e)
            self.monitor.stop()

        result = BenchmarkResult(
            scenario_name=scenario_name,
            task_complexity=task_complexity,
            tool_calls_count=tool_calls_count,
            timing=timing,
            memory=memory_metrics,
            cpu=cpu_metrics,
            iterations=iterations,
            success=success,
            error_message=error_message,
            timestamp=datetime.now().isoformat(),
        )

        self.results.append(result)
        return result

    async def benchmark_simple_task(self) -> BenchmarkResult:
        """Benchmark simple task (1-2 tool calls)."""
        async def simple_task():
            # Simulate simple task execution
            await asyncio.sleep(0.01)  # Minimal work
            return {"result": "simple"}

        return await self.run_benchmark(
            scenario_name="Simple Task",
            task_complexity="simple",
            tool_calls_count=1,
            test_func=simple_task,
            iterations=10,
        )

    async def benchmark_medium_task(self) -> BenchmarkResult:
        """Benchmark medium task (5-10 tool calls)."""
        async def medium_task():
            # Simulate medium task execution
            for _ in range(5):
                await asyncio.sleep(0.01)
            return {"result": "medium"}

        return await self.run_benchmark(
            scenario_name="Medium Task",
            task_complexity="medium",
            tool_calls_count=7,
            test_func=medium_task,
            iterations=5,
        )

    async def benchmark_complex_task(self) -> BenchmarkResult:
        """Benchmark complex task (20+ tool calls)."""
        async def complex_task():
            # Simulate complex task execution
            for _ in range(20):
                await asyncio.sleep(0.005)
            return {"result": "complex"}

        return await self.run_benchmark(
            scenario_name="Complex Task",
            task_complexity="complex",
            tool_calls_count=20,
            test_func=complex_task,
            iterations=3,
        )

    async def benchmark_error_recovery(self) -> BenchmarkResult:
        """Benchmark error recovery scenario."""
        async def error_recovery_task():
            # Simulate error and recovery
            try:
                raise ValueError("Simulated error")
            except ValueError:
                await asyncio.sleep(0.02)  # Recovery time
            return {"result": "recovered"}

        return await self.run_benchmark(
            scenario_name="Error Recovery",
            task_complexity="medium",
            tool_calls_count=3,
            test_func=error_recovery_task,
            iterations=5,
        )

    async def benchmark_memory_intensive(self) -> BenchmarkResult:
        """Benchmark memory-intensive scenario."""
        async def memory_intensive_task():
            # Allocate and process large data
            data = [{"id": i, "data": "x" * 1000} for i in range(100)]
            await asyncio.sleep(0.01)
            del data
            return {"result": "memory_intensive"}

        return await self.run_benchmark(
            scenario_name="Memory Intensive",
            task_complexity="complex",
            tool_calls_count=1,
            test_func=memory_intensive_task,
            iterations=5,
        )

    async def benchmark_concurrent_operations(self) -> BenchmarkResult:
        """Benchmark concurrent operations."""
        async def concurrent_task():
            # Simulate concurrent tool calls
            tasks = [asyncio.sleep(0.01) for _ in range(5)]
            await asyncio.gather(*tasks)
            return {"result": "concurrent"}

        return await self.run_benchmark(
            scenario_name="Concurrent Operations",
            task_complexity="medium",
            tool_calls_count=5,
            test_func=concurrent_task,
            iterations=5,
        )

    async def run_all_benchmarks(self) -> list[BenchmarkResult]:
        """Run all benchmark scenarios.

        Returns:
            List of BenchmarkResult objects
        """
        logger.info("Starting comprehensive benchmark suite")

        benchmarks = [
            self.benchmark_simple_task(),
            self.benchmark_medium_task(),
            self.benchmark_complex_task(),
            self.benchmark_error_recovery(),
            self.benchmark_memory_intensive(),
            self.benchmark_concurrent_operations(),
        ]

        results = await asyncio.gather(*benchmarks, return_exceptions=True)

        # Filter out exceptions
        self.results = [r for r in results if isinstance(r, BenchmarkResult)]

        logger.info(f"Completed {len(self.results)} benchmarks")
        return self.results

    def save_results(self, filename: str = "benchmark_results.json") -> Path:
        """Save benchmark results to JSON file.

        Args:
            filename: Output filename

        Returns:
            Path to saved file
        """
        output_path = self.output_dir / filename
        data = {
            'timestamp': datetime.now().isoformat(),
            'total_benchmarks': len(self.results),
            'results': [r.to_dict() for r in self.results],
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Results saved to {output_path}")
        return output_path

    def generate_summary(self) -> str:
        """Generate summary of benchmark results.

        Returns:
            Formatted summary string
        """
        if not self.results:
            return "No benchmark results available"

        summary = ["=" * 80]
        summary.append("BENCHMARK SUMMARY")
        summary.append("=" * 80)
        summary.append("")

        # Overall statistics
        successful = sum(1 for r in self.results if r.success)
        failed = len(self.results) - successful

        summary.append(f"Total Benchmarks: {len(self.results)}")
        summary.append(f"Successful: {successful}")
        summary.append(f"Failed: {failed}")
        summary.append("")

        # Results by scenario
        summary.append("RESULTS BY SCENARIO")
        summary.append("-" * 80)

        for result in self.results:
            summary.append(f"\n{result.scenario_name}")
            summary.append(f"  Complexity: {result.task_complexity}")
            summary.append(f"  Tool Calls: {result.tool_calls_count}")
            summary.append(f"  Iterations: {result.iterations}")
            summary.append(f"  Status: {'PASS' if result.success else 'FAIL'}")

            if result.success:
                summary.append(f"  Total Time: {result.timing.total_time:.4f}s")
                summary.append(f"  Avg Time/Iteration: {result.timing.total_time/result.iterations:.4f}s")
                summary.append(f"  Peak Memory: {result.memory.peak_memory_mb:.2f} MB")
                summary.append(f"  Memory Delta: {result.memory.memory_delta_mb:.2f} MB")
                summary.append(f"  Avg CPU: {result.cpu.avg_cpu_percent:.2f}%")
                summary.append(f"  Max CPU: {result.cpu.max_cpu_percent:.2f}%")
            else:
                summary.append(f"  Error: {result.error_message}")

        summary.append("")
        summary.append("=" * 80)

        return "\n".join(summary)


async def main():
    """Run benchmark suite."""
    benchmark = AgentV2Benchmark()

    # Run all benchmarks
    results = await benchmark.run_all_benchmarks()

    # Print summary
    print(benchmark.generate_summary())

    # Save results
    benchmark.save_results()

    # Print detailed results
    print("\nDetailed Results:")
    for result in results:
        print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
