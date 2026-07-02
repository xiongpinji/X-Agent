from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_packet import (
    build_integration_review_packet,
    summarize_review_component,
)


def test_review_packet_marks_complete_components_ready() -> None:
    packet = build_integration_review_packet(
        {
            "packet_id": "review-1",
            "scorecard": {
                "kind": "integration_candidate_scorecard",
                "status": "ready",
                "ok": True,
                "summary": {"candidate_count": 2, "integrate_now_count": 2},
                "next_actions": ["review_top_integration_candidate"],
            },
            "dependency_map": {
                "kind": "candidate_dependency_map",
                "status": "ready",
                "ok": True,
                "summary": {"candidate_count": 2},
                "next_actions": ["prepare_ordered_integration_plan"],
            },
            "sequence_plan": {
                "kind": "integration_sequence_plan",
                "status": "ready",
                "ok": True,
                "summary": {"candidate_count": 2},
                "next_actions": ["prepare_traceable_integration_sequence"],
            },
            "traceability_index": {
                "kind": "integration_traceability_index",
                "status": "ready",
                "ok": True,
                "summary": {"candidate_count": 2},
                "next_actions": ["prepare_auditable_integration_review"],
            },
        }
    )

    assert packet["kind"] == "integration_review_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["component_count"] == 4
    assert packet["summary"]["candidate_count"] == 2
    assert packet["highlights"]["ready_components"] == [
        "integration_candidate_scorecard",
        "candidate_dependency_map",
        "integration_sequence_plan",
        "integration_traceability_index",
    ]
    assert packet["recommendations"] == ["submit_packet_for_mainline_review"]


def test_blocked_component_blocks_review_packet() -> None:
    packet = build_integration_review_packet(
        {
            "components": [
                {
                    "kind": "integration_traceability_index",
                    "status": "blocked",
                    "ok": False,
                    "issues": [{"code": "traceability_validation_blocked", "severity": "high"}],
                    "next_actions": ["resolve_blocked_traceability_records"],
                }
            ]
        }
    )

    assert packet["status"] == "blocked"
    assert packet["issues"][0]["code"] == "review_packet_component_blocked"
    assert packet["highlights"]["blocked_components"] == ["integration_traceability_index"]
    assert packet["next_actions"] == [
        "resolve_blocked_review_packet_components",
        "rerun_review_packet",
        "resolve_blocked_traceability_records",
    ]


def test_review_component_requests_review_and_dedupes_actions() -> None:
    packet = build_integration_review_packet(
        {
            "components": [
                {
                    "kind": "integration_decision_audit",
                    "status": "needs_review",
                    "ok": False,
                    "issues": [{"code": "integration_decision_followups_missing", "severity": "medium"}],
                    "next_actions": ["record_missing_decisions", "rerun_review_packet"],
                },
                {
                    "kind": "integration_traceability_index",
                    "status": "needs_review",
                    "ok": False,
                    "issues": [{"code": "traceability_handoff_refs_missing", "severity": "medium"}],
                    "next_actions": ["record_missing_decisions", "attach_handoff_references"],
                },
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["summary"]["needs_review_count"] == 2
    assert packet["next_actions"] == [
        "review_packet_issues",
        "complete_missing_review_evidence",
        "record_missing_decisions",
        "rerun_review_packet",
        "attach_handoff_references",
    ]


def test_high_severity_issue_blocks_even_with_nonblocked_status() -> None:
    component = summarize_review_component(
        {
            "kind": "release_evidence_pack",
            "status": "needs_review",
            "ok": False,
            "issues": [{"code": "release_evidence_matrix_blocked", "severity": "high"}],
        }
    )

    assert component.decision == "blocked"
    assert "component has high severity issues" in component.reasons


def test_accepts_mapping_and_dataclass_like_components() -> None:
    @dataclass
    class Component:
        kind: str
        status: str
        ok: bool
        summary: dict[str, int]
        issues: list[dict[str, str]]
        next_actions: list[str]

    packet = build_integration_review_packet(
        {
            "components": {
                "traceability": Component(
                    "integration_traceability_index",
                    "ready",
                    True,
                    {"candidate_count": 1},
                    [],
                    ["prepare_auditable_integration_review"],
                )
            }
        }
    )

    assert packet["status"] == "ready"
    assert packet["components"][0]["kind"] == "integration_traceability_index"
    assert packet["review_sections"][0]["title"] == "Integration Traceability Index"


def test_empty_review_packet_requests_inputs() -> None:
    packet = build_integration_review_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_review_packet_inputs"]
