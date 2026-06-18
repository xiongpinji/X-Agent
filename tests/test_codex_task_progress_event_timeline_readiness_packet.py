from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_task_progress_event_timeline_readiness_packet import (
    build_codex_task_progress_event_timeline_readiness_packet,
    summarize_codex_task_progress_event_timeline,
)


PACKET_POLICIES = {
    "timeline_policy": "timeline-policy",
    "progress_event_policy": "progress-event-policy",
    "phase_transition_policy": "phase-transition-policy",
    "budget_policy": "budget-policy",
    "task_timeline_manifest_ref": "task-timeline-manifest",
    "task_timeline_governance_ref": "task-timeline-governance",
}


def test_ready_task_progress_event_timeline_has_event_and_budget_evidence() -> None:
    packet = build_codex_task_progress_event_timeline_readiness_packet(
        {
            **PACKET_POLICIES,
            "timelines": [
                {
                    "timeline_id": "timeline-1",
                    "status": "completed",
                    "task_ref": "task",
                    "progress_event_refs": ["progress"],
                    "phase_transition_refs": ["phase"],
                    "tool_event_refs": ["tool"],
                    "validation_event_refs": ["validation-event"],
                    "elapsed_time_refs": ["elapsed-time"],
                    "budget_refs": ["budget"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_task_progress_event_timeline_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["timeline_count"] == 1
    assert packet["summary"]["progress_event_ref_count"] == 1
    assert packet["next_actions"] == ["share_task_progress_event_timeline_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_task_progress_event_timeline_readiness_packet(
        {
            "timelines": [
                {
                    "timeline_id": "timeline-2",
                    "status": "recorded",
                    "task_ref": "task",
                    "progress_event_refs": ["progress"],
                    "phase_transition_refs": ["phase"],
                    "tool_event_refs": ["tool"],
                    "validation_event_refs": ["validation-event"],
                    "elapsed_time_refs": ["elapsed-time"],
                    "budget_refs": ["budget"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_task_progress_event_timeline_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "timeline_policy_ref",
        "progress_event_policy_ref",
        "phase_transition_policy_ref",
        "budget_policy_ref",
        "task_timeline_manifest_ref",
        "task_timeline_governance_ref",
    ]


def test_failed_or_stalled_timeline_blocks_candidate() -> None:
    packet = build_codex_task_progress_event_timeline_readiness_packet(
        {
            **PACKET_POLICIES,
            "timelines": [
                {
                    "timeline_id": "timeline-3",
                    "status": "stalled",
                    "task_ref": "task",
                    "progress_event_refs": ["progress"],
                    "phase_transition_refs": ["phase"],
                    "elapsed_time_refs": ["elapsed-time"],
                    "budget_refs": ["budget"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    timeline = packet["timelines"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_task_progress_event_timeline_status_failed"
    assert "task_progress_event_timeline_status_failed" in timeline["blockers"]
    assert packet["next_actions"] == [
        "resolve_task_progress_event_timeline_blockers",
        "refresh_task_progress_event_timeline_readiness",
    ]


def test_missing_task_progress_phase_elapsed_budget_artifact_and_owner_refs_needs_review() -> None:
    timeline = summarize_codex_task_progress_event_timeline(
        {
            "timeline_id": "timeline-4",
            "status": "recorded",
        }
    )

    assert timeline.readiness_state == "needs_review"
    assert "task_ref" in timeline.missing_refs
    assert "progress_event_refs" in timeline.missing_refs
    assert "phase_transition_refs" in timeline.missing_refs
    assert "elapsed_time_refs" in timeline.missing_refs
    assert "budget_refs" in timeline.missing_refs
    assert "artifact_refs" in timeline.missing_refs
    assert "owner_refs" in timeline.missing_refs


def test_completed_or_validated_timeline_requires_tool_and_validation_event_refs() -> None:
    timeline = summarize_codex_task_progress_event_timeline(
        {
            "timeline_id": "timeline-5",
            "status": "validated",
            "task_ref": "task",
            "progress_event_refs": ["progress"],
            "phase_transition_refs": ["phase"],
            "elapsed_time_refs": ["elapsed-time"],
            "budget_refs": ["budget"],
            "artifact_refs": ["artifact"],
            "owner_refs": ["owner"],
        }
    )

    assert timeline.readiness_state == "needs_review"
    assert "tool_event_refs" in timeline.missing_refs
    assert "validation_event_refs" in timeline.missing_refs


def test_open_timeline_waits_for_completion() -> None:
    packet = build_codex_task_progress_event_timeline_readiness_packet(
        {
            **PACKET_POLICIES,
            "timelines": [
                {
                    "timeline_id": "timeline-6",
                    "status": "running",
                    "task_ref": "task",
                    "progress_event_refs": ["progress"],
                    "phase_transition_refs": ["phase"],
                    "elapsed_time_refs": ["elapsed-time"],
                    "budget_refs": ["budget"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_task_progress_event_timeline_still_open"
    assert packet["next_actions"] == [
        "wait_for_task_progress_event_timeline_completion",
        "attach_task_timeline_receipts",
    ]


def test_live_event_emission_timeline_persistence_or_task_mutation_blocks_candidate() -> None:
    packet = build_codex_task_progress_event_timeline_readiness_packet(
        {
            **PACKET_POLICIES,
            "timelines": [
                {
                    "timeline_id": "timeline-7",
                    "status": "recorded",
                    "task_ref": "task",
                    "progress_event_refs": ["progress"],
                    "phase_transition_refs": ["phase"],
                    "tool_event_refs": ["tool"],
                    "validation_event_refs": ["validation-event"],
                    "elapsed_time_refs": ["elapsed-time"],
                    "budget_refs": ["budget"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "event_emission_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_task_progress_event_timeline_live_operation_blocked"
    assert "live_task_progress_event_timeline_operation_attempted" in packet["timelines"][0]["blockers"]


def test_empty_payload_requests_task_progress_event_timeline_inventory() -> None:
    packet = build_codex_task_progress_event_timeline_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_task_progress_event_timeline_inventory"]


def test_dataclass_like_task_progress_event_timeline_is_accepted_by_summarizer() -> None:
    @dataclass
    class TaskProgressEventTimeline:
        timeline_id: str
        status: str
        task_ref: str
        progress_event_refs: list[str]
        phase_transition_refs: list[str]
        tool_event_refs: list[str]
        validation_event_refs: list[str]
        elapsed_time_refs: list[str]
        budget_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]

    timeline = summarize_codex_task_progress_event_timeline(
        TaskProgressEventTimeline(
            "timeline-8",
            "published",
            "task",
            ["progress"],
            ["phase"],
            ["tool"],
            ["validation-event"],
            ["elapsed-time"],
            ["budget"],
            ["artifact"],
            ["owner"],
        )
    )

    assert timeline.timeline_id == "timeline-8"
    assert timeline.status == "published"
    assert timeline.readiness_state == "ready"
