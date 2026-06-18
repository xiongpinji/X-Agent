from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.api.pagination import apply_pagination
from backend.app.core.admin import UserCreateRequest, UserRecord, UserUpdateRequest, user_store
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal, is_platform_admin
from backend.app.dependencies import enforce_scope, get_current_principal, get_audit_store

router = APIRouter(prefix="/api/v1/users", tags=["users"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]


def _user_not_found(user_id: str):
    return api_error(
        404,
        ErrorCode.RESOURCE_NOT_FOUND,
        "User not found.",
        details={"resource_type": "user", "resource_id": user_id},
    )


def _visible_users(principal: Principal) -> list[UserRecord]:
    records = user_store.list()
    if is_platform_admin(principal):
        return records
    return [record for record in records if record.tenant_id == principal.tenant_id]


def _get_visible_user(user_id: str, principal: Principal) -> UserRecord:
    record = user_store.get(user_id)
    if record is None or (
        not is_platform_admin(principal)
        and record.tenant_id != principal.tenant_id
    ):
        raise _user_not_found(user_id)
    return record


def _create_request_for_principal(
    request: UserCreateRequest,
    principal: Principal,
) -> UserCreateRequest:
    if is_platform_admin(principal):
        return request
    return request.model_copy(update={"tenant_id": principal.tenant_id})


def _update_request_for_principal(
    request: UserUpdateRequest,
    principal: Principal,
) -> UserUpdateRequest:
    if is_platform_admin(principal):
        return request
    return request.model_copy(update={"tenant_id": principal.tenant_id})


@router.post("")
async def create_user(request: UserCreateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return user_store.create(_create_request_for_principal(request, principal)).model_dump(mode="json")


@router.get("")
async def list_users(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return {"data": [item.model_dump(mode="json") for item in _visible_users(principal)]}


@router.get("/{user_id}")
async def get_user(user_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return _get_visible_user(user_id, principal).model_dump(mode="json")


@router.put("/{user_id}")
async def update_user(user_id: str, request: UserUpdateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    _get_visible_user(user_id, principal)
    record = user_store.upsert(_update_request_for_principal(request, principal), user_id)
    return record.model_dump(mode="json")


@router.put("/{user_id}/role")
async def update_user_role(user_id: str, request: dict[str, str], principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = _get_visible_user(user_id, principal)
    record.role = request.get("role", record.role)
    return record.model_dump(mode="json")


@router.get("/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    """Get user activity history with pagination.

    Returns audit log entries for the specified user, including:
    - Login/logout events
    - Resource access
    - Configuration changes
    - API calls

    Args:
        user_id: User ID to get activity for
        principal: Current principal (must have security:manage scope)
        limit: Number of items per page
        offset: Number of items to skip

    Returns:
        Paginated activity history
    """
    enforce_scope(principal, "security:manage")
    _get_visible_user(user_id, principal)

    activities = audit_store.list(
        actor_id=user_id,
        tenant_id=None if is_platform_admin(principal) else principal.tenant_id,
        limit=1000,
    )

    # Apply pagination
    paginated, metadata = apply_pagination(activities, limit, offset)

    return {
        "user_id": user_id,
        "items": [item.model_dump(mode="json") for item in paginated],
        "pagination": metadata.model_dump(),
    }


@router.delete("/{user_id}")
async def delete_user(user_id: str, principal: PrincipalDependency) -> dict[str, bool]:
    enforce_scope(principal, "security:manage")
    _get_visible_user(user_id, principal)
    if not user_store.delete(user_id):
        raise _user_not_found(user_id)
    return {"deleted": True}
