from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_acceptance_rollup import (
    build_integration_review_acceptance_rollup,
    summarize_review_acceptance_rollup_item,
)


def test_review_acceptance_rollup_summarizes_accepted_candidate() -> None:
    rollup = build_integration_review_acceptance_rollup(
        {
            "rollup_id": "rollup-1",
            "export_acceptance_check": {
                "decisions": [
                    {
                        "candidate_id": "integration_review_export_acceptance_check",
                        "check_key": "check-a",
                        "verdict": "accept",
                        "status": "ready",
                        "evidence_refs": ["6 passed"],
                        "handoff_refs": ["handoff"],
                        "owner": "mainline",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "action_status_export": {
                "rows": [
                    {
                        "candidate_id": "integration_review_export_acceptance_check",
                        "status_key": "status-a",
                        "status": "ready",
                        "export_formats": ["summary"],
                    }
                ]
            },
        }
    )

    assert rollup["kind"] == "integration_review_acceptance_rollup"
    assert rollup["ok"] is True
    assert rollup["status"] == "ready"
    assert rollup["summary"]["accepted_count"] == 1
    assert rollup["accepted_candidates"] == ["integration_review_export_acceptance_check"]
    assert rollup["readiness"]["score"] == 1.0
    assert rollup["next_actions"] == ["share_review_acceptance_rollup_with_mainline"]


def test_missing_refs_make_rollup_need_review() -> None:
    rollup = build_integration_review_acceptance_rollup(
        {
            "export_acceptance_check": {
                "decisions": [
                    {
                        "candidate_id": "candidate-a",
                        "check_key": "check-a",
                        "verdict": "needs_review",
                        "status": "needs_review",
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            }
        }
    )

    assert rollup["status"] == "needs_review"
    assert rollup["review_candidates"] == ["candidate-a"]
    assert "export refs missing" in rollup["items"][0]["reasons"]
    assert "rollup evidence missing" in rollup["items"][0]["reasons"]
    assert "attach_acceptance_rollup_export_refs" in rollup["next_actions"]


def test_blocked_acceptance_rollup_blocks_overall_status() -> None:
    rollup = build_integration_review_acceptance_rollup(
        {
            "export_acceptance_check": {
                "decisions": [
                    {
                        "candidate_id": "candidate-a",
                        "check_key": "check-a",
                        "verdict": "blocked",
                        "status": "blocked",
                        "evidence_refs": ["blocked evidence"],
                        "handoff_refs": ["handoff"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                        "blockers": ["validation timeout"],
                    }
                ]
            },
            "action_status_export": {
                "rows": [
                    {
                        "candidate_id": "candidate-a",
                        "status_key": "status-a",
                        "status": "blocked",
                        "export_formats": ["summary"],
                    }
                ]
            },
        }
    )

    assert rollup["status"] == "blocked"
    assert rollup["blocked_candidates"] == ["candidate-a"]
    assert rollup["items"][0]["verdict"] == "blocked"
    assert "rollup source blocked" in rollup["items"][0]["reasons"]
    assert rollup["next_actions"] == [
        "resolve_review_acceptance_rollup_blockers",
        "attach_acceptance_rollup_evidence",
        "rebuild_integration_review_acceptance_rollup",
    ]


def test_explicit_rollup_payload_can_seed_review_item() -> None:
    rollup = build_integration_review_acceptance_rollup(
        {
            "rollups": [
                {
                    "candidate_id": "candidate-a",
                    "rollup_key": "rollup-a",
                    "verdict": "accepted",
                    "status": "ready",
                    "acceptance_refs": ["check-a"],
                    "export_refs": ["status-a"],
                    "evidence_refs": ["manual evidence"],
                    "handoff_refs": ["handoff"],
                    "owner": "owner-a",
                    "reviewer": "reviewer-a",
                }
            ]
        }
    )

    assert rollup["status"] == "ready"
    assert rollup["items"][0]["rollup_key"] == "rollup-a"
    assert rollup["items"][0]["verdict"] == "accepted"


def test_empty_review_acceptance_rollup_requests_inputs() -> None:
    rollup = build_integration_review_acceptance_rollup({})

    assert rollup["ok"] is False
    assert rollup["status"] == "empty"
    assert rollup["next_actions"] == ["provide_review_acceptance_rollup_inputs"]


def test_summarize_review_acceptance_rollup_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Rollup:
        candidate_id: str
        rollup_key: str
        verdict: str
        status: str
        acceptance_refs: tuple[str, ...]
        export_refs: tuple[str, ...]
        evidence_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]
        owner: str
        reviewer: str

    item = summarize_review_acceptance_rollup_item(
        Rollup(
            candidate_id="candidate-a",
            rollup_key="rollup-a",
            verdict="accepted",
            status="ready",
            acceptance_refs=("check-a",),
            export_refs=("status-a",),
            evidence_refs=("evidence",),
            handoff_refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.rollup_key == "rollup-a"
    assert item.verdict == "accepted"
