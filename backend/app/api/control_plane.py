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
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_audit_store, get_current_principal

router = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]

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
    workspace_id: str | None = None
    trace_id: str | None = None


class ControlPlaneInvokeRequest(BaseModel):
    id: str = Field(default_factory=lambda: f"req_{uuid4().hex}")
    method: str = Field(..., min_length=1, max_length=160)
    params: dict[str, Any] = Field(default_factory=dict)
    context: ControlPlaneContext = Field(default_factory=ControlPlaneContext)


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
        result = _contract_result(spec, request)
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
    audit = _audit(
        audit_store,
        principal,
        request=request,
        trace_id=trace_id,
        outcome="blocked",
        details={
            "method": spec.method,
            "group": spec.group,
            "requires_approval": spec.requires_approval,
            "implementation_state": spec.implementation_state,
            "mutation_performed": False,
        },
    )
    return ControlPlaneInvokeResponse(
        id=request.id,
        ok=False,
        error=ControlPlaneError(
            code=error_code,
            message=message,
            retryable=True,
            details={
                "method": spec.method,
                "group": spec.group,
                "operation_kind": spec.operation_kind,
                "requires_approval": spec.requires_approval,
                "mutation_performed": False,
            },
        ),
        evidence=ControlPlaneEvidence(trace_id=trace_id, audit_id=audit.id),
    )


def _contract_result(spec: ControlPlaneMethodSpec, request: ControlPlaneInvokeRequest) -> dict[str, Any]:
    result: dict[str, Any] = {
        **spec.to_payload(),
        "contract": {
            "id": request.id,
            "method": request.method,
            "status_vocabulary": list(STATUS_VOCABULARY),
            "mutation_performed": False,
            "adapter_execution_enabled": False,
        },
        "compatibility": {
            "thread_id": request.params.get("thread_id") or request.params.get("trace_id"),
            "turn_id": request.params.get("turn_id"),
            "item_id": request.params.get("item_id"),
            "trace_id": request.context.trace_id or request.params.get("trace_id"),
            "workspace_id": request.context.workspace_id,
        },
    }
    if spec.method == "runtime/evidence/read":
        result["evidence"] = _runtime_evidence_metadata(request.params)
    return result


def _runtime_evidence_metadata(params: dict[str, Any]) -> dict[str, Any]:
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
