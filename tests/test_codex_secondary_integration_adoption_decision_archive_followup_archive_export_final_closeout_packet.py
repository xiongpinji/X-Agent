from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout,
)


PACKET_POLICIES = {
    "followup_archive_export_final_closeout_policy": "followup-archive-export-final-closeout-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "final_closeout_decision_policy": "final-closeout-decision-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_ref": "followup-archive-export-final-closeout",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_final_closeout_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "final_closeout_id": "final-closeout-1",
                    "status": "closed",
                    "archive_followup_export_final_closeout_ref": "final-closeout",
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["final_closeout_count"] == 1
    assert packet["summary"]["closeout_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet(
        {
            "closeouts": [
                {
                    "final_closeout_id": "final-closeout-2",
                    "status": "closed",
                    "archive_followup_export_final_closeout_ref": "final-closeout",
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_final_closeout_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "final_closeout_decision_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_final_closeout_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "final_closeout_id": "final-closeout-3",
                    "status": "stale",
                    "archive_followup_export_final_closeout_ref": "final-closeout",
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    closeout = packet["closeouts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_status_failed" in closeout["blockers"]


def test_missing_archive_export_final_closeout_refs_needs_review() -> None:
    closeout = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout(
        {
            "final_closeout_id": "final-closeout-4",
            "status": "closed",
            "archive_followup_export_final_closeout_ref": "final-closeout",
        }
    )

    assert closeout.readiness_state == "needs_review"
    assert "final_receipt_refs" in closeout.missing_refs
    assert "final_audit_refs" in closeout.missing_refs
    assert "owner_closeout_refs" in closeout.missing_refs
    assert "owner_receipt_refs" in closeout.missing_refs
    assert "audit_decision_refs" in closeout.missing_refs
    assert "validation_refs" in closeout.missing_refs
    assert "evidence_refs" in closeout.missing_refs
    assert "retention_refs" in closeout.missing_refs
    assert "owner_signoff_refs" in closeout.missing_refs
    assert "closeout_decision_refs" in closeout.missing_refs
    assert "next_action_refs" in closeout.missing_refs


def test_open_archive_export_final_closeout_warns_until_closeouts_attach() -> None:
    closeout = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout(
        {
            "final_closeout_id": "final-closeout-5",
            "status": "needs-review",
            "archive_followup_export_final_closeout_ref": "final-closeout",
            "final_receipt_refs": ["final-receipt"],
            "final_audit_refs": ["final-audit"],
            "owner_closeout_refs": ["owner-closeout"],
            "owner_receipt_refs": ["owner-receipt"],
            "audit_decision_refs": ["audit-decision"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "retention_refs": ["retention"],
            "owner_signoff_refs": ["owner-signoff"],
            "closeout_decision_refs": ["closeout-decision"],
            "next_action_refs": ["next-action"],
        }
    )

    assert closeout.readiness_state == "needs_review"
    assert closeout.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_still_open" in closeout.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "final_closeout_id": "final-closeout-6",
                    "status": "closed",
                    "archive_followup_export_final_closeout_ref": "final-closeout",
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_missing_evidence"
    assert "residual_risk_refs" in packet["closeouts"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet",
    ]


def test_final_closeout_warning_drives_final_closeout_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "final_closeout_id": "final-closeout-7",
                    "status": "closed",
                    "archive_followup_export_final_closeout_ref": "final-closeout",
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                    "final_closeout_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_final_closeouts",
        "refresh_archive_followup_export_final_closeout_packet",
    ]


def test_live_archive_export_final_closeout_file_write_index_persistence_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "final_closeout_id": "final-closeout-8",
                    "status": "closed",
                    "archive_followup_export_final_closeout_ref": "final-closeout",
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                    "final_closeout_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_operation_attempted" in packet["closeouts"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_final_closeout_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_inventory"]


def test_dataclass_like_archive_export_final_closeout_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportFinalCloseout:
        final_closeout_id: str
        status: str
        archive_followup_export_final_closeout_ref: str
        final_receipt_refs: list[str]
        final_audit_refs: list[str]
        owner_closeout_refs: list[str]
        owner_receipt_refs: list[str]
        audit_decision_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        residual_risk_refs: list[str]
        retention_refs: list[str]
        owner_signoff_refs: list[str]
        closeout_decision_refs: list[str]
        next_action_refs: list[str]

    closeout = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout(
        FollowupArchiveExportFinalCloseout(
            "final-closeout-9",
            "complete",
            "final-closeout",
            ["final-receipt"],
            ["final-audit"],
            ["owner-closeout"],
            ["owner-receipt"],
            ["audit-decision"],
            ["validation"],
            ["evidence"],
            ["none"],
            ["retention"],
            ["owner-signoff"],
            ["closeout-decision"],
            ["next-action"],
        )
    )

    assert closeout.final_closeout_id == "final-closeout-9"
    assert closeout.status == "complete"
    assert closeout.readiness_state == "ready"
