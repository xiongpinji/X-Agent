from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff,
)


PACKET_POLICIES = {
    "followup_owner_handoff_policy": "followup-owner-handoff-policy",
    "owner_accountability_policy": "owner-accountability-policy",
    "reviewer_accountability_policy": "reviewer-accountability-policy",
    "handoff_evidence_policy": "handoff-evidence-policy",
    "secondary_integration_adoption_decision_archive_followup_owner_handoff_manifest_ref": "followup-owner-handoff-manifest",
    "secondary_integration_adoption_decision_archive_followup_owner_governance_ref": "followup-owner-governance",
}


def test_ready_secondary_integration_archive_followup_owner_handoff_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet(
        {
            **PACKET_POLICIES,
            "handoffs": [
                {
                    "handoff_id": "owner-handoff-1",
                    "status": "handed-off",
                    "archive_followup_owner_handoff_ref": "followup-owner-handoff",
                    "followup_status_rollup_refs": ["followup-status-rollup"],
                    "owner_refs": ["owner"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["handoff_count"] == 1
    assert packet["summary"]["owner_handoff_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet(
        {
            "handoffs": [
                {
                    "handoff_id": "owner-handoff-2",
                    "status": "assigned",
                    "archive_followup_owner_handoff_ref": "followup-owner-handoff",
                    "followup_status_rollup_refs": ["followup-status-rollup"],
                    "owner_refs": ["owner"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_owner_handoff_policy_ref",
        "owner_accountability_policy_ref",
        "reviewer_accountability_policy_ref",
        "handoff_evidence_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_owner_handoff_manifest_ref",
        "secondary_integration_adoption_decision_archive_followup_owner_governance_ref",
    ]


def test_failed_or_stale_followup_owner_handoff_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet(
        {
            **PACKET_POLICIES,
            "handoffs": [
                {
                    "handoff_id": "owner-handoff-3",
                    "status": "stale",
                    "archive_followup_owner_handoff_ref": "followup-owner-handoff",
                    "followup_status_rollup_refs": ["followup-status-rollup"],
                    "owner_refs": ["owner"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    handoff = packet["handoffs"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_status_failed" in handoff["blockers"]


def test_missing_followup_owner_handoff_refs_needs_review() -> None:
    handoff = summarize_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff(
        {
            "handoff_id": "owner-handoff-4",
            "status": "assigned",
            "archive_followup_owner_handoff_ref": "followup-owner-handoff",
        }
    )

    assert handoff.readiness_state == "needs_review"
    assert "followup_status_rollup_refs" in handoff.missing_refs
    assert "owner_refs" in handoff.missing_refs
    assert "reviewer_refs" in handoff.missing_refs
    assert "open_followup_refs" in handoff.missing_refs
    assert "blocked_followup_refs" in handoff.missing_refs
    assert "resolved_followup_refs" in handoff.missing_refs
    assert "due_window_refs" in handoff.missing_refs
    assert "validation_refs" in handoff.missing_refs
    assert "evidence_refs" in handoff.missing_refs
    assert "owner_handoff_refs" in handoff.missing_refs
    assert "next_action_refs" in handoff.missing_refs


def test_open_followup_owner_handoff_warns_until_receipts_attach() -> None:
    handoff = summarize_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff(
        {
            "handoff_id": "owner-handoff-5",
            "status": "needs-review",
            "archive_followup_owner_handoff_ref": "followup-owner-handoff",
            "followup_status_rollup_refs": ["followup-status-rollup"],
            "owner_refs": ["owner"],
            "reviewer_refs": ["reviewer"],
            "open_followup_refs": ["open"],
            "blocked_followup_refs": ["blocked-none"],
            "resolved_followup_refs": ["resolved"],
            "due_window_refs": ["due-window"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "owner_handoff_refs": ["owner-handoff"],
            "next_action_refs": ["next-action"],
        }
    )

    assert handoff.readiness_state == "needs_review"
    assert handoff.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_still_open" in handoff.warnings


def test_owner_assignment_warning_drives_owner_assignment_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet(
        {
            **PACKET_POLICIES,
            "handoffs": [
                {
                    "handoff_id": "owner-handoff-6",
                    "status": "handed-off",
                    "archive_followup_owner_handoff_ref": "followup-owner-handoff",
                    "followup_status_rollup_refs": ["followup-status-rollup"],
                    "owner_refs": ["owner"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "next_action_refs": ["next-action"],
                    "owner_assignment_missing": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_owner_assignment_missing"
    assert packet["next_actions"] == [
        "review_archive_followup_owner_assignments",
        "refresh_archive_followup_owner_handoff_packet",
    ]


def test_blocked_followups_warning_drives_owner_blocker_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet(
        {
            **PACKET_POLICIES,
            "handoffs": [
                {
                    "handoff_id": "owner-handoff-7",
                    "status": "assigned",
                    "archive_followup_owner_handoff_ref": "followup-owner-handoff",
                    "followup_status_rollup_refs": ["followup-status-rollup"],
                    "owner_refs": ["owner"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open"],
                    "blocked_followup_refs": ["blocked"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "next_action_refs": ["next-action"],
                    "blocked_followups_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_blocked_followups_detected"
    assert packet["next_actions"] == [
        "review_archive_followup_owner_blockers",
        "refresh_archive_followup_owner_handoff_packet",
    ]


def test_live_assignment_issue_taskboard_query_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet(
        {
            **PACKET_POLICIES,
            "handoffs": [
                {
                    "handoff_id": "owner-handoff-8",
                    "status": "handed-off",
                    "archive_followup_owner_handoff_ref": "followup-owner-handoff",
                    "followup_status_rollup_refs": ["followup-status-rollup"],
                    "owner_refs": ["owner"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "next_action_refs": ["next-action"],
                    "owner_assignment_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_operation_attempted" in packet["handoffs"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_owner_handoff_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_inventory"]


def test_dataclass_like_archive_followup_owner_handoff_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupOwnerHandoff:
        handoff_id: str
        status: str
        archive_followup_owner_handoff_ref: str
        followup_status_rollup_refs: list[str]
        owner_refs: list[str]
        reviewer_refs: list[str]
        open_followup_refs: list[str]
        blocked_followup_refs: list[str]
        resolved_followup_refs: list[str]
        due_window_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        owner_handoff_refs: list[str]
        next_action_refs: list[str]

    handoff = summarize_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff(
        FollowupOwnerHandoff(
            "owner-handoff-9",
            "complete",
            "followup-owner-handoff",
            ["followup-status-rollup"],
            ["owner"],
            ["reviewer"],
            ["open-none"],
            ["blocked-none"],
            ["resolved"],
            ["due-window"],
            ["validation"],
            ["evidence"],
            ["owner-handoff"],
            ["next-action"],
        )
    )

    assert handoff.handoff_id == "owner-handoff-9"
    assert handoff.status == "complete"
    assert handoff.readiness_state == "ready"
