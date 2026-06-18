/**
 * Real-time Task Visualization Components
 *
 * High-performance components for displaying streaming task updates,
 * progress tracking, and live metrics with sub-100ms latency.
 */

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { createAgentStreamUrl } from '../../services/streamUrls';

// ============================================================================
// Types
// ============================================================================

export interface StreamEvent {
  event_type: string;
  timestamp: string;
  run_id: string;
  sequence: number;
  [key: string]: any;
}

export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  title: string;
  progress: number;
  details?: Record<string, any>;
}

export interface ProgressData {
  overall_progress: number;
  current_step: string;
  total_steps: number;
  completed_steps: number;
  estimated_remaining_seconds?: number;
}

// ============================================================================
// Real-time Task List Component
// ============================================================================

interface RealtimeTaskListProps {
  runId: string;
  onTaskClick?: (task: TaskStatus) => void;
  maxTasks?: number;
  autoScroll?: boolean;
}

export const RealtimeTaskList: React.FC<RealtimeTaskListProps> = ({
  runId,
  onTaskClick,
  maxTasks = 50,
  autoScroll = true,
}) => {
  const [tasks, setTasks] = useState<Map<string, TaskStatus>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleTaskUpdate = useCallback((event: StreamEvent) => {
    if (event.event_type === 'task_status') {
      setTasks((prev) => {
        const updated = new Map(prev);
        updated.set(event.task_id, {
          task_id: event.task_id,
          status: event.status,
          title: event.title || '',
          progress: event.progress || 0,
          details: event.details,
        });
        return updated;
      });
    }
  }, []);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let cancelled = false;

    const handleMessage = (rawEvent: Event) => {
      try {
        const messageEvent = rawEvent as MessageEvent;
        const data = JSON.parse(messageEvent.data) as StreamEvent;
        handleTaskUpdate(data);
      } catch (e) {
        console.error('Failed to parse event:', e);
      }
    };

    void createAgentStreamUrl(runId).then((url) => {
      if (cancelled) return;
      eventSource = new EventSource(url);
      eventSource.addEventListener('task_status', handleMessage);
      eventSource.addEventListener('message', handleMessage);

      eventSource.onerror = () => {
        setIsConnected(false);
        setError('Connection lost');
        eventSource?.close();
      };

      eventSourceRef.current = eventSource;
      setIsConnected(true);
      setError(null);
    }).catch((error) => {
      setIsConnected(false);
      setError(error instanceof Error ? error.message : 'Connection lost');
    });

    return () => {
      cancelled = true;
      eventSource?.close();
    };
  }, [runId, handleTaskUpdate]);

  const sortedTasks = useMemo(() => {
    return Array.from(tasks.values())
      .sort((a, b) => {
        // Sort by status priority
        const statusPriority: Record<string, number> = {
          running: 0,
          pending: 1,
          completed: 2,
          failed: 3,
        };
        return (statusPriority[a.status] || 99) - (statusPriority[b.status] || 99);
      })
      .slice(0, maxTasks);
  }, [tasks, maxTasks]);

  const statusColors: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-800',
    running: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  };

  const statusIcons: Record<string, string> = {
    pending: '⏳',
    running: '⚙️',
    completed: '✅',
    failed: '❌',
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-lg font-bold text-gray-900">Tasks</h2>
        <div className="flex items-center gap-2">
          <div
            className={`w-3 h-3 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-xs text-gray-600">
            {isConnected ? 'Live' : 'Offline'} ({tasks.size})
          </span>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-3 bg-red-100 border-b border-red-300 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Task List */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-3 space-y-2"
      >
        {sortedTasks.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            Waiting for tasks...
          </div>
        ) : (
          sortedTasks.map((task) => (
            <div
              key={task.task_id}
              onClick={() => onTaskClick?.(task)}
              className={`p-3 rounded-lg border cursor-pointer transition-all hover:shadow-md ${
                statusColors[task.status] || 'bg-gray-50'
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2 flex-1">
                  <span className="text-lg">{statusIcons[task.status]}</span>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-sm truncate">
                      {task.title || task.task_id}
                    </h3>
                    <p className="text-xs opacity-75 truncate">
                      {task.task_id}
                    </p>
                  </div>
                </div>
                <span className="text-xs font-medium ml-2">
                  {Math.round(task.progress * 100)}%
                </span>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-gray-300 rounded-full h-1.5">
                <div
                  className="h-1.5 rounded-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${task.progress * 100}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

// ============================================================================
// Real-time Progress Bar Component
// ============================================================================

interface RealtimeProgressBarProps {
  runId: string;
  compact?: boolean;
}

export const RealtimeProgressBar: React.FC<RealtimeProgressBarProps> = ({
  runId,
  compact = false,
}) => {
  const [progress, setProgress] = useState<ProgressData>({
    overall_progress: 0,
    current_step: 'Initializing...',
    total_steps: 0,
    completed_steps: 0,
  });
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let cancelled = false;

    const handleMessage = (rawEvent: Event) => {
      try {
        const messageEvent = rawEvent as MessageEvent;
        const data = JSON.parse(messageEvent.data) as StreamEvent;

        if (data.event_type === 'progress') {
          setProgress({
            overall_progress: data.overall_progress || 0,
            current_step: data.current_step || '',
            total_steps: data.total_steps || 0,
            completed_steps: data.completed_steps || 0,
            estimated_remaining_seconds: data.estimated_remaining_seconds,
          });
        }
      } catch (e) {
        console.error('Failed to parse event:', e);
      }
    };

    void createAgentStreamUrl(runId).then((url) => {
      if (cancelled) return;
      eventSource = new EventSource(url);
      eventSource.addEventListener('progress', handleMessage);
      eventSource.addEventListener('message', handleMessage);

      eventSource.onerror = () => {
        setIsConnected(false);
        eventSource?.close();
      };

      eventSourceRef.current = eventSource;
      setIsConnected(true);
    }).catch(() => {
      setIsConnected(false);
    });

    return () => {
      cancelled = true;
      eventSource?.close();
    };
  }, [runId]);

  const formatTime = (seconds: number | undefined): string => {
    if (!seconds) return '';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  if (compact) {
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">
            {progress.current_step}
          </span>
          <span className="text-sm font-bold text-gray-900">
            {Math.round(progress.overall_progress * 100)}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="h-2 rounded-full bg-blue-500 transition-all duration-300"
            style={{ width: `${progress.overall_progress * 100}%` }}
          />
        </div>
        {progress.estimated_remaining_seconds && (
          <p className="text-xs text-gray-600">
            Est. {formatTime(progress.estimated_remaining_seconds)} remaining
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-gray-900">
            {progress.current_step}
          </h3>
          <p className="text-sm text-gray-600">
            Step {progress.completed_steps} of {progress.total_steps}
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-blue-600">
            {Math.round(progress.overall_progress * 100)}%
          </div>
          {progress.estimated_remaining_seconds && (
            <p className="text-sm text-gray-600">
              {formatTime(progress.estimated_remaining_seconds)} remaining
            </p>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className="h-3 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-300"
            style={{ width: `${progress.overall_progress * 100}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-600">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Connection Status */}
      <div className="flex items-center gap-2 text-xs">
        <div
          className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-green-500' : 'bg-red-500'
          }`}
        />
        <span className="text-gray-600">
          {isConnected ? 'Live streaming' : 'Offline'}
        </span>
      </div>
    </div>
  );
};

// ============================================================================
// Real-time Log Stream Component
// ============================================================================

interface RealtimeLogStreamProps {
  runId: string;
  maxLogs?: number;
  autoScroll?: boolean;
  filterLevel?: 'all' | 'info' | 'warning' | 'error';
}

export const RealtimeLogStream: React.FC<RealtimeLogStreamProps> = ({
  runId,
  maxLogs = 500,
  autoScroll = true,
  filterLevel: initialFilterLevel = 'all',
}) => {
  const [logs, setLogs] = useState<StreamEvent[]>([]);
  const [filterLevel, setFilterLevel] = useState(initialFilterLevel);
  const [isConnected, setIsConnected] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const scrollToBottom = useCallback(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'auto' });
    }
  }, [autoScroll]);

  useEffect(() => {
    scrollToBottom();
  }, [logs, scrollToBottom]);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let cancelled = false;

    const handleMessage = (rawEvent: Event) => {
      try {
        const messageEvent = rawEvent as MessageEvent;
        const data = JSON.parse(messageEvent.data) as StreamEvent;

        if (['log', 'error', 'message'].includes(data.event_type)) {
          setLogs((prev) => {
            const updated = [...prev, data];
            return updated.length > maxLogs ? updated.slice(-maxLogs) : updated;
          });
        }
      } catch (e) {
        console.error('Failed to parse event:', e);
      }
    };

    void createAgentStreamUrl(runId).then((url) => {
      if (cancelled) return;
      eventSource = new EventSource(url);
      eventSource.addEventListener('log', handleMessage);
      eventSource.addEventListener('error', handleMessage);
      eventSource.addEventListener('message', handleMessage);

      eventSource.onerror = () => {
        setIsConnected(false);
        eventSource?.close();
      };

      eventSourceRef.current = eventSource;
      setIsConnected(true);
    }).catch(() => {
      setIsConnected(false);
    });

    return () => {
      cancelled = true;
      eventSource?.close();
    };
  }, [runId, maxLogs]);

  const filteredLogs = useMemo(() => {
    if (filterLevel === 'all') return logs;

    return logs.filter((log) => {
      if (filterLevel === 'error') {
        return log.event_type === 'error' || log.level === 'error';
      }
      if (filterLevel === 'warning') {
        return ['error', 'warning'].includes(log.level || '');
      }
      return true;
    });
  }, [logs, filterLevel]);

  const logColors: Record<string, string> = {
    debug: 'text-gray-500',
    info: 'text-blue-600',
    warning: 'text-orange-600',
    error: 'text-red-600',
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-3 border-b border-gray-200 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Logs</h3>
        <div className="flex items-center gap-2">
          <select
            value={filterLevel}
            onChange={(e) =>
              setFilterLevel(e.target.value as typeof filterLevel)
            }
            className="px-2 py-1 text-xs border border-gray-300 rounded"
          >
            <option value="all">All</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
          <div
            className={`w-2 h-2 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
        </div>
      </div>

      {/* Log Container */}
      <div className="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-1">
        {filteredLogs.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            Waiting for logs...
          </div>
        ) : (
          filteredLogs.map((log, index) => (
            <div
              key={index}
              className={`p-1 rounded ${
                logColors[log.level || 'info'] || 'text-gray-700'
              }`}
            >
              <span className="text-gray-500">
                [{new Date(log.timestamp).toLocaleTimeString()}]
              </span>
              <span className="ml-2 font-semibold">
                {log.level?.toUpperCase() || log.event_type.toUpperCase()}
              </span>
              <span className="ml-2">{log.message || JSON.stringify(log)}</span>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
};

// ============================================================================
// Unified Real-time Dashboard
// ============================================================================

interface RealtimeDashboardProps {
  runId: string;
  layout?: 'grid' | 'split' | 'tabs';
}

export const RealtimeDashboard: React.FC<RealtimeDashboardProps> = ({
  runId,
  layout = 'split',
}) => {
  const [activeTab, setActiveTab] = useState<'tasks' | 'logs'>('tasks');

  if (layout === 'split') {
    return (
      <div className="flex h-full gap-4 bg-gray-100 p-4 rounded-lg">
        {/* Left: Progress and Tasks */}
        <div className="flex-1 flex flex-col gap-4">
          <RealtimeProgressBar runId={runId} />
          <div className="flex-1 min-h-0">
            <RealtimeTaskList runId={runId} />
          </div>
        </div>

        {/* Right: Logs */}
        <div className="w-96 min-h-0">
          <RealtimeLogStream runId={runId} />
        </div>
      </div>
    );
  }

  if (layout === 'tabs') {
    return (
      <div className="flex flex-col h-full bg-gray-100 rounded-lg">
        {/* Tabs */}
        <div className="flex gap-2 p-4 bg-white border-b border-gray-200">
          <button
            onClick={() => setActiveTab('tasks')}
            className={`px-4 py-2 rounded font-medium transition-colors ${
              activeTab === 'tasks'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-700'
            }`}
          >
            Tasks
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`px-4 py-2 rounded font-medium transition-colors ${
              activeTab === 'logs'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-700'
            }`}
          >
            Logs
          </button>
        </div>

        {/* Progress */}
        <div className="p-4 bg-white border-b border-gray-200">
          <RealtimeProgressBar runId={runId} compact={true} />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden p-4">
          {activeTab === 'tasks' && (
            <RealtimeTaskList runId={runId} />
          )}
          {activeTab === 'logs' && (
            <RealtimeLogStream runId={runId} />
          )}
        </div>
      </div>
    );
  }

  // Grid layout
  return (
    <div className="flex flex-col h-full gap-4 bg-gray-100 p-4 rounded-lg">
      <RealtimeProgressBar runId={runId} />
      <div className="flex gap-4 flex-1 min-h-0">
        <div className="flex-1 min-h-0">
          <RealtimeTaskList runId={runId} />
        </div>
        <div className="w-96 min-h-0">
          <RealtimeLogStream runId={runId} />
        </div>
      </div>
    </div>
  );
};

export default RealtimeDashboard;
