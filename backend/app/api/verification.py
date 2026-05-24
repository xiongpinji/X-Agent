from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.core.test_mapper import test_mapper
from backend.app.core.verification import VerificationEngine
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/verification", tags=["verification"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

_verification_engine = VerificationEngine()


@router.post("/draft")
async def draft_verification(payload: dict[str, object], principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    task = str(payload.get("task", ""))
    test_mapping = test_mapper.map(task, limit=int(payload.get("limit", 10)))
    verification = _verification_engine.summarize_run([], test_mapping=test_mapping)
    return {
        "task": task,
        "test_mapping": test_mapping.__dict__,
        "verification": verification,
    }
