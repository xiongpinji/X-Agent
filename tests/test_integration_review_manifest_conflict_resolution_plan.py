from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_conflict_resolution_plan import (
    build_integration_review_manifest_conflict_resolution_plan,
    summarize_review_manifest_conflict_resolution_item,
)


def test_resolution_plan_marks_clear_preview_ready() -> None:
    plan = build_integration_review_manifest_conflict_resolution_plan(
        {
            "manifest_conflict_preview": {
                "items": [
                    {
                        "candidate_id": "integration_review_manifest_conflict_preview",
                        "conflict_key": "conflict-a",
                        "status": "ready",
                        "conflict_level": "none",
                        "candidate_paths": ["backend/app/core/integration_review_manifest_conflict_preview.py"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert plan["kind"] == "integration_review_manifest_conflict_resolution_plan"
    assert plan["ok"] is True
    assert plan["status"] == "ready"
    assert plan["ready_candidates"] == ["integration_review_manifest_conflict_preview"]
    assert plan["items"][0]["recommended_decision"] == "prepare_candidate_for_mainline_evaluation"
    assert plan["next_actions"] == ["share_manifest_conflict_resolution_plan_with_mainline"]


def test_review_conflict_uses_owner_and_reviewer_hints() -> None:
    plan = build_integration_review_manifest_conflict_resolution_plan(
        {
            "manifest_conflict_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "conflict_key": "conflict-a",
                        "status": "needs_review",
                        "conflict_level": "review",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "handoff_refs": ["handoff"],
                        "reasons": ["active scope overlap"],
                    }
                ]
            },
            "owner_hints": {"candidate-a": "backend-owner"},
            "reviewer_hints": {"candidate-a": {"reviewer": "mainline-reviewer"}},
        }
    )

    assert plan["status"] == "needs_review"
    assert plan["review_candidates"] == ["candidate-a"]
    assert plan["items"][0]["owner"] == "backend-owner"
    assert plan["items"][0]["reviewer"] == "mainline-reviewer"
    assert plan["items"][0]["recommended_decision"] == "coordinate_candidate_with_mainline_owner"
    assert "coordinate_manifest_conflict_with_mainline_owner" in plan["next_actions"]


def test_blocked_conflict_defers_candidate() -> None:
    plan = build_integration_review_manifest_conflict_resolution_plan(
        {
            "manifest_conflict_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "conflict_key": "conflict-a",
                        "status": "blocked",
                        "conflict_level": "blocked",
                        "candidate_paths": ["backend/app/api/router.py"],
                        "handoff_refs": ["handoff"],
                        "forbidden_paths": ["backend/app/api"],
                    }
                ]
            },
            "owner_hints": {"candidate-a": "backend-owner"},
            "reviewer_hints": {"candidate-a": "mainline-reviewer"},
        }
    )

    assert plan["status"] == "blocked"
    assert plan["blocked_candidates"] == ["candidate-a"]
    assert plan["items"][0]["priority"] == "high"
    assert plan["items"][0]["recommended_decision"] == "defer_candidate_until_blockers_resolved"
    assert "backend/app/api" in plan["items"][0]["blockers"]
    assert plan["next_actions"][0] == "resolve_manifest_conflict_resolution_plan_blockers"


def test_missing_handoff_refs_requires_review() -> None:
    plan = build_integration_review_manifest_conflict_resolution_plan(
        {
            "manifest_conflict_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "conflict_key": "conflict-a",
                        "status": "ready",
                        "conflict_level": "none",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                    }
                ]
            }
        }
    )

    assert plan["status"] == "needs_review"
    assert "handoff refs missing" in plan["items"][0]["reasons"]
    assert "attach_manifest_conflict_handoff_refs" in plan["next_actions"]


def test_empty_resolution_plan_requests_inputs() -> None:
    plan = build_integration_review_manifest_conflict_resolution_plan({})

    assert plan["ok"] is False
    assert plan["status"] == "empty"
    assert plan["next_actions"] == ["provide_review_manifest_conflict_resolution_inputs"]


def test_explicit_resolution_payload_can_override_decision_and_actions() -> None:
    plan = build_integration_review_manifest_conflict_resolution_plan(
        {
            "resolutions": [
                {
                    "candidate_id": "candidate-a",
                    "plan_key": "plan-a",
                    "status": "ready",
                    "conflict_level": "none",
                    "candidate_paths": ["module.py"],
                    "handoff_refs": ["handoff"],
                    "recommended_decision": "hold_for_batch_review",
                    "required_actions": ["sync_with_release_owner"],
                }
            ]
        }
    )

    assert plan["status"] == "ready"
    assert plan["items"][0]["plan_key"] == "plan-a"
    assert plan["items"][0]["recommended_decision"] == "hold_for_batch_review"
    assert plan["items"][0]["required_actions"] == ["sync_with_release_owner"]


def test_summarize_resolution_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Resolution:
        candidate_id: str
        conflict_key: str
        status: str
        conflict_level: str
        candidate_paths: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_conflict_resolution_item(
        Resolution(
            candidate_id="candidate-a",
            conflict_key="conflict-a",
            status="ready",
            conflict_level="none",
            candidate_paths=("module.py",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.recommended_decision == "prepare_candidate_for_mainline_evaluation"
