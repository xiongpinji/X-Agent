"""Goals API — 目标模式端点 (前端 GoalModePage 消费)。

接线说明
========
- 响应结构保持与旧内存 stub 一致；资源按已认证 tenant/user 隔离。
- 目标执行由 ``backend.app.core.goal_mode.GoalModeOrchestrator`` 真实编排器
  承担, 在 asyncio 后台任务中运行 (start 端点触发)。
- 生命周期: active →(start)→ running ⇄(pause/resume) paused
  → completed / failed / timeout / cancelled。
- 状态持久化到 ``data/goals.json`` (GoalStore, 原子写入), 重启不丢。
- 启动时惰性注入 billable llm_router 与 agent_loop；计费控制异常不得降级。
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.goal_mode import GoalControl, GoalResult, goal_orchestrator
from backend.app.core.goal_store import GoalStore
from backend.app.core.llm import (
    LLMReplayBlockedError,
    LLMReservationPersistenceError,
    LLMSubmissionUnknownError,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# 持久化存储: _goals 与 store 共享同一 list, 保持旧单测 `_goals.clear()` 契约
_store = GoalStore()
_goals: list[dict[str, Any]] = _store.goals

# 后台执行任务注册表: goal_id -> asyncio.Task
_tasks: dict[str, asyncio.Task] = {}

TERMINAL_STATUSES = {
    "completed",
    "failed",
    "timeout",
    "cancelled",
    "needs_attention",
}
RESTARTABLE_STATUSES = {"failed", "timeout", "cancelled"}
_BILLING_CONTROL_ERRORS = (
    LLMReplayBlockedError,
    LLMReservationPersistenceError,
    LLMSubmissionUnknownError,
)


# ---------------------------------------------------------------------------
# Schemas (契约与旧 stub 一致, 仅新增可选字段)
# ---------------------------------------------------------------------------


class CreateGoalRequest(BaseModel):
    objective: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="目标描述",
        json_schema_extra={"example": "Refactor authentication module to support OIDC and SAML"},
    )


class GoalResponse(BaseModel):
    id: str = Field(json_schema_extra={"example": "goal-a1b2c3d4e5f6"})
    objective: str = Field(json_schema_extra={"example": "Refactor authentication module to support OIDC and SAML"})
    status: str = Field(default="active", json_schema_extra={"example": "active"})
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default=0.0, json_schema_extra={"example": 1753372800.0})
    output: str = Field(default="", description="执行输出 (完成或失败原因)")
    updated_at: float = Field(default=0.0, description="最近状态更新时间")
    attempt_count: int = Field(default=0, ge=0)
    error_code: str | None = None

    model_config = {"json_schema_extra": {"examples": [{
        "id": "goal-a1b2c3d4e5f6",
        "objective": "Refactor authentication module to support OIDC and SAML",
        "status": "active",
        "checkpoints": [
            {"label": "OIDC discovery endpoint configured", "done": True},
            {"label": "SAML metadata exchange", "done": False},
        ],
        "created_at": 1753372800.0,
    }]}}


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _find(goal_id: str, principal: Principal) -> dict[str, Any]:
    for g in _goals:
        if (
            g.get("id") == goal_id
            and g.get("tenant_id") == principal.tenant_id
            and g.get("user_id") == principal.user_id
        ):
            return g
    raise HTTPException(status_code=404, detail=f"Goal not found: {goal_id}")


def _subgoal_view(sg: Any) -> dict[str, Any]:
    d = asdict(sg) if is_dataclass(sg) else dict(sg)
    return d


def _checkpoints_view(goal: dict[str, Any]) -> list[dict[str, Any]]:
    """把子目标进度渲染为前端契约的 checkpoints: [{label, done}]。"""
    view = []
    for sg in goal.get("progress", []):
        d = _subgoal_view(sg)
        view.append({
            "label": d.get("description", ""),
            "done": d.get("status") == "completed",
            "status": d.get("status", "pending"),
            "result": d.get("result", ""),
        })
    return view


def _goal_response(goal: dict[str, Any]) -> GoalResponse:
    return GoalResponse(
        id=goal["id"],
        objective=goal["objective"],
        status=goal["status"],
        checkpoints=_checkpoints_view(goal),
        created_at=goal.get("created_at", 0.0),
        output=goal.get("output", ""),
        updated_at=goal.get("updated_at", 0.0),
        attempt_count=int(goal.get("attempt_count", 0) or 0),
        error_code=goal.get("error_code"),
    )


def _serialize_goal(goal: dict[str, Any]) -> dict[str, Any]:
    """提取可 JSON 序列化的持久化快照 (丢弃 Task/GoalControl 等运行时对象)。"""
    return {
        "id": goal["id"],
        "tenant_id": goal.get("tenant_id"),
        "user_id": goal.get("user_id"),
        "objective": goal["objective"],
        "status": goal["status"],
        "created_at": goal.get("created_at", 0.0),
        "updated_at": goal.get("updated_at", 0.0),
        "output": goal.get("output", ""),
        "total_duration": goal.get("total_duration", 0.0),
        "attempt_count": int(goal.get("attempt_count", 0) or 0),
        "active_attempt_id": goal.get("active_attempt_id"),
        "error_code": goal.get("error_code"),
        "events": goal.get("events", []),
        "progress": [_subgoal_view(sg) for sg in goal.get("progress", [])],
    }


def _persist() -> None:
    try:
        _store.save([_serialize_goal(g) for g in _goals])
    except Exception:
        logger.exception("Failed to persist goals store")


def _add_event(goal: dict[str, Any], event: str, detail: str = "") -> None:
    goal.setdefault("events", []).append({
        "event": event,
        "detail": detail,
        "at": time.time(),
    })
    goal["updated_at"] = time.time()


_orchestrator_wired = False


def _billing_error_code(exc: Exception) -> str:
    if isinstance(exc, LLMReplayBlockedError):
        return "LLM_REPLAY_BLOCKED"
    if isinstance(exc, LLMReservationPersistenceError):
        return "LLM_RESERVATION_PERSISTENCE_FAILED"
    return "LLM_SUBMISSION_UNKNOWN"


def _wire_orchestrator() -> None:
    """惰性为全局编排器注入 billable llm_router / agent_loop。

    测试中若已注入 mock (属性非 None) 则不覆盖。
    """
    global _orchestrator_wired
    if _orchestrator_wired:
        return
    if goal_orchestrator.llm_router is None:
        from backend.app.dependencies import get_billable_llm_router

        goal_orchestrator.llm_router = get_billable_llm_router()
    if goal_orchestrator.agent_loop is None:
        from backend.app.dependencies import get_agent

        goal_orchestrator.agent_loop = get_agent()
    _orchestrator_wired = True


async def _run_goal(goal: dict[str, Any]) -> None:
    """后台执行目标: 调用真实编排器, 推进状态并持久化。"""
    control: GoalControl = goal["control"]
    try:
        _wire_orchestrator()
        attempt_id = str(
            goal.get("active_attempt_id")
            or f"{goal['id']}:attempt-{int(goal.get('attempt_count', 1) or 1)}"
        )
        result: GoalResult = await goal_orchestrator.execute_goal(
            goal["objective"],
            context={
                "tenant_id": goal["tenant_id"],
                "user_id": goal["user_id"],
                "goal_id": goal["id"],
                "operation_id": attempt_id,
                "run_id": attempt_id,
                "trace_id": attempt_id,
            },
            goal_id=goal["id"],
            control=control,
        )
        goal["result"] = result
        goal["progress"] = result.progress
        goal["total_duration"] = result.total_duration

        if result.status == "completed":
            parts = [sg.result for sg in result.progress
                     if getattr(sg, "status", None) == "completed" and getattr(sg, "result", "")]
            goal["output"] = result.output or "\n".join(parts)
            goal["error_code"] = None
        elif result.status in {"failed", "timeout"}:
            goal["output"] = (
                "Goal execution timed out."
                if result.status == "timeout"
                else "Goal execution failed."
            )
            goal["error_code"] = (
                "GOAL_EXECUTION_TIMEOUT"
                if result.status == "timeout"
                else "GOAL_EXECUTION_FAILED"
            )

        # 用户已手动取消/完成的目标不被编排器结果降级覆盖
        if goal["status"] in ("cancelled", "completed") and result.status != "completed":
            pass
        else:
            goal["status"] = result.status
        _add_event(
            goal,
            result.status,
            goal.get("error_code") or f"duration={result.total_duration:.1f}s",
        )
    except asyncio.CancelledError:
        if goal["status"] not in TERMINAL_STATUSES:
            goal["status"] = "cancelled"
            goal["error_code"] = "GOAL_CANCELLED"
        _add_event(goal, "cancelled", "execution task cancelled")
        raise
    except _BILLING_CONTROL_ERRORS as exc:
        code = _billing_error_code(exc)
        goal["status"] = "needs_attention"
        goal["output"] = "Billing reconciliation is required."
        goal["error_code"] = code
        _add_event(goal, "needs_attention", code)
        logger.error(
            "Goal execution requires reconciliation: goal_id=%s code=%s error_type=%s",
            goal["id"],
            code,
            type(exc).__name__,
        )
    except Exception as exc:
        goal["status"] = "failed"
        goal["output"] = "Goal execution failed."
        goal["error_code"] = "GOAL_EXECUTION_FAILED"
        _add_event(goal, "failed", "GOAL_EXECUTION_FAILED")
        logger.error(
            "Goal execution failed: goal_id=%s code=%s error_type=%s",
            goal["id"],
            "GOAL_EXECUTION_FAILED",
            type(exc).__name__,
        )
    finally:
        goal["updated_at"] = time.time()
        _tasks.pop(goal["id"], None)
        _persist()


# ---------------------------------------------------------------------------
# CRUD — 契约兼容端点
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=GoalResponse,
    summary="Create a new goal",
    responses={
        200: {"description": "Goal created successfully"},
        422: {"description": "Validation error — objective empty or too long"},
    },
)
async def create_goal(
    req: CreateGoalRequest,
    principal: PrincipalDependency,
) -> GoalResponse:
    """创建新目标 (active 状态, 通过 POST /{id}/start 启动后台执行)。"""
    enforce_scope(principal, "agent:run")
    goal = {
        "id": f"goal-{uuid4().hex[:12]}",
        "tenant_id": principal.tenant_id,
        "user_id": principal.user_id,
        "objective": req.objective,
        "status": "active",
        "progress": [],
        "output": "",
        "total_duration": 0.0,
        "attempt_count": 0,
        "active_attempt_id": None,
        "error_code": None,
        "events": [],
        "control": None,
        "result": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _add_event(goal, "created", req.objective[:100])
    _goals.append(goal)
    _persist()
    return _goal_response(goal)


@router.get(
    "",
    response_model=list[GoalResponse],
    summary="List all goals",
    responses={200: {"description": "Array of all goals (may be empty)"}},
)
async def list_goals(principal: PrincipalDependency) -> list[GoalResponse]:
    """列出所有目标。"""
    enforce_scope(principal, "agent:read")
    return [
        _goal_response(g)
        for g in _goals
        if g.get("tenant_id") == principal.tenant_id
        and g.get("user_id") == principal.user_id
    ]


@router.get(
    "/{goal_id}",
    response_model=GoalResponse,
    summary="Get a specific goal",
    responses={
        200: {"description": "Goal found"},
        404: {"description": "Goal not found", "content": {"application/json": {"example": {"detail": "Goal not found: goal-xyz"}}}},
    },
)
async def get_goal(
    goal_id: str,
    principal: PrincipalDependency,
) -> GoalResponse:
    """获取指定目标 (状态查询: 进度 checkpoints 随后台执行实时推进)。"""
    enforce_scope(principal, "agent:read")
    return _goal_response(_find(goal_id, principal))


@router.post(
    "/{goal_id}/complete",
    summary="Mark goal as completed",
    responses={
        200: {"description": "Goal marked completed", "content": {"application/json": {"example": {"id": "goal-a1b2c3d4e5f6", "status": "completed"}}}},
        404: {"description": "Goal not found"},
    },
)
async def complete_goal(
    goal_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """手动标记目标完成; 若正在执行则先请求取消后台任务。"""
    enforce_scope(principal, "agent:run")
    goal = _find(goal_id, principal)
    if goal["status"] == "needs_attention":
        raise HTTPException(
            status_code=409,
            detail=f"Goal requires billing reconciliation: {goal_id}",
        )
    control = goal.get("control")
    if goal["status"] in ("running", "paused") and control is not None:
        control.cancel()
    goal["status"] = "completed"
    _add_event(goal, "completed", "marked completed manually")
    _persist()
    return {"id": goal_id, "status": "completed"}


# ---------------------------------------------------------------------------
# 生命周期控制 — 接线真实编排器
# ---------------------------------------------------------------------------


@router.post(
    "/{goal_id}/start",
    summary="Start goal execution in background",
    responses={
        200: {"description": "Goal execution started"},
        404: {"description": "Goal not found"},
        409: {"description": "Goal already running or completed"},
    },
)
async def start_goal(
    goal_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """启动目标: 在 asyncio 后台任务中运行真实编排器。

    active 状态首次启动; failed/timeout/cancelled 状态可重新执行。
    """
    enforce_scope(principal, "agent:run")
    goal = _find(goal_id, principal)
    active_task = _tasks.get(goal_id)
    if active_task is not None and not active_task.done():
        raise HTTPException(
            status_code=409,
            detail=f"Goal execution is still active: {goal_id}",
        )
    if goal["status"] in ("running", "paused"):
        raise HTTPException(status_code=409, detail=f"Goal already running: {goal_id}")
    if goal["status"] in {"completed", "needs_attention"}:
        raise HTTPException(
            status_code=409,
            detail=f"Goal cannot be started from {goal['status']}: {goal_id}",
        )

    restarted = goal["status"] in RESTARTABLE_STATUSES
    attempt_count = int(goal.get("attempt_count", 0) or 0) + 1
    goal["attempt_count"] = attempt_count
    goal["active_attempt_id"] = f"{goal_id}:attempt-{attempt_count}"
    goal["progress"] = []
    goal["output"] = ""
    goal["error_code"] = None
    goal["control"] = GoalControl()
    goal["status"] = "running"
    _add_event(goal, "restarted" if restarted else "started")
    _tasks[goal_id] = asyncio.create_task(_run_goal(goal))
    _persist()
    return {
        "id": goal_id,
        "status": "running",
        "attempt_count": attempt_count,
    }


@router.post(
    "/{goal_id}/pause",
    summary="Pause a running goal",
    responses={
        200: {"description": "Goal paused"},
        404: {"description": "Goal not found"},
        409: {"description": "Goal is not running"},
    },
)
async def pause_goal(
    goal_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """暂停目标: 协作式, 当前子目标执行完毕后暂停在下一个子目标边界。"""
    enforce_scope(principal, "agent:run")
    goal = _find(goal_id, principal)
    if goal["status"] != "running" or goal.get("control") is None:
        raise HTTPException(status_code=409, detail=f"Goal is not running: {goal_id}")
    goal["control"].pause()
    goal["status"] = "paused"
    _add_event(goal, "paused")
    _persist()
    return {"id": goal_id, "status": "paused"}


@router.post(
    "/{goal_id}/resume",
    summary="Resume a paused goal",
    responses={
        200: {"description": "Goal resumed"},
        404: {"description": "Goal not found"},
        409: {"description": "Goal is not paused"},
    },
)
async def resume_goal(
    goal_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """恢复已暂停的目标。"""
    enforce_scope(principal, "agent:run")
    goal = _find(goal_id, principal)
    if goal["status"] != "paused" or goal.get("control") is None:
        raise HTTPException(status_code=409, detail=f"Goal is not paused: {goal_id}")
    goal["control"].resume()
    goal["status"] = "running"
    _add_event(goal, "resumed")
    _persist()
    return {"id": goal_id, "status": "running"}


@router.post(
    "/{goal_id}/cancel",
    summary="Cancel goal execution",
    responses={
        200: {"description": "Goal cancelled"},
        404: {"description": "Goal not found"},
        409: {"description": "Goal already in terminal state"},
    },
)
async def cancel_goal(
    goal_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """取消目标: 协作式取消后台执行; 未启动的目标直接标记取消。"""
    enforce_scope(principal, "agent:run")
    goal = _find(goal_id, principal)
    if goal["status"] in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Goal already in terminal state ({goal['status']}): {goal_id}",
        )
    control = goal.get("control")
    if control is not None:
        control.cancel()
    goal["status"] = "cancelled"
    _add_event(goal, "cancelled", "cancel requested by user")
    _persist()
    return {"id": goal_id, "status": "cancelled"}


@router.get(
    "/{goal_id}/history",
    summary="Get goal execution history",
    responses={
        200: {"description": "Goal history: events + sub-goal progress"},
        404: {"description": "Goal not found"},
    },
)
async def goal_history(
    goal_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """目标执行历史: 状态迁移事件 + 子目标进度 + 检查点。"""
    enforce_scope(principal, "agent:read")
    goal = _find(goal_id, principal)
    return {
        "id": goal["id"],
        "objective": goal["objective"],
        "status": goal["status"],
        "created_at": goal.get("created_at", 0.0),
        "updated_at": goal.get("updated_at", 0.0),
        "total_duration": goal.get("total_duration", 0.0),
        "events": goal.get("events", []),
        "subgoals": [_subgoal_view(sg) for sg in goal.get("progress", [])],
        "checkpoints": _checkpoints_view(goal),
    }
