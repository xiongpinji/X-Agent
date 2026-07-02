from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_evidence_index import (
    build_integration_review_evidence_index,
    summarize_review_evidence_record,
)


def test_review_evidence_index_collects_archive_retention_and_minutes_refs() -> None:
    index = build_integration_review_evidence_index(
        {
            "index_id": "evidence-1",
            "review_archive_manifest": {
                "entries": [
                    {
                        "candidate_id": "integration_review_retention_policy",
                        "status": "ready",
                        "owner": "mainline",
                        "archive_key": "review/integration-review-retention-policy",
                        "artifact_refs": ["backend/app/core/integration_review_retention_policy.py"],
                        "evidence_refs": ["6 passed"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "review_retention_policy": {
                "decisions": [
                    {
                        "candidate_id": "integration_review_retention_policy",
                        "status": "ready",
                        "owner": "mainline",
                        "archive_refs": ["review/integration-review-retention-policy"],
                        "evidence_refs": ["25 passed"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "review_minutes": {
                "decisions": [
                    {
                        "candidate_id": "integration_review_retention_policy",
                        "status": "ready",
                        "owner": "mainline",
                        "evidence_refs": ["minutes evidence"],
                    }
                ]
            },
        }
    )

    assert index["kind"] == "integration_review_evidence_index"
    assert index["ok"] is True
    assert index["status"] == "ready"
    assert index["summary"]["candidate_count"] == 1
    assert "integration_review_retention_policy" in index["by_candidate"]
    assert "integration_review_archive_manifest" in index["by_source"]
    assert "artifact" in index["by_ref_type"]
    assert index["next_actions"] == ["share_review_evidence_index_with_mainline"]


def test_explicit_missing_ref_needs_review() -> None:
    index = build_integration_review_evidence_index(
        {
            "records": [
                {
                    "candidate_id": "candidate-a",
                    "source": "manual",
                    "ref_type": "evidence",
                }
            ]
        }
    )

    assert index["status"] == "needs_review"
    assert index["missing_refs"] == ["candidate-a"]
    assert index["records"][0]["reasons"] == ["evidence ref missing"]
    assert index["next_actions"] == [
        "attach_missing_review_evidence_refs",
        "review_evidence_index_warnings",
        "rebuild_integration_review_evidence_index",
    ]


def test_blocked_retention_policy_ref_blocks_index() -> None:
    index = build_integration_review_evidence_index(
        {
            "review_retention_policy": {
                "decisions": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "blocked",
                        "archive_refs": ["review/candidate-a"],
                    }
                ]
            }
        }
    )

    assert index["status"] == "blocked"
    assert index["blocked_candidates"] == ["candidate-a"]
    assert index["records"][0]["status"] == "blocked"
    assert "evidence source blocked" in index["records"][0]["reasons"]
    assert index["next_actions"] == [
        "resolve_review_evidence_index_blockers",
        "rebuild_integration_review_evidence_index",
    ]


def test_validation_and_handoff_refs_are_indexed() -> None:
    index = build_integration_review_evidence_index(
        {
            "validation_evidence": [
                {
                    "candidate_id": "candidate-a",
                    "refs": ["tests passed"],
                }
            ],
            "handoff_refs": {
                "candidate-a": {
                    "path": "docs/original-kernel-secondary-handoff.md#candidate-a",
                }
            },
        }
    )

    assert index["status"] == "ready"
    assert index["by_ref_type"] == {
        "validation": ["tests passed"],
        "handoff": ["docs/original-kernel-secondary-handoff.md#candidate-a"],
    }


def test_empty_review_evidence_index_requests_inputs() -> None:
    index = build_integration_review_evidence_index({})

    assert index["ok"] is False
    assert index["status"] == "empty"
    assert index["next_actions"] == ["provide_review_evidence_index_inputs"]


def test_summarize_review_evidence_record_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Evidence:
        candidate_id: str
        ref: str
        source: str
        ref_type: str
        status: str

    record = summarize_review_evidence_record(
        Evidence("candidate-a", "handoff", "manual", "handoff", "ready")
    )

    assert record.candidate_id == "candidate-a"
    assert record.ref == "handoff"
    assert record.source == "manual"
    assert record.status == "ready"
