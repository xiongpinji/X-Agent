from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_decision_audit import (
    audit_integration_decision,
    build_integration_decision_audit,
)


def test_decision_audit_passes_complete_accepted_decision() -> None:
    audit = build_integration_decision_audit(
        {
            "review_id": "review-1",
            "decisions": [
                {
                    "candidate_id": "release-evidence-pack",
                    "decision": "accepted",
                    "owner": "mainline",
                    "rationale": "High evidence quality and low integration risk.",
                    "evidence_refs": ["tests/test_release_evidence_pack.py", "handoff"],
                    "rollback_plan": "Keep module detached until endpoint owner wires it.",
                }
            ],
        }
    )

    assert audit["kind"] == "integration_decision_audit"
    assert audit["ok"] is True
    assert audit["status"] == "passed"
    assert audit["summary"]["passed_count"] == 1
    assert audit["next_actions"] == ["prepare_traceable_integration_handoff"]


def test_missing_decision_blocks_audit() -> None:
    audit = build_integration_decision_audit(
        {
            "decisions": [
                {
                    "candidate_id": "candidate-a",
                    "owner": "mainline",
                    "rationale": "Need a decision.",
                    "evidence": ["report"],
                }
            ]
        }
    )

    assert audit["status"] == "blocked"
    assert audit["decisions"][0]["status"] == "blocked"
    assert audit["issues"][0]["code"] == "integration_decision_missing"
    assert audit["next_actions"] == ["record_missing_decisions", "rerun_integration_decision_audit"]


def test_accepted_decision_without_rollback_needs_review() -> None:
    item = audit_integration_decision(
        {
            "candidate_id": "runtime-manifest",
            "decision": "integrate_now",
            "owner": "mainline",
            "rationale": "Ready to integrate.",
            "evidence_refs": ["combined validation"],
        }
    )

    assert item.status == "needs_review"
    assert "rollback plan missing for accepted decision" in item.reasons


def test_deferred_decision_requires_followups_and_review_condition() -> None:
    audit = build_integration_decision_audit(
        {
            "decisions": [
                {
                    "candidate_id": "channel-readiness",
                    "decision": "defer",
                    "owner": "mainline",
                    "rationale": "Needs real callback evidence first.",
                    "evidence_refs": ["handoff"],
                }
            ]
        }
    )

    assert audit["status"] == "needs_review"
    assert audit["issues"][0]["code"] == "integration_decision_followups_missing"
    assert "review condition missing for deferred decision" in audit["decisions"][0]["reasons"]


def test_rejected_decision_requires_reconsideration_condition() -> None:
    item = audit_integration_decision(
        {
            "candidate_id": "unsafe-tool-wiring",
            "decision": "rejected",
            "owner": "mainline",
            "rationale": "Runtime mutation risk.",
            "evidence": ["scorecard"],
        }
    )

    assert item.status == "needs_review"
    assert "reconsideration condition missing for rejected decision" in item.reasons


def test_accepts_audit_and_dataclass_like_decision_payload() -> None:
    @dataclass
    class Decision:
        candidate_id: str
        decision: str
        owner: str
        rationale: str
        evidence_refs: list[str]
        rollback_plan: str

    audit = build_integration_decision_audit(
        {
            "audit": {
                "decisions": [
                    Decision(
                        "scorecard",
                        "approved",
                        "mainline",
                        "Useful prioritization helper.",
                        ["tests", "handoff"],
                        "Keep detached on integration failure.",
                    )
                ]
            }
        }
    )

    assert audit["status"] == "passed"
    assert audit["decisions"][0]["candidate_id"] == "scorecard"
    assert audit["decisions"][0]["decision"] == "accepted"


def test_empty_audit_requests_decisions() -> None:
    audit = build_integration_decision_audit({})

    assert audit["status"] == "empty"
    assert audit["ok"] is False
    assert audit["next_actions"] == ["provide_integration_decisions"]
