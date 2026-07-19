// mobile/src/services/syncManager.ts
// 离线同步管理

import { database } from './database';
import { apiClient } from './apiClient';
import { SyncQueue, Task, WorkflowRun } from '../types';
import NetInfo from '@react-native-community/netinfo';
import { v4 as uuidv4 } from 'uuid';

interface SyncStrategy {
  onWiFi: {
    interval: number;
    maxPayloadSize: number;
    includeMedia: boolean;
  };
  onCellular: {
    interval: number;
    maxPayloadSize: number;
    includeMedia: boolean;
  };
  offline: {
    queueOperations: boolean;
    maxQueueSize: number;
    retryInterval: number;
  };
}

class SyncManager {
  private syncStrategy: SyncStrategy = {
    onWiFi: {
      interval: 5 * 60 * 1000, // 5分钟
      maxPayloadSize: 50 * 1024 * 1024, // 50MB
      includeMedia: true,
    },
    onCellular: {
      interval: 30 * 60 * 1000, // 30分钟
      maxPayloadSize: 5 * 1024 * 1024, // 5MB
      includeMedia: false,
    },
    offline: {
      queueOperations: true,
      maxQueueSize: 100,
      retryInterval: 60 * 1000, // 1分钟
    },
  };

  private syncTimer: NodeJS.Timeout | null = null;
  private lastSyncTime = 0;
  private isSyncing = false;

  async initialize(): Promise<void> {
    // 监听网络状态变化
    NetInfo.addEventListener((state) => {
      this.handleNetworkChange(state);
    });

    // 启动定期同步
    this.startPeriodicSync();
  }

  private handleNetworkChange(state: any): void {
    if (state.isConnected) {
      console.log('Network connected, starting sync');
      this.triggerSync();
    } else {
      console.log('Network disconnected, pausing sync');
      this.stopPeriodicSync();
    }
  }

  private startPeriodicSync(): void {
    const interval = this.getSyncInterval();
    this.syncTimer = setInterval(() => {
      this.triggerSync();
    }, interval);
  }

  private stopPeriodicSync(): void {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
      this.syncTimer = null;
    }
  }

  private getSyncInterval(): number {
    // 根据网络类型返回同步间隔
    return this.syncStrategy.onWiFi.interval;
  }

  async triggerSync(): Promise<void> {
    if (this.isSyncing) return;

    const now = Date.now();
    const interval = this.getSyncInterval();

    if (now - this.lastSyncTime < interval) {
      return;
    }

    this.isSyncing = true;
    try {
      await this.performSync();
      this.lastSyncTime = now;
    } catch (error) {
      console.error('Sync error:', error);
    } finally {
      this.isSyncing = false;
    }
  }

  private async performSync(): Promise<void> {
    try {
      // 1. 同步本地更改到服务器
      await this.syncLocalChanges();

      // 2. 从服务器拉取更新
      await this.pullRemoteChanges();

      // 3. 处理冲突
      await this.resolveConflicts();
    } catch (error) {
      console.error('Perform sync error:', error);
      throw error;
    }
  }

  private async syncLocalChanges(): Promise<void> {
    const queue = await database.getSyncQueue('pending', 50);

    for (const item of queue) {
      try {
        await this.syncQueueItem(item);
        await database.updateSyncQueueItem(item.id, 'synced');
      } catch (error) {
        const retryCount = item.retryCount + 1;
        if (retryCount > 3) {
          await database.updateSyncQueueItem(item.id, 'failed', String(error));
        } else {
          await database.updateSyncQueueItem(item.id, 'pending');
        }
      }
    }
  }

  private async syncQueueItem(item: SyncQueue): Promise<void> {
    const { action, resource, resourceId, payload } = item;

    switch (action) {
      case 'create':
        await apiClient.post(`/${resource}`, payload);
        break;
      case 'update':
        await apiClient.put(`/${resource}/${resourceId}`, payload);
        break;
      case 'delete':
        await apiClient.delete(`/${resource}/${resourceId}`);
        break;
    }
  }

  private async pullRemoteChanges(): Promise<void> {
    try {
      const lastSyncTime = await database.getCache('lastSyncTime');
      const since = lastSyncTime || new Date(0).toISOString();

      const response = await apiClient.get('/sync', {
        params: { since },
      });

      // 更新本地数据
      if (response.tasks) {
        for (const task of response.tasks) {
          await database.updateTask(task.id, task);
        }
      }

      if (response.workflows) {
        for (const workflow of response.workflows) {
          // 更新工作流
        }
      }

      // 更新同步时间
      await database.setCache('lastSyncTime', new Date().toISOString());
    } catch (error) {
      console.error('Pull remote changes error:', error);
      throw error;
    }
  }

  private async resolveConflicts(): Promise<void> {
    // 实现冲突解决逻辑
    // 可以使用服务器优先、本地优先或合并策略
  }

  // 添加离线操作到队列
  async queueOperation(
    action: 'create' | 'update' | 'delete',
    resource: 'task' | 'workflow' | 'memory',
    resourceId: string,
    payload: Record<string, any>
  ): Promise<void> {
    const item: SyncQueue = {
      id: uuidv4(),
      action,
      resource,
      resourceId,
      payload,
      timestamp: new Date(),
      retryCount: 0,
      status: 'pending',
    };

    await database.addToSyncQueue(item);
  }

  // 获取同步状态
  async getSyncStatus(): Promise<{
    isSyncing: boolean;
    queueSize: number;
    lastSyncTime?: Date;
  }> {
    const queue = await database.getSyncQueue('pending');
    const lastSyncTime = await database.getCache('lastSyncTime');

    return {
      isSyncing: this.isSyncing,
      queueSize: queue.length,
      lastSyncTime: lastSyncTime ? new Date(lastSyncTime) : undefined,
    };
  }

  destroy(): void {
    this.stopPeriodicSync();
  }
}

export const syncManager = new SyncManager();
