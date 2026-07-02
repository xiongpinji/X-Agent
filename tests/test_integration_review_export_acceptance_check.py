from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_export_acceptance_check import (
    build_integration_review_export_acceptance_check,
    summarize_review_export_acceptance_decision,
)


def test_review_export_acceptance_check_accepts_ready_export() -> None:
    check = build_integration_review_export_acceptance_check(
        {
            "check_id": "check-1",
            "action_status_export": {
                "rows": [
                    {
                        "candidate_id": "integration_review_action_status_export",
                        "status_key": "status-a",
                        "status": "ready",
                        "export_formats": ["markdown", "json"],
                        "evidence_refs": ["6 passed"],
                        "owner": "mainline",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "handoff_refs": [
                {
                    "candidate_id": "integration_review_action_status_export",
                    "path": "docs/original-kernel-secondary-handoff.md#integration-review-action-status-export",
                }
            ],
        }
    )

    assert check["kind"] == "integration_review_export_acceptance_check"
    assert check["ok"] is True
    assert check["status"] == "ready"
    assert check["summary"]["accepted_count"] == 1
    assert check["accepted_candidates"] == ["integration_review_action_status_export"]
    assert check["decisions"][0]["verdict"] == "accept"
    assert check["next_actions"] == ["share_review_export_acceptance_check_with_mainline"]


def test_missing_handoff_and_formats_need_review() -> None:
    check = build_integration_review_export_acceptance_check(
        {
            "action_status_export": {
                "rows": [
                    {
                        "candidate_id": "candidate-a",
                        "status_key": "status-a",
                        "status": "needs_review",
                        "evidence_refs": ["partial evidence"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            }
        }
    )

    assert check["status"] == "needs_review"
    assert check["review_candidates"] == ["candidate-a"]
    assert "export formats missing" in check["decisions"][0]["reasons"]
    assert "handoff refs missing" in check["decisions"][0]["reasons"]
    assert "attach_export_formats" in check["next_actions"]
    assert "attach_export_acceptance_handoff_refs" in check["next_actions"]


def test_blocked_validation_blocks_acceptance_check() -> None:
    check = build_integration_review_export_acceptance_check(
        {
            "action_status_export": {
                "rows": [
                    {
                        "candidate_id": "candidate-a",
                        "status_key": "status-a",
                        "status": "ready",
                        "export_formats": ["summary"],
                        "evidence_refs": ["blocked evidence"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "validation_evidence": [
                {
                    "candidate_id": "candidate-a",
                    "status": "blocked",
                    "refs": ["blocked evidence"],
                    "blockers": ["validation timeout"],
                }
            ],
            "handoff_refs": {"candidate-a": {"path": "handoff"}},
        }
    )

    assert check["status"] == "blocked"
    assert check["blocked_candidates"] == ["candidate-a"]
    assert check["decisions"][0]["verdict"] == "blocked"
    assert "acceptance source blocked" in check["decisions"][0]["reasons"]
    assert check["next_actions"] == [
        "resolve_review_export_acceptance_blockers",
        "attach_export_acceptance_evidence",
        "rebuild_integration_review_export_acceptance_check",
    ]


def test_explicit_decision_payload_can_seed_check() -> None:
    check = build_integration_review_export_acceptance_check(
        {
            "decisions": [
                {
                    "candidate_id": "candidate-a",
                    "check_key": "check-a",
                    "status": "ready",
                    "export_formats": ["summary"],
                    "evidence_refs": ["manual evidence"],
                    "handoff_refs": ["handoff"],
                    "owner": "owner-a",
                    "reviewer": "reviewer-a",
                }
            ]
        }
    )

    assert check["status"] == "needs_review"
    assert check["decisions"][0]["check_key"] == "check-a"
    assert "export row missing" in check["decisions"][0]["reasons"]


def test_empty_review_export_acceptance_check_requests_inputs() -> None:
    check = build_integration_review_export_acceptance_check({})

    assert check["ok"] is False
    assert check["status"] == "empty"
    assert check["next_actions"] == ["provide_review_export_acceptance_inputs"]


def test_summarize_review_export_acceptance_decision_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Decision:
        candidate_id: str
        check_key: str
        status: str
        export_formats: tuple[str, ...]
        evidence_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]
        owner: str
        reviewer: str

    decision = summarize_review_export_acceptance_decision(
        Decision(
            candidate_id="candidate-a",
            check_key="check-a",
            status="ready",
            export_formats=("summary",),
            evidence_refs=("evidence",),
            handoff_refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
        )
    )

    assert decision.candidate_id == "candidate-a"
    assert decision.check_key == "check-a"
    assert decision.verdict == "needs_review"
    assert "export row missing" in decision.reasons
