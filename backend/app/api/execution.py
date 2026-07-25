from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.code_index import code_index
from backend.app.core.contracts import ErrorCode
from backend.app.core.dispatch import DispatchRequest, dispatch
from backend.app.core.execution_planner import execution_planner
from backend.app.core.security import Principal
from backend.app.core.test_mapper import test_mapper
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.settings import PROJECT_ROOT

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def _resolve_allowed_root(root: str) -> Path:
    base = Path(PROJECT_ROOT).resolve()
    requested = Path(root).expanduser().resolve()
    try:
        requested.relative_to(base)
    except ValueError:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Root path must be within the project directory.")
    return requested


@router.post("/draft")
async def draft_execution(payload: dict[str, object], principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    task = str(payload.get("task", ""))
    root = str(payload.get("root", "."))
    _resolve_allowed_root(root)
    code_index.index(root=root, limit=int(payload.get("limit", 500)))
    mapping = test_mapper.map(task, limit=int(payload.get("limit", 10)))
    plan = execution_planner.build(task, test_mapping=mapping)
    dispatch_result = dispatch(
        DispatchRequest(
            org_id=str(payload.get("org_id") or principal.tenant_id),
            department_id=(payload.get("department_id") and str(payload.get("department_id"))) or None,
            agent_id=(payload.get("agent_id") and str(payload.get("agent_id"))) or principal.agent_id,
            room_id=(payload.get("room_id") and str(payload.get("room_id"))) or None,
            session_id=(payload.get("session_id") and str(payload.get("session_id"))) or principal.session_id,
            trace_id=(payload.get("trace_id") and str(payload.get("trace_id"))) or principal.trace_id,
            task=task,
            task_type=str(payload.get("task_type") or "execution"),
            priority=int(payload.get("priority", 0)),
            summary=str(payload.get("summary") or task),
            mode=str(payload.get("mode") or "suggest"),
            replay_hint=bool(payload.get("replay_hint", False)),
        )
    )
    return {
        "task": task,
        "dispatch": dispatch_result.model_dump(mode="json"),
        "dispatch_next_actions": [action.model_dump(mode="json") if hasattr(action, "model_dump") else action for action in dispatch_result.suggestion.next_actions],
        "execution_plan": dataclasses.asdict(plan),
        "suggested_test_commands": plan.suggested_test_commands,
    }
