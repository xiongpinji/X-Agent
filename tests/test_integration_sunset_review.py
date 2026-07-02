from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_sunset_review import (
    build_integration_sunset_review,
    review_sunset_candidate,
)


def test_sunset_review_keeps_stable_adopted_candidate() -> None:
    review = build_integration_sunset_review(
        {
            "review_id": "sunset-1",
            "post_adoption_monitor": {"kind": "integration_post_adoption_monitor", "status": "ready", "ok": True},
            "owner_digest": {
                "owners": [
                    {
                        "owner": "mainline",
                        "candidate_ids": ["integration_adoption_readme"],
                    }
                ]
            },
            "validation": {"results": ["299 passed"]},
            "candidates": [
                {
                    "candidate_id": "integration_adoption_readme",
                    "adoption_state": "ready",
                    "evidence_refs": ["handoff", "tests"],
                }
            ],
        }
    )

    assert review["kind"] == "integration_sunset_review"
    assert review["ok"] is True
    assert review["status"] == "ready"
    assert review["keep_candidates"] == ["integration_adoption_readme"]
    assert review["summary"]["keep_count"] == 1
    assert review["next_actions"] == ["review_sunset_recommendations_with_mainline"]


def test_requested_deeper_merge_is_recommended_when_stable() -> None:
    review = build_integration_sunset_review(
        {
            "post_adoption_monitor": {"status": "ready", "ok": True},
            "validation_results": ["299 passed"],
            "candidates": [
                {
                    "candidate_id": "integration_rollout_guardrails",
                    "owner": "mainline",
                    "adoption_state": "ready",
                    "recommendation": "merge",
                    "evidence_refs": ["handoff"],
                }
            ],
        }
    )

    assert review["status"] == "ready"
    assert review["merge_deeper_candidates"] == ["integration_rollout_guardrails"]
    assert review["candidates"][0]["recommendation"] == "merge_deeper"


def test_sunset_request_is_preserved_when_evidence_is_stable() -> None:
    review = build_integration_sunset_review(
        {
            "post_adoption_monitor": {"status": "ready", "ok": True},
            "validation_results": ["299 passed"],
            "candidates": [
                {
                    "candidate_id": "old_candidate",
                    "owner": "mainline",
                    "adoption_state": "ready",
                    "recommendation": "sunset",
                    "evidence_refs": ["replaced by mainline"],
                }
            ],
        }
    )

    assert review["status"] == "ready"
    assert review["sunset_candidates"] == ["old_candidate"]


def test_blocked_or_missing_evidence_defers_candidate() -> None:
    review = build_integration_sunset_review(
        {
            "post_adoption_monitor": {"status": "blocked", "ok": False},
            "validation_results": ["1 failed"],
            "candidates": [
                {
                    "candidate_id": "integration_post_adoption_monitor",
                    "adoption_state": "ready",
                }
            ],
        }
    )

    assert review["status"] == "needs_review"
    assert review["defer_candidates"] == ["integration_post_adoption_monitor"]
    assert review["issues"][0]["code"] == "sunset_review_candidate_deferred"
    assert review["next_actions"] == [
        "resolve_deferred_sunset_candidates",
        "rebuild_integration_sunset_review",
    ]


def test_derives_candidates_from_monitor_and_owner_digest() -> None:
    review = build_integration_sunset_review(
        {
            "post_adoption_monitor": {
                "kind": "integration_post_adoption_monitor",
                "status": "ready",
                "watch_signals": [
                    {
                        "signal_id": "integration_rollout_guardrails",
                        "status": "ready",
                        "adoption_state": "ready",
                        "owner": "mainline",
                        "evidence_refs": ["monitor"],
                    }
                ],
            },
            "owner_digest": {
                "owners": [
                    {
                        "owner": "mainline",
                        "candidate_ids": ["integration_rollout_guardrails"],
                        "status": "ready",
                        "evidence_refs": ["owner"],
                    }
                ]
            },
            "validation_results": ["299 passed"],
        }
    )

    assert review["status"] == "ready"
    assert review["keep_candidates"] == ["integration_rollout_guardrails"]
    assert review["candidates"][0]["owner"] == "mainline"


def test_empty_sunset_review_requests_candidates() -> None:
    review = build_integration_sunset_review({})

    assert review["ok"] is False
    assert review["status"] == "empty"
    assert review["next_actions"] == ["provide_sunset_review_candidates"]


def test_review_sunset_candidate_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Candidate:
        candidate_id: str
        owner: str
        adoption_state: str
        monitor_state: str
        validation_state: str
        evidence_refs: list[str]

    candidate = review_sunset_candidate(
        Candidate("candidate-a", "mainline", "ready", "ready", "ready", ["evidence"])
    )

    assert candidate.candidate_id == "candidate-a"
    assert candidate.recommendation == "keep"
    assert candidate.reasons == ("candidate stable after adoption",)
