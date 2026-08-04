from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.api.recovery_helpers import build_recovery_context, build_recovery_payload
from backend.app.core.agent import AgentLoop
from backend.app.core.approvals import (
    ApprovalDecisionRequest,
    ApprovalRequestRecord,
    ApprovalStatus,
    ApprovalStore,
)
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import ErrorCode, RunContext, ToolCallRecord
from backend.app.core.security import Principal
from backend.app.dependencies import (
    enforce_scope,
    get_agent,
    get_approval_store,
    get_audit_store,
    get_current_principal,
)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])
ApprovalStoreDependency = Annotated[ApprovalStore, Depends(get_approval_store)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
AgentDependency = Annotated[AgentLoop, Depends(get_agent)]


def _enforce_approval_tenant_scope(principal: Principal, tenant_id: str | None) -> str | None:
    """强制审批列表查询的租户边界（P0-06 残留修复，与 audit 同模式）。

    非 admin 角色只能访问本租户审批记录：
    - 显式传入与本租户不符的 tenant_id，视为越权尝试，返回 403；
    - 未传入时强制收敛到本租户（store 层 tenant_id=None 不过滤，必须在此兜底）。
    admin 可指定任意租户过滤，或不指定（跨租户全量）。
    """
    if principal.role == "admin":
        return tenant_id
    if tenant_id is not None and tenant_id != principal.tenant_id:
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "Access denied: cannot list approvals of another tenant.",
        )
    return principal.tenant_id


@router.get("", response_model=list[ApprovalRequestRecord])
async def list_approvals(
    approval_store: ApprovalStoreDependency,
    principal: PrincipalDependency,
    limit: int = Query(default=50, ge=1, le=200),
    status: ApprovalStatus | None = None,
    tenant_id: str | None = None,
) -> list[ApprovalRequestRecord]:
    enforce_scope(principal, "workflow:control")
    return approval_store.list(
        limit=limit,
        status=status,
        tenant_id=_enforce_approval_tenant_scope(principal, tenant_id),
    )


@router.get("/{approval_id}", response_model=ApprovalRequestRecord)
async def get_approval(
    approval_id: str,
    approval_store: ApprovalStoreDependency,
    principal: PrincipalDependency,
) -> ApprovalRequestRecord:
    enforce_scope(principal, "workflow:control")
    record = approval_store.get(approval_id)
    if record is None:
        raise api_error(404, ErrorCode.AUTHORIZATION_FAILED, "Approval request not found.")
    # P0-06 残留修复：按 ID 读取同样强制租户边界（admin 除外，与 list 口径一致）
    if principal.authenticated and principal.role != "admin" and principal.tenant_id != record.tenant_id:
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Approval tenant mismatch.")
    return record


@router.get("/{approval_id}/correlation", response_model=dict[str, object])
async def get_approval_correlation(
    approval_id: str,
    approval_store: ApprovalStoreDependency,
    principal: PrincipalDependency,
) -> dict[str, object]:
    enforce_scope(principal, "workflow:control")
    record = approval_store.get(approval_id)
    if record is None:
        raise api_error(404, ErrorCode.AUTHORIZATION_FAILED, "Approval request not found.")
    trace_id = record.execution_trace_id or record.trace_id
    recovery = build_recovery_context(
        status=record.status.value,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        pending_count=1 if record.status == ApprovalStatus.PENDING else 0,
        latest_decision=record.status.value,
        next_actions=[
            "approve request" if record.status == ApprovalStatus.PENDING else "review approval outcome",
            "execute approved tool" if record.status == ApprovalStatus.APPROVED else "continue workflow after decision",
        ],
        retryable=record.status == ApprovalStatus.PENDING,
        confidence=0.9 if record.status == ApprovalStatus.APPROVED else 0.6,
        tool_name="approve_request" if record.status == ApprovalStatus.PENDING else ("execute_approved_request" if record.status == ApprovalStatus.APPROVED else "review_approval"),
        follow_up=["audit approval state", "continue workflow after decision"],
        status_detail=f"approval {record.status.value}",
        remediation="approve, execute, or review according to approval state",
    )
    return {
        "approval_id": record.id,
        "trace_id": trace_id,
        "resource_type": "approval",
        "resource_id": record.id,
        "status": record.status.value,
        "approval_action": record.action,
        "recovery": build_recovery_payload(
        status=record.status.value,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        pending_count=1 if record.status == ApprovalStatus.PENDING else 0,
        latest_decision=record.status.value,
        next_actions=[
            "approve request" if record.status == ApprovalStatus.PENDING else "review approval outcome",
            "execute approved tool" if record.status == ApprovalStatus.APPROVED else "continue workflow after decision",
        ],
        retryable=record.status == ApprovalStatus.PENDING,
        confidence=0.9 if record.status == ApprovalStatus.APPROVED else 0.6,
        tool_name="approve_request" if record.status == ApprovalStatus.PENDING else ("execute_approved_request" if record.status == ApprovalStatus.APPROVED else "review_approval"),
        follow_up=["audit approval state", "continue workflow after decision"],
        status_detail=f"approval {record.status.value}",
        remediation="approve, execute, or review according to approval state",
    ),
        "trace_summary": {
            "trace_id": trace_id,
            "event_count": 1,
            "started_at": record.created_at,
            "ended_at": record.executed_at or record.decided_at or record.created_at,
            "last_event": f"approval.{record.status.value}",
            "task": record.action,
            "snapshot": {
                "resource_type": "approval",
                "resource_id": record.id,
                "trace_id": trace_id,
                "status": record.status.value,
                "approval_action": record.action,
                "risk_level": record.risk_level.value,
                "recovery": recovery.model_dump(mode="json"),
            },
        },
        "snapshot": {
            "approval_id": record.id,
            "resource_type": "approval",
            "resource_id": record.id,
            "trace_id": trace_id,
            "status": record.status.value,
            "approval_action": record.action,
            "risk_level": record.risk_level.value,
            "recovery": recovery.model_dump(mode="json"),
        },
    }


@router.post("/{approval_id}/approve", response_model=ApprovalRequestRecord)
async def approve_request(
    approval_id: str,
    decision: ApprovalDecisionRequest,
    approval_store: ApprovalStoreDependency,
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
) -> ApprovalRequestRecord:
    enforce_scope(principal, "workflow:control")
    _check_decision_authorization(approval_store, approval_id, principal)
    decision = _bind_decision_to_principal(decision, principal)
    record = approval_store.approve(approval_id, decision)
    if record is None:
        raise api_error(404, ErrorCode.AUTHORIZATION_FAILED, "Approval request not found.")
    _audit_decision(audit_store, "approval.approve", record)
    return record


@router.post("/{approval_id}/reject", response_model=ApprovalRequestRecord)
async def reject_request(
    approval_id: str,
    decision: ApprovalDecisionRequest,
    approval_store: ApprovalStoreDependency,
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
) -> ApprovalRequestRecord:
    enforce_scope(principal, "workflow:control")
    _check_decision_authorization(approval_store, approval_id, principal)
    decision = _bind_decision_to_principal(decision, principal)
    record = approval_store.reject(approval_id, decision)
    if record is None:
        raise api_error(404, ErrorCode.AUTHORIZATION_FAILED, "Approval request not found.")
    _audit_decision(audit_store, "approval.reject", record)
    return record


def _bind_decision_to_principal(
    decision: ApprovalDecisionRequest,
    principal: Principal,
) -> ApprovalDecisionRequest:
    """P0-07: decided_by 绝不接受请求体传入，强制绑定为已认证 principal 的身份。

    请求体中的 decided_by 字段一律忽略并覆盖，防止审批人身份伪造。
    """
    return decision.model_copy(update={"decided_by": principal.user_id})


def _check_decision_authorization(
    approval_store: ApprovalStore,
    approval_id: str,
    principal: Principal,
) -> None:
    """P0-07: 审批决定（approve/reject）前的授权校验。

    - 记录必须存在（404）；
    - tenant_id 必须与已认证 principal 一致（403，防跨租户审批）；
    - 职责分离（SoD）：审批请求的 actor 不得与审批人相同（403，防自审自批）。
    """
    record = approval_store.get(approval_id)
    if record is None:
        raise api_error(404, ErrorCode.AUTHORIZATION_FAILED, "Approval request not found.")
    if principal.authenticated and principal.tenant_id != record.tenant_id:
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Approval tenant mismatch.")
    if record.actor_id == principal.user_id:
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "Separation of duties violation: requester cannot decide their own approval request.",
        )


@router.post("/{approval_id}/execute", response_model=ToolCallRecord)
async def execute_approved_request(
    approval_id: str,
    approval_store: ApprovalStoreDependency,
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    agent: AgentDependency,
) -> ToolCallRecord:
    enforce_scope(principal, "workflow:control")
    record = approval_store.get(approval_id)
    if record is None:
        raise api_error(404, ErrorCode.AUTHORIZATION_FAILED, "Approval request not found.")
    if principal.authenticated and principal.tenant_id != record.tenant_id:
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Approval tenant mismatch.")

    context = RunContext(
        tenant_id=record.tenant_id,
        user_id=principal.user_id if principal.authenticated else record.decided_by or "anonymous",
        permission_scope=["tools:*"],
        trace_id=record.trace_id,
        request_id=record.id,
    )
    tool_call = await agent.tools.execute_approved(context, approval_id)
    approval_store.mark_executed(
        approval_id,
        executed_by=context.user_id,
        execution_trace_id=context.trace_id,
        linked_policy_trace_id=record.linked_policy_trace_id,
    )
    _audit_execution(audit_store, record, context, tool_call)
    return tool_call


def _audit_decision(audit_store: AuditStore, action: str, record: ApprovalRequestRecord) -> None:
    audit_store.record(
        action=action,
        resource_type="approval",
        resource_id=record.id,
        outcome=record.status.value,
        tenant_id=record.tenant_id,
        actor_id=record.decided_by or "anonymous",
        trace_id=record.trace_id,
        details={
            "approval_action": record.action,
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "risk_level": record.risk_level.value,
            "linked_policy_trace_id": record.linked_policy_trace_id,
        },
    )


def _audit_execution(
    audit_store: AuditStore,
    record: ApprovalRequestRecord,
    context: RunContext,
    tool_call: ToolCallRecord,
) -> None:
    audit_store.record(
        action="approval.execute",
        resource_type="approval",
        resource_id=record.id,
        outcome="success" if tool_call.success else "failed",
        tenant_id=record.tenant_id,
        actor_id=context.user_id,
        trace_id=context.trace_id,
        details={
            "approval_action": record.action,
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "risk_level": record.risk_level.value,
            "tool_success": tool_call.success,
            "tool_error": tool_call.error,
        },
    )
