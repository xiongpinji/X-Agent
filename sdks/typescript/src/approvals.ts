/**
 * Approval gate resource.
 *
 * Backend surface (backend/app/api/approvals.py, requires `workflow:control` scope):
 *   GET  /api/v1/approvals                       — list approval requests
 *   GET  /api/v1/approvals/{approval_id}         — fetch one request
 *   POST /api/v1/approvals/{approval_id}/approve — approve (records decider server-side)
 *   POST /api/v1/approvals/{approval_id}/reject  — reject
 *   POST /api/v1/approvals/{approval_id}/execute — execute the approved tool call
 *
 * Typical flow: an agent run ends with status "needs_approval" (or emits an
 * `approval_required` SSE event) -> list/get the record -> approve/reject ->
 * optionally execute.
 */

import type { XAgentClient } from "./client.js";
import type {
  ApprovalDecisionInput,
  ApprovalListParams,
  ApprovalRequestRecord,
  ToolCallRecord,
} from "./types.js";

/** Approvals resource. */
export class ApprovalsResource {
  constructor(private readonly client: XAgentClient) {}

  /** List approval requests. Non-admin principals are pinned to their tenant. */
  async list(
    params: ApprovalListParams = {},
    options: { signal?: AbortSignal } = {},
  ): Promise<ApprovalRequestRecord[]> {
    return this.client.request<ApprovalRequestRecord[]>("GET", "/api/v1/approvals", {
      query: {
        limit: params.limit,
        status: params.status,
        tenant_id: params.tenant_id,
      },
      signal: options.signal,
    });
  }

  /** Fetch a single approval request by id. */
  async get(approvalId: string, options: { signal?: AbortSignal } = {}): Promise<ApprovalRequestRecord> {
    return this.client.request<ApprovalRequestRecord>(
      "GET",
      `/api/v1/approvals/${encodeURIComponent(approvalId)}`,
      { signal: options.signal },
    );
  }

  /** Approve a pending request. `decided_by` is bound server-side to the caller. */
  async approve(
    approvalId: string,
    decision: ApprovalDecisionInput = {},
    options: { signal?: AbortSignal } = {},
  ): Promise<ApprovalRequestRecord> {
    return this.client.request<ApprovalRequestRecord>(
      "POST",
      `/api/v1/approvals/${encodeURIComponent(approvalId)}/approve`,
      { body: { reason: decision.reason ?? "" }, signal: options.signal },
    );
  }

  /** Reject a pending request. `decided_by` is bound server-side to the caller. */
  async reject(
    approvalId: string,
    decision: ApprovalDecisionInput = {},
    options: { signal?: AbortSignal } = {},
  ): Promise<ApprovalRequestRecord> {
    return this.client.request<ApprovalRequestRecord>(
      "POST",
      `/api/v1/approvals/${encodeURIComponent(approvalId)}/reject`,
      { body: { reason: decision.reason ?? "" }, signal: options.signal },
    );
  }

  /**
   * Execute an approved request. Runs the gated tool call and returns its
   * ToolCallRecord; the approval is marked executed server-side.
   */
  async execute(approvalId: string, options: { signal?: AbortSignal } = {}): Promise<ToolCallRecord> {
    return this.client.request<ToolCallRecord>(
      "POST",
      `/api/v1/approvals/${encodeURIComponent(approvalId)}/execute`,
      { body: {}, signal: options.signal },
    );
  }
}
