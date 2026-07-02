from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_readiness_gate import (
    build_integration_review_readiness_gate,
    evaluate_review_gate_check,
)


def test_review_readiness_gate_marks_complete_payload_ready() -> None:
    gate = build_integration_review_readiness_gate(
        {
            "gate_id": "gate-1",
            "secondary_index": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1, "blocked_count": 0, "needs_review_count": 0},
                "entries": [
                    {
                        "candidate_id": "integration_conflict_risk_register",
                        "handoff_refs": ["handoff#conflict-risk"],
                    }
                ],
            },
            "conflict_risk_register": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1, "blocked_count": 0, "needs_review_count": 0, "high_risk_count": 0},
                "entries": [{"candidate_id": "integration_conflict_risk_register"}],
            },
            "traceability_index": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1, "blocked_count": 0, "needs_review_count": 0},
                "records": [
                    {
                        "candidate_id": "integration_conflict_risk_register",
                        "handoff_refs": ["handoff#conflict-risk"],
                    }
                ],
            },
            "validation": {
                "commands": ["python -m pytest tests/test_integration_conflict_risk_register.py -q"],
                "results": ["6 passed"],
                "statuses": ["passed"],
            },
            "owner_digest": {"owners": [{"owner": "mainline"}]},
        }
    )

    assert gate["kind"] == "integration_review_readiness_gate"
    assert gate["ok"] is True
    assert gate["status"] == "ready"
    assert gate["verdict"] == "ready_for_review"
    assert gate["summary"]["ready_check_count"] == 6
    assert gate["next_actions"] == ["share_review_readiness_gate_with_mainline"]


def test_blocked_conflict_or_validation_blocks_gate() -> None:
    gate = build_integration_review_readiness_gate(
        {
            "secondary_index": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1},
                "entries": [{"candidate_id": "candidate-a", "handoff_refs": ["handoff"]}],
            },
            "conflict_risk_register": {
                "ok": False,
                "status": "blocked",
                "summary": {"candidate_count": 1, "blocked_count": 1, "high_risk_count": 1},
                "entries": [{"candidate_id": "candidate-a"}],
            },
            "traceability_index": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1},
                "records": [{"candidate_id": "candidate-a", "handoff_refs": ["handoff"]}],
            },
            "validation_statuses": ["failed"],
            "validation_commands": ["python -m pytest tests/test_candidate_a.py -q"],
            "validation_results": ["1 failed"],
            "owners": ["mainline"],
        }
    )

    assert gate["status"] == "blocked"
    assert gate["verdict"] == "blocked"
    assert gate["blocked_checks"] == ["conflict_risk", "validation"]
    assert gate["next_actions"] == [
        "resolve_review_readiness_blockers",
        "resolve_conflict_risk_blockers",
        "refresh_passing_validation_evidence",
        "rebuild_integration_review_readiness_gate",
    ]


def test_missing_owner_and_handoff_need_review() -> None:
    gate = build_integration_review_readiness_gate(
        {
            "secondary_index": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1},
                "entries": [{"candidate_id": "candidate-a"}],
            },
            "conflict_risk_register": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1},
                "entries": [{"candidate_id": "candidate-a"}],
            },
            "traceability_index": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1},
                "records": [{"candidate_id": "candidate-a"}],
            },
            "validation": {
                "commands": ["python -m pytest tests/test_candidate_a.py -q"],
                "results": ["1 passed"],
                "statuses": ["passed"],
            },
        }
    )

    assert gate["status"] == "needs_review"
    assert gate["review_checks"] == ["handoff", "owners"]
    assert gate["next_actions"] == [
        "review_readiness_gate_warnings",
        "attach_secondary_handoff_references",
        "assign_or_confirm_candidate_owners",
        "rebuild_integration_review_readiness_gate",
    ]


def test_explicit_checks_are_supported() -> None:
    gate = build_integration_review_readiness_gate(
        {
            "checks": [
                {"check_id": "secondary_index", "status": "ready", "severity": "low"},
                {"check_id": "traceability", "status": "needs_review", "next_actions": ["complete_traceability_evidence"]},
            ]
        }
    )

    assert gate["status"] == "needs_review"
    assert gate["review_checks"] == ["traceability"]
    assert gate["ready_checks"] == ["secondary_index"]
    assert gate["next_actions"] == [
        "review_readiness_gate_warnings",
        "complete_traceability_evidence",
        "rebuild_integration_review_readiness_gate",
    ]


def test_empty_gate_requests_inputs() -> None:
    gate = build_integration_review_readiness_gate({"checks": []})

    assert gate["ok"] is False
    assert gate["verdict"] == "needs_inputs"
    assert gate["next_actions"] == ["provide_review_readiness_gate_inputs"]


def test_evaluate_review_gate_check_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Check:
        check_id: str
        status: str
        severity: str
        count: int
        refs: list[str]
        reasons: list[str]
        next_actions: list[str]

    check = evaluate_review_gate_check(
        Check("validation", "ready", "low", 1, ["6 passed"], ["validation ready"], [])
    )

    assert check.check_id == "validation"
    assert check.status == "ready"
    assert check.severity == "low"
    assert check.refs == ("6 passed",)
