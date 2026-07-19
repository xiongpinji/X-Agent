from __future__ import annotations

import dataclasses

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.code_index import code_index
from backend.app.core.execution_planner import execution_planner
from backend.app.core.security import Principal
from backend.app.core.test_mapper import test_mapper
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/planning", tags=["planning"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.post("/draft")
async def draft_planning(payload: dict[str, object], principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    task = str(payload.get("task", ""))
    root = str(payload.get("root", "."))
    code_index.index(root=root, limit=int(payload.get("limit", 500)))
    mapping = test_mapper.map(task, limit=int(payload.get("limit", 10)))
    plan = execution_planner.build(task, test_mapping=mapping)
    return {
        "task": task,
        "code_index": {
            "related_files": code_index.related_files(task, limit=10),
            "impact_hints": code_index.impact_hints(task, limit=10),
            "test_files": code_index.test_files_for(task, limit=10),
        },
        "test_mapping": mapping.__dict__,
        "execution_plan": dataclasses.asdict(plan),
    }
