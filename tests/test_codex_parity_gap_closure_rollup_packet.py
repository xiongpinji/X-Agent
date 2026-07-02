from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_parity_gap_closure_rollup_packet import (
    build_codex_parity_gap_closure_rollup_packet,
    summarize_codex_parity_gap_closure_rollup,
)


PACKET_POLICIES = {
    "gap_closure_policy": "gap-closure-policy",
    "validation_chain_policy": "validation-chain-policy",
    "mainline_handoff_policy": "mainline-handoff-policy",
    "next_wave_policy": "next-wave-policy",
    "codex_parity_gap_closure_manifest_ref": "gap-closure-manifest",
    "codex_parity_closure_governance_ref": "gap-closure-governance",
}


def test_ready_codex_parity_gap_closure_rollup_has_complete_evidence() -> None:
    packet = build_codex_parity_gap_closure_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "closure-1",
                    "status": "closed",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_review_refs": ["owner-review"],
                    "accepted_candidate_refs": ["accepted-candidate"],
                    "deferred_candidate_refs": ["none"],
                    "residual_gap_refs": ["none"],
                    "validation_chain_refs": ["validation-chain"],
                    "mainline_handoff_refs": ["mainline-handoff"],
                    "artifact_refs": ["artifact"],
                    "next_wave_refs": ["next-wave"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_parity_gap_closure_rollup_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["rollup_count"] == 1
    assert packet["summary"]["accepted_candidate_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_parity_gap_closure_rollup_packet_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_parity_gap_closure_rollup_packet(
        {
            "rollups": [
                {
                    "rollup_id": "closure-2",
                    "status": "validated",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_review_refs": ["owner-review"],
                    "accepted_candidate_refs": ["accepted-candidate"],
                    "validation_chain_refs": ["validation-chain"],
                    "mainline_handoff_refs": ["mainline-handoff"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_parity_gap_closure_rollup_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "gap_closure_policy_ref",
        "validation_chain_policy_ref",
        "mainline_handoff_policy_ref",
        "next_wave_policy_ref",
        "codex_parity_gap_closure_manifest_ref",
        "codex_parity_closure_governance_ref",
    ]


def test_rejected_or_regressed_closure_rollup_blocks_candidate() -> None:
    packet = build_codex_parity_gap_closure_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "closure-3",
                    "status": "regressed",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_review_refs": ["owner-review"],
                    "accepted_candidate_refs": ["accepted-candidate"],
                    "validation_chain_refs": ["validation-chain"],
                    "mainline_handoff_refs": ["mainline-handoff"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    rollup = packet["rollups"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_parity_gap_closure_rollup_status_failed"
    assert "codex_parity_gap_closure_rollup_status_failed" in rollup["blockers"]


def test_missing_rollup_refs_needs_review() -> None:
    rollup = summarize_codex_parity_gap_closure_rollup(
        {
            "rollup_id": "closure-4",
            "status": "closed",
            "gap_matrix_ref": "gap-matrix",
        }
    )

    assert rollup.readiness_state == "needs_review"
    assert "owner_review_refs" in rollup.missing_refs
    assert "accepted_candidate_refs" in rollup.missing_refs
    assert "validation_chain_refs" in rollup.missing_refs
    assert "mainline_handoff_refs" in rollup.missing_refs
    assert "artifact_refs" in rollup.missing_refs


def test_open_rollup_requires_deferred_residual_and_next_wave_refs() -> None:
    rollup = summarize_codex_parity_gap_closure_rollup(
        {
            "rollup_id": "closure-5",
            "status": "needs-review",
            "gap_matrix_ref": "gap-matrix",
            "owner_review_refs": ["owner-review"],
            "validation_chain_refs": ["validation-chain"],
            "mainline_handoff_refs": ["mainline-handoff"],
            "artifact_refs": ["artifact"],
        }
    )

    assert rollup.readiness_state == "needs_review"
    assert "deferred_candidate_refs" in rollup.missing_refs
    assert "residual_gap_refs" in rollup.missing_refs
    assert "next_wave_refs" in rollup.missing_refs
    assert "codex_parity_gap_closure_rollup_still_open" in rollup.warnings


def test_residual_gap_warning_drives_next_wave_queue() -> None:
    packet = build_codex_parity_gap_closure_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "closure-6",
                    "status": "closed",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_review_refs": ["owner-review"],
                    "accepted_candidate_refs": ["accepted-candidate"],
                    "residual_gap_refs": ["residual-gap"],
                    "validation_chain_refs": ["validation-chain"],
                    "mainline_handoff_refs": ["mainline-handoff"],
                    "artifact_refs": ["artifact"],
                    "next_wave_refs": ["next-wave"],
                    "residual_gap_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_parity_gap_closure_rollup_residual_gap"
    assert packet["next_actions"] == ["review_codex_parity_residual_gaps", "queue_codex_parity_next_wave"]


def test_live_scoring_manifest_stage_or_decision_mutation_blocks_candidate() -> None:
    packet = build_codex_parity_gap_closure_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "closure-7",
                    "status": "approved",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_review_refs": ["owner-review"],
                    "accepted_candidate_refs": ["accepted-candidate"],
                    "validation_chain_refs": ["validation-chain"],
                    "mainline_handoff_refs": ["mainline-handoff"],
                    "artifact_refs": ["artifact"],
                    "scoring_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_parity_gap_closure_rollup_live_operation_blocked"
    assert "live_codex_parity_gap_closure_rollup_operation_attempted" in packet["rollups"][0]["blockers"]


def test_empty_payload_requests_codex_parity_gap_closure_rollup_inventory() -> None:
    packet = build_codex_parity_gap_closure_rollup_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_parity_gap_closure_rollup_inventory"]


def test_dataclass_like_gap_closure_rollup_is_accepted_by_summarizer() -> None:
    @dataclass
    class GapClosure:
        rollup_id: str
        status: str
        gap_matrix_ref: str
        owner_review_refs: list[str]
        accepted_candidate_refs: list[str]
        deferred_candidate_refs: list[str]
        residual_gap_refs: list[str]
        validation_chain_refs: list[str]
        mainline_handoff_refs: list[str]
        artifact_refs: list[str]
        next_wave_refs: list[str]

    rollup = summarize_codex_parity_gap_closure_rollup(
        GapClosure(
            "closure-8",
            "validated",
            "gap-matrix",
            ["owner-review"],
            ["accepted-candidate"],
            ["deferred-candidate"],
            ["none"],
            ["validation-chain"],
            ["mainline-handoff"],
            ["artifact"],
            ["next-wave"],
        )
    )

    assert rollup.rollup_id == "closure-8"
    assert rollup.status == "validated"
    assert rollup.readiness_state == "ready"
