"""Performance benchmarks for multi-agent collaboration system."""

from __future__ import annotations

import asyncio
import time
import logging
from typing import Any

from backend.app.core.collaboration.registry import AgentCapability, AgentRegistry
from backend.app.core.collaboration.dispatcher import TaskDispatcher, DispatchStrategy
from backend.app.core.collaboration.protocol import MessageRouter, Request
from backend.app.core.collaboration.state_sync import StateManager
from backend.app.core.collaboration.aggregator import ResultAggregator, AggregationStrategy
from backend.app.core.collaboration.monitor import CollaborationMonitor

logger = logging.getLogger(__name__)


class BenchmarkAgent:
    """Simple agent for benchmarking."""

    def __init__(self, agent_id: str, processing_time: float = 0.01) -> None:
        self.agent_id = agent_id
        self.processing_time = processing_time
        self.tasks_processed = 0

    async def process(self, data: Any) -> Any:
        """Simulate processing."""
        await asyncio.sleep(self.processing_time)
        self.tasks_processed += 1
        return {"processed": True, "data": data}


async def benchmark_message_routing(num_messages: int = 1000) -> dict[str, Any]:
    """Benchmark message routing performance."""
    logger.info(f"Benchmarking message routing with {num_messages} messages...")

    router = MessageRouter()
    received_count = 0

    async def handler(msg: Request) -> None:
        nonlocal received_count
        received_count += 1

    await router.register_handler("agent1", handler)

    start_time = time.time()

    for i in range(num_messages):
        msg = Request(
            sender_id="agent0",
            receiver_id="agent1",
            action="test",
            parameters={"index": i},
        )
        await router.send_message(msg, wait_response=False)

    elapsed = time.time() - start_time

    return {
        "benchmark": "message_routing",
        "num_messages": num_messages,
        "elapsed_time": elapsed,
        "messages_per_second": num_messages / elapsed,
        "avg_latency_ms": (elapsed / num_messages) * 1000,
    }


async def benchmark_agent_registry(num_agents: int = 100) -> dict[str, Any]:
    """Benchmark agent registry performance."""
    logger.info(f"Benchmarking agent registry with {num_agents} agents...")

    registry = AgentRegistry()

    start_time = time.time()

    for i in range(num_agents):
        await registry.register_agent(
            name=f"agent_{i}",
            agent_type="processor",
            capabilities=[
                AgentCapability(
                    name=f"capability_{i % 10}",
                    description=f"Capability {i % 10}",
                )
            ],
        )

    registration_time = time.time() - start_time

    start_time = time.time()

    for i in range(num_agents):
        await registry.find_agents_for_capability(f"capability_{i % 10}")

    lookup_time = time.time() - start_time

    return {
        "benchmark": "agent_registry",
        "num_agents": num_agents,
        "registration_time": registration_time,
        "registrations_per_second": num_agents / registration_time,
        "lookup_time": lookup_time,
        "lookups_per_second": num_agents / lookup_time,
    }


async def benchmark_task_dispatch(num_tasks: int = 1000) -> dict[str, Any]:
    """Benchmark task dispatch performance."""
    logger.info(f"Benchmarking task dispatch with {num_tasks} tasks...")

    dispatcher = TaskDispatcher(strategy=DispatchStrategy.LEAST_LOADED)
    agents = {f"agent_{i}": {"load": 0, "capabilities": []} for i in range(10)}

    start_time = time.time()

    for i in range(num_tasks):
        await dispatcher.submit_task(
            name=f"task_{i}",
            action="process",
            parameters={"index": i},
        )

    submission_time = time.time() - start_time

    start_time = time.time()

    for i in range(num_tasks):
        task = await dispatcher.get_next_task()
        if task:
            await dispatcher.dispatch_task(task.task_id, agents)

    dispatch_time = time.time() - start_time

    return {
        "benchmark": "task_dispatch",
        "num_tasks": num_tasks,
        "submission_time": submission_time,
        "submissions_per_second": num_tasks / submission_time,
        "dispatch_time": dispatch_time,
        "dispatches_per_second": num_tasks / dispatch_time,
    }


async def benchmark_state_sync(num_updates: int = 1000) -> dict[str, Any]:
    """Benchmark state synchronization performance."""
    logger.info(f"Benchmarking state sync with {num_updates} updates...")

    manager = StateManager()

    start_time = time.time()

    for i in range(num_updates):
        await manager.set_state(f"key_{i}", f"value_{i}")

    set_time = time.time() - start_time

    start_time = time.time()

    for i in range(num_updates):
        await manager.get_state(f"key_{i}")

    get_time = time.time() - start_time

    start_time = time.time()

    remote_state = {f"key_{i}": f"remote_value_{i}" for i in range(num_updates)}
    await manager.sync_state("agent1", remote_state)

    sync_time = time.time() - start_time

    return {
        "benchmark": "state_sync",
        "num_updates": num_updates,
        "set_time": set_time,
        "sets_per_second": num_updates / set_time,
        "get_time": get_time,
        "gets_per_second": num_updates / get_time,
        "sync_time": sync_time,
        "syncs_per_second": num_updates / sync_time,
    }


async def benchmark_result_aggregation(num_results: int = 1000) -> dict[str, Any]:
    """Benchmark result aggregation performance."""
    logger.info(f"Benchmarking result aggregation with {num_results} results...")

    aggregator = ResultAggregator(strategy=AggregationStrategy.MERGE)

    start_time = time.time()

    for i in range(num_results):
        await aggregator.add_partial_result(
            task_id="task1",
            agent_id=f"agent_{i % 10}",
            data={"key": f"value_{i}"},
        )

    add_time = time.time() - start_time

    start_time = time.time()

    result = await aggregator.aggregate_results("task1")

    aggregate_time = time.time() - start_time

    return {
        "benchmark": "result_aggregation",
        "num_results": num_results,
        "add_time": add_time,
        "adds_per_second": num_results / add_time,
        "aggregate_time": aggregate_time,
        "result_size": len(result.final_result) if result else 0,
    }


async def benchmark_end_to_end(num_tasks: int = 100) -> dict[str, Any]:
    """Benchmark end-to-end collaboration performance."""
    logger.info(f"Benchmarking end-to-end collaboration with {num_tasks} tasks...")

    registry = AgentRegistry()
    dispatcher = TaskDispatcher(strategy=DispatchStrategy.LEAST_LOADED)
    aggregator = ResultAggregator(strategy=AggregationStrategy.MERGE)
    monitor = CollaborationMonitor()

    # Register agents
    agents = {}
    for i in range(5):
        agent_info = await registry.register_agent(
            name=f"agent_{i}",
            agent_type="processor",
            capabilities=[
                AgentCapability(name="process", description="Process data")
            ],
        )
        agents[agent_info.agent_id] = BenchmarkAgent(agent_info.agent_id, 0.01)

    await monitor.start_collaboration()

    start_time = time.time()

    # Submit and process tasks
    for i in range(num_tasks):
        task = await dispatcher.submit_task(
            name=f"task_{i}",
            action="process",
            parameters={"data": f"input_{i}"},
        )

        agent_id = await dispatcher.dispatch_task(task.task_id, agents)
        if agent_id:
            agent = agents[agent_id]
            await monitor.start_task(task.task_id, agent_id)

            try:
                result = await agent.process(task.parameters)
                await aggregator.add_partial_result(task.task_id, agent_id, result)
                await monitor.end_task(task.task_id, status="completed")
            except Exception as e:
                await monitor.end_task(task.task_id, status="failed", error=str(e))

    elapsed = time.time() - start_time

    await monitor.end_collaboration()
    metrics = await monitor.get_performance_summary()

    return {
        "benchmark": "end_to_end",
        "num_tasks": num_tasks,
        "elapsed_time": elapsed,
        "tasks_per_second": num_tasks / elapsed,
        "avg_task_time": elapsed / num_tasks,
        "success_rate": metrics.get("success_rate", 0),
    }


async def run_all_benchmarks() -> None:
    """Run all benchmarks."""
    logger.info("Starting performance benchmarks...")

    results = []

    try:
        result = await benchmark_message_routing(1000)
        results.append(result)
        logger.info(f"Message Routing: {result['messages_per_second']:.0f} msg/s")

        result = await benchmark_agent_registry(100)
        results.append(result)
        logger.info(f"Agent Registry: {result['registrations_per_second']:.0f} reg/s")

        result = await benchmark_task_dispatch(1000)
        results.append(result)
        logger.info(f"Task Dispatch: {result['dispatches_per_second']:.0f} dispatch/s")

        result = await benchmark_state_sync(1000)
        results.append(result)
        logger.info(f"State Sync: {result['sets_per_second']:.0f} set/s")

        result = await benchmark_result_aggregation(1000)
        results.append(result)
        logger.info(f"Result Aggregation: {result['adds_per_second']:.0f} add/s")

        result = await benchmark_end_to_end(100)
        results.append(result)
        logger.info(f"End-to-End: {result['tasks_per_second']:.2f} tasks/s")

    except Exception as e:
        logger.error(f"Benchmark error: {e}", exc_info=True)

    logger.info("Benchmarks completed!")

    # Print summary
    logger.info("\n=== Performance Summary ===")
    for result in results:
        logger.info(f"\n{result['benchmark'].upper()}:")
        for key, value in result.items():
            if key != "benchmark":
                if isinstance(value, float):
                    logger.info(f"  {key}: {value:.2f}")
                else:
                    logger.info(f"  {key}: {value}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_all_benchmarks())
