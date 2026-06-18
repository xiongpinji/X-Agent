from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness,
)


PACKET_POLICIES = {
    "followup_notification_readiness_policy": "followup-notification-readiness-policy",
    "recipient_policy": "recipient-policy",
    "channel_policy": "channel-policy",
    "suppression_policy": "suppression-policy",
    "secondary_integration_adoption_decision_archive_followup_notification_readiness_manifest_ref": "followup-notification-readiness-manifest",
    "secondary_integration_adoption_decision_archive_followup_notification_governance_ref": "followup-notification-governance",
}


def test_ready_secondary_integration_archive_followup_notification_readiness_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet(
        {
            **PACKET_POLICIES,
            "notifications": [
                {
                    "notification_id": "notification-1",
                    "status": "prepared",
                    "archive_followup_notification_readiness_ref": "notification-readiness",
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "recipient_refs": ["recipient"],
                    "channel_policy_refs": ["channel-policy"],
                    "message_preview_refs": ["message-preview"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "suppression_refs": ["suppression"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["notification_count"] == 1
    assert packet["summary"]["message_preview_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet(
        {
            "notifications": [
                {
                    "notification_id": "notification-2",
                    "status": "prepared",
                    "archive_followup_notification_readiness_ref": "notification-readiness",
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "recipient_refs": ["recipient"],
                    "channel_policy_refs": ["channel-policy"],
                    "message_preview_refs": ["message-preview"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "suppression_refs": ["suppression"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_notification_readiness_policy_ref",
        "recipient_policy_ref",
        "channel_policy_ref",
        "suppression_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_notification_readiness_manifest_ref",
        "secondary_integration_adoption_decision_archive_followup_notification_governance_ref",
    ]


def test_failed_or_stale_followup_notification_readiness_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet(
        {
            **PACKET_POLICIES,
            "notifications": [
                {
                    "notification_id": "notification-3",
                    "status": "stale",
                    "archive_followup_notification_readiness_ref": "notification-readiness",
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "recipient_refs": ["recipient"],
                    "channel_policy_refs": ["channel-policy"],
                    "message_preview_refs": ["message-preview"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "suppression_refs": ["suppression"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    notification = packet["notifications"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_status_failed" in notification["blockers"]


def test_missing_followup_notification_readiness_refs_needs_review() -> None:
    notification = summarize_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness(
        {
            "notification_id": "notification-4",
            "status": "prepared",
            "archive_followup_notification_readiness_ref": "notification-readiness",
        }
    )

    assert notification.readiness_state == "needs_review"
    assert "owner_handoff_refs" in notification.missing_refs
    assert "followup_status_rollup_refs" in notification.missing_refs
    assert "recipient_refs" in notification.missing_refs
    assert "channel_policy_refs" in notification.missing_refs
    assert "message_preview_refs" in notification.missing_refs
    assert "validation_refs" in notification.missing_refs
    assert "evidence_refs" in notification.missing_refs
    assert "suppression_refs" in notification.missing_refs
    assert "next_action_refs" in notification.missing_refs


def test_open_followup_notification_readiness_warns_until_receipts_attach() -> None:
    notification = summarize_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness(
        {
            "notification_id": "notification-5",
            "status": "needs-review",
            "archive_followup_notification_readiness_ref": "notification-readiness",
            "owner_handoff_refs": ["owner-handoff"],
            "followup_status_rollup_refs": ["status-rollup"],
            "recipient_refs": ["recipient"],
            "channel_policy_refs": ["channel-policy"],
            "message_preview_refs": ["message-preview"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "suppression_refs": ["suppression"],
            "next_action_refs": ["next-action"],
        }
    )

    assert notification.readiness_state == "needs_review"
    assert notification.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_still_open" in notification.warnings


def test_recipient_warning_drives_recipient_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet(
        {
            **PACKET_POLICIES,
            "notifications": [
                {
                    "notification_id": "notification-6",
                    "status": "prepared",
                    "archive_followup_notification_readiness_ref": "notification-readiness",
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "recipient_refs": ["recipient"],
                    "channel_policy_refs": ["channel-policy"],
                    "message_preview_refs": ["message-preview"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "suppression_refs": ["suppression"],
                    "next_action_refs": ["next-action"],
                    "recipient_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_recipient_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_notification_recipients",
        "refresh_archive_followup_notification_readiness_packet",
    ]


def test_suppression_warning_drives_suppression_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet(
        {
            **PACKET_POLICIES,
            "notifications": [
                {
                    "notification_id": "notification-7",
                    "status": "prepared",
                    "archive_followup_notification_readiness_ref": "notification-readiness",
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "recipient_refs": ["recipient"],
                    "channel_policy_refs": ["channel-policy"],
                    "message_preview_refs": ["message-preview"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "suppression_refs": ["suppression"],
                    "next_action_refs": ["next-action"],
                    "suppression_conflict_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_suppression_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_notification_suppressions",
        "refresh_archive_followup_notification_readiness_packet",
    ]


def test_live_notification_issue_taskboard_query_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet(
        {
            **PACKET_POLICIES,
            "notifications": [
                {
                    "notification_id": "notification-8",
                    "status": "prepared",
                    "archive_followup_notification_readiness_ref": "notification-readiness",
                    "owner_handoff_refs": ["owner-handoff"],
                    "followup_status_rollup_refs": ["status-rollup"],
                    "recipient_refs": ["recipient"],
                    "channel_policy_refs": ["channel-policy"],
                    "message_preview_refs": ["message-preview"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "suppression_refs": ["suppression"],
                    "next_action_refs": ["next-action"],
                    "notification_send_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_operation_attempted" in packet["notifications"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_notification_readiness_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_inventory"]


def test_dataclass_like_archive_followup_notification_readiness_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupNoticeReadiness:
        notification_id: str
        status: str
        archive_followup_notification_readiness_ref: str
        owner_handoff_refs: list[str]
        followup_status_rollup_refs: list[str]
        recipient_refs: list[str]
        channel_policy_refs: list[str]
        message_preview_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        suppression_refs: list[str]
        next_action_refs: list[str]

    notification = summarize_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness(
        FollowupNoticeReadiness(
            "notification-9",
            "complete",
            "notification-readiness",
            ["owner-handoff"],
            ["status-rollup"],
            ["recipient"],
            ["channel-policy"],
            ["message-preview"],
            ["validation"],
            ["evidence"],
            ["suppression"],
            ["next-action"],
        )
    )

    assert notification.notification_id == "notification-9"
    assert notification.status == "complete"
    assert notification.readiness_state == "ready"
