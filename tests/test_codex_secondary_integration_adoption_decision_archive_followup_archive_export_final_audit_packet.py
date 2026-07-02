from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit,
)


PACKET_POLICIES = {
    "followup_archive_export_final_audit_policy": "followup-archive-export-final-audit-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "export_audit_decision_policy": "export-audit-decision-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_ref": "followup-archive-export-final-audit",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_final_audit_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet(
        {
            **PACKET_POLICIES,
            "audits": [
                {
                    "final_audit_id": "final-audit-1",
                    "status": "audited",
                    "archive_followup_export_final_audit_ref": "final-audit",
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "archive_export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "audit_decision_refs": ["audit-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["final_audit_count"] == 1
    assert packet["summary"]["audit_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet(
        {
            "audits": [
                {
                    "final_audit_id": "final-audit-2",
                    "status": "audited",
                    "archive_followup_export_final_audit_ref": "final-audit",
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "archive_export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "audit_decision_refs": ["audit-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_final_audit_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "export_audit_decision_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_final_audit_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet(
        {
            **PACKET_POLICIES,
            "audits": [
                {
                    "final_audit_id": "final-audit-3",
                    "status": "stale",
                    "archive_followup_export_final_audit_ref": "final-audit",
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "archive_export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "audit_decision_refs": ["audit-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    audit = packet["audits"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_status_failed" in audit["blockers"]


def test_missing_archive_export_final_audit_refs_needs_review() -> None:
    audit = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit(
        {
            "final_audit_id": "final-audit-4",
            "status": "audited",
            "archive_followup_export_final_audit_ref": "final-audit",
        }
    )

    assert audit.readiness_state == "needs_review"
    assert "owner_closeout_refs" in audit.missing_refs
    assert "owner_receipt_refs" in audit.missing_refs
    assert "archive_export_closeout_refs" in audit.missing_refs
    assert "export_review_refs" in audit.missing_refs
    assert "export_receipt_refs" in audit.missing_refs
    assert "manifest_refs" in audit.missing_refs
    assert "validation_refs" in audit.missing_refs
    assert "evidence_refs" in audit.missing_refs
    assert "retention_refs" in audit.missing_refs
    assert "owner_signoff_refs" in audit.missing_refs
    assert "audit_decision_refs" in audit.missing_refs
    assert "next_action_refs" in audit.missing_refs


def test_open_archive_export_final_audit_warns_until_decisions_attach() -> None:
    audit = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit(
        {
            "final_audit_id": "final-audit-5",
            "status": "needs-review",
            "archive_followup_export_final_audit_ref": "final-audit",
            "owner_closeout_refs": ["owner-closeout"],
            "owner_receipt_refs": ["owner-receipt"],
            "archive_export_closeout_refs": ["export-closeout"],
            "export_review_refs": ["export-review"],
            "export_receipt_refs": ["export-receipt"],
            "manifest_refs": ["export-manifest"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "retention_refs": ["retention"],
            "owner_signoff_refs": ["owner-signoff"],
            "audit_decision_refs": ["audit-decision"],
            "next_action_refs": ["next-action"],
        }
    )

    assert audit.readiness_state == "needs_review"
    assert audit.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_still_open" in audit.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet(
        {
            **PACKET_POLICIES,
            "audits": [
                {
                    "final_audit_id": "final-audit-6",
                    "status": "audited",
                    "archive_followup_export_final_audit_ref": "final-audit",
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "archive_export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "audit_decision_refs": ["audit-decision"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_missing_evidence"
    assert "residual_risk_refs" in packet["audits"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet",
    ]


def test_audit_decision_warning_drives_final_audit_decision_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet(
        {
            **PACKET_POLICIES,
            "audits": [
                {
                    "final_audit_id": "final-audit-7",
                    "status": "audited",
                    "archive_followup_export_final_audit_ref": "final-audit",
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "archive_export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "audit_decision_refs": ["audit-decision"],
                    "next_action_refs": ["next-action"],
                    "audit_decision_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_decision_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_final_audit_decisions",
        "refresh_archive_followup_export_final_audit_packet",
    ]


def test_live_archive_export_final_audit_file_write_index_decision_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet(
        {
            **PACKET_POLICIES,
            "audits": [
                {
                    "final_audit_id": "final-audit-8",
                    "status": "audited",
                    "archive_followup_export_final_audit_ref": "final-audit",
                    "owner_closeout_refs": ["owner-closeout"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "archive_export_closeout_refs": ["export-closeout"],
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "retention_refs": ["retention"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "audit_decision_refs": ["audit-decision"],
                    "next_action_refs": ["next-action"],
                    "final_audit_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_operation_attempted" in packet["audits"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_final_audit_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit_inventory"]


def test_dataclass_like_archive_export_final_audit_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportFinalAudit:
        final_audit_id: str
        status: str
        archive_followup_export_final_audit_ref: str
        owner_closeout_refs: list[str]
        owner_receipt_refs: list[str]
        archive_export_closeout_refs: list[str]
        export_review_refs: list[str]
        export_receipt_refs: list[str]
        manifest_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        residual_risk_refs: list[str]
        retention_refs: list[str]
        owner_signoff_refs: list[str]
        audit_decision_refs: list[str]
        next_action_refs: list[str]

    audit = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_audit(
        FollowupArchiveExportFinalAudit(
            "final-audit-9",
            "complete",
            "final-audit",
            ["owner-closeout"],
            ["owner-receipt"],
            ["export-closeout"],
            ["export-review"],
            ["export-receipt"],
            ["export-manifest"],
            ["validation"],
            ["evidence"],
            ["none"],
            ["retention"],
            ["owner-signoff"],
            ["audit-decision"],
            ["next-action"],
        )
    )

    assert audit.final_audit_id == "final-audit-9"
    assert audit.status == "complete"
    assert audit.readiness_state == "ready"
