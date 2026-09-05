/**
 * @xagent/sdk — unified TypeScript client for the X-Agent core API.
 *
 * The one client shared by the browser extension, web frontend and React
 * Native app (and any other TS runtime). Contract surface:
 *
 *   client.agents.run / runStream (SSE)      POST /api/v1/agents/run
 *                                            POST /api/v1/agent/run/stream
 *                                            GET  /api/v1/agent/stream/{run_id}
 *   client.approvals.list/approve/reject/execute
 *   client.checkpoints.list/resume/delete    POST /api/v1/checkpoints/{trace_id}/resume
 *   client.tasks.submit/get/list/pollUntilDone
 *   client.health / client.ready             GET /health, GET /ready
 *
 * Auth: x-api-key header (CSRF-exempt), or Bearer token, or browser
 * session cookie + automatic CSRF token handling.
 */

export {
  XAgentClient,
  XAgentApiError,
} from "./client.js";
export type { XAgentClientOptions, RequestOptions, FetchCredentials } from "./client.js";

export {
  AgentsResource,
  parseSseFrame,
  parseSseStream,
  toStreamEventEnvelope,
} from "./agents.js";
export type {
  SseMessage,
  StreamOptions,
  ActiveAgentStream,
} from "./agents.js";

export { ApprovalsResource } from "./approvals.js";
export { CheckpointsResource } from "./checkpoints.js";
export { SandboxTasksResource } from "./tasks.js";
export type { PollUntilDoneOptions } from "./tasks.js";

export type {
  // enums
  RunStatus,
  ApprovalStatus,
  RiskLevel,
  ApiErrorCode,
  SdkErrorCode,
  // agent run
  AgentRunRequest,
  AgentRunResponse,
  ToolCallRecord,
  ToolPolicyVerdict,
  TraceEvent,
  AgentPlanStepRecord,
  // streaming
  AgentStreamRunRequest,
  StreamRunStartResponse,
  StreamEventEnvelope,
  StreamEventType,
  TerminalStreamEventType,
  StreamEventsResponse,
  IterationEventData,
  ToolCallEventData,
  ToolResultEventData,
  PlanEventData,
  ObservationEventData,
  ReflectionEventData,
  AgentEventData,
  ApprovalRequiredEventData,
  MessageEventData,
  ProgressEventData,
  StreamErrorEventData,
  CompletionEventData,
  IterationStreamEvent,
  ToolCallStreamEvent,
  ToolResultStreamEvent,
  PlanStreamEvent,
  ObservationStreamEvent,
  ReflectionStreamEvent,
  AgentStreamEvent,
  ApprovalRequiredStreamEvent,
  MessageStreamEvent,
  ProgressStreamEvent,
  StreamErrorEvent,
  CompletionStreamEvent,
  HeartbeatStreamEvent,
  // approvals
  ApprovalRequestRecord,
  ApprovalListParams,
  ApprovalDecisionInput,
  // checkpoints
  CheckpointSummary,
  CheckpointListResponse,
  CheckpointDetailResponse,
  CheckpointResumeRequest,
  CheckpointResumeResponse,
  CheckpointDeleteResponse,
  // sandbox tasks
  SandboxTaskSubmitRequest,
  SandboxTaskSubmitResponse,
  SandboxTaskStatusResponse,
  SandboxTaskListResponse,
  SandboxTaskTerminalStatus,
  // health
  HealthStatus,
  ReadinessStatus,
} from "./types.js";
