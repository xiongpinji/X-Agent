/**
 * Contract types for the X-Agent core API.
 *
 * Every type in this file mirrors the backend implementation 1:1
 * (field names and semantics included). The backend source of truth:
 *
 *   - backend/app/core/contracts.py     — RunStatus / ErrorCode / ToolCallRecord /
 *                                         AgentRunResponse / TraceEvent / ...
 *   - backend/app/api/agents.py         — POST /api/v1/agents/run request shape
 *   - backend/app/api/streaming.py      — SSE event envelope + fine-grained events
 *   - backend/app/core/approvals.py     — ApprovalRequestRecord / ApprovalDecisionRequest
 *   - backend/app/api/checkpoints.py    — checkpoint list/detail/resume responses
 *   - backend/app/api/sandbox_tasks.py  — sandbox task submit/status responses
 *   - backend/app/main.py               — GET /health, GET /ready, CSRF token endpoint
 *
 * Field names intentionally stay snake_case: they are the wire contract,
 * not an ergonomic TS API. Changing a field name here breaks the contract —
 * change the backend first, then this file, then release.
 */

// ---------------------------------------------------------------------------
// Shared enums (backend StrEnum values)
// ---------------------------------------------------------------------------

/** backend/app/core/contracts.py RunStatus */
export type RunStatus = "running" | "completed" | "failed" | "needs_approval";

/** backend/app/core/approvals.py ApprovalStatus */
export type ApprovalStatus = "pending" | "approved" | "rejected" | "executed";

/** backend/app/core/contracts.py RiskLevel */
export type RiskLevel = "low" | "medium" | "high" | "critical";

/** backend/app/core/contracts.py ErrorCode */
export type ApiErrorCode =
  | "validation_error"
  | "authentication_failed"
  | "authorization_failed"
  | "resource_not_found"
  | "resource_already_exists"
  | "resource_conflict"
  | "trace_not_found"
  | "run_not_found"
  | "workflow_not_found"
  | "workflow_invalid"
  | "workflow_execution_failed"
  | "agent_execution_failed"
  | "internal_error"
  | "rate_limit_exceeded"
  | "invalid_token"
  | "token_expired"
  | "email_verification_required"
  | "account_locked"
  | "invalid_credentials";

/** Normalized error codes produced by the SDK itself (no HTTP status). */
export type SdkErrorCode = "network_error" | "timeout_error";

// ---------------------------------------------------------------------------
// Agent run — POST /api/v1/agents/run
// ---------------------------------------------------------------------------

/** Request body for POST /api/v1/agents/run (backend/app/api/agents.py run_agent). */
export interface AgentRunRequest {
  /** Required, non-empty. Max ~10k chars enforced by the agent loop. */
  task: string;
  /** Scopes the principal already holds are honored; others are dropped server-side. */
  permission_scope?: string[];
  /** Persisted multi-turn session id. */
  session_id?: string;
  /** Per-request override, 1..100. */
  max_iterations?: number;
  /** Per-run sandbox mode override. */
  sandbox_mode?: "docker" | "subprocess" | "auto";
  /** Free-form context passed through to the agent loop. */
  extra_context?: Record<string, unknown>;
  /** Codex-style multimodal images, merged into extra_context server-side. */
  images?: string[];
}

/** backend/app/core/contracts.py ToolPolicyVerdict */
export interface ToolPolicyVerdict {
  allowed: boolean;
  requires_approval: boolean;
  sandbox_profile: string;
  reason: string;
  audit_required: boolean;
  approval_id: string | null;
}

/** backend/app/core/contracts.py ToolCallRecord */
export interface ToolCallRecord {
  tool_name: string;
  success: boolean;
  output: unknown;
  error: string | null;
  policy: ToolPolicyVerdict;
  risk_level: RiskLevel;
  latency_ms: number;
  arguments_preview: Record<string, unknown>;
  trace_id: string | null;
  request_id: string | null;
}

/** backend/app/core/contracts.py TraceEvent */
export interface TraceEvent {
  trace_id: string;
  event: string;
  timestamp: string;
  data: Record<string, unknown>;
  request_id: string | null;
  agent_id: string | null;
  tenant_id: string | null;
  user_id: string | null;
}

/** backend/app/core/contracts.py AgentPlanStepRecord */
export interface AgentPlanStepRecord {
  kind: string;
  instruction: string;
  tool_name: string | null;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
  error: string | null;
  summary: string | null;
  actions: string[];
  verifications: string[];
  risks: string[];
  next_steps: string[];
}

/** Response of POST /api/v1/agents/run — backend AgentRunResponse.model_dump(mode="json"). */
export interface AgentRunResponse {
  trace_id: string;
  agent_id: string;
  status: RunStatus;
  answer: string;
  iterations: number;
  memory_hits: number;
  tool_calls: ToolCallRecord[];
  events: TraceEvent[];
  plan: AgentPlanStepRecord[];
  execution_summary: Record<string, unknown>;
  error: string | null;
  snapshot: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Streaming — POST /api/v1/agent/run/stream + GET /api/v1/agent/stream/{run_id}
// ---------------------------------------------------------------------------

/** Body of POST /api/v1/agent/run/stream (backend/app/api/streaming.py). */
export interface AgentStreamRunRequest {
  /** Required, 1..20000 chars. */
  task: string;
  extra_context?: Record<string, unknown>;
  /** Optional session id for multi-turn context. */
  session_id?: string;
}

/** Response of POST /api/v1/agent/run/stream. */
export interface StreamRunStartResponse {
  run_id: string;
  stream_url: string;
  trace_id: string;
  status: string;
}

/**
 * SSE event envelope. Every streamed frame carries this shape in its
 * `data:` line (backend streaming.py StreamEvent).
 */
export interface StreamEventEnvelope<
  E extends string = string,
  D = Record<string, unknown>,
> {
  event_type: E;
  timestamp: string;
  run_id: string;
  data: D;
  sequence: number;
}

/**
 * All event types the backend emits. Fine-grained agent events
 * (iteration/tool_call/tool_result/plan/observation/reflection/agent/
 * approval_required) bridge from AgentLoop trace events; legacy events
 * (message/progress/completion/error/heartbeat/...) are preserved.
 */
export type StreamEventType =
  // fine-grained agent lifecycle
  | "iteration"
  | "tool_call"
  | "tool_result"
  | "plan"
  | "observation"
  | "reflection"
  | "agent"
  | "approval_required"
  // legacy events
  | "message"
  | "task_update"
  | "task_status"
  | "progress"
  | "completion"
  | "error"
  | "heartbeat"
  | "log"
  | "metric";

/** Terminal event types — the server closes the SSE stream after emitting one. */
export type TerminalStreamEventType = "completion" | "error";

// Typed payloads for the fine-grained events (see trace_to_stream_event /
// tool_call_to_result_event / approval_to_event in backend streaming.py).

export interface IterationEventData {
  iteration?: number | null;
  step_kind: string;
  instruction: string;
  trace_id?: string | null;
}

export interface ToolCallEventData {
  phase: "completed";
  tool_name: string;
  success: boolean;
  latency_ms: number | null;
  iteration: number | null;
  trace_id?: string | null;
}

export interface ToolResultEventData {
  tool_name: string;
  success: boolean;
  latency_ms: number;
  arguments: string;
  output: string;
  error: string | null;
}

export interface PlanEventData {
  goal: string;
  step_count: number | null;
  task: string;
  trace_id?: string | null;
}

export interface ObservationEventData {
  iteration: number | null;
  observation: string;
  trace_id?: string | null;
}

export interface ReflectionEventData {
  iteration: number | null;
  reflection: string;
  trace_id?: string | null;
}

/** Generic whitelisted lifecycle event; `trace_event` carries the original name. */
export interface AgentEventData extends Record<string, unknown> {
  trace_event: string;
  trace_id?: string | null;
}

export interface ApprovalRequiredEventData {
  approval_id: string | null;
  tool_name?: string;
  action?: string;
  risk_level?: string;
  reason?: string;
  arguments?: string;
}

export interface MessageEventData {
  content: string;
  role: "assistant" | "user" | "system";
}

export interface ProgressEventData {
  overall_progress: number;
  current_step: string;
  total_steps: number;
  completed_steps: number;
}

export interface StreamErrorEventData {
  error_code: string;
  error_message: string;
  error_details: Record<string, unknown>;
  recoverable: boolean;
}

export interface CompletionEventData {
  status: RunStatus | string;
  result: unknown;
  summary: Record<string, unknown>;
}

/** Narrowed event types for `for await` consumers. */
export type IterationStreamEvent = StreamEventEnvelope<"iteration", IterationEventData>;
export type ToolCallStreamEvent = StreamEventEnvelope<"tool_call", ToolCallEventData>;
export type ToolResultStreamEvent = StreamEventEnvelope<"tool_result", ToolResultEventData>;
export type PlanStreamEvent = StreamEventEnvelope<"plan", PlanEventData>;
export type ObservationStreamEvent = StreamEventEnvelope<"observation", ObservationEventData>;
export type ReflectionStreamEvent = StreamEventEnvelope<"reflection", ReflectionEventData>;
export type AgentStreamEvent = StreamEventEnvelope<"agent", AgentEventData>;
export type ApprovalRequiredStreamEvent = StreamEventEnvelope<"approval_required", ApprovalRequiredEventData>;
export type MessageStreamEvent = StreamEventEnvelope<"message", MessageEventData>;
export type ProgressStreamEvent = StreamEventEnvelope<"progress", ProgressEventData>;
export type StreamErrorEvent = StreamEventEnvelope<"error", StreamErrorEventData>;
export type CompletionStreamEvent = StreamEventEnvelope<"completion", CompletionEventData>;
export type HeartbeatStreamEvent = StreamEventEnvelope<"heartbeat", Record<string, never>>;

/** GET /api/v1/agent/stream/{run_id}/events (non-streaming event history). */
export interface StreamEventsResponse {
  run_id: string;
  events: StreamEventEnvelope[];
  total: number;
  limited: boolean;
}

// ---------------------------------------------------------------------------
// Approvals — /api/v1/approvals
// ---------------------------------------------------------------------------

/** backend/app/core/approvals.py ApprovalRequestRecord */
export interface ApprovalRequestRecord {
  id: string;
  tenant_id: string;
  actor_id: string;
  trace_id: string;
  resource_type: string;
  resource_id: string;
  action: string;
  risk_level: RiskLevel;
  status: ApprovalStatus;
  reason: string;
  arguments_preview: Record<string, unknown>;
  arguments: Record<string, unknown>;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  executed_by: string | null;
  executed_at: string | null;
  execution_trace_id: string | null;
  linked_policy_trace_id: string | null;
  created_at: string;
}

/** Query params for GET /api/v1/approvals. */
export interface ApprovalListParams {
  /** 1..200, default 50. */
  limit?: number;
  status?: ApprovalStatus;
  /** Admin only; non-admin requests are pinned to their own tenant. */
  tenant_id?: string;
}

/**
 * Body for approve/reject. `decided_by` is always overridden server-side with
 * the authenticated principal (P0-07 anti-forgery) — the SDK does not send it.
 */
export interface ApprovalDecisionInput {
  reason?: string;
}

// ---------------------------------------------------------------------------
// Checkpoints — /api/v1/checkpoints
// ---------------------------------------------------------------------------

/** backend/app/core/checkpoint/store.py CheckpointSummary */
export interface CheckpointSummary {
  checkpoint_id: string;
  trace_id: string;
  agent_id: string;
  iteration: number;
  status: string;
  created_at: string;
  task_preview: string;
}

export interface CheckpointListResponse {
  items: CheckpointSummary[];
  total: number;
}

export interface CheckpointDetailResponse {
  trace_id: string;
  agent_id: string;
  checkpoints: Record<string, unknown>[];
  latest_iteration: number;
  status: string;
  resumable: boolean;
}

/** Body for POST /api/v1/checkpoints/{trace_id}/resume. */
export interface CheckpointResumeRequest {
  extra_context?: Record<string, unknown>;
  /** null = resume from the latest checkpoint. */
  from_iteration?: number | null;
}

export interface CheckpointResumeResponse {
  trace_id: string;
  new_trace_id: string;
  resumed_from_iteration: number;
  status: string;
  message: string;
}

export interface CheckpointDeleteResponse {
  trace_id: string;
  deleted_count: number;
}

// ---------------------------------------------------------------------------
// Sandbox tasks — /api/v1/sandbox/tasks
// ---------------------------------------------------------------------------

/** Body for POST /api/v1/sandbox/tasks. */
export interface SandboxTaskSubmitRequest {
  name: string;
  command: string;
  /** Container image, default "python:3.11-slim". */
  image?: string;
  /** 1..3600 seconds, default 300. */
  timeout_seconds?: number;
  enable_network?: boolean;
}

export interface SandboxTaskSubmitResponse {
  task_id: string;
  status: string;
}

export interface SandboxTaskStatusResponse {
  task_id: string;
  status: string;
  backend: string | null;
  steps: Record<string, unknown>[];
  error: string | null;
}

export interface SandboxTaskListResponse {
  tasks: Array<{ task_id: string; status: string }>;
}

/** Terminal sandbox task statuses (sandbox_tasks.py drain loop). */
export type SandboxTaskTerminalStatus = "completed" | "failed" | "error";

// ---------------------------------------------------------------------------
// Health — GET /health, GET /ready
// ---------------------------------------------------------------------------

/** GET /health (backend/app/main.py). 503 + status "draining" during shutdown. */
export interface HealthStatus {
  status: "ok" | "draining" | string;
  service: string;
}

/** GET /ready. 503 with status "not_ready" when a required component fails. */
export interface ReadinessStatus {
  status: "ready" | "not_ready";
  components: Record<string, "ok" | "error" | "degraded" | string>;
  integrations: Record<string, boolean>;
}
