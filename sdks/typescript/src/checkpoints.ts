/**
 * Checkpoint / resume resource (P2-09).
 *
 * Backend surface (backend/app/api/checkpoints.py):
 *   GET    /api/v1/checkpoints                       — list resumable runs
 *   GET    /api/v1/checkpoints/{trace_id}            — checkpoint detail
 *   POST   /api/v1/checkpoints/{trace_id}/resume     — resume from latest (or given) checkpoint
 *   DELETE /api/v1/checkpoints/{trace_id}            — drop all checkpoints for a run
 */

import type { XAgentClient } from "./client.js";
import type {
  CheckpointDeleteResponse,
  CheckpointDetailResponse,
  CheckpointListResponse,
  CheckpointResumeRequest,
  CheckpointResumeResponse,
} from "./types.js";

/** Checkpoints resource. */
export class CheckpointsResource {
  constructor(private readonly client: XAgentClient) {}

  /** List resumable runs (status running/paused/failed). Default limit 20. */
  async list(limit?: number, options: { signal?: AbortSignal } = {}): Promise<CheckpointListResponse> {
    return this.client.request<CheckpointListResponse>("GET", "/api/v1/checkpoints", {
      query: { limit },
      signal: options.signal,
    });
  }

  /** All checkpoints for one run, plus resumability. 404 when none exist. */
  async get(traceId: string, options: { signal?: AbortSignal } = {}): Promise<CheckpointDetailResponse> {
    return this.client.request<CheckpointDetailResponse>(
      "GET",
      `/api/v1/checkpoints/${encodeURIComponent(traceId)}`,
      { signal: options.signal },
    );
  }

  /**
   * POST /api/v1/checkpoints/{trace_id}/resume — resume a run from its latest
   * checkpoint (or `from_iteration` when given). The resume executes to
   * completion server-side; the response carries the new trace id and status.
   */
  async resume(
    traceId: string,
    request: CheckpointResumeRequest = {},
    options: { signal?: AbortSignal } = {},
  ): Promise<CheckpointResumeResponse> {
    return this.client.request<CheckpointResumeResponse>(
      "POST",
      `/api/v1/checkpoints/${encodeURIComponent(traceId)}/resume`,
      {
        body: {
          extra_context: request.extra_context ?? {},
          from_iteration: request.from_iteration ?? null,
        },
        signal: options.signal,
      },
    );
  }

  /** DELETE /api/v1/checkpoints/{trace_id} — clean up a run's checkpoints. */
  async delete(traceId: string, options: { signal?: AbortSignal } = {}): Promise<CheckpointDeleteResponse> {
    return this.client.request<CheckpointDeleteResponse>(
      "DELETE",
      `/api/v1/checkpoints/${encodeURIComponent(traceId)}`,
      { signal: options.signal },
    );
  }
}
