"""Work Mode API — 跨应用长任务管理端点。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.work_mode.orchestrator import get_work_orchestrator

router = APIRouter(prefix="/api/v1/work", tags=["work-mode"])


class StartSessionRequest(BaseModel):
    goal: str
    max_hours: float = Field(default=8.0, ge=0.5, le=72.0)
    max_milestones: int = Field(default=6, ge=1, le=20)


@router.post("/sessions")
async def start_session(req: StartSessionRequest) -> dict[str, Any]:
    """启动新的 Work Session。"""
    orchestrator = get_work_orchestrator()
    session = await orchestrator.start_session(
        goal=req.goal,
        max_hours=req.max_hours,
        max_milestones=req.max_milestones,
    )
    return session.to_dict()


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    """列出所有 Work Sessions。"""
    orchestrator = get_work_orchestrator()
    return {"sessions": orchestrator.list_sessions()}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """获取指定 Session 详情。"""
    orchestrator = get_work_orchestrator()
    session = orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session.to_dict()


@router.post("/sessions/{session_id}/tick")
async def tick_session(session_id: str) -> dict[str, Any]:
    """推进 Session（执行当前里程碑）。"""
    orchestrator = get_work_orchestrator()
    try:
        session = await orchestrator.tick(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return session.to_dict()


@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str) -> dict[str, Any]:
    """暂停 Session。"""
    orchestrator = get_work_orchestrator()
    session = await orchestrator.pause_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session.to_dict()


@router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str) -> dict[str, Any]:
    """恢复 Session。"""
    orchestrator = get_work_orchestrator()
    try:
        session = await orchestrator.resume_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return session.to_dict()
