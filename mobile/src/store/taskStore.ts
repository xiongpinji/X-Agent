// mobile/src/store/taskStore.ts
// 任务状态管理

import { create } from 'zustand';
import { Task, PaginatedResponse } from '../types';
import { apiClient } from '../services/apiClient';

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
      const response = await apiClient.get<PaginatedResponse<Task>>(
        `/tasks?page=${page}&pageSize=${pageSize}`
      );
      set({ tasks: response.items, loading: false });
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  fetchTaskById: async (id: string) => {
    set({ loading: true, error: undefined });
    try {
      const task = await apiClient.get<Task>(`/tasks/${id}`);
      set({ selectedTask: task, loading: false });
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  createTask: async (task: Omit<Task, 'id' | 'createdAt' | 'updatedAt'>) => {
    set({ loading: true, error: undefined });
    try {
      const newTask = await apiClient.post<Task>('/tasks', task);
      set((state) => ({
        tasks: [newTask, ...state.tasks],
        loading: false,
      }));
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  updateTask: async (id: string, updates: Partial<Task>) => {
    set({ loading: true, error: undefined });
    try {
      const updated = await apiClient.put<Task>(`/tasks/${id}`, updates);
      set((state) => ({
        tasks: state.tasks.map((t) => (t.id === id ? updated : t)),
        selectedTask: state.selectedTask?.id === id ? updated : state.selectedTask,
        loading: false,
      }));
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  deleteTask: async (id: string) => {
    set({ loading: true, error: undefined });
    try {
      await apiClient.delete(`/tasks/${id}`);
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
