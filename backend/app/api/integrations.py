from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class IntegrationConnectionRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=80)
    enabled: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)


class IntegrationMessageRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=80)
    target_id: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=20_000)
    metadata: dict[str, object] = Field(default_factory=dict)


_INTEGRATIONS: dict[str, dict[str, object]] = {}


@router.get("")
async def list_integrations(principal: PrincipalDependency) -> list[dict[str, object]]:
    enforce_scope(principal, "security:manage")
    return list(_INTEGRATIONS.values())


@router.post("")
async def create_integration(request: IntegrationConnectionRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = {
        "provider": request.provider,
        "enabled": request.enabled,
        "metadata": request.metadata,
    }
    _INTEGRATIONS[request.provider] = record
    return record


@router.get("/{provider}")
async def get_integration(provider: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = _INTEGRATIONS.get(provider)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Integration not found.", details={"provider": provider})
    return record


@router.post("/{provider}/send")
async def send_integration_message(provider: str, request: IntegrationMessageRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = _INTEGRATIONS.get(provider)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Integration not found.", details={"provider": provider})
    return {
        "provider": provider,
        "target_id": request.target_id,
        "accepted": bool(record.get("enabled", False)),
        "message": request.content,
        "metadata": request.metadata,
    }
