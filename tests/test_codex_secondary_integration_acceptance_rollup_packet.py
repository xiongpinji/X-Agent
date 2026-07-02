from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_acceptance_rollup_packet import (
    build_codex_secondary_integration_acceptance_rollup_packet,
    summarize_codex_secondary_integration_acceptance_rollup,
)


PACKET_POLICIES = {
    "acceptance_rollup_policy": "acceptance-rollup-policy",
    "owner_acceptance_policy": "owner-acceptance-policy",
    "residual_risk_policy": "residual-risk-policy",
    "secondary_integration_policy": "secondary-integration-policy",
    "secondary_integration_acceptance_rollup_manifest_ref": "acceptance-rollup-manifest",
    "secondary_integration_acceptance_governance_ref": "acceptance-governance",
}


def test_ready_secondary_integration_acceptance_rollup_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_acceptance_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "rollup-1",
                    "status": "accepted",
                    "acceptance_rollup_ref": "acceptance-rollup",
                    "final_review_refs": ["final-review"],
                    "closure_index_refs": ["closure-index"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["residual-risk"],
                    "accepted_candidate_refs": ["accepted-candidate"],
                    "deferred_candidate_refs": ["deferred-candidate"],
                    "rejected_candidate_refs": ["rejected-candidate"],
                    "owner_next_action_refs": ["owner-next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_acceptance_rollup_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["rollup_count"] == 1
    assert packet["summary"]["accepted_candidate_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_acceptance_rollup_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_acceptance_rollup_packet(
        {
            "rollups": [
                {
                    "rollup_id": "rollup-2",
                    "status": "accepted",
                    "acceptance_rollup_ref": "acceptance-rollup",
                    "final_review_refs": ["final-review"],
                    "closure_index_refs": ["closure-index"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["residual-risk"],
                    "accepted_candidate_refs": ["accepted-candidate"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_acceptance_rollup_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "acceptance_rollup_policy_ref",
        "owner_acceptance_policy_ref",
        "residual_risk_policy_ref",
        "secondary_integration_policy_ref",
        "secondary_integration_acceptance_rollup_manifest_ref",
        "secondary_integration_acceptance_governance_ref",
    ]


def test_rejected_or_regressed_acceptance_rollup_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_acceptance_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "rollup-3",
                    "status": "rejected",
                    "acceptance_rollup_ref": "acceptance-rollup",
                    "final_review_refs": ["final-review"],
                    "closure_index_refs": ["closure-index"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["residual-risk"],
                    "rejected_candidate_refs": ["rejected-candidate"],
                }
            ],
        }
    )

    rollup = packet["rollups"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_acceptance_rollup_status_failed"
    assert "codex_secondary_integration_acceptance_rollup_status_failed" in rollup["blockers"]


def test_missing_acceptance_rollup_refs_needs_review() -> None:
    rollup = summarize_codex_secondary_integration_acceptance_rollup(
        {
            "rollup_id": "rollup-4",
            "status": "accepted",
            "acceptance_rollup_ref": "acceptance-rollup",
        }
    )

    assert rollup.readiness_state == "needs_review"
    assert "final_review_refs" in rollup.missing_refs
    assert "closure_index_refs" in rollup.missing_refs
    assert "owner_acceptance_refs" in rollup.missing_refs
    assert "validation_refs" in rollup.missing_refs
    assert "residual_risk_refs" in rollup.missing_refs
    assert "candidate_disposition_refs" in rollup.missing_refs


def test_open_acceptance_rollup_requires_owner_next_action_refs() -> None:
    rollup = summarize_codex_secondary_integration_acceptance_rollup(
        {
            "rollup_id": "rollup-5",
            "status": "needs-review",
            "acceptance_rollup_ref": "acceptance-rollup",
            "final_review_refs": ["final-review"],
            "closure_index_refs": ["closure-index"],
            "owner_acceptance_refs": ["owner-acceptance"],
            "validation_refs": ["validation"],
            "residual_risk_refs": ["residual-risk"],
            "deferred_candidate_refs": ["deferred-candidate"],
        }
    )

    assert rollup.readiness_state == "needs_review"
    assert "owner_next_action_refs" in rollup.missing_refs
    assert "codex_secondary_integration_acceptance_rollup_still_open" in rollup.warnings


def test_residual_risk_warning_drives_acceptance_action_decision() -> None:
    packet = build_codex_secondary_integration_acceptance_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "rollup-6",
                    "status": "accepted",
                    "acceptance_rollup_ref": "acceptance-rollup",
                    "final_review_refs": ["final-review"],
                    "closure_index_refs": ["closure-index"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["residual-risk"],
                    "accepted_candidate_refs": ["accepted-candidate"],
                    "owner_next_action_refs": ["owner-next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_acceptance_rollup_residual_risk"
    assert packet["next_actions"] == [
        "review_secondary_integration_acceptance_residual_risks",
        "decide_acceptance_rollup_action",
    ]


def test_deferred_candidates_pending_drives_deferred_review() -> None:
    packet = build_codex_secondary_integration_acceptance_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "rollup-7",
                    "status": "validated",
                    "acceptance_rollup_ref": "acceptance-rollup",
                    "final_review_refs": ["final-review"],
                    "closure_index_refs": ["closure-index"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["residual-risk"],
                    "deferred_candidate_refs": ["deferred-candidate"],
                    "owner_next_action_refs": ["owner-next-action"],
                    "deferred_candidates_pending": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_acceptance_rollup_deferred_candidates_pending"
    assert packet["next_actions"] == [
        "review_deferred_secondary_candidates",
        "refresh_acceptance_rollup_packet",
    ]


def test_live_acceptance_manifest_stage_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_acceptance_rollup_packet(
        {
            **PACKET_POLICIES,
            "rollups": [
                {
                    "rollup_id": "rollup-8",
                    "status": "accepted",
                    "acceptance_rollup_ref": "acceptance-rollup",
                    "final_review_refs": ["final-review"],
                    "closure_index_refs": ["closure-index"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["residual-risk"],
                    "accepted_candidate_refs": ["accepted-candidate"],
                    "acceptance_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_acceptance_rollup_live_operation_blocked"
    assert "live_codex_secondary_integration_acceptance_rollup_operation_attempted" in packet["rollups"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_acceptance_rollup_inventory() -> None:
    packet = build_codex_secondary_integration_acceptance_rollup_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_acceptance_rollup_inventory"]


def test_dataclass_like_acceptance_rollup_is_accepted_by_summarizer() -> None:
    @dataclass
    class AcceptanceRollup:
        rollup_id: str
        status: str
        acceptance_rollup_ref: str
        final_review_refs: list[str]
        closure_index_refs: list[str]
        owner_acceptance_refs: list[str]
        validation_refs: list[str]
        residual_risk_refs: list[str]
        deferred_candidate_refs: list[str]
        accepted_candidate_refs: list[str]
        rejected_candidate_refs: list[str]
        owner_next_action_refs: list[str]

    rollup = summarize_codex_secondary_integration_acceptance_rollup(
        AcceptanceRollup(
            "rollup-9",
            "complete",
            "acceptance-rollup",
            ["final-review"],
            ["closure-index"],
            ["owner-acceptance"],
            ["validation"],
            ["residual-risk"],
            ["deferred-candidate"],
            ["accepted-candidate"],
            ["rejected-candidate"],
            ["owner-next-action"],
        )
    )

    assert rollup.rollup_id == "rollup-9"
    assert rollup.status == "complete"
    assert rollup.readiness_state == "ready"
