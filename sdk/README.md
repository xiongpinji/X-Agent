# X-Agent SDK

[![PyPI](https://img.shields.io/pypi/v/xagent-sdk.svg)](https://pypi.org/project/xagent-sdk/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-quality Python SDK for interacting with **X-Agent** — an enterprise-grade autonomous agent framework for building intelligent workflows, multi-agent systems, and AI-powered automation.

## Features

- **Synchronous & Asynchronous APIs** — Choose sync (`XAgent`) or async (`AsyncXAgent`) based on your needs
- **Task Management** — Submit long-running tasks, poll status, and retrieve results
- **Interactive Chat** — Real-time interaction with the agent
- **Workflow Execution** — Run predefined workflow templates with custom parameters
- **Comprehensive Error Handling** — Specific exceptions for authentication, validation, rate limits, and server errors
- **Polling with Backoff** — Intelligent exponential backoff for task polling
- **Type-Safe** — Full type annotations with Pydantic models
- **Context Managers** — Clean resource management with context manager support
- **Production-Ready** — Tested, documented, and battle-hardened

## Installation

```bash
pip install xagent-sdk
```

For development:

```bash
pip install xagent-sdk[dev]
```

## Quick Start

### Synchronous Usage

```python
from xagent_sdk import XAgent

# Initialize client
client = XAgent(
    base_url="http://localhost:8000",
    api_key="your-api-key"  # Optional
)

# Check server health
health = client.health()
print(f"Server status: {health.status}")

# Submit a task
task = client.submit_task(
    description="Analyze code quality in this repository",
    repo="https://github.com/example/project",
    branch="main",
    params={"max_issues": 10}
)

# Wait for completion (with timeout)
result = task.wait(timeout=600, poll_interval=5)
print(f"Task status: {result.status}")
print(f"Results: {result.result}")

# Or use context manager for auto-cleanup
with XAgent(api_key="your-key") as client:
    response = client.chat("What are the security issues in this code?")
    print(response.content)
```

### Asynchronous Usage

```python
import asyncio
from xagent_sdk import AsyncXAgent

async def main():
    async with AsyncXAgent(api_key="your-key") as client:
        # Check health
        status = await client.health()
        print(f"Server: {status.status}")
        
        # Submit task
        task = await client.submit_task(
            "Analyze code quality",
            repo="https://github.com/example/project"
        )
        
        # Wait for result
        result = await task.wait(timeout=600)
        print(f"Result: {result.result}")
        
        # Chat
        response = await client.chat("Summarize the findings")
        print(response.content)

asyncio.run(main())
```

## API Reference

### XAgent (Synchronous Client)

#### Constructor

```python
client = XAgent(
    base_url="http://localhost:8000",  # Server URL
    api_key=None,                        # API key (optional)
    timeout=30.0                         # Request timeout in seconds
)
```

#### Methods

**`health() -> HealthStatus`**

Check server health and component status.

```python
status = client.health()
print(f"API: {status.components['api']}")
print(f"Database: {status.components['database']}")
```

**`submit_task(...) -> TaskHandle`**

Submit an async task for processing.

```python
task = client.submit_task(
    description="Do something",
    repo="https://github.com/example/project",  # Optional
    branch="main",                                # Optional
    params={"custom": "value"},                   # Optional
    timeout_seconds=300                           # Default: 300
)

# Poll manually
while not task.is_done:
    print(f"Progress: {task.poll().progress}%")

# Or wait for completion
result = task.wait(timeout=600, poll_interval=5)
```

**`chat(message, context=None, model=None) -> AgentResponse`**

Interactive chat with immediate response.

```python
response = client.chat(
    message="What are the issues?",
    context={"code": source_code},    # Optional
    model="claude-3-sonnet"            # Optional
)
print(response.content)
print(f"Tokens used: {response.usage}")
```

**`get_task(task_id) -> TaskResult`**

Retrieve task result by ID.

```python
result = client.get_task("task-123")
```

**`cancel_task(task_id) -> bool`**

Cancel a running task.

```python
if client.cancel_task("task-123"):
    print("Task cancelled")
```

**`workflow_run(template, params=None, wait=False, timeout_seconds=300) -> TaskResult`**

Execute a workflow template.

```python
result = client.workflow_run(
    template="code-review",
    params={"repo": "https://github.com/example/project"},
    wait=True,  # Wait for completion
    timeout_seconds=600
)
```

### AsyncXAgent (Asynchronous Client)

All methods are identical to `XAgent` but must be called with `await`:

```python
async with AsyncXAgent() as client:
    status = await client.health()
    task = await client.submit_task("...")
    result = await task.wait()
    response = await client.chat("...")
```

### TaskHandle / AsyncTaskHandle

Task handles provide polling and state tracking.

**Properties:**

- `task_id: str` — Unique task identifier
- `is_done: bool` — Whether task is complete

**Methods:**

- `poll() -> TaskResult` — Get current status
- `wait(timeout=300, poll_interval=5) -> TaskResult` — Block until completion
- `cancel() -> bool` — Cancel the task
- `result(timeout=None) -> TaskResult` — Get result (alias for wait)

## Models

### TaskResult

Task execution result with status and output.

```python
result: TaskResult
result.task_id        # str: Task identifier
result.status         # TaskStatus: COMPLETED, FAILED, CANCELLED, TIMEOUT
result.result         # Any: Output from task
result.pr_url         # Optional[str]: Generated pull request URL
result.diff           # Optional[str]: Code diff if applicable
result.logs           # Optional[str]: Execution logs
result.error          # Optional[str]: Error message
result.duration_ms    # int: Execution time
result.created_at     # datetime: Creation timestamp
result.completed_at   # Optional[datetime]: Completion timestamp
```

### AgentResponse

Response from chat or analysis.

```python
response: AgentResponse
response.content      # str: Response text
response.model        # str: Model used
response.usage        # Dict[str, int]: {"input_tokens": N, "output_tokens": M}
response.metadata     # Optional[Dict]: Additional metadata
```

### HealthStatus

Server health information.

```python
status: HealthStatus
status.status         # ComponentStatus: healthy, degraded, unhealthy
status.version        # str: Server version
status.components     # Dict[str, ComponentStatus]: Component statuses
status.integrations   # Dict[str, bool]: Available integrations
```

## Exception Handling

The SDK defines specific exception types for proper error handling:

```python
from xagent_sdk.exceptions import (
    XAgentError,                  # Base exception
    AuthenticationError,          # 401 — Invalid/missing API key
    AuthorizationError,           # 403 — Insufficient permissions
    ValidationError,              # 400 — Invalid parameters
    TaskTimeoutError,             # Task did not complete in time
    TaskNotFoundError,            # Task does not exist
    TaskCancelledError,           # Task was cancelled
    ServerError,                  # 5xx — Server error
    ServiceUnavailableError,      # 503 — Service unavailable
    RateLimitError,               # 429 — Rate limit exceeded
    ConnectionError,              # Connection failed
    TimeoutError,                 # Request timeout
)

try:
    result = task.wait(timeout=300)
except TaskTimeoutError:
    print("Task did not complete in 5 minutes")
    task.cancel()
except TaskNotFoundError:
    print("Task no longer exists")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except ServerError as e:
    print(f"Server error ({e.status_code}): {e.message}")
```

## Advanced Usage

### Custom Polling

```python
task = client.submit_task("Do something")

# Manual polling with custom intervals
start = time.time()
while time.time() - start < 300:
    result = task.poll()
    if result.status == TaskStatus.COMPLETED:
        print(f"Done! Result: {result.result}")
        break
    elif result.status == TaskStatus.FAILED:
        print(f"Failed: {result.error}")
        break
    print(f"Still running... (progress: {task.poll().progress}%)")
    time.sleep(10)
```

### Concurrent Tasks

```python
import asyncio
from xagent_sdk import AsyncXAgent

async def process_repo(client, repo_url):
    task = await client.submit_task(
        f"Analyze {repo_url}",
        repo=repo_url
    )
    return await task.wait(timeout=600)

async def main():
    async with AsyncXAgent() as client:
        repos = [
            "https://github.com/example/project1",
            "https://github.com/example/project2",
            "https://github.com/example/project3",
        ]
        
        # Run all in parallel
        results = await asyncio.gather(
            *[process_repo(client, repo) for repo in repos]
        )
        
        for i, result in enumerate(results):
            print(f"Repo {i+1}: {result.status}")
```

### Error Recovery with Retry Logic

```python
import asyncio
from xagent_sdk.exceptions import RateLimitError, ServiceUnavailableError

async def submit_task_with_retry(client, description, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await client.submit_task(description)
        except RateLimitError as e:
            wait_time = e.retry_after * (2 ** attempt)
            print(f"Rate limited. Waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
        except ServiceUnavailableError:
            if attempt < max_retries - 1:
                wait_time = 5 * (2 ** attempt)
                print(f"Service unavailable. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                raise
```

## Configuration

### Environment Variables

```bash
XAGENT_BASE_URL=http://localhost:8000    # Server URL
XAGENT_API_KEY=your-api-key              # API key
XAGENT_TIMEOUT=30                        # Request timeout
```

### Client Configuration

```python
import os

base_url = os.getenv("XAGENT_BASE_URL", "http://localhost:8000")
api_key = os.getenv("XAGENT_API_KEY")
timeout = float(os.getenv("XAGENT_TIMEOUT", 30))

client = XAgent(
    base_url=base_url,
    api_key=api_key,
    timeout=timeout
)
```

## Testing

Run the test suite:

```bash
pytest tests/test_client.py -v
```

With coverage:

```bash
pytest tests/test_client.py --cov=xagent_sdk --cov-report=html
```

The SDK uses `respx` for mocking HTTP requests in tests.

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass: `pytest`
2. Code is formatted: `black xagent_sdk/`
3. Imports are sorted: `isort xagent_sdk/`
4. Types are checked: `mypy xagent_sdk/`

## License

MIT License — see LICENSE file for details.

## Support

- **Documentation**: https://x-agent.readthedocs.io/sdk
- **Issues**: https://github.com/X-Agent/sdk/issues
- **Discussions**: https://github.com/X-Agent/discussions

## Changelog

### 0.1.0 (2024-XX-XX)

- Initial release
- Synchronous and asynchronous clients
- Task submission and polling
- Interactive chat
- Workflow execution
- Comprehensive error handling
- Full type annotations
