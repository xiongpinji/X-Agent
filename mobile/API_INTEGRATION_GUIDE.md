# X-Agent 移动端 - 后端API集成指南

**版本：** v1.0  
**日期：** 2026-05-27

---

## 1. API基础配置

### 1.1 API端点

```typescript
// src/config/api.ts
export const API_CONFIG = {
  // 开发环境
  development: {
    baseURL: 'http://localhost:8000/api',
    wsURL: 'ws://localhost:8000/ws',
  },
  
  // 测试环境
  staging: {
    baseURL: 'https://staging-api.xagent.local/api',
    wsURL: 'wss://staging-api.xagent.local/ws',
  },
  
  // 生产环境
  production: {
    baseURL: 'https://api.xagent.local/api',
    wsURL: 'wss://api.xagent.local/ws',
  },
};

export const getApiConfig = () => {
  const env = process.env.NODE_ENV || 'development';
  return API_CONFIG[env as keyof typeof API_CONFIG];
};
```

---

## 2. 认证API

### 2.1 登录

```typescript
// POST /auth/login
interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  token: string;
  refreshToken: string;
  expiresAt: string;
  user: User;
}

// 使用示例
const response = await apiClient.post<LoginResponse>('/auth/login', {
  email: 'user@example.com',
  password: 'password123',
});
```

### 2.2 刷新Token

```typescript
// POST /auth/refresh
interface RefreshRequest {
  refreshToken: string;
}

interface RefreshResponse {
  token: string;
  expiresAt: string;
}

// 使用示例
const response = await apiClient.post<RefreshResponse>('/auth/refresh', {
  refreshToken: refreshToken,
});
```

### 2.3 登出

```typescript
// POST /auth/logout
interface LogoutRequest {
  token: string;
}

// 使用示例
await apiClient.post('/auth/logout', {
  token: token,
});
```

### 2.4 生物识别认证

```typescript
// POST /auth/biometric
interface BiometricAuthRequest {
  biometricToken: string;
  deviceId: string;
}

interface BiometricAuthResponse {
  token: string;
  refreshToken: string;
  expiresAt: string;
}

// 使用示例
const response = await apiClient.post<BiometricAuthResponse>('/auth/biometric', {
  biometricToken: token,
  deviceId: deviceId,
});
```

---

## 3. 任务API

### 3.1 获取任务列表

```typescript
// GET /tasks?page=1&pageSize=20&status=pending&priority=high
interface GetTasksRequest {
  page?: number;
  pageSize?: number;
  status?: string;
  priority?: string;
  search?: string;
}

interface GetTasksResponse {
  items: Task[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

// 使用示例
const response = await apiClient.get<GetTasksResponse>('/tasks', {
  params: {
    page: 1,
    pageSize: 20,
    status: 'pending',
  },
});
```

### 3.2 获取单个任务

```typescript
// GET /tasks/:id
interface GetTaskResponse {
  task: Task;
}

// 使用示例
const response = await apiClient.get<GetTaskResponse>('/tasks/task-123');
```

### 3.3 创建任务

```typescript
// POST /tasks
interface CreateTaskRequest {
  title: string;
  description: string;
  priority: 'low' | 'medium' | 'high';
  parameters: Record<string, any>;
}

interface CreateTaskResponse {
  task: Task;
}

// 使用示例
const response = await apiClient.post<CreateTaskResponse>('/tasks', {
  title: 'New Task',
  description: 'Task description',
  priority: 'high',
  parameters: {},
});
```

### 3.4 更新任务

```typescript
// PUT /tasks/:id
interface UpdateTaskRequest {
  title?: string;
  description?: string;
  status?: string;
  priority?: string;
  parameters?: Record<string, any>;
}

interface UpdateTaskResponse {
  task: Task;
}

// 使用示例
const response = await apiClient.put<UpdateTaskResponse>('/tasks/task-123', {
  status: 'completed',
});
```

### 3.5 删除任务

```typescript
// DELETE /tasks/:id
interface DeleteTaskResponse {
  success: boolean;
}

// 使用示例
const response = await apiClient.delete<DeleteTaskResponse>('/tasks/task-123');
```

---

## 4. 工作流API

### 4.1 获取工作流列表

```typescript
// GET /workflows?page=1&pageSize=20
interface GetWorkflowsResponse {
  items: Workflow[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

// 使用示例
const response = await apiClient.get<GetWorkflowsResponse>('/workflows');
```

### 4.2 启动工作流

```typescript
// POST /workflows/:id/run
interface StartWorkflowRequest {
  parameters?: Record<string, any>;
}

interface StartWorkflowResponse {
  run: WorkflowRun;
}

// 使用示例
const response = await apiClient.post<StartWorkflowResponse>('/workflows/workflow-123/run', {
  parameters: {},
});
```

### 4.3 获取工作流运行状态

```typescript
// GET /workflows/:id/runs/:runId
interface GetWorkflowRunResponse {
  run: WorkflowRun;
}

// 使用示例
const response = await apiClient.get<GetWorkflowRunResponse>(
  '/workflows/workflow-123/runs/run-456'
);
```

### 4.4 监听工作流实时更新

```typescript
// WebSocket: /ws/workflows/:id/runs/:runId
interface WorkflowRunUpdate {
  type: 'progress' | 'node_update' | 'completed' | 'error';
  data: any;
}

// 使用示例
const ws = apiClient.connectWebSocket(
  '/ws/workflows/workflow-123/runs/run-456',
  (data: WorkflowRunUpdate) => {
    console.log('Workflow update:', data);
  }
);
```

---

## 5. 同步API

### 5.1 获取增量更新

```typescript
// GET /sync?since=2026-05-27T00:00:00Z
interface GetSyncResponse {
  tasks: Task[];
  workflows: WorkflowRun[];
  timestamp: string;
}

// 使用示例
const lastSyncTime = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
const response = await apiClient.get<GetSyncResponse>('/sync', {
  params: { since: lastSyncTime },
});
```

### 5.2 批量同步操作

```typescript
// POST /sync/batch
interface SyncOperation {
  action: 'create' | 'update' | 'delete';
  resource: 'task' | 'workflow';
  resourceId: string;
  payload: Record<string, any>;
}

interface BatchSyncRequest {
  operations: SyncOperation[];
}

interface BatchSyncResponse {
  results: Array<{
    operationId: string;
    success: boolean;
    error?: string;
  }>;
}

// 使用示例
const response = await apiClient.post<BatchSyncResponse>('/sync/batch', {
  operations: [
    {
      action: 'create',
      resource: 'task',
      resourceId: 'task-123',
      payload: { title: 'New Task' },
    },
  ],
});
```

---

## 6. 推送通知API

### 6.1 注册推送Token

```typescript
// POST /notifications/register-token
interface RegisterTokenRequest {
  token: string;
  platform: 'ios' | 'android';
  deviceId: string;
}

interface RegisterTokenResponse {
  success: boolean;
}

// 使用示例
const response = await apiClient.post<RegisterTokenResponse>(
  '/notifications/register-token',
  {
    token: pushToken,
    platform: Platform.OS as 'ios' | 'android',
    deviceId: deviceId,
  }
);
```

### 6.2 获取通知历史

```typescript
// GET /notifications?page=1&pageSize=20
interface GetNotificationsResponse {
  items: PushNotification[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

// 使用示例
const response = await apiClient.get<GetNotificationsResponse>('/notifications');
```

### 6.3 标记通知为已读

```typescript
// PUT /notifications/:id/read
interface MarkNotificationReadResponse {
  success: boolean;
}

// 使用示例
const response = await apiClient.put<MarkNotificationReadResponse>(
  '/notifications/notification-123/read'
);
```

---

## 7. 用户API

### 7.1 获取用户信息

```typescript
// GET /users/me
interface GetUserResponse {
  user: User;
}

// 使用示例
const response = await apiClient.get<GetUserResponse>('/users/me');
```

### 7.2 更新用户信息

```typescript
// PUT /users/me
interface UpdateUserRequest {
  name?: string;
  avatar?: string;
  preferences?: Record<string, any>;
}

interface UpdateUserResponse {
  user: User;
}

// 使用示例
const response = await apiClient.put<UpdateUserResponse>('/users/me', {
  name: 'New Name',
});
```

### 7.3 修改密码

```typescript
// POST /users/me/change-password
interface ChangePasswordRequest {
  oldPassword: string;
  newPassword: string;
}

interface ChangePasswordResponse {
  success: boolean;
}

// 使用示例
const response = await apiClient.post<ChangePasswordResponse>(
  '/users/me/change-password',
  {
    oldPassword: 'old123',
    newPassword: 'new456',
  }
);
```

---

## 8. 错误处理

### 8.1 错误类型

```typescript
// src/services/errors.ts
export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
    message: string,
    public details?: any
  ) {
    super(message);
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
  }
}

export class TimeoutError extends Error {
  constructor(message: string) {
    super(message);
  }
}
```

### 8.2 错误处理示例

```typescript
try {
  const response = await apiClient.get('/tasks');
} catch (error) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      // 处理未授权
      await useAuthStore.getState().logout();
    } else if (error.status === 403) {
      // 处理禁止访问
      console.error('Access denied');
    } else if (error.status === 500) {
      // 处理服务器错误
      console.error('Server error');
    }
  } else if (error instanceof NetworkError) {
    // 处理网络错误
    console.error('Network error');
  } else if (error instanceof TimeoutError) {
    // 处理超时
    console.error('Request timeout');
  }
}
```

---

## 9. 请求拦截器

### 9.1 添加认证头

```typescript
// src/services/apiClient.ts
apiClient.interceptors.request.use(
  async (config) => {
    const token = await SecureStore.getItemAsync('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);
```

### 9.2 处理响应错误

```typescript
apiClient.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token过期，尝试刷新
      await useAuthStore.getState().refreshToken();
    }
    return Promise.reject(error);
  }
);
```

---

## 10. 性能优化

### 10.1 请求缓存

```typescript
// src/services/cache.ts
class RequestCache {
  private cache = new Map<string, { data: any; timestamp: number }>();
  private ttl = 5 * 60 * 1000; // 5分钟

  set(key: string, data: any): void {
    this.cache.set(key, { data, timestamp: Date.now() });
  }

  get(key: string): any | null {
    const item = this.cache.get(key);
    if (!item) return null;

    if (Date.now() - item.timestamp > this.ttl) {
      this.cache.delete(key);
      return null;
    }

    return item.data;
  }

  clear(): void {
    this.cache.clear();
  }
}

export const requestCache = new RequestCache();
```

### 10.2 请求去重

```typescript
// src/services/deduplication.ts
class RequestDeduplication {
  private pending = new Map<string, Promise<any>>();

  async execute<T>(key: string, fn: () => Promise<T>): Promise<T> {
    if (this.pending.has(key)) {
      return this.pending.get(key)!;
    }

    const promise = fn().finally(() => {
      this.pending.delete(key);
    });

    this.pending.set(key, promise);
    return promise;
  }
}

export const deduplication = new RequestDeduplication();
```

---

## 11. 测试API集成

### 11.1 Mock API

```typescript
// src/__mocks__/apiClient.ts
export const mockApiClient = {
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  connectWebSocket: jest.fn(),
};
```

### 11.2 测试示例

```typescript
// src/__tests__/taskService.test.ts
import { taskService } from '../services/taskService';
import { mockApiClient } from '../__mocks__/apiClient';

jest.mock('../services/apiClient', () => ({
  apiClient: mockApiClient,
}));

describe('TaskService', () => {
  it('should fetch tasks', async () => {
    mockApiClient.get.mockResolvedValue({
      items: [{ id: '1', title: 'Task 1' }],
    });

    const tasks = await taskService.getTasks();
    expect(tasks).toHaveLength(1);
    expect(mockApiClient.get).toHaveBeenCalledWith('/tasks');
  });
});
```

---

## 12. 常见问题

### Q1: 如何处理Token过期？

```typescript
// 在响应拦截器中自动刷新Token
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await useAuthStore.getState().refreshToken();
      // 重试原始请求
      return apiClient(error.config);
    }
    return Promise.reject(error);
  }
);
```

### Q2: 如何处理网络离线？

```typescript
// 使用NetInfo监听网络状态
import NetInfo from '@react-native-community/netinfo';

NetInfo.addEventListener((state) => {
  if (!state.isConnected) {
    // 切换到离线模式
    syncManager.pauseSync();
  } else {
    // 恢复同步
    syncManager.resumeSync();
  }
});
```

### Q3: 如何优化API请求？

```typescript
// 1. 使用增量同步
const lastSyncTime = await database.getCache('lastSyncTime');
const response = await apiClient.get('/sync', {
  params: { since: lastSyncTime },
});

// 2. 批量请求
const response = await apiClient.post('/sync/batch', {
  operations: batchOperations,
});

// 3. 请求缓存
const cachedData = requestCache.get(cacheKey);
if (cachedData) return cachedData;
```
