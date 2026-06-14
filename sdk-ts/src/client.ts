/**
 * X-Agent SDK client
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  XAgentConfig,
  HealthStatus,
  Task,
  TaskOptions,
  TaskResult,
  AgentResponse,
  Tool,
  ListToolsOptions,
  PagedResponse,
  ExecutionConfig,
} from './types';
import {
  XAgentError,
  AuthenticationError,
  AuthorizationError,
  NotFoundError,
  ValidationError,
  TimeoutError,
  RateLimitError,
  ServerError,
} from './errors';
import { XAgentTask } from './task';

export class XAgent {
  private client: AxiosInstance;
  private baseUrl: string;
  private apiKey: string;
  private timeout: number;

  constructor(config: XAgentConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, ''); // Remove trailing slash
    this.apiKey = config.apiKey;
    this.timeout = config.timeout || 30000;

    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: this.timeout,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'User-Agent': '@xagent/sdk/1.0.0',
      },
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error) => this.handleError(error),
    );
  }

  /**
   * Check X-Agent server health
   */
  async health(): Promise<HealthStatus> {
    try {
      const response = await this.client.get<HealthStatus>('/health');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Submit a new task to X-Agent
   */
  async submitTask(description: string, options?: TaskOptions): Promise<XAgentTask> {
    try {
      const payload = {
        description,
        priority: options?.priority || 'normal',
        timeout_seconds: options?.timeout_seconds,
        tags: options?.tags,
        metadata: options?.metadata,
      };

      const response = await this.client.post<Task>('/api/v1/tasks', payload);
      const task = response.data;

      return new XAgentTask(task, (taskId) => this.getTask(taskId));
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Get task by ID
   */
  async getTask(taskId: string): Promise<Task> {
    try {
      const response = await this.client.get<Task>(`/api/v1/tasks/${taskId}`);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * List all tasks
   */
  async listTasks(
    limit: number = 50,
    offset: number = 0,
  ): Promise<PagedResponse<Task>> {
    try {
      const response = await this.client.get<PagedResponse<Task>>('/api/v1/tasks', {
        params: { limit, offset },
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Cancel a task
   */
  async cancelTask(taskId: string): Promise<void> {
    try {
      await this.client.post(`/api/v1/tasks/${taskId}/cancel`);
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Chat with the X-Agent
   */
  async chat(
    message: string,
    conversationId?: string,
  ): Promise<AgentResponse> {
    try {
      const payload = {
        message,
        conversation_id: conversationId,
      };

      const response = await this.client.post<AgentResponse>(
        '/api/v1/chat',
        payload,
      );
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * List available tools
   */
  async listTools(options?: ListToolsOptions): Promise<PagedResponse<Tool>> {
    try {
      const params: Record<string, unknown> = {
        limit: options?.limit || 50,
        offset: options?.offset || 0,
      };

      if (options?.category) {
        params.category = options.category;
      }
      if (options?.mcp_server) {
        params.mcp_server = options.mcp_server;
      }

      const response = await this.client.get<PagedResponse<Tool>>(
        '/api/v1/tools',
        { params },
      );
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Get tool details
   */
  async getTool(toolName: string): Promise<Tool> {
    try {
      const response = await this.client.get<Tool>(`/api/v1/tools/${toolName}`);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Get execution configuration
   */
  async getConfig(): Promise<ExecutionConfig> {
    try {
      const response = await this.client.get<ExecutionConfig>(
        '/api/v1/config',
      );
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Update execution configuration
   */
  async updateConfig(config: Partial<ExecutionConfig>): Promise<ExecutionConfig> {
    try {
      const response = await this.client.put<ExecutionConfig>(
        '/api/v1/config',
        config,
      );
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  private handleError(error: unknown): never {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const status = axiosError.response?.status;
      const data = axiosError.response?.data as Record<string, unknown>;

      switch (status) {
        case 401:
          throw new AuthenticationError(
            (data?.message as string) || 'Authentication failed',
          );
        case 403:
          throw new AuthorizationError(
            (data?.message as string) || 'Insufficient permissions',
          );
        case 404:
          throw new NotFoundError((data?.message as string) || 'Not found');
        case 422:
          throw new ValidationError(
            (data?.message as string) || 'Validation failed',
            data?.details as Record<string, string[]>,
          );
        case 429:
          throw new RateLimitError(
            (data?.message as string) || 'Rate limit exceeded',
            parseInt((data?.retry_after as string) || '60', 10),
          );
        case 408:
          throw new TimeoutError((data?.message as string) || 'Request timeout');
        case 500:
        case 502:
        case 503:
          throw new ServerError(
            (data?.message as string) || 'Server error',
          );
        default:
          throw new XAgentError(
            (data?.message as string) || error.message || 'Unknown error',
            'UNKNOWN_ERROR',
            status || 500,
          );
      }
    }

    if (error instanceof Error) {
      throw new XAgentError(error.message);
    }

    throw new XAgentError('Unknown error occurred');
  }
}
