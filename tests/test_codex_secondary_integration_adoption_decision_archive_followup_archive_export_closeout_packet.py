from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout,
)


PACKET_POLICIES = {
    "followup_archive_export_closeout_policy": "followup-archive-export-closeout-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "export_closeout_decision_policy": "export-closeout-decision-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_closeout_ref": "followup-archive-export-closeout",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_closeout_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "export_closeout_id": "export-closeout-1",
                    "status": "closed",
                    "archive_followup_export_closeout_ref": "export-closeout",
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "residual_risk_refs": ["none"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["closeout_count"] == 1
    assert packet["summary"]["closeout_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet(
        {
            "closeouts": [
                {
                    "export_closeout_id": "export-closeout-2",
                    "status": "closed",
                    "archive_followup_export_closeout_ref": "export-closeout",
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_closeout_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "export_closeout_decision_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_closeout_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_closeout_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "export_closeout_id": "export-closeout-3",
                    "status": "stale",
                    "archive_followup_export_closeout_ref": "export-closeout",
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    closeout = packet["closeouts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_status_failed" in closeout["blockers"]


def test_missing_archive_export_closeout_refs_needs_review() -> None:
    closeout = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout(
        {
            "export_closeout_id": "export-closeout-4",
            "status": "closed",
            "archive_followup_export_closeout_ref": "export-closeout",
        }
    )

    assert closeout.readiness_state == "needs_review"
    assert "export_review_refs" in closeout.missing_refs
    assert "export_receipt_refs" in closeout.missing_refs
    assert "manifest_refs" in closeout.missing_refs
    assert "validation_refs" in closeout.missing_refs
    assert "retention_refs" in closeout.missing_refs
    assert "evidence_refs" in closeout.missing_refs
    assert "owner_acknowledgement_refs" in closeout.missing_refs
    assert "reviewer_acknowledgement_refs" in closeout.missing_refs
    assert "closeout_decision_refs" in closeout.missing_refs
    assert "next_action_refs" in closeout.missing_refs


def test_open_archive_export_closeout_warns_until_decisions_attach() -> None:
    closeout = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout(
        {
            "export_closeout_id": "export-closeout-5",
            "status": "needs-review",
            "archive_followup_export_closeout_ref": "export-closeout",
            "export_review_refs": ["export-review"],
            "export_receipt_refs": ["export-receipt"],
            "manifest_refs": ["export-manifest"],
            "validation_refs": ["validation"],
            "retention_refs": ["retention"],
            "evidence_refs": ["evidence"],
            "owner_acknowledgement_refs": ["owner-ack"],
            "reviewer_acknowledgement_refs": ["reviewer-ack"],
            "closeout_decision_refs": ["closeout-decision"],
            "next_action_refs": ["next-action"],
        }
    )

    assert closeout.readiness_state == "needs_review"
    assert closeout.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_still_open" in closeout.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "export_closeout_id": "export-closeout-6",
                    "status": "closed",
                    "archive_followup_export_closeout_ref": "export-closeout",
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_missing_evidence"
    assert "residual_risk_refs" in packet["closeouts"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet",
    ]


def test_closeout_decision_warning_drives_closeout_decision_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "export_closeout_id": "export-closeout-7",
                    "status": "closed",
                    "archive_followup_export_closeout_ref": "export-closeout",
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "residual_risk_refs": ["none"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                    "closeout_decision_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_decision_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_closeout_decisions",
        "refresh_archive_followup_export_closeout_packet",
    ]


def test_live_archive_export_closeout_file_write_index_decision_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet(
        {
            **PACKET_POLICIES,
            "closeouts": [
                {
                    "export_closeout_id": "export-closeout-8",
                    "status": "closed",
                    "archive_followup_export_closeout_ref": "export-closeout",
                    "export_review_refs": ["export-review"],
                    "export_receipt_refs": ["export-receipt"],
                    "manifest_refs": ["export-manifest"],
                    "validation_refs": ["validation"],
                    "retention_refs": ["retention"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "closeout_decision_refs": ["closeout-decision"],
                    "next_action_refs": ["next-action"],
                    "closeout_decision_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_operation_attempted" in packet["closeouts"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_closeout_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout_inventory"]


def test_dataclass_like_archive_export_closeout_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportCloseout:
        export_closeout_id: str
        status: str
        archive_followup_export_closeout_ref: str
        export_review_refs: list[str]
        export_receipt_refs: list[str]
        manifest_refs: list[str]
        validation_refs: list[str]
        retention_refs: list[str]
        evidence_refs: list[str]
        owner_acknowledgement_refs: list[str]
        reviewer_acknowledgement_refs: list[str]
        residual_risk_refs: list[str]
        closeout_decision_refs: list[str]
        next_action_refs: list[str]

    closeout = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_closeout(
        FollowupArchiveExportCloseout(
            "export-closeout-9",
            "complete",
            "export-closeout",
            ["export-review"],
            ["export-receipt"],
            ["export-manifest"],
            ["validation"],
            ["retention"],
            ["evidence"],
            ["owner-ack"],
            ["reviewer-ack"],
            ["none"],
            ["closeout-decision"],
            ["next-action"],
        )
    )

    assert closeout.export_closeout_id == "export-closeout-9"
    assert closeout.status == "complete"
    assert closeout.readiness_state == "ready"
