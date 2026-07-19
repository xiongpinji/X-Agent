// mobile/src/types/index.ts
// 核心类型定义

export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  priority: 'low' | 'medium' | 'high';
  createdAt: Date;
  updatedAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  parameters: Record<string, any>;
  result?: Record<string, any>;
  error?: string;
  syncStatus: 'synced' | 'pending' | 'failed';
}

export interface WorkflowRun {
  id: string;
  workflowId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  nodes: WorkflowNode[];
  startedAt: Date;
  completedAt?: Date;
  duration?: number;
  result?: Record<string, any>;
  error?: string;
  syncStatus: 'synced' | 'pending' | 'failed';
}

export interface WorkflowNode {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  output?: Record<string, any>;
  error?: string;
  duration?: number;
}

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  roles: string[];
  permissions: string[];
}

export interface AuthState {
  isAuthenticated: boolean;
  user?: User;
  token?: string;
  refreshToken?: string;
  expiresAt?: Date;
  biometricEnabled: boolean;
}

export interface SyncQueue {
  id: string;
  action: 'create' | 'update' | 'delete';
  resource: 'task' | 'workflow' | 'memory';
  resourceId: string;
  payload: Record<string, any>;
  timestamp: Date;
  retryCount: number;
  status: 'pending' | 'syncing' | 'synced' | 'failed';
  error?: string;
}

export interface SystemMetrics {
  timestamp: Date;
  cpuUsage: number;
  memoryUsage: number;
  batteryLevel: number;
  networkStatus: 'online' | 'offline' | 'slow';
  syncQueueSize: number;
  lastSyncTime?: Date;
}

export interface PushNotification {
  id: string;
  type: 'task_update' | 'workflow_progress' | 'alert' | 'message';
  title: string;
  body: string;
  data: Record<string, any>;
  deepLink?: string;
  badge?: number;
  sound?: string;
  priority: 'high' | 'normal';
  ttl?: number;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: Date;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}
