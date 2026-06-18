from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_go_no_go import (
    build_integration_review_manifest_adoption_go_no_go,
    summarize_review_manifest_adoption_go_no_go_item,
)


def test_go_no_go_marks_ready_rollback_preview_go() -> None:
    decision = build_integration_review_manifest_adoption_go_no_go(
        {
            "manifest_adoption_rollback_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "rollback_key": "rollback-a",
                        "status": "ready",
                        "recommended_outcome": "adopt",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert decision["kind"] == "integration_review_manifest_adoption_go_no_go"
    assert decision["ok"] is True
    assert decision["status"] == "ready"
    assert decision["go_candidates"] == ["candidate-a"]
    assert decision["items"][0]["confidence"] == "high"
    assert decision["next_actions"] == ["share_manifest_adoption_go_no_go_with_mainline"]


def test_go_no_go_holds_when_rollback_needs_review() -> None:
    decision = build_integration_review_manifest_adoption_go_no_go(
        {
            "manifest_adoption_rollback_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "rollback_key": "rollback-a",
                        "status": "needs_review",
                        "recommended_outcome": "adopt",
                        "handoff_refs": ["handoff"],
                        "warnings": ["validation refs required"],
                    }
                ]
            }
        }
    )

    assert decision["status"] == "needs_review"
    assert decision["hold_candidates"] == ["candidate-a"]
    assert "rollback preview must be completed" in decision["items"][0]["required_evidence"]
    assert "complete_manifest_adoption_rollback_preview" in decision["next_actions"]


def test_go_no_go_blocks_when_rollback_is_blocked() -> None:
    decision = build_integration_review_manifest_adoption_go_no_go(
        {
            "manifest_adoption_rollback_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "rollback_key": "rollback-a",
                        "status": "blocked",
                        "recommended_outcome": "defer",
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            }
        }
    )

    assert decision["status"] == "blocked"
    assert decision["no_go_candidates"] == ["candidate-a"]
    assert decision["items"][0]["confidence"] == "low"
    assert decision["next_actions"][0] == "resolve_manifest_adoption_go_no_go_blockers"


def test_dry_run_report_can_supply_fallback_evidence() -> None:
    decision = build_integration_review_manifest_adoption_go_no_go(
        {
            "manifest_adoption_rollback_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "rollback_key": "rollback-a",
                        "status": "ready",
                        "recommended_outcome": "adopt",
                    }
                ]
            },
            "manifest_adoption_dry_run_report": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
        }
    )

    assert decision["status"] == "ready"
    assert decision["items"][0]["validation_refs"] == ["pytest candidate-a"]
    assert decision["items"][0]["handoff_refs"] == ["handoff"]


def test_explicit_go_no_go_can_override_decision() -> None:
    decision = build_integration_review_manifest_adoption_go_no_go(
        {
            "decisions": [
                {
                    "candidate_id": "candidate-a",
                    "decision_key": "go-no-go-a",
                    "status": "ready",
                    "go_no_go": "hold",
                    "recommended_outcome": "review",
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert decision["status"] == "ready"
    assert decision["hold_candidates"] == ["candidate-a"]
    assert decision["items"][0]["decision_key"] == "go-no-go-a"


def test_empty_go_no_go_requests_inputs() -> None:
    decision = build_integration_review_manifest_adoption_go_no_go({})

    assert decision["ok"] is False
    assert decision["status"] == "empty"
    assert decision["next_actions"] == ["provide_review_manifest_adoption_go_no_go_inputs"]


def test_summarize_go_no_go_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class GoNoGo:
        candidate_id: str
        decision_key: str
        status: str
        go_no_go: str
        recommended_outcome: str
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_go_no_go_item(
        GoNoGo(
            candidate_id="candidate-a",
            decision_key="go-no-go-a",
            status="ready",
            go_no_go="go",
            recommended_outcome="adopt",
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.go_no_go == "go"
