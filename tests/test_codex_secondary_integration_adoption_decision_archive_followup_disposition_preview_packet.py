from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview,
)


PACKET_POLICIES = {
    "followup_disposition_preview_policy": "followup-disposition-preview-policy",
    "preview_decision_policy": "preview-decision-policy",
    "candidate_disposition_policy": "candidate-disposition-policy",
    "evidence_review_policy": "evidence-review-policy",
    "secondary_integration_adoption_decision_archive_followup_disposition_preview_manifest_ref": "followup-disposition-preview-manifest",
    "secondary_integration_adoption_decision_archive_followup_disposition_governance_ref": "followup-disposition-governance",
}


def test_ready_secondary_integration_archive_followup_disposition_preview_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "disposition-preview-1",
                    "status": "previewed",
                    "archive_followup_disposition_preview_ref": "disposition-preview",
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "preview_decision_refs": ["preview-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["preview_count"] == 1
    assert packet["summary"]["preview_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet(
        {
            "previews": [
                {
                    "preview_id": "disposition-preview-2",
                    "status": "previewed",
                    "archive_followup_disposition_preview_ref": "disposition-preview",
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "preview_decision_refs": ["preview-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_disposition_preview_policy_ref",
        "preview_decision_policy_ref",
        "candidate_disposition_policy_ref",
        "evidence_review_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_disposition_preview_manifest_ref",
        "secondary_integration_adoption_decision_archive_followup_disposition_governance_ref",
    ]


def test_failed_or_stale_followup_disposition_preview_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "disposition-preview-3",
                    "status": "stale",
                    "archive_followup_disposition_preview_ref": "disposition-preview",
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "preview_decision_refs": ["preview-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    preview = packet["previews"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_status_failed" in preview["blockers"]


def test_missing_followup_disposition_preview_refs_needs_review() -> None:
    preview = summarize_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview(
        {
            "preview_id": "disposition-preview-4",
            "status": "previewed",
            "archive_followup_disposition_preview_ref": "disposition-preview",
        }
    )

    assert preview.readiness_state == "needs_review"
    assert "notification_readiness_refs" in preview.missing_refs
    assert "owner_handoff_refs" in preview.missing_refs
    assert "followup_status_rollup_refs" in preview.missing_refs
    assert "open_followup_refs" in preview.missing_refs
    assert "blocked_followup_refs" in preview.missing_refs
    assert "resolved_followup_refs" in preview.missing_refs
    assert "validation_refs" in preview.missing_refs
    assert "evidence_refs" in preview.missing_refs
    assert "preview_decision_refs" in preview.missing_refs
    assert "next_action_refs" in preview.missing_refs


def test_open_followup_disposition_preview_warns_until_receipts_attach() -> None:
    preview = summarize_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview(
        {
            "preview_id": "disposition-preview-5",
            "status": "needs-review",
            "archive_followup_disposition_preview_ref": "disposition-preview",
            "notification_readiness_refs": ["notification-readiness"],
            "owner_handoff_refs": ["owner-handoff"],
            "followup_status_rollup_refs": ["status-rollup"],
            "open_followup_refs": ["open"],
            "blocked_followup_refs": ["blocked-none"],
            "resolved_followup_refs": ["resolved"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "preview_decision_refs": ["preview-decision"],
            "next_action_refs": ["next-action"],
        }
    )

    assert preview.readiness_state == "needs_review"
    assert preview.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_still_open" in preview.warnings


def test_blocked_followups_warning_drives_disposition_blocker_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "disposition-preview-6",
                    "status": "previewed",
                    "archive_followup_disposition_preview_ref": "disposition-preview",
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "open_followup_refs": ["open"],
                    "blocked_followup_refs": ["blocked"],
                    "resolved_followup_refs": ["resolved"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "preview_decision_refs": ["preview-decision"],
                    "next_action_refs": ["next-action"],
                    "blocked_followups_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_blocked_followups_detected"
    assert packet["next_actions"] == [
        "review_archive_followup_disposition_blockers",
        "refresh_archive_followup_disposition_preview_packet",
    ]


def test_preview_decision_warning_drives_decision_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "disposition-preview-7",
                    "status": "previewed",
                    "archive_followup_disposition_preview_ref": "disposition-preview",
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "preview_decision_refs": ["preview-decision"],
                    "next_action_refs": ["next-action"],
                    "preview_decision_conflict_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_decision_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_disposition_preview_decisions",
        "refresh_archive_followup_disposition_preview_packet",
    ]


def test_live_disposition_notification_taskboard_query_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "disposition-preview-8",
                    "status": "previewed",
                    "archive_followup_disposition_preview_ref": "disposition-preview",
                    "notification_readiness_refs": ["notification-readiness"],
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "open_followup_refs": ["open-none"],
                    "blocked_followup_refs": ["blocked-none"],
                    "resolved_followup_refs": ["resolved"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "preview_decision_refs": ["preview-decision"],
                    "next_action_refs": ["next-action"],
                    "candidate_disposition_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_operation_attempted" in packet["previews"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_disposition_preview_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_inventory"]


def test_dataclass_like_archive_followup_disposition_preview_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupDispositionPreview:
        preview_id: str
        status: str
        archive_followup_disposition_preview_ref: str
        notification_readiness_refs: list[str]
        owner_handoff_refs: list[str]
        followup_status_rollup_refs: list[str]
        open_followup_refs: list[str]
        blocked_followup_refs: list[str]
        resolved_followup_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        preview_decision_refs: list[str]
        next_action_refs: list[str]

    preview = summarize_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview(
        FollowupDispositionPreview(
            "disposition-preview-9",
            "complete",
            "disposition-preview",
            ["notification-readiness"],
            ["owner-handoff"],
            ["status-rollup"],
            ["open-none"],
            ["blocked-none"],
            ["resolved"],
            ["validation"],
            ["evidence"],
            ["preview-decision"],
            ["next-action"],
        )
    )

    assert preview.preview_id == "disposition-preview-9"
    assert preview.status == "complete"
    assert preview.readiness_state == "ready"
