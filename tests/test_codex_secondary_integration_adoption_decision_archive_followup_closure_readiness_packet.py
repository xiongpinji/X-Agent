from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness,
)


PACKET_POLICIES = {
    "followup_closure_readiness_policy": "followup-closure-readiness-policy",
    "closure_criteria_policy": "closure-criteria-policy",
    "owner_signoff_policy": "owner-signoff-policy",
    "blocker_resolution_policy": "blocker-resolution-policy",
    "secondary_integration_adoption_decision_archive_followup_closure_readiness_manifest_ref": "followup-closure-readiness-manifest",
    "secondary_integration_adoption_decision_archive_followup_closure_governance_ref": "followup-closure-governance",
}


def test_ready_secondary_integration_archive_followup_closure_readiness_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet(
        {
            **PACKET_POLICIES,
            "closures": [
                {
                    "closure_id": "closure-1",
                    "status": "closure-ready",
                    "archive_followup_closure_readiness_ref": "closure-readiness",
                    "disposition_preview_refs": ["disposition-preview"],
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "unresolved_blocker_refs": ["none"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["closure_count"] == 1
    assert packet["summary"]["owner_signoff_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet(
        {
            "closures": [
                {
                    "closure_id": "closure-2",
                    "status": "closure-ready",
                    "archive_followup_closure_readiness_ref": "closure-readiness",
                    "disposition_preview_refs": ["disposition-preview"],
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_closure_readiness_policy_ref",
        "closure_criteria_policy_ref",
        "owner_signoff_policy_ref",
        "blocker_resolution_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_closure_readiness_manifest_ref",
        "secondary_integration_adoption_decision_archive_followup_closure_governance_ref",
    ]


def test_failed_or_stale_followup_closure_readiness_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet(
        {
            **PACKET_POLICIES,
            "closures": [
                {
                    "closure_id": "closure-3",
                    "status": "stale",
                    "archive_followup_closure_readiness_ref": "closure-readiness",
                    "disposition_preview_refs": ["disposition-preview"],
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    closure = packet["closures"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_status_failed" in closure["blockers"]


def test_missing_followup_closure_readiness_refs_needs_review() -> None:
    closure = summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness(
        {
            "closure_id": "closure-4",
            "status": "closure-ready",
            "archive_followup_closure_readiness_ref": "closure-readiness",
        }
    )

    assert closure.readiness_state == "needs_review"
    assert "disposition_preview_refs" in closure.missing_refs
    assert "notification_readiness_refs" in closure.missing_refs
    assert "owner_handoff_refs" in closure.missing_refs
    assert "followup_status_rollup_refs" in closure.missing_refs
    assert "validation_refs" in closure.missing_refs
    assert "evidence_refs" in closure.missing_refs
    assert "owner_signoff_refs" in closure.missing_refs
    assert "closure_criteria_refs" in closure.missing_refs
    assert "next_action_refs" in closure.missing_refs


def test_open_followup_closure_readiness_warns_until_receipts_attach() -> None:
    closure = summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness(
        {
            "closure_id": "closure-5",
            "status": "needs-review",
            "archive_followup_closure_readiness_ref": "closure-readiness",
            "disposition_preview_refs": ["disposition-preview"],
            "notification_readiness_refs": ["notification-readiness"],
            "owner_handoff_refs": ["owner-handoff"],
            "followup_status_rollup_refs": ["status-rollup"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "owner_signoff_refs": ["owner-signoff"],
            "closure_criteria_refs": ["closure-criteria"],
            "next_action_refs": ["next-action"],
        }
    )

    assert closure.readiness_state == "needs_review"
    assert closure.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_still_open" in closure.warnings


def test_unresolved_blockers_warning_requires_blocker_refs_and_drives_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet(
        {
            **PACKET_POLICIES,
            "closures": [
                {
                    "closure_id": "closure-6",
                    "status": "closure-ready",
                    "archive_followup_closure_readiness_ref": "closure-readiness",
                    "disposition_preview_refs": ["disposition-preview"],
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "next_action_refs": ["next-action"],
                    "unresolved_blockers_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_missing_evidence"
    assert "unresolved_blocker_refs" in packet["closures"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet",
    ]


def test_owner_signoff_warning_drives_owner_signoff_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet(
        {
            **PACKET_POLICIES,
            "closures": [
                {
                    "closure_id": "closure-7",
                    "status": "closure-ready",
                    "archive_followup_closure_readiness_ref": "closure-readiness",
                    "disposition_preview_refs": ["disposition-preview"],
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "next_action_refs": ["next-action"],
                    "owner_signoff_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_owner_signoff_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_owner_signoffs",
        "refresh_archive_followup_closure_readiness_packet",
    ]


def test_live_closure_disposition_notification_taskboard_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet(
        {
            **PACKET_POLICIES,
            "closures": [
                {
                    "closure_id": "closure-8",
                    "status": "closure-ready",
                    "archive_followup_closure_readiness_ref": "closure-readiness",
                    "disposition_preview_refs": ["disposition-preview"],
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "next_action_refs": ["next-action"],
                    "followup_closure_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_operation_attempted" in packet["closures"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_closure_readiness_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_inventory"]


def test_dataclass_like_archive_followup_closure_readiness_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupClosureReadiness:
        closure_id: str
        status: str
        archive_followup_closure_readiness_ref: str
        disposition_preview_refs: list[str]
        notification_readiness_refs: list[str]
        owner_handoff_refs: list[str]
        followup_status_rollup_refs: list[str]
        unresolved_blocker_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        owner_signoff_refs: list[str]
        closure_criteria_refs: list[str]
        next_action_refs: list[str]

    closure = summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness(
        FollowupClosureReadiness(
            "closure-9",
            "complete",
            "closure-readiness",
            ["disposition-preview"],
            ["notification-readiness"],
            ["owner-handoff"],
            ["status-rollup"],
            ["none"],
            ["validation"],
            ["evidence"],
            ["owner-signoff"],
            ["closure-criteria"],
            ["next-action"],
        )
    )

    assert closure.closure_id == "closure-9"
    assert closure.status == "complete"
    assert closure.readiness_state == "ready"
