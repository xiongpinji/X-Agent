// mobile/src/store/__tests__/taskStore.test.ts
// 任务列表端点契约测试（对照 backend/app/api/tasks_ui.py）:
//   GET /api/v1/tasks?limit=&offset= → TaskListResponse {tasks, total, ...}
//   TaskModel(task_id/created_at snake_case) → 本地 Task(id/createdAt camelCase) 映射

import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import * as SecureStore from 'expo-secure-store';

jest.mock('../../store/authStore', () => ({
  useAuthStore: {
    getState: () => ({
      refreshAccessToken: jest.fn(() => Promise.resolve()),
      logout: jest.fn(() => Promise.resolve()),
    }),
  },
}));

import { useTaskStore } from '../taskStore';
import { API_KEY_STORAGE_KEY, DEFAULT_API_BASE_URL } from '../../config/env';

const mockedGetItem = jest.mocked(SecureStore.getItemAsync);
type FetchLike = (url: string, init: Record<string, any>) => Promise<any>;
const mockFetch = jest.fn<FetchLike>();
(global as any).fetch = mockFetch;

function setStore(entries: Record<string, string | null>): void {
  const map = new Map(Object.entries(entries));
  mockedGetItem.mockImplementation(async (key: string) => map.get(key) ?? null);
}

describe('taskStore 契约对齐', () => {
  beforeEach(() => {
    jest.resetAllMocks();
    (global as any).fetch = mockFetch;
    useTaskStore.getState().clearError();
    useTaskStore.setState({ tasks: [], selectedTask: undefined, loading: false });
    setStore({});
  });

  it('fetchTasks: GET /api/v1/tasks?limit&offset + x-api-key 头 + snake_case 字段映射', async () => {
    setStore({ [API_KEY_STORAGE_KEY]: 'sk-tasks' });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          tasks: [
            {
              task_id: 'task-001',
              title: 'Fix login bug',
              description: 'OAuth redirect loop',
              status: 'in_progress',
              priority: 'critical',
              created_at: '2026-09-01T10:00:00Z',
              metadata: { source: 'mobile' },
            },
          ],
          total: 1,
          pending: 0,
          in_progress: 1,
          completed: 0,
          failed: 0,
        }),
    });

    await useTaskStore.getState().fetchTasks(1, 20);

    // 端点契约: URL / method / headers
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${DEFAULT_API_BASE_URL}/api/v1/tasks?limit=20&offset=0`);
    expect(init.method).toBe('GET');
    expect(init.headers['x-api-key']).toBe('sk-tasks');
    expect(init.headers['Content-Type']).toBe('application/json');

    // 字段映射: task_id→id, in_progress→running, critical→high
    const { tasks } = useTaskStore.getState();
    expect(tasks).toHaveLength(1);
    expect(tasks[0].id).toBe('task-001');
    expect(tasks[0].title).toBe('Fix login bug');
    expect(tasks[0].status).toBe('running');
    expect(tasks[0].priority).toBe('high');
    expect(tasks[0].parameters).toEqual({ source: 'mobile' });
    expect(tasks[0].createdAt).toEqual(new Date('2026-09-01T10:00:00Z'));
  });

  it('fetchTasks 第 2 页映射 offset=20', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ tasks: [], total: 0 }),
    });

    await useTaskStore.getState().fetchTasks(2, 20);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${DEFAULT_API_BASE_URL}/api/v1/tasks?limit=20&offset=20`);
  });

  it('createTask: POST /api/v1/tasks，TaskCreateRequest 请求体', async () => {
    setStore({ [API_KEY_STORAGE_KEY]: 'sk-tasks' });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      text: async () =>
        JSON.stringify({
          task_id: 'task-002',
          title: 'New task',
          description: 'desc',
          status: 'pending',
          priority: 'high',
          created_at: '2026-09-02T08:00:00Z',
        }),
    });

    await useTaskStore.getState().createTask({
      title: 'New task',
      description: 'desc',
      status: 'pending',
      priority: 'high',
      parameters: { k: 'v' },
      syncStatus: 'pending',
    });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${DEFAULT_API_BASE_URL}/api/v1/tasks`);
    expect(init.method).toBe('POST');
    expect(init.headers['x-api-key']).toBe('sk-tasks');
    expect(JSON.parse(init.body)).toEqual({
      title: 'New task',
      description: 'desc',
      priority: 'high',
      metadata: { k: 'v' },
    });

    expect(useTaskStore.getState().tasks[0].id).toBe('task-002');
  });

  it('fetchTasks 非 2xx 时写入 error，不静默假成功', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      text: async () => JSON.stringify({ error: { code: 'FORBIDDEN' } }),
    });

    await useTaskStore.getState().fetchTasks();

    expect(useTaskStore.getState().tasks).toHaveLength(0);
    expect(useTaskStore.getState().error).toContain('403');
  });
});
