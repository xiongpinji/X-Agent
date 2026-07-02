from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest,
)


PACKET_POLICIES = {
    "followup_archive_export_manifest_policy": "followup-archive-export-manifest-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "export_validation_policy": "export-validation-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_manifest_ref": "followup-archive-export-manifest",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_manifest_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet(
        {
            **PACKET_POLICIES,
            "exports": [
                {
                    "export_id": "export-1",
                    "status": "manifested",
                    "archive_followup_export_manifest_ref": "export-manifest",
                    "closure_receipt_refs": ["closure-receipt"],
                    "closure_readiness_refs": ["closure-readiness"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "receipt_retention_refs": ["retention"],
                    "export_manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "archive_index_refs": ["archive-index"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["export_count"] == 1
    assert packet["summary"]["archive_index_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet(
        {
            "exports": [
                {
                    "export_id": "export-2",
                    "status": "manifested",
                    "archive_followup_export_manifest_ref": "export-manifest",
                    "closure_receipt_refs": ["closure-receipt"],
                    "closure_readiness_refs": ["closure-readiness"],
                    "evidence_refs": ["evidence"],
                    "receipt_retention_refs": ["retention"],
                    "export_manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "archive_index_refs": ["archive-index"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_manifest_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "export_validation_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_manifest_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_manifest_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet(
        {
            **PACKET_POLICIES,
            "exports": [
                {
                    "export_id": "export-3",
                    "status": "stale",
                    "archive_followup_export_manifest_ref": "export-manifest",
                    "closure_receipt_refs": ["closure-receipt"],
                    "closure_readiness_refs": ["closure-readiness"],
                    "evidence_refs": ["evidence"],
                    "receipt_retention_refs": ["retention"],
                    "export_manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "archive_index_refs": ["archive-index"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    export = packet["exports"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_status_failed" in export["blockers"]


def test_missing_archive_export_manifest_refs_needs_review() -> None:
    export = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest(
        {
            "export_id": "export-4",
            "status": "manifested",
            "archive_followup_export_manifest_ref": "export-manifest",
        }
    )

    assert export.readiness_state == "needs_review"
    assert "closure_receipt_refs" in export.missing_refs
    assert "closure_readiness_refs" in export.missing_refs
    assert "evidence_refs" in export.missing_refs
    assert "receipt_retention_refs" in export.missing_refs
    assert "export_manifest_refs" in export.missing_refs
    assert "validation_refs" in export.missing_refs
    assert "archive_index_refs" in export.missing_refs
    assert "next_action_refs" in export.missing_refs


def test_open_archive_export_manifest_warns_until_receipts_attach() -> None:
    export = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest(
        {
            "export_id": "export-5",
            "status": "needs-review",
            "archive_followup_export_manifest_ref": "export-manifest",
            "closure_receipt_refs": ["closure-receipt"],
            "closure_readiness_refs": ["closure-readiness"],
            "evidence_refs": ["evidence"],
            "receipt_retention_refs": ["retention"],
            "export_manifest_refs": ["export-manifest"],
            "validation_refs": ["validation"],
            "archive_index_refs": ["archive-index"],
            "next_action_refs": ["next-action"],
        }
    )

    assert export.readiness_state == "needs_review"
    assert export.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_still_open" in export.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet(
        {
            **PACKET_POLICIES,
            "exports": [
                {
                    "export_id": "export-6",
                    "status": "manifested",
                    "archive_followup_export_manifest_ref": "export-manifest",
                    "closure_receipt_refs": ["closure-receipt"],
                    "closure_readiness_refs": ["closure-readiness"],
                    "evidence_refs": ["evidence"],
                    "receipt_retention_refs": ["retention"],
                    "export_manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "archive_index_refs": ["archive-index"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_missing_evidence"
    assert "residual_risk_refs" in packet["exports"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet",
    ]


def test_export_manifest_drift_warning_drives_drift_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet(
        {
            **PACKET_POLICIES,
            "exports": [
                {
                    "export_id": "export-7",
                    "status": "manifested",
                    "archive_followup_export_manifest_ref": "export-manifest",
                    "closure_receipt_refs": ["closure-receipt"],
                    "closure_readiness_refs": ["closure-readiness"],
                    "evidence_refs": ["evidence"],
                    "receipt_retention_refs": ["retention"],
                    "export_manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "archive_index_refs": ["archive-index"],
                    "next_action_refs": ["next-action"],
                    "export_manifest_drift_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_drift_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_manifest_drift",
        "refresh_archive_followup_export_manifest_packet",
    ]


def test_live_archive_export_file_write_index_report_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet(
        {
            **PACKET_POLICIES,
            "exports": [
                {
                    "export_id": "export-8",
                    "status": "manifested",
                    "archive_followup_export_manifest_ref": "export-manifest",
                    "closure_receipt_refs": ["closure-receipt"],
                    "closure_readiness_refs": ["closure-readiness"],
                    "evidence_refs": ["evidence"],
                    "receipt_retention_refs": ["retention"],
                    "export_manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "archive_index_refs": ["archive-index"],
                    "next_action_refs": ["next-action"],
                    "archive_export_file_write_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_operation_attempted" in packet["exports"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_manifest_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest_inventory"]


def test_dataclass_like_archive_export_manifest_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportManifest:
        export_id: str
        status: str
        archive_followup_export_manifest_ref: str
        closure_receipt_refs: list[str]
        closure_readiness_refs: list[str]
        evidence_refs: list[str]
        residual_risk_refs: list[str]
        receipt_retention_refs: list[str]
        export_manifest_refs: list[str]
        validation_refs: list[str]
        archive_index_refs: list[str]
        next_action_refs: list[str]

    export = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_manifest(
        FollowupArchiveExportManifest(
            "export-9",
            "complete",
            "export-manifest",
            ["closure-receipt"],
            ["closure-readiness"],
            ["evidence"],
            ["none"],
            ["retention"],
            ["export-manifest"],
            ["validation"],
            ["archive-index"],
            ["next-action"],
        )
    )

    assert export.export_id == "export-9"
    assert export.status == "complete"
    assert export.readiness_state == "ready"
