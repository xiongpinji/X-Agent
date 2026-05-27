"""
Parallel Agent Execution - Integration Guide and Examples

This module demonstrates how to use the parallel agent execution system.
"""

# Example 1: Basic Parallel Execution

async def example_basic_parallel_execution():
    """Example: Execute multiple tasks in parallel."""
    from backend.app.core.parallel_agent_executor import (
        ParallelAgentExecutor,
        AgentTask,
        IsolationMode,
    )

    # Create executor
    executor = ParallelAgentExecutor(max_workers=3)

    # Define tasks
    tasks = [
        AgentTask(
            goal="Analyze code quality",
            description="Run static analysis on codebase",
            timeout_seconds=60,
        ),
        AgentTask(
            goal="Run unit tests",
            description="Execute test suite",
            timeout_seconds=120,
        ),
        AgentTask(
            goal="Generate documentation",
            description="Create API documentation",
            timeout_seconds=90,
        ),
    ]

    # Execute in parallel
    result = await executor.spawn_agents(
        tasks=tasks,
        isolation=IsolationMode.THREAD,
        max_parallel=3,
    )

    print(f"Batch {result.batch_id} completed:")
    print(f"  Total tasks: {result.total_tasks}")
    print(f"  Completed: {result.completed_tasks}")
    print(f"  Failed: {result.failed_tasks}")
    print(f"  Duration: {result.total_duration_seconds:.2f}s")

    return result


# Example 2: Inter-Agent Communication

async def example_inter_agent_communication():
    """Example: Agents communicating via message bus."""
    from backend.app.core.agent_communication_bus import (
        AgentCommunicationBus,
        MessagePriority,
    )

    # Create communication bus
    bus = AgentCommunicationBus(enable_persistence=True)

    # Agent 1 sends message to Agent 2
    message_id = await bus.send_message(
        from_agent="agent_1",
        to_agent="agent_2",
        content={"task": "process_data", "data": [1, 2, 3]},
        priority=MessagePriority.HIGH,
    )

    print(f"Message sent: {message_id}")

    # Agent 2 receives message
    message = await bus.receive_message("agent_2")
    print(f"Agent 2 received: {message.content}")

    # Agent 2 sends response
    response_id = await bus.send_message(
        from_agent="agent_2",
        to_agent="agent_1",
        content={"result": "processed", "sum": 6},
        reply_to=message_id,
    )

    print(f"Response sent: {response_id}")

    # Broadcast to all agents
    broadcast_id = await bus.broadcast(
        from_agent="coordinator",
        content={"event": "task_completed"},
    )

    print(f"Broadcast sent: {broadcast_id}")

    # Get statistics
    stats = await bus.get_stats()
    print(f"Bus stats: {stats}")


# Example 3: Topic-Based Pub/Sub

async def example_topic_pubsub():
    """Example: Topic-based publish/subscribe."""
    from backend.app.core.agent_communication_bus import AgentCommunicationBus

    bus = AgentCommunicationBus()

    # Subscribe agents to topics
    await bus.subscribe(agent_id="agent_1", topic="results")
    await bus.subscribe(agent_id="agent_2", topic="results")
    await bus.subscribe(agent_id="agent_3", topic="errors")

    # Publish to topic
    await bus.publish(
        topic="results",
        content={"status": "success", "data": "result_data"},
        from_agent="worker",
    )

    # Agents receive from topic
    message = await bus.receive_topic_message("results")
    print(f"Received from results topic: {message.content}")

    # Get subscribers
    subscribers = await bus.get_subscribers("results")
    print(f"Subscribers to 'results': {subscribers}")


# Example 4: Result Aggregation

async def example_result_aggregation():
    """Example: Aggregating results from multiple agents."""
    from backend.app.core.result_aggregator import (
        ResultAggregator,
        AggregationConfig,
        MergeStrategy,
        ConflictResolution,
    )

    aggregator = ResultAggregator()

    # Results from multiple agents
    results = [
        {"output": {"user_count": 100, "active": 80}},
        {"output": {"user_count": 100, "active": 75}},
        {"output": {"user_count": 100, "active": 78}},
    ]

    # Aggregate with merge strategy
    config = AggregationConfig(
        merge_strategy=MergeStrategy.MERGE,
        conflict_resolution=ConflictResolution.MERGE_VALUES,
    )

    aggregated = await aggregator.collect_results(results, config)

    print(f"Aggregation ID: {aggregated.aggregation_id}")
    print(f"Total results: {aggregated.total_results}")
    print(f"Successful: {aggregated.successful_results}")
    print(f"Merged output: {aggregated.merged_output}")


# Example 5: Task Dependency Analysis

async def example_task_dependency_analysis():
    """Example: Analyzing task dependencies."""
    from backend.app.core.task_dependency_analyzer import (
        TaskDependencyAnalyzer,
        Task,
    )

    analyzer = TaskDependencyAnalyzer()

    # Define tasks with dependencies
    tasks = [
        Task(task_id="1", name="Setup", dependencies=[]),
        Task(task_id="2", name="Build", dependencies=["1"]),
        Task(task_id="3", name="Test", dependencies=["2"]),
        Task(task_id="4", name="Deploy", dependencies=["3"]),
        Task(task_id="5", name="Verify", dependencies=["4"]),
    ]

    # Build dependency graph
    dag = analyzer.build_dependency_graph(tasks)
    print(f"DAG built with {dag.size()} tasks")

    # Check for cycles
    cycles = analyzer.detect_cycles(dag)
    print(f"Cycles detected: {len(cycles)}")

    # Get topological order
    topo_order = analyzer.topological_sort(dag)
    print(f"Topological order: {topo_order}")

    # Build execution plan
    plan = analyzer.build_execution_plan(tasks)
    print(f"Execution plan:")
    for i, layer in enumerate(plan.layers):
        print(f"  Layer {i}: {layer}")

    # Analyze parallelism
    analysis = analyzer.analyze_parallelism(dag)
    print(f"Parallelism analysis:")
    print(f"  Speedup potential: {analysis['speedup_potential']:.2f}x")
    print(f"  Parallelism factor: {analysis['parallelism_factor']:.2f}")


# Example 6: Isolation Management

async def example_isolation_management():
    """Example: Managing isolated execution environments."""
    from backend.app.core.agent_isolation_manager import (
        AgentIsolationManager,
        IsolationType,
        ResourceLimits,
    )

    manager = AgentIsolationManager(enable_resource_monitoring=True)

    # Create isolated environment
    limits = ResourceLimits(
        max_cpu_percent=80.0,
        max_memory_mb=512,
        timeout_seconds=300,
    )

    env = await manager.create_isolated_environment(
        agent_id="agent_1",
        isolation_type=IsolationType.THREAD,
        resource_limits=limits,
    )

    print(f"Created environment: {env.env_id}")
    print(f"  Agent: {env.agent_id}")
    print(f"  Type: {env.isolation_type}")
    print(f"  Active: {env.is_active}")

    # Monitor resources
    resources = await manager.monitor_resources(env.env_id)
    print(f"Resources: {resources}")

    # Cleanup
    await manager.cleanup_environment(env.env_id)
    print("Environment cleaned up")


# Example 7: Complete Workflow

async def example_complete_workflow():
    """Example: Complete parallel execution workflow."""
    from backend.app.core.parallel_agent_executor import (
        ParallelAgentExecutor,
        AgentTask,
        IsolationMode,
    )
    from backend.app.core.agent_communication_bus import AgentCommunicationBus
    from backend.app.core.result_aggregator import (
        ResultAggregator,
        AggregationConfig,
        MergeStrategy,
    )
    from backend.app.core.task_dependency_analyzer import (
        TaskDependencyAnalyzer,
        Task,
    )

    print("=== Complete Parallel Execution Workflow ===\n")

    # Step 1: Analyze dependencies
    print("Step 1: Analyzing task dependencies...")
    analyzer = TaskDependencyAnalyzer()
    tasks_to_analyze = [
        Task(task_id="fetch_data", name="Fetch Data", dependencies=[]),
        Task(task_id="process_data", name="Process Data", dependencies=["fetch_data"]),
        Task(task_id="analyze_data", name="Analyze Data", dependencies=["process_data"]),
        Task(task_id="generate_report", name="Generate Report", dependencies=["analyze_data"]),
    ]

    dag = analyzer.build_dependency_graph(tasks_to_analyze)
    plan = analyzer.build_execution_plan(tasks_to_analyze)
    print(f"  Execution plan: {len(plan.layers)} layers")
    print(f"  Parallelism factor: {plan.parallelism_factor:.2f}\n")

    # Step 2: Create executor and communication bus
    print("Step 2: Setting up execution environment...")
    executor = ParallelAgentExecutor(max_workers=3)
    bus = AgentCommunicationBus(enable_persistence=True)
    aggregator = ResultAggregator()
    print("  Executor, bus, and aggregator ready\n")

    # Step 3: Create execution tasks
    print("Step 3: Creating execution tasks...")
    exec_tasks = [
        AgentTask(
            goal="Fetch data from sources",
            description="Retrieve data from multiple sources",
            timeout_seconds=60,
        ),
        AgentTask(
            goal="Process and clean data",
            description="Apply transformations and cleaning",
            timeout_seconds=120,
        ),
        AgentTask(
            goal="Analyze patterns",
            description="Identify patterns and anomalies",
            timeout_seconds=90,
        ),
    ]
    print(f"  Created {len(exec_tasks)} tasks\n")

    # Step 4: Execute in parallel
    print("Step 4: Executing tasks in parallel...")
    result = await executor.spawn_agents(
        tasks=exec_tasks,
        isolation=IsolationMode.THREAD,
        max_parallel=3,
    )
    print(f"  Batch {result.batch_id} completed")
    print(f"  Duration: {result.total_duration_seconds:.2f}s")
    print(f"  Success rate: {result.completed_tasks}/{result.total_tasks}\n")

    # Step 5: Aggregate results
    print("Step 5: Aggregating results...")
    config = AggregationConfig(
        merge_strategy=MergeStrategy.MERGE,
    )
    aggregated = await aggregator.collect_results(
        [r.to_dict() for r in result.results],
        config=config,
    )
    print(f"  Aggregation ID: {aggregated.aggregation_id}")
    print(f"  Successful results: {aggregated.successful_results}\n")

    # Step 6: Cleanup
    print("Step 6: Cleaning up...")
    executor.shutdown()
    await bus.shutdown()
    print("  Cleanup complete\n")

    print("=== Workflow Complete ===")


# Integration with FastAPI

def setup_parallel_agents_routes(app):
    """Setup parallel agents routes in FastAPI app."""
    from backend.app.api.parallel_agents import router

    app.include_router(router)
    print("Parallel agents routes registered")


# Configuration

class ParallelAgentConfig:
    """Configuration for parallel agent execution."""

    # Executor settings
    MAX_WORKERS = 3
    DEFAULT_ISOLATION = "thread"
    ENABLE_PROCESS_POOL = True
    ENABLE_THREAD_POOL = True

    # Communication bus settings
    ENABLE_PERSISTENCE = True
    MAX_QUEUE_SIZE = 10000
    MAX_HISTORY_SIZE = 10000

    # Aggregator settings
    DEFAULT_MERGE_STRATEGY = "merge"
    DEFAULT_CONFLICT_RESOLUTION = "keep_last"

    # Isolation manager settings
    ENABLE_RESOURCE_MONITORING = True
    MAX_CPU_PERCENT = 80.0
    MAX_MEMORY_MB = 512

    # Task dependency analyzer settings
    ENABLE_CYCLE_DETECTION = True
    ENABLE_OPTIMIZATION = True


# Usage in main application

async def initialize_parallel_agents():
    """Initialize parallel agent system."""
    from backend.app.core.parallel_agent_executor import ParallelAgentExecutor
    from backend.app.core.agent_communication_bus import AgentCommunicationBus
    from backend.app.core.result_aggregator import ResultAggregator
    from backend.app.core.agent_isolation_manager import AgentIsolationManager
    from backend.app.core.task_dependency_analyzer import TaskDependencyAnalyzer

    # Create global instances
    executor = ParallelAgentExecutor(
        max_workers=ParallelAgentConfig.MAX_WORKERS,
    )
    bus = AgentCommunicationBus(
        enable_persistence=ParallelAgentConfig.ENABLE_PERSISTENCE,
        max_queue_size=ParallelAgentConfig.MAX_QUEUE_SIZE,
    )
    aggregator = ResultAggregator()
    isolation_manager = AgentIsolationManager(
        enable_resource_monitoring=ParallelAgentConfig.ENABLE_RESOURCE_MONITORING,
    )
    analyzer = TaskDependencyAnalyzer()

    return {
        "executor": executor,
        "bus": bus,
        "aggregator": aggregator,
        "isolation_manager": isolation_manager,
        "analyzer": analyzer,
    }


if __name__ == "__main__":
    import asyncio

    # Run examples
    async def main():
        print("Running parallel agent examples...\n")

        print("Example 1: Basic Parallel Execution")
        print("-" * 40)
        # await example_basic_parallel_execution()
        print()

        print("Example 2: Inter-Agent Communication")
        print("-" * 40)
        await example_inter_agent_communication()
        print()

        print("Example 3: Topic-Based Pub/Sub")
        print("-" * 40)
        await example_topic_pubsub()
        print()

        print("Example 4: Result Aggregation")
        print("-" * 40)
        await example_result_aggregation()
        print()

        print("Example 5: Task Dependency Analysis")
        print("-" * 40)
        await example_task_dependency_analysis()
        print()

        print("Example 6: Isolation Management")
        print("-" * 40)
        await example_isolation_management()
        print()

        print("Example 7: Complete Workflow")
        print("-" * 40)
        await example_complete_workflow()

    asyncio.run(main())
