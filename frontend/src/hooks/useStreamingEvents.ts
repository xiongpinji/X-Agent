/**
 * useStreamingEvents Hook
 *
 * Manages real-time streaming events from the backend SSE endpoint.
 * Handles connection, reconnection, event parsing, and state management.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

export interface StreamEvent {
  event_type: string;
  timestamp: string;
  run_id: string;
  sequence: number;
  [key: string]: any;
}

export interface ProgressData {
  overall_progress: number;
  current_step: string;
  total_steps: number;
  completed_steps: number;
  estimated_time_remaining?: number;
}

export interface MetricsData {
  [key: string]: number | string;
}

export interface UseStreamingEventsOptions {
  maxMessages?: number;
  autoScroll?: boolean;
  heartbeatTimeout?: number;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  onEvent?: (event: StreamEvent) => void;
  onProgress?: (progress: ProgressData) => void;
  onMetric?: (metric: { name: string; value: number | string; unit: string }) => void;
  onError?: (error: Error) => void;
  onComplete?: (result: any) => void;
}

export const useStreamingEvents = (
  runId: string,
  options: UseStreamingEventsOptions = {}
) => {
  const {
    maxMessages = 1000,
    autoScroll: _autoScroll = true,
    heartbeatTimeout = 60000,
    reconnectAttempts = 5,
    reconnectDelay = 1000,
    onEvent,
    onProgress,
    onMetric,
    onError,
    onComplete,
  } = options;

  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [metrics, setMetrics] = useState<MetricsData>({});
  const [reconnectCount, setReconnectCount] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastSequenceRef = useRef<number>(0);

  const resetHeartbeatTimer = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current);
    }
    heartbeatTimerRef.current = setTimeout(() => {
      console.warn('Heartbeat timeout, reconnecting...');
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    }, heartbeatTimeout);
  }, [heartbeatTimeout]);

  const handleEvent = useCallback(
    (event: StreamEvent) => {
      // Update last sequence for reconnection
      if (event.sequence > lastSequenceRef.current) {
        lastSequenceRef.current = event.sequence;
      }

      // Add to events list
      setEvents((prev) => {
        const updated = [...prev, event];
        return updated.length > maxMessages ? updated.slice(-maxMessages) : updated;
      });

      // Handle specific event types
      switch (event.event_type) {
        case 'progress': {
          const progressData: ProgressData = {
            overall_progress: event.overall_progress,
            current_step: event.current_step,
            total_steps: event.total_steps,
            completed_steps: event.completed_steps,
            estimated_time_remaining: event.estimated_time_remaining,
          };
          setProgress(progressData);
          if (onProgress) onProgress(progressData);
          break;
        }

        case 'metric':
          setMetrics((prev) => ({
            ...prev,
            [event.metric_name]: event.metric_value,
          }));
          if (onMetric) {
            onMetric({
              name: event.metric_name,
              value: event.metric_value,
              unit: event.unit,
            });
          }
          break;

        case 'completion':
          if (onComplete) onComplete(event.result);
          break;

        case 'error':
          if (onError) onError(new Error(event.error_message));
          break;

        case 'heartbeat':
          resetHeartbeatTimer();
          break;
      }

      if (onEvent) onEvent(event);
    },
    [maxMessages, onEvent, onProgress, onMetric, onError, onComplete, resetHeartbeatTimer]
  );

  const connectToStream = useCallback(() => {
    try {
      const url = `/api/v1/agent/stream/${runId}?since_sequence=${lastSequenceRef.current}`;
      const eventSource = new EventSource(url);

      // Generic event handler
      const handleMessage = (rawEvent: Event) => {
        try {
          const messageEvent = rawEvent as MessageEvent;
          const data = JSON.parse(messageEvent.data) as StreamEvent;
          handleEvent(data);
        } catch (e) {
          console.error('Failed to parse event:', e);
        }
      };

      // Listen to all event types
      eventSource.addEventListener('message', handleMessage);
      eventSource.addEventListener('tool_call', handleMessage);
      eventSource.addEventListener('tool_result', handleMessage);
      eventSource.addEventListener('progress', handleMessage);
      eventSource.addEventListener('error', handleMessage);
      eventSource.addEventListener('completion', handleMessage);
      eventSource.addEventListener('heartbeat', handleMessage);
      eventSource.addEventListener('log', handleMessage);
      eventSource.addEventListener('metric', handleMessage);
      eventSource.addEventListener('task_status', handleMessage);

      eventSource.onerror = () => {
        console.error('EventSource error');
        setIsConnected(false);
        setError('Connection lost');
        eventSource.close();

        // Attempt reconnection
        if (reconnectCount < reconnectAttempts) {
          const delay = reconnectDelay * Math.pow(2, reconnectCount);
          reconnectTimerRef.current = setTimeout(() => {
            console.log(`Reconnecting... (attempt ${reconnectCount + 1}/${reconnectAttempts})`);
            setReconnectCount((prev) => prev + 1);
            connectToStream();
          }, delay);
        } else {
          setError('Failed to reconnect after multiple attempts');
        }
      };

      eventSourceRef.current = eventSource;
      setIsConnected(true);
      setError(null);
      setReconnectCount(0);
      resetHeartbeatTimer();

      console.log(`Connected to stream for run ${runId}`);
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : String(e);
      setError(`Failed to connect: ${errorMsg}`);
      setIsConnected(false);
      if (onError) onError(new Error(errorMsg));
    }
  }, [runId, reconnectCount, reconnectAttempts, reconnectDelay, handleEvent, resetHeartbeatTimer, onError]);

  useEffect(() => {
    connectToStream();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [connectToStream]);

  const reconnect = useCallback(() => {
    setReconnectCount(0);
    lastSequenceRef.current = 0;
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    connectToStream();
  }, [connectToStream]);

  return {
    events,
    isConnected,
    error,
    progress,
    metrics,
    reconnect,
    lastSequence: lastSequenceRef.current,
  };
};

export default useStreamingEvents;
