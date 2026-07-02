from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.open_source_adoption_matrix import (
    assess_open_source_candidate,
    build_open_source_adoption_matrix,
)


def test_adoption_matrix_marks_strong_permissive_candidate_ready() -> None:
    matrix = build_open_source_adoption_matrix(
        {
            "target": "browser automation and computer-use agent",
            "candidates": [
                {
                    "name": "browser-use",
                    "url": "https://github.com/browser-use/browser-use",
                    "license": "MIT",
                    "summary": "Browser automation agent for web tasks and computer-use workflows.",
                    "score": 0.88,
                    "tags": ["browser", "automation", "agent"],
                    "metadata": {"stars": 10000, "forks": 1000, "maintenance": "active"},
                }
            ],
        }
    )

    assert matrix["kind"] == "open_source_adoption_matrix"
    assert matrix["ok"] is True
    assert matrix["status"] == "adopt_ready"
    assert matrix["summary"]["top_candidate"] == "browser-use"
    assert matrix["candidates"][0]["recommendation"] == "adopt_ready"
    assert matrix["next_actions"] == ["prepare_integration_design_review"]


def test_restrictive_or_archived_candidate_is_do_not_adopt() -> None:
    matrix = build_open_source_adoption_matrix(
        {
            "target": "agent workflow orchestration",
            "candidates": [
                {
                    "name": "old-agent",
                    "license": "GPL-3.0",
                    "summary": "agent workflow",
                    "score": 0.8,
                    "metadata": {"archived": True},
                }
            ],
        }
    )

    assert matrix["ok"] is False
    assert matrix["status"] == "needs_review"
    assert matrix["candidates"][0]["recommendation"] == "do_not_adopt"
    assert set(matrix["candidates"][0]["risk_flags"]) == {"restrictive_license", "archived"}
    assert matrix["issues"][0]["code"] == "open_source_candidate_do_not_adopt"
    assert matrix["next_actions"] == ["reject_blocked_candidates", "review_alternatives"]


def test_missing_license_or_low_score_needs_review() -> None:
    candidate = assess_open_source_candidate(
        {
            "name": "small-tool",
            "summary": "PR review helper",
            "score": 0.3,
        },
        target="pull request review",
    )

    assert candidate.recommendation == "needs_review"
    assert candidate.risk_flags == ("missing_license", "low_score")
    assert candidate.risk_score > 0


def test_matrix_accepts_report_payload_candidates() -> None:
    matrix = build_open_source_adoption_matrix(
        {
            "target": "coding agent evaluation benchmark",
            "report": {
                "candidates": [
                    {
                        "name": "SWE-agent",
                        "license": "MIT",
                        "summary": "SWE coding agent benchmark and issue-to-fix workflow.",
                        "score": 75,
                        "tags": ["agent", "benchmark", "coding"],
                        "metadata": {"stars": 16000, "maintenance": "maintained"},
                    }
                ]
            },
        }
    )

    assert matrix["summary"]["candidate_count"] == 1
    assert matrix["candidates"][0]["name"] == "SWE-agent"
    assert matrix["candidates"][0]["health_score"] >= 0.9


def test_empty_matrix_requests_candidates() -> None:
    matrix = build_open_source_adoption_matrix({"target": "mcp tool server"})

    assert matrix["ok"] is False
    assert matrix["status"] == "empty"
    assert matrix["summary"]["candidate_count"] == 0
    assert matrix["next_actions"] == ["provide_open_source_candidates"]


def test_unknown_license_and_heavy_runtime_dependency_need_review() -> None:
    matrix = build_open_source_adoption_matrix(
        {
            "target": "agent orchestration",
            "candidates": [
                {
                    "name": "heavy-agent",
                    "license": "Custom",
                    "summary": "agent orchestration platform",
                    "score": 0.7,
                    "metadata": {"heavy_runtime_dependency": True},
                }
            ],
        }
    )

    assert matrix["candidates"][0]["recommendation"] == "needs_review"
    assert set(matrix["candidates"][0]["risk_flags"]) == {
        "unknown_license",
        "heavy_runtime_dependency",
    }
    assert matrix["next_actions"] == ["review_license_and_integration_risk"]


def test_accepts_dataclass_like_candidate() -> None:
    @dataclass
    class Candidate:
        name: str
        license: str
        summary: str
        score: float

    matrix = build_open_source_adoption_matrix(
        {
            "target": "mcp tool integration",
            "candidates": [Candidate("mcp-server", "Apache-2.0", "MCP tool server connector", 0.72)],
        }
    )

    assert matrix["candidates"][0]["name"] == "mcp-server"
    assert matrix["candidates"][0]["recommendation"] == "needs_review"
