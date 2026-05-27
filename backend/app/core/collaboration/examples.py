"""Example scenarios demonstrating multi-agent collaboration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.app.core.collaboration.dispatcher import Task, TaskDispatcher, DispatchStrategy
from backend.app.core.collaboration.registry import AgentCapability, AgentRegistry
from backend.app.core.collaboration.protocol import MessageRouter, Request, Response
from backend.app.core.collaboration.state_sync import StateManager
from backend.app.core.collaboration.aggregator import ResultAggregator, AggregationStrategy
from backend.app.core.collaboration.patterns import (
    PipelinePattern,
    MapReducePattern,
    MasterWorkerPattern,
    PatternContext,
)
from backend.app.core.collaboration.monitor import CollaborationMonitor

logger = logging.getLogger(__name__)


class ExampleAgent:
    """Example agent for demonstration."""

    def __init__(self, agent_id: str, name: str) -> None:
        self.agent_id = agent_id
        self.name = name
        self.capabilities = []

    async def process(self, data: Any) -> Any:
        """Process data."""
        await asyncio.sleep(0.1)
        return {"processed_by": self.name, "data": data}

    async def decompose(self, data: Any) -> list[Any]:
        """Decompose task into subtasks."""
        if isinstance(data, list):
            return data
        return [data]

    async def aggregate(self, results: list[Any]) -> Any:
        """Aggregate results."""
        return {"aggregated": results}

    async def collaborate(self, data: Any, peers: list[str]) -> Any:
        """Collaborate with peers."""
        return {"collaborated_by": self.name, "peers": len(peers)}


async def example_parallel_data_processing() -> None:
    """Example: Parallel data processing with MapReduce pattern.

    Scenario: Process large dataset in parallel across multiple agents.
    """
    logger.info("=== Parallel Data Processing Example ===")

    # Setup
    registry = AgentRegistry()
    aggregator = ResultAggregator(strategy=AggregationStrategy.CONCAT)
    monitor = CollaborationMonitor()

    # Register agents
    agents = {}
    for i in range(3):
        agent_info = await registry.register_agent(
            name=f"DataProcessor-{i}",
            agent_type="processor",
            capabilities=[
                AgentCapability(
                    name="process_data",
                    description="Process data chunk",
                )
            ],
        )
        agents[agent_info.agent_id] = ExampleAgent(agent_info.agent_id, agent_info.name)

    # Start monitoring
    await monitor.start_collaboration()

    # Create tasks
    data_chunks = [
        {"chunk_id": 1, "data": [1, 2, 3]},
        {"chunk_id": 2, "data": [4, 5, 6]},
        {"chunk_id": 3, "data": [7, 8, 9]},
    ]

    # Process in parallel
    tasks = []
    for i, chunk in enumerate(data_chunks):
        agent_id = list(agents.keys())[i % len(agents)]
        agent = agents[agent_id]

        task_metrics = await monitor.start_task(f"task_{i}", agent_id)
        try:
            result = await agent.process(chunk)
            await aggregator.add_partial_result(f"task_{i}", agent_id, result)
            await monitor.end_task(f"task_{i}", status="completed")
        except Exception as e:
            await monitor.end_task(f"task_{i}", status="failed", error=str(e))

    # Aggregate results
    aggregated = await aggregator.aggregate_results("task_0")

    await monitor.end_collaboration()
    metrics = await monitor.get_performance_summary()

    logger.info(f"Processed {len(data_chunks)} chunks")
    logger.info(f"Performance: {metrics}")


async def example_distributed_search() -> None:
    """Example: Distributed search across multiple agents.

    Scenario: Search for information across multiple specialized agents.
    """
    logger.info("=== Distributed Search Example ===")

    # Setup
    registry = AgentRegistry()
    dispatcher = TaskDispatcher(strategy=DispatchStrategy.CAPABILITY_MATCH)
    monitor = CollaborationMonitor()

    # Register specialized agents
    agents = {}
    specializations = ["web_search", "database_search", "file_search"]

    for spec in specializations:
        agent_info = await registry.register_agent(
            name=f"SearchAgent-{spec}",
            agent_type="searcher",
            capabilities=[
                AgentCapability(
                    name=spec,
                    description=f"Search in {spec}",
                )
            ],
        )
        agents[agent_info.agent_id] = ExampleAgent(agent_info.agent_id, agent_info.name)

    await monitor.start_collaboration()

    # Submit search tasks
    search_queries = [
        {"query": "python async", "required_capability": "web_search"},
        {"query": "user data", "required_capability": "database_search"},
        {"query": "config files", "required_capability": "file_search"},
    ]

    for i, query in enumerate(search_queries):
        task = await dispatcher.submit_task(
            name=f"search_{i}",
            action="search",
            parameters=query,
            required_capability=query["required_capability"],
        )

        # Dispatch to appropriate agent
        agent_id = await dispatcher.dispatch_task(task.task_id, agents)
        if agent_id:
            agent = agents[agent_id]
            await monitor.start_task(task.task_id, agent_id)
            try:
                result = await agent.process(query)
                await monitor.end_task(task.task_id, status="completed")
                logger.info(f"Search result: {result}")
            except Exception as e:
                await monitor.end_task(task.task_id, status="failed", error=str(e))

    await monitor.end_collaboration()
    metrics = await monitor.get_performance_summary()
    logger.info(f"Search completed: {metrics}")


async def example_collaborative_qa() -> None:
    """Example: Collaborative question answering.

    Scenario: Multiple agents collaborate to answer complex questions.
    """
    logger.info("=== Collaborative Q&A Example ===")

    # Setup
    registry = AgentRegistry()
    state_manager = StateManager()
    monitor = CollaborationMonitor()

    # Register Q&A agents
    agents = {}
    roles = ["analyzer", "researcher", "synthesizer"]

    for role in roles:
        agent_info = await registry.register_agent(
            name=f"QAAgent-{role}",
            agent_type="qa",
            capabilities=[
                AgentCapability(
                    name=role,
                    description=f"QA {role}",
                )
            ],
        )
        agents[agent_info.agent_id] = ExampleAgent(agent_info.agent_id, agent_info.name)

    await monitor.start_collaboration()

    # Initialize shared state
    question = "What are the benefits of async programming?"
    await state_manager.set_state("question", question)
    await state_manager.set_state("analysis", {})
    await state_manager.set_state("research", {})

    # Execute pipeline: analyze -> research -> synthesize
    pipeline = PipelinePattern(list(agents.keys()))
    context = PatternContext(
        pattern_id="qa_pipeline",
        agents=agents,
        initial_data={"question": question},
    )

    try:
        result = await pipeline.execute(context)
        logger.info(f"Q&A Result: {result}")
    except Exception as e:
        logger.error(f"Q&A Error: {e}")

    await monitor.end_collaboration()
    metrics = await monitor.get_performance_summary()
    logger.info(f"Q&A completed: {metrics}")


async def example_multi_step_workflow() -> None:
    """Example: Multi-step workflow with dependencies.

    Scenario: Execute complex workflow with multiple steps and dependencies.
    """
    logger.info("=== Multi-Step Workflow Example ===")

    # Setup
    registry = AgentRegistry()
    dispatcher = TaskDispatcher(strategy=DispatchStrategy.PRIORITY_QUEUE)
    aggregator = ResultAggregator(strategy=AggregationStrategy.MERGE)
    monitor = CollaborationMonitor()

    # Register workflow agents
    agents = {}
    for i in range(2):
        agent_info = await registry.register_agent(
            name=f"WorkflowAgent-{i}",
            agent_type="executor",
            capabilities=[
                AgentCapability(name="execute", description="Execute workflow step")
            ],
        )
        agents[agent_info.agent_id] = ExampleAgent(agent_info.agent_id, agent_info.name)

    await monitor.start_collaboration()

    # Create workflow tasks with dependencies
    workflow_steps = [
        {"step": 1, "name": "validate", "priority": 3},
        {"step": 2, "name": "process", "priority": 2},
        {"step": 3, "name": "verify", "priority": 1},
    ]

    for step_config in workflow_steps:
        task = await dispatcher.submit_task(
            name=step_config["name"],
            action="execute",
            parameters=step_config,
            priority=step_config["priority"],
        )

        agent_id = await dispatcher.dispatch_task(task.task_id, agents)
        if agent_id:
            agent = agents[agent_id]
            await monitor.start_task(task.task_id, agent_id)
            try:
                result = await agent.process(step_config)
                await aggregator.add_partial_result(task.task_id, agent_id, result)
                await monitor.end_task(task.task_id, status="completed")
            except Exception as e:
                await monitor.end_task(task.task_id, status="failed", error=str(e))

    await monitor.end_collaboration()
    metrics = await monitor.get_performance_summary()
    logger.info(f"Workflow completed: {metrics}")


async def run_all_examples() -> None:
    """Run all example scenarios."""
    logger.info("Starting multi-agent collaboration examples...")

    try:
        await example_parallel_data_processing()
        await example_distributed_search()
        await example_collaborative_qa()
        await example_multi_step_workflow()
    except Exception as e:
        logger.error(f"Example error: {e}", exc_info=True)

    logger.info("All examples completed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_all_examples())
