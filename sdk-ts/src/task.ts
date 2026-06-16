/**
 * Task class for polling and managing task state
 */

import { Task, TaskStatus, TaskResult } from './types';
import { TimeoutError } from './errors';

export class XAgentTask implements Task {
  id: string;
  description: string;
  status: TaskStatus;
  priority: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
  result?: TaskResult;

  private pollIntervalMs: number = 1000;
  private maxWaitMs: number = 3600000; // 1 hour default

  constructor(
    task: Task,
    private fetchTaskFn: (taskId: string) => Promise<Task>,
  ) {
    this.id = task.id;
    this.description = task.description;
    this.status = task.status as TaskStatus;
    this.priority = task.priority;
    this.created_at = task.created_at;
    this.updated_at = task.updated_at;
    this.started_at = task.started_at;
    this.completed_at = task.completed_at;
    this.result = task.result;
  }

  /**
   * Poll for task completion with exponential backoff
   */
  async wait(timeoutMs?: number): Promise<TaskResult> {
    const timeout = timeoutMs || this.maxWaitMs;
    const startTime = Date.now();
    let backoffMs = this.pollIntervalMs;

    while (Date.now() - startTime < timeout) {
      const updated = await this.fetchTaskFn(this.id);
      this.updateFromFetch(updated);

      if (
        this.status === TaskStatus.COMPLETED ||
        this.status === TaskStatus.FAILED ||
        this.status === TaskStatus.CANCELLED
      ) {
        if (!this.result) {
          throw new Error(`Task ${this.id} completed but no result returned`);
        }
        return this.result;
      }

      await this.sleep(backoffMs);
      backoffMs = Math.min(backoffMs * 1.5, 10000); // Cap at 10s
    }

    throw new TimeoutError(
      `Task ${this.id} did not complete within ${timeout}ms`,
    );
  }

  /**
   * Get current task status without waiting
   */
  async refresh(): Promise<void> {
    const updated = await this.fetchTaskFn(this.id);
    this.updateFromFetch(updated);
  }

  /**
   * Check if task is in a terminal state
   */
  isTerminal(): boolean {
    return [
      TaskStatus.COMPLETED,
      TaskStatus.FAILED,
      TaskStatus.CANCELLED,
    ].includes(this.status);
  }

  /**
   * Check if task completed successfully
   */
  isSuccess(): boolean {
    return this.status === TaskStatus.COMPLETED && this.result?.status === 'success';
  }

  /**
   * Get pull request URL if available
   */
  getPRUrl(): string | undefined {
    return this.result?.pr_url;
  }

  private updateFromFetch(task: Task): void {
    this.status = task.status as TaskStatus;
    this.updated_at = task.updated_at;
    this.started_at = task.started_at;
    this.completed_at = task.completed_at;
    this.result = task.result;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
