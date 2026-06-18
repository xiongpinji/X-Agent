from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_mainline_adoption_readiness_rollup_packet import (
    build_codex_mainline_adoption_readiness_rollup_packet,
    summarize_codex_mainline_adoption_readiness_rollup,
)


PACKET_POLICIES = {
    "mainline_adoption_policy": "mainline-adoption-policy",
    "secondary_candidate_policy": "secondary-candidate-policy",
    "integration_risk_policy": "integration-risk-policy",
    "skipped_item_policy": "skipped-item-policy",
    "mainline_adoption_readiness_manifest_ref": "mainline-adoption-readiness-manifest",
    "secondary_integration_governance_ref": "secondary-integration-governance",
}


def test_ready_mainline_adoption_readiness_rollup_has_complete_evidence() -> None:
    packet = build_codex_mainline_adoption_readiness_rollup_packet(
        {
            **PACKET_POLICIES,
            "adoptions": [
                {
                    "adoption_id": "adoption-1",
                    "status": "approved",
                    "secondary_candidate_ref": "secondary-candidate",
                    "closure_rollup_refs": ["closure-rollup"],
                    "owner_review_refs": ["owner-review"],
                    "validation_chain_refs": ["validation-chain"],
                    "integration_risk_refs": ["risk-register"],
                    "skipped_item_refs": ["skipped-items"],
                    "mainline_decision_refs": ["mainline-decision"],
                    "artifact_refs": ["artifact"],
                    "next_step_refs": ["next-step"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_mainline_adoption_readiness_rollup_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["adoption_count"] == 1
    assert packet["summary"]["mainline_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_mainline_adoption_readiness_rollup_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_mainline_adoption_readiness_rollup_packet(
        {
            "adoptions": [
                {
                    "adoption_id": "adoption-2",
                    "status": "validated",
                    "secondary_candidate_ref": "secondary-candidate",
                    "closure_rollup_refs": ["closure-rollup"],
                    "owner_review_refs": ["owner-review"],
                    "validation_chain_refs": ["validation-chain"],
                    "integration_risk_refs": ["risk-register"],
                    "skipped_item_refs": ["skipped-items"],
                    "mainline_decision_refs": ["mainline-decision"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_mainline_adoption_readiness_rollup_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "mainline_adoption_policy_ref",
        "secondary_candidate_policy_ref",
        "integration_risk_policy_ref",
        "skipped_item_policy_ref",
        "mainline_adoption_readiness_manifest_ref",
        "secondary_integration_governance_ref",
    ]


def test_rejected_or_regressed_adoption_readiness_blocks_candidate() -> None:
    packet = build_codex_mainline_adoption_readiness_rollup_packet(
        {
            **PACKET_POLICIES,
            "adoptions": [
                {
                    "adoption_id": "adoption-3",
                    "status": "rejected",
                    "secondary_candidate_ref": "secondary-candidate",
                    "closure_rollup_refs": ["closure-rollup"],
                    "owner_review_refs": ["owner-review"],
                    "validation_chain_refs": ["validation-chain"],
                    "integration_risk_refs": ["risk-register"],
                    "skipped_item_refs": ["skipped-items"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    adoption = packet["adoptions"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_mainline_adoption_readiness_rollup_status_failed"
    assert "codex_mainline_adoption_readiness_status_failed" in adoption["blockers"]


def test_missing_adoption_refs_needs_review() -> None:
    adoption = summarize_codex_mainline_adoption_readiness_rollup(
        {
            "adoption_id": "adoption-4",
            "status": "approved",
            "secondary_candidate_ref": "secondary-candidate",
        }
    )

    assert adoption.readiness_state == "needs_review"
    assert "closure_rollup_refs" in adoption.missing_refs
    assert "owner_review_refs" in adoption.missing_refs
    assert "validation_chain_refs" in adoption.missing_refs
    assert "integration_risk_refs" in adoption.missing_refs
    assert "skipped_item_refs" in adoption.missing_refs
    assert "mainline_decision_refs" in adoption.missing_refs
    assert "artifact_refs" in adoption.missing_refs


def test_open_adoption_readiness_requires_next_step_refs() -> None:
    adoption = summarize_codex_mainline_adoption_readiness_rollup(
        {
            "adoption_id": "adoption-5",
            "status": "needs-review",
            "secondary_candidate_ref": "secondary-candidate",
            "closure_rollup_refs": ["closure-rollup"],
            "owner_review_refs": ["owner-review"],
            "validation_chain_refs": ["validation-chain"],
            "integration_risk_refs": ["risk-register"],
            "skipped_item_refs": ["skipped-items"],
            "artifact_refs": ["artifact"],
        }
    )

    assert adoption.readiness_state == "needs_review"
    assert "next_step_refs" in adoption.missing_refs
    assert "codex_mainline_adoption_readiness_still_open" in adoption.warnings


def test_integration_risk_warning_drives_next_step_decision() -> None:
    packet = build_codex_mainline_adoption_readiness_rollup_packet(
        {
            **PACKET_POLICIES,
            "adoptions": [
                {
                    "adoption_id": "adoption-6",
                    "status": "approved",
                    "secondary_candidate_ref": "secondary-candidate",
                    "closure_rollup_refs": ["closure-rollup"],
                    "owner_review_refs": ["owner-review"],
                    "validation_chain_refs": ["validation-chain"],
                    "integration_risk_refs": ["risk-register"],
                    "skipped_item_refs": ["skipped-items"],
                    "mainline_decision_refs": ["mainline-decision"],
                    "artifact_refs": ["artifact"],
                    "next_step_refs": ["next-step"],
                    "integration_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_mainline_adoption_readiness_rollup_risk"
    assert packet["next_actions"] == [
        "review_mainline_adoption_integration_risks",
        "decide_secondary_candidate_next_steps",
    ]


def test_live_mainline_manifest_stage_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_mainline_adoption_readiness_rollup_packet(
        {
            **PACKET_POLICIES,
            "adoptions": [
                {
                    "adoption_id": "adoption-7",
                    "status": "accepted",
                    "secondary_candidate_ref": "secondary-candidate",
                    "closure_rollup_refs": ["closure-rollup"],
                    "owner_review_refs": ["owner-review"],
                    "validation_chain_refs": ["validation-chain"],
                    "integration_risk_refs": ["risk-register"],
                    "skipped_item_refs": ["skipped-items"],
                    "mainline_decision_refs": ["mainline-decision"],
                    "artifact_refs": ["artifact"],
                    "mainline_decision_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_mainline_adoption_readiness_rollup_live_operation_blocked"
    assert "live_codex_mainline_adoption_readiness_operation_attempted" in packet["adoptions"][0]["blockers"]


def test_empty_payload_requests_mainline_adoption_inventory() -> None:
    packet = build_codex_mainline_adoption_readiness_rollup_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_mainline_adoption_readiness_inventory"]


def test_dataclass_like_mainline_adoption_rollup_is_accepted_by_summarizer() -> None:
    @dataclass
    class Adoption:
        adoption_id: str
        status: str
        secondary_candidate_ref: str
        closure_rollup_refs: list[str]
        owner_review_refs: list[str]
        validation_chain_refs: list[str]
        integration_risk_refs: list[str]
        skipped_item_refs: list[str]
        mainline_decision_refs: list[str]
        artifact_refs: list[str]
        next_step_refs: list[str]

    adoption = summarize_codex_mainline_adoption_readiness_rollup(
        Adoption(
            "adoption-8",
            "validated",
            "secondary-candidate",
            ["closure-rollup"],
            ["owner-review"],
            ["validation-chain"],
            ["risk-register"],
            ["skipped-items"],
            ["mainline-decision"],
            ["artifact"],
            ["next-step"],
        )
    )

    assert adoption.adoption_id == "adoption-8"
    assert adoption.status == "validated"
    assert adoption.readiness_state == "ready"
