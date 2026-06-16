from datetime import UTC, datetime

import pytest

from backend.app.core.long_task_state_machine import (
    ALLOWED_LONG_TASK_STATE_TRANSITIONS,
    IllegalLongTaskStateTransition,
    LongTaskState,
    LongTaskStateEvent,
    LongTaskStateSnapshot,
    allowed_long_task_state_targets,
    ensure_long_task_state_transition_allowed,
    is_terminal_long_task_state,
    transition_long_task_state,
)


def test_long_task_state_snapshot_defaults_to_queued_without_events() -> None:
    snapshot = LongTaskStateSnapshot()

    assert snapshot.state == LongTaskState.QUEUED
    assert snapshot.events == ()
    assert snapshot.updated_at.tzinfo is UTC
    assert snapshot.completed_at is None


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (LongTaskState.QUEUED, LongTaskState.RUNNING),
        (LongTaskState.QUEUED, LongTaskState.BLOCKED),
        (LongTaskState.QUEUED, LongTaskState.FAILED),
        (LongTaskState.QUEUED, LongTaskState.CANCELED),
        (LongTaskState.RUNNING, LongTaskState.BLOCKED),
        (LongTaskState.RUNNING, LongTaskState.SUCCEEDED),
        (LongTaskState.RUNNING, LongTaskState.FAILED),
        (LongTaskState.RUNNING, LongTaskState.CANCELED),
        (LongTaskState.BLOCKED, LongTaskState.QUEUED),
        (LongTaskState.BLOCKED, LongTaskState.RUNNING),
        (LongTaskState.BLOCKED, LongTaskState.FAILED),
        (LongTaskState.BLOCKED, LongTaskState.CANCELED),
    ],
)
def test_allowed_long_task_state_transitions_are_declared(
    from_state: LongTaskState,
    to_state: LongTaskState,
) -> None:
    assert to_state in allowed_long_task_state_targets(from_state)
    ensure_long_task_state_transition_allowed(from_state, to_state)


@pytest.mark.parametrize("terminal_state", list(LongTaskState))
def test_terminal_long_task_states_are_explicit(terminal_state: LongTaskState) -> None:
    expected = terminal_state in {
        LongTaskState.SUCCEEDED,
        LongTaskState.FAILED,
        LongTaskState.CANCELED,
    }

    assert is_terminal_long_task_state(terminal_state) is expected


def test_all_states_have_transition_entries() -> None:
    assert set(ALLOWED_LONG_TASK_STATE_TRANSITIONS) == set(LongTaskState)


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (LongTaskState.QUEUED, LongTaskState.SUCCEEDED),
        (LongTaskState.RUNNING, LongTaskState.QUEUED),
        (LongTaskState.BLOCKED, LongTaskState.SUCCEEDED),
        (LongTaskState.SUCCEEDED, LongTaskState.RUNNING),
        (LongTaskState.FAILED, LongTaskState.RUNNING),
        (LongTaskState.CANCELED, LongTaskState.RUNNING),
    ],
)
def test_illegal_long_task_state_transitions_raise(
    from_state: LongTaskState,
    to_state: LongTaskState,
) -> None:
    with pytest.raises(IllegalLongTaskStateTransition) as exc:
        ensure_long_task_state_transition_allowed(from_state, to_state)

    assert exc.value.from_state == from_state
    assert exc.value.to_state == to_state
    assert f"{from_state.value} -> {to_state.value}" in str(exc.value)


def test_transition_long_task_state_returns_new_snapshot_and_event() -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    original = LongTaskStateSnapshot()

    updated = transition_long_task_state(
        original,
        LongTaskState.RUNNING,
        kind="task.started",
        detail="Worker claimed task",
        payload={"worker_id": "worker-1"},
        now=now,
    )

    assert original.state == LongTaskState.QUEUED
    assert original.events == ()
    assert original.completed_at is None
    assert updated is not original
    assert updated.state == LongTaskState.RUNNING
    assert updated.updated_at == now
    assert updated.completed_at is None
    assert len(updated.events) == 1

    event = updated.events[0]
    assert isinstance(event, LongTaskStateEvent)
    assert event.kind == "task.started"
    assert event.from_state == LongTaskState.QUEUED
    assert event.to_state == LongTaskState.RUNNING
    assert event.detail == "Worker claimed task"
    assert event.payload == {"worker_id": "worker-1"}
    assert event.created_at == now


def test_terminal_transition_sets_completed_at_and_keeps_event_history() -> None:
    started_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    completed_at = datetime(2026, 6, 1, 12, 30, tzinfo=UTC)
    running = transition_long_task_state(
        LongTaskStateSnapshot(),
        LongTaskState.RUNNING,
        now=started_at,
    )

    succeeded = transition_long_task_state(
        running,
        LongTaskState.SUCCEEDED,
        detail="All acceptance checks passed",
        now=completed_at,
    )

    assert running.completed_at is None
    assert succeeded.state == LongTaskState.SUCCEEDED
    assert succeeded.completed_at == completed_at
    assert succeeded.updated_at == completed_at
    assert [event.to_state for event in succeeded.events] == [
        LongTaskState.RUNNING,
        LongTaskState.SUCCEEDED,
    ]
    assert succeeded.events[-1].from_state == LongTaskState.RUNNING
    assert succeeded.events[-1].detail == "All acceptance checks passed"


def test_transition_rejects_illegal_move_without_mutating_snapshot() -> None:
    snapshot = LongTaskStateSnapshot()

    with pytest.raises(IllegalLongTaskStateTransition):
        transition_long_task_state(snapshot, LongTaskState.SUCCEEDED)

    assert snapshot.state == LongTaskState.QUEUED
    assert snapshot.events == ()
    assert snapshot.completed_at is None
