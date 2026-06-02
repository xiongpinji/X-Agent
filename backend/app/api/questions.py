"""
API endpoints for interactive question management.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.core.interactive_questions import (
    InteractiveQuestion,
    QuestionAnswer,
    QuestionHistory,
    QuestionStatus,
    QuestionType,
    question_manager,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/questions", tags=["questions"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class CreateQuestionRequest(BaseModel):
    """Request to create a question."""
    run_id: str = Field(..., description="Associated run ID")
    type: QuestionType = Field(..., description="Question type")
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=5000)
    context: dict[str, Any] = Field(default_factory=dict)
    options: list[dict[str, str]] = Field(default_factory=list)
    allow_multiple: bool = Field(default=False)
    placeholder: str = Field(default="")
    validation_pattern: str | None = Field(default=None)
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=1)
    timeout_seconds: int | None = Field(default=300, ge=1)
    priority: str = Field(default="normal")
    blocking: bool = Field(default=True)
    default_answer: Any = Field(default=None)
    tags: list[str] = Field(default_factory=list)


class AnswerQuestionRequest(BaseModel):
    """Request to answer a question."""
    answer: Any = Field(..., description="The answer")


class QuestionListResponse(BaseModel):
    """Response for question list."""
    questions: list[InteractiveQuestion]
    total: int
    pending: int


@router.post("", response_model=InteractiveQuestion, status_code=status.HTTP_201_CREATED)
async def create_question(
    request: CreateQuestionRequest,
    principal: PrincipalDependency,
) -> InteractiveQuestion:
    """
    Create an interactive question.

    The agent execution will pause and wait for user input.

    Args:
        request: Question creation request

    Returns:
        Created question
    """
    enforce_scope(principal, "agent:run")

    # Convert options
    from backend.app.core.interactive_questions import QuestionOption

    options = [
        QuestionOption(value=opt.get("value", ""), label=opt.get("label", ""))
        for opt in request.options
    ]

    question = InteractiveQuestion(
        run_id=request.run_id,
        type=request.type,
        title=request.title,
        description=request.description,
        context=request.context,
        options=options,
        allow_multiple=request.allow_multiple,
        placeholder=request.placeholder,
        validation_pattern=request.validation_pattern,
        min_length=request.min_length,
        max_length=request.max_length,
        timeout_seconds=request.timeout_seconds,
        priority=request.priority,
        blocking=request.blocking,
        default_answer=request.default_answer,
        tags=request.tags,
    )

    return question_manager.create_question(question)


@router.get("/pending", response_model=QuestionListResponse)
async def get_pending_questions(
    run_id: str = Query(..., description="Run ID"),
    *,
    principal: PrincipalDependency,
) -> QuestionListResponse:
    """
    Get pending questions for a run.

    Args:
        run_id: Run ID

    Returns:
        List of pending questions
    """
    enforce_scope(principal, "agent:read")

    questions = question_manager.get_pending_questions(run_id)
    pending_count = sum(1 for q in questions if q.status == QuestionStatus.PENDING)

    return QuestionListResponse(
        questions=questions,
        total=len(questions),
        pending=pending_count,
    )


@router.get("/{question_id}", response_model=InteractiveQuestion)
async def get_question(
    question_id: str,
    principal: PrincipalDependency,
) -> InteractiveQuestion:
    """
    Get a question by ID.

    Args:
        question_id: Question ID

    Returns:
        Question details
    """
    enforce_scope(principal, "agent:read")

    question = question_manager.get_question(question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    return question


@router.post("/{question_id}/answer", response_model=InteractiveQuestion)
async def answer_question(
    question_id: str,
    request: AnswerQuestionRequest,
    principal: PrincipalDependency,
) -> InteractiveQuestion:
    """
    Submit an answer to a question.

    Args:
        question_id: Question ID
        request: Answer request

    Returns:
        Updated question
    """
    enforce_scope(principal, "agent:run")

    question = question_manager.get_question(question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    if question.status != QuestionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question is not pending (status: {question.status})",
        )

    updated = question_manager.answer_question(question_id, request.answer)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    return updated


@router.post("/{question_id}/timeout", response_model=InteractiveQuestion)
async def timeout_question(
    question_id: str,
    principal: PrincipalDependency,
) -> InteractiveQuestion:
    """
    Mark a question as timed out.

    Args:
        question_id: Question ID

    Returns:
        Updated question
    """
    enforce_scope(principal, "agent:run")

    question = question_manager.get_question(question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    updated = question_manager.timeout_question(question_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    return updated


@router.post("/{question_id}/cancel", response_model=InteractiveQuestion)
async def cancel_question(
    question_id: str,
    principal: PrincipalDependency,
) -> InteractiveQuestion:
    """
    Cancel a question.

    Args:
        question_id: Question ID

    Returns:
        Updated question
    """
    enforce_scope(principal, "agent:run")

    question = question_manager.get_question(question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    updated = question_manager.cancel_question(question_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    return updated


@router.get("/run/{run_id}/history", response_model=list[QuestionHistory])
async def get_question_history(
    run_id: str,
    principal: PrincipalDependency,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[QuestionHistory]:
    """
    Get question history for a run.

    Args:
        run_id: Run ID
        limit: Maximum number of entries to return

    Returns:
        Question history
    """
    enforce_scope(principal, "agent:read")

    return question_manager.get_history(run_id=run_id, limit=limit)


@router.post("/cleanup")
async def cleanup_expired_questions(
    principal: PrincipalDependency,
) -> dict[str, int]:
    """
    Clean up expired questions.

    Args:
        None

    Returns:
        Number of questions cleaned up
    """
    enforce_scope(principal, "agent:run")

    count = question_manager.cleanup_expired()
    return {"cleaned_up": count}
