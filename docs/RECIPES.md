# Recipes & Common Patterns

Collection of common recipes and patterns for using X-Agent Core.

## Table of Contents

- [Workflow Recipes](#workflow-recipes)
- [Agent Recipes](#agent-recipes)
- [Memory Recipes](#memory-recipes)
- [Integration Recipes](#integration-recipes)
- [Performance Recipes](#performance-recipes)

## Workflow Recipes

### Simple Sequential Workflow

```python
from xagent import Workflow, WorkflowStep

workflow = Workflow(name="simple_workflow")

# Add steps
workflow.add_step(WorkflowStep(
    name="step1",
    action="fetch_data",
    params={"url": "https://api.example.com/data"}
))

workflow.add_step(WorkflowStep(
    name="step2",
    action="process_data",
    params={"input": "${step1.output}"}
))

workflow.add_step(WorkflowStep(
    name="step3",
    action="save_data",
    params={"data": "${step2.output}"}
))

# Execute workflow
result = workflow.execute()
```

### Conditional Workflow

```python
workflow = Workflow(name="conditional_workflow")

workflow.add_step(WorkflowStep(
    name="check_condition",
    action="check_status",
    params={"status": "active"}
))

workflow.add_step(WorkflowStep(
    name="process_if_active",
    action="process_data",
    condition="${check_condition.output.is_active}",
    params={"data": "active_data"}
))

workflow.add_step(WorkflowStep(
    name="process_if_inactive",
    action="process_data",
    condition="not ${check_condition.output.is_active}",
    params={"data": "inactive_data"}
))

result = workflow.execute()
```

### Parallel Workflow

```python
workflow = Workflow(name="parallel_workflow")

# Add parallel steps
workflow.add_parallel_steps([
    WorkflowStep(name="task1", action="fetch_data", params={"source": "api1"}),
    WorkflowStep(name="task2", action="fetch_data", params={"source": "api2"}),
    WorkflowStep(name="task3", action="fetch_data", params={"source": "api3"}),
])

# Combine results
workflow.add_step(WorkflowStep(
    name="combine",
    action="combine_data",
    params={
        "data1": "${task1.output}",
        "data2": "${task2.output}",
        "data3": "${task3.output}"
    }
))

result = workflow.execute()
```

### Error Handling Workflow

```python
workflow = Workflow(name="error_handling_workflow")

workflow.add_step(WorkflowStep(
    name="main_task",
    action="risky_operation",
    params={"data": "important_data"},
    retry_count=3,
    retry_delay=5,
    on_error="handle_error"
))

workflow.add_step(WorkflowStep(
    name="handle_error",
    action="log_error",
    params={"error": "${main_task.error}"}
))

result = workflow.execute()
```

## Agent Recipes

### Simple Agent

```python
from xagent import Agent

agent = Agent(
    name="simple_agent",
    model="gpt-4",
    tools=["web_search", "calculator"]
)

# Execute task
result = agent.execute("What is 2 + 2?")
print(result)
```

### Multi-Tool Agent

```python
agent = Agent(
    name="multi_tool_agent",
    model="claude-3-opus",
    tools=[
        "web_search",
        "calculator",
        "file_reader",
        "file_writer",
        "email_sender"
    ]
)

# Execute complex task
result = agent.execute("""
    1. Search for the latest AI news
    2. Calculate the average sentiment score
    3. Write a summary to a file
    4. Send the summary via email
""")
```

### Agent with Memory

```python
agent = Agent(
    name="memory_agent",
    model="gpt-4",
    tools=["web_search", "calculator"],
    memory_enabled=True,
    memory_retention_days=30
)

# First interaction
result1 = agent.execute("Remember that I like Python")

# Second interaction (agent remembers)
result2 = agent.execute("What programming language do I like?")
# Output: "You like Python"
```

### Multi-Agent Collaboration

```python
from xagent import Agent, AgentTeam

# Create agents with different specialties
researcher = Agent(
    name="researcher",
    model="gpt-4",
    tools=["web_search", "document_reader"]
)

analyst = Agent(
    name="analyst",
    model="gpt-4",
    tools=["calculator", "data_analyzer"]
)

writer = Agent(
    name="writer",
    model="gpt-4",
    tools=["file_writer", "email_sender"]
)

# Create team
team = AgentTeam(agents=[researcher, analyst, writer])

# Execute collaborative task
result = team.execute("""
    1. Researcher: Find information about X-Agent
    2. Analyst: Analyze the information
    3. Writer: Write a report
""")
```

## Memory Recipes

### Store Information

```python
from xagent.memory import Memory

memory = Memory()

# Store simple data
memory.store("user_preference", {
    "language": "Python",
    "framework": "FastAPI"
})

# Store with metadata
memory.store("project_info", {
    "name": "X-Agent",
    "description": "Autonomous agent framework"
}, metadata={
    "category": "AI",
    "importance": "high"
})
```

### Retrieve Information

```python
# Retrieve by key
data = memory.retrieve("user_preference")

# Semantic search
results = memory.search("Python frameworks", limit=5)

# Retrieve with filters
results = memory.retrieve_by_metadata(
    category="AI",
    importance="high"
)
```

### Memory Consolidation

```python
# Consolidate old memories
memory.consolidate(days=30)

# Archive old memories
memory.archive(before_date="2025-01-01")

# Clear specific memories
memory.clear("old_data")
```

## Integration Recipes

### Slack Integration

```python
from xagent.integrations import SlackIntegration

slack = SlackIntegration(token="xoxb-...")

# Send message
slack.send_message(
    channel="#general",
    text="Hello from X-Agent!"
)

# Send rich message
slack.send_message(
    channel="#general",
    blocks=[
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*X-Agent Update*\nWorkflow completed successfully"
            }
        }
    ]
)
```

### GitHub Integration

```python
from xagent.integrations import GitHubIntegration

github = GitHubIntegration(token="ghp_...")

# Create issue
github.create_issue(
    repo="x-agent/x-agent-core",
    title="Bug: Memory leak in workflow",
    body="Description of the bug",
    labels=["bug", "critical"]
)

# Create pull request
github.create_pull_request(
    repo="x-agent/x-agent-core",
    title="Fix: Memory leak in workflow",
    body="This PR fixes the memory leak",
    head="fix/memory-leak",
    base="develop"
)
```

### Database Integration

```python
from xagent.integrations import DatabaseIntegration

db = DatabaseIntegration(
    url="postgresql://user:password@localhost/xagent"
)

# Execute query
results = db.query("SELECT * FROM workflows WHERE status = %s", ("active",))

# Insert data
db.insert("workflows", {
    "name": "my_workflow",
    "status": "active",
    "created_at": datetime.now()
})

# Update data
db.update("workflows", {"status": "completed"}, {"id": 123})
```

## Performance Recipes

### Batch Processing

```python
from xagent.utils import batch_process

# Process large dataset in batches
data = list(range(10000))

def process_batch(batch):
    return [x * 2 for x in batch]

results = batch_process(data, process_batch, batch_size=100)
```

### Caching

```python
from xagent.utils import cache

@cache(ttl=3600)  # Cache for 1 hour
def expensive_operation(param):
    # Expensive computation
    return result

# First call: computes result
result1 = expensive_operation("param1")

# Second call: returns cached result
result2 = expensive_operation("param1")
```

### Async Execution

```python
import asyncio
from xagent import Agent

async def run_agents():
    agent1 = Agent(name="agent1", model="gpt-4")
    agent2 = Agent(name="agent2", model="gpt-4")
    
    # Run agents concurrently
    results = await asyncio.gather(
        agent1.execute_async("Task 1"),
        agent2.execute_async("Task 2")
    )
    
    return results

# Execute
results = asyncio.run(run_agents())
```

### Rate Limiting

```python
from xagent.utils import rate_limit

@rate_limit(calls=100, period=60)  # 100 calls per minute
def api_call(endpoint):
    return requests.get(endpoint)

# This will be rate limited
for i in range(150):
    api_call(f"https://api.example.com/endpoint/{i}")
```

## Best Practices

1. **Error Handling**: Always handle errors gracefully
2. **Logging**: Log important events and errors
3. **Testing**: Test recipes before using in production
4. **Documentation**: Document custom recipes
5. **Performance**: Monitor and optimize performance
6. **Security**: Validate all inputs and outputs

## Additional Resources

- [API Documentation](./API.md)
- [Examples](./EXAMPLES.md)
- [Tutorials](./tutorials/)
- [Best Practices](./best-practices/)

---

Last Updated: 2026-05-28
