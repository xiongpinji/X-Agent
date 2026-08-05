"""P2-01: 多 Agent 协作编排 API.

端点:
- POST /api/v1/multi-agent/execute — 提交编排计划并执行
- POST /api/v1/multi-agent/decompose — 任务分解(返回计划不执行)
- GET  /api/v1/multi-agent/executions/{id} — 查询执行状态
- GET  /api/v1/multi-agent/executions — 执行历史列表

P1-09 Collaboration Module Convergence
---------------------------------------
This is ONE of three distinct multi-agent API surfaces (NOT duplicates):

- collaboration  /api/v1/collaboration
    Shared-context rooms, messaging, delegation.
    Use when agents need shared context / chat / hand-off.

- multi_agent (THIS)  /api/v1/multi-agent
    Structured orchestration (decompose -> execute with dependencies).
    Use for task decomposition + dependency-ordered execution.

- parallel_agents  /api/v1/agents/parallel
    Independent fan-out execution + communication bus.
    Use for N independent tasks run concurrently.

Cross-references:
    - backend.app.api.collaboration (collaboration rooms API)
    - backend.app.api.parallel_agents (parallel execution API)
    - backend.app.core.collaboration.orchestrator (core orchestrator)
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.collaboration.orchestrator import (
    FailurePolicy,
    OrchestrationMode,
    OrchestrationPlan,
    SubTask,
    get_multi_agent_orchestrator,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/multi-agent", tags=["multi-agent"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# 挂载状态（P1-09 批次 E-lite，2026-08-04）：orchestrator 假实现已真实化、
# 本 API 已补鉴权与租户上下文注入，达到可挂载状态；当前仍**不挂载**——
# 挂载 +4 路由会顶满 G3（300/300），留待路由预算评审。decompose_task 为
# 规则分解（关键词启发式），非 LLM 分解。


# ─── 请求/响应模型 ─────────────────────────────────────────────────────────────


class SubTaskRequest(BaseModel):
    description: str
    required_capabilities: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class ExecuteRequest(BaseModel):
    task: str = Field(..., description="任务描述")
    mode: str = Field("parallel", description="编排模式: parallel/sequential/hierarchical")
    subtasks: list[SubTaskRequest] | None = Field(None, description="自定义子任务(为空则自动分解)")
    failure_policy: str = Field("retry", description="失败策略: retry/skip/abort")
    max_concurrency: int = Field(5, ge=1, le=20)
    timeout_seconds: int = Field(600, ge=10, le=3600)
    context: dict[str, Any] = Field(default_factory=dict)


class DecomposeRequest(BaseModel):
    task: str = Field(..., description="任务描述")
    context: dict[str, Any] = Field(default_factory=dict)


class ExecutionResponse(BaseModel):
    execution_id: str
    plan_id: str
    status: str
    total_subtasks: int
    completed: int
    failed: int
    skipped: int
    results: dict[str, Any]
    started_at: str
    completed_at: str | None
    duration_ms: int


class PlanResponse(BaseModel):
    plan_id: str
    task: str
    mode: str
    subtasks: list[dict[str, Any]]
    failure_policy: str
    max_concurrency: int
    timeout_seconds: int
    created_at: str


# ─── 端点 ─────────────────────────────────────────────────────────────────────


@router.post("/execute", response_model=ExecutionResponse)
async def execute_orchestration(req: ExecuteRequest, principal: PrincipalDependency):
    """提交编排计划并执行."""
    enforce_scope(principal, "agent:run")
    orchestrator = get_multi_agent_orchestrator()
    # 租户/用户上下文注入委派路径（不信任客户端 context 中的同名字段）
    tenant_context = {
        **dict(req.context),
        "tenant_id": principal.tenant_id,
        "user_id": principal.user_id,
    }

    # 构建计划
    if req.subtasks:
        subtasks = [
            SubTask(
                description=st.description,
                required_capabilities=st.required_capabilities,
                depends_on=st.depends_on,
            )
            for st in req.subtasks
        ]
        plan = OrchestrationPlan(
            task=req.task,
            mode=OrchestrationMode(req.mode),
            subtasks=subtasks,
            failure_policy=FailurePolicy(req.failure_policy),
            max_concurrency=req.max_concurrency,
            timeout_seconds=req.timeout_seconds,
            context=tenant_context,
        )
    else:
        plan = orchestrator.decompose_task(req.task, tenant_context)
        plan.mode = OrchestrationMode(req.mode)
        plan.failure_policy = FailurePolicy(req.failure_policy)
        plan.max_concurrency = req.max_concurrency
        plan.timeout_seconds = req.timeout_seconds

    result = await orchestrator.execute(plan)
    return ExecutionResponse(**result.to_dict())


@router.post("/decompose", response_model=PlanResponse)
async def decompose_task(req: DecomposeRequest, principal: PrincipalDependency):
    """任务分解(返回计划不执行). 规则分解（关键词启发式），非 LLM 分解。"""
    enforce_scope(principal, "agent:run")
    orchestrator = get_multi_agent_orchestrator()
    plan = orchestrator.decompose_task(req.task, req.context)
    return PlanResponse(**plan.to_dict())


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(execution_id: str, principal: PrincipalDependency):
    """查询执行状态."""
    enforce_scope(principal, "agent:run")
    orchestrator = get_multi_agent_orchestrator()
    result = orchestrator.get_execution(execution_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
    return ExecutionResponse(**result.to_dict())


@router.get("/executions", response_model=list[ExecutionResponse])
async def list_executions(principal: PrincipalDependency, limit: int = Query(20, ge=1, le=100)):
    """执行历史列表."""
    enforce_scope(principal, "agent:run")
    orchestrator = get_multi_agent_orchestrator()
    executions = orchestrator.list_executions(limit)
    return [ExecutionResponse(**e.to_dict()) for e in executions]
