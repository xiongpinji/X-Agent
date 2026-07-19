/**
 * API Client Service
 *
 * Provides typed HTTP client for communicating with X-Agent backend API.
 * Handles authentication, error handling, and request/response serialization.
 */

export interface AgentRun {
  run_id: string;
  task: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  result?: any;
  error?: string;
}

export interface Task {
  task_id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  priority: 'low' | 'medium' | 'high' | 'critical';
  progress: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  estimated_duration_seconds?: number;
  depends_on: string[];
  blocks: string[];
  tags: string[];
  metadata: Record<string, any>;
  result?: any;
  error?: string;
  run_id?: string;
  parent_task_id?: string;
}

export interface Question {
  question_id: string;
  run_id: string;
  type: 'single_choice' | 'multiple_choice' | 'text_input' | 'confirmation' | 'file_selection' | 'code_review';
  title: string;
  description: string;
  context: Record<string, any>;
  options: Array<{ value: string; label: string; description?: string }>;
  allow_multiple: boolean;
  placeholder: string;
  validation_pattern?: string;
  min_length?: number;
  max_length?: number;
  created_at: string;
  timeout_seconds?: number;
  expires_at?: string;
  status: 'pending' | 'answered' | 'timeout' | 'cancelled';
  answer?: any;
  answered_at?: string;
  priority: string;
  blocking: boolean;
  default_answer?: any;
  tags: string[];
}

export interface FileMetadata {
  path: string;
  name: string;
  size: number;
  mime_type: string;
  created_at?: string;
  modified_at?: string;
  is_directory: boolean;
  is_readable: boolean;
  is_writable: boolean;
}

export interface FilePreviewData {
  path: string;
  name: string;
  mime_type: string;
  size: number;
  preview_type: 'text' | 'code' | 'image' | 'pdf' | 'binary';
  content?: string;
  language?: string;
  lines?: number;
  truncated: boolean;
  max_lines: number;
}

export interface Mount {
  mount_id: string;
  mount_path: string;
  host_path: string;
  mode: 'ro' | 'rw';
  created_at: string;
}

export interface APIClientConfig {
  baseURL?: string;
  timeout?: number;
  headers?: Record<string, string>;
}

export class APIClient {
  private baseURL: string;
  private timeout: number;
  private headers: Record<string, string>;

  constructor(config: APIClientConfig = {}) {
    this.baseURL = config.baseURL || '/api/v1';
    this.timeout = config.timeout || 30000;
    this.headers = {
      'Content-Type': 'application/json',
      ...config.headers,
    };
  }

  private async request<T>(
    method: string,
    path: string,
    body?: any,
    options?: { timeout?: number; headers?: Record<string, string> }
  ): Promise<T> {
    const url = `${this.baseURL}${path}`;
    const timeout = options?.timeout || this.timeout;
    const headers = { ...this.headers, ...options?.headers };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(error.message || `HTTP ${response.status}`);
      }

      return await response.json();
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // Agent Run APIs
  async startAgentRun(task: string, extraContext?: Record<string, any>): Promise<AgentRun> {
    return this.request<AgentRun>('POST', '/agent/run/stream', {
      task,
      extra_context: extraContext,
    });
  }

  async getAgentRun(runId: string): Promise<AgentRun> {
    return this.request<AgentRun>('GET', `/agent/runs/${encodeURIComponent(runId)}`);
  }

  async listAgentRuns(limit?: number, offset?: number): Promise<{ items: AgentRun[]; total: number }> {
    const params = new URLSearchParams();
    if (limit) params.append('limit', String(limit));
    if (offset) params.append('offset', String(offset));
    return this.request<{ items: AgentRun[]; total: number }>(
      'GET',
      `/agent/runs?${params}`
    );
  }

  async cancelAgentRun(runId: string): Promise<void> {
    return this.request<void>('POST', `/agent/runs/${encodeURIComponent(runId)}/cancel`);
  }

  // Task APIs
  async getTasks(runId?: string, status?: string): Promise<{ tasks: Task[]; total: number; completed: number; in_progress: number; failed: number; pending: number }> {
    const params = new URLSearchParams();
    if (runId) params.append('run_id', runId);
    if (status) params.append('status', status);
    return this.request<any>('GET', `/tasks?${params}`);
  }

  async getTask(taskId: string): Promise<Task> {
    return this.request<Task>('GET', `/tasks/${encodeURIComponent(taskId)}`);
  }

  async updateTask(taskId: string, updates: Partial<Task>): Promise<Task> {
    return this.request<Task>('PATCH', `/tasks/${encodeURIComponent(taskId)}`, updates);
  }

  // Question APIs
  async getPendingQuestions(runId: string): Promise<{ questions: Question[] }> {
    return this.request<{ questions: Question[] }>(
      'GET',
      `/questions/pending?run_id=${encodeURIComponent(runId)}`
    );
  }

  async getQuestion(questionId: string): Promise<Question> {
    return this.request<Question>('GET', `/questions/${encodeURIComponent(questionId)}`);
  }

  async answerQuestion(questionId: string, answer: any): Promise<void> {
    return this.request<void>('POST', `/questions/${encodeURIComponent(questionId)}/answer`, {
      answer,
    });
  }

  async cancelQuestion(questionId: string): Promise<void> {
    return this.request<void>('POST', `/questions/${encodeURIComponent(questionId)}/cancel`);
  }

  // File APIs
  async getFileMetadata(filePath: string): Promise<FileMetadata> {
    return this.request<FileMetadata>(
      'GET',
      `/files/metadata/${encodeURIComponent(filePath)}`
    );
  }

  async getFilePreview(filePath: string, maxLines?: number): Promise<FilePreviewData> {
    const params = new URLSearchParams();
    if (maxLines) params.append('max_lines', String(maxLines));
    return this.request<FilePreviewData>(
      'GET',
      `/files/preview/${encodeURIComponent(filePath)}?${params}`
    );
  }

  async getDirectory(directoryPath: string): Promise<{ files: FileMetadata[]; directories: FileMetadata[] }> {
    return this.request<{ files: FileMetadata[]; directories: FileMetadata[] }>(
      'GET',
      `/files/directory/${encodeURIComponent(directoryPath)}`
    );
  }

  async downloadFile(filePath: string): Promise<Blob> {
    const url = `${this.baseURL}/files/download/${encodeURIComponent(filePath)}`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to download file: ${response.statusText}`);
    }
    return response.blob();
  }

  // Workspace/Mount APIs
  async getMounts(): Promise<Mount[]> {
    return this.request<Mount[]>('GET', '/workspace/mounts');
  }

  async mountDirectory(
    hostPath: string,
    mountPath?: string,
    readOnly?: boolean
  ): Promise<Mount> {
    return this.request<Mount>('POST', '/workspace/mount', {
      host_path: hostPath,
      mount_path: mountPath,
      read_only: readOnly,
    });
  }

  async unmountDirectory(mountId: string): Promise<void> {
    return this.request<void>('DELETE', `/workspace/mount/${encodeURIComponent(mountId)}`);
  }

  // Progress APIs
  async getProgress(runId: string): Promise<{
    overall_progress: number;
    current_step: string;
    total_steps: number;
    completed_steps: number;
    estimated_remaining_seconds?: number;
  }> {
    return this.request<any>('GET', `/agent/stream/${encodeURIComponent(runId)}/events`);
  }

  // Utility methods
  setBaseURL(baseURL: string): void {
    this.baseURL = baseURL;
  }

  setHeaders(headers: Record<string, string>): void {
    this.headers = { ...this.headers, ...headers };
  }

  setTimeout(timeout: number): void {
    this.timeout = timeout;
  }
}

export default APIClient;
