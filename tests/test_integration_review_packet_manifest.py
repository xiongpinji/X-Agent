from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_packet_manifest import (
    build_integration_review_packet_manifest,
    summarize_review_packet_manifest_entry,
)


def test_review_packet_manifest_marks_ready_candidate_ready() -> None:
    manifest = build_integration_review_packet_manifest(
        {
            "manifest_id": "manifest-1",
            "review_readiness_gate": {"verdict": "ready_for_review", "status": "ready", "ok": True},
            "candidates": [
                {
                    "candidate_id": "integration_review_readiness_gate",
                    "stage_label": "secondary_integration_candidate",
                    "review_status": "ready",
                    "owner": "mainline",
                    "files": ["backend/app/core/integration_review_readiness_gate.py"],
                    "tests": ["tests/test_integration_review_readiness_gate.py"],
                    "evidence_refs": ["6 passed"],
                    "handoff_refs": ["handoff#review-readiness-gate"],
                }
            ],
        }
    )

    assert manifest["kind"] == "integration_review_packet_manifest"
    assert manifest["ok"] is True
    assert manifest["status"] == "ready"
    assert manifest["summary"]["ready_count"] == 1
    assert manifest["stage_buckets"] == {"secondary_integration_candidate": ["integration_review_readiness_gate"]}
    assert manifest["next_actions"] == ["share_review_packet_manifest_with_mainline"]


def test_blocked_risk_entry_blocks_manifest_candidate() -> None:
    manifest = build_integration_review_packet_manifest(
        {
            "review_readiness_gate": {"verdict": "blocked"},
            "secondary_index": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "files": ["backend/app/core/candidate_a.py"],
                        "tests": ["tests/test_candidate_a.py"],
                        "validation_results": ["1 failed"],
                        "handoff_refs": ["handoff#candidate-a"],
                    }
                ]
            },
            "conflict_risk_register": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "review_status": "blocked",
                        "reasons": ["candidate touches forbidden path"],
                    }
                ]
            },
        }
    )

    assert manifest["status"] == "blocked"
    entry = manifest["entries"][0]
    assert entry["review_status"] == "blocked"
    assert "risk register blocked candidate" in entry["reasons"]
    assert manifest["next_actions"] == [
        "resolve_blocked_manifest_entries",
        "rebuild_integration_review_packet_manifest",
    ]


def test_missing_evidence_and_handoff_need_review() -> None:
    manifest = build_integration_review_packet_manifest(
        {
            "review_readiness_gate": {"verdict": "ready_for_review"},
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "files": ["backend/app/core/candidate_a.py"],
                    "tests": ["tests/test_candidate_a.py"],
                    "review_status": "ready",
                }
            ],
        }
    )

    assert manifest["status"] == "needs_review"
    entry = manifest["entries"][0]
    assert entry["review_status"] == "needs_review"
    assert entry["reasons"] == ["evidence references missing", "handoff references missing"]
    assert manifest["next_actions"] == [
        "complete_review_packet_manifest_evidence",
        "attach_manifest_handoff_refs",
        "rebuild_integration_review_packet_manifest",
    ]


def test_manifest_merges_secondary_index_risk_and_traceability_payloads() -> None:
    manifest = build_integration_review_packet_manifest(
        {
            "review_readiness_gate": {"verdict": "ready_for_review"},
            "secondary_index": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "integration_status": "secondary_integration_candidate",
                        "owner": "mainline",
                        "files": ["backend/app/core/candidate_a.py"],
                        "tests": ["tests/test_candidate_a.py"],
                        "validation_results": ["1 passed"],
                        "handoff_refs": ["handoff#candidate-a"],
                    }
                ]
            },
            "conflict_risk_register": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "review_status": "ready",
                        "reasons": ["conflict risk low"],
                    }
                ]
            },
            "traceability_index": {
                "records": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "ready",
                        "evidence_refs": ["traceability ready"],
                        "handoff_refs": ["handoff#candidate-a"],
                    }
                ]
            },
        }
    )

    assert manifest["status"] == "ready"
    entry = manifest["entries"][0]
    assert entry["candidate_id"] == "candidate-a"
    assert entry["owner"] == "mainline"
    assert entry["evidence_refs"] == ["traceability ready", "1 passed"]
    assert entry["risk_refs"] == ["conflict risk low"]


def test_empty_manifest_requests_candidates() -> None:
    manifest = build_integration_review_packet_manifest({})

    assert manifest["ok"] is False
    assert manifest["status"] == "empty"
    assert manifest["next_actions"] == ["provide_review_packet_manifest_candidates"]


def test_summarize_manifest_entry_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Entry:
        candidate_id: str
        stage_label: str
        review_status: str
        owner: str
        files: list[str]
        tests: list[str]
        evidence_refs: list[str]
        handoff_refs: list[str]

    entry = summarize_review_packet_manifest_entry(
        Entry(
            "candidate-a",
            "secondary_integration_candidate",
            "ready",
            "mainline",
            ["backend/app/core/candidate_a.py"],
            ["tests/test_candidate_a.py"],
            ["1 passed"],
            ["handoff#candidate-a"],
        )
    )

    assert entry.candidate_id == "candidate-a"
    assert entry.review_status == "ready"
    assert entry.reasons == ("manifest entry ready",)
