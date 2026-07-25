# Code Examples

Practical examples demonstrating X-Agent Core features.

## Table of Contents

- [Basic Workflow](#basic-workflow)
- [LLM Integration](#llm-integration)
- [Memory Management](#memory-management)
- [Browser Automation](#browser-automation)
- [Approval Workflows](#approval-workflows)
- [Error Handling](#error-handling)

## Basic Workflow

### Creating and Executing a Simple Workflow

```python
from backend.app.core.execution_planner import ExecutionPlanner
from backend.app.core.llm import LLMRouter

# Initialize components
planner = ExecutionPlanner()
llm_router = LLMRouter()

# Define workflow
workflow = {
    "name": "Simple Analysis",
    "steps": [
        {
            "id": "analyze",
            "type": "llm_call",
            "prompt": "Analyze this data: {data}",
            "model": "gpt-4"
        }
    ]
}

# Execute workflow
result = await planner.execute(
    workflow=workflow,
    input_data={"data": "Sample data"}
)

print(f"Result: {result}")
```

### Workflow with Conditional Logic

```python
workflow = {
    "name": "Conditional Analysis",
    "steps": [
        {
            "id": "check_data",
            "type": "llm_call",
            "prompt": "Is this data valid? {data}",
            "model": "gpt-4"
        },
        {
            "id": "process_valid",
            "type": "conditional",
            "condition": "check_data.result.contains('valid')",
            "then_steps": [
                {
                    "id": "analyze",
                    "type": "llm_call",
                    "prompt": "Analyze: {data}"
                }
            ],
            "else_steps": [
                {
                    "id": "reject",
                    "type": "action",
                    "action": "log_error",
                    "message": "Invalid data"
                }
            ]
        }
    ]
}
```

## LLM Integration

### Using Multiple LLM Providers

```python
from backend.app.core.llm import LLMRouter

router = LLMRouter()

# Route to different models based on task
response = await router.call(
    prompt="Analyze this complex data",
    model="gpt-4",  # Use GPT-4 for complex tasks
    temperature=0.7,
    max_tokens=2000
)

# Fallback to cheaper model if needed
response = await router.call(
    prompt="Simple classification task",
    model="gpt-3.5-turbo",  # Use cheaper model
    fallback_models=["gpt-4"]
)
```

### Streaming LLM Responses

```python
async def stream_analysis(data: str):
    router = LLMRouter()
    
    async for chunk in router.stream(
        prompt=f"Analyze: {data}",
        model="gpt-4"
    ):
        print(chunk, end="", flush=True)
```

### Using Claude with X-Agent

```python
from backend.app.core.llm import LLMRouter

router = LLMRouter()

response = await router.call(
    prompt="Explain quantum computing",
    model="claude-3-opus",
    system_prompt="You are a helpful AI assistant"
)

print(response.content)
```

## Memory Management

### Storing and Retrieving Memory

```python
from backend.app.core.memory_postgres import PostgresMemory
from backend.app.services.memory.qdrant_client import QdrantClient

# Initialize memory systems
postgres_memory = PostgresMemory()
vector_memory = QdrantClient()

# Store a fact
await postgres_memory.store(
    content="X-Agent is an autonomous agent framework",
    metadata={"type": "fact", "source": "documentation"}
)

# Store with embedding for semantic search
embedding = await vector_memory.embed("X-Agent framework")
await vector_memory.store(
    content="X-Agent is an autonomous agent framework",
    embedding=embedding,
    metadata={"type": "fact"}
)

# Search memory
results = await vector_memory.search(
    query="What is X-Agent?",
    limit=5
)

for result in results:
    print(f"Found: {result.content} (similarity: {result.similarity})")
```

### Building Context from Memory

```python
async def build_context(query: str, memory_system):
    # Search for relevant memories
    memories = await memory_system.search(query, limit=10)
    
    # Build context string
    context = "Relevant information:\n"
    for memory in memories:
        context += f"- {memory.content}\n"
    
    return context

# Use in workflow
context = await build_context("project status", vector_memory)
response = await router.call(
    prompt=f"{context}\n\nBased on the above, provide an update",
    model="gpt-4"
)
```

## Browser Automation

### Web Scraping Example

```python
from backend.app.services.browser.automation import BrowserAutomation

browser = BrowserAutomation()

async with browser.session() as session:
    # Navigate to website
    await session.navigate("https://example.com")
    
    # Take screenshot
    screenshot = await session.screenshot()
    
    # Extract data
    dom = await session.get_dom()
    
    # Fill form
    await session.fill_form({
        "email": "user@example.com",
        "password": "password123"
    })
    
    # Click button
    await session.click("button[type='submit']")
    
    # Wait for navigation
    await session.wait_for_navigation()
```

### Automated Data Collection

```python
async def collect_data(urls: list):
    browser = BrowserAutomation()
    data = []
    
    async with browser.session() as session:
        for url in urls:
            await session.navigate(url)
            
            # Extract structured data
            content = await session.get_dom()
            
            # Parse and store
            data.append({
                "url": url,
                "content": content,
                "timestamp": datetime.now()
            })
    
    return data
```

## Approval Workflows

### Requiring Approval for Sensitive Actions

```python
from backend.app.core.approvals import ApprovalManager

approval_manager = ApprovalManager()

# Create approval request
approval = await approval_manager.create_approval(
    workflow_run_id="run_123",
    action="Execute external API call",
    description="Call third-party payment API",
    required_approvers=["admin@example.com"],
    timeout_minutes=30
)

# Wait for approval
result = await approval_manager.wait_for_approval(approval.id)

if result.approved:
    # Execute the action
    await execute_payment_api()
else:
    # Handle rejection
    print(f"Approval rejected: {result.reason}")
```

### Multi-Level Approvals

```python
# Create approval chain
approvals = await approval_manager.create_approval_chain(
    workflow_run_id="run_123",
    levels=[
        {
            "level": 1,
            "approvers": ["manager@example.com"],
            "description": "Manager approval"
        },
        {
            "level": 2,
            "approvers": ["director@example.com"],
            "description": "Director approval"
        }
    ]
)

# Wait for all approvals
for approval in approvals:
    result = await approval_manager.wait_for_approval(approval.id)
    if not result.approved:
        raise Exception(f"Approval rejected at level {approval.level}")
```

## Error Handling

### Workflow with Error Handling

```python
workflow = {
    "name": "Robust Workflow",
    "steps": [
        {
            "id": "fetch_data",
            "type": "api_call",
            "url": "https://api.example.com/data",
            "retry": {
                "max_attempts": 3,
                "backoff": "exponential"
            },
            "error_handling": {
                "on_error": "continue",
                "fallback_value": {"data": []}
            }
        },
        {
            "id": "process",
            "type": "llm_call",
            "prompt": "Process: {data}",
            "timeout_seconds": 30
        }
    ]
}
```

### Try-Catch Pattern

```python
async def safe_workflow_execution(workflow, input_data):
    try:
        result = await planner.execute(
            workflow=workflow,
            input_data=input_data
        )
        return {"success": True, "result": result}
    
    except TimeoutError:
        print("Workflow execution timed out")
        return {"success": False, "error": "timeout"}
    
    except ValidationError as e:
        print(f"Validation error: {e}")
        return {"success": False, "error": "validation"}
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"success": False, "error": "unknown"}
```

## Complete Example: Data Analysis Workflow

```python
async def data_analysis_workflow():
    # Initialize components
    planner = ExecutionPlanner()
    llm_router = LLMRouter()
    memory = PostgresMemory()
    vector_memory = QdrantClient()
    browser = BrowserAutomation()
    approval_manager = ApprovalManager()
    
    # Define workflow
    workflow = {
        "name": "Complete Data Analysis",
        "steps": [
            {
                "id": "fetch_data",
                "type": "browser_automation",
                "action": "navigate_and_extract",
                "url": "https://data.example.com"
            },
            {
                "id": "analyze",
                "type": "llm_call",
                "prompt": "Analyze this data: {data}",
                "model": "gpt-4"
            },
            {
                "id": "store_results",
                "type": "memory_store",
                "content": "{analysis_result}",
                "metadata": {"type": "analysis"}
            },
            {
                "id": "approval",
                "type": "approval",
                "action": "Publish analysis results",
                "approvers": ["manager@example.com"]
            },
            {
                "id": "publish",
                "type": "api_call",
                "url": "https://api.example.com/publish",
                "method": "POST",
                "data": "{analysis_result}"
            }
        ]
    }
    
    # Execute workflow
    result = await planner.execute(
        workflow=workflow,
        input_data={}
    )
    
    return result
```

## Testing Examples

### Unit Test Example

```python
import pytest
from backend.app.core.llm import LLMRouter

@pytest.fixture
def llm_router():
    return LLMRouter()

@pytest.mark.asyncio
async def test_llm_call(llm_router):
    response = await llm_router.call(
        prompt="What is 2+2?",
        model="gpt-4"
    )
    assert response.content is not None
    assert "4" in response.content
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_workflow_execution():
    workflow = {
        "name": "Test Workflow",
        "steps": [
            {
                "id": "test_step",
                "type": "llm_call",
                "prompt": "Test"
            }
        ]
    }
    
    result = await planner.execute(workflow=workflow)
    assert result.status == "completed"
```

---

For more examples, see [API Documentation](../api/API.md) and [Architecture Guide](../../concepts/architecture/ARCHITECTURE.md).
