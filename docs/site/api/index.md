# X-Agent REST API

The X-Agent REST API provides full programmatic access to create, manage, and monitor autonomous agents. All requests require authentication via API key or OAuth2.

## Base URL

```
https://api.xagent.dev/v1
```

## Authentication

### API Key Authentication
Include your API key in the request header:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.xagent.dev/v1/agents
```

### OAuth2
For server-to-server integrations:

```bash
curl -X POST https://api.xagent.dev/v1/oauth/token \
  -d "grant_type=client_credentials&client_id=...&client_secret=..."
```

[Learn more about authentication →](/api/authentication)

## Rate Limiting

- **Free tier**: 100 requests/minute
- **Pro tier**: 1,000 requests/minute
- **Enterprise**: Custom limits

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640000000
```

[Learn more about rate limiting →](/api/rate-limiting)

## Error Format

All errors follow a consistent format:

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "Required parameter 'name' is missing",
    "details": {
      "parameter": "name"
    }
  }
}
```

HTTP Status Codes:
- `200 OK` - Request succeeded
- `201 Created` - Resource created
- `400 Bad Request` - Invalid parameters
- `401 Unauthorized` - Missing or invalid credentials
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

[Learn more about error handling →](/api/errors)

## Core Resources

### Agents
Create and manage autonomous agents. Each agent runs your custom logic using specified LLM models and tools.

```bash
# Create an agent
curl -X POST https://api.xagent.dev/v1/agents \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "support-agent",
    "model": "gpt-4o-mini",
    "system_prompt": "You are a helpful support agent...",
    "tools": ["web_search", "send_email"]
  }'

# List agents
curl https://api.xagent.dev/v1/agents \
  -H "Authorization: Bearer YOUR_API_KEY"

# Get agent details
curl https://api.xagent.dev/v1/agents/agent-123 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

[Full agents documentation →](/api/agents)

### Runs
Execute agents and track their progress. Each run captures the agent's reasoning, tool calls, and final output.

```bash
# Execute an agent
curl -X POST https://api.xagent.dev/v1/agents/agent-123/runs \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Help me with my account",
    "max_steps": 10
  }'

# Stream run output
curl https://api.xagent.dev/v1/agents/agent-123/runs/run-456/stream \
  -H "Authorization: Bearer YOUR_API_KEY"
```

[Full runs documentation →](/api/runs)

### Workflows
Orchestrate multiple agents in complex workflows. Define sequential, parallel, and conditional execution patterns.

```bash
# Create a workflow
curl -X POST https://api.xagent.dev/v1/workflows \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "code-review",
    "definition": "..."
  }'
```

[Full workflows documentation →](/api/workflows)

### Tools
Integrated external capabilities. Use pre-built tools or create custom integrations.

```bash
# List available tools
curl https://api.xagent.dev/v1/tools \
  -H "Authorization: Bearer YOUR_API_KEY"

# Create custom tool
curl -X POST https://api.xagent.dev/v1/tools \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "name": "my-api",
    "type": "webhook",
    "config": {...}
  }'
```

[Full tools documentation →](/api/tools)

## Advanced Features

### Streaming
Get real-time updates as agents execute:

```bash
curl https://api.xagent.dev/v1/agents/agent-123/runs/run-456/stream \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Accept: text/event-stream"
```

[Learn about streaming →](/api/streaming)

### Webhooks
Receive notifications when agents complete runs:

```bash
curl -X POST https://api.xagent.dev/v1/webhooks \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "url": "https://example.com/webhook",
    "events": ["run.completed", "run.failed"]
  }'
```

[Learn about webhooks →](/api/webhooks)

### Batch Operations
Process multiple requests efficiently:

```bash
curl -X POST https://api.xagent.dev/v1/batch \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "requests": [...]
  }'
```

[Learn about batch operations →](/api/batch)

## SDK Libraries

- **[Python SDK](/sdk/python)** - Full-featured Python client
- **[TypeScript SDK](/sdk/typescript)** - For Node.js and browsers
- **[REST Client](/sdk/rest)** - HTTP client for any language

## OpenAPI Specification

The complete API specification is available in OpenAPI 3.0 format:

```bash
curl https://api.xagent.dev/openapi.json
```

Or download the [Postman collection](/X-Agent.postman_collection.json).

## Common Patterns

### Create and Execute an Agent

```bash
# 1. Create agent
AGENT=$(curl -X POST https://api.xagent.dev/v1/agents \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "assistant", "model": "gpt-4o-mini"}' \
  | jq -r '.id')

# 2. Execute agent
RUN=$(curl -X POST https://api.xagent.dev/v1/agents/$AGENT/runs \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "Your task here"}' \
  | jq -r '.id')

# 3. Get run result
curl https://api.xagent.dev/v1/runs/$RUN \
  -H "Authorization: Bearer YOUR_API_KEY" \
  | jq '.output'
```

### Handle Errors

```bash
curl https://api.xagent.dev/v1/agents/invalid-id \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -w "\nHTTP Status: %{http_code}\n"
```

Response:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Agent 'invalid-id' not found"
  }
}
```

## Need Help?

- **[API Examples](/api/examples)** - Code samples for common tasks
- **[Integration Guides](/api/integrations)** - Connect with your tools
- **[CLI Reference](/api/cli)** - Command-line usage
- **[Discord Support](https://discord.gg/xagent)** - Get help from the community
