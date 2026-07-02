from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision,
)


PACKET_POLICIES = {
    "followup_archive_export_final_decision_policy": "followup-archive-export-final-decision-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "final_decision_policy": "final-final-decision-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_ref": "followup-archive-export-final-decision",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_final_decision_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "final_decision_id": "final-decision-1",
                    "status": "closed",
                    "archive_followup_export_final_decision_ref": "final-decision",
                    "final_review_refs": ["final-review"],
                    "final_closeout_refs": ["final-closeout"],
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-decision"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "final_decision_refs": ["final-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["final_decision_count"] == 1
    assert packet["summary"]["final_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet(
        {
            "decisions": [
                {
                    "final_decision_id": "final-decision-2",
                    "status": "closed",
                    "archive_followup_export_final_decision_ref": "final-decision",
                    "final_review_refs": ["final-review"],
                    "final_closeout_refs": ["final-closeout"],
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-decision"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "final_decision_refs": ["final-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_final_decision_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "final_decision_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_final_decision_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "final_decision_id": "final-decision-3",
                    "status": "stale",
                    "archive_followup_export_final_decision_ref": "final-decision",
                    "final_review_refs": ["final-review"],
                    "final_closeout_refs": ["final-closeout"],
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-decision"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "final_decision_refs": ["final-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    decision = packet["decisions"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_status_failed" in decision["blockers"]


def test_missing_archive_export_final_decision_refs_needs_review() -> None:
    decision = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision(
        {
            "final_decision_id": "final-decision-4",
            "status": "closed",
            "archive_followup_export_final_decision_ref": "final-decision",
        }
    )

    assert decision.readiness_state == "needs_review"
    assert "final_review_refs" in decision.missing_refs
    assert "final_closeout_refs" in decision.missing_refs
    assert "final_receipt_refs" in decision.missing_refs
    assert "final_audit_refs" in decision.missing_refs
    assert "owner_closeout_refs" in decision.missing_refs
    assert "owner_receipt_refs" in decision.missing_refs
    assert "audit_decision_refs" in decision.missing_refs
    assert "validation_refs" in decision.missing_refs
    assert "evidence_refs" in decision.missing_refs
    assert "retention_refs" in decision.missing_refs
    assert "owner_signoff_refs" in decision.missing_refs
    assert "final_decision_refs" in decision.missing_refs
    assert "next_action_refs" in decision.missing_refs


def test_open_archive_export_final_decision_warns_until_decisions_attach() -> None:
    decision = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision(
        {
            "final_decision_id": "final-decision-5",
            "status": "needs-review",
            "archive_followup_export_final_decision_ref": "final-decision",
            "final_review_refs": ["final-review"],
                    "final_closeout_refs": ["final-closeout"],
                    "final_receipt_refs": ["final-receipt"],
            "final_audit_refs": ["final-audit"],
            "owner_closeout_refs": ["owner-decision"],
            "owner_receipt_refs": ["owner-receipt"],
            "audit_decision_refs": ["audit-decision"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "retention_refs": ["retention"],
            "owner_signoff_refs": ["owner-signoff"],
            "final_decision_refs": ["final-decision"],
            "next_action_refs": ["next-action"],
        }
    )

    assert decision.readiness_state == "needs_review"
    assert decision.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_still_open" in decision.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "final_decision_id": "final-decision-6",
                    "status": "closed",
                    "archive_followup_export_final_decision_ref": "final-decision",
                    "final_review_refs": ["final-review"],
                    "final_closeout_refs": ["final-closeout"],
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-decision"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "final_decision_refs": ["final-decision"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_missing_evidence"
    assert "residual_risk_refs" in packet["decisions"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet",
    ]


def test_final_decision_warning_drives_final_decision_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "final_decision_id": "final-decision-7",
                    "status": "closed",
                    "archive_followup_export_final_decision_ref": "final-decision",
                    "final_review_refs": ["final-review"],
                    "final_closeout_refs": ["final-closeout"],
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-decision"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "final_decision_refs": ["final-decision"],
                    "next_action_refs": ["next-action"],
                    "final_decision_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_decision_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_final_decisions",
        "refresh_archive_followup_export_final_decision_packet",
    ]


def test_live_archive_export_final_decision_file_write_index_persistence_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "final_decision_id": "final-decision-8",
                    "status": "closed",
                    "archive_followup_export_final_decision_ref": "final-decision",
                    "final_review_refs": ["final-review"],
                    "final_closeout_refs": ["final-closeout"],
                    "final_receipt_refs": ["final-receipt"],
                    "final_audit_refs": ["final-audit"],
                    "owner_closeout_refs": ["owner-decision"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "audit_decision_refs": ["audit-decision"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "final_decision_refs": ["final-decision"],
                    "next_action_refs": ["next-action"],
                    "final_decision_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_operation_attempted" in packet["decisions"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_final_decision_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision_inventory"]


def test_dataclass_like_archive_export_final_decision_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportFinalDecision:
        final_decision_id: str
        status: str
        archive_followup_export_final_decision_ref: str
        final_review_refs: list[str]
        final_closeout_refs: list[str]
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
        final_decision_refs: list[str]
        next_action_refs: list[str]

    decision = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_decision(
        FollowupArchiveExportFinalDecision(
            "final-decision-9",
            "complete",
            "final-decision",
            ["final-review"],
            ["final-closeout"],
            ["final-receipt"],
            ["final-audit"],
            ["owner-decision"],
            ["owner-receipt"],
            ["audit-decision"],
            ["validation"],
            ["evidence"],
            ["none"],
            ["retention"],
            ["owner-signoff"],
            ["final-decision"],
            ["next-action"],
        )
    )

    assert decision.final_decision_id == "final-decision-9"
    assert decision.status == "complete"
    assert decision.readiness_state == "ready"
