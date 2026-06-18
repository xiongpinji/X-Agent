from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_status_rollup,
)


PACKET_POLICIES = {
    "followup_status_rollup_policy": "followup-status-rollup-policy",
    "owner_status_policy": "owner-status-policy",
    "due_window_status_policy": "due-window-status-policy",
    "status_evidence_policy": "status-evidence-policy",
    "secondary_integration_adoption_decision_archive_followup_status_rollup_manifest_ref": "followup-status-rollup-manifest",
    "secondary_integration_adoption_decision_archive_followup_status_governance_ref": "followup-status-governance",
}


def test_ready_secondary_integration_archive_followup_status_rollup_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "status-rollup-1",
                    "status": "rolled-up",
                    "archive_followup_status_rollup_ref": "followup-status-rollup",
                    "followup_routing_refs": ["followup-routing"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["rollup_count"] == 1
    assert packet["summary"]["blocked_followup_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet(
        {
            "rollups": [
                {
                    "rollup_id": "status-rollup-2",
                    "status": "current",
                    "archive_followup_status_rollup_ref": "followup-status-rollup",
                    "followup_routing_refs": ["followup-routing"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_status_rollup_policy_ref",
        "owner_status_policy_ref",
        "due_window_status_policy_ref",
        "status_evidence_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_status_rollup_manifest_ref",
        "secondary_integration_adoption_decision_archive_followup_status_governance_ref",
    ]


def test_failed_or_stale_followup_status_rollup_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "status-rollup-3",
                    "status": "stale",
                    "archive_followup_status_rollup_ref": "followup-status-rollup",
                    "followup_routing_refs": ["followup-routing"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    rollup = packet["rollups"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_status_rollup_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_status_rollup_status_failed" in rollup["blockers"]


def test_missing_followup_status_rollup_refs_needs_review() -> None:
    rollup = summarize_codex_secondary_integration_adoption_decision_archive_followup_status_rollup(
        {
            "rollup_id": "status-rollup-4",
            "status": "current",
            "archive_followup_status_rollup_ref": "followup-status-rollup",
        }
    )

    assert rollup.readiness_state == "needs_review"
    assert "followup_routing_refs" in rollup.missing_refs
    assert "owner_followup_refs" in rollup.missing_refs
    assert "reviewer_refs" in rollup.missing_refs
    assert "open_followup_refs" in rollup.missing_refs
    assert "blocked_followup_refs" in rollup.missing_refs
    assert "resolved_followup_refs" in rollup.missing_refs
    assert "due_window_refs" in rollup.missing_refs
    assert "validation_refs" in rollup.missing_refs
    assert "evidence_refs" in rollup.missing_refs
    assert "next_action_refs" in rollup.missing_refs


def test_open_followup_status_rollup_warns_until_receipts_attach() -> None:
    rollup = summarize_codex_secondary_integration_adoption_decision_archive_followup_status_rollup(
        {
            "rollup_id": "status-rollup-5",
            "status": "needs-review",
            "archive_followup_status_rollup_ref": "followup-status-rollup",
            "followup_routing_refs": ["followup-routing"],
            "owner_followup_refs": ["owner-followup"],
            "reviewer_refs": ["reviewer"],
            "open_followup_refs": ["open"],
            "blocked_followup_refs": ["blocked-none"],
            "resolved_followup_refs": ["resolved"],
            "due_window_refs": ["due-window"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "next_action_refs": ["next-action"],
        }
    )

    assert rollup.readiness_state == "needs_review"
    assert rollup.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_status_rollup_still_open" in rollup.warnings


def test_due_window_breach_warning_drives_due_status_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "status-rollup-6",
                    "status": "rolled-up",
                    "archive_followup_status_rollup_ref": "followup-status-rollup",
                    "followup_routing_refs": ["followup-routing"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "next_action_refs": ["next-action"],
                    "due_window_breach_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_status_rollup_due_window_breach_detected"
    assert packet["next_actions"] == [
        "review_archive_followup_due_status",
        "refresh_archive_followup_status_rollup_packet",
    ]


def test_blocked_followups_warning_drives_blocked_followup_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "status-rollup-7",
                    "status": "current",
                    "archive_followup_status_rollup_ref": "followup-status-rollup",
                    "followup_routing_refs": ["followup-routing"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open"],
                    "blocked_followup_refs": ["blocked"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "next_action_refs": ["next-action"],
                    "blocked_followups_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_status_rollup_blocked_followups_detected"
    assert packet["next_actions"] == [
        "review_archive_blocked_followups",
        "refresh_archive_followup_status_rollup_packet",
    ]


def test_live_status_issue_taskboard_query_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "status-rollup-8",
                    "status": "rolled-up",
                    "archive_followup_status_rollup_ref": "followup-status-rollup",
                    "followup_routing_refs": ["followup-routing"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "due_window_refs": ["due-window"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "next_action_refs": ["next-action"],
                    "followup_status_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_status_rollup_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_operation_attempted" in packet["rollups"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_status_rollup_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_inventory"]


def test_dataclass_like_archive_followup_status_rollup_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupStatusRollup:
        rollup_id: str
        status: str
        archive_followup_status_rollup_ref: str
        followup_routing_refs: list[str]
        owner_followup_refs: list[str]
        reviewer_refs: list[str]
        open_followup_refs: list[str]
        blocked_followup_refs: list[str]
        resolved_followup_refs: list[str]
        due_window_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        next_action_refs: list[str]

    rollup = summarize_codex_secondary_integration_adoption_decision_archive_followup_status_rollup(
        FollowupStatusRollup(
            "status-rollup-9",
            "complete",
            "followup-status-rollup",
            ["followup-routing"],
            ["owner-followup"],
            ["reviewer"],
            ["open-none"],
            ["blocked-none"],
            ["resolved"],
            ["due-window"],
            ["validation"],
            ["evidence"],
            ["next-action"],
        )
    )

    assert rollup.rollup_id == "status-rollup-9"
    assert rollup.status == "complete"
    assert rollup.readiness_state == "ready"
