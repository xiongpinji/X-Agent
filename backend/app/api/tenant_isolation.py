"""租户隔离API端点和审计"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.core.tenant_isolation import TenantIsolationValidator
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/security/tenant-isolation", tags=["security"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/status")
async def get_tenant_isolation_status(
    principal: PrincipalDependency,
) -> dict[str, object]:
    """获取租户隔离状态"""
    enforce_scope(principal, "security:manage")
    return {
        "current_tenant_id": principal.tenant_id,
        "user_id": principal.user_id,
        "role": principal.role,
        "is_admin": principal.role == "admin",
        "isolation_enabled": True,
    }


@router.post("/validate-access")
async def validate_tenant_access(
    principal: PrincipalDependency,
    resource_tenant_id: str,
    resource_type: str = "resource",
) -> dict[str, object]:
    """验证租户访问权限"""
    enforce_scope(principal, "security:manage")
    is_allowed = TenantIsolationValidator.validate_tenant_access(
        principal,
        resource_tenant_id,
        resource_type=resource_type,
    )
    return {
        "allowed": is_allowed,
        "principal_tenant_id": principal.tenant_id,
        "resource_tenant_id": resource_tenant_id,
        "resource_type": resource_type,
    }


@router.get("/audit-violations")
async def get_tenant_isolation_violations(
    principal: PrincipalDependency,
    limit: int = 100,
) -> list[dict[str, object]]:
    """获取租户隔离违规记录"""
    enforce_scope(principal, "security:manage")

    # 从审计日志中获取租户隔离违规
    from backend.app.dependencies import get_audit_store

    audit_store = get_audit_store()
    violations = []

    for record in audit_store.list():
        if "tenant isolation violation" in str(record).lower():
            violations.append(record.model_dump(mode="json"))

    return violations[:limit]
