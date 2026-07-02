from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_secondary_index import (
    build_integration_secondary_index,
    summarize_secondary_candidate,
)


def test_secondary_index_marks_complete_candidate_ready() -> None:
    index = build_integration_secondary_index(
        {
            "index_id": "secondary-1",
            "candidates": [
                {
                    "candidate_id": "integration_sunset_review",
                    "source_kind": "codex_gap_secondary",
                    "integration_status": "secondary_integration_candidate",
                    "owner": "mainline",
                    "files": ["backend/app/core/integration_sunset_review.py"],
                    "tests": ["tests/test_integration_sunset_review.py"],
                    "validation_commands": ["python -m pytest tests/test_integration_sunset_review.py -q"],
                    "validation_results": ["7 passed"],
                    "validation_statuses": ["passed"],
                    "handoff_refs": ["docs/original-kernel-secondary-handoff.md#integration-sunset-review"],
                    "tags": ["governance"],
                }
            ],
        }
    )

    assert index["kind"] == "integration_secondary_index"
    assert index["ok"] is True
    assert index["status"] == "ready"
    assert index["summary"]["ready_count"] == 1
    assert index["by_status"]["ready"] == ["integration_sunset_review"]
    assert index["by_owner"]["mainline"] == ["integration_sunset_review"]
    assert index["next_actions"] == ["share_secondary_index_with_mainline_for_review"]


def test_secondary_index_flags_missing_validation_and_handoff_refs() -> None:
    index = build_integration_secondary_index(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "integration_status": "secondary_integration_candidate",
                    "files": ["backend/app/core/candidate_a.py"],
                    "tests": ["tests/test_candidate_a.py"],
                }
            ]
        }
    )

    assert index["status"] == "needs_review"
    assert index["issues"][0]["code"] == "secondary_index_validation_commands_missing"
    assert index["issues"][1]["code"] == "secondary_index_validation_results_missing"
    assert index["issues"][2]["code"] == "secondary_index_handoff_refs_missing"
    assert index["next_actions"] == [
        "attach_secondary_candidate_validation_evidence",
        "attach_secondary_handoff_references",
        "rebuild_integration_secondary_index",
    ]


def test_secondary_index_blocks_non_detached_or_failed_candidate() -> None:
    index = build_integration_secondary_index(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "integration_status": "adopted",
                    "files": ["backend/app/core/candidate_a.py"],
                    "tests": ["tests/test_candidate_a.py"],
                    "validation_commands": ["python -m pytest tests/test_candidate_a.py -q"],
                    "validation_results": ["1 failed"],
                    "validation_statuses": ["failed"],
                    "handoff_refs": ["handoff#candidate-a"],
                }
            ]
        }
    )

    assert index["status"] == "blocked"
    assert index["entries"][0]["status"] == "blocked"
    assert index["issues"][0]["code"] == "secondary_index_status_not_detached"
    assert index["issues"][1]["code"] == "secondary_index_validation_blocked"
    assert index["next_actions"] == [
        "resolve_blocked_secondary_index_entries",
        "attach_passing_secondary_validation_status",
        "rebuild_integration_secondary_index",
    ]


def test_secondary_index_merges_traceability_validations_and_handoff_rows() -> None:
    index = build_integration_secondary_index(
        {
            "traceability_index": {
                "records": [
                    {
                        "candidate_id": "candidate-a",
                        "owner": "mainline",
                        "files": ["backend/app/core/candidate_a.py"],
                        "tests": ["tests/test_candidate_a.py"],
                        "validation_commands": ["python -m pytest tests/test_candidate_a.py -q"],
                    }
                ]
            },
            "validations": [
                {
                    "candidate_id": "candidate-a",
                    "result": "1 passed",
                    "status": "passed",
                }
            ],
            "handoff_refs": [
                {
                    "candidate_id": "candidate-a",
                    "ref": "docs/original-kernel-secondary-handoff.md#candidate-a",
                }
            ],
        }
    )

    assert index["status"] == "ready"
    entry = index["entries"][0]
    assert entry["candidate_id"] == "candidate-a"
    assert entry["owner"] == "mainline"
    assert entry["validation_results"] == ["1 passed"]
    assert entry["handoff_refs"] == ["docs/original-kernel-secondary-handoff.md#candidate-a"]


def test_empty_secondary_index_requests_entries() -> None:
    index = build_integration_secondary_index({})

    assert index["ok"] is False
    assert index["status"] == "empty"
    assert index["next_actions"] == ["provide_secondary_candidate_entries"]


def test_summarize_secondary_candidate_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Candidate:
        candidate_id: str
        integration_status: str
        files: list[str]
        tests: list[str]
        validation_commands: list[str]
        validation_results: list[str]
        validation_statuses: list[str]
        handoff_refs: list[str]

    entry = summarize_secondary_candidate(
        Candidate(
            "candidate-a",
            "secondary_integration_candidate",
            ["backend/app/core/candidate_a.py"],
            ["tests/test_candidate_a.py"],
            ["python -m pytest tests/test_candidate_a.py -q"],
            ["1 passed"],
            ["passed"],
            ["handoff#candidate-a"],
        )
    )

    assert entry.candidate_id == "candidate-a"
    assert entry.status == "ready"
    assert entry.reasons == ("secondary index entry complete",)
