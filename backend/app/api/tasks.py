"""统一异步任务 API（2026-09-06 统一任务层）— Codex "submit and come back" 模型.

Endpoints:
  POST /api/v1/agent/tasks              提交异步任务（当前支持 kind=agent_run）
  GET  /api/v1/agent/tasks              任务列表（过滤 status/kind）
  GET  /api/v1/agent/tasks/{task_id}    任务详情（轮询结果）
  POST /api/v1/agent/tasks/{task_id}/cancel  取消（诚实语义，见下）

前缀说明：规划时的 /api/v1/tasks 已被 tasks_ui（前端 TaskList 在用的 CRUD
任务面）占用，二者同路径先注册者胜会互相遮蔽（2026-09-06 与 owner 确认后
改用 /api/v1/agent/tasks——语义上也更准确：统一层的执行体是 agent run）。

与现有机制的关系（不迁移、不破坏）：
- shell 命令任务继续走 /api/v1/sandbox/tasks（本端点对 kind=shell 返回 501
  明确指引——诚实边界，而不是勉强代理）；
- issue_to_pr 继续走 /api/v1/sandbox/webhook/github（同样 501 指引）；
- /agent/run/stream 保持同步 SSE 语义不动；本层是"提交后离开"的异步面，
  响应模型的 source 字段预留未来聚合视图（当前恒为 "unified"）。

取消语义（诚实边界，文档注明）：
- queued → 直接 cancelled（尚未开始执行）；
- running/awaiting_approval → 标记 cancel_requested=True，状态不变；
  agent loop 无法硬杀，执行体返回后按 cancel_requested 落 cancelled；
- 终态 → 409（不允许取消已完成任务）。

安全：全部端点要求 tasks:manage scope（ROLE_SCOPES admin/developer 已配）。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.core.tasks_store import (
    InvalidTaskTransition,
    TaskRecord,
    TasksStore,
    get_tasks_store,
)
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent/tasks", tags=["tasks"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# answer 摘要截断长度（与 main.py B3 agent.run handler 的 2000 对齐）
_ANSWER_SUMMARY_CHARS = 2000
_ERROR_CHARS = 2000


# ─── 请求/响应模型 ────────────────────────────────────────────────────────────


class TaskCreateRequest(BaseModel):
    """提交统一任务。

    kind=agent_run: task 为自然语言任务文本，context 透传 agent.run 的
    extra_context（同 scheduler 的 agent_task 形状）。
    """

    kind: Literal["agent_run", "shell", "issue_to_pr"] = "agent_run"
    task: str = Field(..., min_length=1, max_length=32000, description="任务文本")
    context: dict[str, Any] = Field(default_factory=dict)


class TaskCreateResponse(BaseModel):
    task_id: str
    kind: str
    status: str = "queued"
    source: str = "unified"


class TaskRecordResponse(BaseModel):
    """任务记录视图（列表与详情共用；source 预留聚合来源）。"""

    task_id: str
    kind: str
    status: str
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    trace_id: str | None = None
    created_by: str = ""
    tenant_id: str = "default"
    cancel_requested: bool = False
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskRecordResponse]
    total: int
    limit: int
    offset: int


def _to_response(record: TaskRecord) -> TaskRecordResponse:
    return TaskRecordResponse(
        task_id=record.task_id,
        kind=record.kind,
        status=record.status,
        source=record.source,
        payload=record.payload,
        result=record.result,
        error=record.error,
        trace_id=record.trace_id,
        created_by=record.created_by,
        tenant_id=record.tenant_id,
        cancel_requested=record.cancel_requested,
        created_at=record.created_at,
        updated_at=record.updated_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
    )


# ─── 后台执行（agent_run） ────────────────────────────────────────────────────


async def _execute_agent_run(
    task_id: str,
    task_text: str,
    context: dict[str, Any],
    tenant_id: str,
    user_id: str,
) -> None:
    """后台执行一个 agent_run 任务并回写终态。

    状态流转: queued → running → (awaiting_approval|completed|failed|cancelled)。
    协作式取消：agent.run 返回后若记录带 cancel_requested=True，终态落
    cancelled（结果摘要仍保留，供审计）。
    """
    store = get_tasks_store()

    # queued 阶段已被取消（提交与后台启动之间的窗口）→ 不再启动
    record = store.get(task_id)
    if record is None or record.status == "cancelled":
        logger.info("Unified task %s cancelled before start; skipping", task_id)
        return

    store.update(task_id, status="running")

    # 运行时导入保持可 patch 性（测试 monkeypatch dependencies.get_agent）
    from backend.app.core.contracts import RunContext, RunStatus
    from backend.app.dependencies import get_agent

    ctx = RunContext(tenant_id=tenant_id, user_id=user_id)
    try:
        agent = get_agent()
        result = await agent.run(ctx, task_text, extra_context=context or {})
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("Unified agent_run task %s failed", task_id)
        record = store.update(
            task_id,
            status="failed",
            error=str(e)[:_ERROR_CHARS],
            trace_id=ctx.trace_id,
        )
        await _notify_task_terminal(record)
        return

    summary = {
        "answer": (result.answer or "")[:_ANSWER_SUMMARY_CHARS],
        "iterations": result.iterations,
        "memory_hits": result.memory_hits,
        "tool_call_count": len(result.tool_calls),
        "agent_status": result.status.value,
    }

    # 终态判定：cancel_requested 优先（诚实语义：取消请求已记录，
    # agent 虽跑完也按取消落账）；其次按 agent 状态映射。
    if result.status == RunStatus.COMPLETED:
        final = "completed"
    elif result.status == RunStatus.NEEDS_APPROVAL:
        final = "awaiting_approval"
    else:
        final = "failed"
    error_text = (result.error or None) if final == "failed" else None

    record = store.get(task_id)
    if record is not None and record.cancel_requested:
        final = "cancelled"
        summary["cancel_note"] = (
            "cancel requested during run; agent finished but recorded as cancelled"
        )

    record = store.update(
        task_id,
        status=final,
        result=summary,
        error=error_text,
        trace_id=result.trace_id or ctx.trace_id,
    )
    await _notify_task_terminal(record)


async def _notify_task_terminal(record: TaskRecord) -> None:
    """任务终态通知（best-effort，任何失败只告警不影响任务状态）。

    复用现有通知/审计基建：
    1. audit_store.record 落审计（终态可追溯）；
    2. notifications 模块的 WebSocket ConnectionManager 广播
       （无连接时为 no-op；该路由当前未挂载，属预留）。
    """
    # 1) 审计
    try:
        from backend.app.dependencies import get_audit_store

        get_audit_store().record(
            action=f"task.{record.status}",
            resource_type="unified_task",
            resource_id=record.task_id,
            tenant_id=record.tenant_id,
            actor_id=record.created_by,
            trace_id=record.trace_id,
            outcome="success" if record.status == "completed" else record.status,
            details={
                "kind": record.kind,
                "cancel_requested": record.cancel_requested,
                "error": (record.error or "")[:200] or None,
            },
        )
    except Exception:
        logger.warning("audit record failed for task %s", record.task_id, exc_info=True)

    # 2) WebSocket 广播（现有通知基建，无连接时 no-op）
    try:
        from backend.app.api.notifications import notification_manager

        await notification_manager.broadcast(
            {
                "type": "task.completed" if record.status == "completed" else f"task.{record.status}",
                "task_id": record.task_id,
                "kind": record.kind,
                "status": record.status,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    except Exception:
        logger.debug("task terminal broadcast skipped for %s", record.task_id)


# ─── 端点 ─────────────────────────────────────────────────────────────────────


def _store() -> TasksStore:
    return get_tasks_store()


@router.post("", response_model=TaskCreateResponse)
async def create_task(
    request: TaskCreateRequest, principal: PrincipalDependency
) -> TaskCreateResponse:
    """提交异步任务，立即返回 task_id（fire-and-forget，轮询获取结果）。"""
    enforce_scope(principal, "tasks:manage")

    if request.kind != "agent_run":
        # 诚实边界：shell 走 sandbox orchestrator，issue_to_pr 走 GitHub webhook。
        # 代理它们只会复制一套行为；明确 501 指引到既有端点。
        hint = {
            "shell": "POST /api/v1/sandbox/tasks",
            "issue_to_pr": "POST /api/v1/sandbox/webhook/github",
        }[request.kind]
        raise api_error(
            501,
            ErrorCode.VALIDATION_ERROR,
            f"kind={request.kind!r} is not served by the unified layer yet; "
            f"use {hint}",
        )

    task_text = request.task.strip()
    if not task_text:
        raise api_error(
            422, ErrorCode.VALIDATION_ERROR, "task must not be blank"
        )

    record = TaskRecord(
        kind="agent_run",
        payload={"task": task_text, "context": request.context},
        created_by=principal.user_id,
        tenant_id=principal.tenant_id,
    )
    _store().create(record)

    # 后台执行（挂在 app 事件循环上；同 sandbox webhook 的 create_task 模式）
    asyncio.create_task(
        _execute_agent_run(
            record.task_id,
            task_text,
            request.context,
            principal.tenant_id,
            principal.user_id,
        )
    )
    return TaskCreateResponse(
        task_id=record.task_id, kind=record.kind, status=record.status
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    principal: PrincipalDependency,
    status: str | None = Query(default=None, description="按状态过滤"),
    kind: str | None = Query(default=None, description="按类型过滤"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TaskListResponse:
    """任务列表（按 created_at 倒序）。"""
    enforce_scope(principal, "tasks:manage")
    store = _store()
    records = store.list(status=status, kind=kind, limit=limit, offset=offset)
    total = store.count(status=status, kind=kind)
    return TaskListResponse(
        tasks=[_to_response(r) for r in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=TaskRecordResponse)
async def get_task(task_id: str, principal: PrincipalDependency) -> TaskRecordResponse:
    """任务详情：状态机当前态 + 结果摘要 + trace_id（轮询端点）。"""
    enforce_scope(principal, "tasks:manage")
    record = _store().get(task_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, f"task {task_id} not found")
    return _to_response(record)


@router.post("/{task_id}/cancel", response_model=TaskRecordResponse)
async def cancel_task(
    task_id: str, principal: PrincipalDependency
) -> TaskRecordResponse:
    """取消任务（诚实语义）：

    - queued → cancelled（立即）；
    - running/awaiting_approval → cancel_requested=True，agent 无法硬杀，
      完成后落 cancelled（见 _execute_agent_run）；
    - 终态 → 409。
    """
    enforce_scope(principal, "tasks:manage")
    store = _store()
    if store.get(task_id) is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, f"task {task_id} not found")
    try:
        record = store.request_cancel(task_id)
    except InvalidTaskTransition as e:
        raise api_error(409, ErrorCode.RESOURCE_CONFLICT, str(e)) from e
    return _to_response(record)
