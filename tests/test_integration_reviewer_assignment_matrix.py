from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_reviewer_assignment_matrix import (
    build_integration_reviewer_assignment_matrix,
    summarize_reviewer_assignment,
)


def test_reviewer_assignment_matrix_marks_complete_assignments_ready() -> None:
    matrix = build_integration_reviewer_assignment_matrix(
        {
            "matrix_id": "reviewers-1",
            "review_packet_manifest": {
                "entries": [
                    {
                        "candidate_id": "integration_manifest_review_digest",
                        "stage_label": "secondary_integration_candidate",
                        "review_status": "ready",
                        "owner": "mainline",
                        "evidence_refs": ["tests passed"],
                    }
                ]
            },
            "reviewer_hints": {"integration_manifest_review_digest": "architecture"},
        }
    )

    assert matrix["kind"] == "integration_reviewer_assignment_matrix"
    assert matrix["ok"] is True
    assert matrix["status"] == "ready"
    assert matrix["summary"]["assignment_count"] == 1
    assert matrix["assignments"][0]["primary_reviewer"] == "architecture"
    assert matrix["by_reviewer"] == {"architecture": ["integration_manifest_review_digest"]}
    assert matrix["next_actions"] == ["share_reviewer_assignment_matrix_with_mainline"]


def test_missing_owner_and_reviewer_needs_review() -> None:
    matrix = build_integration_reviewer_assignment_matrix(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "review_status": "ready",
                }
            ]
        }
    )

    assert matrix["status"] == "needs_review"
    assignment = matrix["assignments"][0]
    assert assignment["review_status"] == "needs_review"
    assert assignment["reasons"] == [
        "owner missing",
        "primary reviewer missing",
        "review evidence missing",
    ]
    assert matrix["next_actions"] == [
        "complete_reviewer_assignment_matrix",
        "assign_candidate_owner",
        "assign_primary_reviewer",
        "attach_reviewer_assignment_evidence",
        "rebuild_integration_reviewer_assignment_matrix",
    ]


def test_blocked_digest_signal_blocks_candidate_assignment() -> None:
    matrix = build_integration_reviewer_assignment_matrix(
        {
            "review_packet_manifest": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "owner": "mainline",
                        "primary_reviewer": "review",
                        "review_status": "ready",
                        "evidence_refs": ["handoff"],
                    }
                ]
            },
            "manifest_review_digest": {
                "signals": [
                    {
                        "signal_id": "stage_policy",
                        "status": "blocked",
                        "severity": "high",
                        "refs": ["candidate-a"],
                    }
                ]
            },
        }
    )

    assert matrix["status"] == "blocked"
    assert matrix["blocked_candidates"] == ["candidate-a"]
    assignment = matrix["assignments"][0]
    assert assignment["risk_level"] == "high"
    assert assignment["secondary_reviewers"] == ["mainline"]
    assert "review digest blocks candidate" in assignment["reasons"]
    assert matrix["next_actions"] == [
        "resolve_blocked_reviewer_assignments",
        "rebuild_integration_reviewer_assignment_matrix",
    ]


def test_owner_digest_and_secondary_reviewer_hints_are_used() -> None:
    matrix = build_integration_reviewer_assignment_matrix(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "review_status": "ready",
                    "risk_level": "high",
                    "primary_reviewer": "architecture",
                    "evidence_refs": ["tests passed"],
                }
            ],
            "owner_digest": {
                "owners": [
                    {
                        "owner": "mainline",
                        "candidate_ids": ["candidate-a"],
                    }
                ]
            },
        }
    )

    assert matrix["status"] == "ready"
    assignment = matrix["assignments"][0]
    assert assignment["owner"] == "mainline"
    assert assignment["primary_reviewer"] == "architecture"
    assert assignment["secondary_reviewers"] == ["mainline"]
    assert matrix["by_reviewer"] == {
        "architecture": ["candidate-a"],
        "mainline": ["candidate-a"],
    }


def test_empty_reviewer_assignment_matrix_requests_candidates() -> None:
    matrix = build_integration_reviewer_assignment_matrix({})

    assert matrix["ok"] is False
    assert matrix["status"] == "empty"
    assert matrix["next_actions"] == ["provide_reviewer_assignment_candidates"]


def test_summarize_reviewer_assignment_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Candidate:
        candidate_id: str
        owner: str
        primary_reviewer: str
        review_status: str
        evidence_refs: list[str]

    assignment = summarize_reviewer_assignment(
        Candidate("candidate-a", "mainline", "review", "ready", ["handoff"])
    )

    assert assignment.candidate_id == "candidate-a"
    assert assignment.owner == "mainline"
    assert assignment.primary_reviewer == "review"
    assert assignment.review_status == "ready"
