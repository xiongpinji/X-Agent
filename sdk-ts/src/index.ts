/**
 * X-Agent TypeScript SDK - Main entry point
 */

export { XAgent } from './client';
export { XAgentTask } from './task';
export {
  HealthStatus,
  ComponentHealth,
  TaskOptions,
  Task,
  TaskStatus,
  TaskResult,
  AgentResponse,
  ToolCall,
  Tool,
  ParameterSchema,
  ExecutionConfig,
  MCPServerConfig,
  ListToolsOptions,
  PagedResponse,
} from './types';
export {
  XAgentError,
  AuthenticationError,
  AuthorizationError,
  NotFoundError,
  ValidationError,
  TimeoutError,
  RateLimitError,
  ServerError,
  MCPError,
} from './errors';

// Version
export const VERSION = '1.0.0';
