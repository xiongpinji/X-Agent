"""
PARALLEL EXECUTION ENGINE - QUICK START GUIDE

This guide helps you get started with the Parallel Execution Engine
in 5 minutes.
"""

# ============================================================================
# INSTALLATION
# ============================================================================

"""
The Parallel Execution Engine is included in X-Agent core.

No additional dependencies required beyond:
- Python 3.10+
- asyncio (built-in)
- pydantic (already in X-Agent)
"""

# ============================================================================
# QUICK START: 5-MINUTE TUTORIAL
# ============================================================================

"""
STEP 1: Import the Engine
"""

from backend.app.core.parallel_execution_engine import (
    ParallelToolExecutor,
    ParallelAgentExecutor,
    AgentCommunicationBus,
    ToolDefinition,
    ToolCall,
    PriorityLevel,
)
import asyncio


"""
STEP 2: Define Your Tools
"""

async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    # Simulate API call
    await asyncio.sleep(0.5)
    return {"url": url, "data": "sample data"}


async def process_data(data: dict) -> dict:
    """Process fetched data."""
    await asyncio.sleep(0.3)
    return {"processed": True, "items": len(str(data))}


async def save_results(processed: dict) -> dict:
    """Save processed results."""
    await asyncio.sleep(0.2)
    return {"saved": True, "timestamp": "2026-05-28"}


"""
STEP 3: Create and Configure Executor
"""

async def main():
    # Create executor with 5 concurrent tools
    executor = ParallelToolExecutor(max_concurrent=5)

    # Register tools
    executor.register_tool(ToolDefinition(
        name="fetch_data",
        handler=fetch_data,
        timeout_seconds=10,
        priority=PriorityLevel.HIGH,
    ))

    executor.register_tool(ToolDefinition(
        name="process_data",
        handler=process_data,
        timeout_seconds=10,
    ))

    executor.register_tool(ToolDefinition(
        name="save_results",
        handler=save_results,
        timeout_seconds=10,
    ))

    """
    STEP 4: Create Tool Calls with Dependencies
    """

    tool_calls = [
        # First, fetch data (no dependencies)
        ToolCall(
            tool_id="fetch_1",
            tool_name="fetch_data",
            arguments={"url": "https://api.example.com/data"},
            priority=PriorityLevel.HIGH,
        ),

        # Then, process the fetched data
        ToolCall(
            tool_id="process_1",
            tool_name="process_data",
            arguments={"data": {}},  # Will receive output from fetch_1
            depends_on=["fetch_1"],
            priority=PriorityLevel.NORMAL,
        ),

        # Finally, save the results
        ToolCall(
            tool_id="save_1",
            tool_name="save_results",
            arguments={"processed": {}},  # Will receive output from process_1
            depends_on=["process_1"],
            priority=PriorityLevel.LOW,
        ),
    ]

    """
    STEP 5: Execute and Get Results
    """

    try:
        results = await executor.execute_tools(tool_calls)

        print("Execution Results:")
        for tool_id, result in results.items():
            print(f"  {tool_id}: {result}")

        # Get statistics
        stats = executor.get_execution_stats()
        print(f"\nExecution Statistics:")
        print(f"  Total tools: {stats['total_tools']}")
        print(f"  Completed: {stats['completed']}")
        print(f"  Success rate: {stats['success_rate']:.1%}")
        print(f"  Total duration: {stats['total_duration_ms']:.2f}ms")
        print(f"  Throughput: {stats['total_duration_ms'] / stats['total_tools']:.2f}ms per tool")

    except Exception as e:
        print(f"Error: {e}")


# ============================================================================
# COMMON PATTERNS
# ============================================================================

"""
PATTERN 1: Parallel Independent Tasks
"""

async def pattern_parallel_independent():
    """Execute multiple independent tasks in parallel."""
    executor = ParallelToolExecutor(max_concurrent=10)

    async def task(task_id: int) -> str:
        await asyncio.sleep(0.1)
        return f"Result {task_id}"

    executor.register_tool(ToolDefinition(
        name="task",
        handler=task,
    ))

    # Create independent tool calls (no dependencies)
    tool_calls = [
        ToolCall(
            tool_id=f"task_{i}",
            tool_name="task",
            arguments={"task_id": i},
        )
        for i in range(10)
    ]

    results = await executor.execute_tools(tool_calls)
    return results


"""
PATTERN 2: Sequential Pipeline
"""

async def pattern_sequential_pipeline():
    """Execute tools in a sequential pipeline."""
    executor = ParallelToolExecutor(max_concurrent=5)

    async def step1() -> dict:
        await asyncio.sleep(0.1)
        return {"step": 1}

    async def step2(prev: dict) -> dict:
        await asyncio.sleep(0.1)
        return {**prev, "step": 2}

    async def step3(prev: dict) -> dict:
        await asyncio.sleep(0.1)
        return {**prev, "step": 3}

    executor.register_tool(ToolDefinition(name="step1", handler=step1))
    executor.register_tool(ToolDefinition(name="step2", handler=step2))
    executor.register_tool(ToolDefinition(name="step3", handler=step3))

    tool_calls = [
        ToolCall(tool_id="s1", tool_name="step1", arguments={}),
        ToolCall(tool_id="s2", tool_name="step2", arguments={}, depends_on=["s1"]),
        ToolCall(tool_id="s3", tool_name="step3", arguments={}, depends_on=["s2"]),
    ]

    results = await executor.execute_tools(tool_calls)
    return results


"""
PATTERN 3: Fan-Out / Fan-In
"""

async def pattern_fan_out_fan_in():
    """Execute multiple tasks in parallel, then combine results."""
    executor = ParallelToolExecutor(max_concurrent=5)

    async def fetch(source: str) -> dict:
        await asyncio.sleep(0.1)
        return {"source": source, "data": f"data from {source}"}

    async def combine(results: list) -> dict:
        await asyncio.sleep(0.1)
        return {"combined": True, "count": len(results)}

    executor.register_tool(ToolDefinition(name="fetch", handler=fetch))
    executor.register_tool(ToolDefinition(name="combine", handler=combine))

    # Fan-out: fetch from multiple sources
    fetch_calls = [
        ToolCall(
            tool_id=f"fetch_{i}",
            tool_name="fetch",
            arguments={"source": f"source_{i}"},
        )
        for i in range(3)
    ]

    # Fan-in: combine results
    combine_call = ToolCall(
        tool_id="combine",
        tool_name="combine",
        arguments={"results": []},
        depends_on=[f"fetch_{i}" for i in range(3)],
    )

    tool_calls = fetch_calls + [combine_call]
    results = await executor.execute_tools(tool_calls)
    return results


"""
PATTERN 4: Multi-Agent Coordination
"""

async def pattern_multi_agent():
    """Coordinate multiple agents."""
    executor = ParallelAgentExecutor(max_agents=5)

    class AnalysisAgent:
        def __init__(self, agent_id: str, analysis_type: str):
            self.agent_id = agent_id
            self.analysis_type = analysis_type

        async def run(self, task: str, context: dict) -> dict:
            await asyncio.sleep(0.2)
            return {
                "agent_id": self.agent_id,
                "analysis_type": self.analysis_type,
                "result": f"Analysis complete",
            }

    # Register agents
    agents = [
        ("code_analyzer", "code"),
        ("performance_analyzer", "performance"),
        ("security_analyzer", "security"),
    ]

    for agent_id, analysis_type in agents:
        agent = AnalysisAgent(agent_id, analysis_type)
        executor.register_agent(agent_id, agent)

    # Execute all agents in parallel
    results = await executor.execute_agents(
        agent_ids=[agent_id for agent_id, _ in agents],
        task="Analyze the code",
        context={"file": "example.py"},
    )

    return results


"""
PATTERN 5: Inter-Agent Communication
"""

async def pattern_agent_communication():
    """Agents communicating through message bus."""
    bus = AgentCommunicationBus()

    async def coordinator():
        """Coordinator sends tasks to workers."""
        from backend.app.core.parallel_execution_engine import Message

        for i in range(3):
            message = Message(
                sender_id="coordinator",
                recipient_id=f"worker_{i}",
                message_type="task",
                payload={"task_id": i, "work": f"Process item {i}"},
                priority=PriorityLevel.HIGH,
            )
            await bus.send_message(message)
            await asyncio.sleep(0.1)

    async def worker(worker_id: str):
        """Worker processes tasks."""
        from backend.app.core.parallel_execution_engine import Message

        for _ in range(3):
            message = await bus.receive_message(worker_id, timeout_seconds=2.0)
            if message:
                print(f"{worker_id} received task: {message.payload}")

                # Send result back
                result = Message(
                    sender_id=worker_id,
                    recipient_id="coordinator",
                    message_type="result",
                    payload={"task_id": message.payload["task_id"], "status": "done"},
                )
                await bus.send_message(result)

    # Run coordinator and workers
    await asyncio.gather(
        coordinator(),
        worker("worker_0"),
        worker("worker_1"),
        worker("worker_2"),
    )


# ============================================================================
# BEST PRACTICES
# ============================================================================

"""
BEST PRACTICE 1: Error Handling
"""

async def best_practice_error_handling():
    """Proper error handling in parallel execution."""
    executor = ParallelToolExecutor(max_concurrent=5)

    async def risky_tool(value: int) -> int:
        if value < 0:
            raise ValueError("Value must be positive")
        await asyncio.sleep(0.1)
        return value * 2

    executor.register_tool(ToolDefinition(
        name="risky_tool",
        handler=risky_tool,
        retry_count=2,  # Retry failed tasks
        timeout_seconds=10,
    ))

    tool_calls = [
        ToolCall(
            tool_id=f"call_{i}",
            tool_name="risky_tool",
            arguments={"value": i - 5},  # Some will be negative
        )
        for i in range(10)
    ]

    try:
        results = await executor.execute_tools(tool_calls)
    except Exception as e:
        print(f"Execution failed: {e}")
        # Check metrics for details
        metrics = executor.get_metrics()
        for task_id, metric in metrics.items():
            if metric.status.value == "failed":
                print(f"  {task_id}: {metric.error}")


"""
BEST PRACTICE 2: Resource Management
"""

async def best_practice_resource_management():
    """Manage resources efficiently."""
    # Adjust max_concurrent based on resource availability
    # For I/O-bound tasks: higher concurrency (10-20)
    # For CPU-bound tasks: lower concurrency (2-4)
    # For mixed workloads: moderate concurrency (5-10)

    executor = ParallelToolExecutor(max_concurrent=5)

    async def io_bound_task() -> str:
        await asyncio.sleep(0.5)  # Simulate I/O
        return "done"

    executor.register_tool(ToolDefinition(
        name="io_task",
        handler=io_bound_task,
    ))

    # Monitor resource usage
    stats = executor.get_execution_stats()
    print(f"Success rate: {stats['success_rate']:.1%}")
    print(f"Throughput: {stats['total_duration_ms']:.2f}ms")


"""
BEST PRACTICE 3: Monitoring and Observability
"""

async def best_practice_monitoring():
    """Monitor execution performance."""
    from backend.app.core.parallel_execution_engine import execution_monitor

    executor = ParallelToolExecutor(max_concurrent=5)

    async def monitored_tool() -> str:
        await asyncio.sleep(0.1)
        return "done"

    executor.register_tool(ToolDefinition(
        name="monitored_tool",
        handler=monitored_tool,
    ))

    tool_calls = [
        ToolCall(
            tool_id=f"call_{i}",
            tool_name="monitored_tool",
            arguments={},
        )
        for i in range(10)
    ]

    import time
    start = time.time()
    results = await executor.execute_tools(tool_calls)
    duration = (time.time() - start) * 1000

    # Record metrics
    from backend.app.core.parallel_execution_engine import ExecutionStatus
    execution_monitor.record_execution(
        execution_id="batch_1",
        duration_ms=duration,
        status=ExecutionStatus.COMPLETED,
    )

    # Get performance stats
    perf_stats = execution_monitor.get_performance_stats()
    print(f"P95 latency: {perf_stats['p95_duration_ms']:.2f}ms")
    print(f"P99 latency: {perf_stats['p99_duration_ms']:.2f}ms")


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

"""
Q: How do I increase concurrency?
A: Increase max_concurrent parameter:
   executor = ParallelToolExecutor(max_concurrent=20)

Q: How do I handle timeouts?
A: Set timeout_seconds in ToolDefinition:
   ToolDefinition(name="tool", handler=handler, timeout_seconds=30)

Q: How do I retry failed tasks?
A: Set retry_count in ToolDefinition:
   ToolDefinition(name="tool", handler=handler, retry_count=3)

Q: How do I prioritize tasks?
A: Set priority in ToolCall:
   ToolCall(tool_id="call", tool_name="tool", priority=PriorityLevel.HIGH)

Q: How do I monitor performance?
A: Use ExecutionMonitor:
   stats = execution_monitor.get_performance_stats()
"""

# ============================================================================
# NEXT STEPS
# ============================================================================

"""
1. Read the full architecture document:
   backend/app/core/PARALLEL_EXECUTION_ARCHITECTURE.md

2. Run the examples:
   python -m backend.app.core.parallel_execution_examples

3. Run the benchmarks:
   python -m backend.app.core.parallel_execution_benchmark

4. Run the tests:
   pytest tests/test_parallel_execution_engine.py -v

5. Integrate with your agent:
   - Import ParallelToolExecutor
   - Register your tools
   - Create tool calls with dependencies
   - Execute and collect results
"""

if __name__ == "__main__":
    asyncio.run(main())
