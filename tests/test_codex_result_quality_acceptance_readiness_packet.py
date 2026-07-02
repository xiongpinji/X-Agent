from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_result_quality_acceptance_readiness_packet import (
    build_codex_result_quality_acceptance_readiness_packet,
    summarize_codex_result_quality_acceptance,
)


PACKET_POLICIES = {
    "result_quality_policy": "result-quality-policy",
    "acceptance_policy": "acceptance-policy",
    "evidence_policy": "evidence-policy",
    "regression_policy": "regression-policy",
    "result_quality_manifest_ref": "result-quality-manifest",
    "acceptance_governance_ref": "acceptance-governance",
}


def test_ready_result_quality_has_acceptance_evidence() -> None:
    packet = build_codex_result_quality_acceptance_readiness_packet(
        {
            **PACKET_POLICIES,
            "results": [
                {
                    "result_id": "result-1",
                    "status": "passed",
                    "expected_result_ref": "expected",
                    "acceptance_criteria_refs": ["criteria"],
                    "result_quality_refs": ["quality"],
                    "mismatch_refs": ["mismatch"],
                    "regression_refs": ["regression"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "evidence_refs": ["evidence"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_result_quality_acceptance_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["result_count"] == 1
    assert packet["summary"]["acceptance_criteria_ref_count"] == 1
    assert packet["next_actions"] == ["share_result_quality_acceptance_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_result_quality_acceptance_readiness_packet(
        {
            "results": [
                {
                    "result_id": "result-2",
                    "status": "passed",
                    "expected_result_ref": "expected",
                    "acceptance_criteria_refs": ["criteria"],
                    "result_quality_refs": ["quality"],
                    "regression_refs": ["regression"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "evidence_refs": ["evidence"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_result_quality_acceptance_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "result_quality_policy_ref",
        "acceptance_policy_ref",
        "evidence_policy_ref",
        "regression_policy_ref",
        "result_quality_manifest_ref",
        "acceptance_governance_ref",
    ]


def test_failed_result_requires_mismatch_and_regression_refs_and_blocks() -> None:
    packet = build_codex_result_quality_acceptance_readiness_packet(
        {
            **PACKET_POLICIES,
            "results": [
                {
                    "result_id": "result-3",
                    "status": "failed",
                    "expected_result_ref": "expected",
                    "acceptance_criteria_refs": ["criteria"],
                    "result_quality_refs": ["quality"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "evidence_refs": ["evidence"],
                }
            ],
        }
    )

    result = packet["results"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_result_quality_acceptance_status_failed"
    assert "mismatch_refs" in result["missing_refs"]
    assert "regression_refs" in result["missing_refs"]


def test_missing_expected_result_acceptance_criteria_quality_evidence_and_validation_needs_review() -> None:
    result = summarize_codex_result_quality_acceptance(
        {
            "result_id": "result-4",
            "status": "validated",
            "artifact_refs": ["artifact"],
        }
    )

    assert result.readiness_state == "needs_review"
    assert "expected_result_ref" in result.missing_refs
    assert "acceptance_criteria_refs" in result.missing_refs
    assert "result_quality_refs" in result.missing_refs
    assert "evidence_refs" in result.missing_refs
    assert "validation_receipt_refs" in result.missing_refs


def test_live_result_mutation_or_acceptance_execution_attempt_blocks_candidate() -> None:
    packet = build_codex_result_quality_acceptance_readiness_packet(
        {
            **PACKET_POLICIES,
            "results": [
                {
                    "result_id": "result-5",
                    "status": "passed",
                    "expected_result_ref": "expected",
                    "acceptance_criteria_refs": ["criteria"],
                    "result_quality_refs": ["quality"],
                    "mismatch_refs": ["mismatch"],
                    "regression_refs": ["regression"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "evidence_refs": ["evidence"],
                    "acceptance_execution_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_result_quality_acceptance_live_operation_blocked"
    assert "live_result_quality_operation_attempted" in packet["results"][0]["blockers"]


def test_empty_payload_requests_result_quality_inventory() -> None:
    packet = build_codex_result_quality_acceptance_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_result_quality_acceptance_inventory"]


def test_regression_detection_blocks_candidate() -> None:
    result = summarize_codex_result_quality_acceptance(
        {
            "result_id": "result-6",
            "status": "passed",
            "expected_result_ref": "expected",
            "acceptance_criteria_refs": ["criteria"],
            "result_quality_refs": ["quality"],
            "mismatch_refs": ["mismatch"],
            "regression_refs": ["regression"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "evidence_refs": ["evidence"],
            "regression_detected": True,
        }
    )

    assert result.readiness_state == "blocked"
    assert "result_quality_regression_detected" in result.blockers


def test_dataclass_like_result_is_accepted_by_summarizer() -> None:
    @dataclass
    class Result:
        result_id: str
        status: str
        expected_result_ref: str
        acceptance_criteria_refs: list[str]
        result_quality_refs: list[str]
        mismatch_refs: list[str]
        regression_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]
        evidence_refs: list[str]

    result = summarize_codex_result_quality_acceptance(
        Result(
            "result-7",
            "accepted",
            "expected",
            ["criteria"],
            ["quality"],
            ["mismatch"],
            ["regression"],
            ["validation"],
            ["artifact"],
            ["evidence"],
        )
    )

    assert result.result_id == "result-7"
    assert result.status == "accepted"
    assert result.readiness_state == "ready"
