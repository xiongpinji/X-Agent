from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt,
)


PACKET_POLICIES = {
    "followup_archive_export_owner_receipt_policy": "followup-archive-export-owner-receipt-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "owner_receipt_acknowledgement_policy": "owner-receipt-acknowledgement-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_ref": "followup-archive-export-owner-receipt",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_owner_receipt_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet(
        {
            **PACKET_POLICIES,
            "owner_receipts": [
                {
                    "owner_receipt_id": "owner-receipt-1",
                    "status": "acknowledged",
                    "archive_followup_export_owner_receipt_ref": "owner-receipt",
                    "export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["owner_receipt_count"] == 1
    assert packet["summary"]["export_closeout_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet(
        {
            "owner_receipts": [
                {
                    "owner_receipt_id": "owner-receipt-2",
                    "status": "acknowledged",
                    "archive_followup_export_owner_receipt_ref": "owner-receipt",
                    "export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_owner_receipt_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "owner_receipt_acknowledgement_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_owner_receipt_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet(
        {
            **PACKET_POLICIES,
            "owner_receipts": [
                {
                    "owner_receipt_id": "owner-receipt-3",
                    "status": "stale",
                    "archive_followup_export_owner_receipt_ref": "owner-receipt",
                    "export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    owner_receipt = packet["owner_receipts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_status_failed" in owner_receipt["blockers"]


def test_missing_archive_export_owner_receipt_refs_needs_review() -> None:
    owner_receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt(
        {
            "owner_receipt_id": "owner-receipt-4",
            "status": "acknowledged",
            "archive_followup_export_owner_receipt_ref": "owner-receipt",
        }
    )

    assert owner_receipt.readiness_state == "needs_review"
    assert "export_closeout_refs" in owner_receipt.missing_refs
    assert "export_review_refs" in owner_receipt.missing_refs
    assert "export_receipt_refs" in owner_receipt.missing_refs
    assert "owner_acknowledgement_refs" in owner_receipt.missing_refs
    assert "reviewer_acknowledgement_refs" in owner_receipt.missing_refs
    assert "closeout_decision_refs" in owner_receipt.missing_refs
    assert "validation_refs" in owner_receipt.missing_refs
    assert "evidence_refs" in owner_receipt.missing_refs
    assert "retention_refs" in owner_receipt.missing_refs
    assert "next_action_refs" in owner_receipt.missing_refs


def test_open_archive_export_owner_receipt_warns_until_acknowledgements_attach() -> None:
    owner_receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt(
        {
            "owner_receipt_id": "owner-receipt-5",
            "status": "needs-review",
            "archive_followup_export_owner_receipt_ref": "owner-receipt",
            "export_closeout_refs": ["export-closeout"],
            "export_review_refs": ["export-review"],
            "export_receipt_refs": ["export-receipt"],
            "owner_acknowledgement_refs": ["owner-ack"],
            "reviewer_acknowledgement_refs": ["reviewer-ack"],
            "closeout_decision_refs": ["closeout-decision"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "retention_refs": ["retention"],
            "next_action_refs": ["next-action"],
        }
    )

    assert owner_receipt.readiness_state == "needs_review"
    assert owner_receipt.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_still_open" in owner_receipt.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet(
        {
            **PACKET_POLICIES,
            "owner_receipts": [
                {
                    "owner_receipt_id": "owner-receipt-6",
                    "status": "acknowledged",
                    "archive_followup_export_owner_receipt_ref": "owner-receipt",
                    "export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_missing_evidence"
    assert "residual_risk_refs" in packet["owner_receipts"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet",
    ]


def test_owner_acknowledgement_warning_drives_owner_receipt_acknowledgement_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet(
        {
            **PACKET_POLICIES,
            "owner_receipts": [
                {
                    "owner_receipt_id": "owner-receipt-7",
                    "status": "acknowledged",
                    "archive_followup_export_owner_receipt_ref": "owner-receipt",
                    "export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "next_action_refs": ["next-action"],
                    "owner_acknowledgement_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_owner_acknowledgement_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_owner_receipt_acknowledgements",
        "refresh_archive_followup_export_owner_receipt_packet",
    ]


def test_live_archive_export_owner_receipt_file_write_index_owner_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet(
        {
            **PACKET_POLICIES,
            "owner_receipts": [
                {
                    "owner_receipt_id": "owner-receipt-8",
                    "status": "acknowledged",
                    "archive_followup_export_owner_receipt_ref": "owner-receipt",
                    "export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "next_action_refs": ["next-action"],
                    "owner_receipt_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_operation_attempted" in packet["owner_receipts"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_owner_receipt_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_inventory"]


def test_dataclass_like_archive_export_owner_receipt_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportOwnerReceipt:
        owner_receipt_id: str
        status: str
        archive_followup_export_owner_receipt_ref: str
        export_closeout_refs: list[str]
        export_review_refs: list[str]
        export_receipt_refs: list[str]
        owner_acknowledgement_refs: list[str]
        reviewer_acknowledgement_refs: list[str]
        closeout_decision_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        residual_risk_refs: list[str]
        retention_refs: list[str]
        next_action_refs: list[str]

    owner_receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt(
        FollowupArchiveExportOwnerReceipt(
            "owner-receipt-9",
            "complete",
            "owner-receipt",
            ["export-closeout"],
            ["export-review"],
            ["export-receipt"],
            ["owner-ack"],
            ["reviewer-ack"],
            ["closeout-decision"],
            ["validation"],
            ["evidence"],
            ["none"],
            ["retention"],
            ["next-action"],
        )
    )

    assert owner_receipt.owner_receipt_id == "owner-receipt-9"
    assert owner_receipt.status == "complete"
    assert owner_receipt.readiness_state == "ready"
