from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_eval_repair_readiness_packet import (
    build_codex_eval_repair_readiness_packet,
    summarize_codex_eval_repair,
)


PACKET_POLICIES = {
    "eval_policy": "eval-policy",
    "repair_policy": "repair-policy",
    "validation_policy": "validation-policy",
    "rollback_policy": "rollback-policy",
    "eval_manifest_ref": "eval-manifest",
}


def test_ready_repaired_loop_with_validation_regression_and_closure_receipts() -> None:
    packet = build_codex_eval_repair_readiness_packet(
        {
            **PACKET_POLICIES,
            "repairs": [
                {
                    "repair_id": "repair-1",
                    "state": "validated",
                    "confidence": 0.91,
                    "failure_classification_refs": ["failure-classification"],
                    "repro_command_refs": ["pytest tests/test_x.py"],
                    "repair_plan_refs": ["repair-plan"],
                    "patch_attempt_refs": ["patch-attempt"],
                    "validation_rerun_refs": ["validation-rerun"],
                    "regression_evidence_refs": ["regression-evidence"],
                    "rollback_refs": ["rollback-plan"],
                    "confidence_scoring_refs": ["confidence-score"],
                    "closure_receipts": ["closure"],
                    "artifact_refs": ["repair-artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_eval_repair_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["repair_count"] == 1
    assert packet["summary"]["high_confidence_count"] == 1
    assert packet["next_actions"] == ["share_eval_repair_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_eval_repair_readiness_packet(
        {
            "repairs": [
                {
                    "repair_id": "repair-1",
                    "state": "validated",
                    "confidence": 0.9,
                    "failure_classification_refs": ["failure"],
                    "repro_command_refs": ["repro"],
                    "repair_plan_refs": ["plan"],
                    "patch_attempt_refs": ["patch"],
                    "validation_rerun_refs": ["validation"],
                    "regression_evidence_refs": ["regression"],
                    "confidence_scoring_refs": ["confidence"],
                    "closure_receipts": ["closure"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_eval_repair_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "eval_policy_ref",
        "repair_policy_ref",
        "validation_policy_ref",
        "rollback_policy_ref",
        "eval_manifest_ref",
    ]


def test_open_repair_loop_needs_review_until_validation_rerun_and_patch_refs() -> None:
    repair = summarize_codex_eval_repair(
        {
            "repair_id": "repair-2",
            "state": "needs-repair",
            "confidence": 0.66,
            "failure_classification_refs": ["failure"],
            "repro_command_refs": ["repro"],
            "repair_plan_refs": ["plan"],
            "artifact_refs": ["artifact"],
        }
    )

    assert repair.readiness_state == "needs_review"
    assert "eval_repair_loop_open" in repair.warnings
    assert "confidence_below_threshold" in repair.warnings
    assert "patch_attempt_refs" in repair.missing_refs
    assert "validation_rerun_refs" in repair.missing_refs


def test_regression_detected_blocks_and_requires_rollback_refs() -> None:
    packet = build_codex_eval_repair_readiness_packet(
        {
            **PACKET_POLICIES,
            "repairs": [
                {
                    "repair_id": "repair-3",
                    "state": "regression-detected",
                    "confidence": 0.8,
                    "failure_classification_refs": ["failure"],
                    "repro_command_refs": ["repro"],
                    "repair_plan_refs": ["plan"],
                    "patch_attempt_refs": ["patch"],
                    "validation_rerun_refs": ["validation"],
                    "regression_evidence_refs": ["regression"],
                    "confidence_scoring_refs": ["confidence"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    repair = packet["repairs"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_eval_repair_state_blocked"
    assert "rollback_refs" in repair["missing_refs"]
    assert packet["next_actions"] == ["resolve_eval_repair_blockers", "refresh_eval_repair_readiness"]


def test_validated_repair_without_closure_receipts_needs_review() -> None:
    packet = build_codex_eval_repair_readiness_packet(
        {
            **PACKET_POLICIES,
            "repairs": [
                {
                    "repair_id": "repair-4",
                    "state": "validated",
                    "confidence": 0.9,
                    "failure_classification_refs": ["failure"],
                    "repro_command_refs": ["repro"],
                    "repair_plan_refs": ["plan"],
                    "patch_attempt_refs": ["patch"],
                    "validation_rerun_refs": ["validation"],
                    "regression_evidence_refs": ["regression"],
                    "confidence_scoring_refs": ["confidence"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert "closure_receipts" in packet["repairs"][0]["missing_refs"]
    assert packet["findings"][0]["code"] == "codex_eval_repair_missing_evidence"


def test_empty_payload_requests_eval_repair_inventory() -> None:
    packet = build_codex_eval_repair_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_eval_repair_inventory"]


def test_dataclass_like_repair_is_accepted_by_summarizer() -> None:
    @dataclass
    class Repair:
        repair_id: str
        state: str
        confidence: float
        failure_classification_refs: list[str]
        repro_command_refs: list[str]
        repair_plan_refs: list[str]
        patch_attempt_refs: list[str]
        validation_rerun_refs: list[str]
        regression_evidence_refs: list[str]
        confidence_scoring_refs: list[str]
        closure_receipts: list[str]
        artifact_refs: list[str]

    repair = summarize_codex_eval_repair(
        Repair(
            "repair-5",
            "validated",
            0.9,
            ["failure"],
            ["repro"],
            ["plan"],
            ["patch"],
            ["validation"],
            ["regression"],
            ["confidence"],
            ["closure"],
            ["artifact"],
        )
    )

    assert repair.repair_id == "repair-5"
    assert repair.state == "validated"
    assert repair.readiness_state == "ready"
