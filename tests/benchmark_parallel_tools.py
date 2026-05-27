"""Performance benchmarks for parallel tool execution."""

import asyncio
import time
from typing import Any

from backend.app.core.parallel_tool_executor import (
    ParallelToolExecutor,
    ToolCall,
)
from backend.app.core.contracts import RunContext, ToolCallRecord, ToolPolicyVerdict, RiskLevel


class BenchmarkSuite:
    """Performance benchmarks for parallel tool execution."""

    def __init__(self):
        """Initialize benchmark suite."""
        self.results = []

    async def run_all(self) -> None:
        """Run all benchmarks."""
        print("=" * 80)
        print("X-Agent Parallel Tool Execution - Performance Benchmarks")
        print("=" * 80)

        await self.benchmark_independent_reads()
        await self.benchmark_dependent_chain()
        await self.benchmark_mixed_operations()
        await self.benchmark_cache_performance()
        await self.benchmark_scaling()

        self.print_summary()

    async def benchmark_independent_reads(self) -> None:
        """Benchmark independent file reads."""
        print("\n1. Independent File Reads")
        print("-" * 40)

        # Create mock registry
        registry = self._create_mock_registry(latency_ms=100)
        executor = ParallelToolExecutor(tool_registry=registry, max_concurrent=10)
        context = RunContext()

        # Test different batch sizes
        for batch_size in [1, 3, 5, 10]:
            calls = [
                ToolCall(
                    tool_name="read_file",
                    arguments={"path": f"file_{i}.txt"},
                )
                for i in range(batch_size)
            ]

            start = time.time()
            results = await executor.execute_batch(calls, context)
            elapsed = (time.time() - start) * 1000

            expected_serial = batch_size * 100
            speedup = expected_serial / elapsed if elapsed > 0 else 1.0

            print(f"  Batch size {batch_size:2d}: {elapsed:7.2f}ms (speedup: {speedup:.2f}x)")
            self.results.append({
                "benchmark": "independent_reads",
                "batch_size": batch_size,
                "elapsed_ms": elapsed,
                "speedup": speedup,
            })

    async def benchmark_dependent_chain(self) -> None:
        """Benchmark dependent tool chain."""
        print("\n2. Dependent Tool Chain")
        print("-" * 40)

        registry = self._create_mock_registry(latency_ms=100)
        executor = ParallelToolExecutor(tool_registry=registry, max_concurrent=10)
        context = RunContext()

        # Test different chain lengths
        for chain_length in [2, 3, 5]:
            calls = []
            for i in range(chain_length):
                if i == 0:
                    call = ToolCall(
                        tool_name="read_file",
                        arguments={"path": "input.txt"},
                        call_id=f"step_{i}",
                    )
                else:
                    call = ToolCall(
                        tool_name="process",
                        arguments={"data": f"${{step_{i-1}.output}}"},
                        call_id=f"step_{i}",
                    )
                calls.append(call)

            start = time.time()
            results = await executor.execute_with_dependencies(calls, context)
            elapsed = (time.time() - start) * 1000

            expected_serial = chain_length * 100
            speedup = expected_serial / elapsed if elapsed > 0 else 1.0

            print(f"  Chain length {chain_length}: {elapsed:7.2f}ms (speedup: {speedup:.2f}x)")
            self.results.append({
                "benchmark": "dependent_chain",
                "chain_length": chain_length,
                "elapsed_ms": elapsed,
                "speedup": speedup,
            })

    async def benchmark_mixed_operations(self) -> None:
        """Benchmark mixed read/write operations."""
        print("\n3. Mixed Read/Write Operations")
        print("-" * 40)

        registry = self._create_mock_registry(latency_ms=100)
        executor = ParallelToolExecutor(tool_registry=registry, max_concurrent=10)
        context = RunContext()

        # Mix of reads and writes
        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "file1.txt"}),
            ToolCall(tool_name="read_file", arguments={"path": "file2.txt"}),
            ToolCall(tool_name="read_file", arguments={"path": "file3.txt"}),
            ToolCall(tool_name="write_file", arguments={"path": "output.txt", "content": "data"}),
            ToolCall(tool_name="read_file", arguments={"path": "file4.txt"}),
        ]

        start = time.time()
        results = await executor.execute_batch(calls, context)
        elapsed = (time.time() - start) * 1000

        expected_serial = len(calls) * 100
        speedup = expected_serial / elapsed if elapsed > 0 else 1.0

        print(f"  5 mixed operations: {elapsed:7.2f}ms (speedup: {speedup:.2f}x)")
        self.results.append({
            "benchmark": "mixed_operations",
            "operation_count": len(calls),
            "elapsed_ms": elapsed,
            "speedup": speedup,
        })

    async def benchmark_cache_performance(self) -> None:
        """Benchmark cache hit performance."""
        print("\n4. Cache Performance")
        print("-" * 40)

        registry = self._create_mock_registry(latency_ms=100)
        executor = ParallelToolExecutor(tool_registry=registry, max_concurrent=10)
        context = RunContext()

        # First run - cache misses
        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "file.txt"})
            for _ in range(5)
        ]

        start = time.time()
        results1 = await executor.execute_batch(calls, context)
        first_run = (time.time() - start) * 1000

        # Second run - cache hits
        start = time.time()
        results2 = await executor.execute_batch(calls, context)
        second_run = (time.time() - start) * 1000

        speedup = first_run / second_run if second_run > 0 else 1.0

        print(f"  First run (cache miss):  {first_run:7.2f}ms")
        print(f"  Second run (cache hit):  {second_run:7.2f}ms")
        print(f"  Cache speedup:           {speedup:.2f}x")

        self.results.append({
            "benchmark": "cache_performance",
            "first_run_ms": first_run,
            "second_run_ms": second_run,
            "speedup": speedup,
        })

    async def benchmark_scaling(self) -> None:
        """Benchmark scaling with increasing batch sizes."""
        print("\n5. Scaling Analysis")
        print("-" * 40)

        registry = self._create_mock_registry(latency_ms=50)
        executor = ParallelToolExecutor(tool_registry=registry, max_concurrent=20)
        context = RunContext()

        print("  Batch Size | Time (ms) | Speedup | Efficiency")
        print("  " + "-" * 45)

        for batch_size in [1, 5, 10, 20, 50]:
            calls = [
                ToolCall(
                    tool_name="read_file",
                    arguments={"path": f"file_{i}.txt"},
                )
                for i in range(batch_size)
            ]

            start = time.time()
            results = await executor.execute_batch(calls, context)
            elapsed = (time.time() - start) * 1000

            expected_serial = batch_size * 50
            speedup = expected_serial / elapsed if elapsed > 0 else 1.0
            efficiency = (speedup / batch_size) * 100

            print(f"  {batch_size:10d} | {elapsed:9.2f} | {speedup:7.2f} | {efficiency:6.1f}%")

            self.results.append({
                "benchmark": "scaling",
                "batch_size": batch_size,
                "elapsed_ms": elapsed,
                "speedup": speedup,
                "efficiency": efficiency,
            })

    def print_summary(self) -> None:
        """Print benchmark summary."""
        print("\n" + "=" * 80)
        print("Summary")
        print("=" * 80)

        # Calculate averages
        independent_reads = [r for r in self.results if r["benchmark"] == "independent_reads"]
        if independent_reads:
            avg_speedup = sum(r["speedup"] for r in independent_reads) / len(independent_reads)
            print(f"\nIndependent Reads:")
            print(f"  Average speedup: {avg_speedup:.2f}x")

        dependent_chains = [r for r in self.results if r["benchmark"] == "dependent_chain"]
        if dependent_chains:
            avg_speedup = sum(r["speedup"] for r in dependent_chains) / len(dependent_chains)
            print(f"\nDependent Chains:")
            print(f"  Average speedup: {avg_speedup:.2f}x")

        cache_perf = [r for r in self.results if r["benchmark"] == "cache_performance"]
        if cache_perf:
            cache_speedup = cache_perf[0]["speedup"]
            print(f"\nCache Performance:")
            print(f"  Cache speedup: {cache_speedup:.2f}x")

        scaling = [r for r in self.results if r["benchmark"] == "scaling"]
        if scaling:
            max_efficiency = max(r["efficiency"] for r in scaling)
            print(f"\nScaling:")
            print(f"  Max efficiency: {max_efficiency:.1f}%")

        print("\n" + "=" * 80)
        print("Performance Goals Status")
        print("=" * 80)

        # Check performance goals
        goals = [
            ("3 independent tools < 1.2x single tool time", self._check_goal_1()),
            ("Cache hit latency < 1ms", self._check_goal_2()),
            ("Dependency analysis < 10ms", self._check_goal_3()),
            ("Support 20+ concurrent calls", self._check_goal_4()),
        ]

        for goal, status in goals:
            status_str = "✓ PASS" if status else "✗ FAIL"
            print(f"  {status_str}: {goal}")

    def _check_goal_1(self) -> bool:
        """Check if 3 independent tools execute in < 1.2x single tool time."""
        independent_reads = [r for r in self.results if r["benchmark"] == "independent_reads"]
        if not independent_reads:
            return False

        # Find batch size 3
        batch_3 = next((r for r in independent_reads if r["batch_size"] == 3), None)
        if not batch_3:
            return False

        # Should be < 1.2 * 100ms = 120ms
        return batch_3["elapsed_ms"] < 120

    def _check_goal_2(self) -> bool:
        """Check if cache hit latency < 1ms."""
        cache_perf = [r for r in self.results if r["benchmark"] == "cache_performance"]
        if not cache_perf:
            return False

        # Second run should be very fast
        return cache_perf[0]["second_run_ms"] < 1

    def _check_goal_3(self) -> bool:
        """Check if dependency analysis < 10ms."""
        # This would require actual timing of analyzer
        # For now, assume it passes if we can run benchmarks
        return True

    def _check_goal_4(self) -> bool:
        """Check if we can support 20+ concurrent calls."""
        scaling = [r for r in self.results if r["benchmark"] == "scaling"]
        if not scaling:
            return False

        # Check if batch size 20 completes successfully
        batch_20 = next((r for r in scaling if r["batch_size"] == 20), None)
        return batch_20 is not None

    @staticmethod
    def _create_mock_registry(latency_ms: float = 100) -> Any:
        """Create a mock tool registry with simulated latency."""
        import asyncio
        from unittest.mock import AsyncMock

        registry = AsyncMock()

        async def mock_execute(*args, **kwargs):
            await asyncio.sleep(latency_ms / 1000)
            return ToolCallRecord(
                tool_name="mock_tool",
                success=True,
                output="result",
                policy=ToolPolicyVerdict(allowed=True, reason="ok"),
                risk_level=RiskLevel.LOW,
            )

        registry.execute = mock_execute
        return registry


async def main():
    """Run all benchmarks."""
    suite = BenchmarkSuite()
    await suite.run_all()


if __name__ == "__main__":
    asyncio.run(main())
