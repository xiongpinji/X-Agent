from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.dispatch import DispatchRequest, DispatchResult, dispatch
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.post("", response_model=DispatchResult)
async def dispatch_route(request: DispatchRequest, principal: PrincipalDependency) -> DispatchResult:
    enforce_scope(principal, "agent:run")
    return dispatch(request)
