from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_gap_matrix_traceability_readiness_packet import (
    build_codex_gap_matrix_traceability_readiness_packet,
    summarize_codex_gap_matrix_traceability,
)


PACKET_POLICIES = {
    "gap_matrix_policy": "gap-matrix-policy",
    "traceability_policy": "traceability-policy",
    "adoption_status_policy": "adoption-status-policy",
    "residual_gap_policy": "residual-gap-policy",
    "codex_gap_matrix_manifest_ref": "codex-gap-matrix-manifest",
    "codex_parity_governance_ref": "codex-parity-governance",
}


def test_ready_codex_gap_matrix_traceability_has_complete_evidence() -> None:
    packet = build_codex_gap_matrix_traceability_readiness_packet(
        {
            **PACKET_POLICIES,
            "capabilities": [
                {
                    "capability_id": "gap-1",
                    "status": "validated",
                    "capability_ref": "capability",
                    "competitor_source_refs": ["codex-source"],
                    "candidate_refs": ["candidate"],
                    "implemented_module_refs": ["module"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "adoption_status_refs": ["adoption-status"],
                    "owner_refs": ["owner"],
                    "residual_gap_refs": ["none"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_gap_matrix_traceability_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["capability_count"] == 1
    assert packet["summary"]["implemented_module_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_gap_matrix_traceability_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_gap_matrix_traceability_readiness_packet(
        {
            "capabilities": [
                {
                    "capability_id": "gap-2",
                    "status": "covered",
                    "capability_ref": "capability",
                    "competitor_source_refs": ["codex-source"],
                    "candidate_refs": ["candidate"],
                    "implemented_module_refs": ["module"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "adoption_status_refs": ["adoption-status"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_gap_matrix_traceability_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "gap_matrix_policy_ref",
        "traceability_policy_ref",
        "adoption_status_policy_ref",
        "residual_gap_policy_ref",
        "codex_gap_matrix_manifest_ref",
        "codex_parity_governance_ref",
    ]


def test_unmapped_or_regressed_gap_blocks_candidate() -> None:
    packet = build_codex_gap_matrix_traceability_readiness_packet(
        {
            **PACKET_POLICIES,
            "capabilities": [
                {
                    "capability_id": "gap-3",
                    "status": "unmapped",
                    "capability_ref": "capability",
                    "competitor_source_refs": ["codex-source"],
                    "candidate_refs": ["candidate"],
                    "handoff_refs": ["handoff"],
                    "adoption_status_refs": ["adoption-status"],
                    "owner_refs": ["owner"],
                    "residual_gap_refs": ["residual-gap"],
                }
            ],
        }
    )

    capability = packet["capabilities"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_gap_matrix_traceability_status_failed"
    assert "codex_gap_matrix_traceability_status_failed" in capability["blockers"]


def test_missing_capability_source_candidate_handoff_adoption_owner_and_residual_refs_needs_review() -> None:
    capability = summarize_codex_gap_matrix_traceability(
        {
            "capability_id": "gap-4",
            "status": "needs-review",
        }
    )

    assert capability.readiness_state == "needs_review"
    assert "capability_ref" in capability.missing_refs
    assert "competitor_source_refs" in capability.missing_refs
    assert "candidate_refs" in capability.missing_refs
    assert "handoff_refs" in capability.missing_refs
    assert "adoption_status_refs" in capability.missing_refs
    assert "owner_refs" in capability.missing_refs
    assert "residual_gap_refs" in capability.missing_refs


def test_ready_gap_requires_module_and_validation_refs() -> None:
    capability = summarize_codex_gap_matrix_traceability(
        {
            "capability_id": "gap-5",
            "status": "implemented",
            "capability_ref": "capability",
            "competitor_source_refs": ["codex-source"],
            "candidate_refs": ["candidate"],
            "handoff_refs": ["handoff"],
            "adoption_status_refs": ["adoption-status"],
            "owner_refs": ["owner"],
        }
    )

    assert capability.readiness_state == "needs_review"
    assert "implemented_module_refs" in capability.missing_refs
    assert "validation_receipt_refs" in capability.missing_refs


def test_residual_gap_warning_drives_next_candidate_decision() -> None:
    packet = build_codex_gap_matrix_traceability_readiness_packet(
        {
            **PACKET_POLICIES,
            "capabilities": [
                {
                    "capability_id": "gap-6",
                    "status": "covered",
                    "capability_ref": "capability",
                    "competitor_source_refs": ["codex-source"],
                    "candidate_refs": ["candidate"],
                    "implemented_module_refs": ["module"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "adoption_status_refs": ["adoption-status"],
                    "owner_refs": ["owner"],
                    "residual_gap_refs": ["residual-gap"],
                    "residual_gap_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_gap_matrix_traceability_residual_gap"
    assert packet["next_actions"] == [
        "review_codex_gap_matrix_residual_gaps",
        "decide_next_gap_candidate",
    ]


def test_live_manifest_stage_or_scoring_mutation_blocks_candidate() -> None:
    packet = build_codex_gap_matrix_traceability_readiness_packet(
        {
            **PACKET_POLICIES,
            "capabilities": [
                {
                    "capability_id": "gap-7",
                    "status": "covered",
                    "capability_ref": "capability",
                    "competitor_source_refs": ["codex-source"],
                    "candidate_refs": ["candidate"],
                    "implemented_module_refs": ["module"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "adoption_status_refs": ["adoption-status"],
                    "owner_refs": ["owner"],
                    "manifest_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_gap_matrix_traceability_live_operation_blocked"
    assert "live_codex_gap_matrix_traceability_operation_attempted" in packet["capabilities"][0]["blockers"]


def test_empty_payload_requests_codex_gap_matrix_traceability_inventory() -> None:
    packet = build_codex_gap_matrix_traceability_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_gap_matrix_traceability_inventory"]


def test_dataclass_like_codex_gap_matrix_traceability_is_accepted_by_summarizer() -> None:
    @dataclass
    class CodexGap:
        capability_id: str
        status: str
        capability_ref: str
        competitor_source_refs: list[str]
        candidate_refs: list[str]
        implemented_module_refs: list[str]
        validation_receipt_refs: list[str]
        handoff_refs: list[str]
        adoption_status_refs: list[str]
        owner_refs: list[str]
        residual_gap_refs: list[str]

    capability = summarize_codex_gap_matrix_traceability(
        CodexGap(
            "gap-8",
            "validated",
            "capability",
            ["codex-source"],
            ["candidate"],
            ["module"],
            ["validation"],
            ["handoff"],
            ["adoption-status"],
            ["owner"],
            ["none"],
        )
    )

    assert capability.capability_id == "gap-8"
    assert capability.status == "validated"
    assert capability.readiness_state == "ready"
