"""
API Key Management Endpoints.

Provides REST API for:
- Creating, listing, and managing API keys
- Rotating and revoking keys
- Checking key status and usage
- Managing permissions and restrictions
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from backend.app.core.access_control import PermissionChecker
from backend.app.core.api_key_manager import (
    AnomalyAlert,
    APIKeyConfig,
    APIKeyManager,
    AuditEntry,
    IPWhitelist,
    PermissionLevel,
    RateLimitConfig,
)

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])

# Global API key manager instance
_api_key_manager: APIKeyManager | None = None


def get_api_key_manager() -> APIKeyManager:
    """Get or create API key manager."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def get_permission_checker(
    manager: APIKeyManager = Depends(get_api_key_manager),
) -> PermissionChecker:
    """Get permission checker."""
    return PermissionChecker(manager)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=255)
    permissions: list[str] = Field(default_factory=list)
    expires_in_days: int = Field(default=90, ge=1, le=365)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreateAPIKeyResponse(BaseModel):
    """Response with newly created API key."""
    key: str  # Only shown once
    config: APIKeyConfigResponse


class APIKeyConfigResponse(BaseModel):
    """API key configuration response."""
    id: str
    name: str
    key_prefix: str
    tenant_id: str
    user_id: str
    permissions: list[str]
    status: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    total_requests: int
    failed_requests: int


class UpdateAPIKeyRequest(BaseModel):
    """Request to update API key."""
    name: str | None = None
    permissions: list[str] | None = None
    rate_limit: dict[str, int] | None = None
    ip_whitelist: dict[str, Any] | None = None


class RotateAPIKeyRequest(BaseModel):
    """Request to rotate API key."""
    reason: str | None = None


class RevokeAPIKeyRequest(BaseModel):
    """Request to revoke API key."""
    reason: str | None = None


class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    id: str
    timestamp: datetime
    event_type: str
    key_prefix: str
    actor_id: str
    actor_type: str
    ip_address: str | None
    success: bool
    error_message: str | None


class AnomalyAlertResponse(BaseModel):
    """Anomaly alert response."""
    id: str
    timestamp: datetime
    anomaly_type: str
    severity: str
    description: str
    recommended_action: str | None


class KeyUsageStatsResponse(BaseModel):
    """Key usage statistics response."""
    key_id: str
    name: str
    total_requests: int
    failed_requests: int
    last_used_at: datetime | None
    last_ip: str | None
    created_at: datetime
    expires_at: datetime | None
    days_until_expiry: int | None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _config_to_response(config: APIKeyConfig) -> APIKeyConfigResponse:
    """Convert APIKeyConfig to response model."""
    return APIKeyConfigResponse(
        id=config.id,
        name=config.name,
        key_prefix=config.key_prefix,
        tenant_id=config.tenant_id,
        user_id=config.user_id,
        permissions=[p.value for p in config.permissions],
        status=config.status.value,
        created_at=config.created_at,
        expires_at=config.expires_at,
        last_used_at=config.last_used_at,
        total_requests=config.total_requests,
        failed_requests=config.failed_requests,
    )


def _audit_to_response(entry: AuditEntry) -> AuditLogResponse:
    """Convert AuditEntry to response model."""
    return AuditLogResponse(
        id=entry.id,
        timestamp=entry.timestamp,
        event_type=entry.event_type,
        key_prefix=entry.key_prefix,
        actor_id=entry.actor_id,
        actor_type=entry.actor_type,
        ip_address=entry.ip_address,
        success=entry.success,
        error_message=entry.error_message,
    )


def _alert_to_response(alert: AnomalyAlert) -> AnomalyAlertResponse:
    """Convert AnomalyAlert to response model."""
    return AnomalyAlertResponse(
        id=alert.id,
        timestamp=alert.timestamp,
        anomaly_type=alert.anomaly_type.value,
        severity=alert.severity,
        description=alert.description,
        recommended_action=alert.recommended_action,
    )


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("", response_model=CreateAPIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: Request,
    body: CreateAPIKeyRequest,
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> CreateAPIKeyResponse:
    """Create a new API key.

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    principal = request.state.principal
    config = request.state.api_key_config

    # Convert permission strings to PermissionLevel enums
    permissions = []
    for perm_str in body.permissions:
        try:
            permissions.append(PermissionLevel(perm_str))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission: {perm_str}",
            )

    # Create key
    raw_key, new_config = manager.create_key(
        name=body.name,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        permissions=permissions or [PermissionLevel.AGENT_READ],
        expires_in_days=body.expires_in_days,
        created_by=config.user_id,
    )

    return CreateAPIKeyResponse(
        key=raw_key,
        config=_config_to_response(new_config),
    )


@router.get("", response_model=list[APIKeyConfigResponse])
async def list_api_keys(
    request: Request,
    status_filter: str | None = Query(None, alias="status"),
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> list[APIKeyConfigResponse]:
    """List API keys.

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    principal = request.state.principal

    # List keys for current tenant/user
    keys = manager.list_keys(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )

    return [_config_to_response(k) for k in keys]


@router.get("/{key_id}", response_model=APIKeyConfigResponse)
async def get_api_key(
    request: Request,
    key_id: str,
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> APIKeyConfigResponse:
    """Get API key details.

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    config = manager.get_key(key_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    # Check ownership
    principal = request.state.principal
    if config.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return _config_to_response(config)


@router.patch("/{key_id}", response_model=APIKeyConfigResponse)
async def update_api_key(
    request: Request,
    key_id: str,
    body: UpdateAPIKeyRequest,
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> APIKeyConfigResponse:
    """Update API key configuration.

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    config = manager.get_key(key_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    principal = request.state.principal
    actor_config = request.state.api_key_config

    # Check ownership
    if config.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Prepare updates
    updates = {}

    if body.name is not None:
        updates["name"] = body.name

    if body.permissions is not None:
        permissions = []
        for perm_str in body.permissions:
            try:
                permissions.append(PermissionLevel(perm_str))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid permission: {perm_str}",
                )
        updates["permissions"] = permissions

    if body.rate_limit is not None:
        updates["rate_limit"] = RateLimitConfig(**body.rate_limit)

    if body.ip_whitelist is not None:
        updates["ip_whitelist"] = IPWhitelist(**body.ip_whitelist)

    # Update
    updated = manager.update_key(key_id, updates, actor_config.user_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    return _config_to_response(updated)


@router.post("/{key_id}/rotate", response_model=CreateAPIKeyResponse)
async def rotate_api_key(
    request: Request,
    key_id: str,
    body: RotateAPIKeyRequest,
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> CreateAPIKeyResponse:
    """Rotate an API key.

    Creates a new key and marks the old one as rotated.
    Old key remains active for 7 days for grace period.

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    config = manager.get_key(key_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    principal = request.state.principal
    actor_config = request.state.api_key_config

    # Check ownership
    if config.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Rotate
    try:
        raw_key, new_config = manager.rotate_key(key_id, actor_config.user_id)
        return CreateAPIKeyResponse(
            key=raw_key,
            config=_config_to_response(new_config),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{key_id}/revoke", response_model=APIKeyConfigResponse)
async def revoke_api_key(
    request: Request,
    key_id: str,
    body: RevokeAPIKeyRequest,
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> APIKeyConfigResponse:
    """Revoke an API key.

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    config = manager.get_key(key_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    principal = request.state.principal
    actor_config = request.state.api_key_config

    # Check ownership
    if config.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Revoke
    try:
        revoked = manager.revoke_key(key_id, actor_config.user_id, body.reason)
        return _config_to_response(revoked)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    request: Request,
    key_id: str,
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> None:
    """Delete an API key (same as revoke).

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    config = manager.get_key(key_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    principal = request.state.principal
    actor_config = request.state.api_key_config

    # Check ownership
    if config.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Revoke
    manager.revoke_key(key_id, actor_config.user_id, "Deleted by user")


@router.get("/{key_id}/usage", response_model=KeyUsageStatsResponse)
async def get_key_usage_stats(
    request: Request,
    key_id: str,
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> KeyUsageStatsResponse:
    """Get usage statistics for an API key.

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    stats = manager.get_key_usage_stats(key_id)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    principal = request.state.principal
    config = manager.get_key(key_id)

    # Check ownership
    if config.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return KeyUsageStatsResponse(**stats)


@router.get("/{key_id}/audit-log", response_model=list[AuditLogResponse])
async def get_key_audit_log(
    request: Request,
    key_id: str,
    limit: int = Query(100, ge=1, le=1000),
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> list[AuditLogResponse]:
    """Get audit log for an API key.

    Requires: audit:read permission
    """
    checker.require_permission(request, PermissionLevel.AUDIT_READ)

    config = manager.get_key(key_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    principal = request.state.principal

    # Check ownership
    if config.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    entries = manager.get_audit_log(key_id=key_id, limit=limit)
    return [_audit_to_response(e) for e in entries]


@router.get("/{key_id}/anomalies", response_model=list[AnomalyAlertResponse])
async def get_key_anomalies(
    request: Request,
    key_id: str,
    severity: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> list[AnomalyAlertResponse]:
    """Get anomaly alerts for an API key.

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    config = manager.get_key(key_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    principal = request.state.principal

    # Check ownership
    if config.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    alerts = manager.get_anomaly_alerts(key_id=key_id, severity=severity, limit=limit)
    return [_alert_to_response(a) for a in alerts]


@router.get("/expiring-soon", response_model=list[APIKeyConfigResponse])
async def list_expiring_keys(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    manager: APIKeyManager = Depends(get_api_key_manager),
    checker: PermissionChecker = Depends(get_permission_checker),
) -> list[APIKeyConfigResponse]:
    """List API keys expiring soon.

    Requires: security:manage permission
    """
    checker.require_permission(request, PermissionLevel.SECURITY_MANAGE)

    principal = request.state.principal
    keys = manager.list_keys(tenant_id=principal.tenant_id)

    # Filter expiring keys
    threshold = datetime.now(UTC) + timedelta(days=days)
    expiring = [
        k for k in keys
        if k.expires_at and k.expires_at <= threshold and k.status.value != "revoked"
    ]

    return [_config_to_response(k) for k in expiring]
