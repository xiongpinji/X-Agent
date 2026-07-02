from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_sequence_plan import (
    analyze_sequence_candidate,
    build_integration_sequence_plan,
)


def test_sequence_plan_builds_ready_order_from_dependency_map() -> None:
    plan = build_integration_sequence_plan(
        {
            "plan_id": "secondary-plan",
            "scorecard": {
                "kind": "integration_candidate_scorecard",
                "candidates": [
                    {
                        "candidate_id": "scorecard",
                        "owner": "mainline",
                        "recommendation": "integrate_now",
                        "priority_score": 0.7,
                    },
                    {
                        "candidate_id": "snapshot",
                        "owner": "mainline",
                        "recommendation": "integrate_now",
                        "priority_score": 0.9,
                    },
                ],
            },
            "dependency_map": {
                "kind": "candidate_dependency_map",
                "status": "ready",
                "integration_order": ["scorecard", "snapshot"],
                "candidates": [
                    {"candidate_id": "scorecard", "owner": "mainline", "state": "ready"},
                    {"candidate_id": "snapshot", "owner": "mainline", "state": "ready"},
                ],
            },
            "decision_audit": {
                "kind": "integration_decision_audit",
                "status": "passed",
                "decisions": [
                    {"candidate_id": "scorecard", "owner": "mainline", "decision": "accepted"},
                    {"candidate_id": "snapshot", "owner": "mainline", "decision": "accepted"},
                ],
            },
            "readiness_snapshot": {"kind": "integration_readiness_snapshot", "status": "ready"},
        }
    )

    assert plan["kind"] == "integration_sequence_plan"
    assert plan["ok"] is True
    assert plan["status"] == "ready"
    assert plan["integration_order"] == ["scorecard", "snapshot"]
    assert plan["phases"] == [
        {
            "phase_id": "phase_1_ordered_integration",
            "phase": "ordered_integration",
            "candidate_ids": ["scorecard", "snapshot"],
            "action": "prepare_ordered_mainline_integration_review",
        }
    ]
    assert plan["next_actions"] == ["prepare_traceable_integration_sequence"]


def test_blocked_dependency_map_blocks_sequence_plan() -> None:
    plan = build_integration_sequence_plan(
        {
            "scorecard": {
                "candidates": [
                    {"candidate_id": "a", "owner": "team", "recommendation": "integrate_now"},
                    {"candidate_id": "b", "owner": "team", "recommendation": "integrate_now"},
                ]
            },
            "dependency_map": {
                "status": "blocked",
                "integration_order": [],
                "cycles": [["a", "b", "a"]],
                "candidates": [
                    {"candidate_id": "a", "owner": "team", "state": "blocked"},
                    {"candidate_id": "b", "owner": "team", "state": "blocked"},
                ],
            },
            "decision_audit": {
                "status": "passed",
                "decisions": [
                    {"candidate_id": "a", "owner": "team", "decision": "accepted"},
                    {"candidate_id": "b", "owner": "team", "decision": "accepted"},
                ],
            },
            "readiness_snapshot": {"status": "ready"},
        }
    )

    assert plan["status"] == "blocked"
    assert plan["blocked_candidates"] == ["a", "b"]
    assert plan["issues"][0]["code"] == "integration_sequence_dependency_map_blocked"
    assert plan["next_actions"] == ["resolve_sequence_blockers", "rebuild_integration_sequence_plan"]


def test_missing_decision_moves_candidate_to_review_queue() -> None:
    plan = build_integration_sequence_plan(
        {
            "scorecard": {
                "candidates": [
                    {
                        "candidate_id": "runtime-manifest",
                        "owner": "runtime",
                        "recommendation": "integrate_now",
                    }
                ]
            },
            "dependency_map": {
                "status": "ready",
                "integration_order": ["runtime-manifest"],
                "candidates": [{"candidate_id": "runtime-manifest", "owner": "runtime", "state": "ready"}],
            },
            "readiness_snapshot": {"status": "ready"},
        }
    )

    assert plan["status"] == "needs_review"
    assert plan["review_queue"] == ["runtime-manifest"]
    assert plan["issues"][0]["code"] == "integration_sequence_decision_missing"
    assert plan["next_actions"] == [
        "record_missing_integration_decisions",
        "rebuild_integration_sequence_plan",
    ]


def test_sequence_plan_sorts_by_priority_without_dependency_order() -> None:
    plan = build_integration_sequence_plan(
        {
            "scorecard": {
                "candidates": [
                    {
                        "candidate_id": "low",
                        "owner": "team",
                        "recommendation": "integrate_now",
                        "priority_score": 0.3,
                    },
                    {
                        "candidate_id": "high",
                        "owner": "team",
                        "recommendation": "integrate_now",
                        "priority_score": 0.9,
                    },
                ]
            },
            "dependency_map": {"status": "ready", "candidates": []},
            "decision_audit": {
                "status": "passed",
                "decisions": [
                    {"candidate_id": "low", "owner": "team", "decision": "accepted"},
                    {"candidate_id": "high", "owner": "team", "decision": "accepted"},
                ],
            },
            "readiness_snapshot": {"status": "ready"},
        }
    )

    assert plan["integration_order"] == ["high", "low"]


def test_accepts_components_and_dataclass_like_payloads() -> None:
    @dataclass
    class Candidate:
        candidate_id: str
        owner: str
        recommendation: str
        priority_score: int

    @dataclass
    class Decision:
        candidate_id: str
        owner: str
        decision: str

    plan = build_integration_sequence_plan(
        {
            "components": [
                {
                    "kind": "integration_candidate_scorecard",
                    "candidates": [Candidate("candidate-a", "team", "integrate_now", 82)],
                },
                {
                    "kind": "candidate_dependency_map",
                    "status": "ready",
                    "integration_order": ["candidate-a"],
                    "candidates": [{"candidate_id": "candidate-a", "owner": "team", "state": "ready"}],
                },
                {
                    "kind": "integration_decision_audit",
                    "status": "passed",
                    "decisions": [Decision("candidate-a", "team", "accepted")],
                },
                {"kind": "integration_readiness_snapshot", "status": "ready"},
            ]
        }
    )

    assert plan["status"] == "ready"
    assert plan["candidates"][0]["candidate_id"] == "candidate-a"
    assert plan["candidates"][0]["priority_score"] == 0.82


def test_analyze_sequence_candidate_marks_deferred_decision_for_review() -> None:
    item = analyze_sequence_candidate(
        {"candidate_id": "candidate-a", "owner": "team", "recommendation": "integrate_now"},
        decision={"candidate_id": "candidate-a", "decision": "defer"},
        dependency={"candidate_id": "candidate-a", "state": "ready"},
        readiness_state="ready",
        order_index=0,
    )

    assert item.state == "needs_review"
    assert item.phase == "review_required"
    assert "candidate needs review" in item.reasons


def test_empty_sequence_plan_requests_inputs() -> None:
    plan = build_integration_sequence_plan({})

    assert plan["status"] == "empty"
    assert plan["ok"] is False
    assert plan["next_actions"] == ["provide_sequence_plan_inputs"]
