from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from backend.app.api.errors import api_error
from backend.app.api.linked_summary import build_linked_summary
from backend.app.api.pagination import apply_pagination
from backend.app.core.audit import AuditChainVerification, AuditStore
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_audit_store, get_current_principal

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def _enforce_audit_tenant_scope(principal: Principal, tenant_id: str | None) -> str | None:
    """强制审计查询的租户边界。

    非 admin 角色（含 viewer）只能访问本租户的审计数据：
    - 显式传入与本租户不符的 tenant_id，视为越权尝试，返回 403；
    - 未传入时强制收敛到本租户。
    admin 可指定任意租户过滤，或不指定（跨租户全量）。
    """
    if principal.role == "admin":
        return tenant_id
    if tenant_id is not None and tenant_id != principal.tenant_id:
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "Access denied: cannot access audit logs of another tenant.",
        )
    return principal.tenant_id


@router.get("", response_model=dict[str, object])
async def list_audit_logs(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: str | None = None,
    trace_id: str | None = None,
    run_id: str | None = None,
    workflow_id: str | None = None,
    has_snapshot: bool | None = None,
) -> dict[str, object]:
    """List audit logs with filtering and pagination.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        limit: Number of items per page
        offset: Number of items to skip
        tenant_id: Filter by tenant
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome
        trace_id: Filter by trace ID
        run_id: Filter by run ID
        workflow_id: Filter by workflow ID
        has_snapshot: Filter by snapshot presence

    Returns:
        Paginated audit logs
    """
    enforce_scope(principal, "audit:read")
    tenant_id = _enforce_audit_tenant_scope(principal, tenant_id)
    records = audit_store.list(
        limit=10000,
        offset=0,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
    )
    filtered = [
        record
        for record in records
        if (trace_id is None or record.trace_id == trace_id)
        and (run_id is None or record.run_id == run_id)
        and (workflow_id is None or record.workflow_id == workflow_id)
        and (has_snapshot is None or bool(record.snapshot) == has_snapshot)
    ]

    # Apply pagination
    paginated, metadata = apply_pagination(filtered, limit, offset)

    return {
        "data": [record.model_dump(mode="json") for record in paginated],
        "pagination": metadata.model_dump(),
    }


@router.get("/verify", response_model=AuditChainVerification)
async def verify_audit_chain(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
) -> AuditChainVerification:
    enforce_scope(principal, "audit:read")
    return audit_store.verify_chain()


@router.get("/summary")
async def audit_summary(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
) -> dict[str, object]:
    enforce_scope(principal, "audit:read")
    items = audit_store.list(limit=1000, tenant_id=_enforce_audit_tenant_scope(principal, None))
    by_action: dict[str, int] = {}
    by_resource_type: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for item in items:
        by_action[item.action] = by_action.get(item.action, 0) + 1
        by_resource_type[item.resource_type] = by_resource_type.get(item.resource_type, 0) + 1
        by_outcome[item.outcome] = by_outcome.get(item.outcome, 0) + 1
    primary = {
        "count": len(items),
        "by_action": by_action,
        "by_resource_type": by_resource_type,
        "by_outcome": by_outcome,
    }
    return build_linked_summary(resource_type="audit_summary", resource_id="audit_summary", primary=primary, audit=primary, extra=primary)


@router.get("/export/csv")
async def export_audit_logs_csv(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    tenant_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: str | None = None,
) -> StreamingResponse:
    """Export audit logs as CSV file.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        tenant_id: Filter by tenant
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome

    Returns:
        CSV file as streaming response
    """
    enforce_scope(principal, "audit:read")
    csv_content = audit_store.export_csv(
        tenant_id=_enforce_audit_tenant_scope(principal, tenant_id),
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
    )

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-logs.csv"},
    )


@router.get("/export/json")
async def export_audit_logs_json(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    tenant_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: str | None = None,
) -> dict[str, object]:
    """Export audit logs as JSON.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        tenant_id: Filter by tenant
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome

    Returns:
        JSON formatted audit logs
    """
    enforce_scope(principal, "audit:read")
    records = audit_store.export_json(
        tenant_id=_enforce_audit_tenant_scope(principal, tenant_id),
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
    )
    return {"data": records, "count": len(records)}
