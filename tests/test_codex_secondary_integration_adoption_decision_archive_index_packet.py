from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_index_packet import (
    build_codex_secondary_integration_adoption_decision_archive_index_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_index,
)


PACKET_POLICIES = {
    "adoption_decision_archive_policy": "adoption-decision-archive-policy",
    "archive_index_policy": "archive-index-policy",
    "retention_policy": "retention-policy",
    "lookup_key_policy": "lookup-key-policy",
    "secondary_integration_adoption_decision_archive_index_manifest_ref": "archive-index-manifest",
    "secondary_integration_adoption_decision_archive_governance_ref": "archive-governance",
}


def test_ready_secondary_integration_adoption_decision_archive_index_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_index_packet(
        {
            **PACKET_POLICIES,
            "archives": [
                {
                    "archive_id": "archive-1",
                    "status": "indexed",
                    "adoption_decision_archive_index_ref": "archive-index",
                    "adoption_decision_receipt_refs": ["decision-receipt"],
                    "decision_ledger_refs": ["decision-ledger"],
                    "accepted_disposition_refs": ["accepted"],
                    "deferred_disposition_refs": ["deferred"],
                    "rejected_disposition_refs": ["rejected"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "archive_refs": ["archive"],
                    "retention_refs": ["retention"],
                    "lookup_keys": ["candidate-a"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_index_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["archive_count"] == 1
    assert packet["summary"]["lookup_key_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_index_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_index_packet(
        {
            "archives": [
                {
                    "archive_id": "archive-2",
                    "status": "indexed",
                    "adoption_decision_archive_index_ref": "archive-index",
                    "adoption_decision_receipt_refs": ["decision-receipt"],
                    "decision_ledger_refs": ["decision-ledger"],
                    "accepted_disposition_refs": ["accepted"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "archive_refs": ["archive"],
                    "retention_refs": ["retention"],
                    "lookup_keys": ["candidate-a"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_index_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "adoption_decision_archive_policy_ref",
        "archive_index_policy_ref",
        "retention_policy_ref",
        "lookup_key_policy_ref",
        "secondary_integration_adoption_decision_archive_index_manifest_ref",
        "secondary_integration_adoption_decision_archive_governance_ref",
    ]


def test_failed_or_stale_archive_index_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_index_packet(
        {
            **PACKET_POLICIES,
            "archives": [
                {
                    "archive_id": "archive-3",
                    "status": "stale",
                    "adoption_decision_archive_index_ref": "archive-index",
                    "adoption_decision_receipt_refs": ["decision-receipt"],
                    "decision_ledger_refs": ["decision-ledger"],
                    "rejected_disposition_refs": ["rejected"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "archive_refs": ["archive"],
                    "retention_refs": ["retention"],
                    "lookup_keys": ["candidate-a"],
                }
            ],
        }
    )

    archive = packet["archives"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_index_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_index_status_failed" in archive["blockers"]


def test_missing_archive_index_refs_needs_review() -> None:
    archive = summarize_codex_secondary_integration_adoption_decision_archive_index(
        {
            "archive_id": "archive-4",
            "status": "indexed",
            "adoption_decision_archive_index_ref": "archive-index",
        }
    )

    assert archive.readiness_state == "needs_review"
    assert "adoption_decision_receipt_refs" in archive.missing_refs
    assert "decision_ledger_refs" in archive.missing_refs
    assert "candidate_disposition_refs" in archive.missing_refs
    assert "validation_refs" in archive.missing_refs
    assert "residual_risk_refs" in archive.missing_refs
    assert "handoff_refs" in archive.missing_refs
    assert "archive_refs" in archive.missing_refs
    assert "retention_refs" in archive.missing_refs
    assert "lookup_keys" in archive.missing_refs


def test_open_archive_index_warns_until_index_receipts_attach() -> None:
    archive = summarize_codex_secondary_integration_adoption_decision_archive_index(
        {
            "archive_id": "archive-5",
            "status": "needs-review",
            "adoption_decision_archive_index_ref": "archive-index",
            "adoption_decision_receipt_refs": ["decision-receipt"],
            "decision_ledger_refs": ["decision-ledger"],
            "deferred_disposition_refs": ["deferred"],
            "validation_refs": ["validation"],
            "residual_risk_refs": ["risk"],
            "handoff_refs": ["handoff"],
            "archive_refs": ["archive"],
            "retention_refs": ["retention"],
            "lookup_keys": ["candidate-a"],
        }
    )

    assert archive.readiness_state == "needs_review"
    assert archive.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_index_still_open" in archive.warnings


def test_retention_review_due_drives_retention_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_index_packet(
        {
            **PACKET_POLICIES,
            "archives": [
                {
                    "archive_id": "archive-6",
                    "status": "indexed",
                    "adoption_decision_archive_index_ref": "archive-index",
                    "adoption_decision_receipt_refs": ["decision-receipt"],
                    "decision_ledger_refs": ["decision-ledger"],
                    "accepted_disposition_refs": ["accepted"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "archive_refs": ["archive"],
                    "retention_refs": ["retention"],
                    "lookup_keys": ["candidate-a"],
                    "retention_review_due": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_index_retention_review_due"
    assert packet["next_actions"] == [
        "review_secondary_integration_archive_retention",
        "refresh_archive_index_packet",
    ]


def test_stale_archive_warning_drives_stale_archive_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_index_packet(
        {
            **PACKET_POLICIES,
            "archives": [
                {
                    "archive_id": "archive-7",
                    "status": "indexed",
                    "adoption_decision_archive_index_ref": "archive-index",
                    "adoption_decision_receipt_refs": ["decision-receipt"],
                    "decision_ledger_refs": ["decision-ledger"],
                    "accepted_disposition_refs": ["accepted"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "archive_refs": ["archive"],
                    "retention_refs": ["retention"],
                    "lookup_keys": ["candidate-a"],
                    "archive_stale": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_index_stale"
    assert packet["next_actions"] == [
        "review_stale_secondary_integration_archive_index",
        "refresh_archive_index_packet",
    ]


def test_live_archive_index_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_index_packet(
        {
            **PACKET_POLICIES,
            "archives": [
                {
                    "archive_id": "archive-8",
                    "status": "indexed",
                    "adoption_decision_archive_index_ref": "archive-index",
                    "adoption_decision_receipt_refs": ["decision-receipt"],
                    "decision_ledger_refs": ["decision-ledger"],
                    "accepted_disposition_refs": ["accepted"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "archive_refs": ["archive"],
                    "retention_refs": ["retention"],
                    "lookup_keys": ["candidate-a"],
                    "archive_index_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_index_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_index_operation_attempted" in packet["archives"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_index_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_index_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_index_inventory"]


def test_dataclass_like_archive_index_is_accepted_by_summarizer() -> None:
    @dataclass
    class ArchiveIndex:
        archive_id: str
        status: str
        adoption_decision_archive_index_ref: str
        adoption_decision_receipt_refs: list[str]
        decision_ledger_refs: list[str]
        accepted_disposition_refs: list[str]
        deferred_disposition_refs: list[str]
        rejected_disposition_refs: list[str]
        validation_refs: list[str]
        residual_risk_refs: list[str]
        handoff_refs: list[str]
        archive_refs: list[str]
        retention_refs: list[str]
        lookup_keys: list[str]

    archive = summarize_codex_secondary_integration_adoption_decision_archive_index(
        ArchiveIndex(
            "archive-9",
            "complete",
            "archive-index",
            ["decision-receipt"],
            ["decision-ledger"],
            ["accepted"],
            ["deferred"],
            ["rejected"],
            ["validation"],
            ["risk"],
            ["handoff"],
            ["archive"],
            ["retention"],
            ["candidate-a"],
        )
    )

    assert archive.archive_id == "archive-9"
    assert archive.status == "complete"
    assert archive.readiness_state == "ready"
