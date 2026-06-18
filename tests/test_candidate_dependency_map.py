from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.candidate_dependency_map import (
    analyze_candidate_dependency,
    build_candidate_dependency_map,
)


def test_dependency_map_marks_ready_roots_and_ordered_candidates() -> None:
    dependency_map = build_candidate_dependency_map(
        {
            "map_id": "secondary-next",
            "candidates": [
                {
                    "id": "scorecard",
                    "owner": "mainline",
                    "status": "ready",
                },
                {
                    "id": "snapshot",
                    "owner": "mainline",
                    "status": "ready",
                    "depends_on": ["scorecard"],
                },
            ],
        }
    )

    assert dependency_map["kind"] == "candidate_dependency_map"
    assert dependency_map["ok"] is True
    assert dependency_map["status"] == "ready"
    assert dependency_map["ready_roots"] == ["scorecard"]
    assert dependency_map["ready_with_satisfied_dependencies"] == ["snapshot"]
    assert dependency_map["integration_order"] == ["scorecard", "snapshot"]
    assert dependency_map["next_actions"] == ["prepare_ordered_integration_plan"]


def test_missing_dependency_blocks_map() -> None:
    dependency_map = build_candidate_dependency_map(
        {
            "candidates": [
                {
                    "id": "release-evidence-pack",
                    "owner": "release",
                    "status": "ready",
                    "depends_on": ["runtime-manifest"],
                }
            ]
        }
    )

    assert dependency_map["status"] == "blocked"
    assert dependency_map["missing_dependencies"] == [
        {
            "candidate_id": "release-evidence-pack",
            "dependency_id": "runtime-manifest",
            "code": "candidate_dependency_missing",
        }
    ]
    assert dependency_map["blocked_chains"][0]["chain"] == ["release-evidence-pack", "runtime-manifest"]
    assert dependency_map["next_actions"] == [
        "add_missing_dependencies_or_remove_references",
        "rebuild_candidate_dependency_map",
    ]


def test_dependency_cycle_blocks_map() -> None:
    dependency_map = build_candidate_dependency_map(
        {
            "candidates": [
                {"id": "a", "owner": "team", "status": "ready", "depends_on": ["b"]},
                {"id": "b", "owner": "team", "status": "ready", "depends_on": ["a"]},
            ]
        }
    )

    assert dependency_map["status"] == "blocked"
    assert dependency_map["cycles"] == [["a", "b", "a"]]
    assert dependency_map["integration_order"] == []
    assert dependency_map["issues"][0]["code"] == "candidate_dependency_cycle"
    assert dependency_map["next_actions"] == ["resolve_dependency_cycles", "rebuild_candidate_dependency_map"]


def test_blocks_field_creates_reverse_blocked_chain() -> None:
    dependency_map = build_candidate_dependency_map(
        {
            "candidates": [
                {
                    "id": "unsafe-runtime-wiring",
                    "owner": "runtime",
                    "status": "blocked",
                    "blocks": ["mainline-integration"],
                },
                {
                    "id": "mainline-integration",
                    "owner": "mainline",
                    "status": "ready",
                },
            ]
        }
    )

    assert dependency_map["status"] == "blocked"
    assert dependency_map["blocked_chains"] == [
        {
            "candidate_id": "unsafe-runtime-wiring",
            "chain": ["unsafe-runtime-wiring"],
            "reason": "candidate_blocked",
        },
        {
            "candidate_id": "mainline-integration",
            "chain": ["mainline-integration", "unsafe-runtime-wiring"],
            "reason": "dependency_blocked",
        },
    ]


def test_accepts_mapping_and_dataclass_like_candidates() -> None:
    @dataclass
    class Candidate:
        candidate_id: str
        owner: str
        status: str
        depends_on: list[str]

    dependency_map = build_candidate_dependency_map(
        {
            "candidates": {
                "runtime-manifest": {"owner": "runtime", "status": "ready"},
                "snapshot": Candidate("snapshot", "mainline", "ready", ["runtime-manifest"]),
            }
        }
    )

    assert dependency_map["status"] == "ready"
    assert dependency_map["candidates"][0]["candidate_id"] == "runtime-manifest"
    assert dependency_map["candidates"][1]["candidate_id"] == "snapshot"
    assert dependency_map["integration_order"] == ["runtime-manifest", "snapshot"]


def test_ownerless_candidate_is_orphan_and_needs_review() -> None:
    dependency_map = build_candidate_dependency_map(
        {
            "candidates": [
                {
                    "id": "candidate-without-owner",
                    "status": "ready",
                }
            ]
        }
    )

    assert dependency_map["status"] == "needs_review"
    assert dependency_map["orphan_candidates"] == ["candidate-without-owner"]
    assert dependency_map["issues"][0]["code"] == "candidate_dependency_candidate_needs_review"
    assert "assign_candidate_dependency_owners" in dependency_map["next_actions"]


def test_analyze_single_candidate_normalizes_recommendation() -> None:
    item = analyze_candidate_dependency(
        {
            "candidate_id": "integration-readiness-snapshot",
            "owner": "mainline",
            "recommendation": "integrate_now",
            "blocked_by": "scorecard",
        }
    )

    assert item.state == "ready"
    assert item.blocked_by == ("scorecard",)
    assert item.recommendation == "integrate_now"


def test_empty_dependency_map_requests_candidates() -> None:
    dependency_map = build_candidate_dependency_map({})

    assert dependency_map["status"] == "empty"
    assert dependency_map["ok"] is False
    assert dependency_map["next_actions"] == ["provide_dependency_candidates"]
