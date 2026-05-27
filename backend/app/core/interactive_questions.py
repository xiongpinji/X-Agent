"""
Interactive question system for X-Agent.

Allows agent to pause execution and ask user for input/confirmation,
with support for different question types and timeout handling.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QuestionType(str, Enum):
    """Types of interactive questions."""
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TEXT_INPUT = "text_input"
    CONFIRMATION = "confirmation"
    FILE_SELECTION = "file_selection"
    CODE_REVIEW = "code_review"


class QuestionStatus(str, Enum):
    """Question status."""
    PENDING = "pending"
    ANSWERED = "answered"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class QuestionOption(BaseModel):
    """Option for choice questions."""
    value: str = Field(..., description="Option value/ID")
    label: str = Field(..., description="Display label")
    description: str = Field(default="", description="Optional description")


class InteractiveQuestion(BaseModel):
    """Interactive question model."""
    question_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique question ID")
    run_id: str = Field(..., description="Associated run ID")
    type: QuestionType = Field(..., description="Question type")
    title: str = Field(..., min_length=1, max_length=500, description="Question title")
    description: str = Field(default="", max_length=5000, description="Detailed description")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    # For choice questions
    options: list[QuestionOption] = Field(default_factory=list, description="Available options")
    allow_multiple: bool = Field(default=False, description="Allow multiple selections")

    # For text input
    placeholder: str = Field(default="", description="Input placeholder")
    validation_pattern: str | None = Field(default=None, description="Regex pattern for validation")
    min_length: int | None = Field(default=None, ge=0, description="Minimum input length")
    max_length: int | None = Field(default=None, ge=1, description="Maximum input length")

    # Timing
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    timeout_seconds: int | None = Field(default=300, ge=1, description="Timeout in seconds (None = no timeout)")
    expires_at: str | None = Field(default=None, description="Expiration timestamp")

    # Status
    status: QuestionStatus = Field(default=QuestionStatus.PENDING)
    answer: Any = Field(default=None, description="User's answer")
    answered_at: str | None = Field(default=None, description="Answer timestamp")

    # Metadata
    priority: str = Field(default="normal", description="Question priority: low, normal, high, critical")
    blocking: bool = Field(default=True, description="Whether execution should wait for answer")
    default_answer: Any = Field(default=None, description="Default answer if timeout")
    tags: list[str] = Field(default_factory=list, description="Question tags")


class QuestionAnswer(BaseModel):
    """Answer to a question."""
    question_id: str = Field(..., description="Question ID")
    answer: Any = Field(..., description="The answer")
    answered_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class QuestionHistory(BaseModel):
    """Question history entry."""
    question_id: str
    run_id: str
    type: QuestionType
    title: str
    status: QuestionStatus
    answer: Any | None
    created_at: str
    answered_at: str | None
    timeout_seconds: int | None


class InteractiveQuestionManager:
    """Manages interactive questions for agent execution."""

    def __init__(self):
        self.questions: dict[str, InteractiveQuestion] = {}
        self.history: list[QuestionHistory] = []
        self.pending_by_run: dict[str, list[str]] = {}
        self.answer_events: dict[str, asyncio.Event] = {}

    def create_question(self, question: InteractiveQuestion) -> InteractiveQuestion:
        """Create a new question."""
        # Set expiration time
        if question.timeout_seconds:
            expires_at = datetime.utcnow() + timedelta(seconds=question.timeout_seconds)
            question.expires_at = expires_at.isoformat()

        self.questions[question.question_id] = question

        # Track by run
        if question.run_id not in self.pending_by_run:
            self.pending_by_run[question.run_id] = []
        self.pending_by_run[question.run_id].append(question.question_id)

        # Create answer event
        self.answer_events[question.question_id] = asyncio.Event()

        logger.info(f"Created question {question.question_id} for run {question.run_id}")
        return question

    def get_question(self, question_id: str) -> InteractiveQuestion | None:
        """Get a question by ID."""
        return self.questions.get(question_id)

    def get_pending_questions(self, run_id: str) -> list[InteractiveQuestion]:
        """Get pending questions for a run."""
        question_ids = self.pending_by_run.get(run_id, [])
        questions = []
        for qid in question_ids:
            q = self.questions.get(qid)
            if q and q.status == QuestionStatus.PENDING:
                questions.append(q)
        return questions

    def answer_question(self, question_id: str, answer: Any) -> InteractiveQuestion | None:
        """Answer a question."""
        question = self.questions.get(question_id)
        if not question:
            return None

        if question.status != QuestionStatus.PENDING:
            logger.warning(f"Question {question_id} is not pending (status: {question.status})")
            return question

        # Validate answer based on question type
        if not self._validate_answer(question, answer):
            logger.warning(f"Invalid answer for question {question_id}")
            return question

        question.answer = answer
        question.status = QuestionStatus.ANSWERED
        question.answered_at = datetime.utcnow().isoformat()

        # Record in history
        self._record_history(question)

        # Signal answer event
        if question_id in self.answer_events:
            self.answer_events[question_id].set()

        logger.info(f"Question {question_id} answered")
        return question

    def timeout_question(self, question_id: str) -> InteractiveQuestion | None:
        """Mark question as timed out."""
        question = self.questions.get(question_id)
        if not question:
            return None

        if question.status != QuestionStatus.PENDING:
            return question

        question.status = QuestionStatus.TIMEOUT

        # Use default answer if available
        if question.default_answer is not None:
            question.answer = question.default_answer
            question.status = QuestionStatus.ANSWERED

        question.answered_at = datetime.utcnow().isoformat()

        # Record in history
        self._record_history(question)

        # Signal answer event
        if question_id in self.answer_events:
            self.answer_events[question_id].set()

        logger.info(f"Question {question_id} timed out")
        return question

    def cancel_question(self, question_id: str) -> InteractiveQuestion | None:
        """Cancel a question."""
        question = self.questions.get(question_id)
        if not question:
            return None

        question.status = QuestionStatus.CANCELLED
        question.answered_at = datetime.utcnow().isoformat()

        # Record in history
        self._record_history(question)

        # Signal answer event
        if question_id in self.answer_events:
            self.answer_events[question_id].set()

        logger.info(f"Question {question_id} cancelled")
        return question

    async def wait_for_answer(self, question_id: str, timeout_seconds: int | None = None) -> Any:
        """Wait for answer to a question."""
        question = self.questions.get(question_id)
        if not question:
            raise ValueError(f"Question {question_id} not found")

        event = self.answer_events.get(question_id)
        if not event:
            raise ValueError(f"No event for question {question_id}")

        # Use question's timeout if not specified
        timeout = timeout_seconds or question.timeout_seconds

        try:
            if timeout:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            else:
                await event.wait()
        except asyncio.TimeoutError:
            self.timeout_question(question_id)

        # Return the answer
        question = self.questions.get(question_id)
        return question.answer if question else None

    def get_history(self, run_id: str | None = None, limit: int = 100) -> list[QuestionHistory]:
        """Get question history."""
        history = self.history

        if run_id:
            history = [h for h in history if h.run_id == run_id]

        return history[-limit:]

    def _validate_answer(self, question: InteractiveQuestion, answer: Any) -> bool:
        """Validate answer based on question type."""
        if question.type == QuestionType.CONFIRMATION:
            return isinstance(answer, bool)

        elif question.type == QuestionType.SINGLE_CHOICE:
            if not question.options:
                return True
            valid_values = {opt.value for opt in question.options}
            return answer in valid_values

        elif question.type == QuestionType.MULTIPLE_CHOICE:
            if not isinstance(answer, list):
                return False
            if not question.options:
                return True
            valid_values = {opt.value for opt in question.options}
            return all(a in valid_values for a in answer)

        elif question.type == QuestionType.TEXT_INPUT:
            if not isinstance(answer, str):
                return False
            if question.min_length and len(answer) < question.min_length:
                return False
            if question.max_length and len(answer) > question.max_length:
                return False
            if question.validation_pattern:
                import re
                if not re.match(question.validation_pattern, answer):
                    return False
            return True

        return True

    def _record_history(self, question: InteractiveQuestion) -> None:
        """Record question in history."""
        history_entry = QuestionHistory(
            question_id=question.question_id,
            run_id=question.run_id,
            type=question.type,
            title=question.title,
            status=question.status,
            answer=question.answer,
            created_at=question.created_at,
            answered_at=question.answered_at,
            timeout_seconds=question.timeout_seconds,
        )
        self.history.append(history_entry)

    def cleanup_expired(self) -> int:
        """Clean up expired questions."""
        now = datetime.utcnow()
        expired_count = 0

        for question_id, question in list(self.questions.items()):
            if question.status == QuestionStatus.PENDING and question.expires_at:
                expires_at = datetime.fromisoformat(question.expires_at)
                if now > expires_at:
                    self.timeout_question(question_id)
                    expired_count += 1

        return expired_count


# Global question manager
question_manager = InteractiveQuestionManager()
