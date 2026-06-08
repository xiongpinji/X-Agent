from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.audit import AuditStore
from backend.app.core.approvals import APPROVAL_SUBJECT_ACTIONS, ApprovalStatus, ApprovalSubjectType
from backend.app.core.contracts import RiskLevel, RunContext
from backend.app.core.sandbox.security import get_enterprise_safety_policy
from backend.app.core.security import Principal
from backend.app.dependencies import (
    enforce_scope,
    get_approval_store,
    get_audit_store,
    get_current_principal,
    get_run_store,
    get_trace_store,
)

router = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]
ApprovalStoreDependency = Annotated[object, Depends(get_approval_store)]
RunStoreDependency = Annotated[object, Depends(get_run_store)]
TraceStoreDependency = Annotated[object, Depends(get_trace_store)]

ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"

STATUS_VOCABULARY = (
    "queued",
    "running",
    "waiting_for_approval",
    "waiting_for_user",
    "completed",
    "failed",
    "cancelled",
    "blocked",
)

SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "private_key",
    "password",
    "secret",
    "credential",
    "authorization",
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-.]{16,}", re.IGNORECASE),
)
SAFE_SECRET_VALUES = {"", "***", "<redacted>", "redacted", "<secret-ref>"}
SAFE_SECRET_PREFIXES = ("secret://", "vault://", "env:", "ref:", "${")


@dataclass(frozen=True)
class ControlPlaneMethodSpec:
    method: str
    group: str
    current_backing_surface: tuple[str, ...]
    status: str
    operation_kind: str
    requires_approval: bool
    implementation_state: str
    description: str

    def to_payload(self) -> dict[str, object]:
        return {
            "method": self.method,
            "group": self.group,
            "current_backing_surface": list(self.current_backing_surface),
            "status": self.status,
            "operation_kind": self.operation_kind,
            "requires_approval": self.requires_approval,
            "implementation_state": self.implementation_state,
            "description": self.description,
        }


def _spec(
    method: str,
    group: str,
    backing: tuple[str, ...],
    status: str,
    operation_kind: str,
    requires_approval: bool,
    implementation_state: str,
    description: str,
) -> ControlPlaneMethodSpec:
    return ControlPlaneMethodSpec(
        method=method,
        group=group,
        current_backing_surface=backing,
        status=status,
        operation_kind=operation_kind,
        requires_approval=requires_approval,
        implementation_state=implementation_state,
        description=description,
    )


METHOD_SPECS: tuple[ControlPlaneMethodSpec, ...] = (
    _spec(
        "thread/start",
        "thread",
        ("/api/v1/agent/run", "/api/v1/agents/run", "/api/v1/runs/start"),
        "mapped",
        "write",
        False,
        "adapter_pending",
        "Start a durable product work thread.",
    ),
    _spec(
        "thread/resume",
        "thread",
        ("/api/v1/agents/{agent_id}/resume", "workflow resume endpoints"),
        "partial",
        "write",
        False,
        "adapter_pending",
        "Resume an existing thread or workflow run.",
    ),
    _spec(
        "thread/read",
        "thread",
        ("/api/v1/runs/{trace_id}", "/api/v1/traces/{trace_id}"),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "Read a thread-compatible run or trace snapshot.",
    ),
    _spec(
        "thread/search",
        "thread",
        ("/api/v1/traces", "/api/v1/runs", "audit search"),
        "partial",
        "read",
        False,
        "read_only_contract",
        "Search thread-compatible run and trace evidence.",
    ),
    _spec(
        "thread/fork",
        "thread",
        ("no unified endpoint",),
        "missing",
        "write",
        True,
        "adapter_pending",
        "Fork a thread without implying file-system rollback.",
    ),
    _spec(
        "thread/rollback",
        "thread",
        ("replay/version endpoints",),
        "missing",
        "write",
        True,
        "adapter_pending",
        "Create product rollback intent and audit evidence.",
    ),
    _spec(
        "thread/compact",
        "thread",
        ("/api/sessions/compress",),
        "partial",
        "write",
        False,
        "adapter_pending",
        "Compact thread context into a durable summary.",
    ),
    _spec(
        "turn/start",
        "turn",
        ("agent run endpoints",),
        "mapped",
        "write",
        False,
        "adapter_pending",
        "Start a turn inside a thread.",
    ),
    _spec(
        "turn/steer",
        "turn",
        ("no unified endpoint",),
        "missing",
        "write",
        True,
        "adapter_pending",
        "Steer a running turn.",
    ),
    _spec(
        "turn/interrupt",
        "turn",
        ("cancel/pause endpoints",),
        "partial",
        "write",
        True,
        "adapter_pending",
        "Interrupt or cancel a running turn.",
    ),
    _spec(
        "turn/events/list",
        "turn",
        ("streaming/messages/debug endpoints",),
        "partial",
        "read",
        False,
        "read_only_contract",
        "List normalized turn events.",
    ),
    _spec(
        "tool/list",
        "tool",
        ("/api/v1/tools", "/api/v1/mcp/tools"),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "List native and MCP tools with approval metadata.",
    ),
    _spec(
        "tool/call",
        "tool",
        ("/api/v1/mcp/tools/execute", "tools batch execution"),
        "partial",
        "execute",
        True,
        "adapter_pending",
        "Execute a governed native or MCP tool.",
    ),
    _spec(
        "tool/progress",
        "tool",
        ("streaming events", "trace timeline"),
        "partial",
        "read",
        False,
        "read_only_contract",
        "Read tool progress events.",
    ),
    _spec(
        "tool/execution/read",
        "tool",
        ("/api/v1/tools/executions/{execution_id}",),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "Read a recorded tool execution.",
    ),
    _spec(
        "approval/list",
        "approval",
        ("/api/v1/approvals",),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "List pending approval requests.",
    ),
    _spec(
        "approval/read",
        "approval",
        ("/api/v1/approvals/{approval_id}",),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "Read one approval request.",
    ),
    _spec(
        "approval/decide",
        "approval",
        ("approve/reject endpoints",),
        "mapped",
        "write",
        True,
        "adapter_pending",
        "Decide an approval with scoped decision values.",
    ),
    _spec(
        "approval/execute",
        "approval",
        ("/api/v1/approvals/{approval_id}/execute",),
        "mapped",
        "execute",
        True,
        "adapter_pending",
        "Execute an approved action.",
    ),
    _spec(
        "mcp/status",
        "mcp",
        ("/api/v1/mcp/status", "/api/v1/mcp/health"),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "Read MCP manager health.",
    ),
    _spec(
        "mcp/tool/list",
        "mcp",
        ("/api/v1/mcp/tools",),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "List governed MCP tools.",
    ),
    _spec(
        "mcp/tool/call",
        "mcp",
        ("/api/v1/mcp/tools/execute",),
        "mapped",
        "execute",
        True,
        "adapter_pending",
        "Call a governed MCP tool.",
    ),
    _spec(
        "mcp/resource/read",
        "mcp",
        ("no unified endpoint",),
        "missing",
        "read",
        False,
        "adapter_pending",
        "Read an MCP resource without exposing secrets.",
    ),
    _spec(
        "mcp/oauth/login",
        "mcp",
        ("no unified endpoint",),
        "missing",
        "write",
        True,
        "adapter_pending",
        "Start an owner-approved MCP OAuth flow.",
    ),
    _spec(
        "mcp/elicitation/respond",
        "mcp",
        ("no unified endpoint",),
        "missing",
        "write",
        True,
        "adapter_pending",
        "Respond to MCP elicitation.",
    ),
    _spec(
        "plugin/list",
        "plugin",
        ("/api/v1/plugins", "plugin market endpoints"),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "List governed plugins.",
    ),
    _spec(
        "plugin/read",
        "plugin",
        ("plugin detail endpoints",),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "Read plugin metadata.",
    ),
    _spec(
        "plugin/install",
        "plugin",
        ("install endpoints",),
        "mapped",
        "write",
        True,
        "adapter_pending",
        "Install a plugin after governance checks.",
    ),
    _spec(
        "plugin/uninstall",
        "plugin",
        ("uninstall endpoints",),
        "mapped",
        "write",
        True,
        "adapter_pending",
        "Uninstall a plugin with audit evidence.",
    ),
    _spec(
        "plugin/share",
        "plugin",
        ("no unified commercial sharing model",),
        "missing",
        "write",
        True,
        "adapter_pending",
        "Share a plugin through commercial review.",
    ),
    _spec(
        "plugin/review",
        "plugin",
        ("plugin review/security-scan endpoints",),
        "partial",
        "write",
        True,
        "adapter_pending",
        "Review plugin permissions and security.",
    ),
    _spec(
        "skill/list",
        "skill",
        ("/api/v1/skills", "skill market endpoints"),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "List governed skills.",
    ),
    _spec(
        "skill/analyze",
        "skill",
        ("/api/v1/skill-curator/analyze",),
        "mapped",
        "write",
        False,
        "adapter_pending",
        "Analyze skill candidates.",
    ),
    _spec(
        "skill/draft",
        "skill",
        ("/api/v1/skill-curator/draft",),
        "mapped",
        "write",
        False,
        "adapter_pending",
        "Draft a skill under review gate.",
    ),
    _spec(
        "skill/validate",
        "skill",
        ("no unified endpoint",),
        "missing",
        "write",
        False,
        "adapter_pending",
        "Validate a drafted skill.",
    ),
    _spec(
        "skill/promote",
        "skill",
        ("approve/install endpoints",),
        "partial",
        "write",
        True,
        "adapter_pending",
        "Promote a reviewed skill.",
    ),
    _spec(
        "skill/rollback",
        "skill",
        ("advanced skill market version rollback",),
        "partial",
        "write",
        True,
        "adapter_pending",
        "Rollback a promoted skill version.",
    ),
    _spec(
        "channel/status",
        "channel",
        ("Feishu status", "enterprise IM status endpoints"),
        "partial",
        "read",
        False,
        "read_only_contract",
        "Read channel readiness and status.",
    ),
    _spec(
        "channel/webhook/ingest",
        "channel",
        ("/api/v1/integrations/feishu/events",),
        "mapped",
        "write",
        False,
        "adapter_pending",
        "Ingest a signed channel webhook.",
    ),
    _spec(
        "channel/send",
        "channel",
        ("Feishu send", "enterprise IM send"),
        "mapped",
        "write",
        True,
        "adapter_pending",
        "Send a channel message behind owner gate.",
    ),
    _spec(
        "channel/readiness",
        "channel",
        ("commercial pilot readiness scripts",),
        "partial",
        "read",
        False,
        "read_only_contract",
        "Read commercial channel readiness.",
    ),
    _spec(
        "runtime/rc/status",
        "runtime/evidence",
        ("scripts/rc_delivery_status.py",),
        "mapped",
        "read",
        False,
        "read_only_contract",
        "Read RC delivery status evidence.",
    ),
    _spec(
        "runtime/smoke/run",
        "runtime/evidence",
        ("smoke scripts and pytest groups",),
        "partial",
        "execute",
        True,
        "adapter_pending",
        "Run a governed smoke check.",
    ),
    _spec(
        "runtime/evidence/read",
        "runtime/evidence",
        (".xagent_runtime/reports/*.json",),
        "partial",
        "read",
        False,
        "read_only_contract",
        "Read runtime evidence metadata.",
    ),
    _spec(
        "runtime/package/create",
        "runtime/evidence",
        ("RC evidence pack/source bundle scripts",),
        "mapped",
        "write",
        True,
        "adapter_pending",
        "Create a delivery evidence package.",
    ),
)

METHODS_BY_NAME = {spec.method: spec for spec in METHOD_SPECS}


class ControlPlaneContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str | None = None
    actor_id: str | None = None
    user_id: str | None = None
    workspace_id: str | None = None
    trace_id: str | None = None
    sdk_surface: str | None = None
    sdk_operation: str | None = None
    non_interactive: bool | None = None


class ControlPlaneInvokeRequest(BaseModel):
    id: str = Field(default_factory=lambda: f"req_{uuid4().hex}")
    method: str = Field(..., min_length=1, max_length=160)
    params: dict[str, Any] = Field(default_factory=dict)
    context: ControlPlaneContext = Field(default_factory=ControlPlaneContext)
    idempotency_key: str | None = Field(default=None, max_length=240)
    dry_run: bool = True


class SDKControlPlaneInvokeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    operation: str | None = Field(default=None, max_length=160)
    request: ControlPlaneInvokeRequest | None = None
    approved_approval_id: str | None = Field(default=None, max_length=240)
    owner_approved: bool = False
    id: str = Field(default_factory=lambda: f"sdk_req_{uuid4().hex}")
    method: str | None = Field(default=None, min_length=1, max_length=160)
    params: dict[str, Any] = Field(default_factory=dict)
    context: ControlPlaneContext = Field(default_factory=ControlPlaneContext)
    idempotency_key: str | None = Field(default=None, max_length=240)
    dry_run: bool = True
    mutation_performed: bool = False
    network_mutation_performed: bool = False


class ControlPlaneError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ControlPlaneEvidence(BaseModel):
    trace_id: str
    audit_id: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ControlPlaneInvokeResponse(BaseModel):
    id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: ControlPlaneError | None = None
    evidence: ControlPlaneEvidence


class SDKControlPlaneInvokeResponse(BaseModel):
    id: str
    ok: bool
    status: str
    sdk: dict[str, Any]
    control_plane: ControlPlaneInvokeResponse
    evidence: ControlPlaneEvidence


class SDKOwnerAcceptanceRecordRequest(BaseModel):
    owner_acceptance_id: str = Field(..., min_length=1, max_length=240)
    approval_id: str = Field(..., min_length=1, max_length=240)
    accepted_by: str = Field(..., min_length=1, max_length=240)
    accepted_at: str = Field(..., min_length=1, max_length=80)
    runbook_acknowledged: bool = False
    rollback_plan_acknowledged: bool = False
    acceptance_signature: str | None = Field(default=None, max_length=500)
    acceptance_hash: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    dry_run: bool = True


class SDKOwnerAcceptanceRecordResponse(BaseModel):
    ok: bool
    status: str
    owner_acceptance: dict[str, Any]
    evidence: ControlPlaneEvidence


class SDKRuntimeEnablementReceiptRecordRequest(BaseModel):
    readiness_receipt_id: str = Field(..., min_length=1, max_length=240)
    approval_id: str = Field(..., min_length=1, max_length=240)
    owner_acceptance_id: str = Field(..., min_length=1, max_length=240)
    owner_acceptance_audit_id: str = Field(..., min_length=1, max_length=240)
    runtime_flag_name: str = Field(default="XAGENT_SDK_WRITE_RUNNER_ENABLED", min_length=1, max_length=240)
    smoke_runbook_version: str = Field(..., min_length=1, max_length=80)
    rollback_runbook_version: str = Field(..., min_length=1, max_length=80)
    accepted_by: str = Field(..., min_length=1, max_length=240)
    accepted_at: str = Field(..., min_length=1, max_length=80)
    expires_at: str = Field(..., min_length=1, max_length=80)
    smoke_runbook_acknowledged: bool = False
    rollback_runbook_acknowledged: bool = False
    failure_receipt_reviewed: bool = False
    acceptance_signature: str | None = Field(default=None, max_length=500)
    acceptance_hash: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    dry_run: bool = True


class SDKRuntimeEnablementReceiptRecordResponse(BaseModel):
    ok: bool
    status: str
    runtime_enablement_receipt: dict[str, Any]
    evidence: ControlPlaneEvidence


class SDKRuntimeEnablementOwnerPackDecisionRecordRequest(BaseModel):
    owner_pack_decision_id: str = Field(..., min_length=1, max_length=240)
    decision: str = Field(..., min_length=1, max_length=20)
    approval_id: str = Field(..., min_length=1, max_length=240)
    readiness_receipt_id: str = Field(..., min_length=1, max_length=240)
    readiness_receipt_audit_id: str = Field(..., min_length=1, max_length=240)
    owner_acceptance_id: str = Field(..., min_length=1, max_length=240)
    owner_acceptance_audit_id: str = Field(..., min_length=1, max_length=240)
    decided_by: str = Field(..., min_length=1, max_length=240)
    decided_at: str = Field(..., min_length=1, max_length=80)
    reason: str = Field(..., min_length=1, max_length=1000)
    decision_signature: str | None = Field(default=None, max_length=500)
    decision_hash: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    dry_run: bool = True


class SDKRuntimeEnablementOwnerPackDecisionRecordResponse(BaseModel):
    ok: bool
    status: str
    owner_pack_decision: dict[str, Any]
    evidence: ControlPlaneEvidence


class SDKRuntimeImplementationReadinessLockRecordRequest(BaseModel):
    implementation_lock_id: str = Field(..., min_length=1, max_length=240)
    idempotency_key: str = Field(..., min_length=1, max_length=240)
    idempotency_hash: str = Field(..., min_length=1, max_length=500)
    approval_id: str = Field(..., min_length=1, max_length=240)
    readiness_receipt_id: str = Field(..., min_length=1, max_length=240)
    readiness_receipt_audit_id: str = Field(..., min_length=1, max_length=240)
    owner_pack_decision_id: str = Field(..., min_length=1, max_length=240)
    owner_pack_decision_audit_id: str = Field(..., min_length=1, max_length=240)
    operator_id: str = Field(..., min_length=1, max_length=240)
    locked_at: str = Field(..., min_length=1, max_length=80)
    lock_reason: str = Field(..., min_length=1, max_length=1000)
    lock_signature: str | None = Field(default=None, max_length=500)
    lock_hash: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    dry_run: bool = True


class SDKRuntimeImplementationReadinessLockRecordResponse(BaseModel):
    ok: bool
    status: str
    readiness_lock: dict[str, Any]
    evidence: ControlPlaneEvidence


class SDKRuntimeImplementationFinalDecisionRecordRequest(BaseModel):
    final_decision_id: str = Field(..., min_length=1, max_length=240)
    decision: str = Field(..., min_length=1, max_length=20)
    approval_id: str = Field(..., min_length=1, max_length=240)
    implementation_lock_id: str = Field(..., min_length=1, max_length=240)
    implementation_lock_audit_id: str = Field(..., min_length=1, max_length=240)
    readiness_receipt_id: str = Field(..., min_length=1, max_length=240)
    owner_pack_decision_id: str = Field(..., min_length=1, max_length=240)
    decided_by: str = Field(..., min_length=1, max_length=240)
    decided_at: str = Field(..., min_length=1, max_length=80)
    reason: str = Field(..., min_length=1, max_length=1000)
    decision_signature: str | None = Field(default=None, max_length=500)
    decision_hash: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    dry_run: bool = True


class SDKRuntimeImplementationFinalDecisionRecordResponse(BaseModel):
    ok: bool
    status: str
    final_decision: dict[str, Any]
    evidence: ControlPlaneEvidence


class SDKRuntimeFlagEnablementRecordRequest(BaseModel):
    runtime_flag_enablement_id: str = Field(..., min_length=1, max_length=240)
    approval_id: str = Field(..., min_length=1, max_length=240)
    final_decision_id: str = Field(..., min_length=1, max_length=240)
    final_decision_audit_id: str = Field(..., min_length=1, max_length=240)
    implementation_lock_id: str = Field(..., min_length=1, max_length=240)
    readiness_receipt_id: str = Field(..., min_length=1, max_length=240)
    runtime_flag_name: str = Field(..., min_length=1, max_length=240)
    requested_by: str = Field(..., min_length=1, max_length=240)
    requested_at: str = Field(..., min_length=1, max_length=80)
    enablement_reason: str = Field(..., min_length=1, max_length=1000)
    enablement_signature: str | None = Field(default=None, max_length=500)
    enablement_hash: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    dry_run: bool = True


class SDKRuntimeFlagEnablementRecordResponse(BaseModel):
    ok: bool
    status: str
    runtime_flag_enablement: dict[str, Any]
    evidence: ControlPlaneEvidence


def _method_catalog() -> list[dict[str, object]]:
    return [spec.to_payload() for spec in METHOD_SPECS]


def _group_catalog() -> dict[str, list[dict[str, object]]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for spec in METHOD_SPECS:
        groups.setdefault(spec.group, []).append(spec.to_payload())
    return groups


def _status_payload() -> dict[str, object]:
    mapped = sum(1 for spec in METHOD_SPECS if spec.status == "mapped")
    partial = sum(1 for spec in METHOD_SPECS if spec.status == "partial")
    missing = sum(1 for spec in METHOD_SPECS if spec.status == "missing")
    return {
        "status": "control_plane_contract_ready",
        "implementation_stage": "contract_first",
        "full_codex_parity_claimed": False,
        "method_count": len(METHOD_SPECS),
        "mapped_count": mapped,
        "partial_count": partial,
        "missing_count": missing,
        "groups": sorted(_group_catalog()),
        "status_vocabulary": list(STATUS_VOCABULARY),
        "safety": {
            "auditable": True,
            "raw_secret_payloads_rejected": True,
            "mutation_performed": False,
            "adapter_execution_enabled": False,
        },
    }


@router.get("")
async def get_control_plane_status(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:read")
    return _status_payload()


@router.get("/methods")
async def list_control_plane_methods(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:read")
    return {
        **_status_payload(),
        "methods": _method_catalog(),
        "method_groups": _group_catalog(),
    }


@router.post("/invoke", response_model=ControlPlaneInvokeResponse)
async def invoke_control_plane(
    request: ControlPlaneInvokeRequest,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
    run_store: RunStoreDependency,
    trace_store: TraceStoreDependency,
    approval_store: ApprovalStoreDependency,
) -> ControlPlaneInvokeResponse:
    enforce_scope(principal, "agent:read")
    trace_id = request.context.trace_id or principal.trace_id or f"trace_{uuid4().hex}"
    secret_paths = _find_secret_paths(
        {
            "params": request.params,
            "context": request.context.model_dump(mode="json", exclude_none=True),
        }
    )
    if secret_paths:
        audit = _audit(
            audit_store,
            principal,
            request=request,
            trace_id=trace_id,
            outcome="rejected",
            details={"reason": "raw_secret_payload", "secret_paths": secret_paths},
        )
        return ControlPlaneInvokeResponse(
            id=request.id,
            ok=False,
            error=ControlPlaneError(
                code="raw_secret_payload_rejected",
                message="Raw production secrets are not accepted by the control plane. Use a configured secret reference.",
                retryable=False,
                details={"secret_paths": secret_paths},
            ),
            evidence=ControlPlaneEvidence(trace_id=trace_id, audit_id=audit.id),
        )

    spec = METHODS_BY_NAME.get(request.method)
    if spec is None:
        audit = _audit(
            audit_store,
            principal,
            request=request,
            trace_id=trace_id,
            outcome="failed",
            details={"reason": "method_not_found"},
        )
        return ControlPlaneInvokeResponse(
            id=request.id,
            ok=False,
            error=ControlPlaneError(
                code="method_not_found",
                message=f"Unknown control-plane method: {request.method}",
                retryable=False,
            ),
            evidence=ControlPlaneEvidence(trace_id=trace_id, audit_id=audit.id),
        )

    if spec.operation_kind == "read" and spec.implementation_state == "read_only_contract":
        result = _contract_result(
            spec,
            request,
            principal=principal,
            audit_store=audit_store,
            run_store=run_store,
            trace_store=trace_store,
            approval_store=approval_store,
        )
        audit = _audit(
            audit_store,
            principal,
            request=request,
            trace_id=trace_id,
            outcome="success",
            details={"method": spec.method, "group": spec.group, "contract_only": True},
        )
        return ControlPlaneInvokeResponse(
            id=request.id,
            ok=True,
            result=result,
            evidence=ControlPlaneEvidence(trace_id=trace_id, audit_id=audit.id),
        )

    error_code = "approval_required" if spec.requires_approval else "adapter_pending"
    message = (
        "This control-plane method requires approval and a concrete adapter before execution."
        if spec.requires_approval
        else "This control-plane method is registered but its concrete adapter is not implemented yet."
    )
    adapter_details = _adapter_pending_details(
        spec,
        request,
        run_store=run_store,
        trace_store=trace_store,
        approval_store=approval_store,
    )
    audit = _audit(
        audit_store,
        principal,
        request=request,
        trace_id=trace_id,
        outcome="blocked",
        details=adapter_details,
    )
    return ControlPlaneInvokeResponse(
        id=request.id,
        ok=False,
        error=ControlPlaneError(
            code=error_code,
            message=message,
            retryable=True,
            details=adapter_details,
        ),
        evidence=ControlPlaneEvidence(trace_id=trace_id, audit_id=audit.id),
    )


@router.post("/sdk/invoke", response_model=SDKControlPlaneInvokeResponse)
async def invoke_sdk_control_plane(
    request: SDKControlPlaneInvokeRequest,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
    run_store: RunStoreDependency,
    trace_store: TraceStoreDependency,
    approval_store: ApprovalStoreDependency,
) -> SDKControlPlaneInvokeResponse:
    """Accept SDK envelopes without enabling adapter execution."""
    control_request = _sdk_control_plane_request(request)
    control_response = await invoke_control_plane(
        control_request,
        principal,
        audit_store,
        run_store,
        trace_store,
        approval_store,
    )
    approved_approval_id = _sdk_approved_approval_id(request, control_request)
    approval_intent = _sdk_approval_intent(
        control_request,
        principal=principal,
        approval_store=approval_store,
        approved_approval_id=approved_approval_id,
    )
    sdk_metadata = _sdk_backend_stub_metadata(
        request,
        control_request,
        control_response,
        approval_intent=approval_intent,
        approval_store=approval_store,
        principal=principal,
    )
    sdk_metadata["dry_run_executor_stub"] = _sdk_dry_run_executor_stub(
        audit_store,
        principal,
        request=control_request,
        trace_id=control_response.evidence.trace_id,
        write_runner_safety_contract=sdk_metadata["write_runner_safety_contract"],
    )
    sdk_metadata["write_runner_execute_gate"] = _sdk_write_runner_execute_gate(
        request,
        control_request,
        execution_adapter_contract=sdk_metadata["execution_adapter_contract"],
        write_runner_safety_contract=sdk_metadata["write_runner_safety_contract"],
        dry_run_executor_stub=sdk_metadata["dry_run_executor_stub"],
    )
    sdk_metadata["write_runner_adapter_review"] = _sdk_write_runner_adapter_review(
        request,
        control_request,
        execution_adapter_contract=sdk_metadata["execution_adapter_contract"],
        write_runner_execute_gate=sdk_metadata["write_runner_execute_gate"],
    )
    sdk_metadata["write_runner_runtime_flag"] = _sdk_write_runner_runtime_flag_contract(
        control_request,
        write_runner_adapter_review=sdk_metadata["write_runner_adapter_review"],
    )
    sdk_metadata["owner_acceptance_evidence"] = _sdk_owner_acceptance_evidence_contract(
        control_request,
        write_runner_runtime_flag=sdk_metadata["write_runner_runtime_flag"],
    )
    sdk_metadata["runtime_enablement_review"] = _sdk_runtime_enablement_review_contract(
        control_request,
        write_runner_runtime_flag=sdk_metadata["write_runner_runtime_flag"],
        owner_acceptance_evidence=sdk_metadata["owner_acceptance_evidence"],
        write_runner_execute_gate=sdk_metadata["write_runner_execute_gate"],
        write_runner_adapter_review=sdk_metadata["write_runner_adapter_review"],
    )
    sdk_metadata["write_runner_implementation_plan"] = _sdk_write_runner_implementation_plan_contract(
        control_request,
        runtime_enablement_review=sdk_metadata["runtime_enablement_review"],
        write_runner_adapter_review=sdk_metadata["write_runner_adapter_review"],
        write_runner_execute_gate=sdk_metadata["write_runner_execute_gate"],
        owner_acceptance_evidence=sdk_metadata["owner_acceptance_evidence"],
    )
    sdk_metadata["runtime_smoke_runbook"] = _sdk_runtime_smoke_runbook_contract(
        sdk_metadata["write_runner_implementation_plan"],
    )
    sdk_metadata["runtime_enablement_receipt"] = _sdk_runtime_enablement_receipt_contract(
        sdk_metadata["runtime_smoke_runbook"],
    )
    sdk_metadata["runtime_implementation_preflight"] = _sdk_runtime_implementation_preflight_contract(
        sdk_metadata["runtime_enablement_receipt"],
        sdk_metadata["write_runner_implementation_plan"],
    )
    sdk_metadata["runtime_enablement_receipt_record_workflow"] = (
        _sdk_runtime_enablement_receipt_record_workflow_contract(
            sdk_metadata["runtime_implementation_preflight"],
        )
    )
    sdk_metadata["runtime_enablement_owner_pack"] = _sdk_runtime_enablement_owner_pack_contract(
        sdk_metadata["runtime_enablement_receipt_record_workflow"],
        runtime_enablement_receipt=sdk_metadata["runtime_enablement_receipt"],
        runtime_smoke_runbook=sdk_metadata["runtime_smoke_runbook"],
        owner_acceptance_evidence=sdk_metadata["owner_acceptance_evidence"],
        runtime_enablement_review=sdk_metadata["runtime_enablement_review"],
        runtime_implementation_preflight=sdk_metadata["runtime_implementation_preflight"],
    )
    sdk_metadata["runtime_enablement_owner_pack_decision_workflow"] = (
        _sdk_runtime_enablement_owner_pack_decision_workflow_contract(
            sdk_metadata["runtime_enablement_owner_pack"],
        )
    )
    sdk_metadata["runtime_implementation_readiness_lock_workflow"] = (
        _sdk_runtime_implementation_readiness_lock_workflow_contract(
            sdk_metadata["runtime_enablement_owner_pack_decision_workflow"],
        )
    )
    sdk_metadata["runtime_implementation_owner_pack"] = _sdk_runtime_implementation_owner_pack_contract(
        sdk_metadata["runtime_implementation_readiness_lock_workflow"],
    )
    sdk_metadata["runtime_implementation_final_decision_workflow"] = (
        _sdk_runtime_implementation_final_decision_workflow_contract(
            sdk_metadata["runtime_implementation_owner_pack"],
        )
    )
    sdk_metadata["runtime_flag_enablement_record_workflow"] = (
        _sdk_runtime_flag_enablement_record_workflow_contract(
            sdk_metadata["runtime_implementation_final_decision_workflow"],
        )
    )
    return SDKControlPlaneInvokeResponse(
        id=control_request.id,
        ok=control_response.ok,
        status=sdk_metadata["status"],
        sdk=sdk_metadata,
        control_plane=control_response,
        evidence=control_response.evidence,
    )


@router.post("/sdk/owner-acceptance/record", response_model=SDKOwnerAcceptanceRecordResponse)
async def record_sdk_owner_acceptance(
    request: SDKOwnerAcceptanceRecordRequest,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
    approval_store: ApprovalStoreDependency,
) -> SDKOwnerAcceptanceRecordResponse:
    """Record owner acceptance evidence without enabling SDK write execution."""
    enforce_scope(principal, "workflow:control")
    trace_id = principal.trace_id or f"trace_{uuid4().hex}"
    owner_acceptance = _sdk_record_owner_acceptance(
        request,
        principal=principal,
        approval_store=approval_store,
        audit_store=audit_store,
        trace_id=trace_id,
    )
    evidence = ControlPlaneEvidence(
        trace_id=trace_id,
        audit_id=owner_acceptance.get("audit_id") if owner_acceptance.get("audit_event_recorded") else None,
    )
    return SDKOwnerAcceptanceRecordResponse(
        ok=owner_acceptance["record_status"] == "recorded",
        status="sdk_owner_acceptance_record_workflow_ready",
        owner_acceptance=owner_acceptance,
        evidence=evidence,
    )


@router.post(
    "/sdk/runtime-enablement/receipt/record",
    response_model=SDKRuntimeEnablementReceiptRecordResponse,
)
async def record_sdk_runtime_enablement_receipt(
    request: SDKRuntimeEnablementReceiptRecordRequest,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
    approval_store: ApprovalStoreDependency,
) -> SDKRuntimeEnablementReceiptRecordResponse:
    """Record a runtime enablement readiness receipt without enabling execution."""
    enforce_scope(principal, "workflow:control")
    trace_id = principal.trace_id or f"trace_{uuid4().hex}"
    receipt = _sdk_record_runtime_enablement_receipt(
        request,
        principal=principal,
        approval_store=approval_store,
        audit_store=audit_store,
        trace_id=trace_id,
    )
    evidence = ControlPlaneEvidence(
        trace_id=trace_id,
        audit_id=receipt.get("audit_id") if receipt.get("audit_event_recorded") else None,
    )
    return SDKRuntimeEnablementReceiptRecordResponse(
        ok=receipt["record_status"] == "recorded",
        status="sdk_runtime_enablement_receipt_record_workflow_ready",
        runtime_enablement_receipt=receipt,
        evidence=evidence,
    )


@router.post(
    "/sdk/runtime-enablement/owner-pack/decision/record",
    response_model=SDKRuntimeEnablementOwnerPackDecisionRecordResponse,
)
async def record_sdk_runtime_enablement_owner_pack_decision(
    request: SDKRuntimeEnablementOwnerPackDecisionRecordRequest,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
    approval_store: ApprovalStoreDependency,
) -> SDKRuntimeEnablementOwnerPackDecisionRecordResponse:
    """Record an owner decision for the runtime enablement review pack without executing it."""
    enforce_scope(principal, "workflow:control")
    trace_id = principal.trace_id or f"trace_{uuid4().hex}"
    decision = _sdk_record_runtime_enablement_owner_pack_decision(
        request,
        principal=principal,
        approval_store=approval_store,
        audit_store=audit_store,
        trace_id=trace_id,
    )
    evidence = ControlPlaneEvidence(
        trace_id=trace_id,
        audit_id=decision.get("audit_id") if decision.get("audit_event_recorded") else None,
    )
    return SDKRuntimeEnablementOwnerPackDecisionRecordResponse(
        ok=decision["record_status"] == "recorded",
        status="sdk_runtime_enablement_owner_pack_decision_workflow_ready",
        owner_pack_decision=decision,
        evidence=evidence,
    )


@router.post(
    "/sdk/runtime-implementation/readiness-lock/record",
    response_model=SDKRuntimeImplementationReadinessLockRecordResponse,
)
async def record_sdk_runtime_implementation_readiness_lock(
    request: SDKRuntimeImplementationReadinessLockRecordRequest,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
    approval_store: ApprovalStoreDependency,
) -> SDKRuntimeImplementationReadinessLockRecordResponse:
    """Record a runtime implementation readiness lock without executing the runner."""
    enforce_scope(principal, "workflow:control")
    trace_id = principal.trace_id or f"trace_{uuid4().hex}"
    readiness_lock = _sdk_record_runtime_implementation_readiness_lock(
        request,
        principal=principal,
        approval_store=approval_store,
        audit_store=audit_store,
        trace_id=trace_id,
    )
    evidence = ControlPlaneEvidence(
        trace_id=trace_id,
        audit_id=readiness_lock.get("audit_id") if readiness_lock.get("audit_event_recorded") else None,
    )
    return SDKRuntimeImplementationReadinessLockRecordResponse(
        ok=readiness_lock["record_status"] == "recorded",
        status="sdk_runtime_implementation_readiness_lock_workflow_ready",
        readiness_lock=readiness_lock,
        evidence=evidence,
    )


@router.post(
    "/sdk/runtime-implementation/final-decision/record",
    response_model=SDKRuntimeImplementationFinalDecisionRecordResponse,
)
async def record_sdk_runtime_implementation_final_decision(
    request: SDKRuntimeImplementationFinalDecisionRecordRequest,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
    approval_store: ApprovalStoreDependency,
) -> SDKRuntimeImplementationFinalDecisionRecordResponse:
    """Record the final owner decision before runtime implementation, without executing it."""
    enforce_scope(principal, "workflow:control")
    trace_id = principal.trace_id or f"trace_{uuid4().hex}"
    final_decision = _sdk_record_runtime_implementation_final_decision(
        request,
        principal=principal,
        approval_store=approval_store,
        audit_store=audit_store,
        trace_id=trace_id,
    )
    evidence = ControlPlaneEvidence(
        trace_id=trace_id,
        audit_id=final_decision.get("audit_id") if final_decision.get("audit_event_recorded") else None,
    )
    return SDKRuntimeImplementationFinalDecisionRecordResponse(
        ok=final_decision["record_status"] == "recorded",
        status="sdk_runtime_implementation_final_decision_workflow_ready",
        final_decision=final_decision,
        evidence=evidence,
    )


@router.post(
    "/sdk/runtime-flag/enablement/record",
    response_model=SDKRuntimeFlagEnablementRecordResponse,
)
async def record_sdk_runtime_flag_enablement(
    request: SDKRuntimeFlagEnablementRecordRequest,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
    approval_store: ApprovalStoreDependency,
) -> SDKRuntimeFlagEnablementRecordResponse:
    """Record explicit owner runtime flag enablement intent without enabling the flag."""
    enforce_scope(principal, "workflow:control")
    trace_id = principal.trace_id or f"trace_{uuid4().hex}"
    runtime_flag_enablement = _sdk_record_runtime_flag_enablement(
        request,
        principal=principal,
        approval_store=approval_store,
        audit_store=audit_store,
        trace_id=trace_id,
    )
    evidence = ControlPlaneEvidence(
        trace_id=trace_id,
        audit_id=runtime_flag_enablement.get("audit_id")
        if runtime_flag_enablement.get("audit_event_recorded")
        else None,
    )
    return SDKRuntimeFlagEnablementRecordResponse(
        ok=runtime_flag_enablement["record_status"] == "recorded",
        status="sdk_runtime_flag_enablement_record_workflow_ready",
        runtime_flag_enablement=runtime_flag_enablement,
        evidence=evidence,
    )


def _sdk_control_plane_request(request: SDKControlPlaneInvokeRequest) -> ControlPlaneInvokeRequest:
    if request.request is not None:
        payload = request.request
        context = payload.context.model_copy(
            update={
                "sdk_surface": payload.context.sdk_surface or request.context.sdk_surface or "python",
                "sdk_operation": payload.context.sdk_operation or request.operation,
                "non_interactive": True
                if payload.context.non_interactive is None
                else payload.context.non_interactive,
            }
        )
        return payload.model_copy(
            update={
                "context": context,
                "idempotency_key": payload.idempotency_key or request.idempotency_key,
                "dry_run": payload.dry_run and request.dry_run,
            }
        )
    if not request.method:
        return ControlPlaneInvokeRequest(
            id=request.id,
            method="sdk/missing-method",
            params=request.params,
            context=request.context.model_copy(
                update={
                    "sdk_surface": request.context.sdk_surface or "python",
                    "sdk_operation": request.operation,
                    "non_interactive": True,
                }
            ),
            idempotency_key=request.idempotency_key,
            dry_run=request.dry_run,
        )
    return ControlPlaneInvokeRequest(
        id=request.id,
        method=request.method,
        params=request.params,
        context=request.context.model_copy(
            update={
                "sdk_surface": request.context.sdk_surface or "python",
                "sdk_operation": request.operation,
                "non_interactive": True,
            }
        ),
        idempotency_key=request.idempotency_key,
        dry_run=request.dry_run,
    )


def _sdk_record_owner_acceptance(
    request: SDKOwnerAcceptanceRecordRequest,
    *,
    principal: Principal,
    approval_store: object,
    audit_store: AuditStore,
    trace_id: str,
) -> dict[str, Any]:
    approval = approval_store.get(request.approval_id) if hasattr(approval_store, "get") else None
    raw_evidence = {
        "owner_acceptance_id": request.owner_acceptance_id,
        "accepted_by": request.accepted_by,
        "accepted_at": request.accepted_at,
        "approval_id": request.approval_id,
        "runbook_acknowledged": request.runbook_acknowledged,
        "rollback_plan_acknowledged": request.rollback_plan_acknowledged,
        "acceptance_signature": request.acceptance_signature,
        "acceptance_hash": request.acceptance_hash,
        "notes": request.notes,
    }
    validation = _sdk_owner_acceptance_evidence_validation(raw_evidence)
    approval_status = getattr(approval, "status", None)
    approval_status_value = getattr(approval_status, "value", approval_status)
    approval_resource_id = getattr(approval, "resource_id", None)
    approval_tenant_id = getattr(approval, "tenant_id", None)
    checks = {
        "approval_found": approval is not None,
        "approval_status_approved": approval_status == ApprovalStatus.APPROVED or approval_status_value == "approved",
        "approval_resource_sdk_command": isinstance(approval_resource_id, str)
        and approval_resource_id.startswith("sdk:"),
        "tenant_matches": not principal.authenticated or approval_tenant_id == principal.tenant_id,
        "evidence_valid": validation["status"] == "valid",
        "dry_run_does_not_execute": request.dry_run is True,
    }
    can_record = all(checks.values())
    record_payload = {
        key: value
        for key, value in raw_evidence.items()
        if value is not None
    }
    audit_record = None
    if can_record:
        audit_record = audit_store.record(
            action="sdk.write_runner.owner_acceptance_recorded",
            resource_type="sdk_write_runner_owner_acceptance",
            resource_id=request.owner_acceptance_id,
            outcome="accepted",
            tenant_id=approval_tenant_id or principal.tenant_id,
            actor_id=principal.user_id if principal.authenticated else request.accepted_by,
            trace_id=trace_id,
            details={
                "approval_id": request.approval_id,
                "owner_acceptance_evidence": record_payload,
                "validation": validation,
                "dry_run": request.dry_run,
                "execution_enabled": False,
                "write_runner_enabled": False,
                "mutation_performed": False,
            },
        )
    return {
        "stage": "owner_acceptance_evidence_record_workflow",
        "record_status": "recorded" if audit_record else "rejected",
        "recording_endpoint": "/api/v1/control-plane/sdk/owner-acceptance/record",
        "owner_acceptance_id": request.owner_acceptance_id,
        "approval_id": request.approval_id,
        "approval_status": approval_status_value,
        "approval_resource_id": approval_resource_id,
        "checks": checks,
        "validation": validation,
        "audit_event_recorded": audit_record is not None,
        "audit_action": "sdk.write_runner.owner_acceptance_recorded",
        "audit_id": getattr(audit_record, "id", None) if audit_record else None,
        "audit_hash": getattr(audit_record, "hash", None) if audit_record else None,
        "audit_signature_present": bool(getattr(audit_record, "signature", None)) if audit_record else False,
        "readback": {
            "method": "runtime/evidence/read",
            "endpoint": "/api/v1/control-plane/invoke",
            "params": {
                "evidence_type": "sdk_write_runner_owner_acceptance",
                "report_name": "sdk-write-runner-owner-acceptance.json",
                "approval_id": request.approval_id,
                "owner_acceptance_id": request.owner_acceptance_id,
                "audit_id": getattr(audit_record, "id", None) if audit_record else None,
            },
        },
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This endpoint records owner acceptance evidence only.",
            "It does not mark the approval executed.",
            "It does not enable or invoke the SDK write runner.",
        ],
    }


def _sdk_record_runtime_enablement_receipt(
    request: SDKRuntimeEnablementReceiptRecordRequest,
    *,
    principal: Principal,
    approval_store: object,
    audit_store: AuditStore,
    trace_id: str,
) -> dict[str, Any]:
    approval = approval_store.get(request.approval_id) if hasattr(approval_store, "get") else None
    owner_acceptance = _sdk_owner_acceptance_record_from_audit(
        audit_store,
        approval_id=request.approval_id,
        owner_acceptance_id=request.owner_acceptance_id,
        audit_id=request.owner_acceptance_audit_id,
        tenant_id=principal.tenant_id if principal else None,
    )
    raw_receipt = {
        "readiness_receipt_id": request.readiness_receipt_id,
        "approval_id": request.approval_id,
        "owner_acceptance_id": request.owner_acceptance_id,
        "owner_acceptance_audit_id": request.owner_acceptance_audit_id,
        "runtime_flag_name": request.runtime_flag_name,
        "smoke_runbook_version": request.smoke_runbook_version,
        "rollback_runbook_version": request.rollback_runbook_version,
        "accepted_by": request.accepted_by,
        "accepted_at": request.accepted_at,
        "expires_at": request.expires_at,
        "smoke_runbook_acknowledged": request.smoke_runbook_acknowledged,
        "rollback_runbook_acknowledged": request.rollback_runbook_acknowledged,
        "failure_receipt_reviewed": request.failure_receipt_reviewed,
        "acceptance_signature": request.acceptance_signature,
        "acceptance_hash": request.acceptance_hash,
        "notes": request.notes,
    }
    validation = _sdk_runtime_enablement_receipt_validation(raw_receipt)
    approval_status = getattr(approval, "status", None)
    approval_status_value = getattr(approval_status, "value", approval_status)
    approval_resource_id = getattr(approval, "resource_id", None)
    approval_tenant_id = getattr(approval, "tenant_id", None)
    checks = {
        "approval_found": approval is not None,
        "approval_status_approved": approval_status == ApprovalStatus.APPROVED or approval_status_value == "approved",
        "approval_resource_sdk_command": isinstance(approval_resource_id, str)
        and approval_resource_id.startswith("sdk:"),
        "tenant_matches": not principal.authenticated or approval_tenant_id == principal.tenant_id,
        "owner_acceptance_audit_record_present": isinstance(owner_acceptance, dict),
        "owner_acceptance_validation_valid": bool(
            isinstance(owner_acceptance, dict)
            and _sdk_owner_acceptance_evidence_validation(owner_acceptance)["status"] == "valid"
        ),
        "receipt_valid": validation["status"] == "valid",
        "dry_run_does_not_execute": request.dry_run is True,
    }
    can_record = all(checks.values())
    receipt_payload = {
        key: value
        for key, value in raw_receipt.items()
        if value is not None
    }
    audit_record = None
    if can_record:
        audit_record = audit_store.record(
            action="sdk.write_runner.runtime_enablement_receipt_recorded",
            resource_type="sdk_write_runner_runtime_enablement_readiness",
            resource_id=request.readiness_receipt_id,
            outcome="accepted",
            tenant_id=approval_tenant_id or principal.tenant_id,
            actor_id=principal.user_id if principal.authenticated else request.accepted_by,
            trace_id=trace_id,
            details={
                "approval_id": request.approval_id,
                "owner_acceptance_id": request.owner_acceptance_id,
                "owner_acceptance_audit_id": request.owner_acceptance_audit_id,
                "runtime_enablement_receipt": receipt_payload,
                "owner_acceptance_record": owner_acceptance,
                "validation": validation,
                "dry_run": request.dry_run,
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        )
    return {
        "stage": "runtime_enablement_readiness_receipt_record_workflow",
        "record_status": "recorded" if audit_record else "rejected",
        "recording_endpoint": "/api/v1/control-plane/sdk/runtime-enablement/receipt/record",
        "readiness_receipt_id": request.readiness_receipt_id,
        "approval_id": request.approval_id,
        "owner_acceptance_id": request.owner_acceptance_id,
        "owner_acceptance_audit_id": request.owner_acceptance_audit_id,
        "approval_status": approval_status_value,
        "approval_resource_id": approval_resource_id,
        "checks": checks,
        "validation": validation,
        "audit_event_recorded": audit_record is not None,
        "audit_action": "sdk.write_runner.runtime_enablement_receipt_recorded",
        "audit_id": getattr(audit_record, "id", None) if audit_record else None,
        "audit_hash": getattr(audit_record, "hash", None) if audit_record else None,
        "audit_signature_present": bool(getattr(audit_record, "signature", None)) if audit_record else False,
        "readback": {
            "method": "runtime/evidence/read",
            "endpoint": "/api/v1/control-plane/invoke",
            "params": {
                "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
                "report_name": "sdk-write-runner-runtime-enable-readiness.json",
                "readiness_receipt_id": request.readiness_receipt_id,
                "approval_id": request.approval_id,
                "owner_acceptance_id": request.owner_acceptance_id,
                "audit_id": getattr(audit_record, "id", None) if audit_record else None,
            },
        },
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This endpoint records runtime enablement readiness receipt evidence only.",
            "It does not enable the runtime flag.",
            "It does not invoke the SDK write runner or mark an approval executed.",
        ],
    }


def _sdk_runtime_enablement_owner_pack_decision_validation(
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    required_fields = [
        "owner_pack_decision_id",
        "decision",
        "approval_id",
        "readiness_receipt_id",
        "readiness_receipt_audit_id",
        "owner_acceptance_id",
        "owner_acceptance_audit_id",
        "decided_by",
        "decided_at",
        "reason",
    ]
    checks = {
        "record_present": isinstance(record, dict),
        "required_fields_present": bool(
            isinstance(record, dict) and all(record.get(field) not in (None, "") for field in required_fields)
        ),
        "decision_allowed": bool(
            isinstance(record, dict) and record.get("decision") in {"accepted", "rejected"}
        ),
        "decided_at_rfc3339": bool(
            isinstance(record, dict) and _is_rfc3339_timestamp(record.get("decided_at"))
        ),
        "signature_or_hash_present": bool(
            isinstance(record, dict) and (record.get("decision_signature") or record.get("decision_hash"))
        ),
    }
    return {
        "status": "valid" if all(checks.values()) else "invalid",
        "checks": checks,
    }


def _sdk_record_runtime_enablement_owner_pack_decision(
    request: SDKRuntimeEnablementOwnerPackDecisionRecordRequest,
    *,
    principal: Principal,
    approval_store: object,
    audit_store: AuditStore,
    trace_id: str,
) -> dict[str, Any]:
    approval = approval_store.get(request.approval_id) if hasattr(approval_store, "get") else None
    readiness_receipt = _sdk_runtime_enablement_readiness_record_from_audit(
        audit_store,
        readiness_receipt_id=request.readiness_receipt_id,
        approval_id=request.approval_id,
        owner_acceptance_id=request.owner_acceptance_id,
        audit_id=request.readiness_receipt_audit_id,
        tenant_id=principal.tenant_id if principal else None,
    )
    raw_decision = {
        "owner_pack_decision_id": request.owner_pack_decision_id,
        "decision": request.decision,
        "approval_id": request.approval_id,
        "readiness_receipt_id": request.readiness_receipt_id,
        "readiness_receipt_audit_id": request.readiness_receipt_audit_id,
        "owner_acceptance_id": request.owner_acceptance_id,
        "owner_acceptance_audit_id": request.owner_acceptance_audit_id,
        "decided_by": request.decided_by,
        "decided_at": request.decided_at,
        "reason": request.reason,
        "decision_signature": request.decision_signature,
        "decision_hash": request.decision_hash,
        "notes": request.notes,
    }
    validation = _sdk_runtime_enablement_owner_pack_decision_validation(raw_decision)
    approval_status = getattr(approval, "status", None)
    approval_status_value = getattr(approval_status, "value", approval_status)
    approval_resource_id = getattr(approval, "resource_id", None)
    approval_tenant_id = getattr(approval, "tenant_id", None)
    checks = {
        "approval_found": approval is not None,
        "approval_status_approved": approval_status == ApprovalStatus.APPROVED or approval_status_value == "approved",
        "approval_resource_sdk_command": isinstance(approval_resource_id, str)
        and approval_resource_id.startswith("sdk:"),
        "tenant_matches": not principal.authenticated or approval_tenant_id == principal.tenant_id,
        "readiness_receipt_audit_record_present": isinstance(readiness_receipt, dict),
        "readiness_receipt_validation_valid": bool(
            isinstance(readiness_receipt, dict)
            and _sdk_runtime_enablement_receipt_validation(readiness_receipt)["status"] == "valid"
        ),
        "decision_valid": validation["status"] == "valid",
        "dry_run_does_not_execute": request.dry_run is True,
    }
    can_record = all(checks.values())
    decision_payload = {
        key: value
        for key, value in raw_decision.items()
        if value is not None
    }
    audit_record = None
    if can_record:
        audit_record = audit_store.record(
            action="sdk.write_runner.runtime_enablement_owner_pack_decision_recorded",
            resource_type="sdk_write_runner_runtime_enablement_owner_review_pack",
            resource_id=request.owner_pack_decision_id,
            outcome=request.decision,
            tenant_id=approval_tenant_id or principal.tenant_id,
            actor_id=principal.user_id if principal.authenticated else request.decided_by,
            trace_id=trace_id,
            details={
                "approval_id": request.approval_id,
                "readiness_receipt_id": request.readiness_receipt_id,
                "readiness_receipt_audit_id": request.readiness_receipt_audit_id,
                "owner_acceptance_id": request.owner_acceptance_id,
                "owner_acceptance_audit_id": request.owner_acceptance_audit_id,
                "owner_pack_decision": decision_payload,
                "readiness_receipt_record": readiness_receipt,
                "validation": validation,
                "dry_run": request.dry_run,
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        )
    return {
        "stage": "runtime_enablement_owner_pack_decision_record_workflow",
        "record_status": "recorded" if audit_record else "rejected",
        "recording_endpoint": "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record",
        "owner_pack_decision_id": request.owner_pack_decision_id,
        "decision": request.decision,
        "approval_id": request.approval_id,
        "readiness_receipt_id": request.readiness_receipt_id,
        "readiness_receipt_audit_id": request.readiness_receipt_audit_id,
        "owner_acceptance_id": request.owner_acceptance_id,
        "owner_acceptance_audit_id": request.owner_acceptance_audit_id,
        "approval_status": approval_status_value,
        "approval_resource_id": approval_resource_id,
        "checks": checks,
        "validation": validation,
        "audit_event_recorded": audit_record is not None,
        "audit_action": "sdk.write_runner.runtime_enablement_owner_pack_decision_recorded",
        "audit_id": getattr(audit_record, "id", None) if audit_record else None,
        "audit_hash": getattr(audit_record, "hash", None) if audit_record else None,
        "audit_signature_present": bool(getattr(audit_record, "signature", None)) if audit_record else False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This endpoint records an owner pack decision only.",
            "Accepted decisions do not enable the runtime flag.",
            "Rejected decisions do not roll back or mutate runtime state.",
            "It does not invoke the SDK write runner or mark an approval executed.",
        ],
    }


def _sdk_runtime_implementation_readiness_lock_validation(
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    required_fields = [
        "implementation_lock_id",
        "idempotency_key",
        "idempotency_hash",
        "approval_id",
        "readiness_receipt_id",
        "readiness_receipt_audit_id",
        "owner_pack_decision_id",
        "owner_pack_decision_audit_id",
        "operator_id",
        "locked_at",
        "lock_reason",
    ]
    checks = {
        "record_present": isinstance(record, dict),
        "required_fields_present": bool(
            isinstance(record, dict) and all(record.get(field) not in (None, "") for field in required_fields)
        ),
        "locked_at_rfc3339": bool(
            isinstance(record, dict) and _is_rfc3339_timestamp(record.get("locked_at"))
        ),
        "idempotency_hash_present": bool(isinstance(record, dict) and record.get("idempotency_hash")),
        "signature_or_hash_present": bool(
            isinstance(record, dict) and (record.get("lock_signature") or record.get("lock_hash"))
        ),
    }
    return {
        "status": "valid" if all(checks.values()) else "invalid",
        "checks": checks,
    }


def _sdk_record_runtime_implementation_readiness_lock(
    request: SDKRuntimeImplementationReadinessLockRecordRequest,
    *,
    principal: Principal,
    approval_store: object,
    audit_store: AuditStore,
    trace_id: str,
) -> dict[str, Any]:
    approval = approval_store.get(request.approval_id) if hasattr(approval_store, "get") else None
    readiness_receipt = _sdk_runtime_enablement_readiness_record_from_audit(
        audit_store,
        readiness_receipt_id=request.readiness_receipt_id,
        approval_id=request.approval_id,
        owner_acceptance_id=None,
        audit_id=request.readiness_receipt_audit_id,
        tenant_id=principal.tenant_id if principal else None,
    )
    owner_pack_decision = _sdk_runtime_enablement_owner_pack_decision_record_from_audit(
        audit_store,
        owner_pack_decision_id=request.owner_pack_decision_id,
        approval_id=request.approval_id,
        readiness_receipt_id=request.readiness_receipt_id,
        audit_id=request.owner_pack_decision_audit_id,
        tenant_id=principal.tenant_id if principal else None,
    )
    raw_lock = {
        "implementation_lock_id": request.implementation_lock_id,
        "idempotency_key": request.idempotency_key,
        "idempotency_hash": request.idempotency_hash,
        "approval_id": request.approval_id,
        "readiness_receipt_id": request.readiness_receipt_id,
        "readiness_receipt_audit_id": request.readiness_receipt_audit_id,
        "owner_pack_decision_id": request.owner_pack_decision_id,
        "owner_pack_decision_audit_id": request.owner_pack_decision_audit_id,
        "operator_id": request.operator_id,
        "locked_at": request.locked_at,
        "lock_reason": request.lock_reason,
        "lock_signature": request.lock_signature,
        "lock_hash": request.lock_hash,
        "notes": request.notes,
    }
    validation = _sdk_runtime_implementation_readiness_lock_validation(raw_lock)
    approval_status = getattr(approval, "status", None)
    approval_status_value = getattr(approval_status, "value", approval_status)
    approval_resource_id = getattr(approval, "resource_id", None)
    approval_tenant_id = getattr(approval, "tenant_id", None)
    checks = {
        "approval_found": approval is not None,
        "approval_status_approved": approval_status == ApprovalStatus.APPROVED or approval_status_value == "approved",
        "approval_resource_sdk_command": isinstance(approval_resource_id, str)
        and approval_resource_id.startswith("sdk:"),
        "tenant_matches": not principal.authenticated or approval_tenant_id == principal.tenant_id,
        "readiness_receipt_audit_record_present": isinstance(readiness_receipt, dict),
        "readiness_receipt_validation_valid": bool(
            isinstance(readiness_receipt, dict)
            and _sdk_runtime_enablement_receipt_validation(readiness_receipt)["status"] == "valid"
        ),
        "owner_pack_decision_audit_record_present": isinstance(owner_pack_decision, dict),
        "owner_pack_decision_accepted": bool(
            isinstance(owner_pack_decision, dict) and owner_pack_decision.get("decision") == "accepted"
        ),
        "owner_pack_decision_validation_valid": bool(
            isinstance(owner_pack_decision, dict)
            and _sdk_runtime_enablement_owner_pack_decision_validation(owner_pack_decision)["status"]
            == "valid"
        ),
        "readiness_lock_valid": validation["status"] == "valid",
        "dry_run_does_not_execute": request.dry_run is True,
    }
    can_record = all(checks.values())
    lock_payload = {
        key: value
        for key, value in raw_lock.items()
        if value is not None
    }
    audit_record = None
    if can_record:
        audit_record = audit_store.record(
            action="sdk.write_runner.runtime_implementation_readiness_lock_recorded",
            resource_type="sdk_write_runner_runtime_implementation_readiness_lock",
            resource_id=request.implementation_lock_id,
            outcome="accepted",
            tenant_id=approval_tenant_id or principal.tenant_id,
            actor_id=principal.user_id if principal.authenticated else request.operator_id,
            trace_id=trace_id,
            details={
                "approval_id": request.approval_id,
                "readiness_receipt_id": request.readiness_receipt_id,
                "readiness_receipt_audit_id": request.readiness_receipt_audit_id,
                "owner_pack_decision_id": request.owner_pack_decision_id,
                "owner_pack_decision_audit_id": request.owner_pack_decision_audit_id,
                "readiness_lock": lock_payload,
                "readiness_receipt_record": readiness_receipt,
                "owner_pack_decision_record": owner_pack_decision,
                "validation": validation,
                "dry_run": request.dry_run,
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        )
    return {
        "stage": "runtime_implementation_readiness_lock_record_workflow",
        "record_status": "recorded" if audit_record else "rejected",
        "recording_endpoint": "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
        "implementation_lock_id": request.implementation_lock_id,
        "idempotency_key": request.idempotency_key,
        "idempotency_hash_present": bool(request.idempotency_hash),
        "approval_id": request.approval_id,
        "readiness_receipt_id": request.readiness_receipt_id,
        "readiness_receipt_audit_id": request.readiness_receipt_audit_id,
        "owner_pack_decision_id": request.owner_pack_decision_id,
        "owner_pack_decision_audit_id": request.owner_pack_decision_audit_id,
        "approval_status": approval_status_value,
        "approval_resource_id": approval_resource_id,
        "checks": checks,
        "validation": validation,
        "audit_event_recorded": audit_record is not None,
        "audit_action": "sdk.write_runner.runtime_implementation_readiness_lock_recorded",
        "audit_id": getattr(audit_record, "id", None) if audit_record else None,
        "audit_hash": getattr(audit_record, "hash", None) if audit_record else None,
        "audit_signature_present": bool(getattr(audit_record, "signature", None)) if audit_record else False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This endpoint records a runtime implementation readiness lock only.",
            "The lock is an idempotency and owner-gate receipt, not a runtime flag.",
            "It does not invoke the SDK write runner or mark an approval executed.",
        ],
    }


def _sdk_runtime_implementation_final_decision_validation(
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    required_fields = [
        "final_decision_id",
        "decision",
        "approval_id",
        "implementation_lock_id",
        "implementation_lock_audit_id",
        "readiness_receipt_id",
        "owner_pack_decision_id",
        "decided_by",
        "decided_at",
        "reason",
    ]
    checks = {
        "record_present": isinstance(record, dict),
        "required_fields_present": bool(
            isinstance(record, dict) and all(record.get(field) not in (None, "") for field in required_fields)
        ),
        "decision_allowed": bool(
            isinstance(record, dict) and record.get("decision") in {"accepted", "rejected"}
        ),
        "decided_at_rfc3339": bool(
            isinstance(record, dict) and _is_rfc3339_timestamp(record.get("decided_at"))
        ),
        "signature_or_hash_present": bool(
            isinstance(record, dict) and (record.get("decision_signature") or record.get("decision_hash"))
        ),
    }
    return {
        "status": "valid" if all(checks.values()) else "invalid",
        "checks": checks,
    }


def _sdk_record_runtime_implementation_final_decision(
    request: SDKRuntimeImplementationFinalDecisionRecordRequest,
    *,
    principal: Principal,
    approval_store: object,
    audit_store: AuditStore,
    trace_id: str,
) -> dict[str, Any]:
    approval = approval_store.get(request.approval_id) if hasattr(approval_store, "get") else None
    readiness_lock = _sdk_runtime_implementation_readiness_lock_record_from_audit(
        audit_store,
        implementation_lock_id=request.implementation_lock_id,
        approval_id=request.approval_id,
        readiness_receipt_id=request.readiness_receipt_id,
        owner_pack_decision_id=request.owner_pack_decision_id,
        audit_id=request.implementation_lock_audit_id,
        tenant_id=principal.tenant_id if principal else None,
    )
    raw_decision = {
        "final_decision_id": request.final_decision_id,
        "decision": request.decision,
        "approval_id": request.approval_id,
        "implementation_lock_id": request.implementation_lock_id,
        "implementation_lock_audit_id": request.implementation_lock_audit_id,
        "readiness_receipt_id": request.readiness_receipt_id,
        "owner_pack_decision_id": request.owner_pack_decision_id,
        "decided_by": request.decided_by,
        "decided_at": request.decided_at,
        "reason": request.reason,
        "decision_signature": request.decision_signature,
        "decision_hash": request.decision_hash,
        "notes": request.notes,
    }
    validation = _sdk_runtime_implementation_final_decision_validation(raw_decision)
    approval_status = getattr(approval, "status", None)
    approval_status_value = getattr(approval_status, "value", approval_status)
    approval_resource_id = getattr(approval, "resource_id", None)
    approval_tenant_id = getattr(approval, "tenant_id", None)
    checks = {
        "approval_found": approval is not None,
        "approval_status_approved": approval_status == ApprovalStatus.APPROVED or approval_status_value == "approved",
        "approval_resource_sdk_command": isinstance(approval_resource_id, str)
        and approval_resource_id.startswith("sdk:"),
        "tenant_matches": not principal.authenticated or approval_tenant_id == principal.tenant_id,
        "readiness_lock_audit_record_present": isinstance(readiness_lock, dict),
        "readiness_lock_validation_valid": bool(
            isinstance(readiness_lock, dict)
            and _sdk_runtime_implementation_readiness_lock_validation(readiness_lock)["status"]
            == "valid"
        ),
        "decision_valid": validation["status"] == "valid",
        "dry_run_does_not_execute": request.dry_run is True,
    }
    can_record = all(checks.values())
    decision_payload = {
        key: value
        for key, value in raw_decision.items()
        if value is not None
    }
    audit_record = None
    if can_record:
        audit_record = audit_store.record(
            action="sdk.write_runner.runtime_implementation_final_decision_recorded",
            resource_type="sdk_write_runner_runtime_implementation_final_decision",
            resource_id=request.final_decision_id,
            outcome=request.decision,
            tenant_id=approval_tenant_id or principal.tenant_id,
            actor_id=principal.user_id if principal.authenticated else request.decided_by,
            trace_id=trace_id,
            details={
                "approval_id": request.approval_id,
                "implementation_lock_id": request.implementation_lock_id,
                "implementation_lock_audit_id": request.implementation_lock_audit_id,
                "readiness_receipt_id": request.readiness_receipt_id,
                "owner_pack_decision_id": request.owner_pack_decision_id,
                "final_decision": decision_payload,
                "readiness_lock_record": readiness_lock,
                "validation": validation,
                "dry_run": request.dry_run,
                "runtime_flag_enabled": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        )
    return {
        "stage": "runtime_implementation_final_decision_record_workflow",
        "record_status": "recorded" if audit_record else "rejected",
        "recording_endpoint": "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
        "final_decision_id": request.final_decision_id,
        "decision": request.decision,
        "approval_id": request.approval_id,
        "implementation_lock_id": request.implementation_lock_id,
        "implementation_lock_audit_id": request.implementation_lock_audit_id,
        "readiness_receipt_id": request.readiness_receipt_id,
        "owner_pack_decision_id": request.owner_pack_decision_id,
        "approval_status": approval_status_value,
        "approval_resource_id": approval_resource_id,
        "checks": checks,
        "validation": validation,
        "audit_event_recorded": audit_record is not None,
        "audit_action": "sdk.write_runner.runtime_implementation_final_decision_recorded",
        "audit_id": getattr(audit_record, "id", None) if audit_record else None,
        "audit_hash": getattr(audit_record, "hash", None) if audit_record else None,
        "audit_signature_present": bool(getattr(audit_record, "signature", None)) if audit_record else False,
        "runtime_flag_enabled": False,
        "implementation_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This endpoint records a final runtime implementation decision only.",
            "Accepted decisions do not enable the runtime flag or invoke the SDK write runner.",
            "It does not mark the approval executed or mutate runtime state.",
        ],
    }


def _sdk_runtime_flag_enablement_validation(
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    required_fields = [
        "runtime_flag_enablement_id",
        "approval_id",
        "final_decision_id",
        "final_decision_audit_id",
        "implementation_lock_id",
        "readiness_receipt_id",
        "runtime_flag_name",
        "requested_by",
        "requested_at",
        "enablement_reason",
    ]
    checks = {
        "record_present": isinstance(record, dict),
        "required_fields_present": bool(
            isinstance(record, dict) and all(record.get(field) not in (None, "") for field in required_fields)
        ),
        "requested_at_rfc3339": bool(
            isinstance(record, dict) and _is_rfc3339_timestamp(record.get("requested_at"))
        ),
        "runtime_flag_name_allowed": bool(
            isinstance(record, dict)
            and record.get("runtime_flag_name") == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
        ),
        "signature_or_hash_present": bool(
            isinstance(record, dict) and (record.get("enablement_signature") or record.get("enablement_hash"))
        ),
    }
    return {
        "status": "valid" if all(checks.values()) else "invalid",
        "checks": checks,
    }


def _sdk_record_runtime_flag_enablement(
    request: SDKRuntimeFlagEnablementRecordRequest,
    *,
    principal: Principal,
    approval_store: object,
    audit_store: AuditStore,
    trace_id: str,
) -> dict[str, Any]:
    approval = approval_store.get(request.approval_id) if hasattr(approval_store, "get") else None
    final_decision = _sdk_runtime_implementation_final_decision_record_from_audit(
        audit_store,
        final_decision_id=request.final_decision_id,
        approval_id=request.approval_id,
        implementation_lock_id=request.implementation_lock_id,
        readiness_receipt_id=request.readiness_receipt_id,
        audit_id=request.final_decision_audit_id,
        tenant_id=principal.tenant_id if principal else None,
    )
    raw_enablement = {
        "runtime_flag_enablement_id": request.runtime_flag_enablement_id,
        "approval_id": request.approval_id,
        "final_decision_id": request.final_decision_id,
        "final_decision_audit_id": request.final_decision_audit_id,
        "implementation_lock_id": request.implementation_lock_id,
        "readiness_receipt_id": request.readiness_receipt_id,
        "runtime_flag_name": request.runtime_flag_name,
        "requested_by": request.requested_by,
        "requested_at": request.requested_at,
        "enablement_reason": request.enablement_reason,
        "enablement_signature": request.enablement_signature,
        "enablement_hash": request.enablement_hash,
        "notes": request.notes,
    }
    validation = _sdk_runtime_flag_enablement_validation(raw_enablement)
    approval_status = getattr(approval, "status", None)
    approval_status_value = getattr(approval_status, "value", approval_status)
    approval_resource_id = getattr(approval, "resource_id", None)
    approval_tenant_id = getattr(approval, "tenant_id", None)
    checks = {
        "approval_found": approval is not None,
        "approval_status_approved": approval_status == ApprovalStatus.APPROVED or approval_status_value == "approved",
        "approval_resource_sdk_command": isinstance(approval_resource_id, str)
        and approval_resource_id.startswith("sdk:"),
        "tenant_matches": not principal.authenticated or approval_tenant_id == principal.tenant_id,
        "final_decision_audit_record_present": isinstance(final_decision, dict),
        "final_decision_accepted": bool(
            isinstance(final_decision, dict) and final_decision.get("decision") == "accepted"
        ),
        "final_decision_validation_valid": bool(
            isinstance(final_decision, dict)
            and _sdk_runtime_implementation_final_decision_validation(final_decision)["status"]
            == "valid"
        ),
        "runtime_flag_enablement_valid": validation["status"] == "valid",
        "dry_run_does_not_enable_runtime": request.dry_run is True,
    }
    can_record = all(checks.values())
    enablement_payload = {
        key: value
        for key, value in raw_enablement.items()
        if value is not None
    }
    audit_record = None
    if can_record:
        audit_record = audit_store.record(
            action="sdk.write_runner.runtime_flag_enablement_requested",
            resource_type="sdk_write_runner_runtime_flag_enablement_request",
            resource_id=request.runtime_flag_enablement_id,
            outcome="accepted",
            tenant_id=approval_tenant_id or principal.tenant_id,
            actor_id=principal.user_id if principal.authenticated else request.requested_by,
            trace_id=trace_id,
            details={
                "approval_id": request.approval_id,
                "final_decision_id": request.final_decision_id,
                "final_decision_audit_id": request.final_decision_audit_id,
                "implementation_lock_id": request.implementation_lock_id,
                "readiness_receipt_id": request.readiness_receipt_id,
                "runtime_flag_enablement": enablement_payload,
                "final_decision_record": final_decision,
                "validation": validation,
                "dry_run": request.dry_run,
                "runtime_flag_enabled": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        )
    return {
        "stage": "runtime_flag_enablement_record_workflow",
        "record_status": "recorded" if audit_record else "rejected",
        "recording_endpoint": "/api/v1/control-plane/sdk/runtime-flag/enablement/record",
        "runtime_flag_enablement_id": request.runtime_flag_enablement_id,
        "approval_id": request.approval_id,
        "final_decision_id": request.final_decision_id,
        "final_decision_audit_id": request.final_decision_audit_id,
        "implementation_lock_id": request.implementation_lock_id,
        "readiness_receipt_id": request.readiness_receipt_id,
        "runtime_flag_name": request.runtime_flag_name,
        "approval_status": approval_status_value,
        "approval_resource_id": approval_resource_id,
        "checks": checks,
        "validation": validation,
        "audit_event_recorded": audit_record is not None,
        "audit_action": "sdk.write_runner.runtime_flag_enablement_requested",
        "audit_id": getattr(audit_record, "id", None) if audit_record else None,
        "audit_hash": getattr(audit_record, "hash", None) if audit_record else None,
        "audit_signature_present": bool(getattr(audit_record, "signature", None)) if audit_record else False,
        "runtime_flag_enabled": False,
        "implementation_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This endpoint records explicit owner runtime flag enablement intent only.",
            "It does not set XAGENT_SDK_WRITE_RUNNER_ENABLED or invoke the SDK write runner.",
            "Concrete runtime flag application remains a separate owner-requested implementation task.",
        ],
    }


def _sdk_backend_stub_metadata(
    original: SDKControlPlaneInvokeRequest,
    request: ControlPlaneInvokeRequest,
    response: ControlPlaneInvokeResponse,
    *,
    approval_intent: dict[str, Any],
    approval_store: object,
    principal: Principal,
) -> dict[str, Any]:
    execution_adapter_contract = _sdk_execution_adapter_contract(
        original,
        request,
        approval_store=approval_store,
        principal=principal,
    )
    read_only_runner_contract = _sdk_read_only_runner_contract(original, request, response)
    write_runner_safety_contract = _sdk_write_runner_safety_contract(original, request, execution_adapter_contract)
    return {
        "status": "sdk_runtime_flag_enablement_record_workflow_ready",
        "operation": request.context.sdk_operation or original.operation,
        "method": request.method,
        "sdk_surface": request.context.sdk_surface or "python",
        "non_interactive": request.context.non_interactive is not False,
        "dry_run": request.dry_run,
        "idempotency_key_present": bool(request.idempotency_key),
        "owner_gate_required": request.method != "thread/read",
        "mutation_performed": False,
        "network_mutation_performed": False,
        "adapter_execution_enabled": False,
        "approval_intent": approval_intent,
        "approval_handoff": _sdk_approval_handoff(approval_intent),
        "execution_adapter_contract": execution_adapter_contract,
        "read_only_runner_contract": read_only_runner_contract,
        "write_runner_safety_contract": write_runner_safety_contract,
        "approval_sandbox_admin": _sdk_approval_sandbox_admin_contract(request),
        "control_plane_ok": response.ok,
        "control_plane_error_code": response.error.code if response.error else None,
        "known_limits": [
            "This endpoint accepts SDK envelopes and normalizes them into the control-plane contract.",
            "Read-only SDK methods can return backend read results through the control-plane contract.",
            "Write-method invocations create a pending owner approval intent but do not execute it.",
            "Approved SDK approval ids are read back for execution-adapter preflight only.",
            "Owner-approved write methods expose a runner safety plan and receipt template only.",
            "Approved write methods can produce a dry-run executor stub receipt and audit event.",
            "Runtime evidence/read can return the SDK dry-run executor receipt schema and audit readback hints.",
            "Dry-run executor receipts are persisted in the audit log and can be read back through runtime evidence.",
            "Persisted dry-run receipts expose a read-only write-runner safety review gate.",
            "Owner-approved write dry-run receipts are consolidated into a disabled execute gate contract.",
            "Owner-approved write runner adapter implementation is represented as a disabled review contract.",
            "Runtime feature flag and owner acceptance evidence recording/readback contracts are present and disabled by default.",
            "The concrete SDK write runner implementation plan is declared but remains disabled.",
            "Runtime enablement smoke, rollback, and failure receipt contracts are declared but remain disabled.",
            "Runtime enablement readiness receipt is declared for owner review but remains disabled.",
            "Runtime implementation preflight adapter boundaries are declared but remain disabled.",
            "Runtime enablement readiness receipt recording/readback workflow is owner-gated and disabled for execution.",
            "Runtime enablement owner review pack is ready for audit but disabled for execution.",
            "Runtime enablement owner pack decision workflow is ready for audit but disabled for execution.",
            "Runtime implementation readiness lock recording is owner-gated and disabled for execution.",
            "No SDK HTTP adapter execution, agent runner invocation, channel send, file change, or network mutation is enabled.",
            "Write methods remain owner-gated behind the approval/sandbox/admin contract.",
            "Feishu remains the only domestic V1 pilot channel.",
        ],
    }


def _sdk_approval_handoff(approval_intent: dict[str, Any]) -> dict[str, Any]:
    approval_id = approval_intent.get("approval_id")
    if not approval_intent.get("created") or not isinstance(approval_id, str) or not approval_id:
        return {
            "available": False,
            "approval_id": None,
            "next_commands": [],
            "api_links": {},
            "execute_disabled": True,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
        }
    return {
        "available": True,
        "approval_id": approval_id,
        "next_commands": [
            f"xagent approvals show {approval_id}",
            f"xagent approvals approve {approval_id} --by <owner> --reason <reason>",
        ],
        "blocked_command": f"xagent approvals execute {approval_id}",
        "blocked_reason": "Approval execution remains disabled for SDK long-running runs in this task.",
        "api_links": {
            "show": f"/api/v1/approvals/{approval_id}",
            "approve": f"/api/v1/approvals/{approval_id}/approve",
            "control_plane": "/api/v1/control-plane/sdk/invoke",
        },
        "readback": {
            "method": "approval/read",
            "params": {"approval_id": approval_id},
            "control_plane": "/api/v1/control-plane/invoke",
        },
        "execute_disabled": True,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
    }


def _sdk_execution_adapter_contract(
    original: SDKControlPlaneInvokeRequest,
    request: ControlPlaneInvokeRequest,
    *,
    approval_store: object,
    principal: Principal,
) -> dict[str, Any]:
    approved_approval_id = _sdk_approved_approval_id(original, request)
    base: dict[str, Any] = {
        "available": True,
        "contract_stage": "owner_approved_preflight",
        "approved_approval_id": approved_approval_id,
        "owner_approved_requested": bool(original.owner_approved or approved_approval_id),
        "approval_readback_method": "approval/read",
        "approval_readback_params": {"approval_id": approved_approval_id} if approved_approval_id else {},
        "approval_readback_endpoint": "/api/v1/control-plane/invoke",
        "required_approval_status": ApprovalStatus.APPROVED.value,
        "expected_resource_id": f"sdk:{request.method}",
        "preflight_status": "approval_id_required",
        "ready_for_owner_approved_adapter": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "execute_disabled": True,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "next_commands": [
            "xagent sdk turn-run <thread_id> <input> --execute --approved-approval-id <approval_id>"
        ],
        "known_limits": [
            "This contract verifies approval readiness only.",
            "The SDK execution adapter remains disabled until a concrete owner-approved runner is implemented.",
            "No approval is marked executed by /api/v1/control-plane/sdk/invoke.",
        ],
    }
    if request.method == "thread/read":
        return {
            **base,
            "preflight_status": "not_required_for_read",
            "owner_approved_requested": False,
            "ready_for_owner_approved_adapter": False,
        }
    if not approved_approval_id:
        return base

    record = getattr(approval_store, "get", lambda _approval_id: None)(approved_approval_id)
    if record is None:
        return {**base, "preflight_status": "approval_not_found"}

    record_status = _status_value(getattr(record, "status", None))
    record_resource_id = getattr(record, "resource_id", None)
    tenant_id = getattr(record, "tenant_id", None)
    tenant_matches = (
        not principal.authenticated
        or principal.tenant_id is None
        or tenant_id is None
        or principal.tenant_id == tenant_id
    )
    checks = {
        "approval_exists": True,
        "approval_status": record_status,
        "approval_status_ok": record_status == ApprovalStatus.APPROVED.value,
        "resource_id": record_resource_id,
        "resource_id_ok": record_resource_id == f"sdk:{request.method}",
        "tenant_id": tenant_id,
        "tenant_ok": tenant_matches,
        "subject_type": _status_value(getattr(record, "subject_type", None)),
        "decision_type": _status_value(getattr(record, "decision_type", None)),
        "decision_scope": getattr(record, "decision_scope", None),
        "sandbox_profile": getattr(record, "sandbox_profile", None),
    }
    ready = (
        checks["approval_status_ok"] is True
        and checks["resource_id_ok"] is True
        and checks["tenant_ok"] is True
    )
    if ready:
        preflight_status = "approved_ready"
    elif checks["approval_status_ok"] is not True:
        preflight_status = "approval_not_approved"
    elif checks["resource_id_ok"] is not True:
        preflight_status = "approval_resource_mismatch"
    else:
        preflight_status = "approval_tenant_mismatch"
    return {
        **base,
        **checks,
        "preflight_status": preflight_status,
        "ready_for_owner_approved_adapter": ready,
    }


def _sdk_approved_approval_id(
    original: SDKControlPlaneInvokeRequest,
    request: ControlPlaneInvokeRequest,
) -> str | None:
    if isinstance(original.approved_approval_id, str) and original.approved_approval_id:
        return original.approved_approval_id
    value = request.params.get("approved_approval_id")
    if isinstance(value, str) and value:
        return value
    owner_gate = getattr(original, "owner_gate", None)
    if isinstance(owner_gate, dict):
        value = owner_gate.get("approved_approval_id")
        if isinstance(value, str) and value:
            return value
    return None


def _sdk_read_only_runner_contract(
    original: SDKControlPlaneInvokeRequest,
    request: ControlPlaneInvokeRequest,
    response: ControlPlaneInvokeResponse,
) -> dict[str, Any]:
    spec = METHODS_BY_NAME.get(request.method)
    read_only = spec is not None and spec.operation_kind == "read"
    available = read_only and response.ok and response.result is not None
    runner_kind = "read_only_control_plane" if read_only else "write_methods_owner_gated"
    return {
        "available": available,
        "runner_kind": runner_kind,
        "contract_stage": "read_only_runner",
        "method": request.method,
        "operation": request.context.sdk_operation or original.operation,
        "supported_methods": [
            spec.method
            for spec in METHOD_SPECS
            if spec.operation_kind == "read" and spec.implementation_state == "read_only_contract"
        ],
        "result_available": response.result is not None,
        "control_plane_ok": response.ok,
        "control_plane_error_code": response.error.code if response.error else None,
        "read_only_runner_enabled": available,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "adapter_execution_enabled": False,
        "adapter_mode": "read_only_contract" if available else "disabled",
        "owner_approval_required": False if read_only else True,
        "dry_run": request.dry_run,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "mark_executed": False,
        "known_limits": [
            "Only read-only control-plane methods can use this runner contract.",
            "Write methods remain owner-gated and do not reach the agent runner here.",
            "Read-only runner availability does not claim full Codex SDK parity.",
        ],
    }


def _sdk_write_runner_safety_contract(
    original: SDKControlPlaneInvokeRequest,
    request: ControlPlaneInvokeRequest,
    execution_adapter_contract: dict[str, Any],
) -> dict[str, Any]:
    spec = METHODS_BY_NAME.get(request.method)
    write_method = spec is not None and spec.operation_kind == "write"
    approved_ready = execution_adapter_contract.get("preflight_status") == "approved_ready"
    approved_approval_id = execution_adapter_contract.get("approved_approval_id")
    ready = write_method and approved_ready and isinstance(approved_approval_id, str) and bool(approved_approval_id)
    runner_plan = {
        "runner_kind": "sdk_owner_approved_write",
        "operation": request.context.sdk_operation or original.operation,
        "method": request.method,
        "approval_id": approved_approval_id,
        "idempotency_key_present": bool(request.idempotency_key),
        "input_preview": _sdk_write_runner_input_preview(request),
        "guard_order": [
            "approval/read",
            "approval_status_must_be_approved",
            "resource_id_must_match_sdk_method",
            "tenant_must_match",
            "sandbox_profile_must_allow_command_locked",
            "idempotency_key_must_be_present_for_write",
            "agent_runner_still_disabled_in_this_task",
        ],
    }
    return {
        "available": write_method,
        "contract_stage": "owner_approved_write_runner_safety",
        "ready_for_runner_contract": ready,
        "preflight_status": execution_adapter_contract.get("preflight_status"),
        "approved_approval_id": approved_approval_id,
        "runner_plan": runner_plan,
        "receipt_template": {
            "status": "planned_not_executed" if ready else "blocked_before_runner",
            "runner_invoked": False,
            "agent_trace_id": None,
            "approval_id": approved_approval_id,
            "method": request.method,
            "operation": request.context.sdk_operation or original.operation,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "required_guards": {
            "approval_preflight_ready": approved_ready,
            "write_method": write_method,
            "idempotency_key_present": bool(request.idempotency_key),
            "sandbox_profile": execution_adapter_contract.get("sandbox_profile", "command_locked"),
            "owner_gate_required": True,
            "audit_required": True,
        },
        "next_commands": [
            "xagent sdk turn-run <thread_id> <input> --execute --approved-approval-id <approval_id> --idempotency-key <key>",
            "python scripts\\sdk_noninteractive_report.py",
        ],
        "runner_invoked": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "adapter_execution_enabled": False,
        "execute_disabled": True,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This is a safety contract and receipt template for future write execution.",
            "No concrete SDK write runner is invoked in this task.",
            "Approvals are not marked executed by this endpoint.",
        ],
    }


def _sdk_write_runner_input_preview(request: ControlPlaneInvokeRequest) -> dict[str, Any]:
    preview: dict[str, Any] = {
        "dry_run": request.dry_run,
        "idempotency_key_present": bool(request.idempotency_key),
    }
    for key in ("thread_id", "task", "input"):
        value = request.params.get(key)
        if isinstance(value, str):
            preview[key] = value[:200]
    return preview


def _sdk_dry_run_executor_stub(
    audit_store: AuditStore,
    principal: Principal,
    *,
    request: ControlPlaneInvokeRequest,
    trace_id: str,
    write_runner_safety_contract: dict[str, Any],
) -> dict[str, Any]:
    ready = write_runner_safety_contract.get("ready_for_runner_contract") is True
    receipt = {
        **write_runner_safety_contract.get("receipt_template", {}),
        "status": "dry_run_planned" if ready else "blocked_before_dry_run_executor",
        "dry_run_executor_invoked": ready,
        "runner_invoked": False,
        "agent_trace_id": None,
        "audit_id": None,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
    }
    if not ready:
        return {
            "available": False,
            "stub_stage": "owner_approved_write_dry_run_executor",
            "blocked_reason": write_runner_safety_contract.get("preflight_status"),
            "audit_event_recorded": False,
            "receipt": receipt,
            "runner_invoked": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "mutation_performed": False,
        }

    audit = audit_store.record(
        action="sdk.write_runner.dry_run_planned",
        resource_type="sdk_write_runner",
        resource_id=request.method,
        outcome="planned",
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        trace_id=trace_id,
        details={
            "request_id": request.id,
            "method": request.method,
            "operation": request.context.sdk_operation,
            "approval_id": write_runner_safety_contract.get("approved_approval_id"),
            "runner_plan": write_runner_safety_contract.get("runner_plan"),
            "receipt": receipt,
            "receipt_persisted": True,
            "runner_invoked": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
    )
    receipt["audit_id"] = audit.id
    response_receipt = {
        **receipt,
        "audit_hash": audit.hash,
        "audit_signature_present": bool(audit.signature),
        "receipt_persisted": True,
    }
    return {
        "available": True,
        "stub_stage": "owner_approved_write_dry_run_executor",
        "audit_event_recorded": True,
        "audit_action": "sdk.write_runner.dry_run_planned",
        "audit_id": audit.id,
        "audit_hash": audit.hash,
        "audit_signature_present": bool(audit.signature),
        "receipt_persisted": True,
        "receipt_readback_method": "runtime/evidence/read",
        "receipt": response_receipt,
        "runner_invoked": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "adapter_execution_enabled": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
    }


def _sdk_write_runner_execute_gate(
    original: SDKControlPlaneInvokeRequest,
    request: ControlPlaneInvokeRequest,
    *,
    execution_adapter_contract: dict[str, Any],
    write_runner_safety_contract: dict[str, Any],
    dry_run_executor_stub: dict[str, Any],
) -> dict[str, Any]:
    spec = METHODS_BY_NAME.get(request.method)
    receipt = dry_run_executor_stub.get("receipt")
    receipt_payload = receipt if isinstance(receipt, dict) else None
    safety_review = _sdk_write_runner_safety_review(receipt_payload)
    write_method = spec is not None and spec.operation_kind == "write"
    mutation_keys = (
        "mutation_performed",
        "network_mutation_performed",
        "file_mutation_performed",
        "channel_mutation_performed",
    )
    checks = {
        "write_method": write_method,
        "approved_preflight_ready": execution_adapter_contract.get("preflight_status") == "approved_ready"
        and execution_adapter_contract.get("ready_for_owner_approved_adapter") is True,
        "runner_contract_ready": write_runner_safety_contract.get("ready_for_runner_contract") is True,
        "receipt_persisted": dry_run_executor_stub.get("receipt_persisted") is True
        and bool(receipt_payload and receipt_payload.get("receipt_persisted") is True),
        "dry_run_receipt_planned": bool(receipt_payload and receipt_payload.get("status") == "dry_run_planned"),
        "audit_event_recorded": dry_run_executor_stub.get("audit_event_recorded") is True,
        "audit_hash_present": bool(
            receipt_payload
            and isinstance(receipt_payload.get("audit_hash"), str)
            and receipt_payload.get("audit_hash")
        ),
        "audit_signature_present": bool(receipt_payload and receipt_payload.get("audit_signature_present") is True),
        "safety_review_passed": safety_review.get("status") == "passed",
        "runner_not_invoked": write_runner_safety_contract.get("runner_invoked") is False
        and dry_run_executor_stub.get("runner_invoked") is False
        and bool(receipt_payload and receipt_payload.get("runner_invoked") is False),
        "mark_executed_false": execution_adapter_contract.get("mark_executed") is False
        and write_runner_safety_contract.get("mark_executed") is False
        and dry_run_executor_stub.get("mark_executed") is False
        and bool(receipt_payload and receipt_payload.get("mark_executed") is False),
        "mutation_false": all(
            execution_adapter_contract.get(key) is False
            and write_runner_safety_contract.get(key) is False
            and dry_run_executor_stub.get(key) is False
            and bool(receipt_payload and receipt_payload.get(key) is False)
            for key in mutation_keys
        ),
        "idempotency_key_present": bool(request.idempotency_key)
        and write_runner_safety_contract.get("required_guards", {}).get("idempotency_key_present") is True,
    }
    gate_ready = all(checks.values())
    return {
        "available": write_method,
        "stage": "owner_approved_write_runner_execute_gate",
        "gate_status": "ready_but_disabled" if gate_ready else "blocked",
        "method": request.method,
        "operation": request.context.sdk_operation or original.operation,
        "approved_approval_id": write_runner_safety_contract.get("approved_approval_id"),
        "idempotency_key_present": bool(request.idempotency_key),
        "checks": checks,
        "safety_review": safety_review,
        "receipt_readback": {
            "method": "runtime/evidence/read",
            "evidence_type": "sdk_dry_run_executor_stub",
            "audit_id": receipt_payload.get("audit_id") if receipt_payload else None,
        },
        "next_gate": "owner_approved_write_runner_adapter_implementation",
        "execute_enabled": False,
        "write_runner_enabled": False,
        "agent_execution_enabled": False,
        "adapter_execution_enabled": False,
        "write_execution_enabled": False,
        "execute_disabled": True,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This gate proves the owner-approved write runner preconditions are machine-readable.",
            "It intentionally keeps execution disabled until a concrete runner adapter implementation is reviewed.",
            "No approval is marked executed and no agent, file, network, or channel mutation is performed.",
        ],
    }


def _sdk_write_runner_adapter_review(
    original: SDKControlPlaneInvokeRequest,
    request: ControlPlaneInvokeRequest,
    *,
    execution_adapter_contract: dict[str, Any],
    write_runner_execute_gate: dict[str, Any],
) -> dict[str, Any]:
    gate_checks = write_runner_execute_gate.get("checks", {})
    checks = {
        "execute_gate_ready_but_disabled": write_runner_execute_gate.get("gate_status") == "ready_but_disabled",
        "approved_preflight_ready": gate_checks.get("approved_preflight_ready") is True,
        "approval_id_bound": isinstance(write_runner_execute_gate.get("approved_approval_id"), str)
        and bool(write_runner_execute_gate.get("approved_approval_id")),
        "idempotency_key_present": gate_checks.get("idempotency_key_present") is True,
        "receipt_persisted": gate_checks.get("receipt_persisted") is True,
        "safety_review_passed": gate_checks.get("safety_review_passed") is True,
        "adapter_target_declared": True,
        "approval_mark_executed_deferred": True,
        "runner_invocation_disabled": write_runner_execute_gate.get("write_runner_enabled") is False,
        "agent_execution_disabled": write_runner_execute_gate.get("agent_execution_enabled") is False,
        "mutation_disabled": write_runner_execute_gate.get("mutation_performed") is False,
    }
    review_ready = all(checks.values())
    return {
        "available": write_runner_execute_gate.get("available") is True,
        "stage": "owner_approved_write_runner_adapter_implementation_review",
        "review_status": "ready_but_disabled" if review_ready else "blocked",
        "method": request.method,
        "operation": request.context.sdk_operation or original.operation,
        "approved_approval_id": write_runner_execute_gate.get("approved_approval_id"),
        "adapter_target": {
            "module": "backend.app.core.agent.coordinator",
            "callable": "AgentCoordinator.run",
            "request_mapping": {
                "thread/start": "task",
                "thread/resume": "input",
                "turn/start": "input",
            },
            "expected_context_fields": [
                "tenant_id",
                "user_id",
                "request_id",
                "permission_scope",
                "risk_level",
            ],
        },
        "approval_execution_policy": {
            "readback_method": execution_adapter_contract.get("approval_readback_method"),
            "required_status": execution_adapter_contract.get("required_approval_status"),
            "resource_id": execution_adapter_contract.get("expected_resource_id"),
            "mark_executed_allowed_after_runner_success": True,
            "mark_executed_called_now": False,
        },
        "audit_contract": {
            "planned_action": "sdk.write_runner.adapter_review_ready",
            "future_execute_action": "sdk.write_runner.executed",
            "dry_run_receipt_required": True,
            "idempotency_key_required": True,
            "result_receipt_required": True,
        },
        "checks": checks,
        "next_gate": "owner_approved_write_runner_runtime_feature_flag",
        "implementation_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "agent_execution_enabled": False,
        "adapter_execution_enabled": False,
        "write_execution_enabled": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This is the adapter implementation review contract, not the implementation switch.",
            "The future adapter target is declared, but AgentCoordinator.run is not called here.",
            "Approvals are not marked executed until a future runner succeeds under an explicit runtime feature flag.",
        ],
    }


def _sdk_write_runner_runtime_flag_contract(
    request: ControlPlaneInvokeRequest,
    *,
    write_runner_adapter_review: dict[str, Any],
) -> dict[str, Any]:
    review_ready = write_runner_adapter_review.get("review_status") == "ready_but_disabled"
    checks = {
        "adapter_review_ready_but_disabled": review_ready,
        "feature_flag_declared": True,
        "feature_flag_default_disabled": True,
        "owner_acceptance_required": True,
        "audit_required": True,
        "rollback_required": True,
        "implementation_still_disabled": write_runner_adapter_review.get("implementation_enabled") is False,
    }
    return {
        "available": write_runner_adapter_review.get("available") is True,
        "stage": "owner_approved_write_runner_runtime_feature_flag",
        "flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        "flag_status": "declared_disabled",
        "default_enabled": False,
        "env_var": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        "owner_acceptance_evidence_required": True,
        "required_owner_evidence": [
            "owner_acceptance_id",
            "accepted_by",
            "accepted_at",
            "approval_id",
            "runbook_acknowledged",
            "rollback_plan_acknowledged",
        ],
        "required_runtime_guards": [
            "runtime_flag_enabled",
            "owner_acceptance_evidence_present",
            "adapter_review_ready",
            "approval_status_approved",
            "idempotency_key_present",
            "dry_run_receipt_persisted",
            "audit_hmac_available",
        ],
        "checks": checks,
        "next_gate": "owner_acceptance_evidence_record",
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This declares the runtime switch required before concrete write runner execution.",
            "The flag defaults disabled and is not read as an execution permission in this task.",
            "Owner acceptance evidence is still required before the flag can be honored.",
        ],
    }


def _sdk_owner_acceptance_evidence_contract(
    request: ControlPlaneInvokeRequest,
    *,
    write_runner_runtime_flag: dict[str, Any],
) -> dict[str, Any]:
    required_fields = list(write_runner_runtime_flag.get("required_owner_evidence", []))
    schema = _sdk_owner_acceptance_evidence_schema(required_fields)
    checks = {
        "runtime_flag_contract_declared": write_runner_runtime_flag.get("flag_status") == "declared_disabled",
        "runtime_flag_disabled": write_runner_runtime_flag.get("runtime_flag_enabled") is False,
        "owner_acceptance_required": write_runner_runtime_flag.get("owner_acceptance_evidence_required") is True,
        "recording_contract_declared": True,
        "readback_contract_declared": True,
        "schema_declared": True,
        "acceptance_record_present": False,
        "runbook_acknowledged": False,
        "rollback_plan_acknowledged": False,
        "execution_still_disabled": write_runner_runtime_flag.get("execute_enabled") is False,
    }
    return {
        "available": write_runner_runtime_flag.get("available") is True,
        "stage": "owner_acceptance_evidence_record",
        "evidence_status": "recording_contract_ready_not_provided",
        "recording_contract_ready": True,
        "recording_action": "sdk.write_runner.owner_acceptance_recorded",
        "resource_type": "sdk_write_runner_owner_acceptance",
        "method": request.method,
        "required_fields": required_fields,
        "schema": schema,
        "evidence_readback_method": "runtime/evidence/read",
        "evidence_type": "sdk_write_runner_owner_acceptance",
        "acceptance_report_name": "sdk-write-runner-owner-acceptance.json",
        "acceptance_report_path": str(REPORT_DIR / "sdk-write-runner-owner-acceptance.json"),
        "readback_contract": {
            "endpoint": "/api/v1/control-plane/invoke",
            "method": "runtime/evidence/read",
            "params": {
                "evidence_type": "sdk_write_runner_owner_acceptance",
                "report_name": "sdk-write-runner-owner-acceptance.json",
                "approval_id": "<approval_id>",
                "owner_acceptance_id": "<owner_acceptance_id>",
                "audit_id": "<audit_id>",
            },
            "query_keys": ["approval_id", "owner_acceptance_id", "audit_id"],
            "returns_schema": True,
            "returns_record_if_present": True,
        },
        "recording_contract": {
            "audit_action": "sdk.write_runner.owner_acceptance_recorded",
            "resource_type": "sdk_write_runner_owner_acceptance",
            "resource_id_field": "owner_acceptance_id",
            "required_acknowledgements": [
                "runbook_acknowledged",
                "rollback_plan_acknowledged",
            ],
            "signature_or_hash_required": True,
            "mutation_source": "owner_controlled_evidence",
            "created_by_sdk_invoke": False,
        },
        "checks": checks,
        "next_gate": "owner_approved_write_runner_runtime_enablement",
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "No owner acceptance record is created by /sdk/invoke.",
            "This contract defines the owner evidence schema and readback shape only.",
            "The concrete write runner remains disabled until this evidence is provided and reviewed.",
        ],
    }


def _sdk_runtime_enablement_review_contract(
    request: ControlPlaneInvokeRequest,
    *,
    write_runner_runtime_flag: dict[str, Any],
    owner_acceptance_evidence: dict[str, Any],
    write_runner_execute_gate: dict[str, Any],
    write_runner_adapter_review: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "write_method": request.method not in {"thread/read", "thread/search", "runtime/evidence/read"},
        "execute_gate_ready_but_disabled": write_runner_execute_gate.get("gate_status") == "ready_but_disabled",
        "adapter_review_ready_but_disabled": write_runner_adapter_review.get("review_status") == "ready_but_disabled",
        "runtime_flag_declared_disabled": write_runner_runtime_flag.get("flag_status") == "declared_disabled"
        and write_runner_runtime_flag.get("runtime_flag_enabled") is False,
        "owner_acceptance_recording_contract_ready": owner_acceptance_evidence.get("recording_contract_ready")
        is True,
        "owner_acceptance_readback_contract_ready": owner_acceptance_evidence.get("readback_contract", {}).get(
            "returns_record_if_present"
        )
        is True,
        "strict_acceptance_readback_keys_required": owner_acceptance_evidence.get("readback_contract", {}).get(
            "query_keys"
        )
        == ["approval_id", "owner_acceptance_id", "audit_id"],
        "approval_execute_still_disabled": owner_acceptance_evidence.get("mark_executed") is False,
        "mutation_still_disabled": owner_acceptance_evidence.get("mutation_performed") is False,
    }
    review_ready = all(checks.values())
    return {
        "available": owner_acceptance_evidence.get("available") is True,
        "stage": "owner_approved_write_runner_runtime_enablement_review",
        "review_status": "ready_but_disabled" if review_ready else "blocked",
        "required_evidence_type": "sdk_write_runner_owner_acceptance",
        "required_audit_action": "sdk.write_runner.owner_acceptance_recorded",
        "required_readback_keys": ["approval_id", "owner_acceptance_id", "audit_id"],
        "required_runtime_guards": [
            "runtime_flag_enabled",
            "owner_acceptance_audit_record_valid",
            "approval_status_approved",
            "adapter_review_ready",
            "execute_gate_ready",
            "dry_run_receipt_safety_review_passed",
            "idempotency_key_present",
        ],
        "checks": checks,
        "next_gate": "owner_approved_write_runner_concrete_runner_implementation",
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This review consumes owner acceptance contracts only; it does not read a runtime flag as permission.",
            "A valid audit-backed owner acceptance record remains necessary before implementation work.",
            "The concrete SDK write runner remains disabled.",
        ],
    }


def _sdk_write_runner_implementation_plan_contract(
    request: ControlPlaneInvokeRequest,
    *,
    runtime_enablement_review: dict[str, Any],
    write_runner_adapter_review: dict[str, Any],
    write_runner_execute_gate: dict[str, Any],
    owner_acceptance_evidence: dict[str, Any],
) -> dict[str, Any]:
    adapter_target = write_runner_adapter_review.get("adapter_target", {})
    checks = {
        "write_method": request.method not in {"thread/read", "thread/search", "runtime/evidence/read"},
        "runtime_enablement_ready_but_disabled": runtime_enablement_review.get("review_status")
        == "ready_but_disabled",
        "adapter_target_declared": adapter_target.get("callable") == "AgentCoordinator.run",
        "execute_gate_ready_but_disabled": write_runner_execute_gate.get("gate_status") == "ready_but_disabled",
        "owner_acceptance_readback_required": owner_acceptance_evidence.get("readback_contract", {}).get(
            "query_keys"
        )
        == ["approval_id", "owner_acceptance_id", "audit_id"],
        "runtime_flag_disabled": runtime_enablement_review.get("runtime_flag_enabled") is False,
        "execution_still_disabled": runtime_enablement_review.get("execute_enabled") is False,
        "mutation_still_disabled": runtime_enablement_review.get("mutation_performed") is False,
    }
    plan_ready = all(checks.values())
    return {
        "available": runtime_enablement_review.get("available") is True,
        "stage": "owner_approved_write_runner_concrete_implementation_plan",
        "plan_status": "ready_but_disabled" if plan_ready else "blocked",
        "adapter_target": {
            "module": adapter_target.get("module"),
            "callable": adapter_target.get("callable"),
            "request_mapping": adapter_target.get("request_mapping", {}),
            "expected_context_fields": adapter_target.get("expected_context_fields", []),
        },
        "implementation_steps": [
            "resolve_owner_acceptance_record_by_strict_keys",
            "read_approved_sdk_approval",
            "verify_runtime_flag_enabled",
            "build_agent_run_request_from_sdk_envelope",
            "invoke_agent_runner_once_with_idempotency_key",
            "persist_result_receipt_and_audit_hash",
            "mark_approval_executed_after_runner_success",
            "return_control_plane_result_receipt",
        ],
        "rollback_plan": {
            "disable_runtime_flag": True,
            "do_not_mark_approval_executed_on_failure": True,
            "persist_failure_receipt": True,
            "restore_owner_gate_required": True,
            "operator_runbook": "docs/runbooks/sdk-write-runner-runtime-enable.md",
        },
        "idempotency_contract": {
            "required": True,
            "key_source": "ControlPlaneInvokeRequest.idempotency_key",
            "dedupe_scope": ["tenant_id", "method", "approved_approval_id", "idempotency_key"],
            "duplicate_behavior": "return_existing_result_receipt_without_reinvoking_runner",
        },
        "audit_result_shape": {
            "planned_action": "sdk.write_runner.implementation_plan_ready",
            "future_start_action": "sdk.write_runner.execution_started",
            "future_success_action": "sdk.write_runner.executed",
            "future_failure_action": "sdk.write_runner.failed",
            "required_result_fields": [
                "result_receipt_id",
                "approval_id",
                "owner_acceptance_id",
                "audit_id",
                "agent_trace_id",
                "idempotency_key_hash",
                "runner_status",
                "mutation_summary",
            ],
        },
        "owner_enablement_steps": [
            "approve_sdk_command",
            "record_owner_acceptance_evidence",
            "verify_runtime_enablement_review",
            "set_XAGENT_SDK_WRITE_RUNNER_ENABLED_true",
            "run_sdk_write_runner_smoke",
            "review_result_receipt_before_general_availability",
        ],
        "checks": checks,
        "next_gate": "owner_approved_write_runner_runtime_implementation",
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This is a concrete implementation plan contract, not a runtime implementation.",
            "The AgentCoordinator.run target is declared for review only and is not imported or called here.",
            "The runtime flag, runner invocation, approval execution marker, and all mutations remain disabled.",
        ],
    }


def _sdk_runtime_smoke_runbook_contract(
    write_runner_implementation_plan: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "implementation_plan_ready_but_disabled": write_runner_implementation_plan.get("plan_status")
        == "ready_but_disabled",
        "runtime_flag_still_disabled": write_runner_implementation_plan.get("runtime_flag_enabled") is False,
        "write_runner_still_disabled": write_runner_implementation_plan.get("write_runner_enabled") is False,
        "runner_not_invoked": write_runner_implementation_plan.get("runner_invoked") is False,
        "rollback_plan_declared": write_runner_implementation_plan.get("rollback_plan", {}).get(
            "disable_runtime_flag"
        )
        is True,
        "idempotency_required": write_runner_implementation_plan.get("idempotency_contract", {}).get("required")
        is True,
        "failure_audit_declared": write_runner_implementation_plan.get("audit_result_shape", {}).get(
            "future_failure_action"
        )
        == "sdk.write_runner.failed",
    }
    ready = all(checks.values())
    return {
        "available": write_runner_implementation_plan.get("available") is True,
        "stage": "owner_approved_write_runner_runtime_smoke_runbook",
        "contract_status": "ready_but_disabled" if ready else "blocked",
        "runbook_path": "docs/runbooks/sdk-write-runner-runtime-enable.md",
        "smoke_plan": {
            "command": "xagent sdk turn-run <thread_id> <input> --execute --approved-approval-id <approval_id> --idempotency-key <key>",
            "requires_runtime_flag": "XAGENT_SDK_WRITE_RUNNER_ENABLED=true",
            "requires_owner_acceptance_evidence": True,
            "requires_result_receipt_review": True,
            "expected_receipt_status": "dry_run_until_runtime_enabled",
        },
        "rollback_plan": {
            "first_step": "set XAGENT_SDK_WRITE_RUNNER_ENABLED=false",
            "second_step": "verify approvals remain unexecuted for failed runs",
            "third_step": "read sdk.write_runner.failed audit receipt",
            "failure_receipt_required": True,
            "operator_runbook": "docs/runbooks/sdk-write-runner-runtime-enable.md",
        },
        "failure_receipt_contract": {
            "audit_action": "sdk.write_runner.failed",
            "required_fields": [
                "approval_id",
                "owner_acceptance_id",
                "idempotency_key_hash",
                "failure_reason",
                "rollback_required",
                "mark_executed",
                "mutation_summary",
            ],
            "mark_executed_must_be_false_on_failure": True,
            "runner_reinvoke_allowed": False,
        },
        "owner_checklist": [
            "confirm_owner_acceptance_record_readback",
            "confirm_runtime_enablement_review_ready",
            "confirm_implementation_plan_ready",
            "enable_runtime_flag_for_smoke_only",
            "run_single_idempotent_smoke",
            "review_success_or_failure_receipt",
            "disable_runtime_flag_after_smoke",
        ],
        "checks": checks,
        "next_gate": "owner_approved_write_runner_runtime_implementation",
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This contract defines the runtime enablement smoke and rollback runbook only.",
            "The runtime feature flag is not read as permission here and remains disabled.",
            "No smoke command, runner invocation, approval execution marker, or mutation is performed.",
        ],
    }


def _sdk_runtime_enablement_receipt_contract(
    runtime_smoke_runbook: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "runtime_smoke_runbook_ready_but_disabled": runtime_smoke_runbook.get("contract_status")
        == "ready_but_disabled",
        "smoke_requires_runtime_flag": runtime_smoke_runbook.get("smoke_plan", {}).get("requires_runtime_flag")
        == "XAGENT_SDK_WRITE_RUNNER_ENABLED=true",
        "failure_receipt_required": runtime_smoke_runbook.get("rollback_plan", {}).get("failure_receipt_required")
        is True,
        "runtime_flag_still_disabled": runtime_smoke_runbook.get("runtime_flag_enabled") is False,
        "runner_not_invoked": runtime_smoke_runbook.get("runner_invoked") is False,
        "mutation_still_disabled": runtime_smoke_runbook.get("mutation_performed") is False,
    }
    ready = all(checks.values())
    return {
        "available": runtime_smoke_runbook.get("available") is True,
        "stage": "owner_approved_write_runner_runtime_enablement_receipt",
        "receipt_status": "ready_but_disabled" if ready else "blocked",
        "receipt_type": "sdk_write_runner_runtime_enablement_readiness",
        "receipt_schema": {
            "required_fields": [
                "readiness_receipt_id",
                "approval_id",
                "owner_acceptance_id",
                "runtime_flag_name",
                "smoke_runbook_version",
                "rollback_runbook_version",
                "expires_at",
                "accepted_by",
                "acceptance_hash",
            ],
            "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "expires_at_required": True,
            "acceptance_hash_required": True,
        },
        "review_readback": {
            "method": "runtime/evidence/read",
            "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
            "query_keys": ["readiness_receipt_id", "approval_id", "owner_acceptance_id"],
            "returns_schema": True,
            "returns_record_if_present": True,
        },
        "owner_review_policy": {
            "requires_smoke_runbook_acknowledged": True,
            "requires_rollback_runbook_acknowledged": True,
            "requires_failure_receipt_review": True,
            "requires_expiry": True,
            "revoke_command": "xagent sdk runtime-enable revoke <readiness_receipt_id>",
        },
        "audit_contract": {
            "planned_action": "sdk.write_runner.runtime_enablement_receipt_ready",
            "future_record_action": "sdk.write_runner.runtime_enablement_receipt_recorded",
            "future_revoke_action": "sdk.write_runner.runtime_enablement_receipt_revoked",
            "resource_type": "sdk_write_runner_runtime_enablement_readiness",
        },
        "checks": checks,
        "next_gate": "owner_approved_write_runner_runtime_implementation",
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This contract defines a readiness receipt schema and review policy only.",
            "No readiness receipt is recorded by /sdk/invoke.",
            "The runtime flag, runner invocation, approval execution marker, and all mutations remain disabled.",
        ],
    }


def _sdk_runtime_implementation_preflight_contract(
    runtime_enablement_receipt: dict[str, Any],
    write_runner_implementation_plan: dict[str, Any],
) -> dict[str, Any]:
    adapter_target = write_runner_implementation_plan.get("adapter_target", {})
    checks = {
        "readiness_receipt_ready_but_disabled": runtime_enablement_receipt.get("receipt_status")
        == "ready_but_disabled",
        "readiness_receipt_review_readback_strict": runtime_enablement_receipt.get("review_readback", {}).get(
            "query_keys"
        )
        == ["readiness_receipt_id", "approval_id", "owner_acceptance_id"],
        "implementation_plan_ready_but_disabled": write_runner_implementation_plan.get("plan_status")
        == "ready_but_disabled",
        "adapter_module_boundary_declared": adapter_target.get("module")
        == "backend.app.core.agent.coordinator",
        "adapter_callable_declared": adapter_target.get("callable") == "AgentCoordinator.run",
        "idempotency_required": write_runner_implementation_plan.get("idempotency_contract", {}).get("required")
        is True,
        "runtime_flag_still_disabled": runtime_enablement_receipt.get("runtime_flag_enabled") is False,
        "runner_not_invoked": runtime_enablement_receipt.get("runner_invoked") is False,
        "mutation_still_disabled": runtime_enablement_receipt.get("mutation_performed") is False,
    }
    ready = all(checks.values())
    return {
        "available": runtime_enablement_receipt.get("available") is True,
        "stage": "owner_approved_write_runner_runtime_implementation_preflight",
        "preflight_status": "ready_but_disabled" if ready else "blocked",
        "adapter_module_boundary": {
            "module": "backend.app.core.agent.coordinator",
            "class": "AgentCoordinator",
            "callable": "AgentCoordinator.run",
            "import_allowed": False,
            "instantiation_allowed": False,
            "execution_allowed": False,
        },
        "dependency_injection_contract": {
            "required": True,
            "factory_name": "sdk_write_runner_factory",
            "injects": [
                "approval_store",
                "audit_store",
                "agent_coordinator",
                "receipt_store",
                "runtime_flag_reader",
            ],
            "default_factory_enabled": False,
            "runtime_override_allowed": False,
        },
        "idempotency_lock_contract": {
            "required": True,
            "lock_scope": ["tenant_id", "approval_id", "owner_acceptance_id", "idempotency_key"],
            "lock_action": "sdk.write_runner.idempotency_lock_acquired",
            "duplicate_behavior": "return_existing_result_receipt_without_runner_invocation",
            "lock_enabled": False,
        },
        "receipt_persistence_interface": {
            "required": True,
            "interface": "SDKWriteRunnerReceiptStore",
            "success_action": "sdk.write_runner.executed",
            "failure_action": "sdk.write_runner.failed",
            "readback_method": "runtime/evidence/read",
            "required_result_fields": [
                "result_receipt_id",
                "readiness_receipt_id",
                "approval_id",
                "owner_acceptance_id",
                "agent_trace_id",
                "runner_status",
                "idempotency_key_hash",
                "mutation_summary",
            ],
            "persistence_enabled": False,
        },
        "approval_postcondition_contract": {
            "mark_executed_action": "approval.mark_executed",
            "allowed_only_after": [
                "runtime_flag_enabled",
                "idempotency_lock_acquired",
                "agent_runner_success",
                "success_receipt_persisted",
                "audit_success_recorded",
            ],
            "failure_postcondition": "mark_executed_must_remain_false",
            "mark_executed_enabled": False,
        },
        "failure_handling_contract": {
            "failure_action": "sdk.write_runner.failed",
            "persist_failure_receipt": True,
            "release_idempotency_lock_on_failure": True,
            "disable_runtime_flag_on_operator_rollback": True,
            "runner_reinvoke_allowed": False,
            "mark_executed_on_failure": False,
        },
        "checks": checks,
        "next_gate": "owner_approved_write_runner_runtime_implementation",
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This contract declares runtime implementation adapter preflight boundaries only.",
            "AgentCoordinator is not imported, instantiated, or invoked by /sdk/invoke.",
            "Receipt persistence, idempotency locks, approval execution markers, and all mutations remain disabled.",
        ],
    }


def _sdk_runtime_enablement_receipt_record_workflow_contract(
    runtime_implementation_preflight: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "runtime_implementation_preflight_ready_but_disabled": runtime_implementation_preflight.get(
            "preflight_status"
        )
        == "ready_but_disabled",
        "adapter_execution_still_disabled": runtime_implementation_preflight.get("adapter_execution_enabled")
        is False,
        "runner_not_invoked": runtime_implementation_preflight.get("runner_invoked") is False,
        "mark_executed_disabled": runtime_implementation_preflight.get("mark_executed") is False,
        "mutation_still_disabled": runtime_implementation_preflight.get("mutation_performed") is False,
    }
    ready = all(checks.values())
    return {
        "available": runtime_implementation_preflight.get("available") is True,
        "stage": "runtime_enablement_readiness_receipt_record_workflow",
        "workflow_status": "ready_but_disabled" if ready else "blocked",
        "endpoint": "/api/v1/control-plane/sdk/runtime-enablement/receipt/record",
        "sdk_operation": "runtime_enablement_receipt_record",
        "cli_command": "xagent sdk runtime-enable-receipt-record --execute",
        "requires_approved_sdk_approval": True,
        "requires_owner_acceptance_audit_record": True,
        "requires_signature_or_hash": True,
        "requires_expiry": True,
        "requires_smoke_runbook_acknowledged": True,
        "requires_rollback_runbook_acknowledged": True,
        "requires_failure_receipt_reviewed": True,
        "audit_action": "sdk.write_runner.runtime_enablement_receipt_recorded",
        "resource_type": "sdk_write_runner_runtime_enablement_readiness",
        "readback_contract": {
            "method": "runtime/evidence/read",
            "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
            "report_name": "sdk-write-runner-runtime-enable-readiness.json",
            "query_keys": ["readiness_receipt_id", "approval_id", "owner_acceptance_id", "audit_id"],
            "returns_schema": True,
            "returns_record_if_present": True,
        },
        "checks": checks,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This workflow records readiness receipt evidence only.",
            "It does not enable the runtime flag or invoke the SDK write runner.",
            "The readiness receipt can be read back through runtime/evidence/read.",
        ],
    }


def _sdk_runtime_enablement_owner_pack_contract(
    receipt_record_workflow: dict[str, Any],
    *,
    runtime_enablement_receipt: dict[str, Any],
    runtime_smoke_runbook: dict[str, Any],
    owner_acceptance_evidence: dict[str, Any],
    runtime_enablement_review: dict[str, Any],
    runtime_implementation_preflight: dict[str, Any],
) -> dict[str, Any]:
    required_evidence = [
        "approved_sdk_approval",
        "owner_acceptance_audit_record",
        "runtime_enablement_readiness_receipt_record",
        "runtime_enablement_readiness_receipt_readback",
        "smoke_runbook_acknowledgement",
        "rollback_runbook_acknowledgement",
        "failure_receipt_review",
        "expiry_window",
    ]
    checks = {
        "receipt_record_workflow_ready_but_disabled": receipt_record_workflow.get("workflow_status")
        == "ready_but_disabled",
        "readiness_receipt_schema_ready": runtime_enablement_receipt.get("receipt_status")
        == "ready_but_disabled",
        "strict_readback_keys_declared": receipt_record_workflow.get("readback_contract", {}).get("query_keys")
        == ["readiness_receipt_id", "approval_id", "owner_acceptance_id", "audit_id"],
        "owner_acceptance_recording_ready": owner_acceptance_evidence.get("recording_contract_ready") is True,
        "runtime_enablement_review_ready": runtime_enablement_review.get("review_status")
        == "ready_but_disabled",
        "runtime_smoke_runbook_ready": runtime_smoke_runbook.get("contract_status") == "ready_but_disabled",
        "runtime_implementation_preflight_ready": runtime_implementation_preflight.get("preflight_status")
        == "ready_but_disabled",
        "runtime_flag_still_disabled": receipt_record_workflow.get("runtime_flag_enabled") is False,
        "runner_not_invoked": receipt_record_workflow.get("runner_invoked") is False,
        "mark_executed_disabled": receipt_record_workflow.get("mark_executed") is False,
        "mutation_still_disabled": receipt_record_workflow.get("mutation_performed") is False,
    }
    ready = all(checks.values())
    return {
        "available": receipt_record_workflow.get("available") is True,
        "stage": "runtime_enablement_owner_acceptance_pack",
        "pack_status": "ready_but_disabled" if ready else "blocked",
        "pack_type": "sdk_write_runner_runtime_enablement_owner_review_pack",
        "source_workflow": receipt_record_workflow.get("stage"),
        "required_evidence": required_evidence,
        "owner_review_sections": [
            "approval",
            "owner_acceptance",
            "readiness_receipt",
            "readback",
            "smoke_runbook",
            "rollback",
            "failure_receipt",
            "expiry",
            "disabled_execution_invariants",
        ],
        "readback_contract": {
            "method": "runtime/evidence/read",
            "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
            "query_keys": ["readiness_receipt_id", "approval_id", "owner_acceptance_id", "audit_id"],
            "record_required_before_runtime_flag": True,
        },
        "audit_contract": {
            "review_action": "sdk.write_runner.runtime_enablement_owner_pack_reviewed",
            "source_record_action": "sdk.write_runner.runtime_enablement_receipt_recorded",
            "resource_type": "sdk_write_runner_runtime_enablement_owner_review_pack",
            "audit_event_recorded_now": False,
        },
        "owner_decision_policy": {
            "manual_review_required": True,
            "can_enable_runtime_flag_after_pack": False,
            "next_gate": "owner_approved_write_runner_runtime_implementation",
            "rollback_required_before_any_smoke": True,
        },
        "checks": checks,
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This pack aggregates owner review evidence only.",
            "It does not record a new audit event by /sdk/invoke.",
            "It does not enable the runtime flag or invoke the SDK write runner.",
        ],
    }


def _sdk_runtime_enablement_owner_pack_decision_workflow_contract(
    owner_pack: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "owner_pack_ready_but_disabled": owner_pack.get("pack_status") == "ready_but_disabled",
        "manual_review_required": owner_pack.get("owner_decision_policy", {}).get("manual_review_required")
        is True,
        "runtime_flag_cannot_be_enabled_after_pack": owner_pack.get("owner_decision_policy", {}).get(
            "can_enable_runtime_flag_after_pack"
        )
        is False,
        "runtime_flag_still_disabled": owner_pack.get("runtime_flag_enabled") is False,
        "runner_not_invoked": owner_pack.get("runner_invoked") is False,
        "mark_executed_disabled": owner_pack.get("mark_executed") is False,
        "mutation_still_disabled": owner_pack.get("mutation_performed") is False,
    }
    ready = all(checks.values())
    return {
        "available": owner_pack.get("available") is True,
        "stage": "runtime_enablement_owner_pack_decision_record_workflow",
        "workflow_status": "ready_but_disabled" if ready else "blocked",
        "endpoint": "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record",
        "sdk_operation": "runtime_enablement_owner_pack_decision_record",
        "cli_command": "xagent sdk runtime-enable-owner-pack-decision-record --execute",
        "requires_approved_sdk_approval": True,
        "requires_runtime_enablement_readiness_receipt": True,
        "requires_decision_accept_or_reject": True,
        "requires_signature_or_hash": True,
        "audit_action": "sdk.write_runner.runtime_enablement_owner_pack_decision_recorded",
        "resource_type": "sdk_write_runner_runtime_enablement_owner_review_pack",
        "audit_event_recorded_by_sdk_invoke": False,
        "allowed_decisions": ["accepted", "rejected"],
        "decision_effect": {
            "accepted_enables_runtime_flag": False,
            "rejected_rolls_back_runtime": False,
            "marks_approval_executed": False,
        },
        "checks": checks,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This workflow records owner pack accept/reject decisions only.",
            "It does not enable the runtime flag or invoke the SDK write runner.",
            "It does not mark approvals executed or mutate runtime state.",
        ],
    }


def _sdk_runtime_implementation_readiness_lock_workflow_contract(
    owner_pack_decision: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "owner_pack_decision_workflow_ready_but_disabled": owner_pack_decision.get("workflow_status")
        == "ready_but_disabled",
        "decision_accept_or_reject_required": owner_pack_decision.get("requires_decision_accept_or_reject")
        is True,
        "runtime_flag_still_disabled": owner_pack_decision.get("runtime_flag_enabled") is False,
        "runner_not_invoked": owner_pack_decision.get("runner_invoked") is False,
        "mark_executed_disabled": owner_pack_decision.get("mark_executed") is False,
        "mutation_still_disabled": owner_pack_decision.get("mutation_performed") is False,
    }
    ready = all(checks.values())
    return {
        "available": owner_pack_decision.get("available") is True,
        "stage": "runtime_implementation_readiness_lock_record_workflow",
        "workflow_status": "ready_but_disabled" if ready else "blocked",
        "endpoint": "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
        "sdk_operation": "runtime_implementation_readiness_lock_record",
        "cli_command": "xagent sdk runtime-implementation-readiness-lock-record --execute",
        "requires_approved_sdk_approval": True,
        "requires_runtime_enablement_readiness_receipt": True,
        "requires_accepted_owner_pack_decision": True,
        "requires_idempotency_key": True,
        "requires_idempotency_hash": True,
        "requires_signature_or_hash": True,
        "audit_action": "sdk.write_runner.runtime_implementation_readiness_lock_recorded",
        "resource_type": "sdk_write_runner_runtime_implementation_readiness_lock",
        "audit_event_recorded_by_sdk_invoke": False,
        "lock_effect": {
            "enables_runtime_flag": False,
            "starts_agent_execution": False,
            "marks_approval_executed": False,
            "persists_runner_default": False,
        },
        "checks": checks,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This workflow records a runtime implementation readiness lock only.",
            "The lock is idempotency evidence, not an execution enablement switch.",
            "It does not enable runtime flags, invoke the SDK write runner, or mark approvals executed.",
        ],
    }


def _sdk_runtime_implementation_owner_pack_contract(
    readiness_lock_workflow: dict[str, Any],
) -> dict[str, Any]:
    required_evidence = [
        "approved_sdk_approval",
        "runtime_enablement_readiness_receipt_record",
        "accepted_owner_pack_decision",
        "runtime_implementation_readiness_lock_record",
        "runtime_implementation_readiness_lock_readback",
        "idempotency_key_and_hash",
        "disabled_execution_invariants",
    ]
    checks = {
        "readiness_lock_workflow_ready": readiness_lock_workflow.get("workflow_status")
        == "ready_but_disabled",
        "readiness_lock_endpoint_present": readiness_lock_workflow.get("endpoint")
        == "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
        "readiness_lock_requires_accepted_decision": readiness_lock_workflow.get(
            "requires_accepted_owner_pack_decision"
        )
        is True,
        "runtime_flag_still_disabled": readiness_lock_workflow.get("runtime_flag_enabled") is False,
        "runner_not_invoked": readiness_lock_workflow.get("runner_invoked") is False,
        "mark_executed_disabled": readiness_lock_workflow.get("mark_executed") is False,
        "mutation_still_disabled": readiness_lock_workflow.get("mutation_performed") is False,
    }
    ready = all(checks.values())
    return {
        "available": readiness_lock_workflow.get("available") is True,
        "stage": "runtime_implementation_owner_acceptance_pack",
        "pack_status": "ready_but_disabled" if ready else "blocked",
        "pack_type": "sdk_write_runner_runtime_implementation_owner_review_pack",
        "source_workflow": "runtime_implementation_readiness_lock_record_workflow",
        "required_evidence": required_evidence,
        "owner_review_sections": [
            "approval",
            "readiness_receipt",
            "owner_pack_decision",
            "readiness_lock",
            "readback",
            "idempotency",
            "disabled_execution_invariants",
        ],
        "readback_contract": {
            "method": "runtime/evidence/read",
            "evidence_type": "sdk_write_runner_runtime_implementation_readiness_lock",
            "report_name": "sdk-write-runner-runtime-implementation-readiness-lock.json",
            "query_keys": [
                "implementation_lock_id",
                "approval_id",
                "readiness_receipt_id",
                "owner_pack_decision_id",
                "audit_id",
            ],
            "record_required_before_runtime_implementation": True,
        },
        "audit_contract": {
            "review_action": "sdk.write_runner.runtime_implementation_owner_pack_reviewed",
            "source_record_action": "sdk.write_runner.runtime_implementation_readiness_lock_recorded",
            "resource_type": "sdk_write_runner_runtime_implementation_owner_review_pack",
            "audit_event_recorded_now": False,
        },
        "owner_decision_policy": {
            "manual_review_required": True,
            "can_enable_runtime_flag_after_pack": False,
            "can_invoke_write_runner_after_pack": False,
            "next_gate": "owner_approved_write_runner_runtime_implementation_final_decision",
        },
        "checks": checks,
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This pack aggregates readiness lock evidence only.",
            "It does not record a new audit event by /sdk/invoke.",
            "It does not enable the runtime flag or invoke the SDK write runner.",
        ],
    }


def _sdk_runtime_implementation_final_decision_workflow_contract(
    implementation_owner_pack: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "owner_pack_ready_but_disabled": implementation_owner_pack.get("pack_status")
        == "ready_but_disabled",
        "manual_review_required": implementation_owner_pack.get("owner_decision_policy", {}).get(
            "manual_review_required"
        )
        is True,
        "runtime_flag_still_disabled": implementation_owner_pack.get("runtime_flag_enabled") is False,
        "implementation_still_disabled": implementation_owner_pack.get("implementation_enabled") is False,
        "runner_not_invoked": implementation_owner_pack.get("runner_invoked") is False,
        "mark_executed_disabled": implementation_owner_pack.get("mark_executed") is False,
        "mutation_still_disabled": implementation_owner_pack.get("mutation_performed") is False,
    }
    ready = all(checks.values())
    return {
        "available": implementation_owner_pack.get("available") is True,
        "stage": "runtime_implementation_final_decision_record_workflow",
        "workflow_status": "ready_but_disabled" if ready else "blocked",
        "endpoint": "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
        "sdk_operation": "runtime_implementation_final_decision_record",
        "cli_command": "xagent sdk runtime-implementation-final-decision-record --execute",
        "requires_approved_sdk_approval": True,
        "requires_runtime_implementation_readiness_lock": True,
        "requires_decision_accept_or_reject": True,
        "requires_signature_or_hash": True,
        "audit_action": "sdk.write_runner.runtime_implementation_final_decision_recorded",
        "resource_type": "sdk_write_runner_runtime_implementation_final_decision",
        "audit_event_recorded_by_sdk_invoke": False,
        "decision_effect": {
            "enables_runtime_flag": False,
            "starts_agent_execution": False,
            "marks_approval_executed": False,
            "persists_runner_default": False,
        },
        "next_gate": "owner_explicit_runtime_flag_enablement_and_live_runner_implementation",
        "checks": checks,
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This workflow records a final owner decision only.",
            "Accepted final decisions do not enable runtime flags or invoke the SDK write runner.",
            "Concrete runtime implementation remains a separate owner-requested task.",
        ],
    }


def _sdk_runtime_flag_enablement_record_workflow_contract(
    final_decision_workflow: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "final_decision_ready_but_disabled": final_decision_workflow.get("workflow_status")
        == "ready_but_disabled",
        "final_decision_does_not_enable_flag": final_decision_workflow.get("decision_effect", {}).get(
            "enables_runtime_flag"
        )
        is False,
        "runtime_flag_still_disabled": final_decision_workflow.get("runtime_flag_enabled") is False,
        "implementation_still_disabled": final_decision_workflow.get("implementation_enabled") is False,
        "runner_not_invoked": final_decision_workflow.get("runner_invoked") is False,
        "mark_executed_disabled": final_decision_workflow.get("mark_executed") is False,
        "mutation_still_disabled": final_decision_workflow.get("mutation_performed") is False,
    }
    ready = all(checks.values())
    return {
        "available": final_decision_workflow.get("available") is True,
        "stage": "runtime_flag_enablement_record_workflow",
        "workflow_status": "ready_but_disabled" if ready else "blocked",
        "endpoint": "/api/v1/control-plane/sdk/runtime-flag/enablement/record",
        "sdk_operation": "runtime_flag_enablement_record",
        "cli_command": "xagent sdk runtime-flag-enable-record --execute",
        "requires_approved_sdk_approval": True,
        "requires_runtime_implementation_final_decision": True,
        "requires_final_decision_accepted": True,
        "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        "requires_signature_or_hash": True,
        "audit_action": "sdk.write_runner.runtime_flag_enablement_requested",
        "resource_type": "sdk_write_runner_runtime_flag_enablement_request",
        "audit_event_recorded_by_sdk_invoke": False,
        "decision_effect": {
            "enables_runtime_flag": False,
            "starts_agent_execution": False,
            "marks_approval_executed": False,
            "persists_runner_default": False,
        },
        "next_gate": "owner_requested_live_runtime_flag_application_and_write_runner_implementation",
        "checks": checks,
        "implementation_enabled": False,
        "runtime_flag_enabled": False,
        "execute_enabled": False,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "write_execution_enabled": False,
        "runner_invoked": False,
        "mark_executed": False,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "file_mutation_performed": False,
        "channel_mutation_performed": False,
        "known_limits": [
            "This workflow records explicit owner runtime flag enablement intent only.",
            "It does not set XAGENT_SDK_WRITE_RUNNER_ENABLED or start the SDK write runner.",
            "Live runtime flag application remains a separate owner-requested implementation task.",
        ],
    }


def _sdk_owner_acceptance_evidence_schema(required_fields: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": required_fields,
        "properties": {
            "owner_acceptance_id": "string",
            "accepted_by": "string",
            "accepted_at": "RFC3339 timestamp",
            "approval_id": "string",
            "runbook_acknowledged": "boolean true",
            "rollback_plan_acknowledged": "boolean true",
            "acceptance_signature": "string optional",
            "acceptance_hash": "string optional",
            "notes": "string optional",
        },
        "safety_invariants": {
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "mutation_performed": False,
        },
    }


def _sdk_owner_acceptance_evidence_validation(record: dict[str, Any] | None) -> dict[str, Any]:
    required_fields = [
        "owner_acceptance_id",
        "accepted_by",
        "accepted_at",
        "approval_id",
        "runbook_acknowledged",
        "rollback_plan_acknowledged",
    ]
    checks = {
        "record_present": isinstance(record, dict),
        "required_fields_present": bool(
            isinstance(record, dict) and all(record.get(field) not in (None, "") for field in required_fields)
        ),
        "accepted_at_rfc3339": bool(
            isinstance(record, dict) and _is_rfc3339_timestamp(record.get("accepted_at"))
        ),
        "runbook_acknowledged": bool(isinstance(record, dict) and record.get("runbook_acknowledged") is True),
        "rollback_plan_acknowledged": bool(
            isinstance(record, dict) and record.get("rollback_plan_acknowledged") is True
        ),
        "signature_or_hash_present": bool(
            isinstance(record, dict) and (record.get("acceptance_signature") or record.get("acceptance_hash"))
        ),
    }
    return {
        "status": "valid" if all(checks.values()) else "invalid",
        "checks": checks,
    }


def _sdk_runtime_enablement_receipt_schema(required_fields: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": required_fields,
        "properties": {
            "readiness_receipt_id": "string",
            "approval_id": "string",
            "owner_acceptance_id": "string",
            "owner_acceptance_audit_id": "string",
            "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "smoke_runbook_version": "string",
            "rollback_runbook_version": "string",
            "accepted_by": "string",
            "accepted_at": "RFC3339 timestamp",
            "expires_at": "RFC3339 timestamp",
            "smoke_runbook_acknowledged": "boolean true",
            "rollback_runbook_acknowledged": "boolean true",
            "failure_receipt_reviewed": "boolean true",
            "acceptance_signature": "string optional",
            "acceptance_hash": "string optional",
            "notes": "string optional",
        },
        "safety_invariants": {
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }


def _sdk_runtime_enablement_receipt_validation(record: dict[str, Any] | None) -> dict[str, Any]:
    required_fields = [
        "readiness_receipt_id",
        "approval_id",
        "owner_acceptance_id",
        "owner_acceptance_audit_id",
        "runtime_flag_name",
        "smoke_runbook_version",
        "rollback_runbook_version",
        "accepted_by",
        "accepted_at",
        "expires_at",
        "smoke_runbook_acknowledged",
        "rollback_runbook_acknowledged",
        "failure_receipt_reviewed",
    ]
    checks = {
        "record_present": isinstance(record, dict),
        "required_fields_present": bool(
            isinstance(record, dict) and all(record.get(field) not in (None, "") for field in required_fields)
        ),
        "runtime_flag_name_expected": bool(
            isinstance(record, dict)
            and record.get("runtime_flag_name") == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
        ),
        "accepted_at_rfc3339": bool(
            isinstance(record, dict) and _is_rfc3339_timestamp(record.get("accepted_at"))
        ),
        "expires_at_rfc3339": bool(
            isinstance(record, dict) and _is_rfc3339_timestamp(record.get("expires_at"))
        ),
        "expires_after_accepted_at": _expires_after_accepted_at(record),
        "smoke_runbook_acknowledged": bool(
            isinstance(record, dict) and record.get("smoke_runbook_acknowledged") is True
        ),
        "rollback_runbook_acknowledged": bool(
            isinstance(record, dict) and record.get("rollback_runbook_acknowledged") is True
        ),
        "failure_receipt_reviewed": bool(
            isinstance(record, dict) and record.get("failure_receipt_reviewed") is True
        ),
        "signature_or_hash_present": bool(
            isinstance(record, dict) and (record.get("acceptance_signature") or record.get("acceptance_hash"))
        ),
    }
    return {
        "status": "valid" if all(checks.values()) else "invalid",
        "checks": checks,
    }


def _expires_after_accepted_at(record: dict[str, Any] | None) -> bool:
    if not isinstance(record, dict):
        return False
    accepted_at = record.get("accepted_at")
    expires_at = record.get("expires_at")
    if not isinstance(accepted_at, str) or not isinstance(expires_at, str):
        return False
    try:
        accepted = datetime.fromisoformat(accepted_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return expires > accepted


def _is_rfc3339_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _sdk_approval_intent(
    request: ControlPlaneInvokeRequest,
    *,
    principal: Principal,
    approval_store: object,
    approved_approval_id: str | None = None,
) -> dict[str, Any]:
    spec = METHODS_BY_NAME.get(request.method)
    if spec is None or spec.operation_kind == "read":
        return {
            "required": False,
            "created": False,
            "approval_id": None,
            "status": "not_required",
            "mutation_performed": False,
        }
    if approved_approval_id:
        return {
            "required": True,
            "created": False,
            "approval_id": approved_approval_id,
            "status": "provided_for_preflight",
            "subject_type": ApprovalSubjectType.COMMAND.value,
            "resource_type": "command",
            "resource_id": f"sdk:{request.method}",
            "mutation_performed": False,
            "adapter_execution_enabled": False,
        }

    approval_contract = _sdk_approval_sandbox_admin_contract(request)
    context = RunContext(
        trace_id=request.context.trace_id or principal.trace_id or f"trace_{uuid4().hex}",
        tenant_id=request.context.tenant_id or principal.tenant_id,
        user_id=request.context.user_id or request.context.actor_id or principal.user_id,
        request_id=request.id,
        permission_scope=_permission_scope_from_request(request),
        risk_level=RiskLevel.HIGH,
    )
    create = getattr(approval_store, "create_approval", None)
    if not callable(create):
        return {
            "required": True,
            "created": False,
            "approval_id": None,
            "status": "approval_store_unavailable",
            "mutation_performed": False,
        }

    record = create(
        context=context,
        resource_type="command",
        resource_id=f"sdk:{request.method}",
        action=approval_contract["action"],
        risk_level=RiskLevel.HIGH,
        reason=f"Owner approval required before SDK non-interactive execution for {request.method}.",
        arguments_preview=_sdk_approval_arguments_preview(request),
        arguments={},
        subject_type=ApprovalSubjectType.COMMAND,
        sandbox_profile=approval_contract["sandbox_profile"],
        owner_gate_required=True,
        audit_required=True,
        policy_snapshot={
            "source": "sdk_control_plane",
            "method": request.method,
            "operation": request.context.sdk_operation,
            "idempotency_key_present": bool(request.idempotency_key),
            "adapter_execution_enabled": False,
            "mutation_performed": False,
        },
    )
    return {
        "required": True,
        "created": True,
        "approval_id": getattr(record, "id", None),
        "status": _status_value(getattr(record, "status", None)),
        "subject_type": _status_value(getattr(record, "subject_type", None)),
        "resource_type": getattr(record, "resource_type", None),
        "resource_id": getattr(record, "resource_id", None),
        "action": getattr(record, "action", None),
        "risk_level": _status_value(getattr(record, "risk_level", None)),
        "sandbox_profile": getattr(record, "sandbox_profile", None),
        "owner_gate_required": getattr(record, "owner_gate_required", True),
        "audit_required": getattr(record, "audit_required", True),
        "mutation_performed": False,
        "adapter_execution_enabled": False,
    }


def _permission_scope_from_request(request: ControlPlaneInvokeRequest) -> list[str]:
    scope = request.params.get("permission_scope")
    if isinstance(scope, list) and all(isinstance(item, str) for item in scope):
        return list(scope)
    return ["tools:read", "memory:read"]


def _sdk_approval_arguments_preview(request: ControlPlaneInvokeRequest) -> dict[str, Any]:
    preview: dict[str, Any] = {
        "method": request.method,
        "operation": request.context.sdk_operation,
        "dry_run": request.dry_run,
        "idempotency_key_present": bool(request.idempotency_key),
        "adapter_execution_enabled": False,
        "mutation_performed": False,
    }
    for key in ("thread_id", "task", "input"):
        value = request.params.get(key)
        if isinstance(value, str):
            preview[key] = value[:200]
    return preview


def _sdk_approval_sandbox_admin_contract(request: ControlPlaneInvokeRequest) -> dict[str, Any]:
    subject_type = ApprovalSubjectType.COMMAND
    policy = get_enterprise_safety_policy(subject_type)
    return {
        "subject_type": subject_type.value,
        "action": APPROVAL_SUBJECT_ACTIONS[subject_type],
        "sandbox_profile": policy.default_sandbox_profile if policy else "command_locked",
        "minimum_risk_level": policy.minimum_risk_level.value if policy else "high",
        "owner_gate_required": True,
        "admin_policy_required": True if policy is None else policy.admin_policy_required,
        "audit_required": True if policy is None else policy.audit_required,
        "blocked_without_approval": True if policy is None else policy.blocked_without_approval,
        "adapter_execution_enabled": False,
        "mutation_performed": False,
        "decision_types": list(policy.allowed_decision_types) if policy else [],
        "method": request.method,
    }


def _contract_result(
    spec: ControlPlaneMethodSpec,
    request: ControlPlaneInvokeRequest,
    *,
    principal: Principal,
    audit_store: AuditStore,
    run_store: object,
    trace_store: object,
    approval_store: object,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        **spec.to_payload(),
        "contract": {
            "id": request.id,
            "method": request.method,
            "status_vocabulary": list(STATUS_VOCABULARY),
            "dry_run": request.dry_run,
            "idempotency_key_present": bool(request.idempotency_key),
            "mutation_performed": False,
            "adapter_execution_enabled": False,
        },
        "compatibility": {
            "thread_id": request.params.get("thread_id") or request.params.get("trace_id"),
            "turn_id": request.params.get("turn_id"),
            "item_id": request.params.get("item_id"),
            "trace_id": request.context.trace_id or request.params.get("trace_id"),
            "workspace_id": request.context.workspace_id,
            "actor_id": request.context.actor_id or request.context.user_id,
            "sdk_surface": request.context.sdk_surface,
            "non_interactive": request.context.non_interactive,
        },
    }
    if spec.method == "thread/read":
        result["thread"] = _thread_read_state(
            request,
            principal=principal,
            run_store=run_store,
            trace_store=trace_store,
            approval_store=approval_store,
        )
    elif spec.method == "thread/search":
        result["threads"] = _thread_search_state(
            request,
            principal=principal,
            run_store=run_store,
            trace_store=trace_store,
            approval_store=approval_store,
        )
    elif spec.method == "turn/events/list":
        result["events"] = _turn_events_state(request, trace_store=trace_store)
    elif spec.method == "approval/list":
        result["approvals"] = _approval_list_state(
            request,
            principal=principal,
            approval_store=approval_store,
        )
    elif spec.method == "approval/read":
        result["approval"] = _approval_read_state(request, approval_store=approval_store)
    if spec.method == "runtime/evidence/read":
        result["evidence"] = _runtime_evidence_metadata(
            request.params,
            audit_store=audit_store,
            principal=principal,
        )
    return result


def _adapter_pending_details(
    spec: ControlPlaneMethodSpec,
    request: ControlPlaneInvokeRequest,
    *,
    run_store: object,
    trace_store: object,
    approval_store: object,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "method": spec.method,
        "group": spec.group,
        "operation_kind": spec.operation_kind,
        "requires_approval": spec.requires_approval,
        "implementation_state": spec.implementation_state,
        "dry_run": request.dry_run,
        "idempotency_key_present": bool(request.idempotency_key),
        "mutation_performed": False,
    }
    if request.context.non_interactive is True or request.context.sdk_surface:
        details["sdk"] = {
            "operation": request.context.sdk_operation,
            "surface": request.context.sdk_surface,
            "non_interactive": True,
            "owner_gate_required": spec.operation_kind != "read",
            "adapter_execution_enabled": False,
            "mutation_performed": False,
            "approval_sandbox_admin": _sdk_approval_sandbox_admin_contract(request),
        }
    if spec.method in {"thread/start", "thread/fork", "thread/resume", "thread/rollback", "thread/compact", "turn/start"}:
        details["thread_operation"] = _thread_operation_metadata(
            spec,
            request,
            run_store=run_store,
            trace_store=trace_store,
            approval_store=approval_store,
        )
    return details


def _thread_read_state(
    request: ControlPlaneInvokeRequest,
    *,
    principal: Principal,
    run_store: object,
    trace_store: object,
    approval_store: object,
) -> dict[str, Any]:
    thread_id = _thread_id_from_request(request)
    if not thread_id:
        return {
            "status": "missing_thread_id",
            "thread_id": None,
            "error": "thread/read requires thread_id or trace_id.",
        }

    record = _store_get(run_store, thread_id)
    if record is not None and getattr(record, "tenant_id", principal.tenant_id) != principal.tenant_id:
        return {"status": "not_found", "thread_id": thread_id}

    if record is not None:
        return _thread_payload_from_run(record, trace_store, approval_store)

    summary = _trace_summary(trace_store, thread_id)
    if summary is not None and getattr(summary, "event_count", 0) > 0:
        return _thread_payload_from_trace(summary, trace_store, approval_store)
    return {"status": "not_found", "thread_id": thread_id}


def _thread_search_state(
    request: ControlPlaneInvokeRequest,
    *,
    principal: Principal,
    run_store: object,
    trace_store: object,
    approval_store: object,
) -> dict[str, Any]:
    limit = _bounded_int(request.params.get("limit"), default=20, minimum=1, maximum=100)
    status_filter = request.params.get("status")
    records = [
        record
        for record in _store_list(run_store, limit=limit)
        if getattr(record, "tenant_id", principal.tenant_id) == principal.tenant_id
    ]
    if isinstance(status_filter, str):
        records = [
            record
            for record in records
            if _status_value(getattr(record, "status", None)) == status_filter
        ]
    threads = [
        _thread_summary_from_run(record, trace_store, approval_store)
        for record in records[:limit]
    ]
    return {
        "count": len(threads),
        "limit": limit,
        "items": threads,
        "worktree": _worktree_metadata(request),
        "automations": _automation_metadata(),
    }


def _turn_events_state(
    request: ControlPlaneInvokeRequest,
    *,
    trace_store: object,
) -> dict[str, Any]:
    thread_id = _thread_id_from_request(request)
    limit = _bounded_int(request.params.get("limit"), default=100, minimum=1, maximum=500)
    if not thread_id:
        return {
            "thread_id": None,
            "turn_id": request.params.get("turn_id"),
            "count": 0,
            "items": [],
            "error": "turn/events/list requires thread_id or trace_id.",
        }
    events = _trace_events(trace_store, thread_id)[:limit]
    turn_id = request.params.get("turn_id") or f"{thread_id}:turn:latest"
    return {
        "thread_id": thread_id,
        "turn_id": turn_id,
        "count": len(events),
        "items": [
            {
                "event_id": f"{thread_id}:event:{index + 1}",
                "type": getattr(event, "event", "unknown"),
                "thread_id": thread_id,
                "turn_id": turn_id,
                "item_id": f"{thread_id}:item:{index + 1}",
                "payload": getattr(event, "data", {}),
                "created_at": _jsonable(getattr(event, "timestamp", None)),
            }
            for index, event in enumerate(events)
        ],
    }


def _approval_list_state(
    request: ControlPlaneInvokeRequest,
    *,
    principal: Principal,
    approval_store: object,
) -> dict[str, Any]:
    limit = _bounded_int(request.params.get("limit"), default=50, minimum=1, maximum=200)
    status_filter = request.params.get("status")
    records = _approval_records(
        approval_store,
        tenant_id=principal.tenant_id,
        status=status_filter if isinstance(status_filter, str) else None,
        limit=limit,
    )
    return {
        "count": len(records),
        "limit": limit,
        "items": [_approval_payload(record) for record in records],
    }


def _approval_read_state(
    request: ControlPlaneInvokeRequest,
    *,
    approval_store: object,
) -> dict[str, Any]:
    approval_id = request.params.get("approval_id")
    if not isinstance(approval_id, str) or not approval_id:
        return {"status": "missing_approval_id", "approval_id": None}
    record = getattr(approval_store, "get", lambda _approval_id: None)(approval_id)
    if record is None:
        return {"status": "not_found", "approval_id": approval_id}
    return _approval_payload(record)


def _thread_operation_metadata(
    spec: ControlPlaneMethodSpec,
    request: ControlPlaneInvokeRequest,
    *,
    run_store: object,
    trace_store: object,
    approval_store: object,
) -> dict[str, Any]:
    thread_id = _thread_id_from_request(request)
    record = _store_get(run_store, thread_id) if thread_id else None
    return {
        "operation": spec.method.rsplit("/", 1)[-1],
        "thread_id": thread_id,
        "source_status": _status_value(getattr(record, "status", None)) if record else "unknown",
        "source_exists": record is not None,
        "metadata_only": True,
        "mutation_performed": False,
        "file_system_rollback": False,
        "file_rollback_claimed": False,
        "approval_required": spec.requires_approval,
        "worktree": _worktree_metadata(request),
        "automations": _automation_metadata(),
        "evidence_links": _thread_evidence_links(thread_id) if thread_id else {},
        "approval_summary": _approval_summary(thread_id, approval_store) if thread_id else {},
        "trace_event_count": len(_trace_events(trace_store, thread_id)) if thread_id else 0,
    }


def _thread_payload_from_run(
    record: Any,
    trace_store: object,
    approval_store: object,
) -> dict[str, Any]:
    trace_id = getattr(record, "trace_id", "")
    events = _trace_events(trace_store, trace_id)
    status = _status_value(getattr(record, "status", None))
    return {
        "status": status,
        "thread_id": trace_id,
        "trace_id": trace_id,
        "task": getattr(record, "task", ""),
        "agent_id": getattr(record, "agent_id", None),
        "tenant_id": getattr(record, "tenant_id", None),
        "user_id": getattr(record, "user_id", None),
        "created_at": _jsonable(getattr(record, "created_at", None)),
        "completed_at": _jsonable(getattr(record, "completed_at", None)),
        "turns": [_turn_summary_from_run(record, events)],
        "items": _thread_items_from_run(record),
        "tool_calls": {
            "count": getattr(record, "tool_call_count", 0),
            "items": [_jsonable(item) for item in getattr(record, "tool_calls", [])],
        },
        "approval_summary": _approval_summary(trace_id, approval_store),
        "artifacts": _artifact_metadata(record),
        "channel_events": _channel_event_metadata(record),
        "evidence_links": _thread_evidence_links(trace_id),
        "fork": _thread_action_metadata("fork", trace_id),
        "resume": _thread_action_metadata("resume", trace_id),
        "rollback": _thread_action_metadata("rollback", trace_id),
        "worktree": _worktree_metadata_from_record(record),
        "automations": _automation_metadata(),
    }


def _thread_payload_from_trace(
    summary: Any,
    trace_store: object,
    approval_store: object,
) -> dict[str, Any]:
    trace_id = getattr(summary, "trace_id", "")
    events = _trace_events(trace_store, trace_id)
    return {
        "status": "trace_only",
        "thread_id": trace_id,
        "trace_id": trace_id,
        "task": getattr(summary, "task", None),
        "turns": [_turn_summary_from_trace(summary, events)],
        "items": _thread_items_from_events(trace_id, events),
        "tool_calls": {"count": 0, "items": []},
        "approval_summary": _approval_summary(trace_id, approval_store),
        "artifacts": [],
        "channel_events": [],
        "evidence_links": _thread_evidence_links(trace_id),
        "fork": _thread_action_metadata("fork", trace_id),
        "resume": _thread_action_metadata("resume", trace_id),
        "rollback": _thread_action_metadata("rollback", trace_id),
        "worktree": _worktree_metadata_from_trace(summary),
        "automations": _automation_metadata(),
    }


def _thread_summary_from_run(
    record: Any,
    trace_store: object,
    approval_store: object,
) -> dict[str, Any]:
    trace_id = getattr(record, "trace_id", "")
    summary = _trace_summary(trace_store, trace_id)
    return {
        "thread_id": trace_id,
        "trace_id": trace_id,
        "task": getattr(record, "task", ""),
        "status": _status_value(getattr(record, "status", None)),
        "agent_id": getattr(record, "agent_id", None),
        "created_at": _jsonable(getattr(record, "created_at", None)),
        "completed_at": _jsonable(getattr(record, "completed_at", None)),
        "event_count": getattr(summary, "event_count", 0) if summary else 0,
        "tool_call_count": getattr(record, "tool_call_count", 0),
        "approval_summary": _approval_summary(trace_id, approval_store),
        "evidence_links": _thread_evidence_links(trace_id),
        "worktree": _worktree_metadata_from_record(record),
        "automations": _automation_metadata(),
    }


def _thread_id_from_request(request: ControlPlaneInvokeRequest) -> str | None:
    value = (
        request.params.get("thread_id")
        or request.params.get("trace_id")
        or request.context.trace_id
    )
    return value if isinstance(value, str) and value else None


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _store_get(store: object, trace_id: str | None) -> Any | None:
    if not trace_id or not hasattr(store, "get"):
        return None
    try:
        return store.get(trace_id)
    except Exception:
        return None


def _store_list(store: object, *, limit: int) -> list[Any]:
    if not hasattr(store, "list"):
        return []
    try:
        records = store.list(limit=limit)
    except TypeError:
        records = store.list()
    except Exception:
        return []
    return list(records or [])[:limit]


def _trace_summary(trace_store: object, trace_id: str | None) -> Any | None:
    if not trace_id or not hasattr(trace_store, "get_summary"):
        return None
    try:
        return trace_store.get_summary(trace_id)
    except Exception:
        return None


def _trace_events(trace_store: object, trace_id: str | None) -> list[Any]:
    if not trace_id or not hasattr(trace_store, "list_events"):
        return []
    try:
        return list(trace_store.list_events(trace_id) or [])
    except Exception:
        return []


def _status_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    if raw is None:
        return "queued"
    text = str(raw)
    if text == "needs_approval":
        return "waiting_for_approval"
    return text if text in STATUS_VOCABULARY else text


def _approval_records(
    approval_store: object,
    *,
    tenant_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[Any]:
    if not hasattr(approval_store, "list"):
        return []
    try:
        records = list(approval_store.list(limit=limit, tenant_id=tenant_id) or [])
    except TypeError:
        try:
            records = list(approval_store.list(limit=limit) or [])
        except Exception:
            return []
    except Exception:
        return []

    filtered = []
    for record in records:
        if tenant_id and getattr(record, "tenant_id", None) != tenant_id:
            continue
        if status and _status_value(getattr(record, "status", None)) != status:
            continue
        filtered.append(record)
    return filtered[:limit]


def _approval_payload(record: Any) -> dict[str, Any]:
    return {
        "approval_id": getattr(record, "id", None),
        "tenant_id": getattr(record, "tenant_id", None),
        "actor_id": getattr(record, "actor_id", None),
        "trace_id": getattr(record, "trace_id", None),
        "resource_type": getattr(record, "resource_type", None),
        "resource_id": getattr(record, "resource_id", None),
        "action": getattr(record, "action", None),
        "risk_level": _status_value(getattr(record, "risk_level", None)),
        "status": _status_value(getattr(record, "status", None)),
        "reason": getattr(record, "reason", None),
        "arguments_preview": _jsonable(getattr(record, "arguments_preview", {})),
        "decided_by": getattr(record, "decided_by", None),
        "decided_at": _jsonable(getattr(record, "decided_at", None)),
        "executed_by": getattr(record, "executed_by", None),
        "executed_at": _jsonable(getattr(record, "executed_at", None)),
        "created_at": _jsonable(getattr(record, "created_at", None)),
    }


def _approval_summary(trace_id: str | None, approval_store: object) -> dict[str, Any]:
    records = [
        record
        for record in _approval_records(approval_store, limit=200)
        if trace_id and getattr(record, "trace_id", None) == trace_id
    ]
    statuses: dict[str, int] = {}
    for record in records:
        status = _status_value(getattr(record, "status", None))
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "trace_id": trace_id,
        "count": len(records),
        "pending": statuses.get("pending", 0),
        "statuses": statuses,
        "items": [_approval_payload(record) for record in records[:10]],
    }


def _thread_evidence_links(trace_id: str) -> dict[str, str]:
    return {
        "run": f"/api/v1/runs/{trace_id}",
        "trace": f"/api/v1/traces/{trace_id}",
        "timeline": f"/api/v1/runs/{trace_id}/timeline",
        "agent_timeline": f"/api/v1/agents/runs/{trace_id}/timeline",
        "control_plane": "/api/v1/control-plane/invoke",
    }


def _thread_action_metadata(action: str, trace_id: str) -> dict[str, Any]:
    return {
        "action": action,
        "thread_id": trace_id,
        "available": True,
        "metadata_only": True,
        "mutation_performed": False,
        "requires_approval": action in {"fork", "rollback"},
        "file_system_rollback": False,
        "file_rollback_claimed": False,
    }


def _worktree_metadata(request: ControlPlaneInvokeRequest) -> dict[str, Any]:
    return {
        "mode": "metadata_only",
        "workspace_id": request.context.workspace_id,
        "workspace_root": str(ROOT),
        "branch": request.params.get("branch"),
        "commit_sha": request.params.get("commit_sha"),
        "file_mutation_performed": False,
        "file_system_rollback": False,
    }


def _worktree_metadata_from_record(record: Any) -> dict[str, Any]:
    summary = getattr(record, "execution_summary", {}) or {}
    worktree = summary.get("worktree") if isinstance(summary, dict) else {}
    return {
        "mode": "metadata_only",
        "workspace_root": str(ROOT),
        "branch": worktree.get("branch") if isinstance(worktree, dict) else None,
        "commit_sha": worktree.get("commit_sha") if isinstance(worktree, dict) else None,
        "file_mutation_performed": False,
        "file_system_rollback": False,
    }


def _worktree_metadata_from_trace(summary: Any) -> dict[str, Any]:
    snapshot = getattr(summary, "snapshot", {}) or {}
    return {
        "mode": "metadata_only",
        "workspace_root": str(ROOT),
        "branch": snapshot.get("branch") if isinstance(snapshot, dict) else None,
        "commit_sha": snapshot.get("commit_sha") if isinstance(snapshot, dict) else None,
        "file_mutation_performed": False,
        "file_system_rollback": False,
    }


def _automation_metadata() -> dict[str, Any]:
    return {
        "scheduled_runs_supported": False,
        "evidence_only": True,
        "items": [],
        "mutation_performed": False,
    }


def _turn_summary_from_run(record: Any, events: list[Any]) -> dict[str, Any]:
    trace_id = getattr(record, "trace_id", "")
    return {
        "turn_id": f"{trace_id}:turn:latest",
        "thread_id": trace_id,
        "status": _status_value(getattr(record, "status", None)),
        "task": getattr(record, "task", ""),
        "created_at": _jsonable(getattr(record, "created_at", None)),
        "completed_at": _jsonable(getattr(record, "completed_at", None)),
        "event_count": len(events),
        "item_count": 2 if getattr(record, "answer", "") else 1,
        "latest_event": getattr(events[-1], "event", None) if events else None,
    }


def _turn_summary_from_trace(summary: Any, events: list[Any]) -> dict[str, Any]:
    trace_id = getattr(summary, "trace_id", "")
    return {
        "turn_id": f"{trace_id}:turn:latest",
        "thread_id": trace_id,
        "status": "completed" if getattr(summary, "event_count", 0) else "queued",
        "task": getattr(summary, "task", None),
        "created_at": _jsonable(getattr(summary, "started_at", None)),
        "completed_at": _jsonable(getattr(summary, "ended_at", None)),
        "event_count": len(events),
        "item_count": len(events),
        "latest_event": getattr(summary, "last_event", None),
    }


def _thread_items_from_run(record: Any) -> list[dict[str, Any]]:
    trace_id = getattr(record, "trace_id", "")
    items = [
        {
            "item_id": f"{trace_id}:item:task",
            "thread_id": trace_id,
            "type": "message",
            "role": "user",
            "content": getattr(record, "task", ""),
            "created_at": _jsonable(getattr(record, "created_at", None)),
        }
    ]
    answer = getattr(record, "answer", "")
    if answer:
        items.append(
            {
                "item_id": f"{trace_id}:item:answer",
                "thread_id": trace_id,
                "type": "message",
                "role": "assistant",
                "content": answer,
                "created_at": _jsonable(getattr(record, "completed_at", None)),
            }
        )
    return items


def _thread_items_from_events(trace_id: str, events: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "item_id": f"{trace_id}:item:{index + 1}",
            "thread_id": trace_id,
            "type": "event",
            "role": "system",
            "content": getattr(event, "event", "unknown"),
            "payload": _jsonable(getattr(event, "data", {})),
            "created_at": _jsonable(getattr(event, "timestamp", None)),
        }
        for index, event in enumerate(events)
    ]


def _artifact_metadata(record: Any) -> list[dict[str, Any]]:
    summary = getattr(record, "execution_summary", {}) or {}
    artifacts = summary.get("artifacts", []) if isinstance(summary, dict) else []
    if isinstance(artifacts, list):
        return [_jsonable(item) for item in artifacts if isinstance(item, dict)]
    affected_files = summary.get("affected_files", []) if isinstance(summary, dict) else []
    return [
        {"type": "file", "path": path, "mutation_performed": False}
        for path in affected_files
        if isinstance(path, str)
    ]


def _channel_event_metadata(record: Any) -> list[dict[str, Any]]:
    summary = getattr(record, "execution_summary", {}) or {}
    channel_events = summary.get("channel_events", []) if isinstance(summary, dict) else []
    if isinstance(channel_events, list):
        return [_jsonable(item) for item in channel_events if isinstance(item, dict)]
    return []


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    raw = getattr(value, "value", None)
    if raw is not None:
        return raw
    return str(value)


def _runtime_evidence_metadata(
    params: dict[str, Any],
    *,
    audit_store: AuditStore | None = None,
    principal: Principal | None = None,
) -> dict[str, Any]:
    evidence_type = params.get("evidence_type")
    if evidence_type == "sdk_dry_run_executor_stub":
        return _sdk_dry_run_executor_runtime_evidence(
            params,
            audit_store=audit_store,
            principal=principal,
        )
    if evidence_type == "sdk_write_runner_owner_acceptance":
        return _sdk_owner_acceptance_runtime_evidence(
            params,
            audit_store=audit_store,
            principal=principal,
        )
    if evidence_type == "sdk_write_runner_runtime_enablement_readiness":
        return _sdk_runtime_enablement_readiness_evidence(
            params,
            audit_store=audit_store,
            principal=principal,
        )
    if evidence_type == "sdk_write_runner_runtime_implementation_readiness_lock":
        return _sdk_runtime_implementation_readiness_lock_evidence(
            params,
            audit_store=audit_store,
            principal=principal,
        )
    report_name = params.get("report_name")
    if not isinstance(report_name, str) or not report_name:
        return {
            "report_name": None,
            "available": False,
            "report_dir": str(REPORT_DIR),
            "note": "Provide report_name to inspect one runtime evidence report.",
        }
    safe_name = report_name.replace("\\", "/").split("/")[-1]
    if safe_name != report_name or not safe_name.endswith(".json"):
        return {
            "report_name": report_name,
            "available": False,
            "error": "report_name must be a JSON filename under the runtime reports directory",
        }
    path = REPORT_DIR / safe_name
    return {
        "report_name": safe_name,
        "available": path.exists(),
        "path": str(path),
        "size_bytes": path.stat().st_size if path.exists() else None,
    }


def _sdk_dry_run_executor_runtime_evidence(
    params: dict[str, Any],
    *,
    audit_store: AuditStore | None = None,
    principal: Principal | None = None,
) -> dict[str, Any]:
    approval_id = params.get("approval_id")
    method = params.get("method")
    audit_id = params.get("audit_id")
    receipt = _sdk_dry_run_receipt_from_audit(
        audit_store,
        approval_id=approval_id if isinstance(approval_id, str) else None,
        method=method if isinstance(method, str) else None,
        audit_id=audit_id if isinstance(audit_id, str) else None,
        tenant_id=principal.tenant_id if principal else None,
    )
    safety_review = _sdk_write_runner_safety_review(receipt)
    return {
        "evidence_type": "sdk_dry_run_executor_stub",
        "available": True,
        "receipt_available": receipt is not None,
        "receipt_persisted": receipt is not None,
        "receipt": receipt,
        "approval_id": approval_id if isinstance(approval_id, str) and approval_id else None,
        "method": method if isinstance(method, str) and method else None,
        "audit_id": audit_id if isinstance(audit_id, str) and audit_id else None,
        "status_vocabulary": [
            "blocked_before_dry_run_executor",
            "dry_run_planned",
            "planned_not_executed",
        ],
        "receipt_schema": {
            "status": "dry_run_planned",
            "dry_run_executor_invoked": "boolean",
            "runner_invoked": "false",
            "agent_trace_id": "null",
            "audit_id": "string|null",
            "approval_id": "string|null",
            "method": "string",
            "operation": "string|null",
            "mark_executed": "false",
            "mutation_performed": "false",
            "network_mutation_performed": "false",
            "file_mutation_performed": "false",
            "channel_mutation_performed": "false",
        },
        "audit_readback": {
            "action": "sdk.write_runner.dry_run_planned",
            "resource_type": "sdk_write_runner",
            "control_plane_method": "runtime/evidence/read",
            "query_keys": ["approval_id", "method", "trace_id", "audit_id"],
            "receipt_persisted": receipt is not None,
        },
        "runner_safety_review": safety_review,
        "control_plane_readback": {
            "method": "runtime/evidence/read",
            "params": {
                "evidence_type": "sdk_dry_run_executor_stub",
                "approval_id": approval_id,
                "method": method,
                "audit_id": audit_id,
            },
            "endpoint": "/api/v1/control-plane/invoke",
        },
        "safety": {
            "runner_invoked": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "known_limits": [
            "This runtime evidence reads SDK dry-run executor receipts persisted in the audit log.",
            "It does not execute or replay the recorded receipt.",
            "Concrete owner-approved write execution remains disabled.",
        ],
    }


def _sdk_owner_acceptance_runtime_evidence(
    params: dict[str, Any],
    *,
    audit_store: AuditStore | None = None,
    principal: Principal | None = None,
) -> dict[str, Any]:
    approval_id = params.get("approval_id")
    owner_acceptance_id = params.get("owner_acceptance_id")
    audit_id = params.get("audit_id")
    report_name = params.get("report_name")
    safe_report_name = (
        report_name
        if isinstance(report_name, str)
        and report_name == "sdk-write-runner-owner-acceptance.json"
        else "sdk-write-runner-owner-acceptance.json"
    )
    required_query_keys = {
        "approval_id": isinstance(approval_id, str) and bool(approval_id),
        "owner_acceptance_id": isinstance(owner_acceptance_id, str) and bool(owner_acceptance_id),
        "audit_id": isinstance(audit_id, str) and bool(audit_id),
    }
    missing_required_query_keys = [
        key for key, present in required_query_keys.items() if present is not True
    ]
    report = _read_owner_acceptance_report(
        safe_report_name,
        approval_id=approval_id if isinstance(approval_id, str) else None,
        owner_acceptance_id=owner_acceptance_id if isinstance(owner_acceptance_id, str) else None,
    )
    audit_record = (
        _sdk_owner_acceptance_record_from_audit(
            audit_store,
            approval_id=approval_id if isinstance(approval_id, str) else None,
            owner_acceptance_id=owner_acceptance_id if isinstance(owner_acceptance_id, str) else None,
            audit_id=audit_id if isinstance(audit_id, str) else None,
            tenant_id=principal.tenant_id if principal else None,
        )
        if not missing_required_query_keys
        else None
    )
    record = audit_record
    validation = _sdk_owner_acceptance_evidence_validation(record if isinstance(record, dict) else None)
    record_present = validation["status"] == "valid"
    return {
        "evidence_type": "sdk_write_runner_owner_acceptance",
        "available": True,
        "evidence_status": "provided" if record_present else "required_not_provided",
        "recording_contract_ready": True,
        "readback_contract_ready": True,
        "acceptance_record_present": record_present,
        "missing_required_query_keys": missing_required_query_keys,
        "validation": validation,
        "record": record,
        "approval_id": approval_id if isinstance(approval_id, str) and approval_id else None,
        "owner_acceptance_id": owner_acceptance_id
        if isinstance(owner_acceptance_id, str) and owner_acceptance_id
        else None,
        "audit_id": audit_id if isinstance(audit_id, str) and audit_id else None,
        "report": report,
        "report_preview_only": True,
        "schema": _sdk_owner_acceptance_evidence_schema(
            [
                "owner_acceptance_id",
                "accepted_by",
                "accepted_at",
                "approval_id",
                "runbook_acknowledged",
                "rollback_plan_acknowledged",
            ]
        ),
        "audit_readback": {
            "action": "sdk.write_runner.owner_acceptance_recorded",
            "resource_type": "sdk_write_runner_owner_acceptance",
            "control_plane_method": "runtime/evidence/read",
            "query_keys": ["approval_id", "owner_acceptance_id", "audit_id"],
            "record_persisted": audit_record is not None,
        },
        "control_plane_readback": {
            "method": "runtime/evidence/read",
            "params": {
                "evidence_type": "sdk_write_runner_owner_acceptance",
                "report_name": safe_report_name,
                "approval_id": approval_id,
                "owner_acceptance_id": owner_acceptance_id,
                "audit_id": audit_id,
            },
            "endpoint": "/api/v1/control-plane/invoke",
        },
        "safety": {
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "known_limits": [
            "This readback only inspects owner acceptance evidence if it already exists.",
            "No owner acceptance evidence is recorded by runtime/evidence/read.",
            "Concrete owner-approved write execution remains disabled.",
        ],
    }


def _sdk_runtime_enablement_readiness_evidence(
    params: dict[str, Any],
    *,
    audit_store: AuditStore | None = None,
    principal: Principal | None = None,
) -> dict[str, Any]:
    readiness_receipt_id = params.get("readiness_receipt_id")
    approval_id = params.get("approval_id")
    owner_acceptance_id = params.get("owner_acceptance_id")
    audit_id = params.get("audit_id")
    report_name = params.get("report_name")
    safe_report_name = (
        report_name
        if isinstance(report_name, str)
        and report_name == "sdk-write-runner-runtime-enable-readiness.json"
        else "sdk-write-runner-runtime-enable-readiness.json"
    )
    required_query_keys = {
        "readiness_receipt_id": isinstance(readiness_receipt_id, str) and bool(readiness_receipt_id),
        "approval_id": isinstance(approval_id, str) and bool(approval_id),
        "owner_acceptance_id": isinstance(owner_acceptance_id, str) and bool(owner_acceptance_id),
        "audit_id": isinstance(audit_id, str) and bool(audit_id),
    }
    missing_required_query_keys = [
        key for key, present in required_query_keys.items() if present is not True
    ]
    report = _read_runtime_enablement_readiness_report(
        safe_report_name,
        readiness_receipt_id=readiness_receipt_id if isinstance(readiness_receipt_id, str) else None,
        approval_id=approval_id if isinstance(approval_id, str) else None,
        owner_acceptance_id=owner_acceptance_id if isinstance(owner_acceptance_id, str) else None,
    )
    audit_record = (
        _sdk_runtime_enablement_readiness_record_from_audit(
            audit_store,
            readiness_receipt_id=readiness_receipt_id if isinstance(readiness_receipt_id, str) else None,
            approval_id=approval_id if isinstance(approval_id, str) else None,
            owner_acceptance_id=owner_acceptance_id if isinstance(owner_acceptance_id, str) else None,
            audit_id=audit_id if isinstance(audit_id, str) else None,
            tenant_id=principal.tenant_id if principal else None,
        )
        if not missing_required_query_keys
        else None
    )
    record = audit_record
    validation = _sdk_runtime_enablement_receipt_validation(record if isinstance(record, dict) else None)
    record_present = validation["status"] == "valid"
    return {
        "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
        "available": True,
        "evidence_status": "provided" if record_present else "required_not_provided",
        "recording_contract_ready": True,
        "readback_contract_ready": True,
        "readiness_receipt_present": record_present,
        "missing_required_query_keys": missing_required_query_keys,
        "validation": validation,
        "record": record,
        "readiness_receipt_id": readiness_receipt_id
        if isinstance(readiness_receipt_id, str) and readiness_receipt_id
        else None,
        "approval_id": approval_id if isinstance(approval_id, str) and approval_id else None,
        "owner_acceptance_id": owner_acceptance_id
        if isinstance(owner_acceptance_id, str) and owner_acceptance_id
        else None,
        "audit_id": audit_id if isinstance(audit_id, str) and audit_id else None,
        "report": report,
        "report_preview_only": True,
        "schema": _sdk_runtime_enablement_receipt_schema(
            [
                "readiness_receipt_id",
                "approval_id",
                "owner_acceptance_id",
                "owner_acceptance_audit_id",
                "runtime_flag_name",
                "smoke_runbook_version",
                "rollback_runbook_version",
                "accepted_by",
                "accepted_at",
                "expires_at",
                "smoke_runbook_acknowledged",
                "rollback_runbook_acknowledged",
                "failure_receipt_reviewed",
            ]
        ),
        "audit_readback": {
            "action": "sdk.write_runner.runtime_enablement_receipt_recorded",
            "resource_type": "sdk_write_runner_runtime_enablement_readiness",
            "control_plane_method": "runtime/evidence/read",
            "query_keys": ["readiness_receipt_id", "approval_id", "owner_acceptance_id", "audit_id"],
            "record_persisted": audit_record is not None,
        },
        "control_plane_readback": {
            "method": "runtime/evidence/read",
            "params": {
                "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
                "report_name": safe_report_name,
                "readiness_receipt_id": readiness_receipt_id,
                "approval_id": approval_id,
                "owner_acceptance_id": owner_acceptance_id,
                "audit_id": audit_id,
            },
            "endpoint": "/api/v1/control-plane/invoke",
        },
        "safety": {
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "known_limits": [
            "This readback only inspects runtime enablement readiness receipts if they already exist.",
            "No readiness receipt is recorded by runtime/evidence/read.",
            "Concrete owner-approved write execution remains disabled.",
        ],
    }


def _sdk_runtime_implementation_readiness_lock_schema(required_fields: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": required_fields,
        "properties": {
            "implementation_lock_id": "string",
            "idempotency_key": "string",
            "idempotency_hash": "string",
            "approval_id": "string",
            "readiness_receipt_id": "string",
            "readiness_receipt_audit_id": "string",
            "owner_pack_decision_id": "string",
            "owner_pack_decision_audit_id": "string",
            "operator_id": "string",
            "locked_at": "RFC3339 timestamp",
            "lock_reason": "string",
            "lock_signature": "string optional",
            "lock_hash": "string optional",
            "notes": "string optional",
        },
        "safety_invariants": {
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }


def _sdk_runtime_implementation_readiness_lock_evidence(
    params: dict[str, Any],
    *,
    audit_store: AuditStore | None = None,
    principal: Principal | None = None,
) -> dict[str, Any]:
    implementation_lock_id = params.get("implementation_lock_id")
    approval_id = params.get("approval_id")
    readiness_receipt_id = params.get("readiness_receipt_id")
    owner_pack_decision_id = params.get("owner_pack_decision_id")
    audit_id = params.get("audit_id")
    report_name = params.get("report_name")
    safe_report_name = (
        report_name
        if isinstance(report_name, str)
        and report_name == "sdk-write-runner-runtime-implementation-readiness-lock.json"
        else "sdk-write-runner-runtime-implementation-readiness-lock.json"
    )
    required_query_keys = {
        "implementation_lock_id": isinstance(implementation_lock_id, str) and bool(implementation_lock_id),
        "approval_id": isinstance(approval_id, str) and bool(approval_id),
        "readiness_receipt_id": isinstance(readiness_receipt_id, str) and bool(readiness_receipt_id),
        "owner_pack_decision_id": isinstance(owner_pack_decision_id, str) and bool(owner_pack_decision_id),
        "audit_id": isinstance(audit_id, str) and bool(audit_id),
    }
    missing_required_query_keys = [
        key for key, present in required_query_keys.items() if present is not True
    ]
    audit_record = (
        _sdk_runtime_implementation_readiness_lock_record_from_audit(
            audit_store,
            implementation_lock_id=implementation_lock_id if isinstance(implementation_lock_id, str) else None,
            approval_id=approval_id if isinstance(approval_id, str) else None,
            readiness_receipt_id=readiness_receipt_id if isinstance(readiness_receipt_id, str) else None,
            owner_pack_decision_id=owner_pack_decision_id if isinstance(owner_pack_decision_id, str) else None,
            audit_id=audit_id if isinstance(audit_id, str) else None,
            tenant_id=principal.tenant_id if principal else None,
        )
        if not missing_required_query_keys
        else None
    )
    validation = _sdk_runtime_implementation_readiness_lock_validation(
        audit_record if isinstance(audit_record, dict) else None
    )
    record_present = validation["status"] == "valid"
    return {
        "evidence_type": "sdk_write_runner_runtime_implementation_readiness_lock",
        "available": True,
        "evidence_status": "provided" if record_present else "required_not_provided",
        "recording_contract_ready": True,
        "readback_contract_ready": True,
        "implementation_lock_present": record_present,
        "missing_required_query_keys": missing_required_query_keys,
        "validation": validation,
        "record": audit_record,
        "implementation_lock_id": implementation_lock_id
        if isinstance(implementation_lock_id, str) and implementation_lock_id
        else None,
        "approval_id": approval_id if isinstance(approval_id, str) and approval_id else None,
        "readiness_receipt_id": readiness_receipt_id
        if isinstance(readiness_receipt_id, str) and readiness_receipt_id
        else None,
        "owner_pack_decision_id": owner_pack_decision_id
        if isinstance(owner_pack_decision_id, str) and owner_pack_decision_id
        else None,
        "audit_id": audit_id if isinstance(audit_id, str) and audit_id else None,
        "report_preview_only": True,
        "schema": _sdk_runtime_implementation_readiness_lock_schema(
            [
                "implementation_lock_id",
                "idempotency_key",
                "idempotency_hash",
                "approval_id",
                "readiness_receipt_id",
                "readiness_receipt_audit_id",
                "owner_pack_decision_id",
                "owner_pack_decision_audit_id",
                "operator_id",
                "locked_at",
                "lock_reason",
            ]
        ),
        "audit_readback": {
            "action": "sdk.write_runner.runtime_implementation_readiness_lock_recorded",
            "resource_type": "sdk_write_runner_runtime_implementation_readiness_lock",
            "control_plane_method": "runtime/evidence/read",
            "query_keys": [
                "implementation_lock_id",
                "approval_id",
                "readiness_receipt_id",
                "owner_pack_decision_id",
                "audit_id",
            ],
            "record_persisted": audit_record is not None,
        },
        "control_plane_readback": {
            "method": "runtime/evidence/read",
            "params": {
                "evidence_type": "sdk_write_runner_runtime_implementation_readiness_lock",
                "report_name": safe_report_name,
                "implementation_lock_id": implementation_lock_id,
                "approval_id": approval_id,
                "readiness_receipt_id": readiness_receipt_id,
                "owner_pack_decision_id": owner_pack_decision_id,
                "audit_id": audit_id,
            },
            "endpoint": "/api/v1/control-plane/invoke",
        },
        "safety": {
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "known_limits": [
            "This readback only inspects runtime implementation readiness locks if they already exist.",
            "No readiness lock is recorded by runtime/evidence/read.",
            "Concrete owner-approved write execution remains disabled.",
        ],
    }


def _sdk_write_runner_safety_review(receipt: dict[str, Any] | None) -> dict[str, Any]:
    checks = {
        "receipt_available": receipt is not None,
        "receipt_persisted": bool(receipt and receipt.get("receipt_persisted") is True),
        "status_dry_run_planned": bool(receipt and receipt.get("status") == "dry_run_planned"),
        "audit_signature_present": bool(receipt and receipt.get("audit_signature_present") is True),
        "audit_hash_present": bool(receipt and isinstance(receipt.get("audit_hash"), str) and receipt.get("audit_hash")),
        "runner_not_invoked": bool(receipt and receipt.get("runner_invoked") is False),
        "agent_trace_absent": bool(receipt and receipt.get("agent_trace_id") is None),
        "mark_executed_false": bool(receipt and receipt.get("mark_executed") is False),
        "mutation_false": bool(receipt and receipt.get("mutation_performed") is False),
        "network_mutation_false": bool(receipt and receipt.get("network_mutation_performed") is False),
        "file_mutation_false": bool(receipt and receipt.get("file_mutation_performed") is False),
        "channel_mutation_false": bool(receipt and receipt.get("channel_mutation_performed") is False),
    }
    passed = all(checks.values())
    return {
        "stage": "persisted_dry_run_receipt_safety_review",
        "status": "passed" if passed else "action_required",
        "checks": checks,
        "write_runner_enabled": False,
        "adapter_execution_enabled": False,
        "agent_execution_enabled": False,
        "mark_executed": False,
        "mutation_performed": False,
        "next_gate": "owner_approved_write_runner_implementation_review",
        "known_limits": [
            "Passing this review only proves the dry-run receipt is safe to inspect.",
            "It does not enable or invoke the owner-approved write runner.",
        ],
    }


def _sdk_dry_run_receipt_from_audit(
    audit_store: AuditStore | None,
    *,
    approval_id: str | None,
    method: str | None,
    audit_id: str | None,
    tenant_id: str | None,
) -> dict[str, Any] | None:
    if audit_store is None:
        return None
    records = audit_store.list(
        limit=200,
        tenant_id=tenant_id,
        action="sdk.write_runner.dry_run_planned",
        resource_type="sdk_write_runner",
        outcome="planned",
    )
    for record in records:
        if audit_id and getattr(record, "id", None) != audit_id:
            continue
        if method and getattr(record, "resource_id", None) != method:
            continue
        details = getattr(record, "details", {}) or {}
        if approval_id and details.get("approval_id") != approval_id:
            continue
        receipt = details.get("receipt")
        if not isinstance(receipt, dict):
            continue
        return {
            **_jsonable(receipt),
            "audit_id": getattr(record, "id", receipt.get("audit_id")),
            "audit_created_at": _jsonable(getattr(record, "created_at", None)),
            "audit_hash": getattr(record, "hash", None),
            "audit_signature_present": bool(getattr(record, "signature", None)),
            "receipt_persisted": details.get("receipt_persisted") is True,
        }
    return None


def _read_owner_acceptance_report(
    report_name: str,
    *,
    approval_id: str | None,
    owner_acceptance_id: str | None,
) -> dict[str, Any]:
    path = REPORT_DIR / report_name
    if not path.exists():
        return {
            "report_name": report_name,
            "available": False,
            "path": str(path),
            "record": None,
        }
    try:
        payload = _jsonable(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        return {
            "report_name": report_name,
            "available": False,
            "path": str(path),
            "error": str(exc),
            "record": None,
        }
    record = payload if isinstance(payload, dict) else None
    if record and approval_id and record.get("approval_id") != approval_id:
        record = None
    if record and owner_acceptance_id and record.get("owner_acceptance_id") != owner_acceptance_id:
        record = None
    return {
        "report_name": report_name,
        "available": True,
        "path": str(path),
        "record": record,
    }


def _sdk_owner_acceptance_record_from_audit(
    audit_store: AuditStore | None,
    *,
    approval_id: str | None,
    owner_acceptance_id: str | None,
    audit_id: str | None,
    tenant_id: str | None,
) -> dict[str, Any] | None:
    if audit_store is None or not approval_id or not owner_acceptance_id or not audit_id:
        return None
    records = audit_store.list(
        limit=200,
        tenant_id=tenant_id,
        action="sdk.write_runner.owner_acceptance_recorded",
        resource_type="sdk_write_runner_owner_acceptance",
        outcome="accepted",
    )
    for record in records:
        if audit_id and getattr(record, "id", None) != audit_id:
            continue
        if owner_acceptance_id and getattr(record, "resource_id", None) != owner_acceptance_id:
            continue
        details = getattr(record, "details", {}) or {}
        if approval_id and details.get("approval_id") != approval_id:
            continue
        evidence = details.get("owner_acceptance_evidence")
        if not isinstance(evidence, dict):
            continue
        return {
            **_jsonable(evidence),
            "audit_id": getattr(record, "id", audit_id),
            "audit_created_at": _jsonable(getattr(record, "created_at", None)),
            "audit_hash": getattr(record, "hash", None),
            "audit_signature_present": bool(getattr(record, "signature", None)),
            "record_persisted": True,
        }
    return None


def _read_runtime_enablement_readiness_report(
    report_name: str,
    *,
    readiness_receipt_id: str | None,
    approval_id: str | None,
    owner_acceptance_id: str | None,
) -> dict[str, Any]:
    path = REPORT_DIR / report_name
    if not path.exists():
        return {
            "report_name": report_name,
            "available": False,
            "path": str(path),
            "record": None,
        }
    try:
        payload = _jsonable(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        return {
            "report_name": report_name,
            "available": False,
            "path": str(path),
            "error": str(exc),
            "record": None,
        }
    record = payload if isinstance(payload, dict) else None
    if record and readiness_receipt_id and record.get("readiness_receipt_id") != readiness_receipt_id:
        record = None
    if record and approval_id and record.get("approval_id") != approval_id:
        record = None
    if record and owner_acceptance_id and record.get("owner_acceptance_id") != owner_acceptance_id:
        record = None
    return {
        "report_name": report_name,
        "available": True,
        "path": str(path),
        "record": record,
    }


def _sdk_runtime_enablement_readiness_record_from_audit(
    audit_store: AuditStore | None,
    *,
    readiness_receipt_id: str | None,
    approval_id: str | None,
    owner_acceptance_id: str | None,
    audit_id: str | None,
    tenant_id: str | None,
) -> dict[str, Any] | None:
    if audit_store is None or not readiness_receipt_id or not approval_id or not audit_id:
        return None
    records = audit_store.list(
        limit=200,
        tenant_id=tenant_id,
        action="sdk.write_runner.runtime_enablement_receipt_recorded",
        resource_type="sdk_write_runner_runtime_enablement_readiness",
        outcome="accepted",
    )
    for record in records:
        if audit_id and getattr(record, "id", None) != audit_id:
            continue
        if readiness_receipt_id and getattr(record, "resource_id", None) != readiness_receipt_id:
            continue
        details = getattr(record, "details", {}) or {}
        if approval_id and details.get("approval_id") != approval_id:
            continue
        if owner_acceptance_id and details.get("owner_acceptance_id") != owner_acceptance_id:
            continue
        receipt = details.get("runtime_enablement_receipt")
        if not isinstance(receipt, dict):
            continue
        return {
            **_jsonable(receipt),
            "audit_id": getattr(record, "id", audit_id),
            "audit_created_at": _jsonable(getattr(record, "created_at", None)),
            "audit_hash": getattr(record, "hash", None),
            "audit_signature_present": bool(getattr(record, "signature", None)),
            "record_persisted": True,
        }
    return None


def _sdk_runtime_enablement_owner_pack_decision_record_from_audit(
    audit_store: AuditStore | None,
    *,
    owner_pack_decision_id: str | None,
    approval_id: str | None,
    readiness_receipt_id: str | None,
    audit_id: str | None,
    tenant_id: str | None,
) -> dict[str, Any] | None:
    if audit_store is None or not owner_pack_decision_id or not approval_id or not readiness_receipt_id or not audit_id:
        return None
    records = audit_store.list(
        limit=200,
        tenant_id=tenant_id,
        action="sdk.write_runner.runtime_enablement_owner_pack_decision_recorded",
        resource_type="sdk_write_runner_runtime_enablement_owner_review_pack",
        outcome="accepted",
    )
    for record in records:
        if audit_id and getattr(record, "id", None) != audit_id:
            continue
        if owner_pack_decision_id and getattr(record, "resource_id", None) != owner_pack_decision_id:
            continue
        details = getattr(record, "details", {}) or {}
        if approval_id and details.get("approval_id") != approval_id:
            continue
        if readiness_receipt_id and details.get("readiness_receipt_id") != readiness_receipt_id:
            continue
        decision = details.get("owner_pack_decision")
        if not isinstance(decision, dict):
            continue
        return {
            **_jsonable(decision),
            "audit_id": getattr(record, "id", audit_id),
            "audit_created_at": _jsonable(getattr(record, "created_at", None)),
            "audit_hash": getattr(record, "hash", None),
            "audit_signature_present": bool(getattr(record, "signature", None)),
            "record_persisted": True,
        }
    return None


def _sdk_runtime_implementation_readiness_lock_record_from_audit(
    audit_store: AuditStore | None,
    *,
    implementation_lock_id: str | None,
    approval_id: str | None,
    readiness_receipt_id: str | None,
    owner_pack_decision_id: str | None,
    audit_id: str | None,
    tenant_id: str | None,
) -> dict[str, Any] | None:
    if (
        audit_store is None
        or not implementation_lock_id
        or not approval_id
        or not readiness_receipt_id
        or not owner_pack_decision_id
        or not audit_id
    ):
        return None
    records = audit_store.list(
        limit=200,
        tenant_id=tenant_id,
        action="sdk.write_runner.runtime_implementation_readiness_lock_recorded",
        resource_type="sdk_write_runner_runtime_implementation_readiness_lock",
        outcome="accepted",
    )
    for record in records:
        if audit_id and getattr(record, "id", None) != audit_id:
            continue
        if implementation_lock_id and getattr(record, "resource_id", None) != implementation_lock_id:
            continue
        details = getattr(record, "details", {}) or {}
        if approval_id and details.get("approval_id") != approval_id:
            continue
        if readiness_receipt_id and details.get("readiness_receipt_id") != readiness_receipt_id:
            continue
        if owner_pack_decision_id and details.get("owner_pack_decision_id") != owner_pack_decision_id:
            continue
        readiness_lock = details.get("readiness_lock")
        if not isinstance(readiness_lock, dict):
            continue
        return {
            **_jsonable(readiness_lock),
            "audit_id": getattr(record, "id", audit_id),
            "audit_created_at": _jsonable(getattr(record, "created_at", None)),
            "audit_hash": getattr(record, "hash", None),
            "audit_signature_present": bool(getattr(record, "signature", None)),
            "record_persisted": True,
        }
    return None


def _sdk_runtime_implementation_final_decision_record_from_audit(
    audit_store: AuditStore | None,
    *,
    final_decision_id: str | None,
    approval_id: str | None,
    implementation_lock_id: str | None,
    readiness_receipt_id: str | None,
    audit_id: str | None,
    tenant_id: str | None,
) -> dict[str, Any] | None:
    if (
        audit_store is None
        or not final_decision_id
        or not approval_id
        or not implementation_lock_id
        or not readiness_receipt_id
        or not audit_id
    ):
        return None
    records = audit_store.list(
        limit=200,
        tenant_id=tenant_id,
        action="sdk.write_runner.runtime_implementation_final_decision_recorded",
        resource_type="sdk_write_runner_runtime_implementation_final_decision",
        outcome="accepted",
    )
    for record in records:
        if audit_id and getattr(record, "id", None) != audit_id:
            continue
        if final_decision_id and getattr(record, "resource_id", None) != final_decision_id:
            continue
        details = getattr(record, "details", {}) or {}
        if approval_id and details.get("approval_id") != approval_id:
            continue
        if implementation_lock_id and details.get("implementation_lock_id") != implementation_lock_id:
            continue
        if readiness_receipt_id and details.get("readiness_receipt_id") != readiness_receipt_id:
            continue
        final_decision = details.get("final_decision")
        if not isinstance(final_decision, dict):
            continue
        return {
            **_jsonable(final_decision),
            "audit_id": getattr(record, "id", audit_id),
            "audit_created_at": _jsonable(getattr(record, "created_at", None)),
            "audit_hash": getattr(record, "hash", None),
            "audit_signature_present": bool(getattr(record, "signature", None)),
            "record_persisted": True,
        }
    return None


def _audit(
    audit_store: AuditStore,
    principal: Principal,
    *,
    request: ControlPlaneInvokeRequest,
    trace_id: str,
    outcome: str,
    details: dict[str, Any],
):
    return audit_store.record(
        action="control_plane.invoke",
        resource_type="control_plane_method",
        resource_id=request.method,
        outcome=outcome,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        trace_id=trace_id,
        details={
            "request_id": request.id,
            "method": request.method,
            **details,
        },
    )


def _find_secret_paths(value: Any, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if _is_secret_key(key_text):
                if not _is_safe_secret_reference(item):
                    paths.append(child_path)
                continue
            paths.extend(_find_secret_paths(item, child_path))
        return paths
    if isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_find_secret_paths(item, f"{path}[{index}]"))
        return paths
    if isinstance(value, str) and _looks_like_raw_secret(value):
        return [path]
    return []


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in SECRET_KEY_FRAGMENTS)


def _is_safe_secret_reference(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return stripped in SAFE_SECRET_VALUES or stripped.startswith(SAFE_SECRET_PREFIXES)
    if isinstance(value, dict):
        reference_keys = {"secret_ref", "credential_ref", "vault_ref", "env_var"}
        return bool(reference_keys.intersection(value)) and not _find_secret_paths(value)
    return False


def _looks_like_raw_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)
