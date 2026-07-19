from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.dependencies import get_agent, get_current_principal, enforce_scope
from backend.app.core.security import Principal

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])
AgentDependency = Annotated[object, Depends(get_agent)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("")
async def list_tools(agent: AgentDependency, principal: PrincipalDependency) -> list[dict]:
    enforce_scope(principal, "tools:read")
    return agent.tools.manifest()


@router.get("/executions/{execution_id}")
async def get_tool_execution(execution_id: str, agent: AgentDependency, principal: PrincipalDependency) -> dict:
    enforce_scope(principal, "agent:run")
    store = agent.tools.get_execution_store()
    if store is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Tool execution store not available.", trace_id=execution_id)
    record = store.get(execution_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Tool execution not found.", trace_id=execution_id)
    return record.model_dump(mode="json")


@router.get("/executions/{execution_id}/correlation")
async def get_tool_execution_correlation(execution_id: str, agent: AgentDependency, principal: PrincipalDependency) -> dict:
    enforce_scope(principal, "agent:run")
    store = agent.tools.get_execution_store()
    if store is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Tool execution store not available.", trace_id=execution_id)
    record = store.get(execution_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Tool execution not found.", trace_id=execution_id)
    return {
        "trace_id": record.trace_id,
        "resource_type": "tool_execution",
        "resource_id": record.execution_id,
        "tool_name": record.tool_name,
        "status": "completed" if record.success else "failed",
        "trace_summary": {
            "trace_id": record.trace_id,
            "event_count": 1,
            "started_at": record.created_at,
            "ended_at": record.updated_at,
            "last_event": "tool.execution.completed" if record.success else "tool.execution.failed",
            "task": record.tool_name,
            "snapshot": {
                "resource_type": "tool_execution",
                "resource_id": record.execution_id,
                "trace_id": record.trace_id,
                "tool_name": record.tool_name,
                "success": record.success,
            },
        },
        "snapshot": {
            "resource_type": "tool_execution",
            "resource_id": record.execution_id,
            "trace_id": record.trace_id,
            "tool_name": record.tool_name,
            "tenant_id": record.tenant_id,
            "user_id": record.user_id,
            "success": record.success,
        },
    }
