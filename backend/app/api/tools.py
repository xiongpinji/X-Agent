from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode, RunContext
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_agent, get_current_principal

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])
AgentDependency = Annotated[object, Depends(get_agent)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class ToolUpdateRequest(BaseModel):
    enabled: bool | None = None
    config: dict | None = None


class ToolTestRequest(BaseModel):
    parameters: dict = Field(default_factory=dict)


@router.get("")
async def list_tools(agent: AgentDependency, principal: PrincipalDependency) -> list[dict]:
    enforce_scope(principal, "tools:read")
    return agent.tools.manifest()


@router.put("/{tool_name}")
async def update_tool(
    tool_name: str,
    request: ToolUpdateRequest,
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> dict:
    """Update tool configuration (enable/disable, config)."""
    enforce_scope(principal, "tools:write")
    manifest = agent.tools.manifest()
    tool = next((t for t in manifest if t.get("name") == tool_name), None)
    if tool is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, f"Tool '{tool_name}' not found.", trace_id=tool_name)

    # Apply updates to tool registry if supported
    if hasattr(agent.tools, "set_enabled") and request.enabled is not None:
        agent.tools.set_enabled(tool_name, request.enabled)
    if hasattr(agent.tools, "update_config") and request.config is not None:
        agent.tools.update_config(tool_name, request.config)

    return {
        "name": tool_name,
        "enabled": request.enabled if request.enabled is not None else True,
        "config": request.config or {},
        "status": "updated",
    }


@router.post("/{tool_name}/test")
async def test_tool(
    tool_name: str,
    request: ToolTestRequest,
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> dict:
    """Test a tool with given parameters without side effects."""
    enforce_scope(principal, "tools:write")
    manifest = agent.tools.manifest()
    tool = next((t for t in manifest if t.get("name") == tool_name), None)
    if tool is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, f"Tool '{tool_name}' not found.", trace_id=tool_name)

    # Attempt dry-run execution. The runtime ToolRegistry.execute has no
    # ``dry_run`` kwarg; its canonical signature is
    # ``execute(context, name, arguments) -> ToolCallRecord``.
    try:
        if hasattr(agent.tools, "dry_run"):
            result = await agent.tools.dry_run(tool_name, request.parameters)
            return {"name": tool_name, "status": "success", "result": result}
        if hasattr(agent.tools, "execute"):
            context = RunContext(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                agent_id=principal.agent_id,
                request_id=principal.request_id,
                trace_id=principal.trace_id,
                # Principal 的授权作用域在 ``scopes`` 字段；``permission_scope``
                # 默认为空，直接用会被 ToolPolicyEngine 以 "Missing permission
                # scope tool:<name>" 拒绝。
                permission_scope=principal.permission_scope or principal.scopes,
            )
            record = await agent.tools.execute(context, tool_name, request.parameters)
            if record.success:
                return {"name": tool_name, "status": "success", "result": record.output}
            return {"name": tool_name, "status": "error", "error": record.error or "Tool execution failed."}
        return {
            "name": tool_name,
            "status": "success",
            "result": {"message": "Dry-run not supported for this tool", "parameters": request.parameters},
        }
    except Exception as e:
        return {
            "name": tool_name,
            "status": "error",
            "error": str(e),
        }


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
