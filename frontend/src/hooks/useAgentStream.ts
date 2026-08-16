/**
 * useAgentStream Hook
 *
 * Fetch-based POST SSE consumer for the /agents/run/stream endpoint.
 * EventSource only supports GET, so we use fetch + ReadableStream to parse
 * the SSE response from a POST request.
 */

import { useCallback, useRef, useState } from 'react';

const AGENT_STREAM_UNAVAILABLE_MESSAGE = 'Unable to reach the agent service';
const AGENT_EXECUTION_FAILED_MESSAGE = 'Agent execution failed';

export interface TraceEvent {
  event_type?: string;
  type?: string;
  event?: string;
  timestamp?: string;
  tool_name?: string;
  tool_id?: string;
  arguments?: Record<string, unknown>;
  result?: unknown;
  success?: boolean;
  message?: string;
  content?: string;
  data?: unknown;
  status?: string;
  [key: string]: unknown;
}

export interface AgentStreamResult {
  _final: boolean;
  result?: {
    status: string;
    answer?: string;
    tool_calls?: unknown[];
    iterations?: number;
    trace_id?: string;
    agent_id?: string;
    execution_summary?: {
      tokens_used?: number;
      total_tokens?: number;
      model?: string;
    };
    error?: string;
    error_code?: string;
    [key: string]: unknown;
  };
  error?: string;
}

export interface AgentStreamOptions {
  agent_id?: string;
  session_id?: string;
  extra_context?: Record<string, unknown>;
}

export interface UseAgentStreamReturn {
  events: TraceEvent[];
  isStreaming: boolean;
  finalResult: AgentStreamResult | null;
  error: string | null;
  startStream: (task: string, options?: AgentStreamOptions) => Promise<void>;
  stopStream: () => void;
  reset: () => void;
}

/** Parse a single SSE frame from raw text. Returns [eventName, data] pairs. */
function parseSSEFrames(chunk: string): Array<{ event: string; data: string }> {
  const frames: Array<{ event: string; data: string }> = [];
  const blocks = chunk.split(/\r\n\r\n|\n\n|\r\r/);
  for (const block of blocks) {
    if (!block.trim()) continue;
    let eventName = 'message';
    const dataLines: string[] = [];
    for (const line of block.split(/\r\n|\n|\r/)) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trimStart();
      } else if (line.startsWith('data:')) {
        const data = line.slice(5);
        dataLines.push(data.startsWith(' ') ? data.slice(1) : data);
      }
    }
    if (dataLines.length) {
      frames.push({ event: eventName, data: dataLines.join('\n') });
    }
  }
  return frames;
}

function takeCompleteSSEFrames(buffer: string): { frames: string[]; rest: string } {
  const frames: string[] = [];
  let rest = buffer;
  for (;;) {
    const boundary = rest.match(/\r\n\r\n|\n\n|\r\r/);
    if (!boundary || boundary.index === undefined) break;
    frames.push(rest.slice(0, boundary.index));
    rest = rest.slice(boundary.index + boundary[0].length);
  }
  return { frames, rest };
}

function isValidFinalResult(value: unknown): value is AgentStreamResult {
  if (!value || typeof value !== 'object') return false;
  const envelope = value as AgentStreamResult;
  const result = envelope.result;
  return envelope._final === true
    && !!result
    && (result.status === 'completed' || result.status === 'failed')
    && typeof result.trace_id === 'string'
    && result.trace_id.length > 0;
}

export function useAgentStream(options?: {
  maxEvents?: number;
  onEvent?: (event: TraceEvent) => void;
  onComplete?: (result: AgentStreamResult) => void;
  onError?: (error: string) => void;
}): UseAgentStreamReturn {
  const { maxEvents = 2000, onEvent, onComplete, onError } = options || {};

  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [finalResult, setFinalResult] = useState<AgentStreamResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const bufferRef = useRef('');

  const startStream = useCallback(async (task: string, streamOptions: AgentStreamOptions = {}) => {
    // Reset state
    setEvents([]);
    setFinalResult(null);
    setError(null);
    setIsStreaming(true);
    bufferRef.current = '';

    const controller = new AbortController();
    abortRef.current = controller;
    let finalReceived = false;

    try {
      const token = localStorage.getItem('auth_token');
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      } else {
        const apiKey = localStorage.getItem('api_key');
        if (apiKey) {
          headers['X-API-Key'] = apiKey;
        }
      }

      const extraContext = { ...(streamOptions.extra_context || {}) };
      for (const reservedKey of ['agent_profile', 'persona', 'profile']) {
        delete extraContext[reservedKey];
      }

      const response = await fetch('/api/v1/agents/run/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          task,
          ...(streamOptions.agent_id ? { agent_id: streamOptions.agent_id } : {}),
          ...(streamOptions.session_id ? { session_id: streamOptions.session_id } : {}),
          extra_context: extraContext,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errText = await response.text().catch(() => '');
        throw new Error(`HTTP ${response.status}: ${errText.slice(0, 200)}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Response body is not readable');
      }

      const decoder = new TextDecoder();

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;

        bufferRef.current += decoder.decode(value, { stream: true });

        const { frames: parts, rest } = takeCompleteSSEFrames(bufferRef.current);
        bufferRef.current = rest;

        for (const part of parts) {
          if (!part.trim()) continue;
          const frames = parseSSEFrames(part);
          for (const frame of frames) {
            const parsed: unknown = JSON.parse(frame.data);

            if (frame.event === 'completed' || (parsed as AgentStreamResult)?._final) {
              if (finalReceived || !isValidFinalResult(parsed)) {
                throw new Error('Invalid agent stream final frame');
              }
              finalReceived = true;
              setFinalResult(parsed);
              setError(parsed.result?.status === 'failed' ? AGENT_EXECUTION_FAILED_MESSAGE : null);
              setIsStreaming(false);
              onComplete?.(parsed);
              if (typeof reader.cancel === 'function') {
                await reader.cancel().catch(() => undefined);
              }
              return;
            } else {
              if (!parsed || typeof parsed !== 'object') {
                throw new Error('Invalid agent stream event');
              }
              const traceEvent: TraceEvent = {
                ...parsed,
                event_type: (parsed as TraceEvent).event_type || (parsed as TraceEvent).type || frame.event,
                timestamp: (parsed as TraceEvent).timestamp || new Date().toISOString(),
              };
              setEvents((prev) => {
                const updated = [...prev, traceEvent];
                return updated.length > maxEvents ? updated.slice(-maxEvents) : updated;
              });
              onEvent?.(traceEvent);
            }
          }
        }
      }

      bufferRef.current += decoder.decode();
      if (!finalReceived) {
        throw new Error('Agent stream ended without a final frame');
      }
      setIsStreaming(false);
    } catch (err: unknown) {
      if (controller.signal.aborted || (err && typeof err === 'object' && 'name' in err && err.name === 'AbortError')) {
        setIsStreaming(false);
        return;
      }
      if (finalReceived) {
        setIsStreaming(false);
        return;
      }
      setError(AGENT_STREAM_UNAVAILABLE_MESSAGE);
      setIsStreaming(false);
      onError?.(AGENT_STREAM_UNAVAILABLE_MESSAGE);
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }, [maxEvents, onEvent, onComplete, onError]);

  const stopStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const reset = useCallback(() => {
    stopStream();
    setEvents([]);
    setFinalResult(null);
    setError(null);
  }, [stopStream]);

  return { events, isStreaming, finalResult, error, startStream, stopStream, reset };
}

export default useAgentStream;
