from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyRecord,
    APIKeyStore,
    Principal,
    RBACPolicy,
    ROLE_SCOPES,
    is_platform_admin,
)
from backend.app.dependencies import enforce_scope, get_api_key_store, get_current_principal

router = APIRouter(prefix="/api/v1/security", tags=["security"])
APIKeyStoreDependency = Annotated[APIKeyStore, Depends(get_api_key_store)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def _tenant_visible_api_keys(
    records: list[APIKeyRecord],
    principal: Principal,
) -> list[APIKeyRecord]:
    if is_platform_admin(principal):
        return records
    return [record for record in records if record.tenant_id == principal.tenant_id]


def _get_visible_api_key(
    key_id: str,
    principal: Principal,
    store: APIKeyStore,
) -> APIKeyRecord:
    record = next((item for item in store.list() if item.id == key_id), None)
    if record is None or (
        not is_platform_admin(principal)
        and record.tenant_id != principal.tenant_id
    ):
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "API key not found.")
    return record


def _api_key_create_request_for_principal(
    request: APIKeyCreateRequest,
    principal: Principal,
) -> APIKeyCreateRequest:
    if is_platform_admin(principal):
        return request
    policy = RBACPolicy()
    requested_scopes = request.scopes or ROLE_SCOPES.get(request.role, [])
    allowed_scopes = [
        scope for scope in requested_scopes if policy.has_scope(principal, scope)
    ]
    return request.model_copy(
        update={
            "tenant_id": principal.tenant_id,
            "user_id": principal.user_id,
            "role": "custom",
            "scopes": allowed_scopes,
        }
    )


@router.get("/me", response_model=Principal)
async def get_me(principal: PrincipalDependency) -> Principal:
    return principal


@router.post("/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> APIKeyCreateResponse:
    enforce_scope(principal, "security:manage")
    return store.create(_api_key_create_request_for_principal(request, principal))


@router.get("/api-keys", response_model=list[APIKeyRecord])
async def list_api_keys(
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> list[APIKeyRecord]:
    enforce_scope(principal, "security:manage")
    return _tenant_visible_api_keys(store.list(), principal)


@router.get("/api-keys/expiring-soon", response_model=list[APIKeyRecord])
async def list_expiring_api_keys(
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
    days: int = 30,
) -> list[APIKeyRecord]:
    """获取即将过期的API Key（默认30天内）"""
    enforce_scope(principal, "security:manage")
    from datetime import UTC, datetime, timedelta

    expiring_keys = []
    threshold = datetime.now(UTC) + timedelta(days=days)

    for record in _tenant_visible_api_keys(store.list(), principal):
        if record.revoked or not record.expires_at:
            continue
        if record.expires_at <= threshold:
            expiring_keys.append(record)

    return sorted(expiring_keys, key=lambda r: r.expires_at or datetime.now(UTC))


@router.get("/api-keys/{key_id}", response_model=APIKeyRecord)
async def get_api_key(
    key_id: str,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> APIKeyRecord:
    enforce_scope(principal, "security:manage")
    return _get_visible_api_key(key_id, principal, store)


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> dict[str, bool]:
    enforce_scope(principal, "security:manage")
    _get_visible_api_key(key_id, principal, store)
    record = store.revoke(key_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "API key not found.")
    return {"deleted": True}


@router.post("/bootstrap-key/mark-changed")
async def mark_bootstrap_key_changed(
    principal: PrincipalDependency,
) -> dict[str, bool]:
    """标记Bootstrap Key已更换"""
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    from backend.app.core.bootstrap_key_enforcer import get_bootstrap_key_enforcer
    enforcer = get_bootstrap_key_enforcer()
    enforcer.mark_bootstrap_key_changed(principal.user_id)
    return {"success": True}


@router.get("/bootstrap-key/status")
async def get_bootstrap_key_status(
    principal: PrincipalDependency,
) -> dict[str, object]:
    """获取Bootstrap Key状态"""
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    from backend.app.core.bootstrap_key_enforcer import get_bootstrap_key_enforcer
    enforcer = get_bootstrap_key_enforcer()
    status = enforcer.get_status(principal.user_id)
    return status.model_dump(mode="json")


@router.post("/api-keys/{key_id}/revoke", response_model=APIKeyRecord)
async def revoke_api_key(
    key_id: str,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> APIKeyRecord:
    enforce_scope(principal, "security:manage")
    _get_visible_api_key(key_id, principal, store)
    record = store.revoke(key_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "API key not found.")
    return record
