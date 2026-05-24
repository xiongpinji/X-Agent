from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.agent import AgentLoop
from backend.app.core.contracts import AgentRunResponse, ErrorCode, RunContext, AgentPlanStepRecord, AgentRunRecord
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_agent, get_current_principal, get_run_store

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
AgentDependency = Annotated[AgentLoop, Depends(get_agent)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
RunStoreDependency = Annotated[object, Depends(get_run_store)]


class AgentRunRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=20_000)
    extra_context: dict[str, Any] = Field(default_factory=dict)
    resume_trace_id: str | None = None


class AgentRunStreamRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=20_000)
    extra_context: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponseModel(BaseModel):
    trace_id: str
    agent_id: str
    status: str
    answer: str = ""
    iterations: int = 0
    memory_hits: int = 0
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    execution_summary: dict[str, Any] = Field(default_factory=dict)
    snapshot: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class AgentSummaryResponse(BaseModel):
    agent_id: str
    status: str
    max_iterations: int
    memory_snapshot: dict[str, Any] = Field(default_factory=dict)
    tool_count: int = 0
    execution_summary: dict[str, Any] = Field(default_factory=dict)


class AgentRunHistoryResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentRunDetailResponse(BaseModel):
    run: dict[str, Any]
    snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentRunPlanResponse(BaseModel):
    trace_id: str
    agent_id: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentRunToolCallsResponse(BaseModel):
    trace_id: str
    agent_id: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentRunReplayResponse(BaseModel):
    trace_id: str
    agent_id: str
    run: dict[str, Any]
    plan: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    execution_summary: dict[str, Any] = Field(default_factory=dict)
    subtasks: list[str] = Field(default_factory=list)
    verifications: list[list[str]] = Field(default_factory=list)
    risks: list[list[str]] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    file_results: list[dict[str, Any]] = Field(default_factory=list)
    snapshot: dict[str, Any] = Field(default_factory=dict)


@router.get("/summary", response_model=AgentSummaryResponse)
async def get_agent_summary(agent: AgentDependency, principal: PrincipalDependency) -> AgentSummaryResponse:
    enforce_scope(principal, "agent:read")
    memory_snapshot = agent.memory.snapshot() if hasattr(agent.memory, "snapshot") else {}
    return AgentSummaryResponse(
        agent_id=principal.agent_id,
        status="active",
        max_iterations=agent.max_iterations,
        memory_snapshot=memory_snapshot,
        tool_count=len(agent.tools.manifest()),
        execution_summary={
            "capabilities": agent.tools.capability_index(),
            "tool_count": len(agent.tools.manifest()),
            "max_iterations": agent.max_iterations,
        },
    )


@router.post("/run", response_model=AgentRunResponseModel)
async def run_agent(
    request: AgentRunRequest,
    agent: AgentDependency,
    principal: PrincipalDependency,
    run_store: RunStoreDependency,
) -> AgentRunResponseModel:
    enforce_scope(principal, "agent:run")
    context = _context_from_principal(principal)
    result: AgentRunResponse = await agent.run(context, request.task, request.extra_context)
    if request.resume_trace_id:
        previous = run_store.continue_from(request.resume_trace_id, result)
        if previous is None:
            run_store.save(context, request.task, result)
    else:
        run_store.save(context, request.task, result)
    return AgentRunResponseModel(**result.model_dump())


@router.post("/run/stream", response_model=AgentRunResponseModel)
async def run_agent_stream(
    request: AgentRunStreamRequest,
    agent: AgentDependency,
    principal: PrincipalDependency,
    run_store: RunStoreDependency,
) -> AgentRunResponseModel:
    enforce_scope(principal, "agent:run")
    context = _context_from_principal(principal)
    result: AgentRunResponse = await agent.run(context, request.task, request.extra_context)
    if request.resume_trace_id:
        previous = run_store.continue_from(request.resume_trace_id, result)
        if previous is None:
            run_store.save(context, request.task, result)
    else:
        run_store.save(context, request.task, result)
    return AgentRunResponseModel(**result.model_dump())


@router.get("/runs", response_model=AgentRunHistoryResponse)
async def list_agent_runs(run_store: RunStoreDependency, principal: PrincipalDependency, limit: int = 20) -> AgentRunHistoryResponse:
    enforce_scope(principal, "agent:read")
    items = [record.model_dump(mode="json") for record in run_store.list(limit=limit)]
    return AgentRunHistoryResponse(items=items, snapshot={"count": len(items), "limit": limit})


@router.get("/runs/{trace_id}", response_model=AgentRunDetailResponse)
async def get_agent_run(trace_id: str, run_store: RunStoreDependency, principal: PrincipalDependency) -> AgentRunDetailResponse:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Agent run not found.", details={"resource_type": "agent_run", "resource_id": trace_id})
    return AgentRunDetailResponse(run={**record.model_dump(mode="json"), "stage": record.stage}, snapshot={"trace_id": trace_id, "tool_call_count": record.tool_call_count, "plan_steps": len(record.plan), "has_summary": bool(record.execution_summary), "stage": record.stage})


@router.get("/{agent_id}", response_model=AgentSummaryResponse)
async def get_agent_detail(agent_id: str, agent: AgentDependency, principal: PrincipalDependency) -> AgentSummaryResponse:
    enforce_scope(principal, "agent:read")
    if agent_id != principal.agent_id and agent_id != "default-agent":
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    memory_snapshot = agent.memory.snapshot() if hasattr(agent.memory, "snapshot") else {}
    return AgentSummaryResponse(
        agent_id=agent_id,
        status="active",
        max_iterations=agent.max_iterations,
        memory_snapshot=memory_snapshot,
        tool_count=len(agent.tools.manifest()),
        execution_summary={
            "capabilities": agent.tools.capability_index(),
            "tool_count": len(agent.tools.manifest()),
            "max_iterations": agent.max_iterations,
        },
    )


@router.get("/{agent_id}/runs", response_model=AgentRunHistoryResponse)
async def list_agent_runs(agent_id: str, run_store: RunStoreDependency, principal: PrincipalDependency, limit: int = 20) -> AgentRunHistoryResponse:
    enforce_scope(principal, "agent:read")
    items = []
    for record in run_store.list(limit=limit):
        if record.agent_id != agent_id:
            continue
        items.append({
            **record.model_dump(mode="json"),
            "id": record.trace_id,
            "trace_id": record.trace_id,
            "agent_id": record.agent_id,
            "resource_type": "agent_run",
            "snapshot": {
                "trace_id": record.trace_id,
                "agent_id": record.agent_id,
                "status": record.status.value,
                "tool_call_count": record.tool_call_count,
                "plan_count": len(record.plan),
                "execution_summary": record.execution_summary,
            },
            "ui": {
                "title": record.task,
                "subtitle": record.status.value,
                "badges": [record.status.value, f"tools:{record.tool_call_count}", f"steps:{len(record.plan)}"],
            },
        })
    return AgentRunHistoryResponse(items=items, snapshot={"count": len(items), "agent_id": agent_id})


@router.get("/{agent_id}/runs/{trace_id}", response_model=AgentRunDetailResponse)
async def get_agent_run_detail(agent_id: str, trace_id: str, run_store: RunStoreDependency, principal: PrincipalDependency) -> AgentRunDetailResponse:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None or record.agent_id != agent_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Agent run not found.", details={"resource_type": "agent_run", "resource_id": trace_id})
    return AgentRunDetailResponse(
        run={
            **record.model_dump(mode="json"),
            "id": record.trace_id,
            "trace_id": record.trace_id,
            "agent_id": record.agent_id,
            "resource_type": "agent_run",
        },
        snapshot={
            "trace_id": record.trace_id,
            "agent_id": record.agent_id,
            "status": record.status.value,
            "tool_call_count": record.tool_call_count,
            "plan_count": len(record.plan),
            "execution_summary": record.execution_summary,
            "subtasks": record.execution_summary.get("subtasks", []),
            "subtask_status": record.execution_summary.get("subtask_status", {}),
            "current_subtask_index": record.execution_summary.get("current_subtask_index", 0),
            "workflow": record.execution_summary.get("workflow", {}),
            "approval": record.execution_summary.get("approval", {}),
            "browser": record.execution_summary.get("browser", {}),
            "desktop": record.execution_summary.get("desktop", {}),
            "verifications": [step.verifications for step in record.plan],
            "risks": [step.risks for step in record.plan],
        },
    )


@router.get("/{agent_id}/runs/{trace_id}/plan", response_model=AgentRunPlanResponse)
async def get_agent_run_plan(agent_id: str, trace_id: str, run_store: RunStoreDependency, principal: PrincipalDependency) -> AgentRunPlanResponse:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None or record.agent_id != agent_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Agent run not found.", details={"resource_type": "agent_run", "resource_id": trace_id})
    items = [step.model_dump(mode="json") for step in record.plan]
    return AgentRunPlanResponse(trace_id=trace_id, agent_id=agent_id, items=items, snapshot={"trace_id": trace_id, "agent_id": agent_id, "plan_steps": len(items), "subtasks": record.execution_summary.get("subtasks", [])})


@router.get("/{agent_id}/runs/{trace_id}/tool-calls", response_model=AgentRunToolCallsResponse)
async def get_agent_run_tool_calls(agent_id: str, trace_id: str, run_store: RunStoreDependency, principal: PrincipalDependency) -> AgentRunToolCallsResponse:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None or record.agent_id != agent_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Agent run not found.", details={"resource_type": "agent_run", "resource_id": trace_id})
    items = [tool_call.model_dump(mode="json") for tool_call in record.tool_calls]
    return AgentRunToolCallsResponse(trace_id=trace_id, agent_id=agent_id, items=items, snapshot={"trace_id": trace_id, "agent_id": agent_id, "tool_call_count": record.tool_call_count, "successful_tools": record.execution_summary.get("successful_tools", []), "failed_tools": record.execution_summary.get("failed_tools", [])})


@router.get("/{agent_id}/runs/{trace_id}/replay", response_model=AgentRunReplayResponse)
async def get_agent_run_replay(agent_id: str, trace_id: str, run_store: RunStoreDependency, principal: PrincipalDependency) -> AgentRunReplayResponse:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None or record.agent_id != agent_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Agent run not found.", details={"resource_type": "agent_run", "resource_id": trace_id})
    plan = [step.model_dump(mode="json") for step in record.plan]
    tool_calls = [tool_call.model_dump(mode="json") for tool_call in record.tool_calls]
    subtasks = list(record.execution_summary.get("subtasks", []))
    verifications = [step.get("verifications", []) for step in plan]
    risks = [step.get("risks", []) for step in plan]
    affected_files = list(record.execution_summary.get("affected_files", []))
    file_results = list(record.execution_summary.get("file_results", []))
    return AgentRunReplayResponse(
        trace_id=trace_id,
        agent_id=agent_id,
        run=record.model_dump(mode="json"),
        plan=plan,
        tool_calls=tool_calls,
        execution_summary=record.execution_summary,
        subtasks=subtasks,
        verifications=verifications,
        risks=risks,
        affected_files=affected_files,
        file_results=file_results,
        snapshot={
            "trace_id": trace_id,
            "agent_id": agent_id,
            "plan_steps": len(plan),
            "tool_call_count": len(tool_calls),
            "subtasks": subtasks,
            "subtask_status": record.execution_summary.get("subtask_status", {}),
            "current_subtask_index": record.execution_summary.get("current_subtask_index", 0),
            "risks": risks,
            "verifications": verifications,
            "affected_files": affected_files,
            "file_results_count": len(file_results),
        },
    )


@router.get("/{agent_id}/correlation")
async def get_agent_correlation(agent_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:read")
    return {
        "agent_id": agent_id,
        "trace_id": principal.trace_id or principal.request_id or agent_id,
        "resource_type": "agent",
        "resource_id": agent_id,
        "snapshot": {
            "agent_id": agent_id,
            "tenant_id": principal.tenant_id,
            "user_id": principal.user_id,
            "request_id": principal.request_id,
            "trace_id": principal.trace_id,
        },
    }


@router.post("/{agent_id}/pause")
async def pause_agent(agent_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:manage")
    return {"agent_id": agent_id, "status": "paused"}


@router.post("/{agent_id}/resume")
async def resume_agent(agent_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:manage")
    return {"agent_id": agent_id, "status": "active"}


@router.post("/{agent_id}/cancel")
async def cancel_agent(agent_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:manage")
    return {"agent_id": agent_id, "status": "canceled"}


@router.post("/{agent_id}/focus")
async def focus_agent(agent_id: str, payload: dict[str, Any] | None = None, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "agent:manage")
    payload = payload or {}
    return {
        "agent_id": agent_id,
        "status": "accepted",
        "focus": payload.get("focus", "task"),
        "snapshot": payload,
    }


@router.post("/{agent_id}/delegate")
async def delegate_agent_task(agent_id: str, payload: dict[str, Any] | None = None, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "agent:manage")
    payload = payload or {}
    return {
        "agent_id": agent_id,
        "status": "accepted",
        "task": payload.get("task", ""),
        "children": payload.get("children", []),
        "preferred_domains": payload.get("preferred_domains", []),
        "preferred_capabilities": payload.get("preferred_capabilities", []),
    }


def _context_from_principal(principal: Principal) -> RunContext:
    return RunContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        agent_id=principal.agent_id,
        request_id=principal.request_id,
        trace_id=principal.trace_id,
        permission_scope=principal.permission_scope,
    )
