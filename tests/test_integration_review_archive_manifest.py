from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_archive_manifest import (
    build_integration_review_archive_manifest,
    summarize_review_archive_entry,
)


def test_review_archive_manifest_marks_complete_refs_ready() -> None:
    manifest = build_integration_review_archive_manifest(
        {
            "manifest_id": "archive-1",
            "review_minutes": {
                "decisions": [
                    {
                        "candidate_id": "integration_review_minutes",
                        "owner": "mainline",
                        "reviewer": "architecture",
                        "status": "ready",
                        "risk_level": "low",
                        "evidence_refs": ["24 passed"],
                    }
                ]
            },
            "entries": [
                {
                    "candidate_id": "integration_review_minutes",
                    "artifact_refs": ["backend/app/core/integration_review_minutes.py"],
                }
            ],
            "handoff_refs": {
                "integration_review_minutes": {
                    "path": "docs/original-kernel-secondary-handoff.md#integration-review-minutes",
                }
            },
        }
    )

    assert manifest["kind"] == "integration_review_archive_manifest"
    assert manifest["ok"] is True
    assert manifest["status"] == "ready"
    assert manifest["summary"]["entry_count"] == 1
    assert manifest["entries"][0]["archive_key"] == "review/integration-review-minutes"
    assert manifest["ready_candidates"] == ["integration_review_minutes"]
    assert manifest["next_actions"] == ["share_review_archive_manifest_with_mainline"]


def test_missing_refs_keep_archive_manifest_in_review() -> None:
    manifest = build_integration_review_archive_manifest(
        {
            "review_minutes": {
                "decisions": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "ready",
                        "owner": "mainline",
                        "reviewer": "review",
                    }
                ]
            }
        }
    )

    assert manifest["status"] == "needs_review"
    entry = manifest["entries"][0]
    assert entry["status"] == "needs_review"
    assert entry["reasons"] == [
        "archive artifact refs missing",
        "archive evidence refs missing",
        "archive handoff refs missing",
    ]
    assert manifest["missing_refs"] == {
        "candidate-a": ["artifact_refs", "evidence_refs", "handoff_refs"]
    }
    assert manifest["next_actions"] == [
        "complete_review_archive_manifest",
        "attach_archive_artifact_refs",
        "attach_archive_evidence_refs",
        "attach_archive_handoff_refs",
        "rebuild_integration_review_archive_manifest",
    ]


def test_blocked_minutes_blocks_archive_manifest() -> None:
    manifest = build_integration_review_archive_manifest(
        {
            "review_minutes": {
                "decisions": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "blocked",
                        "risk_level": "high",
                        "evidence_refs": ["blocked signal"],
                    }
                ]
            },
            "entries": [
                {
                    "candidate_id": "candidate-a",
                    "artifact_refs": ["module.py"],
                    "handoff_refs": ["handoff"],
                }
            ],
        }
    )

    assert manifest["status"] == "blocked"
    assert manifest["blocked_candidates"] == ["candidate-a"]
    entry = manifest["entries"][0]
    assert entry["risk_level"] == "high"
    assert "archive source blocked" in entry["reasons"]
    assert manifest["next_actions"] == [
        "resolve_review_archive_blockers",
        "rebuild_integration_review_archive_manifest",
    ]


def test_validation_and_handoff_refs_are_merged() -> None:
    manifest = build_integration_review_archive_manifest(
        {
            "review_minutes": {
                "decisions": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "ready",
                        "owner": "mainline",
                        "reviewer": "architecture",
                    }
                ]
            },
            "review_calendar": {
                "slots": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "ready",
                        "evidence_refs": ["calendar evidence"],
                    }
                ]
            },
            "entries": {"candidate-a": {"artifact_refs": ["minutes payload"]}},
            "validation_evidence": [
                {
                    "candidate_id": "candidate-a",
                    "refs": ["tests passed"],
                }
            ],
            "handoff_refs": [
                {
                    "candidate_id": "candidate-a",
                    "refs": ["handoff entry"],
                }
            ],
        }
    )

    assert manifest["status"] == "ready"
    entry = manifest["entries"][0]
    assert entry["evidence_refs"] == ["calendar evidence", "tests passed"]
    assert entry["handoff_refs"] == ["handoff entry"]


def test_empty_archive_manifest_requests_inputs() -> None:
    manifest = build_integration_review_archive_manifest({})

    assert manifest["ok"] is False
    assert manifest["status"] == "empty"
    assert manifest["next_actions"] == ["provide_review_archive_manifest_inputs"]


def test_summarize_review_archive_entry_accepts_dataclass_like_payload() -> None:
    @dataclass
    class ArchiveItem:
        candidate_id: str
        artifact_refs: list[str]
        evidence_refs: list[str]
        handoff_refs: list[str]
        status: str

    entry = summarize_review_archive_entry(
        ArchiveItem("candidate-a", ["module.py"], ["tests"], ["handoff"], "ready")
    )

    assert entry.candidate_id == "candidate-a"
    assert entry.archive_key == "review/candidate-a"
    assert entry.status == "needs_review"
    assert "review minutes missing" in entry.reasons
