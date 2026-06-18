from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_artifact_evidence_index_readiness_packet import (
    build_codex_artifact_evidence_index_readiness_packet,
    summarize_codex_artifact_evidence_index,
)


PACKET_POLICIES = {
    "artifact_policy": "artifact-policy",
    "evidence_index_policy": "evidence-index-policy",
    "provenance_policy": "provenance-policy",
    "retention_policy": "retention-policy",
    "artifact_evidence_manifest_ref": "artifact-evidence-manifest",
    "work_product_governance_ref": "work-product-governance",
}


def test_ready_artifact_evidence_index_has_work_product_evidence() -> None:
    packet = build_codex_artifact_evidence_index_readiness_packet(
        {
            **PACKET_POLICIES,
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "status": "indexed",
                    "artifact_ref": "artifact",
                    "evidence_index_refs": ["index"],
                    "provenance_refs": ["provenance"],
                    "retention_refs": ["retention"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "source_refs": ["source"],
                    "owner_refs": ["owner"],
                    "integrity_refs": ["checksum"],
                    "integrity_claimed": True,
                }
            ],
        }
    )

    assert packet["kind"] == "codex_artifact_evidence_index_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["artifact_count"] == 1
    assert packet["summary"]["evidence_index_ref_count"] == 1
    assert packet["next_actions"] == [
        "share_artifact_evidence_index_readiness_with_mainline"
    ]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_artifact_evidence_index_readiness_packet(
        {
            "artifacts": [
                {
                    "artifact_id": "artifact-2",
                    "status": "indexed",
                    "artifact_ref": "artifact",
                    "evidence_index_refs": ["index"],
                    "provenance_refs": ["provenance"],
                    "retention_refs": ["retention"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "source_refs": ["source"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == (
        "codex_artifact_evidence_index_packet_missing_evidence"
    )
    assert packet["packet_missing_refs"] == [
        "artifact_policy_ref",
        "evidence_index_policy_ref",
        "provenance_policy_ref",
        "retention_policy_ref",
        "artifact_evidence_manifest_ref",
        "work_product_governance_ref",
    ]


def test_missing_index_provenance_retention_handoff_source_and_owner_refs_needs_review() -> None:
    artifact = summarize_codex_artifact_evidence_index(
        {
            "artifact_id": "artifact-3",
            "status": "indexed",
            "artifact_ref": "artifact",
            "validation_receipt_refs": ["validation"],
        }
    )

    assert artifact.readiness_state == "needs_review"
    assert "evidence_index_refs" in artifact.missing_refs
    assert "provenance_refs" in artifact.missing_refs
    assert "retention_refs" in artifact.missing_refs
    assert "handoff_refs" in artifact.missing_refs
    assert "source_refs" in artifact.missing_refs
    assert "owner_refs" in artifact.missing_refs


def test_failed_or_orphaned_artifact_blocks_candidate() -> None:
    packet = build_codex_artifact_evidence_index_readiness_packet(
        {
            **PACKET_POLICIES,
            "artifacts": [
                {
                    "artifact_id": "artifact-4",
                    "status": "orphaned",
                    "artifact_ref": "artifact",
                    "evidence_index_refs": ["index"],
                    "provenance_refs": ["provenance"],
                    "retention_refs": ["retention"],
                    "validation_receipt_refs": ["validation"],
                    "source_refs": ["source"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    artifact = packet["artifacts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_artifact_evidence_index_status_failed"
    assert "handoff_refs" in artifact["missing_refs"]
    assert "failure_handoff_refs" in artifact["missing_refs"]


def test_integrity_claim_requires_integrity_refs() -> None:
    artifact = summarize_codex_artifact_evidence_index(
        {
            "artifact_id": "artifact-5",
            "status": "validated",
            "artifact_ref": "artifact",
            "evidence_index_refs": ["index"],
            "provenance_refs": ["provenance"],
            "retention_refs": ["retention"],
            "validation_receipt_refs": ["validation"],
            "handoff_refs": ["handoff"],
            "source_refs": ["source"],
            "owner_refs": ["owner"],
            "checksum_claimed": True,
        }
    )

    assert artifact.readiness_state == "needs_review"
    assert "integrity_refs" in artifact.missing_refs


def test_live_artifact_creation_indexing_or_storage_mutation_blocks_candidate() -> None:
    packet = build_codex_artifact_evidence_index_readiness_packet(
        {
            **PACKET_POLICIES,
            "artifacts": [
                {
                    "artifact_id": "artifact-6",
                    "status": "indexed",
                    "artifact_ref": "artifact",
                    "evidence_index_refs": ["index"],
                    "provenance_refs": ["provenance"],
                    "retention_refs": ["retention"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "source_refs": ["source"],
                    "owner_refs": ["owner"],
                    "storage_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == (
        "codex_artifact_evidence_index_live_operation_blocked"
    )
    assert "live_artifact_evidence_index_operation_attempted" in packet["artifacts"][0][
        "blockers"
    ]


def test_empty_payload_requests_artifact_evidence_inventory() -> None:
    packet = build_codex_artifact_evidence_index_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == [
        "provide_codex_artifact_evidence_index_inventory"
    ]


def test_dataclass_like_artifact_evidence_index_is_accepted_by_summarizer() -> None:
    @dataclass
    class ArtifactEvidence:
        artifact_id: str
        status: str
        artifact_ref: str
        evidence_index_refs: list[str]
        provenance_refs: list[str]
        retention_refs: list[str]
        validation_receipt_refs: list[str]
        handoff_refs: list[str]
        source_refs: list[str]
        owner_refs: list[str]
        integrity_refs: list[str]

    artifact = summarize_codex_artifact_evidence_index(
        ArtifactEvidence(
            "artifact-7",
            "validated",
            "artifact",
            ["index"],
            ["provenance"],
            ["retention"],
            ["validation"],
            ["handoff"],
            ["source"],
            ["owner"],
            ["integrity"],
        )
    )

    assert artifact.artifact_id == "artifact-7"
    assert artifact.status == "validated"
    assert artifact.readiness_state == "ready"
