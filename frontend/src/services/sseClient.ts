/**
 * SSE Client Service
 *
 * Manages Server-Sent Events (SSE) connections for real-time streaming
 * of agent execution events with automatic reconnection and error handling.
 */

export interface StreamEvent {
  event_type: string;
  timestamp: string;
  run_id: string;
  data?: Record<string, any>;
  sequence?: number;
}

export interface MessageEvent extends StreamEvent {
  event_type: 'message';
  content: string;
  role: 'assistant' | 'user' | 'system';
}

export interface ToolCallEvent extends StreamEvent {
  event_type: 'tool_call';
  tool_name: string;
  tool_id: string;
  arguments: Record<string, any>;
}

export interface ToolResultEvent extends StreamEvent {
  event_type: 'tool_result';
  tool_id: string;
  tool_name: string;
  result: any;
  success: boolean;
}

export interface ProgressEvent extends StreamEvent {
  event_type: 'progress';
  overall_progress: number;
  current_step: string;
  total_steps: number;
  completed_steps: number;
  estimated_remaining_seconds?: number;
}

export interface ErrorEvent extends StreamEvent {
  event_type: 'error';
  error_code: string;
  error_message: string;
  error_details: Record<string, any>;
  recoverable: boolean;
}

export interface CompletionEvent extends StreamEvent {
  event_type: 'completion';
  status: string;
  result: any;
  summary: Record<string, any>;
}

export type AnyStreamEvent =
  | MessageEvent
  | ToolCallEvent
  | ToolResultEvent
  | ProgressEvent
  | ErrorEvent
  | CompletionEvent
  | StreamEvent;

export interface SSEClientConfig {
  maxReconnectAttempts?: number;
  reconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
  heartbeatTimeoutMs?: number;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts: number;
  private reconnectDelayMs: number;
  private maxReconnectDelayMs: number;
  private heartbeatTimeoutMs: number;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private isManuallyClosed = false;

  constructor(config: SSEClientConfig = {}) {
    this.maxReconnectAttempts = config.maxReconnectAttempts ?? 10;
    this.reconnectDelayMs = config.reconnectDelayMs ?? 1000;
    this.maxReconnectDelayMs = config.maxReconnectDelayMs ?? 30000;
    this.heartbeatTimeoutMs = config.heartbeatTimeoutMs ?? 60000;
  }

  connect(
    runId: string,
    onMessage: (event: AnyStreamEvent) => void,
    onError?: (error: Error) => void,
    onComplete?: () => void
  ): void {
    if (this.eventSource) {
      this.disconnect();
    }

    this.isManuallyClosed = false;

    try {
      const url = `/api/v1/agent/stream/${encodeURIComponent(runId)}`;
      this.eventSource = new EventSource(url);

      // Generic message handler
      this.eventSource.addEventListener('message', (event) => {
        this.handleMessage(event, onMessage, onError);
      });

      // Specific event type handlers
      this.eventSource.addEventListener('tool_call', (event) => {
        this.handleMessage(event, onMessage, onError);
      });

      this.eventSource.addEventListener('tool_result', (event) => {
        this.handleMessage(event, onMessage, onError);
      });

      this.eventSource.addEventListener('progress', (event) => {
        this.handleMessage(event, onMessage, onError);
      });

      this.eventSource.addEventListener('error', (event) => {
        this.handleMessage(event, onMessage, onError);
      });

      this.eventSource.addEventListener('completion', (event) => {
        this.handleMessage(event, onMessage, onError);
        this.disconnect();
        onComplete?.();
      });

      this.eventSource.addEventListener('heartbeat', () => {
        this.resetHeartbeatTimer();
      });

      this.eventSource.onerror = () => {
        if (!this.isManuallyClosed) {
          this.handleConnectionError(runId, onMessage, onError, onComplete);
        }
      };

      this.reconnectAttempts = 0;
      this.resetHeartbeatTimer();
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      onError?.(err);
    }
  }

  disconnect(): void {
    this.isManuallyClosed = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.clearHeartbeatTimer();
  }

  private handleMessage(
    event: MessageEvent,
    onMessage: (event: AnyStreamEvent) => void,
    onError?: (error: Error) => void
  ): void {
    try {
      const data = JSON.parse(event.data) as AnyStreamEvent;
      this.resetHeartbeatTimer();
      onMessage(data);
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      console.error('Failed to parse SSE event:', err);
      onError?.(err);
    }
  }

  private handleConnectionError(
    runId: string,
    onMessage: (event: AnyStreamEvent) => void,
    onError?: (error: Error) => void,
    onComplete?: () => void
  ): void {
    this.clearHeartbeatTimer();

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      const error = new Error(
        `Failed to connect after ${this.maxReconnectAttempts} attempts`
      );
      onError?.(error);
      return;
    }

    const delay = Math.min(
      this.reconnectDelayMs * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelayMs
    );

    this.reconnectAttempts++;
    console.log(
      `Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    setTimeout(() => {
      if (!this.isManuallyClosed) {
        this.connect(runId, onMessage, onError, onComplete);
      }
    }, delay);
  }

  private resetHeartbeatTimer(): void {
    this.clearHeartbeatTimer();
    this.heartbeatTimer = setTimeout(() => {
      console.warn('Heartbeat timeout - connection may be stale');
    }, this.heartbeatTimeoutMs);
  }

  private clearHeartbeatTimer(): void {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }

  getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }
}

export default SSEClient;
