/**
 * Core types for X-Agent SDK
 */

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  timestamp: string;
  uptime_seconds: number;
  components?: Record<string, ComponentHealth>;
}

export interface ComponentHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency_ms?: number;
  error?: string;
}

export interface TaskOptions {
  priority?: 'low' | 'normal' | 'high';
  timeout_seconds?: number;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export interface Task {
  id: string;
  description: string;
  status: TaskStatus;
  priority: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
  result?: TaskResult;
}

export enum TaskStatus {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export interface TaskResult {
  status: 'success' | 'failure';
  output: string;
  pr_url?: string;
  branch?: string;
  changes_count?: number;
  execution_time_ms: number;
  error?: string;
}

export interface AgentResponse {
  message: string;
  task_id?: string;
  tool_calls?: ToolCall[];
  reasoning?: string;
  confidence: number;
}

export interface ToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  execution_time_ms: number;
  result?: string;
  error?: string;
}

export interface Tool {
  name: string;
  description: string;
  parameters: Record<string, ParameterSchema>;
  required?: string[];
  category?: string;
  mcp_server?: string;
}

export interface ParameterSchema {
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  description?: string;
  default?: unknown;
  enum?: unknown[];
  items?: ParameterSchema;
  properties?: Record<string, ParameterSchema>;
}

export interface ExecutionConfig {
  mcp_servers?: MCPServerConfig[];
  timeout_ms?: number;
  max_retries?: number;
  enable_observability?: boolean;
  observability_endpoint?: string;
}

export interface MCPServerConfig {
  name: string;
  command: string;
  args?: string[];
  env?: Record<string, string>;
  timeout_ms?: number;
}

export interface ListToolsOptions {
  category?: string;
  mcp_server?: string;
  limit?: number;
  offset?: number;
}

export interface PagedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}
