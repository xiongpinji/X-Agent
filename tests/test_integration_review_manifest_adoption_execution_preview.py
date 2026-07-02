from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_execution_preview import (
    build_integration_review_manifest_adoption_execution_preview,
    summarize_review_manifest_adoption_execution_preview_item,
)


def test_execution_preview_marks_adopt_row_ready() -> None:
    preview = build_integration_review_manifest_adoption_execution_preview(
        {
            "manifest_adoption_decision_sheet": {
                "rows": [
                    {
                        "candidate_id": "candidate-a",
                        "decision_key": "decision-a",
                        "decision_status": "ready",
                        "recommended_outcome": "adopt",
                        "stage_label": "secondary_integration_candidate",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "manifest_refs": ["manifest-a"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert preview["kind"] == "integration_review_manifest_adoption_execution_preview"
    assert preview["ok"] is True
    assert preview["status"] == "ready"
    assert preview["ready_candidates"] == ["candidate-a"]
    assert preview["items"][0]["operation"] == "preview_stage_candidate_for_adoption"
    assert "stage_include:backend/app/core/candidate_a.py" in preview["items"][0]["touched_paths"]
    assert preview["next_actions"] == ["share_manifest_adoption_execution_preview_with_mainline"]


def test_execution_preview_can_preview_defer_without_stage_include() -> None:
    preview = build_integration_review_manifest_adoption_execution_preview(
        {
            "manifest_adoption_decision_sheet": {
                "rows": [
                    {
                        "candidate_id": "candidate-a",
                        "decision_key": "decision-a",
                        "decision_status": "ready",
                        "recommended_outcome": "defer",
                        "stage_label": "secondary_deferred",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert preview["status"] == "ready"
    assert preview["items"][0]["operation"] == "preview_mark_candidate_deferred"
    assert "stage_include:backend/app/core/candidate_a.py" not in preview["items"][0]["touched_paths"]


def test_execution_preview_blocks_blocked_decision() -> None:
    preview = build_integration_review_manifest_adoption_execution_preview(
        {
            "manifest_adoption_decision_sheet": {
                "rows": [
                    {
                        "candidate_id": "candidate-a",
                        "decision_key": "decision-a",
                        "decision_status": "blocked",
                        "recommended_outcome": "defer",
                        "candidate_paths": ["backend/app/api/router.py"],
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            }
        }
    )

    assert preview["status"] == "blocked"
    assert preview["blocked_candidates"] == ["candidate-a"]
    assert preview["items"][0]["blockers"] == ["forbidden scope overlap"]
    assert preview["next_actions"][0] == "resolve_manifest_adoption_execution_preview_blockers"


def test_execution_preview_requires_adopt_evidence() -> None:
    preview = build_integration_review_manifest_adoption_execution_preview(
        {
            "manifest_adoption_decision_sheet": {
                "rows": [
                    {
                        "candidate_id": "candidate-a",
                        "decision_key": "decision-a",
                        "decision_status": "ready",
                        "recommended_outcome": "adopt",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert preview["status"] == "needs_review"
    assert "manifest refs missing" in preview["items"][0]["warnings"]
    assert "validation refs missing" in preview["items"][0]["warnings"]
    assert "attach_manifest_adoption_execution_manifest_refs" in preview["next_actions"]


def test_manifest_preview_can_supply_paths_and_manifest_refs() -> None:
    preview = build_integration_review_manifest_adoption_execution_preview(
        {
            "manifest_adoption_decision_sheet": {
                "rows": [
                    {
                        "candidate_id": "candidate-a",
                        "decision_key": "decision-a",
                        "decision_status": "ready",
                        "recommended_outcome": "adopt",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "adoption_manifest_preview": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "manifest_key": "manifest-a",
                        "include_paths": ["backend/app/core/candidate_a.py"],
                    }
                ]
            },
        }
    )

    assert preview["status"] == "ready"
    assert preview["items"][0]["candidate_paths"] == ["backend/app/core/candidate_a.py"]
    assert preview["items"][0]["manifest_refs"] == ["manifest-a"]


def test_empty_execution_preview_requests_inputs() -> None:
    preview = build_integration_review_manifest_adoption_execution_preview({})

    assert preview["ok"] is False
    assert preview["status"] == "empty"
    assert preview["next_actions"] == ["provide_review_manifest_adoption_execution_preview_inputs"]


def test_summarize_execution_preview_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Preview:
        candidate_id: str
        preview_key: str
        decision_status: str
        recommended_outcome: str
        candidate_paths: tuple[str, ...]
        manifest_refs: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_execution_preview_item(
        Preview(
            candidate_id="candidate-a",
            preview_key="preview-a",
            decision_status="ready",
            recommended_outcome="adopt",
            candidate_paths=("module.py",),
            manifest_refs=("manifest-a",),
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.operation == "preview_stage_candidate_for_adoption"
