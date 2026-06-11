from datetime import UTC

import pytest
from pydantic import ValidationError

from backend.app.core import long_task_models
from backend.app.core.long_task_models import (
    LongTaskCreateRequest,
    LongTaskDispatchResponse,
    LongTaskEvent,
    LongTaskNextAction,
    LongTaskNextActionDecision,
    LongTaskPhaseState,
    LongTaskPhaseStatus,
    LongTaskRecord,
    LongTaskStatus,
    long_task_utcnow,
    new_long_task_id,
)


def test_long_task_models_export_core_symbols_without_entrypoint_coupling() -> None:
    assert long_task_models.LongTaskCreateRequest is LongTaskCreateRequest
    assert long_task_models.LongTaskRecord is LongTaskRecord
    assert long_task_models.LongTaskStatus is LongTaskStatus
    assert long_task_models.LongTaskNextAction is LongTaskNextAction


def test_long_task_record_defaults_are_side_effect_free_model_values() -> None:
    record = LongTaskRecord(title="Release report", task="Prepare release evidence")

    assert record.status == LongTaskStatus.QUEUED
    assert record.priority == 5
    assert record.tenant_id == "default"
    assert record.user_id == "anonymous"
    assert record.plan == []
    assert record.phases == []
    assert record.timeline == []
    assert record.artifacts == []
    assert record.context == {}
    assert record.metadata == {}
    assert record.created_at.tzinfo is UTC
    assert record.updated_at.tzinfo is UTC


def test_long_task_nested_models_keep_enum_and_timestamp_defaults() -> None:
    phase = LongTaskPhaseState(id="plan", title="Plan")
    event = LongTaskEvent(kind="task.created", status=LongTaskStatus.QUEUED)

    assert phase.status == LongTaskPhaseStatus.PENDING
    assert phase.artifact_ids == []
    assert phase.metadata == {}
    assert event.id
    assert event.created_at.tzinfo is UTC


def test_long_task_request_validation_stays_in_model_layer() -> None:
    with pytest.raises(ValidationError):
        LongTaskCreateRequest(task="", priority=11)

    request = LongTaskCreateRequest(task="Ship release", priority=3)
    assert request.priority == 3
    assert request.requires_approval is True
    assert request.auto_plan is True


def test_long_task_dispatch_response_can_embed_record_without_store() -> None:
    record = LongTaskRecord(title="Resume work", task="Continue")
    decision = LongTaskNextActionDecision(
        action=LongTaskNextAction.RESUME,
        reason="Task can continue",
    )

    response = LongTaskDispatchResponse(decision=decision, executed=True, record=record)

    assert response.executed is True
    assert response.blocked is False
    assert response.record is record
    assert response.decision.action == LongTaskNextAction.RESUME


def test_long_task_model_helpers_return_runtime_values() -> None:
    first_id = new_long_task_id()
    second_id = new_long_task_id()
    now = long_task_utcnow()

    assert first_id
    assert second_id
    assert first_id != second_id
    assert now.tzinfo is UTC
