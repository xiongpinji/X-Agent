from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.linked_summary import LinkedSummaryEnvelope, build_linked_summary
from backend.app.core.audit import AuditChainVerification, AuditLogRecord, AuditStore
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_audit_store, get_current_principal

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("", response_model=list[AuditLogRecord])
async def list_audit_logs(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: str | None = None,
    trace_id: str | None = None,
    run_id: str | None = None,
    workflow_id: str | None = None,
    has_snapshot: bool | None = None,
) -> list[AuditLogRecord]:
    enforce_scope(principal, "audit:read")
    records = audit_store.list(
        limit=limit,
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
    return filtered


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
    items = audit_store.list(limit=1000)
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
