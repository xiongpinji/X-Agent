"""
Performance Benchmarks for Parallel Agent Execution System

Measures and reports performance metrics for all components.
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""
    name: str
    iterations: int
    total_time: float
    min_time: float
    max_time: float
    avg_time: float
    median_time: float
    std_dev: float
    throughput: float  # operations per second

    def __str__(self) -> str:
        return (
            f"{self.name}:\n"
            f"  Iterations: {self.iterations}\n"
            f"  Total time: {self.total_time:.3f}s\n"
            f"  Min: {self.min_time:.3f}s\n"
            f"  Max: {self.max_time:.3f}s\n"
            f"  Avg: {self.avg_time:.3f}s\n"
            f"  Median: {self.median_time:.3f}s\n"
            f"  Std Dev: {self.std_dev:.3f}s\n"
            f"  Throughput: {self.throughput:.2f} ops/s"
        )


class ParallelAgentBenchmarks:
    """Benchmark suite for parallel agent execution."""

    @staticmethod
    async def benchmark_parallel_executor():
        """Benchmark parallel agent executor."""
        from backend.app.core.parallel_agent_executor import (
            ParallelAgentExecutor,
            AgentTask,
            IsolationMode,
        )

        print("\n=== Parallel Agent Executor Benchmarks ===\n")

        executor = ParallelAgentExecutor(max_workers=3)

        # Benchmark 1: Thread isolation with varying task counts
        print("Benchmark 1: Thread Isolation Performance")
        print("-" * 50)

        for task_count in [1, 3, 5, 10]:
            times = []

            for _ in range(3):
                tasks = [
                    AgentTask(goal=f"Task {i}", timeout_seconds=10)
                    for i in range(task_count)
                ]

                start = time.time()
                result = await executor.spawn_agents(
                    tasks=tasks,
                    isolation=IsolationMode.THREAD,
                    max_parallel=3,
                )
                elapsed = time.time() - start
                times.append(elapsed)

            avg_time = statistics.mean(times)
            print(f"  {task_count} tasks: {avg_time:.3f}s (avg)")

        # Benchmark 2: Process isolation
        print("\nBenchmark 2: Process Isolation Performance")
        print("-" * 50)

        for task_count in [1, 2, 3]:
            times = []

            for _ in range(2):
                tasks = [
                    AgentTask(goal=f"Task {i}", timeout_seconds=10)
                    for i in range(task_count)
                ]

                start = time.time()
                result = await executor.spawn_agents(
                    tasks=tasks,
                    isolation=IsolationMode.PROCESS,
                    max_parallel=2,
                )
                elapsed = time.time() - start
                times.append(elapsed)

            avg_time = statistics.mean(times)
            print(f"  {task_count} tasks: {avg_time:.3f}s (avg)")

        # Benchmark 3: Parallel vs Sequential
        print("\nBenchmark 3: Parallel vs Sequential Speedup")
        print("-" * 50)

        task_count = 5
        tasks = [
            AgentTask(goal=f"Task {i}", timeout_seconds=10)
            for i in range(task_count)
        ]

        # Parallel execution
        start = time.time()
        result = await executor.spawn_agents(
            tasks=tasks,
            isolation=IsolationMode.THREAD,
            max_parallel=5,
        )
        parallel_time = time.time() - start

        # Estimate sequential time (sum of individual task times)
        sequential_time = sum(r.duration_seconds for r in result.results)

        speedup = sequential_time / parallel_time if parallel_time > 0 else 1.0
        print(f"  Sequential time (estimated): {sequential_time:.3f}s")
        print(f"  Parallel time: {parallel_time:.3f}s")
        print(f"  Speedup: {speedup:.2f}x")

        executor.shutdown()

    @staticmethod
    async def benchmark_communication_bus():
        """Benchmark communication bus."""
        from backend.app.core.agent_communication_bus import (
            AgentCommunicationBus,
            MessagePriority,
        )

        print("\n=== Communication Bus Benchmarks ===\n")

        bus = AgentCommunicationBus(enable_persistence=True)

        # Benchmark 1: Message sending throughput
        print("Benchmark 1: Message Sending Throughput")
        print("-" * 50)

        message_counts = [100, 500, 1000]

        for count in message_counts:
            start = time.time()

            for i in range(count):
                await bus.send_message(
                    from_agent="agent_1",
                    to_agent="agent_2",
                    content={"index": i, "data": "x" * 100},
                )

            elapsed = time.time() - start
            throughput = count / elapsed
            print(f"  {count} messages: {throughput:.2f} msg/s")

        # Benchmark 2: Message receiving throughput
        print("\nBenchmark 2: Message Receiving Throughput")
        print("-" * 50)

        # Send messages first
        for i in range(100):
            await bus.send_message(
                from_agent="agent_1",
                to_agent="agent_2",
                content={"index": i},
            )

        start = time.time()
        received = 0

        while True:
            message = await bus.receive_message("agent_2")
            if not message:
                break
            received += 1

        elapsed = time.time() - start
        throughput = received / elapsed if elapsed > 0 else 0
        print(f"  Received {received} messages in {elapsed:.3f}s")
        print(f"  Throughput: {throughput:.2f} msg/s")

        # Benchmark 3: Broadcast performance
        print("\nBenchmark 3: Broadcast Performance")
        print("-" * 50)

        times = []

        for _ in range(10):
            start = time.time()

            for i in range(100):
                await bus.broadcast(
                    from_agent="coordinator",
                    content={"event": i},
                )

            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = statistics.mean(times)
        print(f"  100 broadcasts: {avg_time:.3f}s (avg)")

        # Benchmark 4: Topic operations
        print("\nBenchmark 4: Topic Operations")
        print("-" * 50)

        # Subscribe
        start = time.time()
        for i in range(100):
            await bus.subscribe(agent_id=f"agent_{i}", topic="results")
        subscribe_time = time.time() - start
        print(f"  100 subscriptions: {subscribe_time:.3f}s")

        # Publish
        start = time.time()
        for i in range(100):
            await bus.publish(
                topic="results",
                content={"index": i},
            )
        publish_time = time.time() - start
        print(f"  100 publishes: {publish_time:.3f}s")

        await bus.shutdown()

    @staticmethod
    async def benchmark_result_aggregator():
        """Benchmark result aggregator."""
        from backend.app.core.result_aggregator import (
            ResultAggregator,
            AggregationConfig,
            MergeStrategy,
        )

        print("\n=== Result Aggregator Benchmarks ===\n")

        aggregator = ResultAggregator()

        # Benchmark 1: Merge strategy performance
        print("Benchmark 1: Merge Strategy Performance")
        print("-" * 50)

        for result_count in [10, 50, 100, 500]:
            results = [
                {"output": {"key": f"value_{i}", "data": list(range(10))}}
                for i in range(result_count)
            ]

            config = AggregationConfig(
                merge_strategy=MergeStrategy.MERGE,
            )

            start = time.time()
            aggregated = await aggregator.collect_results(results, config)
            elapsed = time.time() - start

            print(f"  {result_count} results: {elapsed:.3f}s")

        # Benchmark 2: Concatenation strategy
        print("\nBenchmark 2: Concatenation Strategy Performance")
        print("-" * 50)

        for result_count in [10, 50, 100, 500]:
            results = [
                {"output": list(range(100))}
                for i in range(result_count)
            ]

            config = AggregationConfig(
                merge_strategy=MergeStrategy.CONCAT,
            )

            start = time.time()
            aggregated = await aggregator.collect_results(results, config)
            elapsed = time.time() - start

            print(f"  {result_count} results: {elapsed:.3f}s")

        # Benchmark 3: Conflict detection
        print("\nBenchmark 3: Conflict Detection Performance")
        print("-" * 50)

        for result_count in [10, 50, 100]:
            results = [
                {"output": f"value_{i}"}
                for i in range(result_count)
            ]

            start = time.time()
            conflicts = await aggregator._detect_conflicts(results)
            elapsed = time.time() - start

            print(f"  {result_count} results: {elapsed:.3f}s ({len(conflicts)} conflicts)")

    @staticmethod
    async def benchmark_task_dependency_analyzer():
        """Benchmark task dependency analyzer."""
        from backend.app.core.task_dependency_analyzer import (
            TaskDependencyAnalyzer,
            Task,
        )

        print("\n=== Task Dependency Analyzer Benchmarks ===\n")

        analyzer = TaskDependencyAnalyzer()

        # Benchmark 1: DAG construction
        print("Benchmark 1: DAG Construction Performance")
        print("-" * 50)

        for task_count in [10, 50, 100, 500]:
            tasks = [
                Task(
                    task_id=f"task_{i}",
                    name=f"Task {i}",
                    dependencies=[f"task_{i-1}"] if i > 0 else [],
                )
                for i in range(task_count)
            ]

            start = time.time()
            dag = analyzer.build_dependency_graph(tasks)
            elapsed = time.time() - start

            print(f"  {task_count} tasks: {elapsed:.3f}s")

        # Benchmark 2: Topological sort
        print("\nBenchmark 2: Topological Sort Performance")
        print("-" * 50)

        for task_count in [10, 50, 100, 500]:
            tasks = [
                Task(
                    task_id=f"task_{i}",
                    name=f"Task {i}",
                    dependencies=[f"task_{i-1}"] if i > 0 else [],
                )
                for i in range(task_count)
            ]

            dag = analyzer.build_dependency_graph(tasks)

            start = time.time()
            topo_order = analyzer.topological_sort(dag)
            elapsed = time.time() - start

            print(f"  {task_count} tasks: {elapsed:.3f}s")

        # Benchmark 3: Execution plan generation
        print("\nBenchmark 3: Execution Plan Generation Performance")
        print("-" * 50)

        for task_count in [10, 50, 100]:
            tasks = [
                Task(
                    task_id=f"task_{i}",
                    name=f"Task {i}",
                    dependencies=[f"task_{i-1}"] if i > 0 else [],
                )
                for i in range(task_count)
            ]

            start = time.time()
            plan = analyzer.build_execution_plan(tasks)
            elapsed = time.time() - start

            print(f"  {task_count} tasks: {elapsed:.3f}s")
            print(f"    Layers: {len(plan.layers)}")
            print(f"    Parallelism factor: {plan.parallelism_factor:.2f}")

    @staticmethod
    async def benchmark_isolation_manager():
        """Benchmark isolation manager."""
        from backend.app.core.agent_isolation_manager import (
            AgentIsolationManager,
            IsolationType,
        )

        print("\n=== Isolation Manager Benchmarks ===\n")

        manager = AgentIsolationManager(enable_resource_monitoring=True)

        # Benchmark 1: Environment creation
        print("Benchmark 1: Environment Creation Performance")
        print("-" * 50)

        for isolation_type in [IsolationType.THREAD, IsolationType.PROCESS]:
            times = []

            for i in range(5):
                start = time.time()
                env = await manager.create_isolated_environment(
                    agent_id=f"agent_{i}",
                    isolation_type=isolation_type,
                )
                elapsed = time.time() - start
                times.append(elapsed)

                await manager.cleanup_environment(env.env_id)

            avg_time = statistics.mean(times)
            print(f"  {isolation_type}: {avg_time:.3f}s (avg)")

        # Benchmark 2: Resource monitoring
        print("\nBenchmark 2: Resource Monitoring Performance")
        print("-" * 50)

        env = await manager.create_isolated_environment(
            agent_id="monitor_test",
            isolation_type=IsolationType.THREAD,
        )

        times = []

        for _ in range(100):
            start = time.time()
            resources = await manager.monitor_resources(env.env_id)
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = statistics.mean(times)
        print(f"  100 monitoring calls: {avg_time:.3f}s (avg)")
        print(f"  Per call: {avg_time*1000:.2f}ms")

        await manager.cleanup_environment(env.env_id)

    @staticmethod
    async def run_all_benchmarks():
        """Run all benchmarks."""
        print("\n" + "=" * 60)
        print("PARALLEL AGENT EXECUTION SYSTEM - PERFORMANCE BENCHMARKS")
        print("=" * 60)

        try:
            await ParallelAgentBenchmarks.benchmark_parallel_executor()
            await ParallelAgentBenchmarks.benchmark_communication_bus()
            await ParallelAgentBenchmarks.benchmark_result_aggregator()
            await ParallelAgentBenchmarks.benchmark_task_dependency_analyzer()
            await ParallelAgentBenchmarks.benchmark_isolation_manager()

            print("\n" + "=" * 60)
            print("BENCHMARKS COMPLETED")
            print("=" * 60 + "\n")

        except Exception as e:
            print(f"\nError during benchmarking: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(ParallelAgentBenchmarks.run_all_benchmarks())
