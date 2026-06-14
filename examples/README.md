# X-Agent Integration Examples

This directory contains comprehensive examples of how to integrate with X-Agent from different programming languages and tools.

## Overview

X-Agent provides a REST API and webhooks for submitting tasks, monitoring progress, and retrieving results. Whether you're building a web application, backend service, or command-line tool, these examples show the best practices for each language.

## Quick Start

### Prerequisites

1. X-Agent running: `docker run -p 8000:8000 xagent:latest`
2. An API key (get from X-Agent dashboard or use default for local dev)
3. Language-specific tools installed

### Basic Pattern

All examples follow this pattern:

```
1. Initialize client with API key
2. Submit task (get task ID)
3. Poll/wait for completion
4. Retrieve and process results
```

## Language-Specific Guides

### Python

**File**: `python/basic.py`

**Installation**:
```bash
pip install xagent-sdk
```

**Quick Example**:
```python
from xagent_sdk import XAgent

agent = XAgent(base_url="http://localhost:8000", api_key="sk_your_key")
result = agent.submit_task("Analyze code quality").wait()
print(result.output)
```

**Features Demonstrated**:
- Basic task submission
- Streaming output
- Batch task processing
- Tool-specific execution
- Error handling with retries
- Task history retrieval

**Run Examples**:
```bash
python python/basic.py basic       # Basic submission
python python/basic.py streaming   # Stream output
python python/basic.py batch       # Batch tasks
python python/basic.py errors      # Error handling
python python/basic.py history     # Task history
```

### JavaScript / Node.js

**File**: `javascript/basic.mjs`

**Installation**:
```bash
npm install xagent-sdk
```

**Quick Example**:
```javascript
const { XAgent } = require('xagent-sdk');

const agent = new XAgent({
  baseUrl: "http://localhost:8000",
  apiKey: "sk_your_key"
});

const result = await agent.submitTask("Analyze code");
console.log(result.output);
```

**Browser Usage**:
```html
<script src="https://unpkg.com/xagent-sdk/dist/browser.js"></script>
<script>
  const agent = new XAgent({
    baseUrl: "http://localhost:8000",
    apiKey: "sk_your_key"
  });
</script>
```

**Features Demonstrated**:
- Basic task submission
- Streaming with async iterators
- Batch task processing
- WebSocket streaming (browser)
- Error handling
- Task history

**Run Examples**:
```bash
node javascript/basic.mjs basic      # Basic submission
node javascript/basic.mjs streaming  # Stream output
node javascript/basic.mjs batch      # Batch tasks
node javascript/basic.mjs errors     # Error handling
```

### cURL / Bash

**File**: `curl/basic.sh`

**Prerequisites**: `curl`, `jq` (optional, for JSON parsing)

**Quick Example**:
```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_your_key" \
  -d '{"prompt": "Analyze code"}'
```

**Features Demonstrated**:
- Direct HTTP API calls
- Task submission and polling
- Batch task handling
- API key management
- Webhook configuration
- System health checks

**Run Examples**:
```bash
bash curl/basic.sh basic       # Basic submission
bash curl/basic.sh batch       # Batch tasks
bash curl/basic.sh history     # Task history
bash curl/basic.sh keys        # Manage API keys
bash curl/basic.sh webhooks    # Manage webhooks
bash curl/basic.sh health      # System health
```

### Go

**File**: `go/main.go`

**Installation**:
```bash
go get github.com/xagent/sdk-go
```

**Quick Example**:
```go
package main

import "github.com/xagent/sdk-go"

func main() {
    client := sdk.NewClient("http://localhost:8000", "sk_your_key")
    run, _ := client.SubmitTask(context.Background(), "Analyze code")
    result, _ := run.Wait(context.Background(), 5*time.Minute)
    println(result.Output)
}
```

**Features Demonstrated**:
- Basic task submission
- Polling task status
- Batch task handling
- Task history
- Error handling with retries
- Signal handling (graceful shutdown)
- Context-based cancellation

**Run Examples**:
```bash
go run go/main.go -example basic     # Basic submission
go run go/main.go -example polling   # Poll status
go run go/main.go -example batch     # Batch tasks
go run go/main.go -example errors    # Error handling
go run go/main.go -example signals   # Signal handling
go run go/main.go -example all       # All examples
```

## Common Tasks

### Submit a Simple Task

**Python**:
```python
agent = XAgent("http://localhost:8000", "sk_xxx")
result = agent.submit_task("Fix the bug").wait()
```

**JavaScript**:
```javascript
const agent = new XAgent({baseUrl: "http://localhost:8000", apiKey: "sk_xxx"});
const result = await agent.submitTask("Fix the bug");
```

**cURL**:
```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "X-API-Key: sk_xxx" \
  -d '{"prompt": "Fix the bug"}'
```

**Go**:
```go
run, _ := client.SubmitTask(ctx, "Fix the bug")
result, _ := run.Wait(ctx, 5*time.Minute)
```

### Stream Long-Running Tasks

**Python**:
```python
for update in agent.submit_task_stream("Generate docs"):
    if update.event == "output":
        print(update.data, end="", flush=True)
```

**JavaScript**:
```javascript
for await (const update of agent.submitTaskStream("Generate docs")) {
    if (update.event === "output") {
        process.stdout.write(update.data);
    }
}
```

**cURL**:
```bash
bash curl/basic.sh stream
```

### Handle Multiple Tasks

**Python**:
```python
tasks = ["Task 1", "Task 2", "Task 3"]
runs = [agent.submit_task(t) for t in tasks]
results = agent.wait_for_all(runs)
```

**JavaScript**:
```javascript
const tasks = ["Task 1", "Task 2", "Task 3"];
const runs = await Promise.all(tasks.map(t => agent.submitTask(t)));
```

**Go**:
```go
for _, task := range tasks {
    run, _ := client.SubmitTask(ctx, task)
    runs = append(runs, run)
}
```

### Implement Retry Logic

**Python**:
```python
try:
    result = agent.submit_task(prompt).wait(timeout=60)
except TimeoutError:
    result = agent.submit_task(prompt).wait(timeout=120)
```

**JavaScript**:
```javascript
try {
    return await run.wait({timeout: 60000});
} catch (e) {
    if (e.code === 'TIMEOUT') {
        return await run.wait({timeout: 120000});
    }
}
```

**Go**:
```go
result, _ := run.Wait(ctx, 1*time.Minute)
if ctx.Err() == context.DeadlineExceeded {
    result, _ = run.Wait(ctx, 2*time.Minute)
}
```

## API Reference

### Endpoints

All examples use these core endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/agent/run` | Submit new task |
| GET | `/api/v1/agent/run/{id}` | Get task status |
| GET | `/api/v1/agent/runs` | List tasks |
| POST | `/api/v1/agent/run/{id}/cancel` | Cancel task |
| POST | `/api/v1/webhooks` | Create webhook |
| GET | `/api/v1/health` | Health check |

### Authentication

All requests require the `X-API-Key` header:

```bash
curl -H "X-API-Key: sk_your_api_key_here" http://localhost:8000/api/v1/health
```

Or with Python SDK:
```python
agent = XAgent(api_key="sk_your_api_key_here")
```

### Task Status Values

- `pending` - Task submitted, waiting to start
- `running` - Task actively executing
- `completed` - Task finished successfully
- `failed` - Task encountered an error
- `cancelled` - Task was cancelled

## Best Practices

### 1. Always Set Timeouts

```python
# Good - prevents hanging forever
result = run.wait(timeout=300)

# Risky - could wait indefinitely
result = run.wait()
```

### 2. Implement Retry Logic

```python
@retry(max_attempts=3, backoff_factor=2)
def submit_task(prompt):
    return agent.submit_task(prompt).wait()
```

### 3. Stream Large Results

```python
# Good - stream output as it arrives
for update in agent.submit_task_stream(prompt):
    print(update.data, end="", flush=True)

# Risky - loads entire response in memory
result = agent.submit_task(prompt).wait()
print(result.output)
```

### 4. Handle Rate Limiting

```python
try:
    result = agent.submit_task(prompt)
except RateLimitError as e:
    time.sleep(e.retry_after)
    result = agent.submit_task(prompt)
```

### 5. Use Webhooks for Notifications

```bash
# Create outgoing webhook
curl -X POST http://localhost:8000/api/v1/webhooks \
  -H "X-API-Key: sk_xxx" \
  -d '{
    "url": "https://your-api.com/webhook",
    "events": ["xagent.run.completed"],
    "direction": "outgoing"
  }'
```

### 6. Monitor Rate Limits

```python
response = agent.submit_task(prompt)
print(f"Rate limit remaining: {response.headers.get('X-RateLimit-Remaining')}")
```

## Deployment

### Docker Compose

Include X-Agent in your stack:

```yaml
version: '3.9'
services:
  xagent-api:
    image: xagent:latest
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:pass@db/xagent
      
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deployment/nginx/nginx.conf:/etc/nginx/nginx.conf
```

### Kubernetes

```bash
kubectl apply -f deployment/k8s/
kubectl port-forward svc/xagent-api 8000:8000
```

## Troubleshooting

### Connection Refused

```
Error: Connection refused
```

**Solution**: Ensure X-Agent is running:
```bash
docker run -p 8000:8000 xagent:latest
```

### Authentication Failed

```
Error: 401 Unauthorized
```

**Solution**: Check your API key:
```bash
export XAGENT_API_KEY="sk_your_actual_key"
```

### Timeout

```
Error: Request timeout
```

**Solution**: Increase timeout for long tasks:
```python
result = run.wait(timeout=600)  # 10 minutes
```

### Task Cancelled

```
Error: Task was cancelled
```

**Solution**: Check server logs and retry:
```python
result = agent.submit_task(prompt).wait()
```

## Additional Resources

- [X-Agent Documentation](https://docs.xagent.ai)
- [API Reference](https://docs.xagent.ai/api)
- [Webhook Guide](https://docs.xagent.ai/webhooks)
- [GitHub Repository](https://github.com/xagent/xagent)
- [Community Slack](https://slack.xagent.ai)

## Contributing

Have a better example? Submit a PR!

1. Fork the repository
2. Create a feature branch
3. Add your example with comprehensive documentation
4. Test thoroughly
5. Submit pull request

## License

MIT License - see LICENSE file in project root
