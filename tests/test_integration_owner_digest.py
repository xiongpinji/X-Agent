from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_owner_digest import (
    build_integration_owner_digest,
    summarize_owner_digest,
)


def test_owner_digest_groups_ready_followups_by_owner() -> None:
    digest = build_integration_owner_digest(
        {
            "digest_id": "owners-1",
            "followups": [
                {
                    "followup_id": "f1",
                    "owner": "mainline",
                    "action": "review_traceability_index",
                    "source_kind": "integration_traceability_index",
                    "candidate_id": "traceability",
                    "severity": "medium",
                    "priority": 60,
                    "evidence_refs": ["handoff", "tests passed"],
                },
                {
                    "followup_id": "f2",
                    "owner": "mainline",
                    "action": "review_governance_summary",
                    "source_kind": "integration_governance_summary",
                    "candidate_id": "governance",
                    "severity": "low",
                    "priority": 30,
                    "evidence_refs": ["handoff"],
                },
            ],
        }
    )

    assert digest["kind"] == "integration_owner_digest"
    assert digest["ok"] is True
    assert digest["status"] == "ready"
    assert digest["summary"]["owner_count"] == 1
    assert digest["owners"][0]["owner"] == "mainline"
    assert digest["owners"][0]["followup_ids"] == ["f1", "f2"]
    assert digest["owners"][0]["candidate_ids"] == ["traceability", "governance"]
    assert digest["next_actions"] == ["review_owner_digest_with_mainline"]


def test_blocked_followup_blocks_owner_digest() -> None:
    digest = build_integration_owner_digest(
        {
            "followup_queue": {
                "followups": [
                    {
                        "followup_id": "blocked",
                        "owner": "mainline",
                        "action": "resolve_dependency_cycle",
                        "source_kind": "candidate_dependency_map",
                        "candidate_id": "dependency-map",
                        "severity": "high",
                        "status": "blocked",
                        "priority": 100,
                        "evidence_refs": ["cycle"],
                    }
                ]
            }
        }
    )

    assert digest["status"] == "blocked"
    assert digest["blocked_owners"] == ["mainline"]
    assert digest["owners"][0]["blocked_count"] == 1
    assert digest["owners"][0]["high_priority_count"] == 1
    assert digest["issues"][0]["code"] == "owner_digest_blocked_followups"
    assert digest["next_actions"] == ["resolve_owner_blocked_followups", "rebuild_integration_owner_digest"]


def test_unassigned_and_missing_evidence_needs_review() -> None:
    digest = build_integration_owner_digest(
        {
            "followups": [
                {
                    "followup_id": "f1",
                    "action": "attach_handoff_references",
                    "source_kind": "integration_traceability_index",
                    "candidate_id": "traceability",
                    "severity": "medium",
                }
            ]
        }
    )

    assert digest["status"] == "needs_review"
    assert digest["review_owners"] == ["unassigned"]
    assert digest["issues"][0]["code"] == "owner_digest_owner_missing"
    assert digest["issues"][1]["code"] == "owner_digest_missing_evidence"
    assert digest["next_actions"] == [
        "assign_missing_digest_owners",
        "attach_owner_followup_evidence",
        "rebuild_integration_owner_digest",
    ]


def test_accepts_dataclass_like_followups() -> None:
    @dataclass
    class Followup:
        followup_id: str
        owner: str
        action: str
        source_kind: str
        candidate_id: str
        priority: int
        evidence_refs: list[str]

    digest = build_integration_owner_digest(
        {
            "items": [
                Followup(
                    "f1",
                    "release",
                    "prepare_release_evidence",
                    "release_evidence_pack",
                    "release-evidence-pack",
                    80,
                    ["release evidence"],
                )
            ]
        }
    )

    assert digest["status"] == "ready"
    assert digest["owners"][0]["owner"] == "release"
    assert digest["owners"][0]["high_priority_count"] == 1


def test_summarize_single_owner_digest() -> None:
    digest = summarize_owner_digest(
        "mainline",
        [
            {
                "followup_id": "f1",
                "action": "review_packet",
                "source_kind": "integration_review_packet",
                "candidate_id": "packet",
                "evidence_refs": ["handoff"],
            }
        ],
    )

    assert digest.status == "ready"
    assert digest.actions == ("review_packet",)
    assert digest.reasons == ("owner digest ready",)


def test_empty_owner_digest_requests_inputs() -> None:
    digest = build_integration_owner_digest({})

    assert digest["status"] == "empty"
    assert digest["ok"] is False
    assert digest["next_actions"] == ["provide_owner_digest_inputs"]
