from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_governance_summary import (
    build_integration_governance_summary,
    summarize_governance_signal,
)


def test_governance_summary_marks_all_ready_signals_ready() -> None:
    summary = build_integration_governance_summary(
        {
            "summary_id": "gov-1",
            "review_packet": {
                "kind": "integration_review_packet",
                "status": "ready",
                "ok": True,
                "summary": {"candidate_count": 3},
                "next_actions": ["submit_packet_for_mainline_review"],
            },
            "traceability_index": {
                "kind": "integration_traceability_index",
                "status": "ready",
                "ok": True,
                "summary": {"candidate_count": 3},
                "next_actions": ["prepare_auditable_integration_review"],
            },
            "decision_audit": {
                "kind": "integration_decision_audit",
                "status": "passed",
                "ok": True,
                "summary": {"passed_count": 3},
            },
        }
    )

    assert summary["kind"] == "integration_governance_summary"
    assert summary["ok"] is True
    assert summary["status"] == "ready"
    assert summary["governance_posture"] == "ready"
    assert summary["summary"]["candidate_count"] == 3
    assert summary["ready_components"] == [
        "integration_review_packet",
        "integration_traceability_index",
        "integration_decision_audit",
    ]
    assert summary["recommendations"] == ["approve_governance_summary_for_mainline_review"]


def test_blocked_signal_blocks_governance_summary() -> None:
    summary = build_integration_governance_summary(
        {
            "signals": [
                {
                    "kind": "candidate_dependency_map",
                    "status": "blocked",
                    "ok": False,
                    "summary": {"missing_dependency_count": 1},
                    "issues": [{"code": "candidate_dependency_missing", "severity": "high"}],
                    "next_actions": ["add_missing_dependencies_or_remove_references"],
                }
            ]
        }
    )

    assert summary["status"] == "blocked"
    assert summary["blocked_topics"] == [
        "candidate_dependency_map",
        "blocked_status",
        "not_ok",
        "candidate_dependency_missing",
        "high_severity_issue",
        "missing_dependency_count",
    ]
    assert summary["issues"][0]["code"] == "governance_signal_blocked"
    assert summary["next_actions"] == [
        "resolve_blocked_governance_signals",
        "rerun_governance_summary",
        "add_missing_dependencies_or_remove_references",
    ]


def test_review_signal_needs_review_without_blocking() -> None:
    summary = build_integration_governance_summary(
        {
            "signals": [
                {
                    "kind": "integration_traceability_index",
                    "status": "needs_review",
                    "ok": False,
                    "issues": [{"code": "traceability_handoff_refs_missing", "severity": "medium"}],
                    "next_actions": ["attach_handoff_references"],
                }
            ]
        }
    )

    assert summary["status"] == "needs_review"
    assert summary["review_topics"] == [
        "integration_traceability_index",
        "review_status",
        "not_ok",
        "traceability_handoff_refs_missing",
    ]
    assert summary["recommendations"] == ["review_governance_signals", "complete_governance_evidence"]


def test_high_severity_issue_blocks_even_if_status_needs_review() -> None:
    signal = summarize_governance_signal(
        {
            "kind": "integration_review_packet",
            "status": "needs_review",
            "ok": False,
            "issues": [{"code": "review_packet_high_severity_component_issues", "severity": "high"}],
        }
    )

    assert signal.posture == "blocked"
    assert "high_severity_issue" in signal.topics


def test_accepts_mapping_and_dataclass_like_signals() -> None:
    @dataclass
    class Signal:
        kind: str
        status: str
        ok: bool
        summary: dict[str, int]
        issues: list[dict[str, str]]
        next_actions: list[str]

    summary = build_integration_governance_summary(
        {
            "signals": {
                "review": Signal(
                    "integration_review_packet",
                    "ready",
                    True,
                    {"candidate_count": 1},
                    [],
                    ["submit_packet_for_mainline_review"],
                )
            }
        }
    )

    assert summary["status"] == "ready"
    assert summary["signals"][0]["kind"] == "integration_review_packet"
    assert summary["governance_topics"][0] == {"topic": "integration_review_packet", "count": 1}


def test_empty_governance_summary_requests_inputs() -> None:
    summary = build_integration_governance_summary({})

    assert summary["status"] == "empty"
    assert summary["ok"] is False
    assert summary["next_actions"] == ["provide_governance_summary_inputs"]
