from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_closure_checklist import (
    build_integration_closure_checklist,
    summarize_closure_check,
)


def _ready_component(kind: str) -> dict[str, object]:
    return {
        "kind": kind,
        "status": "ready",
        "ok": True,
        "summary": {"issue_count": 0},
        "next_actions": [],
    }


def test_closure_checklist_is_ready_when_all_components_are_ready() -> None:
    checklist = build_integration_closure_checklist(
        {
            "checklist_id": "closure-1",
            "owner_digest": _ready_component("integration_owner_digest"),
            "followup_queue": _ready_component("integration_followup_queue"),
            "governance_summary": _ready_component("integration_governance_summary"),
            "review_packet": _ready_component("integration_review_packet"),
            "traceability_index": _ready_component("integration_traceability_index"),
            "sequence_plan": _ready_component("integration_sequence_plan"),
            "decision_audit": _ready_component("integration_decision_audit"),
        }
    )

    assert checklist["kind"] == "integration_closure_checklist"
    assert checklist["ok"] is True
    assert checklist["status"] == "ready"
    assert checklist["closure_ready"] is True
    assert checklist["summary"]["ready_count"] == 7
    assert checklist["ready_checks"] == [
        "owner_digest",
        "followup_queue",
        "governance_summary",
        "review_packet",
        "traceability_index",
        "sequence_plan",
        "decision_audit",
    ]
    assert checklist["next_actions"] == ["submit_closure_checklist_for_mainline_review"]


def test_blocked_component_blocks_closure_checklist() -> None:
    checklist = build_integration_closure_checklist(
        {
            "owner_digest": _ready_component("integration_owner_digest"),
            "followup_queue": {
                "kind": "integration_followup_queue",
                "status": "blocked",
                "ok": False,
                "issues": [{"code": "followup_blocked", "severity": "high"}],
                "next_actions": ["resolve_blocked_followups"],
            },
            "governance_summary": _ready_component("integration_governance_summary"),
            "review_packet": _ready_component("integration_review_packet"),
            "traceability_index": _ready_component("integration_traceability_index"),
            "sequence_plan": _ready_component("integration_sequence_plan"),
            "decision_audit": _ready_component("integration_decision_audit"),
        }
    )

    assert checklist["status"] == "blocked"
    assert checklist["closure_ready"] is False
    assert checklist["blocked_checks"] == ["followup_queue"]
    assert checklist["issues"][0]["code"] == "closure_check_blocked"
    assert checklist["next_actions"] == [
        "resolve_closure_blockers",
        "resolve_blocked_followups",
        "rebuild_integration_closure_checklist",
    ]


def test_missing_components_are_reported_without_filesystem_scans() -> None:
    checklist = build_integration_closure_checklist(
        {
            "owner_digest": _ready_component("integration_owner_digest"),
        }
    )

    assert checklist["status"] == "needs_review"
    assert checklist["summary"]["missing_count"] == 6
    assert checklist["missing_checks"] == [
        "followup_queue",
        "governance_summary",
        "review_packet",
        "traceability_index",
        "sequence_plan",
        "decision_audit",
    ]
    assert checklist["issues"][0]["code"] == "closure_check_component_missing"
    assert checklist["next_actions"][:2] == [
        "provide_missing_closure_components",
        "provide_followup_queue",
    ]


def test_missing_evidence_keeps_closure_in_review() -> None:
    checklist = build_integration_closure_checklist(
        {
            "owner_digest": {
                "kind": "integration_owner_digest",
                "status": "ready",
                "ok": True,
                "summary": {"missing_evidence_count": 1},
            },
            "followup_queue": _ready_component("integration_followup_queue"),
            "governance_summary": _ready_component("integration_governance_summary"),
            "review_packet": _ready_component("integration_review_packet"),
            "traceability_index": _ready_component("integration_traceability_index"),
            "sequence_plan": _ready_component("integration_sequence_plan"),
            "decision_audit": _ready_component("integration_decision_audit"),
        }
    )

    assert checklist["status"] == "needs_review"
    assert checklist["review_checks"] == ["owner_digest"]
    assert checklist["summary"]["missing_evidence_count"] == 1
    assert checklist["issues"][0]["code"] == "closure_check_missing_evidence"
    assert checklist["next_actions"] == [
        "attach_closure_evidence",
        "rebuild_integration_closure_checklist",
    ]


def test_components_list_aliases_are_accepted() -> None:
    checklist = build_integration_closure_checklist(
        {
            "components": [
                _ready_component("integration_owner_digest"),
                _ready_component("integration_followup_queue"),
                _ready_component("integration_governance_summary"),
                _ready_component("integration_review_packet"),
                _ready_component("integration_traceability_index"),
                _ready_component("integration_sequence_plan"),
                _ready_component("integration_decision_audit"),
            ]
        }
    )

    assert checklist["status"] == "ready"
    assert checklist["summary"]["check_count"] == 7


def test_summarize_closure_check_accepts_dataclass_like_component() -> None:
    @dataclass
    class Component:
        kind: str
        status: str
        ok: bool
        summary: dict[str, int]

    check = summarize_closure_check(
        "traceability_index",
        Component("integration_traceability_index", "ready", True, {"issue_count": 0}),
    )

    assert check.check_id == "traceability_index"
    assert check.component_kind == "integration_traceability_index"
    assert check.decision == "ready"
    assert check.reasons == ("component ready for closure",)
