from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_APPROVAL = "needs_approval"


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    RESOURCE_NOT_FOUND = "resource_not_found"
    RESOURCE_ALREADY_EXISTS = "resource_already_exists"
    RESOURCE_CONFLICT = "resource_conflict"
    TRACE_NOT_FOUND = "trace_not_found"
    RUN_NOT_FOUND = "run_not_found"
    WORKFLOW_NOT_FOUND = "workflow_not_found"
    WORKFLOW_INVALID = "workflow_invalid"
    WORKFLOW_EXECUTION_FAILED = "workflow_execution_failed"
    AGENT_EXECUTION_FAILED = "agent_execution_failed"
    INTERNAL_ERROR = "internal_error"


class RunContext(BaseModel):
    """Cross-module execution contract for tracing, budgets, authorization, and session continuity."""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    user_id: str = "anonymous"
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str | None = None
    permission_scope: list[str] = Field(
        default_factory=lambda: ["tools:read", "memory:read", "memory:write"]
    )
    budget_tokens: int = 16_000
    budget_usd: float = 1.0
    risk_level: RiskLevel = RiskLevel.LOW
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolPolicyVerdict(BaseModel):
    allowed: bool
    requires_approval: bool = False
    sandbox_profile: str = "none"
    reason: str
    audit_required: bool = True
    approval_id: str | None = None


class TraceEvent(BaseModel):
    trace_id: str
    event: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    agent_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None


class TraceSummary(BaseModel):
    trace_id: str
    event_count: int
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_event: str | None = None
    task: str | None = None
    snapshot: dict[str, Any] = Field(default_factory=dict)


class TraceDetail(BaseModel):
    summary: TraceSummary
    events: list[TraceEvent]


class ErrorResponse(BaseModel):
    code: ErrorCode
    message: str
    request_id: str | None = None
    trace_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TaskFrame(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    goal: str
    description: str = ""
    constraints: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    success_criteria: list[str] = Field(default_factory=list)
    fallback_policy: str = "replan"
    requires_approval: bool = False
    source: str = "agent"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanFrame(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    goal: str
    steps: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    rollback_steps: list[str] = Field(default_factory=list)
    status: str = "draft"
    revision: int = 0


class RecoveryFrame(BaseModel):
    branch: str = "continue"
    reason: str | None = None
    status_detail: str | None = None
    error_type: str | None = None
    retry_count: int = 0
    compensation_steps: list[str] = Field(default_factory=list)
    approval_id: str | None = None
    escalation_target: str | None = None
    next_action: str | None = None
    next_actions: list[str] = Field(default_factory=list)
    recovery_plan: dict[str, Any] = Field(default_factory=dict)
    status: str | None = None
    pending_count: int = 0
    latest_decision: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    remediation: str | None = None
    retryable: bool | None = None
    confidence: float | None = None
    tool_name: str | None = None
    follow_up: list[str] = Field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ToolDecision(BaseModel):
    tool_name: str
    reason: str = ""
    input_preview: dict[str, Any] = Field(default_factory=dict)
    expected_output: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    approval_required: bool = False


class ExecutionFrame(BaseModel):
    trace_id: str
    agent_id: str
    tenant_id: str
    user_id: str
    request_id: str
    task: TaskFrame
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    plan: PlanFrame | None = None
    memory: dict[str, Any] = Field(default_factory=dict)
    tool_history: list[dict[str, Any]] = Field(default_factory=list)
    workflow_state: dict[str, Any] = Field(default_factory=dict)
    approval_state: dict[str, Any] = Field(default_factory=dict)
    browser_state: dict[str, Any] = Field(default_factory=dict)
    desktop_state: dict[str, Any] = Field(default_factory=dict)
    recovery_hint: RecoveryFrame = Field(default_factory=RecoveryFrame)
    execution_summary: dict[str, Any] = Field(default_factory=dict)


class AgentRunRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=10_000)
    context: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = "default"
    user_id: str = "anonymous"
    permission_scope: list[str] = Field(
        default_factory=lambda: ["tools:read", "memory:read", "memory:write"]
    )
    stream: bool = False
    resume_trace_id: str | None = None


class ToolCallRecord(BaseModel):
    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    policy: ToolPolicyVerdict
    risk_level: RiskLevel = RiskLevel.LOW
    latency_ms: float = 0.0
    arguments_preview: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    request_id: str | None = None


class AgentPlanStepRecord(BaseModel):
    kind: str
    instruction: str
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    summary: str | None = None
    actions: list[str] = Field(default_factory=list)
    verifications: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    trace_id: str
    agent_id: str
    status: RunStatus
    answer: str
    iterations: int
    memory_hits: int
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    events: list[TraceEvent] = Field(default_factory=list)
    plan: list[AgentPlanStepRecord] = Field(default_factory=list)
    execution_summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentRunRecord(BaseModel):
    trace_id: str
    agent_id: str
    tenant_id: str
    user_id: str
    task: str
    status: RunStatus
    answer: str
    iterations: int
    memory_hits: int
    tool_call_count: int
    error: str | None = None
    stage: str = "finalizing"
    execution_summary: dict[str, Any] = Field(default_factory=dict)
    plan: list[AgentPlanStepRecord] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    run_view: dict[str, Any] = Field(default_factory=dict)
    snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
