from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_readiness_snapshot import (
    build_integration_readiness_snapshot,
    summarize_integration_component,
)


def test_snapshot_marks_all_ready_components_ready() -> None:
    snapshot = build_integration_readiness_snapshot(
        {
            "snapshot_id": "snap-1",
            "components": [
                {
                    "kind": "integration_candidate_scorecard",
                    "status": "ready",
                    "ok": True,
                    "summary": {"integrate_now_count": 1},
                    "next_actions": ["review_top_integration_candidate"],
                },
                {
                    "kind": "integration_decision_audit",
                    "status": "passed",
                    "ok": True,
                    "summary": {"passed_count": 1},
                    "next_actions": ["prepare_traceable_integration_handoff"],
                },
            ],
        }
    )

    assert snapshot["kind"] == "integration_readiness_snapshot"
    assert snapshot["ok"] is True
    assert snapshot["status"] == "ready"
    assert snapshot["summary"]["ready_count"] == 2
    assert snapshot["highlights"]["ready_components"] == [
        "integration_candidate_scorecard",
        "integration_decision_audit",
    ]
    assert snapshot["next_actions"] == ["prepare_mainline_integration_review"]


def test_blocked_component_blocks_snapshot() -> None:
    snapshot = build_integration_readiness_snapshot(
        {
            "components": [
                {
                    "kind": "release_evidence_pack",
                    "status": "blocked",
                    "ok": False,
                    "issues": [{"code": "release_evidence_matrix_blocked", "severity": "high"}],
                    "next_actions": ["resolve_blocking_evidence_matrices"],
                }
            ]
        }
    )

    assert snapshot["status"] == "blocked"
    assert snapshot["issues"][0]["code"] == "integration_snapshot_component_blocked"
    assert snapshot["highlights"]["blocked_components"] == ["release_evidence_pack"]
    assert snapshot["next_actions"] == ["resolve_blocked_snapshot_components", "rebuild_integration_readiness_snapshot"]


def test_review_component_bubbles_next_actions() -> None:
    snapshot = build_integration_readiness_snapshot(
        {
            "components": [
                {
                    "kind": "runtime_capability_manifest",
                    "status": "needs_review",
                    "ok": False,
                    "issues": [{"code": "runtime_capability_owner_missing"}],
                    "next_actions": ["assign_integration_owners", "collect_missing_runtime_evidence"],
                }
            ]
        }
    )

    assert snapshot["status"] == "needs_review"
    assert snapshot["issues"][0]["code"] == "integration_snapshot_unresolved_issues"
    assert snapshot["next_actions"] == ["assign_integration_owners", "collect_missing_runtime_evidence"]


def test_ready_status_with_false_ok_needs_review() -> None:
    component = summarize_integration_component(
        {
            "kind": "scorecard",
            "status": "ready",
            "ok": False,
        }
    )

    assert component.decision == "needs_review"
    assert "ready component has ok=false" in component.reasons


def test_empty_snapshot_requests_components() -> None:
    snapshot = build_integration_readiness_snapshot({})

    assert snapshot["status"] == "empty"
    assert snapshot["ok"] is False
    assert snapshot["next_actions"] == ["provide_snapshot_components"]


def test_accepts_mapping_and_dataclass_like_components() -> None:
    @dataclass
    class Component:
        kind: str
        status: str
        ok: bool
        issues: list[dict[str, str]]
        next_actions: list[str]
        summary: dict[str, int]

    snapshot = build_integration_readiness_snapshot(
        {
            "components": {
                "decision": Component(
                    "integration_decision_audit",
                    "passed",
                    True,
                    [],
                    ["prepare_traceable_integration_handoff"],
                    {"passed_count": 1},
                )
            }
        }
    )

    assert snapshot["status"] == "ready"
    assert snapshot["components"][0]["kind"] == "integration_decision_audit"
    assert snapshot["components"][0]["summary"] == {"passed_count": 1}


def test_snapshot_highlights_dedupe_top_actions() -> None:
    snapshot = build_integration_readiness_snapshot(
        {
            "components": [
                {"kind": "a", "status": "needs_review", "ok": False, "next_actions": ["fix", "rerun"]},
                {"kind": "b", "status": "needs_review", "ok": False, "next_actions": ["fix", "review"]},
            ]
        }
    )

    assert snapshot["highlights"]["top_next_actions"] == ["fix", "rerun", "review"]
