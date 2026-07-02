from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_owner_handoff import (
    build_integration_review_manifest_adoption_owner_handoff,
    summarize_review_manifest_adoption_owner_handoff_item,
)


def test_owner_handoff_marks_assigned_final_packet_ready() -> None:
    handoff = build_integration_review_manifest_adoption_owner_handoff(
        {
            "manifest_adoption_final_packet": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "packet_key": "packet-a",
                        "status": "ready",
                        "go_no_go": "go",
                        "recommended_outcome": "adopt",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "owner_context": {"candidate-a": "backend-owner"},
            "reviewer_context": {"candidate-a": "mainline-reviewer"},
        }
    )

    assert handoff["kind"] == "integration_review_manifest_adoption_owner_handoff"
    assert handoff["ok"] is True
    assert handoff["status"] == "ready"
    assert handoff["items"][0]["handoff_state"] == "ready_for_owner_review"
    assert handoff["owner_groups"] == {"backend-owner": ["candidate-a"]}
    assert handoff["next_actions"] == ["share_manifest_adoption_owner_handoff_with_mainline"]


def test_owner_handoff_requires_missing_assignments() -> None:
    handoff = build_integration_review_manifest_adoption_owner_handoff(
        {
            "manifest_adoption_final_packet": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "packet_key": "packet-a",
                        "status": "ready",
                        "go_no_go": "go",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert handoff["status"] == "needs_review"
    assert handoff["review_candidates"] == ["candidate-a"]
    assert handoff["items"][0]["missing_assignments"] == ["owner", "reviewer"]
    assert "assign_manifest_adoption_owner" in handoff["next_actions"]


def test_owner_handoff_blocks_no_go_packet() -> None:
    handoff = build_integration_review_manifest_adoption_owner_handoff(
        {
            "manifest_adoption_final_packet": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "packet_key": "packet-a",
                        "status": "blocked",
                        "go_no_go": "no_go",
                        "recommended_outcome": "defer",
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            },
            "owner_context": {"candidate-a": "backend-owner"},
            "reviewer_context": {"candidate-a": "mainline-reviewer"},
        }
    )

    assert handoff["status"] == "blocked"
    assert handoff["blocked_candidates"] == ["candidate-a"]
    assert handoff["items"][0]["owner_actions"] == ["review_manifest_adoption_blockers"]
    assert handoff["next_actions"][0] == "resolve_manifest_adoption_owner_handoff_blockers"


def test_go_no_go_can_supply_fallback_refs() -> None:
    handoff = build_integration_review_manifest_adoption_owner_handoff(
        {
            "manifest_adoption_final_packet": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "packet_key": "packet-a",
                        "status": "ready",
                        "go_no_go": "go",
                    }
                ]
            },
            "manifest_adoption_go_no_go": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "owner_context": {"candidate-a": "backend-owner"},
            "reviewer_context": {"candidate-a": "mainline-reviewer"},
        }
    )

    assert handoff["status"] == "ready"
    assert handoff["items"][0]["validation_refs"] == ["pytest candidate-a"]
    assert handoff["items"][0]["handoff_refs"] == ["handoff"]


def test_explicit_owner_handoff_can_seed_payload() -> None:
    handoff = build_integration_review_manifest_adoption_owner_handoff(
        {
            "owner_handoffs": [
                {
                    "candidate_id": "candidate-a",
                    "handoff_key": "handoff-a",
                    "status": "ready",
                    "go_no_go": "go",
                    "recommended_outcome": "adopt",
                    "owner": "backend-owner",
                    "reviewer": "mainline-reviewer",
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert handoff["status"] == "ready"
    assert handoff["items"][0]["handoff_key"] == "handoff-a"
    assert handoff["items"][0]["owner"] == "backend-owner"


def test_empty_owner_handoff_requests_inputs() -> None:
    handoff = build_integration_review_manifest_adoption_owner_handoff({})

    assert handoff["ok"] is False
    assert handoff["status"] == "empty"
    assert handoff["next_actions"] == ["provide_review_manifest_adoption_owner_handoff_inputs"]


def test_summarize_owner_handoff_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Handoff:
        candidate_id: str
        handoff_key: str
        status: str
        go_no_go: str
        recommended_outcome: str
        owner: str
        reviewer: str
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_owner_handoff_item(
        Handoff(
            candidate_id="candidate-a",
            handoff_key="handoff-a",
            status="ready",
            go_no_go="go",
            recommended_outcome="adopt",
            owner="backend-owner",
            reviewer="mainline-reviewer",
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.handoff_state == "ready_for_owner_review"
