# X-Agent SDK

Official client libraries for X-Agent REST API. Available for Python, TypeScript, and as a generic HTTP client.

## Available SDKs

### Python SDK
Full-featured async Python client with type hints.

```bash
pip install xagent-framework
```

```python
from xagent import XAgent

client = XAgent(api_key="YOUR_API_KEY")

# Create and execute an agent
agent = await client.agents.create(
    name="assistant",
    model="gpt-4o-mini",
    system_prompt="You are a helpful assistant"
)

run = await client.agents.run(agent.id, input="Help me with X")
print(run.output)
```

[Python SDK Documentation](/sdk/python)

### TypeScript SDK
Type-safe SDK for Node.js and modern browsers.

```bash
npm install xagent-sdk
```

```typescript
import { XAgent } from 'xagent-sdk';

const client = new XAgent({ apiKey: 'YOUR_API_KEY' });

// Create and execute an agent
const agent = await client.agents.create({
  name: 'assistant',
  model: 'gpt-4o-mini',
  systemPrompt: 'You are a helpful assistant'
});

const run = await client.agents.run(agent.id, { input: 'Help me with X' });
console.log(run.output);
```

[TypeScript SDK Documentation](/sdk/typescript)

### REST Client
Use X-Agent API directly with any HTTP client:

```bash
curl https://api.xagent.dev/v1/agents \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json"
```

[REST API Documentation](/api/)

## Features

All SDKs provide:

- **Type Safety**: Full type hints and IDE autocomplete
- **Async Support**: Non-blocking, efficient I/O
- **Error Handling**: Consistent error types and messages
- **Retries**: Automatic retry with exponential backoff
- **Streaming**: Real-time agent output streaming
- **Timeout**: Configurable request timeouts
- **Logging**: Detailed debug logging

## Installation

### Python

```bash
# Basic installation
pip install xagent-framework

# With extras
pip install "xagent-framework[postgres,langfuse]"

# Development
pip install -e ".[dev]"
```

**Requirements**: Python 3.11+

### TypeScript

```bash
npm install xagent-sdk

# or with Yarn
yarn add xagent-sdk

# or with pnpm
pnpm add xagent-sdk
```

**Requirements**: Node.js 18+, TypeScript 5+ (for TypeScript projects)

## Configuration

### Python

```python
from xagent import XAgent

client = XAgent(
    api_key="YOUR_API_KEY",
    base_url="https://api.xagent.dev/v1",  # Optional
    timeout=30,  # Request timeout in seconds
    max_retries=3,
    debug=False,  # Enable debug logging
)
```

### TypeScript

```typescript
import { XAgent } from 'xagent-sdk';

const client = new XAgent({
  apiKey: 'YOUR_API_KEY',
  baseUrl: 'https://api.xagent.dev/v1',  // Optional
  timeout: 30000,  // Request timeout in ms
  maxRetries: 3,
});
```

## Common Tasks

### Create an Agent

```python
# Python
agent = await client.agents.create(
    name="code-reviewer",
    model="gpt-4o",
    system_prompt="You are an expert code reviewer",
    tools=["github_api", "code_parser"]
)
```

```typescript
// TypeScript
const agent = await client.agents.create({
  name: 'code-reviewer',
  model: 'gpt-4o',
  systemPrompt: 'You are an expert code reviewer',
  tools: ['github_api', 'code_parser']
});
```

### Execute an Agent

```python
# Python
run = await client.agents.run(
    agent_id="agent-123",
    input="Review this PR: https://github.com/...",
    max_steps=10
)
print(run.output)
```

```typescript
// TypeScript
const run = await client.agents.run('agent-123', {
  input: 'Review this PR: https://github.com/...',
  maxSteps: 10
});
console.log(run.output);
```

### Stream Agent Output

```python
# Python
async for event in client.agents.stream(
    agent_id="agent-123",
    input="Your task"
):
    if event.type == "thought":
        print(f"Thinking: {event.content}")
    elif event.type == "tool_call":
        print(f"Calling: {event.tool_name}")
    elif event.type == "result":
        print(f"Result: {event.content}")
```

```typescript
// TypeScript
for await (const event of client.agents.stream('agent-123', {
  input: 'Your task'
})) {
  if (event.type === 'thought') {
    console.log(`Thinking: ${event.content}`);
  } else if (event.type === 'tool_call') {
    console.log(`Calling: ${event.toolName}`);
  } else if (event.type === 'result') {
    console.log(`Result: ${event.content}`);
  }
}
```

### List Agents

```python
# Python
agents = await client.agents.list()
for agent in agents:
    print(f"{agent.name} ({agent.id})")
```

```typescript
// TypeScript
const agents = await client.agents.list();
for (const agent of agents) {
  console.log(`${agent.name} (${agent.id})`);
}
```

## Error Handling

### Python

```python
from xagent import XAgent
from xagent.errors import XAgentError, NotFoundError, RateLimitError

try:
    agent = await client.agents.get("invalid-id")
except NotFoundError:
    print("Agent not found")
except RateLimitError:
    print("Rate limited, retry after 60 seconds")
except XAgentError as e:
    print(f"Error: {e.code} - {e.message}")
```

### TypeScript

```typescript
import { XAgent } from 'xagent-sdk';
import { XAgentError, NotFoundError, RateLimitError } from 'xagent-sdk/errors';

try {
  const agent = await client.agents.get('invalid-id');
} catch (error) {
  if (error instanceof NotFoundError) {
    console.log('Agent not found');
  } else if (error instanceof RateLimitError) {
    console.log('Rate limited, retry after 60 seconds');
  } else if (error instanceof XAgentError) {
    console.log(`Error: ${error.code} - ${error.message}`);
  }
}
```

## Advanced Usage

### Custom Middleware

```python
# Python
from xagent.middleware import Middleware

class LoggingMiddleware(Middleware):
    async def before_request(self, request):
        print(f"→ {request.method} {request.url}")
    
    async def after_response(self, response):
        print(f"← {response.status_code}")

client = XAgent(api_key="...", middlewares=[LoggingMiddleware()])
```

### Batch Operations

```python
# Python
results = await client.batch([
    client.agents.run("agent-1", input="Task 1"),
    client.agents.run("agent-2", input="Task 2"),
    client.agents.run("agent-3", input="Task 3"),
])
```

## Debugging

### Enable Debug Logging

```python
# Python
import logging
logging.basicConfig(level=logging.DEBUG)
client = XAgent(api_key="...", debug=True)
```

```typescript
// TypeScript (set env var)
export DEBUG=xagent:*
```

## Performance Tips

- **Reuse client**: Create one client instance and reuse it
- **Connection pooling**: SDK automatically pools connections
- **Batch operations**: Group multiple requests when possible
- **Streaming**: Use streaming for long-running operations
- **Caching**: Cache agent definitions, don't recreate them

## Limits

- **Request size**: 1MB per request
- **Timeout**: 30 seconds (configurable)
- **Rate limit**: See your API plan
- **Stream timeout**: 5 minutes
- **Batch size**: 100 requests per batch

## Support

- **[Python API Reference](/sdk/python)** - Full Python API docs
- **[TypeScript API Reference](/sdk/typescript)** - Full TypeScript API docs
- **[GitHub Issues](https://github.com/xiongpinji/X-Agent/issues)** - Report bugs
- **[Discord](https://discord.gg/xagent)** - Community support
