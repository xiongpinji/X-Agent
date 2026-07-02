from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt,
)


PACKET_POLICIES = {
    "followup_archive_export_final_receipt_policy": "followup-archive-export-final-receipt-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "final_receipt_acknowledgement_policy": "final-receipt-acknowledgement-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_ref": "followup-archive-export-final-receipt",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_final_receipt_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "final_receipt_id": "final-receipt-1",
                    "status": "receipted",
                    "archive_followup_export_final_receipt_ref": "final-receipt",
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "final_receipt_refs": ["final-receipt"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["final_receipt_count"] == 1
    assert packet["summary"]["final_receipt_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet(
        {
            "receipts": [
                {
                    "final_receipt_id": "final-receipt-2",
                    "status": "receipted",
                    "archive_followup_export_final_receipt_ref": "final-receipt",
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "final_receipt_refs": ["final-receipt"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_final_receipt_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "final_receipt_acknowledgement_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_final_receipt_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "final_receipt_id": "final-receipt-3",
                    "status": "stale",
                    "archive_followup_export_final_receipt_ref": "final-receipt",
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "final_receipt_refs": ["final-receipt"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    receipt = packet["receipts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_status_failed" in receipt["blockers"]


def test_missing_archive_export_final_receipt_refs_needs_review() -> None:
    receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt(
        {
            "final_receipt_id": "final-receipt-4",
            "status": "receipted",
            "archive_followup_export_final_receipt_ref": "final-receipt",
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert "final_audit_refs" in receipt.missing_refs
    assert "owner_closeout_refs" in receipt.missing_refs
    assert "owner_receipt_refs" in receipt.missing_refs
    assert "audit_decision_refs" in receipt.missing_refs
    assert "validation_refs" in receipt.missing_refs
    assert "evidence_refs" in receipt.missing_refs
    assert "retention_refs" in receipt.missing_refs
    assert "final_receipt_refs" in receipt.missing_refs
    assert "owner_signoff_refs" in receipt.missing_refs
    assert "next_action_refs" in receipt.missing_refs


def test_open_archive_export_final_receipt_warns_until_receipts_attach() -> None:
    receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt(
        {
            "final_receipt_id": "final-receipt-5",
            "status": "needs-review",
            "archive_followup_export_final_receipt_ref": "final-receipt",
            "final_audit_refs": ["final-audit"],
            "owner_closeout_refs": ["owner-closeout"],
            "owner_receipt_refs": ["owner-receipt"],
            "audit_decision_refs": ["audit-decision"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "retention_refs": ["retention"],
            "final_receipt_refs": ["final-receipt"],
            "owner_signoff_refs": ["owner-signoff"],
            "next_action_refs": ["next-action"],
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert receipt.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_still_open" in receipt.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "final_receipt_id": "final-receipt-6",
                    "status": "receipted",
                    "archive_followup_export_final_receipt_ref": "final-receipt",
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "final_receipt_refs": ["final-receipt"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_missing_evidence"
    assert "residual_risk_refs" in packet["receipts"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet",
    ]


def test_final_receipt_warning_drives_final_receipt_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "final_receipt_id": "final-receipt-7",
                    "status": "receipted",
                    "archive_followup_export_final_receipt_ref": "final-receipt",
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "final_receipt_refs": ["final-receipt"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                    "final_receipt_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_final_receipts",
        "refresh_archive_followup_export_final_receipt_packet",
    ]


def test_live_archive_export_final_receipt_file_write_index_persistence_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "final_receipt_id": "final-receipt-8",
                    "status": "receipted",
                    "archive_followup_export_final_receipt_ref": "final-receipt",
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "final_receipt_refs": ["final-receipt"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "next_action_refs": ["next-action"],
                    "final_receipt_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_operation_attempted" in packet["receipts"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_final_receipt_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt_inventory"]


def test_dataclass_like_archive_export_final_receipt_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportFinalReceipt:
        final_receipt_id: str
        status: str
        archive_followup_export_final_receipt_ref: str
        final_audit_refs: list[str]
        owner_closeout_refs: list[str]
        owner_receipt_refs: list[str]
        audit_decision_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        residual_risk_refs: list[str]
        retention_refs: list[str]
        final_receipt_refs: list[str]
        owner_signoff_refs: list[str]
        next_action_refs: list[str]

    receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_receipt(
        FollowupArchiveExportFinalReceipt(
            "final-receipt-9",
            "complete",
            "final-receipt",
            ["final-audit"],
            ["owner-closeout"],
            ["owner-receipt"],
            ["audit-decision"],
            ["validation"],
            ["evidence"],
            ["none"],
            ["retention"],
            ["final-receipt"],
            ["owner-signoff"],
            ["next-action"],
        )
    )

    assert receipt.final_receipt_id == "final-receipt-9"
    assert receipt.status == "complete"
    assert receipt.readiness_state == "ready"
