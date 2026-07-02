from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_retention_policy import (
    build_integration_review_retention_policy,
    review_retention_candidate,
)


def test_review_retention_policy_retains_complete_archive_entry() -> None:
    policy = build_integration_review_retention_policy(
        {
            "policy_id": "retention-1",
            "review_archive_manifest": {
                "entries": [
                    {
                        "candidate_id": "integration_review_archive_manifest",
                        "status": "ready",
                        "owner": "mainline",
                        "risk_level": "low",
                        "archive_key": "review/integration-review-archive-manifest",
                        "artifact_refs": ["backend/app/core/integration_review_archive_manifest.py"],
                        "evidence_refs": ["6 passed"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
        }
    )

    assert policy["kind"] == "integration_review_retention_policy"
    assert policy["ok"] is True
    assert policy["status"] == "ready"
    assert policy["summary"]["retain_count"] == 1
    assert policy["retain_candidates"] == ["integration_review_archive_manifest"]
    assert policy["decisions"][0]["retention_days"] == 365
    assert policy["next_actions"] == ["share_review_retention_policy_with_mainline"]


def test_missing_refs_needs_evidence() -> None:
    policy = build_integration_review_retention_policy(
        {
            "review_archive_manifest": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "ready",
                        "owner": "mainline",
                    }
                ]
            }
        }
    )

    assert policy["status"] == "needs_review"
    assert policy["needs_evidence_candidates"] == ["candidate-a"]
    decision = policy["decisions"][0]
    assert decision["recommendation"] == "needs_evidence"
    assert decision["reasons"] == [
        "archive refs missing",
        "retention evidence missing",
        "retention handoff refs missing",
    ]
    assert policy["next_actions"] == [
        "complete_review_retention_policy",
        "attach_retention_archive_refs",
        "attach_retention_evidence",
        "attach_retention_handoff_refs",
        "rebuild_integration_review_retention_policy",
    ]


def test_blocked_archive_entry_holds_retention() -> None:
    policy = build_integration_review_retention_policy(
        {
            "review_archive_manifest": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "blocked",
                        "owner": "mainline",
                        "archive_key": "review/candidate-a",
                        "artifact_refs": ["module.py"],
                        "evidence_refs": ["blocked"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert policy["status"] == "blocked"
    assert policy["hold_blocked_candidates"] == ["candidate-a"]
    decision = policy["decisions"][0]
    assert decision["recommendation"] == "hold_blocked"
    assert decision["risk_level"] == "high"
    assert decision["retention_days"] == 1095
    assert policy["next_actions"] == [
        "resolve_retention_blockers",
        "rebuild_integration_review_retention_policy",
    ]


def test_explicit_candidate_can_override_retention_days() -> None:
    policy = build_integration_review_retention_policy(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "retention_days": 90,
                }
            ],
            "review_archive_manifest": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "ready",
                        "owner": "mainline",
                        "archive_key": "review/candidate-a",
                        "artifact_refs": ["module.py"],
                        "evidence_refs": ["tests"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
        }
    )

    assert policy["status"] == "ready"
    assert policy["decisions"][0]["retention_days"] == 90
    assert policy["decisions"][0]["recommendation"] == "retain"


def test_empty_retention_policy_requests_inputs() -> None:
    policy = build_integration_review_retention_policy({})

    assert policy["ok"] is False
    assert policy["status"] == "empty"
    assert policy["next_actions"] == ["provide_review_retention_policy_inputs"]


def test_review_retention_candidate_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Candidate:
        candidate_id: str
        owner: str
        archive_refs: list[str]
        evidence_refs: list[str]
        handoff_refs: list[str]
        status: str

    decision = review_retention_candidate(
        Candidate("candidate-a", "mainline", ["archive"], ["tests"], ["handoff"], "ready")
    )

    assert decision.candidate_id == "candidate-a"
    assert decision.recommendation == "defer"
    assert "archive manifest entry missing" in decision.reasons
