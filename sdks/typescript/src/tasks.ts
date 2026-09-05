/**
 * Sandbox task resource — Codex-style fire-and-forget execution.
 *
 * Backend surface (backend/app/api/sandbox_tasks.py, requires `sandbox:run`):
 *   POST /api/v1/sandbox/tasks          — submit (returns task_id immediately)
 *   GET  /api/v1/sandbox/tasks/{id}     — poll status/steps/error
 *   GET  /api/v1/sandbox/tasks          — list known task ids + statuses
 */

import type { XAgentClient } from "./client.js";
import { XAgentApiError } from "./client.js";
import type {
  SandboxTaskStatusResponse,
  SandboxTaskSubmitRequest,
  SandboxTaskSubmitResponse,
  SandboxTaskListResponse,
} from "./types.js";

const TERMINAL_STATUSES = new Set(["completed", "failed", "error"]);

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason instanceof Error ? signal.reason : new Error("Aborted"));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort(): void {
      clearTimeout(timer);
      const reason = signal?.reason;
      reject(reason instanceof Error ? reason : new Error("Aborted"));
    }
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/** Options for {@link SandboxTasksResource.pollUntilDone}. */
export interface PollUntilDoneOptions {
  /** Poll interval, default 1000ms. */
  intervalMs?: number;
  /** Overall deadline, default 600000ms. */
  timeoutMs?: number;
  signal?: AbortSignal;
}

/** Sandbox tasks resource. */
export class SandboxTasksResource {
  constructor(private readonly client: XAgentClient) {}

  /** Submit a task for isolated sandbox execution; resolves as soon as queued. */
  async submit(
    request: SandboxTaskSubmitRequest,
    options: { signal?: AbortSignal } = {},
  ): Promise<SandboxTaskSubmitResponse> {
    return this.client.request<SandboxTaskSubmitResponse>("POST", "/api/v1/sandbox/tasks", {
      body: request,
      signal: options.signal,
    });
  }

  /** Poll a task's status and result. 404 until the task id is known to the server. */
  async get(taskId: string, options: { signal?: AbortSignal } = {}): Promise<SandboxTaskStatusResponse> {
    return this.client.request<SandboxTaskStatusResponse>(
      "GET",
      `/api/v1/sandbox/tasks/${encodeURIComponent(taskId)}`,
      { signal: options.signal },
    );
  }

  /** List all known task ids and statuses. */
  async list(options: { signal?: AbortSignal } = {}): Promise<SandboxTaskListResponse> {
    return this.client.request<SandboxTaskListResponse>("GET", "/api/v1/sandbox/tasks", {
      signal: options.signal,
    });
  }

  /**
   * Poll until the task reaches a terminal status (completed/failed/error)
   * or the deadline expires (throws XAgentApiError with code "timeout_error").
   */
  async pollUntilDone(
    taskId: string,
    options: PollUntilDoneOptions = {},
  ): Promise<SandboxTaskStatusResponse> {
    const intervalMs = options.intervalMs ?? 1_000;
    const timeoutMs = options.timeoutMs ?? 600_000;
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const status = await this.get(taskId, { signal: options.signal });
      if (TERMINAL_STATUSES.has(status.status)) return status;
      if (Date.now() + intervalMs > deadline) {
        throw new XAgentApiError({
          message: `Sandbox task ${taskId} did not reach a terminal status within ${timeoutMs}ms (last: ${status.status}).`,
          status: 0,
          code: "timeout_error",
          method: "GET",
          url: `/api/v1/sandbox/tasks/${taskId}`,
        });
      }
      await sleep(intervalMs, options.signal);
    }
  }
}
