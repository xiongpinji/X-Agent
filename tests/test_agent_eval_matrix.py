from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.agent_eval_matrix import (
    AgentEvalCriterion,
    build_agent_eval_matrix,
    evaluate_agent_task_result,
)


def test_agent_eval_matrix_accepts_all_required_passed_with_evidence() -> None:
    matrix = build_agent_eval_matrix(
        {
            "task_id": "task-1",
            "goal": "ship patch with tests",
            "criteria": [
                {"id": "tests", "label": "Tests pass", "required": True},
                {"id": "handoff", "label": "Handoff updated", "required": True},
            ],
            "results": {
                "tests": {"status": "passed", "score": 0.96, "evidence": [{"cmd": "pytest"}]},
                "handoff": {"status": "accepted", "score": 0.9, "evidence": [{"file": "handoff.md"}]},
            },
        }
    )

    assert matrix["kind"] == "agent_eval_matrix"
    assert matrix["ok"] is True
    assert matrix["status"] == "accepted"
    assert matrix["summary"]["accepted_count"] == 2
    assert matrix["next_actions"] == ["prepare_release_or_review_handoff"]


def test_required_missing_result_blocks_release() -> None:
    matrix = build_agent_eval_matrix(
        {
            "criteria": [{"id": "browser", "label": "Browser evidence", "required": True}],
            "results": {},
        }
    )

    assert matrix["ok"] is False
    assert matrix["status"] == "blocked"
    assert matrix["summary"]["missing_count"] == 1
    assert matrix["issues"][0]["code"] == "agent_eval_required_criterion_missing"
    assert matrix["next_actions"] == ["collect_missing_results_or_evidence", "rerun_agent_eval_matrix"]


def test_required_failed_result_blocks_release() -> None:
    matrix = build_agent_eval_matrix(
        {
            "criteria": [{"id": "lint", "label": "Lint", "required": True}],
            "results": {"lint": {"status": "failed", "score": 0.2, "evidence": [{"cmd": "ruff"}]}},
        }
    )

    assert matrix["status"] == "blocked"
    assert matrix["rows"][0]["decision"] == "blocked"
    assert matrix["issues"][0]["code"] == "agent_eval_required_criterion_failed"
    assert "result failed" in matrix["rows"][0]["reasons"]


def test_optional_failed_result_needs_review() -> None:
    matrix = build_agent_eval_matrix(
        {
            "criteria": [{"id": "screenshot", "label": "Screenshot", "required": False}],
            "results": {"screenshot": {"status": "failed", "score": 0.0}},
        }
    )

    assert matrix["status"] == "needs_review"
    assert matrix["rows"][0]["decision"] == "needs_review"
    assert matrix["issues"][0]["code"] == "agent_eval_optional_criterion_failed"


def test_regression_from_baseline_needs_review_when_otherwise_passed() -> None:
    matrix = build_agent_eval_matrix(
        {
            "criteria": [
                {
                    "id": "quality",
                    "label": "Quality score",
                    "required": False,
                    "min_score": 0.7,
                    "regression_tolerance": 0.1,
                }
            ],
            "results": {"quality": {"status": "passed", "score": 0.72, "evidence": [{"report": "eval"}]}},
            "baseline": {"quality": {"score": 0.92}},
        }
    )

    assert matrix["status"] == "needs_review"
    assert matrix["summary"]["regression_count"] == 1
    assert matrix["rows"][0]["regression_delta"] == -0.2
    assert matrix["issues"][0]["code"] == "agent_eval_regression_detected"
    assert matrix["next_actions"] == ["review_regression_delta", "compare_against_baseline"]


def test_missing_evidence_blocks_required_criterion() -> None:
    row = evaluate_agent_task_result(
        AgentEvalCriterion("artifact", "Artifact produced", required=True, evidence_required=True),
        {"status": "passed", "score": 0.95},
    )

    assert row.decision == "blocked"
    assert row.evidence_count == 0
    assert "evidence missing" in row.reasons


def test_accepts_dataclass_like_payloads_and_percent_scores() -> None:
    @dataclass
    class Criterion:
        id: str
        label: str
        required: bool
        min_score: int

    @dataclass
    class Result:
        criterion_id: str
        status: str
        score: int
        evidence: list[dict[str, str]]

    matrix = build_agent_eval_matrix(
        {
            "criteria": [Criterion("security", "Security", True, 80)],
            "results": [Result("security", "passed", 91, [{"report": "scan"}])],
            "baseline": [{"criterion_id": "security", "score": 88}],
        }
    )

    assert matrix["status"] == "accepted"
    assert matrix["rows"][0]["score"] == 0.91
    assert matrix["rows"][0]["baseline_score"] == 0.88
    assert matrix["rows"][0]["regression_delta"] == 0.03


def test_empty_matrix_requests_criteria_and_results() -> None:
    matrix = build_agent_eval_matrix({})

    assert matrix["status"] == "empty"
    assert matrix["ok"] is False
    assert matrix["next_actions"] == ["provide_acceptance_criteria_and_task_results"]
