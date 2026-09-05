// mobile/src/store/taskStore.ts
// 任务状态管理
//
// 契约对齐 backend/app/api/tasks_ui.py（前缀 /api/v1/tasks）:
//   GET    /api/v1/tasks?limit=&offset=&status=&run_id=
//     → TaskListResponse {tasks: TaskModel[], total, pending, in_progress, completed, failed}
//   POST   /api/v1/tasks                     body TaskCreateRequest → TaskModel (201)
//   GET    /api/v1/tasks/{task_id}           → TaskModel
//   PUT    /api/v1/tasks/{task_id}           body TaskUpdateRequest → TaskModel
//   DELETE /api/v1/tasks/{task_id}           → 204
// TaskModel 字段为 snake_case（task_id/created_at/...），此处做本地 camelCase 映射。

import { create } from 'zustand';
import { Task } from '../types';
import { apiClient } from '../services/apiClient';

/** 后端 TaskModel（snake_case 原样） */
interface BackendTask {
  task_id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  priority: 'low' | 'medium' | 'high' | 'critical';
  progress?: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  metadata?: Record<string, any>;
  tags?: string[];
  result?: any;
  error?: string | null;
  run_id?: string | null;
}

interface BackendTaskListResponse {
  tasks: BackendTask[];
  total: number;
  pending: number;
  in_progress: number;
  completed: number;
  failed: number;
}

/** 后端 TaskModel → 本地 Task 类型 */
function mapTask(t: BackendTask): Task {
  return {
    id: t.task_id,
    title: t.title,
    description: t.description,
    // 后端 in_progress/cancelled 折叠到本地 running/failed
    status:
      t.status === 'in_progress'
        ? 'running'
        : t.status === 'cancelled'
        ? 'failed'
        : t.status,
    // 后端 critical 折叠到本地 high
    priority: t.priority === 'critical' ? 'high' : t.priority,
    createdAt: new Date(t.created_at),
    updatedAt: new Date(t.created_at),
    startedAt: t.started_at ? new Date(t.started_at) : undefined,
    completedAt: t.completed_at ? new Date(t.completed_at) : undefined,
    parameters: t.metadata ?? {},
    result: t.result ?? undefined,
    error: t.error ?? undefined,
    syncStatus: 'synced',
  };
}

/** 本地 Task 子集 → TaskUpdateRequest */
function toUpdateRequest(updates: Partial<Task>): Record<string, any> {
  const body: Record<string, any> = {};
  if (updates.title !== undefined) body.title = updates.title;
  if (updates.description !== undefined) body.description = updates.description;
  if (updates.status !== undefined) {
    body.status =
      updates.status === 'running'
        ? 'in_progress'
        : updates.status === 'failed'
        ? 'failed'
        : updates.status;
  }
  if (updates.priority !== undefined) body.priority = updates.priority;
  if (updates.parameters !== undefined) body.metadata = updates.parameters;
  if (updates.result !== undefined) body.result = updates.result;
  if (updates.error !== undefined) body.error = updates.error;
  return body;
}

interface TaskStore {
  tasks: Task[];
  selectedTask?: Task;
  loading: boolean;
  error?: string;

  // Actions
  fetchTasks: (page?: number, pageSize?: number) => Promise<void>;
  fetchTaskById: (id: string) => Promise<void>;
  createTask: (task: Omit<Task, 'id' | 'createdAt' | 'updatedAt'>) => Promise<void>;
  updateTask: (id: string, updates: Partial<Task>) => Promise<void>;
  deleteTask: (id: string) => Promise<void>;
  setSelectedTask: (task?: Task) => void;
  clearError: () => void;
}

export const useTaskStore = create<TaskStore>((set, get) => ({
  tasks: [],
  loading: false,

  fetchTasks: async (page = 1, pageSize = 20) => {
    set({ loading: true, error: undefined });
    try {
      // 后端使用 limit/offset 分页（无 page/pageSize 参数）
      const offset = (page - 1) * pageSize;
      const response = await apiClient.get<BackendTaskListResponse>(
        `/api/v1/tasks`,
        { params: { limit: pageSize, offset } }
      );
      set({ tasks: response.tasks.map(mapTask), loading: false });
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  fetchTaskById: async (id: string) => {
    set({ loading: true, error: undefined });
    try {
      const task = await apiClient.get<BackendTask>(`/api/v1/tasks/${id}`);
      set({ selectedTask: mapTask(task), loading: false });
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  createTask: async (task: Omit<Task, 'id' | 'createdAt' | 'updatedAt'>) => {
    set({ loading: true, error: undefined });
    try {
      // TaskCreateRequest: {title, description, priority, depends_on, tags, metadata, ...}
      const newTask = await apiClient.post<BackendTask>('/api/v1/tasks', {
        title: task.title,
        description: task.description,
        priority: task.priority === 'high' ? 'high' : task.priority,
        metadata: task.parameters ?? {},
      });
      set((state) => ({
        tasks: [mapTask(newTask), ...state.tasks],
        loading: false,
      }));
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  updateTask: async (id: string, updates: Partial<Task>) => {
    set({ loading: true, error: undefined });
    try {
      const updated = await apiClient.put<BackendTask>(
        `/api/v1/tasks/${id}`,
        toUpdateRequest(updates)
      );
      const mapped = mapTask(updated);
      set((state) => ({
        tasks: state.tasks.map((t) => (t.id === id ? mapped : t)),
        selectedTask: state.selectedTask?.id === id ? mapped : state.selectedTask,
        loading: false,
      }));
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  deleteTask: async (id: string) => {
    set({ loading: true, error: undefined });
    try {
      await apiClient.delete(`/api/v1/tasks/${id}`);
      set((state) => ({
        tasks: state.tasks.filter((t) => t.id !== id),
        selectedTask: state.selectedTask?.id === id ? undefined : state.selectedTask,
        loading: false,
      }));
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  setSelectedTask: (task?: Task) => {
    set({ selectedTask: task });
  },

  clearError: () => {
    set({ error: undefined });
  },
}));
