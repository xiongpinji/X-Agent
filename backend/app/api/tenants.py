from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.admin import TenantCreateRequest, TenantUpdateRequest, tenant_store
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.post("")
async def create_tenant(request: TenantCreateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return tenant_store.create(request).model_dump(mode="json")


@router.get("")
async def list_tenants(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return {"data": [item.model_dump(mode="json") for item in tenant_store.list()]}


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = tenant_store.get(tenant_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Tenant not found.", details={"resource_type": "tenant", "resource_id": tenant_id})
    return record.model_dump(mode="json")


@router.put("/{tenant_id}")
async def update_tenant(tenant_id: str, request: TenantUpdateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return tenant_store.upsert(request, tenant_id).model_dump(mode="json")


@router.get("/{tenant_id}/usage")
async def get_tenant_usage(tenant_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = tenant_store.get(tenant_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Tenant not found.", details={"resource_type": "tenant", "resource_id": tenant_id})
    return {"tenant_id": tenant_id, "usage": {"runs": 0, "agents": 0, "memory": 0}}


@router.get("/{tenant_id}/billing")
async def get_tenant_billing(tenant_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = tenant_store.get(tenant_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Tenant not found.", details={"resource_type": "tenant", "resource_id": tenant_id})
    return {"tenant_id": tenant_id, "plan": record.plan, "billing": {"amount": 0, "currency": "USD"}}


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str, principal: PrincipalDependency) -> dict[str, bool]:
    enforce_scope(principal, "security:manage")
    if not tenant_store.delete(tenant_id):
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Tenant not found.", details={"resource_type": "tenant", "resource_id": tenant_id})
    return {"deleted": True}
