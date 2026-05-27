from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.core.dispatch import DispatchRequest, dispatch
from backend.app.core.execution_planner import execution_planner
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/execution-control", tags=["execution-control"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class ExecutionControlOverviewResponse(BaseModel):
    resource_type: str = "execution_control_overview"
    resource_id: str
    primary: dict[str, object]
    linked_summaries: dict[str, object]


class ExecutionControlDetailResponse(BaseModel):
    resource_type: str = "execution_control_detail"
    resource_id: str
    primary: dict[str, object]
    linked_summaries: dict[str, object]


class ExecutionControlRecoveryResponse(BaseModel):
    resource_type: str = "execution_control_recovery"
    resource_id: str
    primary: dict[str, object]
    linked_summaries: dict[str, object]


class ExecutionControlDispatchResponse(BaseModel):
    resource_type: str = "execution_control_dispatch"
    resource_id: str
    primary: dict[str, object]
    linked_summaries: dict[str, object]


class ExecutionControlIdentifiers(BaseModel):
    run_id: str = Field(default="execution-control")


@router.get("/overview", response_model=ExecutionControlOverviewResponse)
async def get_execution_overview(principal: PrincipalDependency) -> ExecutionControlOverviewResponse:
    enforce_scope(principal, "agent:run")
    dispatch_result = dispatch(
        DispatchRequest(
            org_id=principal.tenant_id,
            agent_id=principal.agent_id,
            session_id=principal.session_id,
            trace_id=principal.trace_id,
            task="execution control overview",
            task_type="execution_overview",
            mode="suggest",
            replay_hint=True,
        )
    )
    plan = execution_planner.build("execution control overview")
    plan_dump = plan.__dict__ if hasattr(plan, "__dict__") else {}
    dispatch_dump = dispatch_result.model_dump(mode="json")
    return ExecutionControlOverviewResponse(
        resource_id=principal.session_id or principal.user_id,
        primary={
            "active_runs": 6,
            "pending_runs": 4,
            "failed_runs": 1,
            "completed_runs": 12,
            "intervention_count": 1,
            "risk_level": "medium",
            "source": "execution_control/overview",
            "priority_focus": "failed_runs",
            "dispatch": dispatch_dump,
            "execution_plan": plan_dump,
        },
        linked_summaries={
            "dispatch": {"summary": {"title": "execution overview dispatch"}, "data": dispatch_dump},
            "execution": {"summary": {"title": "execution plan"}, "data": plan_dump},
            "audit": {"summary": {"title": "audit reference"}, "data": {"status": "pending", "count": 0}},
            "messages": {"summary": {"title": "message reference"}, "data": {"status": "pending", "count": 0}},
        },
    )


@router.get("/detail/{run_id}", response_model=ExecutionControlDetailResponse)
async def get_execution_detail(run_id: str, principal: PrincipalDependency) -> ExecutionControlDetailResponse:
    enforce_scope(principal, "agent:run")
    return ExecutionControlDetailResponse(
        resource_id=run_id,
        primary={
            "run_id": run_id,
            "task_name": "工具调用工作流",
            "status": "running",
            "trigger_source": "workflow",
            "owner": principal.agent_id or principal.user_id,
            "current_step": "tool.execute",
            "progress": 72,
            "result_summary": "等待工具返回",
            "current_step_label": "调用工具",
            "progress_label": "72%",
            "risk_level": "medium",
        },
        linked_summaries={
            "workflow": {"summary": {"title": "workflow trace"}, "data": {"status": "running", "steps": 4}},
            "dispatch": {"summary": {"title": "dispatch trace"}, "data": {"suggested_action": "优先重试工具调用"}},
            "messages": {"summary": {"title": "message trace"}, "data": {"count": 12, "latest": None}},
            "tools": {"summary": {"title": "tool calls"}, "data": {"count": 3, "active": 1}},
            "audit": {"summary": {"title": "audit trail"}, "data": {"count": 5, "status": "pending"}},
            "memory": {"summary": {"title": "memory refs"}, "data": {"count": 2, "status": "available"}},
            "recovery": {"summary": {"title": "recovery hint"}, "data": {"can_retry": True, "can_rollback": True}},
        },
    )


@router.get("/recovery/{run_id}", response_model=ExecutionControlRecoveryResponse)
async def get_execution_recovery(run_id: str, principal: PrincipalDependency) -> ExecutionControlRecoveryResponse:
    enforce_scope(principal, "agent:run")
    return ExecutionControlRecoveryResponse(
        resource_id=run_id,
        primary={
            "run_id": run_id,
            "status": "recoverable",
            "failure_level": "medium",
            "failure_reason": "tool timeout",
            "current_step": "tool.execute",
            "can_retry": True,
            "can_rollback": True,
            "needs_human": False,
            "retry_priority": "high",
            "recovery_mode": "automatic-first",
        },
        linked_summaries={
            "workflow": {"summary": {"title": "workflow trace"}, "data": {"status": "running", "steps": 4}},
            "dispatch": {"summary": {"title": "dispatch result"}, "data": {"suggested_action": "优先重试工具调用"}},
            "messages": {"summary": {"title": "message evidence"}, "data": {"count": 12, "status": "available"}},
            "tools": {"summary": {"title": "tool evidence"}, "data": {"count": 3, "last_error": "timeout"}},
            "audit": {"summary": {"title": "audit evidence"}, "data": {"count": 5, "status": "pending"}},
            "memory": {"summary": {"title": "memory evidence"}, "data": {"count": 2, "status": "available"}},
            "recovery": {"summary": {"title": "recovery plan"}, "data": {"can_retry": True, "can_rollback": True, "needs_human": False}},
        },
    )


@router.get("/dispatch/{run_id}", response_model=ExecutionControlDispatchResponse)
async def get_execution_dispatch(run_id: str, principal: PrincipalDependency) -> ExecutionControlDispatchResponse:
    enforce_scope(principal, "agent:run")
    return ExecutionControlDispatchResponse(
        resource_id=run_id,
        primary={
            "run_id": run_id,
            "suggested_action": "优先重试工具调用",
            "confidence": 0.92,
            "risk_level": "low",
            "requires_confirmation": False,
            "impact_summary": "恢复执行并继续当前任务",
            "recommended_order": ["重试", "校验工具", "继续执行"],
            "decision_reason": "当前失败集中在外部工具超时。",
        },
        linked_summaries={
            "workflow": {"summary": {"title": "workflow basis"}, "data": {"status": "running", "steps": 4}},
            "execution": {"summary": {"title": "execution context"}, "data": {"current_step": "tool.execute", "progress": 72}},
            "dispatch": {"summary": {"title": "dispatch reasoning"}, "data": {"confidence": 0.92, "risk_level": "low"}},
            "audit": {"summary": {"title": "audit reference"}, "data": {"count": 5, "status": "pending"}},
            "messages": {"summary": {"title": "message reference"}, "data": {"count": 12, "status": "available"}},
            "tools": {"summary": {"title": "tool reference"}, "data": {"count": 3, "last_error": "timeout"}},
        },
    )
