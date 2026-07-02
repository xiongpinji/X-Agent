from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_open_source_candidate_evaluation_readiness_packet import (
    build_codex_open_source_candidate_evaluation_readiness_packet,
    summarize_codex_open_source_candidate_evaluation,
)


PACKET_POLICIES = {
    "open_source_policy": "open-source-policy",
    "license_policy": "license-policy",
    "security_policy": "security-policy",
    "adoption_policy": "adoption-policy",
    "open_source_evaluation_manifest_ref": "open-source-evaluation-manifest",
    "capability_gap_governance_ref": "capability-gap-governance",
}


def test_ready_open_source_candidate_evaluation_has_gap_and_adoption_evidence() -> None:
    packet = build_codex_open_source_candidate_evaluation_readiness_packet(
        {
            **PACKET_POLICIES,
            "candidates": [
                {
                    "candidate_id": "candidate-1",
                    "status": "approved",
                    "repository_ref": "repo",
                    "license_refs": ["license"],
                    "maintenance_refs": ["maintenance"],
                    "security_refs": ["security"],
                    "capability_gap_refs": ["gap"],
                    "competitor_comparison_refs": ["comparison"],
                    "adoption_decision_refs": ["decision"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_open_source_candidate_evaluation_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["candidate_count"] == 1
    assert packet["summary"]["capability_gap_ref_count"] == 1
    assert packet["next_actions"] == ["share_open_source_candidate_evaluation_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_open_source_candidate_evaluation_readiness_packet(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-2",
                    "status": "evaluated",
                    "repository_ref": "repo",
                    "license_refs": ["license"],
                    "maintenance_refs": ["maintenance"],
                    "security_refs": ["security"],
                    "capability_gap_refs": ["gap"],
                    "competitor_comparison_refs": ["comparison"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_open_source_candidate_evaluation_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "open_source_policy_ref",
        "license_policy_ref",
        "security_policy_ref",
        "adoption_policy_ref",
        "open_source_evaluation_manifest_ref",
        "capability_gap_governance_ref",
    ]


def test_incompatible_license_or_security_risk_blocks_candidate() -> None:
    packet = build_codex_open_source_candidate_evaluation_readiness_packet(
        {
            **PACKET_POLICIES,
            "candidates": [
                {
                    "candidate_id": "candidate-3",
                    "status": "evaluated",
                    "repository_ref": "repo",
                    "license_refs": ["license"],
                    "maintenance_refs": ["maintenance"],
                    "security_refs": ["security"],
                    "capability_gap_refs": ["gap"],
                    "competitor_comparison_refs": ["comparison"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "license_incompatible": True,
                    "security_risk_detected": True,
                }
            ],
        }
    )

    candidate = packet["candidates"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_open_source_candidate_evaluation_license_blocked"
    assert "open_source_candidate_license_incompatible" in candidate["blockers"]
    assert "open_source_candidate_security_risk_detected" in candidate["blockers"]


def test_missing_repository_license_maintenance_security_gap_comparison_validation_artifact_owner_refs_needs_review() -> None:
    candidate = summarize_codex_open_source_candidate_evaluation(
        {
            "candidate_id": "candidate-4",
            "status": "evaluated",
        }
    )

    assert candidate.readiness_state == "needs_review"
    assert "repository_ref" in candidate.missing_refs
    assert "license_refs" in candidate.missing_refs
    assert "maintenance_refs" in candidate.missing_refs
    assert "security_refs" in candidate.missing_refs
    assert "capability_gap_refs" in candidate.missing_refs
    assert "competitor_comparison_refs" in candidate.missing_refs
    assert "validation_receipt_refs" in candidate.missing_refs
    assert "artifact_refs" in candidate.missing_refs
    assert "owner_refs" in candidate.missing_refs


def test_approved_or_validated_candidate_requires_adoption_decision_refs() -> None:
    candidate = summarize_codex_open_source_candidate_evaluation(
        {
            "candidate_id": "candidate-5",
            "status": "validated",
            "repository_ref": "repo",
            "license_refs": ["license"],
            "maintenance_refs": ["maintenance"],
            "security_refs": ["security"],
            "capability_gap_refs": ["gap"],
            "competitor_comparison_refs": ["comparison"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "owner_refs": ["owner"],
        }
    )

    assert candidate.readiness_state == "needs_review"
    assert "adoption_decision_refs" in candidate.missing_refs


def test_unmaintained_candidate_warns_for_guardrail_review() -> None:
    packet = build_codex_open_source_candidate_evaluation_readiness_packet(
        {
            **PACKET_POLICIES,
            "candidates": [
                {
                    "candidate_id": "candidate-6",
                    "status": "evaluated",
                    "repository_ref": "repo",
                    "license_refs": ["license"],
                    "maintenance_refs": ["maintenance"],
                    "security_refs": ["security"],
                    "capability_gap_refs": ["gap"],
                    "competitor_comparison_refs": ["comparison"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "unmaintained_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_open_source_candidate_evaluation_maintenance_risk"
    assert packet["next_actions"] == [
        "review_open_source_candidate_maintenance_risk",
        "decide_adoption_guardrail",
    ]


def test_live_repository_clone_network_search_or_package_install_blocks_candidate() -> None:
    packet = build_codex_open_source_candidate_evaluation_readiness_packet(
        {
            **PACKET_POLICIES,
            "candidates": [
                {
                    "candidate_id": "candidate-7",
                    "status": "evaluated",
                    "repository_ref": "repo",
                    "license_refs": ["license"],
                    "maintenance_refs": ["maintenance"],
                    "security_refs": ["security"],
                    "capability_gap_refs": ["gap"],
                    "competitor_comparison_refs": ["comparison"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "repository_clone_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_open_source_candidate_evaluation_live_operation_blocked"
    assert "live_open_source_candidate_operation_attempted" in packet["candidates"][0]["blockers"]


def test_empty_payload_requests_open_source_candidate_evaluation_inventory() -> None:
    packet = build_codex_open_source_candidate_evaluation_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_open_source_candidate_evaluation_inventory"]


def test_dataclass_like_open_source_candidate_evaluation_is_accepted_by_summarizer() -> None:
    @dataclass
    class OpenSourceCandidateEvaluation:
        candidate_id: str
        status: str
        repository_ref: str
        license_refs: list[str]
        maintenance_refs: list[str]
        security_refs: list[str]
        capability_gap_refs: list[str]
        competitor_comparison_refs: list[str]
        adoption_decision_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]

    candidate = summarize_codex_open_source_candidate_evaluation(
        OpenSourceCandidateEvaluation(
            "candidate-8",
            "approved",
            "repo",
            ["license"],
            ["maintenance"],
            ["security"],
            ["gap"],
            ["comparison"],
            ["decision"],
            ["validation"],
            ["artifact"],
            ["owner"],
        )
    )

    assert candidate.candidate_id == "candidate-8"
    assert candidate.status == "approved"
    assert candidate.readiness_state == "ready"
