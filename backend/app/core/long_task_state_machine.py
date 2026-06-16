from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def long_task_state_machine_utcnow() -> datetime:
    return datetime.now(UTC)


def new_long_task_state_event_id() -> str:
    return str(uuid4())


class LongTaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


TERMINAL_LONG_TASK_STATES = frozenset(
    {
        LongTaskState.SUCCEEDED,
        LongTaskState.FAILED,
        LongTaskState.CANCELED,
    }
)
TERMINAL_LONG_TASK_RECORD_STATUS_VALUES = frozenset({"completed", "succeeded", "failed", "canceled"})


ALLOWED_LONG_TASK_STATE_TRANSITIONS: dict[LongTaskState, frozenset[LongTaskState]] = {
    LongTaskState.QUEUED: frozenset(
        {
            LongTaskState.RUNNING,
            LongTaskState.BLOCKED,
            LongTaskState.FAILED,
            LongTaskState.CANCELED,
        }
    ),
    LongTaskState.RUNNING: frozenset(
        {
            LongTaskState.BLOCKED,
            LongTaskState.SUCCEEDED,
            LongTaskState.FAILED,
            LongTaskState.CANCELED,
        }
    ),
    LongTaskState.BLOCKED: frozenset(
        {
            LongTaskState.QUEUED,
            LongTaskState.RUNNING,
            LongTaskState.FAILED,
            LongTaskState.CANCELED,
        }
    ),
    LongTaskState.SUCCEEDED: frozenset(),
    LongTaskState.FAILED: frozenset(),
    LongTaskState.CANCELED: frozenset(),
}


class IllegalLongTaskStateTransition(ValueError):
    def __init__(self, from_state: LongTaskState, to_state: LongTaskState) -> None:
        super().__init__(
            f"Illegal long task state transition: {from_state.value} -> {to_state.value}"
        )
        self.from_state = from_state
        self.to_state = to_state


class LongTaskStateEvent(BaseModel):
    id: str = Field(default_factory=new_long_task_state_event_id)
    kind: str = Field(default="long_task.state_transition", max_length=120)
    from_state: LongTaskState
    to_state: LongTaskState
    detail: str = Field(default="", max_length=4_000)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=long_task_state_machine_utcnow)


class LongTaskStateSnapshot(BaseModel):
    state: LongTaskState = LongTaskState.QUEUED
    events: tuple[LongTaskStateEvent, ...] = Field(default_factory=tuple)
    updated_at: datetime = Field(default_factory=long_task_state_machine_utcnow)
    completed_at: datetime | None = None


def is_terminal_long_task_state(state: LongTaskState) -> bool:
    return state in TERMINAL_LONG_TASK_STATES


def is_terminal_long_task_record_status(status: object) -> bool:
    value = getattr(status, "value", status)
    return str(value or "").strip().lower() in TERMINAL_LONG_TASK_RECORD_STATUS_VALUES


def allowed_long_task_state_targets(state: LongTaskState) -> frozenset[LongTaskState]:
    return ALLOWED_LONG_TASK_STATE_TRANSITIONS[state]


def ensure_long_task_state_transition_allowed(
    from_state: LongTaskState,
    to_state: LongTaskState,
) -> None:
    if to_state not in allowed_long_task_state_targets(from_state):
        raise IllegalLongTaskStateTransition(from_state, to_state)


def transition_long_task_state(
    snapshot: LongTaskStateSnapshot,
    to_state: LongTaskState,
    *,
    kind: str = "long_task.state_transition",
    detail: str = "",
    payload: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> LongTaskStateSnapshot:
    ensure_long_task_state_transition_allowed(snapshot.state, to_state)
    event_created_at = now or long_task_state_machine_utcnow()
    event = LongTaskStateEvent(
        kind=kind,
        from_state=snapshot.state,
        to_state=to_state,
        detail=detail,
        payload=dict(payload or {}),
        created_at=event_created_at,
    )
    completed_at = event_created_at if is_terminal_long_task_state(to_state) else None
    return snapshot.model_copy(
        update={
            "state": to_state,
            "events": (*snapshot.events, event),
            "updated_at": event_created_at,
            "completed_at": completed_at,
        }
    )


__all__ = [
    "ALLOWED_LONG_TASK_STATE_TRANSITIONS",
    "IllegalLongTaskStateTransition",
    "LongTaskState",
    "LongTaskStateEvent",
    "LongTaskStateSnapshot",
    "TERMINAL_LONG_TASK_STATES",
    "TERMINAL_LONG_TASK_RECORD_STATUS_VALUES",
    "allowed_long_task_state_targets",
    "ensure_long_task_state_transition_allowed",
    "is_terminal_long_task_record_status",
    "is_terminal_long_task_state",
    "long_task_state_machine_utcnow",
    "new_long_task_state_event_id",
    "transition_long_task_state",
]
