from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_conflict_risk_register import (
    assess_conflict_risk,
    build_integration_conflict_risk_register,
)


def test_conflict_risk_register_marks_detached_candidate_ready() -> None:
    register = build_integration_conflict_risk_register(
        {
            "register_id": "risk-1",
            "candidates": [
                {
                    "candidate_id": "integration_secondary_index",
                    "integration_status": "secondary_integration_candidate",
                    "owner": "secondary",
                    "files": ["backend/app/core/integration_secondary_index.py"],
                    "tests": ["tests/test_integration_secondary_index.py"],
                    "validation_statuses": ["passed"],
                }
            ],
            "forbidden_paths": ["backend/app/api/", "frontend/", "backend/app/core/__init__.py"],
            "active_mainline_scopes": ["backend/app/api/workbench.py"],
        }
    )

    assert register["kind"] == "integration_conflict_risk_register"
    assert register["ok"] is True
    assert register["status"] == "ready"
    assert register["summary"]["low_risk_count"] == 1
    assert register["ready_candidates"] == ["integration_secondary_index"]
    assert register["next_actions"] == ["share_conflict_risk_register_with_mainline_for_review"]


def test_forbidden_path_or_failed_validation_blocks_candidate() -> None:
    register = build_integration_conflict_risk_register(
        {
            "candidates": [
                {
                    "candidate_id": "router_candidate",
                    "integration_status": "secondary_integration_candidate",
                    "files": ["backend/app/api/workbench.py"],
                    "tests": ["tests/test_workbench.py"],
                    "validation_statuses": ["failed"],
                }
            ],
            "forbidden_paths": ["backend/app/api/"],
        }
    )

    assert register["status"] == "blocked"
    entry = register["entries"][0]
    assert entry["risk_level"] == "high"
    assert entry["review_status"] == "blocked"
    assert entry["forbidden_matches"] == ["backend/app/api/"]
    assert "candidate touches forbidden path" in entry["reasons"]
    assert "validation failed or blocked" in entry["reasons"]
    assert entry["next_actions"] == [
        "exclude_or_reclassify_candidate_scope",
        "refresh_candidate_validation_evidence",
        "rebuild_integration_conflict_risk_register",
    ]


def test_active_scope_and_owner_overlap_needs_review() -> None:
    register = build_integration_conflict_risk_register(
        {
            "candidates": [
                {
                    "candidate_id": "review_packet",
                    "owner": "mainline",
                    "files": ["backend/app/core/integration_review_packet.py"],
                    "tests": ["tests/test_integration_review_packet.py"],
                    "validation_statuses": ["passed"],
                }
            ],
            "active_mainline_scopes": ["backend/app/core/integration_review_packet.py"],
            "active_owners": ["mainline"],
        }
    )

    assert register["status"] == "needs_review"
    assert register["review_candidates"] == ["review_packet"]
    assert register["owner_conflicts"] == {"mainline": ["review_packet"]}
    entry = register["entries"][0]
    assert entry["risk_level"] == "medium"
    assert entry["active_scope_matches"] == ["backend/app/core/integration_review_packet.py"]
    assert entry["shared_owner_matches"] == ["mainline"]
    assert entry["next_actions"] == [
        "coordinate_with_active_mainline_scope_owner",
        "confirm_owner_capacity_before_review",
        "rebuild_integration_conflict_risk_register",
    ]


def test_register_merges_secondary_index_and_validation_rows() -> None:
    register = build_integration_conflict_risk_register(
        {
            "secondary_index": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "integration_status": "secondary_integration_candidate",
                        "owner": "secondary",
                        "files": ["backend/app/core/candidate_a.py"],
                        "tests": ["tests/test_candidate_a.py"],
                    }
                ]
            },
            "validations": [
                {
                    "candidate_id": "candidate-a",
                    "status": "passed",
                }
            ],
        }
    )

    assert register["status"] == "ready"
    entry = register["entries"][0]
    assert entry["candidate_id"] == "candidate-a"
    assert entry["owner"] == "secondary"
    assert entry["validation_statuses"] == ["passed"]


def test_empty_register_requests_candidates() -> None:
    register = build_integration_conflict_risk_register({})

    assert register["ok"] is False
    assert register["status"] == "empty"
    assert register["next_actions"] == ["provide_conflict_risk_candidates"]


def test_assess_conflict_risk_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Candidate:
        candidate_id: str
        integration_status: str
        owner: str
        files: list[str]
        tests: list[str]
        validation_statuses: list[str]

    entry = assess_conflict_risk(
        Candidate(
            "candidate-a",
            "secondary_integration_candidate",
            "secondary",
            ["backend/app/core/candidate_a.py"],
            ["tests/test_candidate_a.py"],
            ["passed"],
        )
    )

    assert entry.candidate_id == "candidate-a"
    assert entry.risk_level == "low"
    assert entry.review_status == "ready"
    assert entry.reasons == ("conflict risk low",)
