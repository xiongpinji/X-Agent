from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.admin import UserCreateRequest, UserUpdateRequest, user_store
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/users", tags=["users"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.post("")
async def create_user(request: UserCreateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return user_store.create(request).model_dump(mode="json")


@router.get("")
async def list_users(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return {"data": [item.model_dump(mode="json") for item in user_store.list()]}


@router.get("/{user_id}")
async def get_user(user_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = user_store.get(user_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "User not found.", details={"resource_type": "user", "resource_id": user_id})
    return record.model_dump(mode="json")


@router.put("/{user_id}")
async def update_user(user_id: str, request: UserUpdateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = user_store.upsert(request, user_id)
    return record.model_dump(mode="json")


@router.put("/{user_id}/role")
async def update_user_role(user_id: str, request: dict[str, str], principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = user_store.get(user_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "User not found.", details={"resource_type": "user", "resource_id": user_id})
    record.role = request.get("role", record.role)
    return record.model_dump(mode="json")


@router.get("/{user_id}/activity")
async def get_user_activity(user_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = user_store.get(user_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "User not found.", details={"resource_type": "user", "resource_id": user_id})
    return {"user_id": user_id, "items": []}


@router.delete("/{user_id}")
async def delete_user(user_id: str, principal: PrincipalDependency) -> dict[str, bool]:
    enforce_scope(principal, "security:manage")
    if not user_store.delete(user_id):
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "User not found.", details={"resource_type": "user", "resource_id": user_id})
    return {"deleted": True}
