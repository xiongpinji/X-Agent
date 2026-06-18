from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_conflict_preview import (
    build_integration_review_manifest_conflict_preview,
    summarize_review_manifest_conflict_item,
)


def test_manifest_conflict_preview_marks_clear_candidate() -> None:
    preview = build_integration_review_manifest_conflict_preview(
        {
            "adoption_manifest_preview": {
                "entries": [
                    {
                        "candidate_id": "integration_review_adoption_manifest_preview",
                        "manifest_key": "manifest-a",
                        "status": "ready",
                        "include_paths": ["backend/app/core/integration_review_adoption_manifest_preview.py"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "active_scopes": ["frontend/src/App.tsx"],
        }
    )

    assert preview["kind"] == "integration_review_manifest_conflict_preview"
    assert preview["ok"] is True
    assert preview["status"] == "ready"
    assert preview["clear_candidates"] == ["integration_review_adoption_manifest_preview"]
    assert preview["items"][0]["conflict_level"] == "none"
    assert preview["next_actions"] == ["share_review_manifest_conflict_preview_with_mainline"]


def test_active_scope_overlap_needs_review() -> None:
    preview = build_integration_review_manifest_conflict_preview(
        {
            "adoption_manifest_preview": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "manifest_key": "manifest-a",
                        "status": "ready",
                        "include_paths": ["backend/app/core/candidate_a.py"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "active_scopes": {"mainline": {"paths": ["backend/app/core"]}},
        }
    )

    assert preview["status"] == "needs_review"
    assert preview["review_candidates"] == ["candidate-a"]
    assert preview["items"][0]["overlaps"] == ["backend/app/core/candidate_a.py::backend/app/core"]
    assert "active scope overlap" in preview["items"][0]["reasons"]
    assert "review_manifest_scope_overlap" in preview["next_actions"]


def test_forbidden_scope_overlap_blocks_preview() -> None:
    preview = build_integration_review_manifest_conflict_preview(
        {
            "adoption_manifest_preview": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "manifest_key": "manifest-a",
                        "status": "ready",
                        "include_paths": ["backend/app/api/router.py"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "forbidden_paths": ["backend/app/api"],
        }
    )

    assert preview["status"] == "blocked"
    assert preview["blocked_candidates"] == ["candidate-a"]
    assert preview["items"][0]["conflict_level"] == "blocked"
    assert "forbidden scope overlap" in preview["items"][0]["reasons"]
    assert preview["next_actions"] == [
        "resolve_manifest_conflict_blockers",
        "remove_forbidden_manifest_paths",
        "rebuild_integration_review_manifest_conflict_preview",
    ]


def test_empty_manifest_conflict_preview_requests_inputs() -> None:
    preview = build_integration_review_manifest_conflict_preview({})

    assert preview["ok"] is False
    assert preview["status"] == "empty"
    assert preview["next_actions"] == ["provide_review_manifest_conflict_preview_inputs"]


def test_explicit_conflict_payload_can_seed_preview() -> None:
    preview = build_integration_review_manifest_conflict_preview(
        {
            "conflicts": [
                {
                    "candidate_id": "candidate-a",
                    "conflict_key": "conflict-a",
                    "candidate_paths": ["module.py"],
                    "handoff_refs": ["handoff"],
                    "status": "ready",
                }
            ]
        }
    )

    assert preview["status"] == "ready"
    assert preview["items"][0]["conflict_key"] == "conflict-a"


def test_summarize_review_manifest_conflict_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Conflict:
        candidate_id: str
        conflict_key: str
        candidate_paths: tuple[str, ...]
        handoff_refs: tuple[str, ...]
        status: str

    item = summarize_review_manifest_conflict_item(
        Conflict(
            candidate_id="candidate-a",
            conflict_key="conflict-a",
            candidate_paths=("module.py",),
            handoff_refs=("handoff",),
            status="ready",
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.conflict_level == "none"
    assert item.status == "ready"
