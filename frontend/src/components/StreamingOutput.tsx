/**
 * StreamingOutput Component
 *
 * Displays real-time streaming output from agent execution with support for
 * different event types: messages, tool calls, progress updates, and errors.
 */

import React, { useEffect, useRef, useState } from 'react';

interface StreamEvent {
  event_type: string;
  timestamp: string;
  run_id: string;
  data?: Record<string, any>;
  sequence?: number;
}

interface MessageEvent extends StreamEvent {
  event_type: 'message';
  content: string;
  role: 'assistant' | 'user' | 'system';
}

interface ToolCallEvent extends StreamEvent {
  event_type: 'tool_call';
  tool_name: string;
  tool_id: string;
  arguments: Record<string, any>;
}

interface ToolResultEvent extends StreamEvent {
  event_type: 'tool_result';
  tool_id: string;
  tool_name: string;
  result: any;
  success: boolean;
}

interface ProgressEvent extends StreamEvent {
  event_type: 'progress';
  overall_progress: number;
  current_step: string;
  total_steps: number;
  completed_steps: number;
}

interface ErrorEvent extends StreamEvent {
  event_type: 'error';
  error_code: string;
  error_message: string;
  error_details: Record<string, any>;
  recoverable: boolean;
}

interface CompletionEvent extends StreamEvent {
  event_type: 'completion';
  status: string;
  result: any;
  summary: Record<string, any>;
}

type AnyStreamEvent = MessageEvent | ToolCallEvent | ToolResultEvent | ProgressEvent | ErrorEvent | CompletionEvent | StreamEvent;

interface StreamingOutputProps {
  runId: string;
  onComplete?: (result: any) => void;
  onError?: (error: ErrorEvent) => void;
  maxMessages?: number;
  autoScroll?: boolean;
}

export const StreamingOutput: React.FC<StreamingOutputProps> = ({
  runId,
  onComplete,
  onError,
  maxMessages = 1000,
  autoScroll = true,
}) => {
  const [events, setEvents] = useState<AnyStreamEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const scrollToBottom = () => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [events, autoScroll]);

  useEffect(() => {
    const connectToStream = () => {
      try {
        const eventSource = new EventSource(`/api/v1/agent/stream/${runId}`);

        eventSource.addEventListener('message', (event) => {
          try {
            const data = JSON.parse(event.data) as AnyStreamEvent;
            setEvents((prev) => {
              const updated = [...prev, data];
              return updated.length > maxMessages ? updated.slice(-maxMessages) : updated;
            });
          } catch (e) {
            console.error('Failed to parse event:', e);
          }
        });

        eventSource.addEventListener('tool_call', (event) => {
          try {
            const data = JSON.parse(event.data) as ToolCallEvent;
            setEvents((prev) => [...prev, data]);
          } catch (e) {
            console.error('Failed to parse tool_call event:', e);
          }
        });

        eventSource.addEventListener('tool_result', (event) => {
          try {
            const data = JSON.parse(event.data) as ToolResultEvent;
            setEvents((prev) => [...prev, data]);
          } catch (e) {
            console.error('Failed to parse tool_result event:', e);
          }
        });

        eventSource.addEventListener('progress', (event) => {
          try {
            const data = JSON.parse(event.data) as ProgressEvent;
            setEvents((prev) => [...prev, data]);
          } catch (e) {
            console.error('Failed to parse progress event:', e);
          }
        });

        eventSource.addEventListener('error', (event) => {
          try {
            const data = JSON.parse(event.data) as ErrorEvent;
            setEvents((prev) => [...prev, data]);
            if (onError) {
              onError(data);
            }
          } catch (e) {
            console.error('Failed to parse error event:', e);
          }
        });

        eventSource.addEventListener('completion', (event) => {
          try {
            const data = JSON.parse(event.data) as CompletionEvent;
            setEvents((prev) => [...prev, data]);
            if (onComplete) {
              onComplete(data.result);
            }
            eventSource.close();
            setIsConnected(false);
          } catch (e) {
            console.error('Failed to parse completion event:', e);
          }
        });

        eventSource.addEventListener('heartbeat', () => {
          // Keep-alive signal, no action needed
        });

        eventSource.onerror = () => {
          setIsConnected(false);
          setError('Connection lost');
          eventSource.close();
        };

        eventSourceRef.current = eventSource;
        setIsConnected(true);
        setError(null);
      } catch (e) {
        setError(`Failed to connect: ${e instanceof Error ? e.message : String(e)}`);
        setIsConnected(false);
      }
    };

    connectToStream();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [runId, maxMessages, onComplete, onError]);

  const renderEvent = (event: AnyStreamEvent, index: number) => {
    switch (event.event_type) {
      case 'message':
        return (
          <div key={index} className="mb-4 p-3 bg-gray-50 rounded border-l-4 border-blue-500">
            <div className="text-xs text-gray-500 mb-1">
              {(event as MessageEvent).role.toUpperCase()} • {new Date(event.timestamp).toLocaleTimeString()}
            </div>
            <div className="text-sm text-gray-800 whitespace-pre-wrap">
              {(event as MessageEvent).content}
            </div>
          </div>
        );

      case 'tool_call':
        return (
          <div key={index} className="mb-4 p-3 bg-yellow-50 rounded border-l-4 border-yellow-500">
            <div className="text-xs text-gray-500 mb-1">
              TOOL CALL • {new Date(event.timestamp).toLocaleTimeString()}
            </div>
            <div className="font-mono text-sm font-semibold text-yellow-700 mb-2">
              {(event as ToolCallEvent).tool_name}
            </div>
            <pre className="text-xs bg-white p-2 rounded overflow-auto max-h-40">
              {JSON.stringify((event as ToolCallEvent).arguments, null, 2)}
            </pre>
          </div>
        );

      case 'tool_result':
        return (
          <div key={index} className="mb-4 p-3 bg-green-50 rounded border-l-4 border-green-500">
            <div className="text-xs text-gray-500 mb-1">
              TOOL RESULT • {new Date(event.timestamp).toLocaleTimeString()}
            </div>
            <div className="font-mono text-sm font-semibold text-green-700 mb-2">
              {(event as ToolResultEvent).tool_name}
              {!(event as ToolResultEvent).success && ' (FAILED)'}
            </div>
            <pre className="text-xs bg-white p-2 rounded overflow-auto max-h-40">
              {JSON.stringify((event as ToolResultEvent).result, null, 2)}
            </pre>
          </div>
        );

      case 'progress':
        const progressEvent = event as ProgressEvent;
        return (
          <div key={index} className="mb-4 p-3 bg-blue-50 rounded border-l-4 border-blue-500">
            <div className="text-xs text-gray-500 mb-2">
              PROGRESS • {new Date(event.timestamp).toLocaleTimeString()}
            </div>
            <div className="text-sm font-semibold text-blue-700 mb-2">
              {progressEvent.current_step}
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${progressEvent.overall_progress * 100}%` }}
              />
            </div>
            <div className="text-xs text-gray-600">
              {progressEvent.completed_steps} / {progressEvent.total_steps} steps
            </div>
          </div>
        );

      case 'error':
        const errorEvent = event as ErrorEvent;
        return (
          <div key={index} className="mb-4 p-3 bg-red-50 rounded border-l-4 border-red-500">
            <div className="text-xs text-gray-500 mb-1">
              ERROR • {new Date(event.timestamp).toLocaleTimeString()}
            </div>
            <div className="font-semibold text-red-700 mb-1">
              {errorEvent.error_code}
            </div>
            <div className="text-sm text-red-600 mb-2">
              {errorEvent.error_message}
            </div>
            {Object.keys(errorEvent.error_details).length > 0 && (
              <pre className="text-xs bg-white p-2 rounded overflow-auto max-h-40">
                {JSON.stringify(errorEvent.error_details, null, 2)}
              </pre>
            )}
            {errorEvent.recoverable && (
              <div className="text-xs text-orange-600 mt-2">
                ⚠️ This error may be recoverable
              </div>
            )}
          </div>
        );

      case 'completion':
        const completionEvent = event as CompletionEvent;
        return (
          <div key={index} className="mb-4 p-3 bg-green-50 rounded border-l-4 border-green-500">
            <div className="text-xs text-gray-500 mb-1">
              COMPLETION • {new Date(event.timestamp).toLocaleTimeString()}
            </div>
            <div className="font-semibold text-green-700 mb-2">
              Status: {completionEvent.status}
            </div>
            {completionEvent.result && (
              <pre className="text-xs bg-white p-2 rounded overflow-auto max-h-40">
                {JSON.stringify(completionEvent.result, null, 2)}
              </pre>
            )}
          </div>
        );

      default:
        return (
          <div key={index} className="mb-4 p-3 bg-gray-50 rounded text-xs text-gray-600">
            <div className="text-gray-500 mb-1">
              {event.event_type.toUpperCase()} • {new Date(event.timestamp).toLocaleTimeString()}
            </div>
            <pre className="overflow-auto max-h-40">
              {JSON.stringify(event, null, 2)}
            </pre>
          </div>
        );
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm font-semibold text-gray-700">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          {events.length} events
        </span>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-3 bg-red-100 border-b border-red-300 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Events Container */}
      <div className="flex-1 overflow-y-auto p-4">
        {events.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            Waiting for events...
          </div>
        ) : (
          events.map((event, index) => renderEvent(event, index))
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default StreamingOutput;
