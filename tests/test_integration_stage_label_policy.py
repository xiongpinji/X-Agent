from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_stage_label_policy import (
    build_integration_stage_label_policy,
    normalize_stage_label,
)


def test_stage_label_policy_marks_canonical_label_ready() -> None:
    policy = build_integration_stage_label_policy(
        {
            "policy_id": "stage-1",
            "candidates": [
                {
                    "candidate_id": "integration_review_packet_manifest",
                    "stage_label": "secondary_integration_candidate",
                    "owner": "mainline",
                }
            ],
        }
    )

    assert policy["kind"] == "integration_stage_label_policy"
    assert policy["ok"] is True
    assert policy["status"] == "ready"
    assert policy["summary"]["ready_count"] == 1
    assert policy["stage_buckets"] == {
        "secondary_integration_candidate": ["integration_review_packet_manifest"]
    }
    assert policy["next_actions"] == ["share_stage_label_policy_with_mainline"]


def test_stage_alias_needs_review_before_manifest_write() -> None:
    policy = build_integration_stage_label_policy(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "stage": "ready for review",
                }
            ]
        }
    )

    assert policy["status"] == "needs_review"
    decision = policy["decisions"][0]
    assert decision["input_label"] == "ready_for_review"
    assert decision["normalized_label"] == "secondary_review_ready"
    assert decision["status"] == "needs_review"
    assert decision["next_actions"] == ["confirm_stage_label_alias"]
    assert policy["next_actions"] == [
        "review_stage_label_aliases",
        "confirm_stage_label_alias",
        "rebuild_integration_stage_label_policy",
    ]


def test_unknown_or_blocking_stage_blocks_policy() -> None:
    policy = build_integration_stage_label_policy(
        {
            "candidates": [
                {"candidate_id": "candidate-a", "stage_label": "production"},
                {"candidate_id": "candidate-b", "stage_label": "blocked"},
            ]
        }
    )

    assert policy["status"] == "blocked"
    assert policy["summary"]["blocked_count"] == 2
    assert policy["issues"][0]["code"] == "stage_label_blocked"
    assert "stage label unknown" in policy["decisions"][0]["reasons"]
    assert "stage label blocks review" in policy["decisions"][1]["reasons"]
    assert policy["next_actions"] == [
        "resolve_blocked_stage_labels",
        "replace_unknown_stage_label",
        "confirm_stage_label_alias",
        "resolve_blocking_stage_label",
        "rebuild_integration_stage_label_policy",
    ]


def test_stage_policy_reads_review_packet_manifest_entries() -> None:
    policy = build_integration_stage_label_policy(
        {
            "review_packet_manifest": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "stage_label": "mainline_review_candidate",
                    }
                ]
            }
        }
    )

    assert policy["status"] == "ready"
    assert policy["decisions"][0]["normalized_label"] == "mainline_review_candidate"


def test_empty_stage_policy_requests_candidates() -> None:
    policy = build_integration_stage_label_policy({})

    assert policy["ok"] is False
    assert policy["status"] == "empty"
    assert policy["next_actions"] == ["provide_stage_label_candidates"]


def test_normalize_stage_label_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Candidate:
        candidate_id: str
        stage_label: str
        owner: str

    decision = normalize_stage_label(Candidate("candidate-a", "review", "mainline"))

    assert decision.candidate_id == "candidate-a"
    assert decision.input_label == "review"
    assert decision.normalized_label == "secondary_needs_review"
    assert decision.status == "needs_review"
