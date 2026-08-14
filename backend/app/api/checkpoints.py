"""P2-09: Checkpoint / Resume API.

提供断点续跑能力:
- GET  /api/v1/checkpoints          — 列出可恢复的 run
- GET  /api/v1/checkpoints/{trace_id} — 查看指定 run 的 checkpoint 详情
- POST /api/v1/checkpoints/{trace_id}/resume — 从最近 checkpoint 恢复执行
- DELETE /api/v1/checkpoints/{trace_id} — 清理 checkpoint
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.core.checkpoint import (
    CheckpointSummary,
    get_checkpoint_store,
)
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/checkpoints", tags=["checkpoints"])


# ─── 依赖 ─────────────────────────────────────────────────────────────────────


def get_principal(request: Request) -> Principal:
    """获取当前认证主体（统一走标准鉴权链，不再直接信任 request.state）."""
    return get_current_principal(request)


# ─── 响应模型 ─────────────────────────────────────────────────────────────────


class CheckpointListResponse(BaseModel):
    items: list[CheckpointSummary] = Field(default_factory=list)
    total: int = 0


class CheckpointDetailResponse(BaseModel):
    trace_id: str
    agent_id: str
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    latest_iteration: int = 0
    status: str = "unknown"
    resumable: bool = False


class ResumeRequest(BaseModel):
    """恢复执行请求."""
    extra_context: dict[str, Any] = Field(default_factory=dict)
    from_iteration: int | None = None  # None = 从最新 checkpoint 恢复


class ResumeResponse(BaseModel):
    trace_id: str
    new_trace_id: str
    resumed_from_iteration: int
    status: str
    message: str


class DeleteResponse(BaseModel):
    trace_id: str
    deleted_count: int


# ─── 端点 ─────────────────────────────────────────────────────────────────────


@router.get("", response_model=CheckpointListResponse)
async def list_checkpoints(
    limit: int = 20,
    principal: Principal = Depends(get_principal),
) -> CheckpointListResponse:
    """列出可恢复的 Agent run (status=running/paused/failed)."""
    store = get_checkpoint_store()
    items = store.list_resumable(limit=limit)
    return CheckpointListResponse(items=items, total=len(items))


@router.get("/{trace_id}", response_model=CheckpointDetailResponse)
async def get_checkpoint_detail(
    trace_id: str,
    principal: Principal = Depends(get_principal),
) -> CheckpointDetailResponse:
    """查看指定 run 的所有 checkpoint."""
    store = get_checkpoint_store()
    checkpoints = store.list_for_run(trace_id)

    if not checkpoints:
        raise HTTPException(status_code=404, detail=f"No checkpoints found for trace_id={trace_id}")

    latest = checkpoints[-1]
    return CheckpointDetailResponse(
        trace_id=trace_id,
        agent_id=latest.agent_id,
        checkpoints=[cp.model_dump(mode="json") for cp in checkpoints],
        latest_iteration=latest.iteration,
        status=latest.status,
        resumable=latest.status in ("running", "paused", "failed"),
    )


@router.post("/{trace_id}/resume", response_model=ResumeResponse)
async def resume_from_checkpoint(
    trace_id: str,
    body: ResumeRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> ResumeResponse:
    """从 checkpoint 恢复执行.

    恢复逻辑:
    1. 加载最近的 checkpoint
    2. 将 remaining_steps + 已完成的 tool_calls/observations 注入 extra_context
    3. 设置 resume_trace_id 触发 Agent Loop 的恢复路径
    4. 调用 Agent run API 执行
    """
    store = get_checkpoint_store()
    checkpoint = store.get_latest(trace_id)

    if checkpoint is None:
        raise HTTPException(status_code=404, detail=f"No checkpoint found for trace_id={trace_id}")

    if checkpoint.status == "completed":
        raise HTTPException(status_code=400, detail="Run already completed, cannot resume")

    # 确定恢复点
    resume_iteration = body.from_iteration or checkpoint.iteration

    # 构建恢复上下文
    resume_context = {
        **body.extra_context,
        "resume_trace_id": trace_id,
        "resume_from_iteration": resume_iteration,
        "resume_checkpoint_id": checkpoint.checkpoint_id,
        "resume_remaining_steps": checkpoint.remaining_steps,
        "resume_completed_observations": checkpoint.observations,
        "resume_tool_calls": checkpoint.tool_calls,
        "resume_goal": checkpoint.trajectory_goal,
        "resume_stage": checkpoint.trajectory_stage,
        "session_id": checkpoint.session_id,
    }

    # 调用 Agent 执行 (通过内部依赖注入)
    try:
        import uuid

        from backend.app.core.contracts import RunContext

        new_trace_id = f"resume-{uuid.uuid4().hex[:12]}"

        # 获取 agent 实例
        agent = getattr(request.app.state, "agent", None)
        if agent is None:
            raise HTTPException(status_code=503, detail="Agent not available")

        context = RunContext(
            trace_id=new_trace_id,
            agent_id=checkpoint.agent_id,
            tenant_id=checkpoint.tenant_id or "default",
            user_id=checkpoint.user_id or principal.user_id,
            session_id=checkpoint.session_id,
        )

        result = await agent.run(context, checkpoint.task, resume_context)

        # 标记原 run 已完成
        store.mark_completed(trace_id)

        return ResumeResponse(
            trace_id=trace_id,
            new_trace_id=new_trace_id,
            resumed_from_iteration=resume_iteration,
            status=result.status.value if hasattr(result.status, "value") else str(result.status),
            message=f"Resumed from iteration {resume_iteration}, completed with status: {result.status}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Resume failed for trace_id=%s: %s", trace_id, e)
        raise HTTPException(status_code=500, detail=f"Resume failed: {e!s}")


@router.delete("/{trace_id}", response_model=DeleteResponse)
async def delete_checkpoints(
    trace_id: str,
    principal: Principal = Depends(get_principal),
) -> DeleteResponse:
    """清理指定 run 的所有 checkpoint."""
    store = get_checkpoint_store()
    deleted = store.delete(trace_id)
    return DeleteResponse(trace_id=trace_id, deleted_count=deleted)
