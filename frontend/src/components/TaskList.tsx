/**
 * TaskList Component
 *
 * Displays a list of tasks with status, progress, and dependency information.
 * Supports filtering, sorting, and real-time updates.
 */

import React, { useEffect, useState } from 'react';

interface TaskModel {
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

interface TaskListProps {
  runId?: string;
  status?: string;
  onTaskClick?: (task: TaskModel) => void;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const statusColors: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800',
  in_progress: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-yellow-100 text-yellow-800',
};

const priorityColors: Record<string, string> = {
  low: 'text-gray-500',
  medium: 'text-blue-500',
  high: 'text-orange-500',
  critical: 'text-red-500',
};

const statusIcons: Record<string, string> = {
  pending: '⏳',
  in_progress: '⚙️',
  completed: '✅',
  failed: '❌',
  cancelled: '⛔',
};

export const TaskList: React.FC<TaskListProps> = ({
  runId,
  status: filterStatus,
  onTaskClick,
  autoRefresh = true,
  refreshInterval = 5000,
}) => {
  const [tasks, setTasks] = useState<TaskModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    total: 0,
    completed: 0,
    in_progress: 0,
    failed: 0,
    pending: 0,
  });

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (runId) params.append('run_id', runId);
      if (filterStatus) params.append('status', filterStatus);

      const response = await fetch(`/api/v1/tasks?${params}`);
      if (!response.ok) throw new Error('Failed to fetch tasks');

      const data = await response.json();
      setTasks(data.tasks);
      setStats({
        total: data.total,
        completed: data.completed,
        in_progress: data.in_progress,
        failed: data.failed,
        pending: data.pending,
      });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();

    if (autoRefresh) {
      const interval = setInterval(fetchTasks, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [runId, filterStatus, autoRefresh, refreshInterval]);

  const getProgressColor = (progress: number): string => {
    if (progress === 1) return 'bg-green-500';
    if (progress >= 0.75) return 'bg-blue-500';
    if (progress >= 0.5) return 'bg-yellow-500';
    return 'bg-gray-400';
  };

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h`;
  };

  const renderTaskItem = (task: TaskModel) => (
    <div
      key={task.task_id}
      className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => onTaskClick?.(task)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">{statusIcons[task.status]}</span>
            <h3 className="font-semibold text-gray-900">{task.title}</h3>
            <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[task.status]}`}>
              {task.status}
            </span>
          </div>
          {task.description && (
            <p className="text-sm text-gray-600 line-clamp-2">{task.description}</p>
          )}
        </div>
        <div className={`text-lg font-bold ${priorityColors[task.priority]}`}>
          {task.priority === 'critical' && '🔴'}
          {task.priority === 'high' && '🟠'}
          {task.priority === 'medium' && '🟡'}
          {task.priority === 'low' && '🟢'}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-600">Progress</span>
          <span className="text-xs font-semibold text-gray-700">
            {Math.round(task.progress * 100)}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all ${getProgressColor(task.progress)}`}
            style={{ width: `${task.progress * 100}%` }}
          />
        </div>
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 mb-3">
        {task.estimated_duration_seconds && (
          <div>
            ⏱️ Est. {formatDuration(task.estimated_duration_seconds)}
          </div>
        )}
        {task.started_at && (
          <div>
            Started {new Date(task.started_at).toLocaleTimeString()}
          </div>
        )}
        {task.completed_at && (
          <div>
            Completed {new Date(task.completed_at).toLocaleTimeString()}
          </div>
        )}
      </div>

      {/* Tags */}
      {task.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {task.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Dependencies */}
      {(task.depends_on.length > 0 || task.blocks.length > 0) && (
        <div className="text-xs text-gray-600 space-y-1">
          {task.depends_on.length > 0 && (
            <div>
              ⬅️ Depends on {task.depends_on.length} task{task.depends_on.length !== 1 ? 's' : ''}
            </div>
          )}
          {task.blocks.length > 0 && (
            <div>
              ➡️ Blocks {task.blocks.length} task{task.blocks.length !== 1 ? 's' : ''}
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {task.error && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          {task.error}
        </div>
      )}
    </div>
  );

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-900">Tasks</h2>
          <button
            onClick={fetchTasks}
            disabled={loading}
            className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-5 gap-2 text-center">
          <div className="p-2 bg-gray-50 rounded">
            <div className="text-lg font-bold text-gray-900">{stats.total}</div>
            <div className="text-xs text-gray-600">Total</div>
          </div>
          <div className="p-2 bg-blue-50 rounded">
            <div className="text-lg font-bold text-blue-600">{stats.in_progress}</div>
            <div className="text-xs text-gray-600">In Progress</div>
          </div>
          <div className="p-2 bg-green-50 rounded">
            <div className="text-lg font-bold text-green-600">{stats.completed}</div>
            <div className="text-xs text-gray-600">Completed</div>
          </div>
          <div className="p-2 bg-red-50 rounded">
            <div className="text-lg font-bold text-red-600">{stats.failed}</div>
            <div className="text-xs text-gray-600">Failed</div>
          </div>
          <div className="p-2 bg-yellow-50 rounded">
            <div className="text-lg font-bold text-yellow-600">{stats.pending}</div>
            <div className="text-xs text-gray-600">Pending</div>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-3 bg-red-100 border-b border-red-300 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Tasks Container */}
      <div className="flex-1 overflow-y-auto p-4">
        {tasks.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            {loading ? 'Loading tasks...' : 'No tasks found'}
          </div>
        ) : (
          <div className="grid gap-3">
            {tasks.map(renderTaskItem)}
          </div>
        )}
      </div>
    </div>
  );
};

export default TaskList;
