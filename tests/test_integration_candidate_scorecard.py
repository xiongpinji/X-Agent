from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_candidate_scorecard import (
    build_integration_candidate_scorecard,
    score_integration_candidate,
)


def test_scorecard_ranks_high_payoff_low_risk_candidate_integrate_now() -> None:
    scorecard = build_integration_candidate_scorecard(
        {
            "portfolio": "secondary",
            "candidates": [
                {
                    "id": "release-evidence-pack",
                    "name": "Release evidence pack",
                    "owner": "release",
                    "payoff_tags": ["codex_parity", "release_gate", "developer_experience"],
                    "evidence": ["unit", "combined", "py_compile", "handoff"],
                    "integration_effort": "low",
                }
            ],
        }
    )

    assert scorecard["kind"] == "integration_candidate_scorecard"
    assert scorecard["status"] == "ready"
    assert scorecard["summary"]["integrate_now_count"] == 1
    assert scorecard["candidates"][0]["recommendation"] == "integrate_now"
    assert scorecard["next_actions"] == ["review_top_integration_candidate", "prepare_mainline_integration_plan"]


def test_blocking_risk_candidate_blocks_scorecard() -> None:
    scorecard = build_integration_candidate_scorecard(
        {
            "candidates": [
                {
                    "id": "unsafe-tool-wiring",
                    "owner": "tools",
                    "payoff_score": 0.9,
                    "evidence_score": 0.9,
                    "effort_score": 0.8,
                    "risk_flags": ["runtime_mutation"],
                }
            ]
        }
    )

    assert scorecard["status"] == "blocked"
    assert scorecard["candidates"][0]["recommendation"] == "block"
    assert scorecard["issues"][0]["code"] == "integration_candidate_blocked"
    assert scorecard["next_actions"] == ["remove_or_remediate_blocked_candidates", "rebuild_integration_scorecard"]


def test_low_evidence_missing_owner_candidate_is_deferred() -> None:
    item = score_integration_candidate(
        {
            "id": "preview-channel",
            "payoff_tags": ["ecosystem"],
            "integration_effort": "high",
            "issues": [{"code": "missing"}],
        }
    )

    assert item.recommendation == "defer"
    assert item.owner_score == 0.2
    assert "owner missing" in item.reasons


def test_review_next_candidate_with_medium_effort_and_some_risk() -> None:
    item = score_integration_candidate(
        {
            "id": "mcp-readiness",
            "owner": "tools",
            "payoff_tags": ["safety", "ecosystem"],
            "evidence": ["unit", "combined"],
            "integration_effort": "medium",
            "risk_flags": ["policy_review"],
        }
    )

    assert item.recommendation == "review_next"
    assert 0.45 <= item.priority_score < 0.68
    assert item.risk_score > 0


def test_scorecard_sorts_by_priority_descending() -> None:
    scorecard = build_integration_candidate_scorecard(
        {
            "candidates": [
                {"id": "b", "owner": "team", "payoff_score": 0.4, "evidence_score": 0.4, "effort_score": 0.5},
                {"id": "a", "owner": "team", "payoff_score": 0.9, "evidence_score": 0.9, "effort_score": 1.0},
            ]
        }
    )

    assert [item["candidate_id"] for item in scorecard["candidates"]] == ["a", "b"]


def test_accepts_scorecard_and_dataclass_like_candidate() -> None:
    @dataclass
    class Candidate:
        candidate_id: str
        name: str
        owner: str
        payoff_score: int
        evidence_score: int
        effort: str

    scorecard = build_integration_candidate_scorecard(
        {
            "scorecard": {
                "candidates": [
                    Candidate("runtime-manifest", "Runtime manifest", "runtime", 82, 78, "low")
                ]
            }
        }
    )

    assert scorecard["candidates"][0]["candidate_id"] == "runtime-manifest"
    assert scorecard["candidates"][0]["payoff_score"] == 0.82
    assert scorecard["candidates"][0]["evidence_score"] == 0.78


def test_empty_scorecard_requests_candidates() -> None:
    scorecard = build_integration_candidate_scorecard({})

    assert scorecard["status"] == "empty"
    assert scorecard["ok"] is False
    assert scorecard["next_actions"] == ["provide_integration_candidates"]
