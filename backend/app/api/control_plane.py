from __future__ import annotations

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
    return SDKControlPlaneInvokeResponse(
        id=control_request.id,
        ok=control_response.ok,
        status=sdk_metadata["status"],
        sdk=sdk_metadata,
        control_plane=control_response,
        evidence=control_response.evidence,
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
        "status": "sdk_dry_run_receipt_persistence_ready",
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
    return {
        "available": True,
        "stub_stage": "owner_approved_write_dry_run_executor",
        "audit_event_recorded": True,
        "audit_action": "sdk.write_runner.dry_run_planned",
        "audit_id": audit.id,
        "receipt_persisted": True,
        "receipt_readback_method": "runtime/evidence/read",
        "receipt": receipt,
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
