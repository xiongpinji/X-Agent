from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_ledger_packet import (
    build_codex_secondary_integration_adoption_decision_ledger_packet,
    summarize_codex_secondary_integration_adoption_decision_ledger,
)


PACKET_POLICIES = {
    "adoption_decision_ledger_policy": "adoption-decision-ledger-policy",
    "owner_decision_policy": "owner-decision-policy",
    "candidate_disposition_policy": "candidate-disposition-policy",
    "decision_timestamp_policy": "decision-timestamp-policy",
    "secondary_integration_adoption_decision_ledger_manifest_ref": "adoption-decision-ledger-manifest",
    "secondary_integration_adoption_decision_governance_ref": "adoption-decision-governance",
}


def test_ready_secondary_integration_adoption_decision_ledger_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_ledger_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "decision_id": "decision-1",
                    "status": "recorded",
                    "adoption_decision_ledger_ref": "decision-ledger",
                    "acceptance_rollup_refs": ["acceptance-rollup"],
                    "final_review_refs": ["final-review"],
                    "owner_decision_refs": ["owner-decision"],
                    "accepted_disposition_refs": ["accepted"],
                    "deferred_disposition_refs": ["deferred"],
                    "rejected_disposition_refs": ["rejected"],
                    "residual_risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "decision_timestamp_refs": ["timestamp"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_ledger_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["decision_count"] == 1
    assert packet["summary"]["accepted_disposition_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_ledger_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_ledger_packet(
        {
            "decisions": [
                {
                    "decision_id": "decision-2",
                    "status": "adopted",
                    "adoption_decision_ledger_ref": "decision-ledger",
                    "acceptance_rollup_refs": ["acceptance-rollup"],
                    "final_review_refs": ["final-review"],
                    "owner_decision_refs": ["owner-decision"],
                    "accepted_disposition_refs": ["accepted"],
                    "residual_risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "decision_timestamp_refs": ["timestamp"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_ledger_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "adoption_decision_ledger_policy_ref",
        "owner_decision_policy_ref",
        "candidate_disposition_policy_ref",
        "decision_timestamp_policy_ref",
        "secondary_integration_adoption_decision_ledger_manifest_ref",
        "secondary_integration_adoption_decision_governance_ref",
    ]


def test_failed_or_invalid_adoption_decision_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_ledger_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "decision_id": "decision-3",
                    "status": "invalid",
                    "adoption_decision_ledger_ref": "decision-ledger",
                    "acceptance_rollup_refs": ["acceptance-rollup"],
                    "final_review_refs": ["final-review"],
                    "owner_decision_refs": ["owner-decision"],
                    "rejected_disposition_refs": ["rejected"],
                    "residual_risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "decision_timestamp_refs": ["timestamp"],
                }
            ],
        }
    )

    decision = packet["decisions"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_ledger_status_failed"
    assert "codex_secondary_integration_adoption_decision_ledger_status_failed" in decision["blockers"]


def test_missing_adoption_decision_refs_needs_review() -> None:
    decision = summarize_codex_secondary_integration_adoption_decision_ledger(
        {
            "decision_id": "decision-4",
            "status": "recorded",
            "adoption_decision_ledger_ref": "decision-ledger",
        }
    )

    assert decision.readiness_state == "needs_review"
    assert "acceptance_rollup_refs" in decision.missing_refs
    assert "final_review_refs" in decision.missing_refs
    assert "owner_decision_refs" in decision.missing_refs
    assert "candidate_disposition_refs" in decision.missing_refs
    assert "residual_risk_refs" in decision.missing_refs
    assert "validation_refs" in decision.missing_refs
    assert "handoff_refs" in decision.missing_refs
    assert "decision_timestamp_refs" in decision.missing_refs


def test_open_adoption_decision_warns_until_receipts_attach() -> None:
    decision = summarize_codex_secondary_integration_adoption_decision_ledger(
        {
            "decision_id": "decision-5",
            "status": "needs-review",
            "adoption_decision_ledger_ref": "decision-ledger",
            "acceptance_rollup_refs": ["acceptance-rollup"],
            "final_review_refs": ["final-review"],
            "owner_decision_refs": ["owner-decision"],
            "deferred_disposition_refs": ["deferred"],
            "residual_risk_refs": ["risk"],
            "validation_refs": ["validation"],
            "handoff_refs": ["handoff"],
            "decision_timestamp_refs": ["timestamp"],
        }
    )

    assert decision.readiness_state == "needs_review"
    assert decision.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_ledger_still_open" in decision.warnings


def test_residual_risk_warning_drives_decision_input_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_ledger_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "decision_id": "decision-6",
                    "status": "recorded",
                    "adoption_decision_ledger_ref": "decision-ledger",
                    "acceptance_rollup_refs": ["acceptance-rollup"],
                    "final_review_refs": ["final-review"],
                    "owner_decision_refs": ["owner-decision"],
                    "accepted_disposition_refs": ["accepted"],
                    "residual_risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "decision_timestamp_refs": ["timestamp"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_ledger_residual_risk"
    assert packet["next_actions"] == [
        "review_secondary_integration_adoption_decision_risks",
        "update_adoption_decision_inputs",
    ]


def test_missing_timestamp_warning_drives_timestamp_attachment() -> None:
    packet = build_codex_secondary_integration_adoption_decision_ledger_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "decision_id": "decision-7",
                    "status": "recorded",
                    "adoption_decision_ledger_ref": "decision-ledger",
                    "acceptance_rollup_refs": ["acceptance-rollup"],
                    "final_review_refs": ["final-review"],
                    "owner_decision_refs": ["owner-decision"],
                    "deferred_disposition_refs": ["deferred"],
                    "residual_risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "decision_timestamp_refs": ["timestamp"],
                    "decision_timestamp_missing": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_ledger_timestamp_missing"
    assert packet["next_actions"] == [
        "attach_adoption_decision_timestamps",
        "refresh_adoption_decision_ledger_packet",
    ]


def test_live_ledger_disposition_manifest_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_ledger_packet(
        {
            **PACKET_POLICIES,
            "decisions": [
                {
                    "decision_id": "decision-8",
                    "status": "recorded",
                    "adoption_decision_ledger_ref": "decision-ledger",
                    "acceptance_rollup_refs": ["acceptance-rollup"],
                    "final_review_refs": ["final-review"],
                    "owner_decision_refs": ["owner-decision"],
                    "accepted_disposition_refs": ["accepted"],
                    "residual_risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "decision_timestamp_refs": ["timestamp"],
                    "ledger_persistence_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_ledger_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_ledger_operation_attempted" in packet["decisions"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_adoption_decision_ledger_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_ledger_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_ledger_inventory"]


def test_dataclass_like_adoption_decision_ledger_is_accepted_by_summarizer() -> None:
    @dataclass
    class AdoptionDecision:
        decision_id: str
        status: str
        adoption_decision_ledger_ref: str
        acceptance_rollup_refs: list[str]
        final_review_refs: list[str]
        owner_decision_refs: list[str]
        accepted_disposition_refs: list[str]
        deferred_disposition_refs: list[str]
        rejected_disposition_refs: list[str]
        residual_risk_refs: list[str]
        validation_refs: list[str]
        handoff_refs: list[str]
        decision_timestamp_refs: list[str]

    decision = summarize_codex_secondary_integration_adoption_decision_ledger(
        AdoptionDecision(
            "decision-9",
            "closed",
            "decision-ledger",
            ["acceptance-rollup"],
            ["final-review"],
            ["owner-decision"],
            ["accepted"],
            ["deferred"],
            ["rejected"],
            ["risk"],
            ["validation"],
            ["handoff"],
            ["timestamp"],
        )
    )

    assert decision.decision_id == "decision-9"
    assert decision.status == "closed"
    assert decision.readiness_state == "ready"
