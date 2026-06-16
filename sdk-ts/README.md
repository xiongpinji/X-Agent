# X-Agent TypeScript SDK

Official TypeScript/Node.js SDK for X-Agent enterprise autonomous agent framework.

## Features

- Full TypeScript support with comprehensive type definitions
- Async/await API for all operations
- Automatic error handling and retry logic
- Task polling with exponential backoff
- MCP protocol integration
- Production-ready with comprehensive error types

## Installation

```bash
npm install @xagent/sdk
# or
yarn add @xagent/sdk
```

## Quick Start

```typescript
import { XAgent } from '@xagent/sdk';

const agent = new XAgent({
  baseUrl: 'http://localhost:8000',
  apiKey: 'your-api-key',
  timeout: 30000,
});

// Check server health
const health = await agent.health();
console.log(`Server status: ${health.status}`);

// Submit a task
const task = await agent.submitTask('Fix the login bug', {
  priority: 'high',
  timeout_seconds: 300,
});

// Wait for completion
const result = await task.wait();
console.log(`Task completed: ${result.pr_url}`);

// Or chat with the agent
const response = await agent.chat('What are the available tools?');
console.log(response.message);
```

## API Reference

### XAgent Constructor

```typescript
new XAgent(config: XAgentConfig)
```

**Options:**
- `baseUrl` (string): X-Agent server URL
- `apiKey` (string): API key for authentication
- `timeout` (number, optional): Request timeout in ms (default: 30000)

### Methods

#### `health(): Promise<HealthStatus>`
Check X-Agent server health status.

#### `submitTask(description: string, options?: TaskOptions): Promise<XAgentTask>`
Submit a new task for execution.

**TaskOptions:**
- `priority`: 'low' | 'normal' | 'high'
- `timeout_seconds`: Max execution time
- `tags`: Array of task tags
- `metadata`: Custom metadata object

#### `getTask(taskId: string): Promise<Task>`
Get task status by ID.

#### `listTasks(limit?: number, offset?: number): Promise<PagedResponse<Task>>`
List all tasks with pagination.

#### `cancelTask(taskId: string): Promise<void>`
Cancel a running task.

#### `chat(message: string, conversationId?: string): Promise<AgentResponse>`
Send a message to the agent.

#### `listTools(options?: ListToolsOptions): Promise<PagedResponse<Tool>>`
List available tools.

**ListToolsOptions:**
- `category`: Filter by tool category
- `mcp_server`: Filter by MCP server
- `limit`: Results per page (default: 50)
- `offset`: Pagination offset (default: 0)

#### `getTool(toolName: string): Promise<Tool>`
Get tool details by name.

#### `getConfig(): Promise<ExecutionConfig>`
Get current execution configuration.

#### `updateConfig(config: Partial<ExecutionConfig>): Promise<ExecutionConfig>`
Update execution configuration.

### XAgentTask Methods

#### `wait(timeoutMs?: number): Promise<TaskResult>`
Poll for task completion with exponential backoff.

#### `refresh(): Promise<void>`
Refresh task state without waiting.

#### `isTerminal(): boolean`
Check if task is in terminal state.

#### `isSuccess(): boolean`
Check if task completed successfully.

#### `getPRUrl(): string | undefined`
Get pull request URL if available.

## Error Handling

```typescript
import {
  AuthenticationError,
  AuthorizationError,
  NotFoundError,
  ValidationError,
  TimeoutError,
  RateLimitError,
  ServerError,
  XAgentError,
} from '@xagent/sdk';

try {
  const task = await agent.submitTask('Fix bug');
  const result = await task.wait(60000);
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('Invalid API key');
  } else if (error instanceof ValidationError) {
    console.error('Validation failed:', error.details);
  } else if (error instanceof TimeoutError) {
    console.error('Task timeout exceeded');
  } else if (error instanceof RateLimitError) {
    console.error('Rate limited, retry after:', error.retryAfter);
  } else if (error instanceof XAgentError) {
    console.error(`Error (${error.code}):`, error.message);
  }
}
```

## Advanced Usage

### Custom Polling Intervals

```typescript
const task = await agent.submitTask('Long-running task');
// Poll every 5 seconds, max 2 hours
const result = await task.wait(7200000);
```

### Tool Discovery

```typescript
// List all tools
const allTools = await agent.listTools();
console.log(`Found ${allTools.total} tools`);

// Filter by category
const browserTools = await agent.listTools({ category: 'browser' });

// Get specific tool details
const tool = await getTool('github_create_pr');
console.log(tool.parameters);
```

### Configuration Management

```typescript
// Get current configuration
const config = await agent.getConfig();

// Update MCP servers
await agent.updateConfig({
  mcp_servers: [
    {
      name: 'github',
      command: 'python',
      args: ['-m', 'mcp.server.github'],
    },
  ],
  timeout_ms: 60000,
});
```

## Batch Operations

```typescript
// Submit multiple tasks
const tasks = await Promise.all([
  agent.submitTask('Fix bug 1'),
  agent.submitTask('Fix bug 2'),
  agent.submitTask('Fix bug 3'),
]);

// Wait for all to complete
const results = await Promise.all(
  tasks.map((task) => task.wait())
);
```

## TypeScript Configuration

The SDK includes full TypeScript support. Add to your `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "lib": ["ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "moduleResolution": "node"
  }
}
```

## Requirements

- Node.js 18+
- TypeScript 5.0+ (for development)

## Development

```bash
# Build
npm run build

# Test
npm run test

# Lint
npm run lint

# Format
npm run format
```

## License

MIT

## Contributing

Contributions welcome. Please open an issue or pull request.

## Support

- Documentation: https://x-agent.dev/docs
- Issues: https://github.com/x-agent/sdk-ts/issues
- Community: https://discord.gg/x-agent
