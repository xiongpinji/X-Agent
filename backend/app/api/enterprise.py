"""
Enterprise API routes for multi-tenancy, SSO, team management, and compliance.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.enterprise import (
    APIKey,
    AuditEventType,
    AuditLog,
    ComplianceReport,
    EnterpriseService,
    EnterpriseTenant,
    EnterpriseUser,
    PermissionType,
    RoleType,
    Team,
    TenantPlan,
)

router = APIRouter(prefix="/api/v1/enterprise", tags=["enterprise"])

# Global enterprise service instance
_enterprise_service: EnterpriseService | None = None


def get_enterprise_service() -> EnterpriseService:
    """Get or create enterprise service."""
    global _enterprise_service
    if _enterprise_service is None:
        _enterprise_service = EnterpriseService()
    return _enterprise_service


# ============================================================================
# TENANT MANAGEMENT
# ============================================================================

@router.post("/tenants", response_model=EnterpriseTenant)
async def create_tenant(
    tenant_data: dict[str, Any],
    service: EnterpriseService = Depends(get_enterprise_service),
) -> EnterpriseTenant:
    """Create a new enterprise tenant."""
    tenant = EnterpriseTenant(
        name=tenant_data.get("name", ""),
        plan=TenantPlan(tenant_data.get("plan", "free")),
        organization_name=tenant_data.get("organization_name"),
        industry=tenant_data.get("industry"),
        country=tenant_data.get("country"),
    )
    return service.tenants.create(tenant)


@router.get("/tenants/{tenant_id}", response_model=EnterpriseTenant)
async def get_tenant(
    tenant_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> EnterpriseTenant:
    """Get tenant details."""
    tenant = service.tenants.get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.put("/tenants/{tenant_id}", response_model=EnterpriseTenant)
async def update_tenant(
    tenant_id: str,
    updates: dict[str, Any],
    service: EnterpriseService = Depends(get_enterprise_service),
) -> EnterpriseTenant:
    """Update tenant configuration."""
    tenant = service.tenants.update(tenant_id, updates)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/tenants", response_model=list[EnterpriseTenant])
async def list_tenants(
    service: EnterpriseService = Depends(get_enterprise_service),
) -> list[EnterpriseTenant]:
    """List all tenants."""
    return service.tenants.list_all()


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@router.post("/tenants/{tenant_id}/users", response_model=EnterpriseUser)
async def create_user(
    tenant_id: str,
    user_data: dict[str, Any],
    service: EnterpriseService = Depends(get_enterprise_service),
) -> EnterpriseUser:
    """Create a new user in a tenant."""
    user = EnterpriseUser(
        email=user_data.get("email", ""),
        display_name=user_data.get("display_name", ""),
        tenant_id=tenant_id,
        role=RoleType(user_data.get("role", "developer")),
        department=user_data.get("department"),
        manager_id=user_data.get("manager_id"),
    )
    created_user = service.users.create(user)

    # Log event
    service.log_event(
        tenant_id=tenant_id,
        event_type=AuditEventType.USER_CREATED,
        resource_type="user",
        resource_id=created_user.id,
        action="create",
        changes={"email": user.email, "role": user.role.value},
    )

    return created_user


@router.get("/tenants/{tenant_id}/users/{user_id}", response_model=EnterpriseUser)
async def get_user(
    tenant_id: str,
    user_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> EnterpriseUser:
    """Get user details."""
    user = service.users.get(user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/tenants/{tenant_id}/users/{user_id}", response_model=EnterpriseUser)
async def update_user(
    tenant_id: str,
    user_id: str,
    updates: dict[str, Any],
    service: EnterpriseService = Depends(get_enterprise_service),
) -> EnterpriseUser:
    """Update user."""
    user = service.users.get(user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = service.users.update(user_id, updates)

    # Log event
    service.log_event(
        tenant_id=tenant_id,
        event_type=AuditEventType.USER_ROLE_CHANGED,
        resource_type="user",
        resource_id=user_id,
        action="update",
        changes=updates,
    )

    return updated_user


@router.delete("/tenants/{tenant_id}/users/{user_id}", status_code=204)
async def delete_user(
    tenant_id: str,
    user_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> None:
    """Delete user."""
    user = service.users.get(user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="User not found")

    service.users.delete(user_id)

    # Log event
    service.log_event(
        tenant_id=tenant_id,
        event_type=AuditEventType.USER_DELETED,
        resource_type="user",
        resource_id=user_id,
        action="delete",
    )


@router.get("/tenants/{tenant_id}/users", response_model=list[EnterpriseUser])
async def list_users(
    tenant_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> list[EnterpriseUser]:
    """List all users in a tenant."""
    return service.users.list_by_tenant(tenant_id)


# ============================================================================
# TEAM MANAGEMENT
# ============================================================================

@router.post("/tenants/{tenant_id}/teams", response_model=Team)
async def create_team(
    tenant_id: str,
    team_data: dict[str, Any],
    service: EnterpriseService = Depends(get_enterprise_service),
) -> Team:
    """Create a new team."""
    team = Team(
        tenant_id=tenant_id,
        name=team_data.get("name", ""),
        description=team_data.get("description"),
        owner_id=team_data.get("owner_id", ""),
    )
    created_team = service.teams.create(team)

    # Log event
    service.log_event(
        tenant_id=tenant_id,
        event_type=AuditEventType.TEAM_CREATED,
        resource_type="team",
        resource_id=created_team.id,
        action="create",
        changes={"name": team.name},
    )

    return created_team


@router.get("/tenants/{tenant_id}/teams/{team_id}", response_model=Team)
async def get_team(
    tenant_id: str,
    team_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> Team:
    """Get team details."""
    team = service.teams.get(team_id)
    if not team or team.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("/tenants/{tenant_id}/teams", response_model=list[Team])
async def list_teams(
    tenant_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> list[Team]:
    """List all teams in a tenant."""
    return service.teams.list_by_tenant(tenant_id)


@router.post("/tenants/{tenant_id}/teams/{team_id}/members/{user_id}", status_code=201)
async def add_team_member(
    tenant_id: str,
    team_id: str,
    user_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> dict[str, str]:
    """Add member to team."""
    team = service.teams.get(team_id)
    if not team or team.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Team not found")

    success = service.teams.add_member(team_id, user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add member")

    # Log event
    service.log_event(
        tenant_id=tenant_id,
        event_type=AuditEventType.TEAM_MEMBER_ADDED,
        resource_type="team",
        resource_id=team_id,
        action="add_member",
        changes={"user_id": user_id},
    )

    return {"status": "success"}


@router.delete("/tenants/{tenant_id}/teams/{team_id}/members/{user_id}", status_code=204)
async def remove_team_member(
    tenant_id: str,
    team_id: str,
    user_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> None:
    """Remove member from team."""
    team = service.teams.get(team_id)
    if not team or team.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Team not found")

    service.teams.remove_member(team_id, user_id)

    # Log event
    service.log_event(
        tenant_id=tenant_id,
        event_type=AuditEventType.TEAM_MEMBER_REMOVED,
        resource_type="team",
        resource_id=team_id,
        action="remove_member",
        changes={"user_id": user_id},
    )


# ============================================================================
# API KEY MANAGEMENT
# ============================================================================

@router.post("/tenants/{tenant_id}/api-keys", response_model=APIKey)
async def create_api_key(
    tenant_id: str,
    key_data: dict[str, Any],
    service: EnterpriseService = Depends(get_enterprise_service),
) -> APIKey:
    """Create a new API key."""
    import hashlib
    import secrets

    # Generate secure key
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = APIKey(
        tenant_id=tenant_id,
        user_id=key_data.get("user_id", ""),
        name=key_data.get("name", ""),
        key_hash=key_hash,
        permissions=[
            PermissionType(p) for p in key_data.get("permissions", [])
        ],
        rate_limit=key_data.get("rate_limit"),
    )

    created_key = service.api_keys.create(api_key)

    # Log event
    service.log_event(
        tenant_id=tenant_id,
        event_type=AuditEventType.API_KEY_CREATED,
        resource_type="api_key",
        resource_id=created_key.id,
        action="create",
        changes={"name": api_key.name},
    )

    return created_key


@router.get("/tenants/{tenant_id}/api-keys", response_model=list[APIKey])
async def list_api_keys(
    tenant_id: str,
    user_id: str | None = Query(None),
    service: EnterpriseService = Depends(get_enterprise_service),
) -> list[APIKey]:
    """List API keys."""
    if user_id:
        return service.api_keys.list_by_user(user_id)
    # Would need to filter by tenant
    return []


@router.delete("/tenants/{tenant_id}/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    tenant_id: str,
    key_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> None:
    """Revoke an API key."""
    service.api_keys.revoke(key_id)

    # Log event
    service.log_event(
        tenant_id=tenant_id,
        event_type=AuditEventType.API_KEY_REVOKED,
        resource_type="api_key",
        resource_id=key_id,
        action="revoke",
    )


# ============================================================================
# AUDIT & COMPLIANCE
# ============================================================================

@router.get("/tenants/{tenant_id}/audit-logs", response_model=list[AuditLog])
async def list_audit_logs(
    tenant_id: str,
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    event_type: str | None = Query(None),
    service: EnterpriseService = Depends(get_enterprise_service),
) -> list[AuditLog]:
    """List audit logs for a tenant."""
    event_type_enum = None
    if event_type:
        try:
            event_type_enum = AuditEventType(event_type)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event_type: {event_type}. Must be one of {[e.name for e in AuditEventType]}",
            ) from e

    return service.audit_logs.list_by_tenant(
        tenant_id,
        start_date=start_date,
        end_date=end_date,
        event_type=event_type_enum,
    )


@router.get("/tenants/{tenant_id}/compliance-reports", response_model=list[ComplianceReport])
async def list_compliance_reports(
    tenant_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> list[ComplianceReport]:
    """List compliance reports for a tenant."""
    # Would retrieve from storage
    return []


@router.post("/tenants/{tenant_id}/compliance-reports", response_model=ComplianceReport)
async def generate_compliance_report(
    tenant_id: str,
    report_data: dict[str, Any],
    service: EnterpriseService = Depends(get_enterprise_service),
) -> ComplianceReport:
    """Generate a compliance report."""
    report_type = report_data.get("report_type", "general")
    days_back = report_data.get("days_back", 30)

    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days_back)

    return service.generate_compliance_report(
        tenant_id=tenant_id,
        report_type=report_type,
        period_start=start_date,
        period_end=end_date,
    )


# ============================================================================
# PERMISSIONS & ACCESS CONTROL
# ============================================================================

@router.get("/tenants/{tenant_id}/users/{user_id}/permissions", response_model=list[str])
async def get_user_permissions(
    tenant_id: str,
    user_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> list[str]:
    """Get user permissions."""
    user = service.users.get(user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="User not found")

    return [p.value for p in user.permissions]


@router.post("/tenants/{tenant_id}/users/{user_id}/permissions/{permission}")
async def grant_permission(
    tenant_id: str,
    user_id: str,
    permission: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> dict[str, str]:
    """Grant permission to user."""
    user = service.users.get(user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        perm = PermissionType(permission)
        if perm not in user.permissions:
            user.permissions.append(perm)
            service.users.update(user_id, {"permissions": user.permissions})
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid permission")

    return {"status": "success"}


@router.delete("/tenants/{tenant_id}/users/{user_id}/permissions/{permission}", status_code=204)
async def revoke_permission(
    tenant_id: str,
    user_id: str,
    permission: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> None:
    """Revoke permission from user."""
    user = service.users.get(user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        perm = PermissionType(permission)
        if perm in user.permissions:
            user.permissions.remove(perm)
            service.users.update(user_id, {"permissions": user.permissions})
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid permission")


# ============================================================================
# SSO CONFIGURATION
# ============================================================================

@router.put("/tenants/{tenant_id}/sso-config")
async def update_sso_config(
    tenant_id: str,
    sso_config: dict[str, Any],
    service: EnterpriseService = Depends(get_enterprise_service),
) -> EnterpriseTenant:
    """Update SSO configuration for a tenant."""
    tenant = service.tenants.get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    updates = {
        "sso_enabled": sso_config.get("enabled", False),
        "sso_provider": sso_config.get("provider"),
        "sso_config": sso_config.get("config", {}),
    }

    updated_tenant = service.tenants.update(tenant_id, updates)

    # Log event
    service.log_event(
        tenant_id=tenant_id,
        event_type=AuditEventType.POLICY_CHANGED,
        resource_type="tenant",
        resource_id=tenant_id,
        action="update_sso",
        changes=updates,
    )

    return updated_tenant


@router.get("/tenants/{tenant_id}/sso-config")
async def get_sso_config(
    tenant_id: str,
    service: EnterpriseService = Depends(get_enterprise_service),
) -> dict[str, Any]:
    """Get SSO configuration for a tenant."""
    tenant = service.tenants.get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return {
        "enabled": tenant.sso_enabled,
        "provider": tenant.sso_provider,
        "config": tenant.sso_config,
    }
