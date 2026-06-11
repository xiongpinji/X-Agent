from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.agent import AgentLoop
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import ErrorCode, RunContext
from backend.app.core.control_modes import (
    ControlModeStore,
    GoalAdvanceRequest,
    GoalCreateRequest,
    GoalLoopService,
    GoalRecord,
    GoalStatus,
    PlanModeDecisionRequest,
    PlanModeDraftRequest,
    PlanModeRecord,
    PlanModeService,
)
from backend.app.core.runs import RunStore
from backend.app.core.security import Principal
from backend.app.dependencies import (
    enforce_scope,
    get_agent,
    get_audit_store,
    get_control_mode_store,
    get_current_principal,
    get_run_store,
)

router = APIRouter(prefix="/api/v1/control", tags=["control"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
StoreDependency = Annotated[ControlModeStore, Depends(get_control_mode_store)]
AgentDependency = Annotated[AgentLoop, Depends(get_agent)]
RunStoreDependency = Annotated[RunStore, Depends(get_run_store)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]


@router.post("/plans", response_model=PlanModeRecord)
async def draft_plan_mode(
    request: PlanModeDraftRequest,
    principal: PrincipalDependency,
    store: StoreDependency,
    audit_store: AuditStoreDependency,
) -> PlanModeRecord:
    """Create a plan-only draft for approval before execution."""
    enforce_scope(principal, "agent:run")
    record = PlanModeService().draft(
        request,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )
    store.save_plan(record)
    _record_audit(
        "control.plan.draft",
        principal,
        "control_plan",
        record.plan_id,
        {"task_preview": request.task[:160], "status": record.status.value},
        audit_store=audit_store,
    )
    return record


@router.get("/plans", response_model=list[PlanModeRecord])
async def list_plan_mode_records(
    principal: PrincipalDependency,
    store: StoreDependency,
    limit: int = 50,
) -> list[PlanModeRecord]:
    enforce_scope(principal, "agent:read")
    return store.list_plans(tenant_id=principal.tenant_id, limit=limit)


@router.get("/plans/{plan_id}", response_model=PlanModeRecord)
async def get_plan_mode_record(
    plan_id: str,
    principal: PrincipalDependency,
    store: StoreDependency,
) -> PlanModeRecord:
    enforce_scope(principal, "agent:read")
    record = _get_plan_for_principal(plan_id, principal, store)
    return record


@router.post("/plans/{plan_id}/approve", response_model=PlanModeRecord)
async def approve_plan_mode(
    plan_id: str,
    request: PlanModeDecisionRequest,
    principal: PrincipalDependency,
    store: StoreDependency,
    audit_store: AuditStoreDependency,
) -> PlanModeRecord:
    enforce_scope(principal, "agent:run")
    _get_plan_for_principal(plan_id, principal, store)
    record = store.approve_plan(plan_id, actor_id=principal.user_id, reason=request.reason)
    if record is None:
        raise _not_found("control_plan", plan_id)
    _record_audit(
        "control.plan.approve",
        principal,
        "control_plan",
        plan_id,
        {"reason": request.reason[:500]},
        audit_store=audit_store,
    )
    return record


@router.post("/plans/{plan_id}/reject", response_model=PlanModeRecord)
async def reject_plan_mode(
    plan_id: str,
    request: PlanModeDecisionRequest,
    principal: PrincipalDependency,
    store: StoreDependency,
    audit_store: AuditStoreDependency,
) -> PlanModeRecord:
    enforce_scope(principal, "agent:run")
    _get_plan_for_principal(plan_id, principal, store)
    record = store.reject_plan(plan_id, actor_id=principal.user_id, reason=request.reason)
    if record is None:
        raise _not_found("control_plan", plan_id)
    _record_audit(
        "control.plan.reject",
        principal,
        "control_plan",
        plan_id,
        {"reason": request.reason[:500]},
        audit_store=audit_store,
    )
    return record


@router.post("/goals", response_model=GoalRecord)
async def create_goal(
    request: GoalCreateRequest,
    principal: PrincipalDependency,
    store: StoreDependency,
    audit_store: AuditStoreDependency,
) -> GoalRecord:
    """Create a persistent loop-engineering goal with an initial plan."""
    enforce_scope(principal, "agent:run")
    goal, plan = GoalLoopService().create(
        request,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )
    store.save_plan(plan)
    store.save_goal(goal)
    _record_audit(
        "control.goal.create",
        principal,
        "control_goal",
        goal.goal_id,
        {
            "plan_id": plan.plan_id,
            "objective_preview": request.objective[:160],
            "status": goal.status.value,
        },
        audit_store=audit_store,
    )
    return goal


@router.get("/goals", response_model=list[GoalRecord])
async def list_goals(
    principal: PrincipalDependency,
    store: StoreDependency,
    limit: int = 50,
) -> list[GoalRecord]:
    enforce_scope(principal, "agent:read")
    return store.list_goals(tenant_id=principal.tenant_id, limit=limit)


@router.get("/goals/{goal_id}", response_model=GoalRecord)
async def get_goal(
    goal_id: str,
    principal: PrincipalDependency,
    store: StoreDependency,
) -> GoalRecord:
    enforce_scope(principal, "agent:read")
    return _get_goal_for_principal(goal_id, principal, store)


@router.post("/goals/{goal_id}/advance", response_model=GoalRecord)
async def advance_goal(
    goal_id: str,
    request: GoalAdvanceRequest,
    principal: PrincipalDependency,
    store: StoreDependency,
    agent: AgentDependency,
    run_store: RunStoreDependency,
    audit_store: AuditStoreDependency,
) -> GoalRecord:
    """Advance a goal by one loop-engineering iteration.

    By default this is plan-only. Set ``execute=true`` to run the agent for the
    next iteration after plan approval.
    """
    enforce_scope(principal, "agent:run")
    goal = _get_goal_for_principal(goal_id, principal, store)
    plan = store.get_plan(goal.plan_id) if goal.plan_id else None
    service = GoalLoopService()

    merged_context = {**goal.context, **request.context}
    if not request.execute:
        goal = service.advance_without_execution(
            goal,
            plan,
            force=request.force,
            user_feedback=request.user_feedback,
        )
        goal.context = merged_context
        store.save_goal(goal)
        _record_audit(
            "control.goal.advance.plan",
            principal,
            "control_goal",
            goal.goal_id,
            {"execute": False, "status": goal.status.value},
            audit_store=audit_store,
        )
        return goal

    if goal.status in {GoalStatus.COMPLETED, GoalStatus.CANCELED} and not request.force:
        raise api_error(
            409,
            ErrorCode.RESOURCE_CONFLICT,
            "Goal is already closed.",
            details={"goal_id": goal_id, "status": goal.status.value},
        )

    planned = service.advance_without_execution(
        goal.model_copy(deep=True),
        plan,
        force=request.force,
        user_feedback=request.user_feedback,
    )
    if planned.status == GoalStatus.WAITING_APPROVAL and not request.force:
        store.save_goal(planned)
        return planned
    if planned.status != GoalStatus.ACTIVE or not planned.iterations:
        store.save_goal(planned)
        return planned

    iteration_task = planned.iterations[-1].task if planned.iterations else goal.objective
    context = _run_context_from_principal(principal)
    result = await agent.run(
        context,
        iteration_task,
        {
            **merged_context,
            "goal_id": goal.goal_id,
            "plan_id": goal.plan_id,
            "loop_engineering": True,
            "phase_order": ["explore", "plan", "edit", "verify", "deliver"],
        },
    )
    run_store.save(context, iteration_task, result)
    updated = service.record_execution_result(
        goal,
        task=iteration_task,
        result=result,
        plan=plan,
    )
    updated.context = merged_context
    store.save_goal(updated)
    _record_audit(
        "control.goal.advance.execute",
        principal,
        "control_goal",
        updated.goal_id,
        {
            "execute": True,
            "trace_id": result.trace_id,
            "status": updated.status.value,
            "stop_reason": updated.stop_reason.value,
        },
        trace_id=result.trace_id,
        run_id=result.trace_id,
        audit_store=audit_store,
    )
    return updated


@router.post("/goals/{goal_id}/cancel", response_model=GoalRecord)
async def cancel_goal(
    goal_id: str,
    request: PlanModeDecisionRequest,
    principal: PrincipalDependency,
    store: StoreDependency,
    audit_store: AuditStoreDependency,
) -> GoalRecord:
    enforce_scope(principal, "agent:run")
    goal = _get_goal_for_principal(goal_id, principal, store)
    goal = GoalLoopService().cancel(goal, reason=request.reason)
    store.save_goal(goal)
    _record_audit(
        "control.goal.cancel",
        principal,
        "control_goal",
        goal.goal_id,
        {"reason": request.reason[:500]},
        audit_store=audit_store,
    )
    return goal


def _get_plan_for_principal(
    plan_id: str,
    principal: Principal,
    store: ControlModeStore,
) -> PlanModeRecord:
    record = store.get_plan(plan_id)
    if record is None or record.tenant_id != principal.tenant_id:
        raise _not_found("control_plan", plan_id)
    return record


def _get_goal_for_principal(
    goal_id: str,
    principal: Principal,
    store: ControlModeStore,
) -> GoalRecord:
    record = store.get_goal(goal_id)
    if record is None or record.tenant_id != principal.tenant_id:
        raise _not_found("control_goal", goal_id)
    return record


def _not_found(resource_type: str, resource_id: str) -> Exception:
    return api_error(
        404,
        ErrorCode.RESOURCE_NOT_FOUND,
        "Control resource not found.",
        details={"resource_type": resource_type, "resource_id": resource_id},
    )


def _run_context_from_principal(principal: Principal) -> RunContext:
    return RunContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        agent_id=principal.agent_id,
        session_id=principal.session_id,
        request_id=principal.request_id,
        permission_scope=["tools:read", "memory:read", "memory:write"],
    )


def _record_audit(
    action: str,
    principal: Principal,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any],
    *,
    trace_id: str | None = None,
    run_id: str | None = None,
    audit_store: AuditStore,
) -> None:
    audit_store.record(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        trace_id=trace_id,
        run_id=run_id,
        details=details,
    )
