from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_adoption_manifest_preview import (
    build_integration_review_adoption_manifest_preview,
    summarize_review_adoption_manifest_entry,
)


def test_review_adoption_manifest_preview_builds_ready_entry() -> None:
    preview = build_integration_review_adoption_manifest_preview(
        {
            "preview_id": "preview-1",
            "adoption_candidate_pack": {
                "packs": [
                    {
                        "candidate_id": "integration_review_adoption_candidate_pack",
                        "pack_key": "pack-a",
                        "status": "ready",
                        "adoption_state": "adoption_ready",
                        "files": ["backend/app/core/integration_review_adoption_candidate_pack.py"],
                        "tests": ["tests/test_integration_review_adoption_candidate_pack.py"],
                        "evidence_refs": ["6 passed"],
                        "handoff_refs": ["handoff"],
                        "owner": "mainline",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
        }
    )

    assert preview["kind"] == "integration_review_adoption_manifest_preview"
    assert preview["ok"] is True
    assert preview["status"] == "ready"
    assert preview["summary"]["entry_count"] == 1
    assert preview["entries"][0]["stage_label"] == "secondary_integration_candidate"
    assert preview["include_paths"] == ["backend/app/core/integration_review_adoption_candidate_pack.py"]
    assert preview["test_paths"] == ["tests/test_integration_review_adoption_candidate_pack.py"]
    assert preview["render_hints"]["write_manifest"] is False
    assert preview["next_actions"] == ["share_review_adoption_manifest_preview_with_mainline"]


def test_missing_paths_and_handoff_need_review() -> None:
    preview = build_integration_review_adoption_manifest_preview(
        {
            "adoption_candidate_pack": {
                "packs": [
                    {
                        "candidate_id": "candidate-a",
                        "pack_key": "pack-a",
                        "status": "ready",
                        "evidence_refs": ["manual evidence"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            }
        }
    )

    assert preview["status"] == "needs_review"
    assert preview["review_candidates"] == ["candidate-a"]
    assert "include paths missing" in preview["entries"][0]["reasons"]
    assert "test paths missing" in preview["entries"][0]["reasons"]
    assert "handoff refs missing" in preview["entries"][0]["reasons"]
    assert "attach_manifest_include_paths" in preview["next_actions"]


def test_blocked_candidate_pack_blocks_manifest_preview() -> None:
    preview = build_integration_review_adoption_manifest_preview(
        {
            "adoption_candidate_pack": {
                "packs": [
                    {
                        "candidate_id": "candidate-a",
                        "pack_key": "pack-a",
                        "status": "blocked",
                        "files": ["module.py"],
                        "tests": ["test_module.py"],
                        "evidence_refs": ["blocked evidence"],
                        "handoff_refs": ["handoff"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                        "blockers": ["validation timeout"],
                    }
                ]
            }
        }
    )

    assert preview["status"] == "blocked"
    assert preview["blocked_candidates"] == ["candidate-a"]
    assert preview["entries"][0]["status"] == "blocked"
    assert "manifest source blocked" in preview["entries"][0]["reasons"]
    assert preview["next_actions"] == [
        "resolve_review_adoption_manifest_blockers",
        "attach_manifest_evidence",
        "rebuild_integration_review_adoption_manifest_preview",
    ]


def test_explicit_entry_payload_can_seed_manifest_preview() -> None:
    preview = build_integration_review_adoption_manifest_preview(
        {
            "entries": [
                {
                    "candidate_id": "candidate-a",
                    "manifest_key": "manifest-a",
                    "status": "ready",
                    "stage_label": "secondary_integration_candidate",
                    "include_paths": ["module.py"],
                    "test_paths": ["test_module.py"],
                    "evidence_refs": ["manual evidence"],
                    "handoff_refs": ["handoff"],
                    "owner": "owner-a",
                    "reviewer": "reviewer-a",
                }
            ]
        }
    )

    assert preview["status"] == "ready"
    assert preview["entries"][0]["manifest_key"] == "manifest-a"
    assert preview["by_stage_label"] == {"secondary_integration_candidate": ["manifest-a"]}


def test_empty_review_adoption_manifest_preview_requests_inputs() -> None:
    preview = build_integration_review_adoption_manifest_preview({})

    assert preview["ok"] is False
    assert preview["status"] == "empty"
    assert preview["next_actions"] == ["provide_review_adoption_manifest_preview_inputs"]


def test_summarize_review_adoption_manifest_entry_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Entry:
        candidate_id: str
        manifest_key: str
        status: str
        include_paths: tuple[str, ...]
        test_paths: tuple[str, ...]
        evidence_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]
        owner: str
        reviewer: str

    entry = summarize_review_adoption_manifest_entry(
        Entry(
            candidate_id="candidate-a",
            manifest_key="manifest-a",
            status="ready",
            include_paths=("module.py",),
            test_paths=("test_module.py",),
            evidence_refs=("evidence",),
            handoff_refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
        )
    )

    assert entry.candidate_id == "candidate-a"
    assert entry.manifest_key == "manifest-a"
    assert entry.status == "ready"
