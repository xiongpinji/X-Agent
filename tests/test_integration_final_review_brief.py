from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_final_review_brief import (
    build_integration_final_review_brief,
    summarize_review_brief_signal,
)


def _ready_signal(kind: str) -> dict[str, object]:
    return {
        "kind": kind,
        "status": "ready",
        "ok": True,
        "summary": {"issue_count": 0},
        "evidence_refs": [f"{kind}:handoff"],
    }


def test_final_review_brief_is_ready_for_mainline_review() -> None:
    brief = build_integration_final_review_brief(
        {
            "brief_id": "brief-1",
            "closure_checklist": _ready_signal("integration_closure_checklist"),
            "owner_digest": {
                "kind": "integration_owner_digest",
                "status": "ready",
                "ok": True,
                "summary": {"owner_count": 2, "issue_count": 0},
                "owners": [{"owner": "mainline"}, {"owner": "release"}],
                "evidence_refs": ["owners:handoff"],
            },
            "governance_summary": _ready_signal("integration_governance_summary"),
            "review_packet": _ready_signal("integration_review_packet"),
            "traceability_index": _ready_signal("integration_traceability_index"),
        }
    )

    assert brief["kind"] == "integration_final_review_brief"
    assert brief["ok"] is True
    assert brief["status"] == "ready"
    assert brief["verdict"] == "ready_for_mainline_review"
    assert brief["summary"]["signal_count"] == 5
    assert brief["owner_summary"]["owners"] == ["mainline", "release"]
    assert brief["summary"]["evidence_ref_count"] == 5
    assert brief["next_actions"] == ["submit_final_review_brief_to_mainline"]


def test_blocked_signal_blocks_final_review_brief() -> None:
    brief = build_integration_final_review_brief(
        {
            "closure_checklist": {
                "kind": "integration_closure_checklist",
                "status": "blocked",
                "ok": False,
                "summary": {"blocked_count": 1, "issue_count": 1},
                "issues": [{"code": "closure_check_blocked", "severity": "high"}],
                "next_actions": ["resolve_closure_blockers"],
            },
            "owner_digest": _ready_signal("integration_owner_digest"),
        }
    )

    assert brief["status"] == "blocked"
    assert brief["verdict"] == "blocked"
    assert brief["summary"]["blocked_signal_count"] == 1
    assert brief["issues"][0]["code"] == "final_review_signal_blocked"
    assert brief["risks"] == ["blocked_signals_present", "unresolved_review_issues_present"]
    assert brief["next_actions"] == [
        "resolve_final_review_blockers",
        "resolve_closure_blockers",
        "rebuild_integration_final_review_brief",
    ]


def test_review_items_and_missing_evidence_keep_brief_in_review() -> None:
    brief = build_integration_final_review_brief(
        {
            "signals": [
                {
                    "kind": "integration_owner_digest",
                    "status": "needs_review",
                    "ok": False,
                    "summary": {
                        "needs_review_owner_count": 1,
                        "missing_evidence_count": 2,
                    },
                    "owners": [{"owner": "unassigned"}],
                }
            ]
        }
    )

    assert brief["status"] == "needs_review"
    assert brief["verdict"] == "needs_review"
    assert brief["owner_summary"]["owner_count"] == 0
    assert brief["evidence_summary"]["missing_evidence_count"] == 2
    assert brief["risks"] == ["unresolved_review_issues_present", "missing_evidence_present"]
    assert brief["next_actions"] == [
        "review_final_brief_issues",
        "rebuild_integration_final_review_brief",
    ]


def test_owner_summary_reads_owner_digest_from_components() -> None:
    brief = build_integration_final_review_brief(
        {
            "components": [
                _ready_signal("integration_closure_checklist"),
                {
                    "kind": "integration_owner_digest",
                    "status": "ready",
                    "ok": True,
                    "summary": {"owner_count": 1},
                    "owners": [{"owner": "mainline", "evidence_refs": ["owner evidence"]}],
                },
            ]
        }
    )

    assert brief["owner_summary"]["owners"] == ["mainline"]
    assert brief["evidence_summary"]["evidence_refs"] == [
        "integration_closure_checklist:handoff",
        "owner evidence",
    ]


def test_empty_final_review_brief_requests_inputs() -> None:
    brief = build_integration_final_review_brief({})

    assert brief["ok"] is False
    assert brief["status"] == "needs_review"
    assert brief["verdict"] == "needs_inputs"
    assert brief["next_actions"] == ["provide_final_review_brief_inputs"]


def test_summarize_review_brief_signal_accepts_dataclass_like_component() -> None:
    @dataclass
    class Component:
        kind: str
        status: str
        ok: bool
        summary: dict[str, int]

    signal = summarize_review_brief_signal(
        Component("integration_review_packet", "ready", True, {"issue_count": 0})
    )

    assert signal.kind == "integration_review_packet"
    assert signal.verdict == "ready"
    assert signal.reasons == ("signal ready for final review brief",)
