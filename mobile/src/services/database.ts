// mobile/src/services/database.ts
// SQLite数据库管理

import * as SQLite from 'expo-sqlite';
import { Task, WorkflowRun, SyncQueue } from '../types';

const DB_NAME = 'xagent.db';

class Database {
  private db: SQLite.SQLiteDatabase | null = null;

  async initialize(): Promise<void> {
    try {
      this.db = await SQLite.openDatabaseAsync(DB_NAME);
      await this.createTables();
    } catch (error) {
      console.error('Database initialization error:', error);
      throw error;
    }
  }

  private async createTables(): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    const queries = [
      // 任务表
      `CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL,
        priority TEXT,
        parameters JSON,
        result JSON,
        error TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        started_at DATETIME,
        completed_at DATETIME,
        sync_status TEXT,
        sync_timestamp DATETIME
      );`,

      // 工作流运行表
      `CREATE TABLE IF NOT EXISTS workflow_runs (
        id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        status TEXT NOT NULL,
        progress INTEGER,
        nodes JSON,
        result JSON,
        error TEXT,
        started_at DATETIME,
        completed_at DATETIME,
        sync_status TEXT,
        sync_timestamp DATETIME
      );`,

      // 同步队列表
      `CREATE TABLE IF NOT EXISTS sync_queue (
        id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        resource TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        payload JSON,
        timestamp DATETIME,
        retry_count INTEGER DEFAULT 0,
        status TEXT,
        error TEXT
      );`,

      // 缓存表
      `CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        value JSON,
        expires_at DATETIME,
        created_at DATETIME
      );`,

      // 索引
      `CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);`,
      `CREATE INDEX IF NOT EXISTS idx_tasks_sync_status ON tasks(sync_status);`,
      `CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);`,
      `CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status);`,
    ];

    for (const query of queries) {
      await this.db.execAsync(query);
    }
  }

  // 任务操作
  async insertTask(task: Task): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    await this.db.runAsync(
      `INSERT INTO tasks (id, title, description, status, priority, parameters, result, error, created_at, updated_at, started_at, completed_at, sync_status, sync_timestamp)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        task.id,
        task.title,
        task.description,
        task.status,
        task.priority,
        JSON.stringify(task.parameters),
        task.result ? JSON.stringify(task.result) : null,
        task.error,
        task.createdAt.toISOString(),
        task.updatedAt.toISOString(),
        task.startedAt?.toISOString(),
        task.completedAt?.toISOString(),
        task.syncStatus,
        new Date().toISOString(),
      ]
    );
  }

  async updateTask(id: string, updates: Partial<Task>): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    const fields: string[] = [];
    const values: any[] = [];

    Object.entries(updates).forEach(([key, value]) => {
      if (key === 'parameters' || key === 'result') {
        fields.push(`${key} = ?`);
        values.push(JSON.stringify(value));
      } else if (key === 'createdAt' || key === 'updatedAt' || key === 'startedAt' || key === 'completedAt') {
        fields.push(`${key.replace(/([A-Z])/g, '_$1').toLowerCase()} = ?`);
        values.push((value as Date).toISOString());
      } else {
        fields.push(`${key.replace(/([A-Z])/g, '_$1').toLowerCase()} = ?`);
        values.push(value);
      }
    });

    fields.push('sync_timestamp = ?');
    values.push(new Date().toISOString());
    values.push(id);

    await this.db.runAsync(
      `UPDATE tasks SET ${fields.join(', ')} WHERE id = ?`,
      values
    );
  }

  async getTask(id: string): Promise<Task | null> {
    if (!this.db) throw new Error('Database not initialized');

    const result = await this.db.getFirstAsync<any>(
      'SELECT * FROM tasks WHERE id = ?',
      [id]
    );

    return result ? this.parseTask(result) : null;
  }

  async getTasks(status?: string, limit = 20, offset = 0): Promise<Task[]> {
    if (!this.db) throw new Error('Database not initialized');

    let query = 'SELECT * FROM tasks';
    const params: any[] = [];

    if (status) {
      query += ' WHERE status = ?';
      params.push(status);
    }

    query += ' ORDER BY updated_at DESC LIMIT ? OFFSET ?';
    params.push(limit, offset);

    const results = await this.db.getAllAsync<any>(query, params);
    return results.map((r) => this.parseTask(r));
  }

  async deleteTask(id: string): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');
    await this.db.runAsync('DELETE FROM tasks WHERE id = ?', [id]);
  }

  // 同步队列操作
  async addToSyncQueue(item: SyncQueue): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    await this.db.runAsync(
      `INSERT INTO sync_queue (id, action, resource, resource_id, payload, timestamp, retry_count, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        item.id,
        item.action,
        item.resource,
        item.resourceId,
        JSON.stringify(item.payload),
        item.timestamp.toISOString(),
        item.retryCount,
        item.status,
      ]
    );
  }

  async getSyncQueue(status = 'pending', limit = 50): Promise<SyncQueue[]> {
    if (!this.db) throw new Error('Database not initialized');

    const results = await this.db.getAllAsync<any>(
      'SELECT * FROM sync_queue WHERE status = ? ORDER BY timestamp ASC LIMIT ?',
      [status, limit]
    );

    return results.map((r) => ({
      id: r.id,
      action: r.action,
      resource: r.resource,
      resourceId: r.resource_id,
      payload: JSON.parse(r.payload),
      timestamp: new Date(r.timestamp),
      retryCount: r.retry_count,
      status: r.status,
      error: r.error,
    }));
  }

  async updateSyncQueueItem(id: string, status: string, error?: string): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    await this.db.runAsync(
      'UPDATE sync_queue SET status = ?, error = ? WHERE id = ?',
      [status, error, id]
    );
  }

  async deleteSyncQueueItem(id: string): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');
    await this.db.runAsync('DELETE FROM sync_queue WHERE id = ?', [id]);
  }

  // 缓存操作
  async setCache(key: string, value: any, ttl = 3600): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    const expiresAt = new Date(Date.now() + ttl * 1000);
    await this.db.runAsync(
      `INSERT OR REPLACE INTO cache (key, value, expires_at, created_at)
       VALUES (?, ?, ?, ?)`,
      [key, JSON.stringify(value), expiresAt.toISOString(), new Date().toISOString()]
    );
  }

  async getCache(key: string): Promise<any | null> {
    if (!this.db) throw new Error('Database not initialized');

    const result = await this.db.getFirstAsync<any>(
      'SELECT value, expires_at FROM cache WHERE key = ?',
      [key]
    );

    if (!result) return null;

    if (new Date(result.expires_at) < new Date()) {
      await this.db.runAsync('DELETE FROM cache WHERE key = ?', [key]);
      return null;
    }

    return JSON.parse(result.value);
  }

  private parseTask(row: any): Task {
    return {
      id: row.id,
      title: row.title,
      description: row.description,
      status: row.status,
      priority: row.priority,
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
      startedAt: row.started_at ? new Date(row.started_at) : undefined,
      completedAt: row.completed_at ? new Date(row.completed_at) : undefined,
      parameters: JSON.parse(row.parameters),
      result: row.result ? JSON.parse(row.result) : undefined,
      error: row.error,
      syncStatus: row.sync_status,
    };
  }
}

export const database = new Database();
