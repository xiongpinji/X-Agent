from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_long_task_id() -> str:
    return str(uuid4())


def long_task_utcnow() -> datetime:
    return datetime.now(UTC)


class LongTaskStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class LongTaskPhaseStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class LongTaskNextAction(StrEnum):
    WAIT_APPROVAL = "wait_approval"
    WAIT_USER = "wait_user"
    RUN_AGENT = "run_agent"
    RUN_ENGINEERING = "run_engineering"
    RUN_WORKFLOW = "run_workflow"
    RESUME = "resume"
    ADVANCE_PHASE = "advance_phase"
    DELIVER = "deliver"
    COMPLETE_READY = "complete_ready"
    NONE = "none"


class LongTaskCreateRequest(BaseModel):
    title: str = Field(default="", max_length=180)
    task: str = Field(..., min_length=1, max_length=20_000)
    agent_id: str | None = None
    workflow_id: str | None = None
    priority: int = Field(default=5, ge=1, le=10)
    requires_approval: bool = True
    auto_plan: bool = True
    context: dict[str, Any] = Field(default_factory=dict)


class LongTaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=180)
    status: LongTaskStatus | None = None
    plan: list[str] | None = None
    result_summary: str | None = Field(default=None, max_length=10_000)
    error: str | None = Field(default=None, max_length=4_000)
    metadata: dict[str, Any] | None = None


class LongTaskPhaseUpdateRequest(BaseModel):
    status: LongTaskPhaseStatus | None = None
    result_summary: str | None = Field(default=None, max_length=4_000)
    artifact_ids: list[str] | None = None
    metadata: dict[str, Any] | None = None


class LongTaskPhaseResultCreate(BaseModel):
    subagent_id: str | None = None
    subagent_name: str = Field(default="", max_length=180)
    role: str = Field(default="", max_length=80)
    result_summary: str = Field(..., min_length=1, max_length=4_000)
    artifact_ids: list[str] = Field(default_factory=list)
    status: LongTaskPhaseStatus | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LongTaskNextActionDecision(BaseModel):
    action: LongTaskNextAction
    reason: str
    phase_id: str | None = None
    phase_title: str = ""
    recommended_endpoint: str = ""
    requires_confirmation: bool = False
    tool_mode: str = "agent"
    metadata: dict[str, Any] = Field(default_factory=dict)


class LongTaskDispatchRequest(BaseModel):
    allow_agent_run: bool = False
    allow_engineering_run: bool = False
    allow_workflow_run: bool = False
    resume_reason: str = Field(default="automatic task resume", max_length=1_000)
    result_summary: str = Field(default="automatic phase advancement", max_length=4_000)


class LongTaskWorkflowAttachRequest(BaseModel):
    workflow_id: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1_000)
    mode: str = Field(default="auto", pattern="^(auto|agent|engineering)$")


class LongTaskEventCreate(BaseModel):
    kind: str = Field(..., min_length=1, max_length=80)
    status: LongTaskStatus | None = None
    detail: str = Field(default="", max_length=4_000)
    payload: dict[str, Any] = Field(default_factory=dict)


class LongTaskArtifactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=180)
    kind: str = Field(default="text", max_length=80)
    uri: str = Field(default="", max_length=2_000)
    summary: str = Field(default="", max_length=2_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LongTaskEvent(BaseModel):
    id: str = Field(default_factory=new_long_task_id)
    kind: str
    status: LongTaskStatus
    detail: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=long_task_utcnow)


class LongTaskArtifact(BaseModel):
    id: str = Field(default_factory=new_long_task_id)
    name: str
    kind: str = "text"
    uri: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=long_task_utcnow)


class LongTaskPhaseState(BaseModel):
    id: str
    title: str
    owner: str = ""
    status: LongTaskPhaseStatus = LongTaskPhaseStatus.PENDING
    acceptance: str = ""
    result_summary: str = ""
    artifact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class LongTaskRecord(BaseModel):
    id: str = Field(default_factory=new_long_task_id)
    title: str
    task: str
    status: LongTaskStatus = LongTaskStatus.QUEUED
    priority: int = 5
    requires_approval: bool = True
    agent_id: str | None = None
    workflow_id: str | None = None
    run_trace_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"
    plan: list[str] = Field(default_factory=list)
    phases: list[LongTaskPhaseState] = Field(default_factory=list)
    timeline: list[LongTaskEvent] = Field(default_factory=list)
    artifacts: list[LongTaskArtifact] = Field(default_factory=list)
    result_summary: str = ""
    error: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=long_task_utcnow)
    updated_at: datetime = Field(default_factory=long_task_utcnow)
    completed_at: datetime | None = None


class LongTaskDispatchResponse(BaseModel):
    decision: LongTaskNextActionDecision
    executed: bool = False
    blocked: bool = False
    message: str = ""
    recovery_gate: dict[str, Any] = Field(default_factory=dict)
    record: LongTaskRecord | None = None


__all__ = [
    "LongTaskArtifact",
    "LongTaskArtifactCreate",
    "LongTaskCreateRequest",
    "LongTaskDispatchRequest",
    "LongTaskDispatchResponse",
    "LongTaskEvent",
    "LongTaskEventCreate",
    "LongTaskNextAction",
    "LongTaskNextActionDecision",
    "LongTaskPhaseResultCreate",
    "LongTaskPhaseState",
    "LongTaskPhaseStatus",
    "LongTaskPhaseUpdateRequest",
    "LongTaskRecord",
    "LongTaskStatus",
    "LongTaskUpdateRequest",
    "LongTaskWorkflowAttachRequest",
    "long_task_utcnow",
    "new_long_task_id",
]
