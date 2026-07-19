"""
Performance Benchmark Tests for Concurrency Control

Measures performance improvements from concurrency optimization.
"""

import asyncio
import time
import statistics
from typing import List, Callable, Any
from dataclasses import dataclass


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""
    name: str
    duration: float
    operations: int
    throughput: float  # ops/sec
    latencies: List[float]
    p50: float
    p95: float
    p99: float
    min_latency: float
    max_latency: float


class BenchmarkSuite:
    """Suite of performance benchmarks."""

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    async def benchmark_connection_pool(self):
        """Benchmark connection pool performance."""
        from backend.app.core.pools import ConnectionPool, PoolConfig
        from unittest.mock import MagicMock

        async def factory():
            return MagicMock()

        config = PoolConfig(min_size=5, max_size=20)
        pool = ConnectionPool(factory, config, name="bench_pool")
        await pool.initialize()

        latencies = []
        start_time = time.time()
        operations = 1000

        for _ in range(operations):
            op_start = time.time()
            conn = await pool.acquire()
            await pool.release(conn)
            latencies.append(time.time() - op_start)

        duration = time.time() - start_time
        throughput = operations / duration

        result = BenchmarkResult(
            name="Connection Pool (1000 acquire/release)",
            duration=duration,
            operations=operations,
            throughput=throughput,
            latencies=latencies,
            p50=statistics.median(latencies),
            p95=self._percentile(latencies, 95),
            p99=self._percentile(latencies, 99),
            min_latency=min(latencies),
            max_latency=max(latencies),
        )

        await pool.close()
        self.results.append(result)
        return result

    async def benchmark_concurrency_limiter(self):
        """Benchmark concurrency limiter performance."""
        from backend.app.core.concurrency_limiter import ConcurrencyLimiter

        limiter = ConcurrencyLimiter(max_concurrent=10, name="bench_limiter")

        latencies = []
        start_time = time.time()
        operations = 1000

        async def task():
            op_start = time.time()
            await limiter.acquire()
            try:
                await asyncio.sleep(0.001)  # Simulate work
            finally:
                limiter.release()
            latencies.append(time.time() - op_start)

        await asyncio.gather(*[task() for _ in range(operations)])

        duration = time.time() - start_time
        throughput = operations / duration

        result = BenchmarkResult(
            name="Concurrency Limiter (1000 tasks, max 10 concurrent)",
            duration=duration,
            operations=operations,
            throughput=throughput,
            latencies=latencies,
            p50=statistics.median(latencies),
            p95=self._percentile(latencies, 95),
            p99=self._percentile(latencies, 99),
            min_latency=min(latencies),
            max_latency=max(latencies),
        )

        self.results.append(result)
        return result

    async def benchmark_adaptive_limiter(self):
        """Benchmark adaptive concurrency limiter."""
        from backend.app.core.concurrency_limiter import AdaptiveConcurrencyLimiter

        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=10,
            min_limit=5,
            max_limit=50,
            adjustment_interval=0.5,
            name="bench_adaptive",
        )
        await limiter.initialize()

        latencies = []
        start_time = time.time()
        operations = 1000

        async def task():
            op_start = time.time()
            await limiter.acquire()
            try:
                await asyncio.sleep(0.001)  # Simulate work
            finally:
                limiter.release(success=True)
            latencies.append(time.time() - op_start)

        await asyncio.gather(*[task() for _ in range(operations)])

        duration = time.time() - start_time
        throughput = operations / duration

        result = BenchmarkResult(
            name="Adaptive Limiter (1000 tasks, adaptive limit)",
            duration=duration,
            operations=operations,
            throughput=throughput,
            latencies=latencies,
            p50=statistics.median(latencies),
            p95=self._percentile(latencies, 95),
            p99=self._percentile(latencies, 99),
            min_latency=min(latencies),
            max_latency=max(latencies),
        )

        await limiter.close()
        self.results.append(result)
        return result

    async def benchmark_rate_limiter(self):
        """Benchmark rate limiter performance."""
        from backend.app.core.concurrency_limiter import RateLimiter

        limiter = RateLimiter(rate=1000.0, burst=100, name="bench_rate")

        latencies = []
        start_time = time.time()
        operations = 1000

        for _ in range(operations):
            op_start = time.time()
            await limiter.acquire(1)
            latencies.append(time.time() - op_start)

        duration = time.time() - start_time
        throughput = operations / duration

        result = BenchmarkResult(
            name="Rate Limiter (1000 acquire, rate=1000/sec)",
            duration=duration,
            operations=operations,
            throughput=throughput,
            latencies=latencies,
            p50=statistics.median(latencies),
            p95=self._percentile(latencies, 95),
            p99=self._percentile(latencies, 99),
            min_latency=min(latencies),
            max_latency=max(latencies),
        )

        self.results.append(result)
        return result

    async def benchmark_task_queue(self):
        """Benchmark task queue performance."""
        from backend.app.core.concurrency_limiter import PriorityTaskQueue, TaskPriority

        queue = PriorityTaskQueue(
            max_queue_size=10000,
            worker_count=4,
            name="bench_queue",
        )
        await queue.start()

        latencies = []
        lock = asyncio.Lock()
        operations = 1000

        async def task(task_id):
            async with lock:
                latencies.append(time.time())

        start_time = time.time()

        for i in range(operations):
            await queue.enqueue(
                lambda i=i: task(i),
                priority=TaskPriority.NORMAL,
            )

        # Wait for all tasks to complete
        await asyncio.sleep(2.0)

        duration = time.time() - start_time
        throughput = operations / duration

        # Calculate latencies from timestamps
        if len(latencies) > 1:
            latencies = [latencies[i+1] - latencies[i] for i in range(len(latencies)-1)]
        else:
            latencies = [0]

        result = BenchmarkResult(
            name="Task Queue (1000 tasks, 4 workers)",
            duration=duration,
            operations=operations,
            throughput=throughput,
            latencies=latencies,
            p50=statistics.median(latencies),
            p95=self._percentile(latencies, 95),
            p99=self._percentile(latencies, 99),
            min_latency=min(latencies),
            max_latency=max(latencies),
        )

        await queue.stop()
        self.results.append(result)
        return result

    async def benchmark_concurrent_pool_access(self):
        """Benchmark concurrent pool access."""
        from backend.app.core.pools import ConnectionPool, PoolConfig
        from unittest.mock import MagicMock

        async def factory():
            return MagicMock()

        config = PoolConfig(min_size=5, max_size=20)
        pool = ConnectionPool(factory, config, name="bench_concurrent")
        await pool.initialize()

        latencies = []
        lock = asyncio.Lock()

        async def worker():
            for _ in range(100):
                op_start = time.time()
                conn = await pool.acquire()
                await asyncio.sleep(0.001)  # Simulate work
                await pool.release(conn)
                async with lock:
                    latencies.append(time.time() - op_start)

        start_time = time.time()
        await asyncio.gather(*[worker() for _ in range(10)])
        duration = time.time() - start_time

        operations = 1000
        throughput = operations / duration

        result = BenchmarkResult(
            name="Concurrent Pool Access (10 workers, 100 ops each)",
            duration=duration,
            operations=operations,
            throughput=throughput,
            latencies=latencies,
            p50=statistics.median(latencies),
            p95=self._percentile(latencies, 95),
            p99=self._percentile(latencies, 99),
            min_latency=min(latencies),
            max_latency=max(latencies),
        )

        await pool.close()
        self.results.append(result)
        return result

    async def run_all_benchmarks(self):
        """Run all benchmarks."""
        print("=" * 80)
        print("X-Agent Concurrency Control Performance Benchmarks")
        print("=" * 80)
        print()

        benchmarks = [
            ("Connection Pool", self.benchmark_connection_pool),
            ("Concurrency Limiter", self.benchmark_concurrency_limiter),
            ("Adaptive Limiter", self.benchmark_adaptive_limiter),
            ("Rate Limiter", self.benchmark_rate_limiter),
            ("Task Queue", self.benchmark_task_queue),
            ("Concurrent Pool Access", self.benchmark_concurrent_pool_access),
        ]

        for name, benchmark_func in benchmarks:
            print(f"Running: {name}...")
            try:
                result = await benchmark_func()
                self._print_result(result)
            except Exception as e:
                print(f"  ERROR: {e}")
            print()

        self._print_summary()

    def _print_result(self, result: BenchmarkResult):
        """Print benchmark result."""
        print(f"  Name: {result.name}")
        print(f"  Duration: {result.duration:.3f}s")
        print(f"  Operations: {result.operations}")
        print(f"  Throughput: {result.throughput:.0f} ops/sec")
        print(f"  Latency (ms):")
        print(f"    Min: {result.min_latency*1000:.3f}")
        print(f"    P50: {result.p50*1000:.3f}")
        print(f"    P95: {result.p95*1000:.3f}")
        print(f"    P99: {result.p99*1000:.3f}")
        print(f"    Max: {result.max_latency*1000:.3f}")

    def _print_summary(self):
        """Print summary of all benchmarks."""
        print("=" * 80)
        print("Summary")
        print("=" * 80)
        print()

        total_throughput = sum(r.throughput for r in self.results)
        avg_p99 = statistics.mean(r.p99 for r in self.results)

        print(f"Total Throughput: {total_throughput:.0f} ops/sec")
        print(f"Average P99 Latency: {avg_p99*1000:.3f}ms")
        print()

        print("Benchmark Results:")
        print(f"{'Name':<50} {'Throughput':<15} {'P99 (ms)':<15}")
        print("-" * 80)

        for result in self.results:
            print(
                f"{result.name:<50} "
                f"{result.throughput:>10.0f} ops/s  "
                f"{result.p99*1000:>10.3f}ms"
            )

    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


async def main():
    """Run benchmark suite."""
    suite = BenchmarkSuite()
    await suite.run_all_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())
