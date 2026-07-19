"""Multi-Agent Collaboration Architecture and Best Practices.

This document provides comprehensive guidance on using the X-Agent multi-agent
collaboration system.
"""

# Multi-Agent Collaboration System Architecture

## Overview

The X-Agent collaboration system enables multiple agents to work together on
complex tasks through coordinated execution, state synchronization, and result
aggregation.

## Core Components

### 1. Communication Protocol (`protocol.py`)

**Purpose**: Enable inter-agent messaging with support for synchronous and
asynchronous communication.

**Key Classes**:
- `Message`: Base message class with serialization support
- `Request`: Request message for task execution
- `Response`: Response message with results
- `Event`: Event notification message
- `MessageRouter`: Routes messages between agents

**Usage Pattern**:
```python
router = MessageRouter()

# Register handler
async def handle_message(msg: Message):
    if isinstance(msg, Request):
        result = await process(msg.payload)
        await router.send_response(msg, result)

await router.register_handler("agent_id", handle_message)

# Send request
request = Request(
    sender_id="agent1",
    receiver_id="agent2",
    action="process",
    parameters={"data": "..."}
)
response = await router.send_message(request, wait_response=True)
```

### 2. Agent Registry (`registry.py`)

**Purpose**: Manage agent discovery, capability tracking, and health monitoring.

**Key Classes**:
- `AgentCapability`: Describes what an agent can do
- `AgentInfo`: Agent metadata and status
- `AgentRegistry`: Central registry for agent management

**Usage Pattern**:
```python
registry = AgentRegistry()

# Register agent
agent_info = await registry.register_agent(
    name="DataProcessor",
    agent_type="processor",
    capabilities=[
        AgentCapability(
            name="process_data",
            description="Process data chunks",
            estimated_duration=1.0
        )
    ]
)

# Find agents by capability
agents = await registry.find_agents_for_capability("process_data")

# Update agent status
await registry.update_agent_status(agent_id, AgentStatus.HEALTHY)

# Record heartbeat
await registry.heartbeat(agent_id)
```

### 3. Task Dispatcher (`dispatcher.py`)

**Purpose**: Distribute tasks to agents using various strategies.

**Key Classes**:
- `Task`: Represents a unit of work
- `TaskDispatcher`: Manages task distribution
- `DispatchStrategy`: Enum for dispatch strategies

**Dispatch Strategies**:
- `ROUND_ROBIN`: Distribute tasks in round-robin fashion
- `LEAST_LOADED`: Assign to least busy agent
- `CAPABILITY_MATCH`: Match task to agent capabilities
- `PRIORITY_QUEUE`: Prioritize high-priority tasks
- `RANDOM`: Random assignment

**Usage Pattern**:
```python
dispatcher = TaskDispatcher(strategy=DispatchStrategy.CAPABILITY_MATCH)

# Submit task
task = await dispatcher.submit_task(
    name="analyze_data",
    action="analyze",
    parameters={"data": "..."},
    required_capability="analyze",
    priority=5
)

# Dispatch to agent
agent_id = await dispatcher.dispatch_task(task.task_id, agents)

# Track task
task = await dispatcher.get_task(task.task_id)
```

### 4. State Synchronization (`state_sync.py`)

**Purpose**: Maintain consistent distributed state across agents.

**Key Classes**:
- `StateManager`: Manages local and remote state
- `ConflictResolutionStrategy`: Base for conflict resolution
- `LastWriteWinsStrategy`: Last write wins conflict resolution
- `MergeStrategy`: Merge-based conflict resolution

**Usage Pattern**:
```python
state_manager = StateManager()

# Set local state
await state_manager.set_state("key", "value")

# Sync with remote agent
remote_state = {"key": "remote_value", "new_key": "new_value"}
await state_manager.sync_state("agent_id", remote_state)

# Create snapshot
snapshot = await state_manager.create_snapshot("agent_id")

# Restore from snapshot
await state_manager.restore_snapshot(snapshot.snapshot_id)

# Get state diff
diff = await state_manager.get_state_diff(other_state)
```

### 5. Result Aggregation (`aggregator.py`)

**Purpose**: Combine partial results from multiple agents.

**Key Classes**:
- `PartialResult`: Result from single agent
- `AggregatedResult`: Final combined result
- `ResultAggregator`: Aggregates results

**Aggregation Strategies**:
- `MERGE`: Merge dictionaries
- `CONCAT`: Concatenate lists
- `FIRST`: Return first successful result
- `LAST`: Return last successful result
- `MAJORITY_VOTE`: Return majority voted result
- `CUSTOM`: Custom aggregation function

**Usage Pattern**:
```python
aggregator = ResultAggregator(strategy=AggregationStrategy.MERGE)

# Add partial results
await aggregator.add_partial_result(
    task_id="task1",
    agent_id="agent1",
    data={"key1": "value1"}
)

await aggregator.add_partial_result(
    task_id="task1",
    agent_id="agent2",
    data={"key2": "value2"}
)

# Aggregate
result = await aggregator.aggregate_results("task1")
print(result.final_result)  # {"key1": "value1", "key2": "value2"}
```

### 6. Collaboration Patterns (`patterns.py`)

**Purpose**: Provide reusable patterns for common collaboration scenarios.

**Available Patterns**:

#### Pipeline Pattern
Sequential execution through agents:
```python
pattern = PipelinePattern(["agent1", "agent2", "agent3"])
context = PatternContext(
    pattern_id="pipeline",
    agents=agents,
    initial_data={"input": "data"}
)
result = await pattern.execute(context)
```

#### MapReduce Pattern
Parallel execution with aggregation:
```python
pattern = MapReducePattern(
    map_agents=["agent1", "agent2", "agent3"],
    reducer=custom_reducer_function
)
result = await pattern.execute(context)
```

#### Master-Worker Pattern
Centralized coordination:
```python
pattern = MasterWorkerPattern(
    master_agent_id="master",
    worker_agent_ids=["worker1", "worker2", "worker3"]
)
result = await pattern.execute(context)
```

#### Peer-to-Peer Pattern
Decentralized collaboration:
```python
pattern = PeerToPeerPattern(["agent1", "agent2", "agent3"])
result = await pattern.execute(context)
```

### 7. Monitoring (`monitor.py`)

**Purpose**: Track performance and identify bottlenecks.

**Key Classes**:
- `TaskMetrics`: Metrics for individual tasks
- `AgentMetrics`: Metrics for agents
- `CollaborationMetrics`: Overall collaboration metrics
- `CollaborationMonitor`: Monitoring coordinator

**Usage Pattern**:
```python
monitor = CollaborationMonitor()

await monitor.start_collaboration()

# Track task
await monitor.start_task("task1", "agent1")
await asyncio.sleep(1)
await monitor.end_task("task1", status="completed")

await monitor.end_collaboration()

# Get metrics
summary = await monitor.get_performance_summary()
bottleneck = await monitor.get_bottleneck_analysis()
```

## Best Practices

### 1. Agent Design

- **Single Responsibility**: Each agent should have a clear, focused purpose
- **Capability Declaration**: Explicitly declare capabilities for proper routing
- **Error Handling**: Implement robust error handling and recovery
- **Timeout Management**: Set appropriate timeouts for operations
- **Resource Limits**: Define max concurrent tasks to prevent overload

### 2. Task Management

- **Task Decomposition**: Break complex tasks into smaller subtasks
- **Priority Assignment**: Use priorities to handle urgent tasks first
- **Dependency Tracking**: Track task dependencies for proper sequencing
- **Retry Logic**: Implement exponential backoff for retries
- **Timeout Handling**: Handle timeouts gracefully

### 3. State Management

- **Minimize Shared State**: Keep shared state to minimum
- **Conflict Resolution**: Choose appropriate conflict resolution strategy
- **State Snapshots**: Create snapshots before risky operations
- **State Validation**: Validate state consistency
- **State Cleanup**: Clean up old state periodically

### 4. Communication

- **Message Serialization**: Use JSON for cross-process communication
- **Correlation IDs**: Track related messages with correlation IDs
- **Timeout Configuration**: Set appropriate timeouts for requests
- **Error Responses**: Always respond with error details
- **Message Ordering**: Consider message ordering requirements

### 5. Performance Optimization

- **Load Balancing**: Use least-loaded strategy for even distribution
- **Capability Matching**: Match tasks to agent capabilities
- **Parallel Execution**: Use MapReduce for parallel processing
- **Result Caching**: Cache frequently accessed results
- **Batch Processing**: Batch small tasks together

### 6. Monitoring and Debugging

- **Comprehensive Logging**: Log all important events
- **Metrics Collection**: Track key performance metrics
- **Bottleneck Analysis**: Identify and address bottlenecks
- **Performance Profiling**: Profile slow operations
- **Health Checks**: Regular health checks for agents

### 7. Scalability

- **Horizontal Scaling**: Add more agents as needed
- **Load Distribution**: Distribute load across agents
- **Resource Pooling**: Share resources efficiently
- **Circuit Breakers**: Implement circuit breakers for failing agents
- **Graceful Degradation**: Handle agent failures gracefully

## Common Patterns

### Pattern 1: Data Processing Pipeline
```python
# Process data through multiple stages
pattern = PipelinePattern([
    "data_loader",
    "data_cleaner",
    "data_transformer",
    "data_validator"
])
```

### Pattern 2: Parallel Analysis
```python
# Analyze data from multiple perspectives
pattern = MapReducePattern(
    map_agents=["sentiment_analyzer", "topic_analyzer", "entity_analyzer"],
    reducer=merge_analysis_results
)
```

### Pattern 3: Hierarchical Processing
```python
# Process with hierarchy
pattern = HierarchicalPattern({
    "coordinator": ["processor1", "processor2"],
    "processor1": ["worker1", "worker2"],
    "processor2": ["worker3", "worker4"]
})
```

### Pattern 4: Collaborative Problem Solving
```python
# Multiple agents collaborate as peers
pattern = PeerToPeerPattern([
    "analyzer",
    "researcher",
    "synthesizer"
])
```

## Error Handling

### Task Failures
```python
try:
    result = await agent.process(task)
except Exception as e:
    if task.is_retryable():
        task.retry_count += 1
        await dispatcher.submit_task(...)
    else:
        await monitor.end_task(task.task_id, status="failed", error=str(e))
```

### Agent Failures
```python
# Monitor agent health
if not agent.is_healthy():
    await registry.update_agent_status(agent_id, AgentStatus.UNHEALTHY)
    # Reassign tasks to other agents
    await dispatcher.reassign_tasks(agent_id)
```

### State Conflicts
```python
# Use appropriate conflict resolution
manager = StateManager(conflict_strategy=MergeStrategy())
await manager.sync_state(agent_id, remote_state)
```

## Performance Tuning

### Metrics to Monitor
- Task execution time
- Agent load distribution
- Message latency
- State sync frequency
- Error rates

### Optimization Strategies
- Adjust dispatch strategy based on workload
- Tune timeout values
- Optimize state sync frequency
- Batch small tasks
- Use caching for frequently accessed data

## Troubleshooting

### High Latency
- Check agent load distribution
- Verify network connectivity
- Review message queue size
- Profile slow operations

### High Error Rate
- Check agent health
- Review error logs
- Verify task parameters
- Check resource availability

### Uneven Load Distribution
- Switch to least-loaded strategy
- Check agent capabilities
- Verify task routing
- Review agent performance

## References

- Communication Protocol: `protocol.py`
- Agent Registry: `registry.py`
- Task Dispatcher: `dispatcher.py`
- State Synchronization: `state_sync.py`
- Result Aggregation: `aggregator.py`
- Collaboration Patterns: `patterns.py`
- Monitoring: `monitor.py`
- Examples: `examples.py`
- Tests: `test_collaboration.py`
