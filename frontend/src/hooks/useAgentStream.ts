/**
 * useAgentStream Hook
 *
 * Fetch-based POST SSE consumer for the /agents/run/stream endpoint.
 * EventSource only supports GET, so we use fetch + ReadableStream to parse
 * the SSE response from a POST request.
 */

import { useCallback, useRef, useState } from 'react';

export interface TraceEvent {
  event_type?: string;
  type?: string;
  timestamp?: string;
  tool_name?: string;
  tool_id?: string;
  arguments?: Record<string, any>;
  result?: any;
  success?: boolean;
  message?: string;
  content?: string;
  status?: string;
  [key: string]: any;
}

export interface AgentStreamResult {
  _final: boolean;
  result?: {
    status: string;
    answer?: string;
    tool_calls?: any[];
    iterations?: number;
    trace_id?: string;
    [key: string]: any;
  };
  error?: string;
}

export interface UseAgentStreamReturn {
  events: TraceEvent[];
  isStreaming: boolean;
  finalResult: AgentStreamResult | null;
  error: string | null;
  startStream: (task: string, extraContext?: Record<string, any>) => Promise<void>;
  stopStream: () => void;
  reset: () => void;
}

/** Parse a single SSE frame from raw text. Returns [eventName, data] pairs. */
function parseSSEFrames(chunk: string): Array<{ event: string; data: string }> {
  const frames: Array<{ event: string; data: string }> = [];
  const blocks = chunk.split('\n\n');
  for (const block of blocks) {
    if (!block.trim()) continue;
    let eventName = 'message';
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) {
        eventName = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        data += line.slice(6);
      } else if (line.startsWith('data:')) {
        data += line.slice(5);
      }
    }
    if (data) {
      frames.push({ event: eventName, data });
    }
  }
  return frames;
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

  const startStream = useCallback(async (task: string, extraContext?: Record<string, any>) => {
    // Reset state
    setEvents([]);
    setFinalResult(null);
    setError(null);
    setIsStreaming(true);
    bufferRef.current = '';

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const token = localStorage.getItem('auth_token');
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      // Also support API key auth
      const apiKey = localStorage.getItem('api_key');
      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }

      const response = await fetch('/api/v1/agents/run/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          task,
          extra_context: extraContext || {},
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

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        bufferRef.current += decoder.decode(value, { stream: true });

        // Process complete frames (separated by \n\n)
        const parts = bufferRef.current.split('\n\n');
        // Keep the last incomplete part in buffer
        bufferRef.current = parts.pop() || '';

        for (const part of parts) {
          if (!part.trim()) continue;
          const frames = parseSSEFrames(part + '\n\n');
          for (const frame of frames) {
            try {
              const parsed = JSON.parse(frame.data);

              if (frame.event === 'completed' || parsed._final) {
                const result: AgentStreamResult = parsed;
                setFinalResult(result);
                setIsStreaming(false);
                onComplete?.(result);
              } else {
                // Trace event
                const traceEvent: TraceEvent = {
                  ...parsed,
                  event_type: parsed.event_type || parsed.type || frame.event,
                  timestamp: parsed.timestamp || new Date().toISOString(),
                };
                setEvents((prev) => {
                  const updated = [...prev, traceEvent];
                  return updated.length > maxEvents ? updated.slice(-maxEvents) : updated;
                });
                onEvent?.(traceEvent);
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }
      }

      // Stream ended without explicit completion
      setIsStreaming(false);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setIsStreaming(false);
        return;
      }
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setIsStreaming(false);
      onError?.(msg);
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
