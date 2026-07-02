from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.second_batch_capabilities import build_second_batch_capability_manifest
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/capabilities", tags=["capabilities"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/second-batch")
async def second_batch_capabilities(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "audit:read")
    return build_second_batch_capability_manifest()
