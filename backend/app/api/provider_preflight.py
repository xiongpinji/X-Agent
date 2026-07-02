from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.core.provider_preflight import PROVIDER_STATUSES, build_provider_preflight
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/providers", tags=["provider-preflight"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/preflight")
async def provider_preflight(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "audit:read")
    providers = build_provider_preflight()
    invalid_statuses = [
        item["status"]
        for item in providers
        if item.get("status") not in PROVIDER_STATUSES
    ]
    return {
        "status": "failed" if invalid_statuses else "passed",
        "dry_run": True,
        "network_mutation_performed": False,
        "providers": providers,
        "known_limits": [
            "This endpoint inspects configuration shape only; it does not call external providers.",
            "ready_to_call is not proof that the remote provider accepts requests.",
        ],
    }
