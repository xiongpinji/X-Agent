from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_final_packet import (
    build_integration_review_manifest_adoption_final_packet,
    summarize_review_manifest_adoption_final_packet_item,
)


def test_final_packet_marks_go_decision_ready() -> None:
    packet = build_integration_review_manifest_adoption_final_packet(
        {
            "manifest_adoption_go_no_go": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "decision_key": "go-no-go-a",
                        "status": "ready",
                        "go_no_go": "go",
                        "recommended_outcome": "adopt",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert packet["kind"] == "integration_review_manifest_adoption_final_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["items"][0]["packet_state"] == "ready_for_mainline_review"
    assert packet["next_actions"] == ["share_manifest_adoption_final_packet_with_mainline"]


def test_final_packet_holds_hold_decision_for_review() -> None:
    packet = build_integration_review_manifest_adoption_final_packet(
        {
            "manifest_adoption_go_no_go": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "decision_key": "go-no-go-a",
                        "status": "ready",
                        "go_no_go": "hold",
                        "recommended_outcome": "review",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["review_candidates"] == ["candidate-a"]
    assert "resolve_manifest_adoption_hold_decision" in packet["next_actions"]


def test_final_packet_blocks_no_go_decision() -> None:
    packet = build_integration_review_manifest_adoption_final_packet(
        {
            "manifest_adoption_go_no_go": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "decision_key": "go-no-go-a",
                        "status": "blocked",
                        "go_no_go": "no_go",
                        "recommended_outcome": "defer",
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            }
        }
    )

    assert packet["status"] == "blocked"
    assert packet["blocked_candidates"] == ["candidate-a"]
    assert "forbidden scope overlap" in packet["packet_sections"]["blockers"]
    assert packet["next_actions"][0] == "resolve_manifest_adoption_final_packet_blockers"


def test_rollback_and_dry_run_can_supply_fallback_refs() -> None:
    packet = build_integration_review_manifest_adoption_final_packet(
        {
            "manifest_adoption_go_no_go": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "decision_key": "go-no-go-a",
                        "status": "ready",
                        "go_no_go": "go",
                    }
                ]
            },
            "manifest_adoption_rollback_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "validation_refs": ["pytest candidate-a"],
                    }
                ]
            },
            "manifest_adoption_dry_run_report": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
        }
    )

    assert packet["status"] == "ready"
    assert packet["items"][0]["validation_refs"] == ["pytest candidate-a"]
    assert packet["items"][0]["handoff_refs"] == ["handoff"]


def test_explicit_final_packet_can_seed_packet() -> None:
    packet = build_integration_review_manifest_adoption_final_packet(
        {
            "packets": [
                {
                    "candidate_id": "candidate-a",
                    "packet_key": "packet-a",
                    "status": "ready",
                    "go_no_go": "go",
                    "recommended_outcome": "adopt",
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert packet["status"] == "ready"
    assert packet["items"][0]["packet_key"] == "packet-a"
    assert packet["items"][0]["go_no_go"] == "go"


def test_empty_final_packet_requests_inputs() -> None:
    packet = build_integration_review_manifest_adoption_final_packet({})

    assert packet["ok"] is False
    assert packet["status"] == "empty"
    assert packet["next_actions"] == ["provide_review_manifest_adoption_final_packet_inputs"]


def test_summarize_final_packet_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Packet:
        candidate_id: str
        packet_key: str
        status: str
        go_no_go: str
        recommended_outcome: str
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_final_packet_item(
        Packet(
            candidate_id="candidate-a",
            packet_key="packet-a",
            status="ready",
            go_no_go="go",
            recommended_outcome="adopt",
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.packet_state == "ready_for_mainline_review"
