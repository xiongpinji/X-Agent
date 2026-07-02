from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_followup_queue import (
    analyze_followup_item,
    build_integration_followup_queue,
)


def test_followup_queue_builds_ready_queue_from_explicit_items() -> None:
    queue = build_integration_followup_queue(
        {
            "queue_id": "followups-1",
            "followups": [
                {
                    "followup_id": "f1",
                    "owner": "mainline",
                    "action": "review_traceability_index",
                    "source_kind": "integration_traceability_index",
                    "candidate_id": "traceability",
                    "severity": "medium",
                    "evidence_refs": ["handoff", "tests passed"],
                }
            ],
        }
    )

    assert queue["kind"] == "integration_followup_queue"
    assert queue["ok"] is True
    assert queue["status"] == "ready"
    assert queue["summary"]["followup_count"] == 1
    assert queue["by_owner"] == {"mainline": ["f1"]}
    assert queue["next_actions"] == ["review_followup_queue_with_mainline"]


def test_high_severity_issue_generates_blocked_followup() -> None:
    queue = build_integration_followup_queue(
        {
            "governance_summary": {
                "kind": "integration_governance_summary",
                "issues": [
                    {
                        "code": "governance_signal_blocked",
                        "severity": "high",
                        "owner": "mainline",
                        "candidate_id": "dependency-map",
                        "evidence_refs": ["governance summary"],
                    }
                ],
            }
        }
    )

    assert queue["status"] == "blocked"
    assert queue["summary"]["blocked_count"] == 1
    assert queue["followups"][0]["action"] == "resolve_governance_signal_blocked"
    assert queue["blocked_followups"] == [queue["followups"][0]["followup_id"]]
    assert queue["next_actions"] == ["resolve_blocked_followups", "rebuild_integration_followup_queue"]


def test_missing_owner_and_evidence_needs_review() -> None:
    queue = build_integration_followup_queue(
        {
            "followups": [
                {
                    "action": "attach_handoff_references",
                    "source_kind": "integration_traceability_index",
                    "severity": "medium",
                }
            ]
        }
    )

    assert queue["status"] == "needs_review"
    assert queue["summary"]["owner_missing_count"] == 1
    assert queue["issues"][0]["code"] == "followup_owner_missing"
    assert queue["issues"][1]["code"] == "followup_evidence_missing"
    assert queue["next_actions"] == [
        "assign_followup_owners",
        "attach_followup_evidence",
        "rebuild_integration_followup_queue",
    ]


def test_component_next_actions_generate_followups_and_dedupe() -> None:
    queue = build_integration_followup_queue(
        {
            "components": [
                {
                    "kind": "integration_review_packet",
                    "owner": "mainline",
                    "next_actions": ["review_packet_issues", "review_packet_issues"],
                    "review_topics": ["traceability_handoff_refs_missing"],
                }
            ]
        }
    )

    assert queue["status"] == "needs_review"
    assert len(queue["followups"]) == 1
    assert queue["followups"][0]["action"] == "review_packet_issues"
    assert queue["followups"][0]["topics"] == ["traceability_handoff_refs_missing"]


def test_accepts_dataclass_like_followup() -> None:
    @dataclass
    class Followup:
        owner: str
        action: str
        source_kind: str
        candidate_id: str
        severity: str
        evidence_refs: list[str]

    queue = build_integration_followup_queue(
        {
            "items": [
                Followup(
                    "release",
                    "prepare_release_evidence",
                    "release_evidence_pack",
                    "release-evidence-pack",
                    "low",
                    ["release tests passed"],
                )
            ]
        }
    )

    assert queue["status"] == "ready"
    assert queue["followups"][0]["owner"] == "release"
    assert queue["followups"][0]["priority"] == 30


def test_analyze_followup_item_marks_blocked_priority() -> None:
    item = analyze_followup_item(
        {
            "owner": "mainline",
            "action": "resolve_dependency_cycle",
            "source_kind": "candidate_dependency_map",
            "severity": "high",
            "evidence_refs": ["cycle"],
        }
    )

    assert item.status == "blocked"
    assert item.priority == 100
    assert "followup blocked" in item.reasons


def test_empty_followup_queue_requests_inputs() -> None:
    queue = build_integration_followup_queue({})

    assert queue["status"] == "empty"
    assert queue["ok"] is False
    assert queue["next_actions"] == ["provide_followup_queue_inputs"]
