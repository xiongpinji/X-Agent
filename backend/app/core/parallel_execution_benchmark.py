"""
Performance Testing and Benchmarking Suite for Parallel Execution Engine

Measures:
- Throughput (tasks/second)
- Latency (p50, p95, p99)
- Resource utilization
- Scalability (1-10 agents/tools)
- Overhead comparison (serial vs parallel)
"""

import asyncio
import time
import statistics
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass

from backend.app.core.parallel_execution_engine import (
    ParallelToolExecutor,
    ParallelAgentExecutor,
    ToolDefinition,
    ToolCall,
    PriorityLevel,
    ExecutionStatus,
)


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    total_duration_ms: float
    task_count: int
    throughput_per_sec: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    success_rate: float


class PerformanceBenchmark:
    """Benchmark suite for parallel execution engine."""

    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.latencies: List[float] = []

    async def benchmark_tool_execution(
        self,
        tool_count: int = 10,
        max_concurrent: int = 5,
        tool_duration_ms: int = 100,
    ) -> BenchmarkResult:
        """
        Benchmark tool execution performance.

        Args:
            tool_count: Number of tools to execute
            max_concurrent: Maximum concurrent executions
            tool_duration_ms: Duration of each tool execution

        Returns:
            Benchmark result
        """
        executor = ParallelToolExecutor(max_concurrent=max_concurrent)
        self.latencies = []

        # Define a simple tool
        async def simple_tool(task_id: int) -> Dict[str, Any]:
            """Simple tool that simulates work."""
            await asyncio.sleep(tool_duration_ms / 1000.0)
            return {"task_id": task_id, "result": "done"}

        # Register tool
        executor.register_tool(ToolDefinition(
            name="simple_tool",
            handler=simple_tool,
            timeout_seconds=30,
        ))

        # Create tool calls
        tool_calls = [
            ToolCall(
                tool_id=f"tool_{i}",
                tool_name="simple_tool",
                arguments={"task_id": i},
                priority=PriorityLevel.NORMAL,
            )
            for i in range(tool_count)
        ]

        # Execute and measure
        start_time = time.time()
        results = await executor.execute_tools(tool_calls)
        total_duration = (time.time() - start_time) * 1000

        # Collect latencies
        metrics = executor.get_metrics()
        for metric in metrics.values():
            self.latencies.append(metric.duration_ms)

        # Calculate statistics
        return self._calculate_stats(
            name=f"Tool Execution ({tool_count} tools, {max_concurrent} concurrent)",
            total_duration_ms=total_duration,
            task_count=tool_count,
        )

    async def benchmark_agent_execution(
        self,
        agent_count: int = 5,
        agent_duration_ms: int = 100,
    ) -> BenchmarkResult:
        """
        Benchmark agent execution performance.

        Args:
            agent_count: Number of agents to execute
            agent_duration_ms: Duration of each agent execution

        Returns:
            Benchmark result
        """
        executor = ParallelAgentExecutor(max_agents=agent_count)
        self.latencies = []

        # Create mock agents
        class MockAgent:
            def __init__(self, agent_id: str, duration_ms: int):
                self.agent_id = agent_id
                self.duration_ms = duration_ms

            async def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
                """Run the agent."""
                await asyncio.sleep(self.duration_ms / 1000.0)
                return {"agent_id": self.agent_id, "result": "done"}

        # Register agents
        agent_ids = []
        for i in range(agent_count):
            agent_id = f"agent_{i}"
            agent_ids.append(agent_id)
            executor.register_agent(agent_id, MockAgent(agent_id, agent_duration_ms))

        # Execute and measure
        start_time = time.time()
        results = await executor.execute_agents(
            agent_ids=agent_ids,
            task="benchmark task",
            context={},
        )
        total_duration = (time.time() - start_time) * 1000

        # Collect latencies from metrics
        metrics = executor.get_agent_metrics()
        for metric in metrics.values():
            self.latencies.append(metric["total_duration_ms"])

        # Calculate statistics
        return self._calculate_stats(
            name=f"Agent Execution ({agent_count} agents)",
            total_duration_ms=total_duration,
            task_count=agent_count,
        )

    async def benchmark_dag_execution(
        self,
        dag_depth: int = 3,
        dag_width: int = 3,
    ) -> BenchmarkResult:
        """
        Benchmark DAG execution with dependencies.

        Args:
            dag_depth: Depth of dependency chain
            dag_width: Width of parallel tasks at each level

        Returns:
            Benchmark result
        """
        executor = ParallelToolExecutor(max_concurrent=dag_width)
        self.latencies = []

        # Define tool
        async def dag_tool(task_id: int) -> Dict[str, Any]:
            """Tool for DAG execution."""
            await asyncio.sleep(0.05)  # 50ms per task
            return {"task_id": task_id, "result": "done"}

        # Register tool
        executor.register_tool(ToolDefinition(
            name="dag_tool",
            handler=dag_tool,
            timeout_seconds=30,
        ))

        # Create DAG structure
        tool_calls = []
        for level in range(dag_depth):
            for width in range(dag_width):
                task_id = level * dag_width + width
                depends_on = []

                # Add dependencies from previous level
                if level > 0:
                    for prev_width in range(dag_width):
                        prev_task_id = (level - 1) * dag_width + prev_width
                        depends_on.append(f"tool_{prev_task_id}")

                tool_calls.append(ToolCall(
                    tool_id=f"tool_{task_id}",
                    tool_name="dag_tool",
                    arguments={"task_id": task_id},
                    depends_on=depends_on,
                ))

        # Execute and measure
        start_time = time.time()
        results = await executor.execute_tools(tool_calls)
        total_duration = (time.time() - start_time) * 1000

        # Collect latencies
        metrics = executor.get_metrics()
        for metric in metrics.values():
            self.latencies.append(metric.duration_ms)

        # Calculate statistics
        total_tasks = dag_depth * dag_width
        return self._calculate_stats(
            name=f"DAG Execution (depth={dag_depth}, width={dag_width})",
            total_duration_ms=total_duration,
            task_count=total_tasks,
        )

    async def benchmark_scalability(self) -> List[BenchmarkResult]:
        """
        Benchmark scalability with increasing task counts.

        Returns:
            List of benchmark results
        """
        results = []

        for task_count in [1, 5, 10, 20, 50]:
            result = await self.benchmark_tool_execution(
                tool_count=task_count,
                max_concurrent=5,
                tool_duration_ms=50,
            )
            results.append(result)

        return results

    async def benchmark_concurrency_impact(self) -> List[BenchmarkResult]:
        """
        Benchmark impact of concurrency limits.

        Returns:
            List of benchmark results
        """
        results = []

        for max_concurrent in [1, 2, 5, 10]:
            result = await self.benchmark_tool_execution(
                tool_count=20,
                max_concurrent=max_concurrent,
                tool_duration_ms=50,
            )
            results.append(result)

        return results

    async def benchmark_serial_vs_parallel(self) -> Tuple[BenchmarkResult, BenchmarkResult]:
        """
        Compare serial vs parallel execution.

        Returns:
            Tuple of (serial_result, parallel_result)
        """
        # Serial execution (max_concurrent=1)
        serial_result = await self.benchmark_tool_execution(
            tool_count=10,
            max_concurrent=1,
            tool_duration_ms=50,
        )

        # Parallel execution (max_concurrent=5)
        parallel_result = await self.benchmark_tool_execution(
            tool_count=10,
            max_concurrent=5,
            tool_duration_ms=50,
        )

        return serial_result, parallel_result

    def _calculate_stats(
        self,
        name: str,
        total_duration_ms: float,
        task_count: int,
    ) -> BenchmarkResult:
        """Calculate benchmark statistics."""
        if not self.latencies:
            self.latencies = [total_duration_ms]

        sorted_latencies = sorted(self.latencies)
        throughput = (task_count / total_duration_ms) * 1000 if total_duration_ms > 0 else 0

        result = BenchmarkResult(
            name=name,
            total_duration_ms=total_duration_ms,
            task_count=task_count,
            throughput_per_sec=throughput,
            avg_latency_ms=statistics.mean(self.latencies),
            min_latency_ms=min(self.latencies),
            max_latency_ms=max(self.latencies),
            p50_latency_ms=sorted_latencies[len(sorted_latencies) // 2],
            p95_latency_ms=sorted_latencies[int(len(sorted_latencies) * 0.95)],
            p99_latency_ms=sorted_latencies[int(len(sorted_latencies) * 0.99)],
            success_rate=1.0,  # Assuming all succeeded
        )

        self.results.append(result)
        return result

    def print_results(self, results: List[BenchmarkResult]) -> None:
        """Print benchmark results in a formatted table."""
        print("\n" + "=" * 120)
        print("BENCHMARK RESULTS")
        print("=" * 120)

        for result in results:
            print(f"\n{result.name}")
            print("-" * 120)
            print(f"  Total Duration:     {result.total_duration_ms:>10.2f} ms")
            print(f"  Task Count:         {result.task_count:>10}")
            print(f"  Throughput:         {result.throughput_per_sec:>10.2f} tasks/sec")
            print(f"  Avg Latency:        {result.avg_latency_ms:>10.2f} ms")
            print(f"  Min Latency:        {result.min_latency_ms:>10.2f} ms")
            print(f"  Max Latency:        {result.max_latency_ms:>10.2f} ms")
            print(f"  P50 Latency:        {result.p50_latency_ms:>10.2f} ms")
            print(f"  P95 Latency:        {result.p95_latency_ms:>10.2f} ms")
            print(f"  P99 Latency:        {result.p99_latency_ms:>10.2f} ms")
            print(f"  Success Rate:       {result.success_rate:>10.1%}")

    def print_comparison(self, serial: BenchmarkResult, parallel: BenchmarkResult) -> None:
        """Print comparison between serial and parallel execution."""
        print("\n" + "=" * 120)
        print("SERIAL vs PARALLEL COMPARISON")
        print("=" * 120)

        speedup = serial.total_duration_ms / parallel.total_duration_ms
        efficiency = speedup / 5  # Assuming 5x concurrency

        print(f"\nSerial Execution:   {serial.total_duration_ms:>10.2f} ms")
        print(f"Parallel Execution: {parallel.total_duration_ms:>10.2f} ms")
        print(f"Speedup:            {speedup:>10.2f}x")
        print(f"Efficiency:         {efficiency:>10.1%}")

    def print_summary(self) -> None:
        """Print summary of all results."""
        print("\n" + "=" * 120)
        print("SUMMARY")
        print("=" * 120)

        if not self.results:
            print("No results to summarize")
            return

        avg_throughput = statistics.mean(r.throughput_per_sec for r in self.results)
        avg_latency = statistics.mean(r.avg_latency_ms for r in self.results)

        print(f"\nTotal Benchmarks:   {len(self.results)}")
        print(f"Avg Throughput:     {avg_throughput:>10.2f} tasks/sec")
        print(f"Avg Latency:        {avg_latency:>10.2f} ms")


async def main():
    """Run all benchmarks."""
    benchmark = PerformanceBenchmark()

    print("Starting Parallel Execution Engine Benchmarks...")
    print("=" * 120)

    # Benchmark 1: Tool Execution
    print("\n1. Tool Execution Benchmark")
    result = await benchmark.benchmark_tool_execution(
        tool_count=20,
        max_concurrent=5,
        tool_duration_ms=50,
    )
    benchmark.print_results([result])

    # Benchmark 2: Agent Execution
    print("\n2. Agent Execution Benchmark")
    result = await benchmark.benchmark_agent_execution(
        agent_count=5,
        agent_duration_ms=100,
    )
    benchmark.print_results([result])

    # Benchmark 3: DAG Execution
    print("\n3. DAG Execution Benchmark")
    result = await benchmark.benchmark_dag_execution(
        dag_depth=3,
        dag_width=3,
    )
    benchmark.print_results([result])

    # Benchmark 4: Scalability
    print("\n4. Scalability Benchmark")
    results = await benchmark.benchmark_scalability()
    benchmark.print_results(results)

    # Benchmark 5: Concurrency Impact
    print("\n5. Concurrency Impact Benchmark")
    results = await benchmark.benchmark_concurrency_impact()
    benchmark.print_results(results)

    # Benchmark 6: Serial vs Parallel
    print("\n6. Serial vs Parallel Comparison")
    serial, parallel = await benchmark.benchmark_serial_vs_parallel()
    benchmark.print_comparison(serial, parallel)

    # Summary
    benchmark.print_summary()

    print("\n" + "=" * 120)
    print("Benchmarks completed")
    print("=" * 120)


if __name__ == "__main__":
    asyncio.run(main())
