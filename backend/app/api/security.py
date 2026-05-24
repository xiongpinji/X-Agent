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
)
from backend.app.dependencies import enforce_scope, get_api_key_store, get_current_principal

router = APIRouter(prefix="/api/v1/security", tags=["security"])
APIKeyStoreDependency = Annotated[APIKeyStore, Depends(get_api_key_store)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


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
    return store.create(request)


@router.get("/api-keys", response_model=list[APIKeyRecord])
async def list_api_keys(
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> list[APIKeyRecord]:
    enforce_scope(principal, "security:manage")
    return store.list()


@router.get("/api-keys/{key_id}", response_model=APIKeyRecord)
async def get_api_key(
    key_id: str,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> APIKeyRecord:
    enforce_scope(principal, "security:manage")
    record = next((item for item in store.list() if item.id == key_id), None)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "API key not found.")
    return record


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> dict[str, bool]:
    enforce_scope(principal, "security:manage")
    record = store.revoke(key_id)
    if record is None:
        raise api_error(404, ErrorCode.AUTHENTICATION_FAILED, "API key not found.")
    return {"deleted": True}


@router.post("/api-keys/{key_id}/revoke", response_model=APIKeyRecord)
async def revoke_api_key(
    key_id: str,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> APIKeyRecord:
    enforce_scope(principal, "security:manage")
    record = store.revoke(key_id)
    if record is None:
        raise api_error(404, ErrorCode.AUTHENTICATION_FAILED, "API key not found.")
    return record
