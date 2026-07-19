"""Integration Guide for Multi-Agent Collaboration System.

This guide explains how to integrate the collaboration system into X-Agent.
"""

# Integration Guide: Multi-Agent Collaboration System

## Quick Start

### 1. Import Required Components

```python
from backend.app.core.collaboration import (
    AgentRegistry,
    AgentCapability,
    TaskDispatcher,
    DispatchStrategy,
    MessageRouter,
    StateManager,
    ResultAggregator,
    AggregationStrategy,
    CollaborationMonitor,
    PipelinePattern,
    MapReducePattern,
)
```

### 2. Initialize Components

```python
# Create registry
registry = AgentRegistry()

# Create dispatcher
dispatcher = TaskDispatcher(strategy=DispatchStrategy.CAPABILITY_MATCH)

# Create message router
router = MessageRouter()

# Create state manager
state_manager = StateManager()

# Create result aggregator
aggregator = ResultAggregator(strategy=AggregationStrategy.MERGE)

# Create monitor
monitor = CollaborationMonitor()
```

### 3. Register Agents

```python
# Register an agent
agent_info = await registry.register_agent(
    name="DataAnalyzer",
    agent_type="analyzer",
    capabilities=[
        AgentCapability(
            name="analyze_data",
            description="Analyze data patterns",
            estimated_duration=2.0,
            tags=["analysis", "data"]
        )
    ],
    max_concurrent_tasks=5
)

agent_id = agent_info.agent_id
```

### 4. Submit and Execute Tasks

```python
# Submit task
task = await dispatcher.submit_task(
    name="analyze_sales_data",
    action="analyze",
    parameters={"data": sales_data},
    required_capability="analyze_data",
    priority=5
)

# Dispatch to agent
assigned_agent_id = await dispatcher.dispatch_task(task.task_id, agents)

# Monitor execution
await monitor.start_task(task.task_id, assigned_agent_id)

try:
    result = await execute_task(task)
    await aggregator.add_partial_result(task.task_id, assigned_agent_id, result)
    await monitor.end_task(task.task_id, status="completed")
except Exception as e:
    await monitor.end_task(task.task_id, status="failed", error=str(e))
```

## Integration Patterns

### Pattern 1: Integrate with AgentLoop

```python
from backend.app.core.agent import AgentLoop
from backend.app.core.collaboration import (
    TaskDispatcher,
    ResultAggregator,
    CollaborationMonitor,
)

class CollaborativeAgentLoop(AgentLoop):
    """AgentLoop with collaboration support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispatcher = TaskDispatcher()
        self.aggregator = ResultAggregator()
        self.monitor = CollaborationMonitor()

    async def execute_collaborative_task(self, task_description: str):
        """Execute task with collaboration."""
        await self.monitor.start_collaboration()

        # Decompose task
        subtasks = await self._decompose_task(task_description)

        # Dispatch subtasks
        for subtask in subtasks:
            task = await self.dispatcher.submit_task(
                name=subtask["name"],
                action=subtask["action"],
                parameters=subtask["parameters"]
            )

        # Collect results
        results = []
        for subtask in subtasks:
            result = await self.aggregator.aggregate_results(subtask["task_id"])
            results.append(result)

        await self.monitor.end_collaboration()
        return results
```

### Pattern 2: Integrate with Tool Execution

```python
from backend.app.core.tool_executor import ToolExecutor
from backend.app.core.collaboration import TaskDispatcher

class CollaborativeToolExecutor(ToolExecutor):
    """Tool executor with collaboration support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispatcher = TaskDispatcher()

    async def execute_tool(self, tool_name: str, parameters: dict):
        """Execute tool with potential collaboration."""
        # Check if tool can be parallelized
        if self._is_parallelizable(tool_name):
            # Dispatch to multiple agents
            tasks = await self._create_parallel_tasks(tool_name, parameters)
            results = await self._collect_results(tasks)
            return self._merge_results(results)
        else:
            # Execute normally
            return await super().execute_tool(tool_name, parameters)
```

### Pattern 3: Integrate with Memory System

```python
from backend.app.core.memory import MemorySystem
from backend.app.core.collaboration import StateManager

class CollaborativeMemorySystem(MemorySystem):
    """Memory system with distributed state support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_manager = StateManager()

    async def sync_memory_across_agents(self, agent_ids: list[str]):
        """Synchronize memory across agents."""
        for agent_id in agent_ids:
            agent_memory = await self._get_agent_memory(agent_id)
            await self.state_manager.sync_state(agent_id, agent_memory)
```

### Pattern 4: Integrate with Workflow System

```python
from backend.app.core.workflows import WorkflowRepository
from backend.app.core.collaboration import (
    PipelinePattern,
    MapReducePattern,
    PatternContext,
)

class CollaborativeWorkflow:
    """Workflow with collaboration support."""

    def __init__(self, workflow_repo: WorkflowRepository):
        self.workflow_repo = workflow_repo

    async def execute_collaborative_workflow(self, workflow_id: str, agents: dict):
        """Execute workflow with collaboration."""
        workflow = await self.workflow_repo.get_workflow(workflow_id)

        if workflow.collaboration_type == "pipeline":
            pattern = PipelinePattern(workflow.agent_sequence)
        elif workflow.collaboration_type == "mapreduce":
            pattern = MapReducePattern(workflow.map_agents)
        else:
            raise ValueError(f"Unknown collaboration type: {workflow.collaboration_type}")

        context = PatternContext(
            pattern_id=workflow_id,
            agents=agents,
            initial_data=workflow.initial_data
        )

        return await pattern.execute(context)
```

## API Integration

### REST API Endpoints

```python
from fastapi import APIRouter, HTTPException
from backend.app.core.collaboration import (
    AgentRegistry,
    TaskDispatcher,
    CollaborationMonitor,
)

router = APIRouter(prefix="/api/collaboration", tags=["collaboration"])

# Agent Management
@router.post("/agents")
async def register_agent(agent_data: dict):
    """Register a new agent."""
    registry = AgentRegistry()
    agent_info = await registry.register_agent(**agent_data)
    return agent_info

@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent information."""
    registry = AgentRegistry()
    agent = await registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.get("/agents")
async def list_agents(agent_type: str = None):
    """List agents."""
    registry = AgentRegistry()
    agents = await registry.list_agents(agent_type=agent_type)
    return agents

# Task Management
@router.post("/tasks")
async def submit_task(task_data: dict):
    """Submit a new task."""
    dispatcher = TaskDispatcher()
    task = await dispatcher.submit_task(**task_data)
    return task

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task information."""
    dispatcher = TaskDispatcher()
    task = await dispatcher.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/tasks")
async def list_tasks(status: str = None, agent_id: str = None):
    """List tasks."""
    dispatcher = TaskDispatcher()
    tasks = await dispatcher.list_tasks(status=status, agent_id=agent_id)
    return tasks

# Monitoring
@router.get("/metrics/collaboration")
async def get_collaboration_metrics():
    """Get collaboration metrics."""
    monitor = CollaborationMonitor()
    metrics = await monitor.get_collaboration_metrics()
    return metrics

@router.get("/metrics/agents")
async def get_agent_metrics():
    """Get agent metrics."""
    monitor = CollaborationMonitor()
    metrics = await monitor.get_all_agent_metrics()
    return metrics

@router.get("/metrics/bottleneck")
async def get_bottleneck_analysis():
    """Get bottleneck analysis."""
    monitor = CollaborationMonitor()
    analysis = await monitor.get_bottleneck_analysis()
    return analysis
```

## Configuration

### Environment Variables

```bash
# Collaboration System Configuration
COLLAB_HEARTBEAT_TIMEOUT=30
COLLAB_MESSAGE_QUEUE_SIZE=1000
COLLAB_MAX_RETRIES=3
COLLAB_TASK_TIMEOUT=300
COLLAB_DISPATCH_STRATEGY=capability_match
COLLAB_AGGREGATION_STRATEGY=merge
```

### Configuration File

```yaml
collaboration:
  heartbeat_timeout: 30
  message_queue_size: 1000
  max_retries: 3
  task_timeout: 300
  dispatch_strategy: capability_match
  aggregation_strategy: merge
  monitoring:
    enabled: true
    window_size: 100
    export_interval: 60
```

## Testing

### Unit Tests

```python
import pytest
from backend.app.core.collaboration import (
    AgentRegistry,
    TaskDispatcher,
    MessageRouter,
)

@pytest.mark.asyncio
async def test_agent_registration():
    """Test agent registration."""
    registry = AgentRegistry()
    agent = await registry.register_agent(
        name="test_agent",
        agent_type="processor",
        capabilities=[]
    )
    assert agent.name == "test_agent"

@pytest.mark.asyncio
async def test_task_dispatch():
    """Test task dispatch."""
    dispatcher = TaskDispatcher()
    task = await dispatcher.submit_task(
        name="test_task",
        action="process",
        parameters={}
    )
    assert task.name == "test_task"
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_end_to_end_collaboration():
    """Test end-to-end collaboration."""
    # Setup
    registry = AgentRegistry()
    dispatcher = TaskDispatcher()
    aggregator = ResultAggregator()

    # Register agents
    agent1 = await registry.register_agent(
        name="agent1",
        agent_type="processor",
        capabilities=[]
    )

    # Submit task
    task = await dispatcher.submit_task(
        name="test_task",
        action="process",
        parameters={"data": "test"}
    )

    # Dispatch and execute
    await dispatcher.dispatch_task(task.task_id, {agent1.agent_id: {}})

    # Verify
    assert task.status == TaskStatus.ASSIGNED
```

## Troubleshooting

### Common Issues

#### Issue: Tasks not being dispatched
**Solution**: Check agent availability and capabilities
```python
# Verify agents are registered
agents = await registry.list_agents()
assert len(agents) > 0

# Verify agent capabilities
agent = await registry.get_agent(agent_id)
assert len(agent.capabilities) > 0
```

#### Issue: High message latency
**Solution**: Check message queue size and network
```python
# Monitor queue size
stats = router.get_stats()
print(f"Queue size: {stats['queue_size']}")

# Increase queue size if needed
router._message_queue = asyncio.Queue(maxsize=5000)
```

#### Issue: Uneven load distribution
**Solution**: Switch dispatch strategy
```python
# Use least-loaded strategy
dispatcher = TaskDispatcher(strategy=DispatchStrategy.LEAST_LOADED)

# Or use capability matching
dispatcher = TaskDispatcher(strategy=DispatchStrategy.CAPABILITY_MATCH)
```

## Performance Optimization

### Tips for Better Performance

1. **Use appropriate dispatch strategy**
   - `LEAST_LOADED` for balanced distribution
   - `CAPABILITY_MATCH` for specialized tasks
   - `PRIORITY_QUEUE` for mixed workloads

2. **Optimize task granularity**
   - Not too small (overhead)
   - Not too large (blocking)
   - Aim for 100ms - 1s per task

3. **Monitor and tune**
   - Track metrics regularly
   - Identify bottlenecks
   - Adjust configuration based on metrics

4. **Use appropriate aggregation strategy**
   - `MERGE` for combining dictionaries
   - `CONCAT` for combining lists
   - `MAJORITY_VOTE` for consensus

## References

- Architecture: `ARCHITECTURE.md`
- Examples: `examples.py`
- Benchmarks: `benchmarks.py`
- Tests: `test_collaboration.py`
