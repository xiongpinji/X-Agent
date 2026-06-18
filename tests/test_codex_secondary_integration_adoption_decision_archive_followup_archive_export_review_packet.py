from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review,
)


PACKET_POLICIES = {
    "followup_archive_export_review_policy": "followup-archive-export-review-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "export_review_decision_policy": "export-review-decision-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_review_ref": "followup-archive-export-review",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_review_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "export_review_id": "export-review-1",
                    "status": "approved",
                    "archive_followup_export_review_ref": "export-review",
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "residual_risk_refs": ["none"],
                    "review_decision_refs": ["review-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["review_count"] == 1
    assert packet["summary"]["review_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet(
        {
            "reviews": [
                {
                    "export_review_id": "export-review-2",
                    "status": "approved",
                    "archive_followup_export_review_ref": "export-review",
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "review_decision_refs": ["review-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_review_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "export_review_decision_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_review_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_review_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "export_review_id": "export-review-3",
                    "status": "stale",
                    "archive_followup_export_review_ref": "export-review",
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "review_decision_refs": ["review-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    review = packet["reviews"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_status_failed" in review["blockers"]


def test_missing_archive_export_review_refs_needs_review() -> None:
    review = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review(
        {
            "export_review_id": "export-review-4",
            "status": "approved",
            "archive_followup_export_review_ref": "export-review",
        }
    )

    assert review.readiness_state == "needs_review"
    assert "export_receipt_refs" in review.missing_refs
    assert "manifest_refs" in review.missing_refs
    assert "validation_refs" in review.missing_refs
    assert "retention_refs" in review.missing_refs
    assert "evidence_refs" in review.missing_refs
    assert "owner_acknowledgement_refs" in review.missing_refs
    assert "reviewer_acknowledgement_refs" in review.missing_refs
    assert "review_decision_refs" in review.missing_refs
    assert "next_action_refs" in review.missing_refs


def test_open_archive_export_review_warns_until_decisions_attach() -> None:
    review = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review(
        {
            "export_review_id": "export-review-5",
            "status": "needs-review",
            "archive_followup_export_review_ref": "export-review",
            "export_receipt_refs": ["export-receipt"],
            "manifest_refs": ["export-manifest"],
            "validation_refs": ["validation"],
            "retention_refs": ["retention"],
            "evidence_refs": ["evidence"],
            "owner_acknowledgement_refs": ["owner-ack"],
            "reviewer_acknowledgement_refs": ["reviewer-ack"],
            "review_decision_refs": ["review-decision"],
            "next_action_refs": ["next-action"],
        }
    )

    assert review.readiness_state == "needs_review"
    assert review.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_still_open" in review.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "export_review_id": "export-review-6",
                    "status": "approved",
                    "archive_followup_export_review_ref": "export-review",
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "review_decision_refs": ["review-decision"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_missing_evidence"
    assert "residual_risk_refs" in packet["reviews"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet",
    ]


def test_review_decision_warning_drives_review_decision_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "export_review_id": "export-review-7",
                    "status": "approved",
                    "archive_followup_export_review_ref": "export-review",
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "residual_risk_refs": ["none"],
                    "review_decision_refs": ["review-decision"],
                    "next_action_refs": ["next-action"],
                    "review_decision_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_decision_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_review_decisions",
        "refresh_archive_followup_export_review_packet",
    ]


def test_live_archive_export_review_file_write_index_decision_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "export_review_id": "export-review-8",
                    "status": "approved",
                    "archive_followup_export_review_ref": "export-review",
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "review_decision_refs": ["review-decision"],
                    "next_action_refs": ["next-action"],
                    "review_decision_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_operation_attempted" in packet["reviews"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_review_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review_inventory"]


def test_dataclass_like_archive_export_review_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportReview:
        export_review_id: str
        status: str
        archive_followup_export_review_ref: str
        export_receipt_refs: list[str]
        manifest_refs: list[str]
        validation_refs: list[str]
        retention_refs: list[str]
        evidence_refs: list[str]
        owner_acknowledgement_refs: list[str]
        reviewer_acknowledgement_refs: list[str]
        residual_risk_refs: list[str]
        review_decision_refs: list[str]
        next_action_refs: list[str]

    review = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_review(
        FollowupArchiveExportReview(
            "export-review-9",
            "complete",
            "export-review",
            ["export-receipt"],
            ["export-manifest"],
            ["validation"],
            ["retention"],
            ["evidence"],
            ["owner-ack"],
            ["reviewer-ack"],
            ["none"],
            ["review-decision"],
            ["next-action"],
        )
    )

    assert review.export_review_id == "export-review-9"
    assert review.status == "complete"
    assert review.readiness_state == "ready"
