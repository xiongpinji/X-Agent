from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_rollback_preview import (
    build_integration_review_manifest_adoption_rollback_preview,
    summarize_review_manifest_adoption_rollback_preview_item,
)


def test_rollback_preview_marks_ready_adoption_ready() -> None:
    preview = build_integration_review_manifest_adoption_rollback_preview(
        {
            "manifest_adoption_dry_run_report": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "report_key": "report-a",
                        "status": "ready",
                        "recommended_outcome": "adopt",
                        "touched_paths": ["stage_include:backend/app/core/candidate_a.py"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert preview["kind"] == "integration_review_manifest_adoption_rollback_preview"
    assert preview["ok"] is True
    assert preview["status"] == "ready"
    assert preview["ready_candidates"] == ["candidate-a"]
    assert preview["items"][0]["rollback_operation"] == "preview_remove_staged_candidate"
    assert "stage_remove:backend/app/core/candidate_a.py" in preview["rollback_sections"]["rollback_paths"]
    assert preview["next_actions"] == ["share_manifest_adoption_rollback_preview_with_mainline"]


def test_rollback_preview_blocks_blocked_dry_run() -> None:
    preview = build_integration_review_manifest_adoption_rollback_preview(
        {
            "manifest_adoption_dry_run_report": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "report_key": "report-a",
                        "status": "blocked",
                        "recommended_outcome": "defer",
                        "touched_paths": ["backend/app/api/router.py"],
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            }
        }
    )

    assert preview["status"] == "blocked"
    assert preview["blocked_candidates"] == ["candidate-a"]
    assert "forbidden scope overlap" in preview["rollback_sections"]["blockers"]
    assert preview["next_actions"][0] == "resolve_manifest_adoption_rollback_preview_blockers"


def test_rollback_preview_surfaces_warnings_for_review() -> None:
    preview = build_integration_review_manifest_adoption_rollback_preview(
        {
            "manifest_adoption_dry_run_report": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "report_key": "report-a",
                        "status": "needs_review",
                        "recommended_outcome": "adopt",
                        "touched_paths": ["stage_include:backend/app/core/candidate_a.py"],
                        "handoff_refs": ["handoff"],
                        "warnings": ["validation refs missing"],
                    }
                ]
            }
        }
    )

    assert preview["status"] == "needs_review"
    assert preview["review_candidates"] == ["candidate-a"]
    assert "validation refs missing" in preview["rollback_sections"]["warnings"]
    assert "complete_manifest_adoption_dry_run_report" in preview["next_actions"]


def test_execution_preview_can_supply_fallback_refs() -> None:
    preview = build_integration_review_manifest_adoption_rollback_preview(
        {
            "manifest_adoption_dry_run_report": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "report_key": "report-a",
                        "status": "ready",
                        "recommended_outcome": "adopt",
                    }
                ]
            },
            "manifest_adoption_execution_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "touched_paths": ["stage_include:backend/app/core/candidate_a.py"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
        }
    )

    assert preview["status"] == "ready"
    assert "stage_remove:backend/app/core/candidate_a.py" in preview["items"][0]["rollback_paths"]
    assert preview["items"][0]["validation_refs"] == ["pytest candidate-a"]


def test_explicit_rollback_preview_can_seed_preview() -> None:
    preview = build_integration_review_manifest_adoption_rollback_preview(
        {
            "rollback_previews": [
                {
                    "candidate_id": "candidate-a",
                    "rollback_key": "rollback-a",
                    "status": "ready",
                    "recommended_outcome": "reject",
                    "source_touched_paths": ["module.py"],
                    "rollback_paths": ["rollback_check:module.py"],
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert preview["status"] == "ready"
    assert preview["items"][0]["rollback_key"] == "rollback-a"
    assert preview["items"][0]["recommended_outcome"] == "reject"


def test_empty_rollback_preview_requests_inputs() -> None:
    preview = build_integration_review_manifest_adoption_rollback_preview({})

    assert preview["ok"] is False
    assert preview["status"] == "empty"
    assert preview["next_actions"] == ["provide_review_manifest_adoption_rollback_preview_inputs"]


def test_summarize_rollback_preview_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Rollback:
        candidate_id: str
        rollback_key: str
        status: str
        recommended_outcome: str
        source_touched_paths: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_rollback_preview_item(
        Rollback(
            candidate_id="candidate-a",
            rollback_key="rollback-a",
            status="ready",
            recommended_outcome="adopt",
            source_touched_paths=("stage_include:module.py",),
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.rollback_operation == "preview_remove_staged_candidate"
