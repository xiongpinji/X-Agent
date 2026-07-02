from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout,
)


PACKET_POLICIES = {
    "followup_archive_export_owner_closeout_policy": "followup-archive-export-owner-closeout-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "owner_signoff_policy": "owner-signoff-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_ref": "followup-archive-export-owner-closeout",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_owner_closeout_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet(
        {
            **PACKET_POLICIES,
            "owner_closeouts": [
                {
                    "owner_closeout_id": "owner-closeout-1",
                    "status": "signed-off",
                    "archive_followup_export_owner_closeout_ref": "owner-closeout",
                    "archive_export_closeout_refs": ["export-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["owner_closeout_count"] == 1
    assert packet["summary"]["owner_signoff_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet(
        {
            "owner_closeouts": [
                {
                    "owner_closeout_id": "owner-closeout-2",
                    "status": "signed-off",
                    "archive_followup_export_owner_closeout_ref": "owner-closeout",
                    "archive_export_closeout_refs": ["export-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_owner_closeout_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "owner_signoff_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_owner_closeout_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet(
        {
            **PACKET_POLICIES,
            "owner_closeouts": [
                {
                    "owner_closeout_id": "owner-closeout-3",
                    "status": "stale",
                    "archive_followup_export_owner_closeout_ref": "owner-closeout",
                    "archive_export_closeout_refs": ["export-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    owner_closeout = packet["owner_closeouts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_status_failed" in owner_closeout["blockers"]


def test_missing_archive_export_owner_closeout_refs_needs_review() -> None:
    owner_closeout = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout(
        {
            "owner_closeout_id": "owner-closeout-4",
            "status": "signed-off",
            "archive_followup_export_owner_closeout_ref": "owner-closeout",
        }
    )

    assert owner_closeout.readiness_state == "needs_review"
    assert "archive_export_closeout_refs" in owner_closeout.missing_refs
    assert "owner_receipt_refs" in owner_closeout.missing_refs
    assert "owner_acknowledgement_refs" in owner_closeout.missing_refs
    assert "reviewer_acknowledgement_refs" in owner_closeout.missing_refs
    assert "closeout_decision_refs" in owner_closeout.missing_refs
    assert "validation_refs" in owner_closeout.missing_refs
    assert "evidence_refs" in owner_closeout.missing_refs
    assert "retention_refs" in owner_closeout.missing_refs
    assert "owner_signoff_refs" in owner_closeout.missing_refs
    assert "next_action_refs" in owner_closeout.missing_refs


def test_open_archive_export_owner_closeout_warns_until_signoffs_attach() -> None:
    owner_closeout = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout(
        {
            "owner_closeout_id": "owner-closeout-5",
            "status": "needs-review",
            "archive_followup_export_owner_closeout_ref": "owner-closeout",
            "archive_export_closeout_refs": ["export-closeout"],
            "owner_receipt_refs": ["owner-receipt"],
            "owner_acknowledgement_refs": ["owner-ack"],
            "reviewer_acknowledgement_refs": ["reviewer-ack"],
            "closeout_decision_refs": ["closeout-decision"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "retention_refs": ["retention"],
            "owner_signoff_refs": ["owner-signoff"],
            "next_action_refs": ["next-action"],
        }
    )

    assert owner_closeout.readiness_state == "needs_review"
    assert owner_closeout.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_still_open" in owner_closeout.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet(
        {
            **PACKET_POLICIES,
            "owner_closeouts": [
                {
                    "owner_closeout_id": "owner-closeout-6",
                    "status": "signed-off",
                    "archive_followup_export_owner_closeout_ref": "owner-closeout",
                    "archive_export_closeout_refs": ["export-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_missing_evidence"
    assert "residual_risk_refs" in packet["owner_closeouts"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet",
    ]


def test_owner_signoff_warning_drives_owner_closeout_signoff_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet(
        {
            **PACKET_POLICIES,
            "owner_closeouts": [
                {
                    "owner_closeout_id": "owner-closeout-7",
                    "status": "signed-off",
                    "archive_followup_export_owner_closeout_ref": "owner-closeout",
                    "archive_export_closeout_refs": ["export-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                    "owner_signoff_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_owner_signoff_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_owner_closeout_signoffs",
        "refresh_archive_followup_export_owner_closeout_packet",
    ]


def test_live_archive_export_owner_closeout_file_write_index_owner_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet(
        {
            **PACKET_POLICIES,
            "owner_closeouts": [
                {
                    "owner_closeout_id": "owner-closeout-8",
                    "status": "signed-off",
                    "archive_followup_export_owner_closeout_ref": "owner-closeout",
                    "archive_export_closeout_refs": ["export-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                    "owner_signoff_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_operation_attempted" in packet["owner_closeouts"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_owner_closeout_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout_inventory"]


def test_dataclass_like_archive_export_owner_closeout_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportOwnerCloseout:
        owner_closeout_id: str
        status: str
        archive_followup_export_owner_closeout_ref: str
        archive_export_closeout_refs: list[str]
        owner_receipt_refs: list[str]
        owner_acknowledgement_refs: list[str]
        reviewer_acknowledgement_refs: list[str]
        closeout_decision_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        residual_risk_refs: list[str]
        retention_refs: list[str]
        owner_signoff_refs: list[str]
        next_action_refs: list[str]

    owner_closeout = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_closeout(
        FollowupArchiveExportOwnerCloseout(
            "owner-closeout-9",
            "complete",
            "owner-closeout",
            ["export-closeout"],
            ["owner-receipt"],
            ["owner-ack"],
            ["reviewer-ack"],
            ["closeout-decision"],
            ["validation"],
            ["evidence"],
            ["none"],
            ["retention"],
            ["owner-signoff"],
            ["next-action"],
        )
    )

    assert owner_closeout.owner_closeout_id == "owner-closeout-9"
    assert owner_closeout.status == "complete"
    assert owner_closeout.readiness_state == "ready"
