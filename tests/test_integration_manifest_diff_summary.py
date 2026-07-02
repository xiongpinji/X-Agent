from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_manifest_diff_summary import (
    build_integration_manifest_diff_summary,
    summarize_manifest_diff_entry,
)


def test_manifest_diff_marks_unchanged_payload_ready() -> None:
    manifest = {
        "entries": [
            {
                "candidate_id": "candidate-a",
                "stage_label": "secondary_integration_candidate",
                "review_status": "ready",
                "owner": "mainline",
                "files": ["backend/app/core/candidate_a.py"],
                "tests": ["tests/test_candidate_a.py"],
                "evidence_refs": ["1 passed"],
                "handoff_refs": ["handoff#candidate-a"],
            }
        ]
    }

    diff = build_integration_manifest_diff_summary(
        {
            "diff_id": "diff-1",
            "previous_manifest": manifest,
            "proposed_manifest": manifest,
        }
    )

    assert diff["kind"] == "integration_manifest_diff_summary"
    assert diff["ok"] is True
    assert diff["status"] == "ready"
    assert diff["summary"]["unchanged_count"] == 1
    assert diff["entries"][0]["change_type"] == "unchanged"
    assert diff["next_actions"] == ["share_manifest_diff_summary_with_mainline"]


def test_manifest_diff_tracks_added_removed_and_changed_candidates() -> None:
    diff = build_integration_manifest_diff_summary(
        {
            "previous_manifest": {
                "entries": [
                    {"candidate_id": "removed", "stage_label": "secondary_integration_candidate"},
                    {"candidate_id": "changed", "stage_label": "secondary_integration_candidate", "owner": "a"},
                ]
            },
            "proposed_manifest": {
                "entries": [
                    {"candidate_id": "added", "stage_label": "secondary_integration_candidate"},
                    {"candidate_id": "changed", "stage_label": "secondary_review_ready", "owner": "b"},
                ]
            },
        }
    )

    assert diff["status"] == "ready"
    assert diff["added_candidates"] == ["added"]
    assert diff["removed_candidates"] == ["removed"]
    assert diff["changed_candidates"] == ["changed"]
    changed = next(item for item in diff["entries"] if item["candidate_id"] == "changed")
    assert changed["changed_fields"] == ["stage_label", "owner"]
    assert diff["next_actions"] == [
        "review_removed_manifest_candidates",
        "review_changed_manifest_candidates",
        "rebuild_integration_manifest_diff_summary",
    ]


def test_risk_increase_or_readiness_regression_needs_review() -> None:
    diff = build_integration_manifest_diff_summary(
        {
            "previous_manifest": {
                "entries": [
                    {"candidate_id": "candidate-a", "review_status": "ready", "risk_refs": []},
                ]
            },
            "proposed_manifest": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "review_status": "blocked",
                        "risk_refs": ["forbidden path"],
                    },
                ]
            },
        }
    )

    assert diff["status"] == "needs_review"
    entry = diff["entries"][0]
    assert entry["risk_change"] == "increased"
    assert entry["readiness_change"] == "regressed"
    assert diff["next_actions"] == [
        "review_manifest_risk_increases",
        "review_manifest_readiness_regressions",
        "review_changed_manifest_candidates",
        "rebuild_integration_manifest_diff_summary",
    ]


def test_readiness_improvement_and_risk_reduction_are_ready() -> None:
    diff = build_integration_manifest_diff_summary(
        {
            "previous_manifest": {
                "entries": [
                    {"candidate_id": "candidate-a", "review_status": "blocked", "risk_refs": ["blocked"]},
                ]
            },
            "proposed_manifest": {
                "entries": [
                    {"candidate_id": "candidate-a", "review_status": "ready", "risk_refs": []},
                ]
            },
        }
    )

    assert diff["status"] == "ready"
    entry = diff["entries"][0]
    assert entry["risk_change"] == "reduced"
    assert entry["readiness_change"] == "improved"


def test_empty_manifest_diff_requests_inputs() -> None:
    diff = build_integration_manifest_diff_summary({})

    assert diff["ok"] is False
    assert diff["status"] == "empty"
    assert diff["next_actions"] == ["provide_previous_and_proposed_manifests"]


def test_summarize_manifest_diff_entry_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Entry:
        candidate_id: str
        change_type: str
        previous_stage: str
        proposed_stage: str
        changed_fields: list[str]
        risk_change: str
        readiness_change: str

    entry = summarize_manifest_diff_entry(
        Entry(
            "candidate-a",
            "changed",
            "secondary_integration_candidate",
            "secondary_review_ready",
            ["stage_label"],
            "unchanged",
            "improved",
        )
    )

    assert entry.candidate_id == "candidate-a"
    assert entry.change_type == "changed"
    assert entry.changed_fields == ("stage_label",)
    assert entry.readiness_change == "improved"
