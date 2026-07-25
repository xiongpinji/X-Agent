"""Goals API — 目标模式端点 (前端 GoalModePage 消费)。"""
from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])

# In-memory store (轻量级; 生产环境可替换为 DB 持久化)
_goals: list[dict[str, Any]] = []


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


@router.post(
    "",
    response_model=GoalResponse,
    summary="Create a new goal",
    responses={
        200: {"description": "Goal created successfully"},
        422: {"description": "Validation error — objective empty or too long"},
    },
)
async def create_goal(req: CreateGoalRequest) -> GoalResponse:
    """创建新目标。

    Creates a new autonomous goal that the agent will track.
    The goal starts in `active` status and can accumulate checkpoints
    as the agent makes progress.
    """
    goal = {
        "id": f"goal-{uuid4().hex[:12]}",
        "objective": req.objective,
        "status": "active",
        "checkpoints": [],
        "created_at": time.time(),
    }
    _goals.append(goal)
    return GoalResponse(**goal)


@router.get(
    "",
    response_model=list[GoalResponse],
    summary="List all goals",
    responses={200: {"description": "Array of all goals (may be empty)"}},
)
async def list_goals() -> list[GoalResponse]:
    """列出所有目标。"""
    return [GoalResponse(**g) for g in _goals]


@router.get(
    "/{goal_id}",
    response_model=GoalResponse,
    summary="Get a specific goal",
    responses={
        200: {"description": "Goal found"},
        404: {"description": "Goal not found", "content": {"application/json": {"example": {"detail": "Goal not found: goal-xyz"}}}},
    },
)
async def get_goal(goal_id: str) -> GoalResponse:
    """获取指定目标。"""
    for g in _goals:
        if g["id"] == goal_id:
            return GoalResponse(**g)
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail=f"Goal not found: {goal_id}")


@router.post(
    "/{goal_id}/complete",
    summary="Mark goal as completed",
    responses={
        200: {"description": "Goal marked completed", "content": {"application/json": {"example": {"id": "goal-a1b2c3d4e5f6", "status": "completed"}}}},
        404: {"description": "Goal not found"},
    },
)
async def complete_goal(goal_id: str) -> dict[str, Any]:
    """标记目标完成。"""
    for g in _goals:
        if g["id"] == goal_id:
            g["status"] = "completed"
            return {"id": goal_id, "status": "completed"}
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail=f"Goal not found: {goal_id}")
