"""租户隔离API端点和审计"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.core.tenant_isolation import TenantIsolationValidator
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/security/tenant-isolation", tags=["security"])
extended_router = APIRouter(prefix="/api/v1/security/tenant-isolation", tags=["tenant-isolation-extended"])  # C2: unmounted
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@extended_router.get("/status")
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


@extended_router.post("/validate-access")
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


@extended_router.get("/audit-violations")
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


# ─── N: Tenant Quota / Usage / RBAC ──────────────────────────────────────────


@router.get("/quotas")
async def get_tenant_quotas(principal: PrincipalDependency = None) -> dict[str, object]:
    """Current tenant resource quotas and usage."""
    enforce_scope(principal, "agent:run")
    import time

    tenant_id = principal.tenant_id
    user_id = principal.user_id

    quota_info: dict[str, object] = {}
    try:
        from backend.app.core.llm.quota import get_quota_manager
        mgr = get_quota_manager()
        if mgr is None:
            quota_info = {"enabled": False}
        else:
            quota_info = {
                "tenant_token_limit": mgr.tenant_limit(tenant_id),
                "user_token_limit": mgr.user_limit(user_id),
                "period": mgr.period,
                "enabled": mgr.enabled,
            }
    except Exception:
        quota_info = {"error": "quota manager unavailable"}

    return {
        "timestamp": time.time(),
        "tenant_id": tenant_id,
        "user_id": user_id,
        "quotas": quota_info,
    }


@router.get("/usage")
async def get_tenant_usage(principal: PrincipalDependency = None) -> dict[str, object]:
    """Tenant resource usage summary: runs, tokens, tools."""
    enforce_scope(principal, "agent:run")
    import time

    tenant_id = principal.tenant_id

    # Run count for this tenant
    run_count = 0
    try:
        from backend.app.core.run_store import get_run_store
        records = get_run_store().list(limit=200)
        tenant_runs = [r for r in records if getattr(r, "tenant_id", None) == tenant_id]
        run_count = len(tenant_runs)
    except Exception:
        pass

    # Active agents for this tenant
    active_agents = 0
    try:
        from backend.app.core.agent_spawner import agent_spawner
        stats = agent_spawner.get_stats()
        active_agents = stats.get("active_agents", 0)
    except Exception:
        pass

    return {
        "timestamp": time.time(),
        "tenant_id": tenant_id,
        "usage": {
            "total_runs": run_count,
            "active_agents": active_agents,
        },
    }


@router.get("/rbac-matrix")
async def get_rbac_matrix(principal: PrincipalDependency = None) -> dict[str, object]:
    """RBAC permission matrix: roles × scopes."""
    enforce_scope(principal, "security:manage")

    # Define the standard RBAC matrix
    matrix = {
        "admin": [
            "agent:run", "agent:manage", "security:manage",
            "tools:*", "memory:*", "plugins:manage",
            "collaboration:*", "admin:*",
        ],
        "developer": [
            "agent:run", "agent:manage",
            "tools:*", "memory:read", "memory:write",
            "collaboration:read", "collaboration:write",
        ],
        "viewer": [
            "agent:read", "memory:read", "collaboration:read",
        ],
        "service": [
            "agent:run", "tools:execute",
        ],
    }

    return {
        "current_role": principal.role,
        "current_scopes": list(getattr(principal, "scopes", None) or []),
        "roles": matrix,
    }
