from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_resolution_receipt import (
    build_integration_review_manifest_resolution_receipt,
    summarize_review_manifest_resolution_receipt_item,
)


def test_resolution_receipt_marks_signed_ready_plan_ready() -> None:
    receipt = build_integration_review_manifest_resolution_receipt(
        {
            "manifest_conflict_resolution_plan": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "plan_key": "plan-a",
                        "status": "ready",
                        "recommended_decision": "prepare_candidate_for_mainline_evaluation",
                        "owner": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "signoffs": {"candidate-a": {"owner": "approved", "reviewer": "approved"}},
        }
    )

    assert receipt["kind"] == "integration_review_manifest_resolution_receipt"
    assert receipt["ok"] is True
    assert receipt["status"] == "ready"
    assert receipt["ready_candidates"] == ["candidate-a"]
    assert receipt["items"][0]["receipt_state"] == "review_ready"
    assert receipt["next_actions"] == ["share_manifest_resolution_receipt_with_mainline"]


def test_resolution_receipt_requires_missing_signoff() -> None:
    receipt = build_integration_review_manifest_resolution_receipt(
        {
            "manifest_conflict_resolution_plan": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "plan_key": "plan-a",
                        "status": "ready",
                        "owner": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "signoffs": {"candidate-a": {"owner": "approved"}},
        }
    )

    assert receipt["status"] == "needs_review"
    assert receipt["review_candidates"] == ["candidate-a"]
    assert receipt["items"][0]["missing_signoffs"] == ["reviewer"]
    assert "collect_manifest_resolution_signoffs" in receipt["next_actions"]


def test_blocked_resolution_plan_blocks_receipt() -> None:
    receipt = build_integration_review_manifest_resolution_receipt(
        {
            "manifest_conflict_resolution_plan": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "plan_key": "plan-a",
                        "status": "blocked",
                        "recommended_decision": "defer_candidate_until_blockers_resolved",
                        "candidate_paths": ["backend/app/api/router.py"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            }
        }
    )

    assert receipt["status"] == "blocked"
    assert receipt["blocked_candidates"] == ["candidate-a"]
    assert receipt["items"][0]["receipt_state"] == "blocked"
    assert "forbidden scope overlap" in receipt["items"][0]["blockers"]
    assert receipt["next_actions"][0] == "resolve_manifest_resolution_receipt_blockers"


def test_validation_evidence_can_be_supplied_outside_plan_item() -> None:
    receipt = build_integration_review_manifest_resolution_receipt(
        {
            "manifest_conflict_resolution_plan": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "plan_key": "plan-a",
                        "status": "ready",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "validation_evidence": {"candidate-a": {"validation_refs": ["pytest candidate-a"]}},
            "signoffs": {"candidate-a": {"reviewer": "approved"}},
        }
    )

    assert receipt["status"] == "ready"
    assert receipt["items"][0]["validation_refs"] == ["pytest candidate-a"]
    assert receipt["items"][0]["signoffs"] == ["reviewer"]


def test_empty_resolution_receipt_requests_inputs() -> None:
    receipt = build_integration_review_manifest_resolution_receipt({})

    assert receipt["ok"] is False
    assert receipt["status"] == "empty"
    assert receipt["next_actions"] == ["provide_review_manifest_resolution_receipt_inputs"]


def test_explicit_receipt_payload_can_seed_receipt() -> None:
    receipt = build_integration_review_manifest_resolution_receipt(
        {
            "receipts": [
                {
                    "candidate_id": "candidate-a",
                    "receipt_key": "receipt-a",
                    "status": "ready",
                    "recommended_decision": "hold_for_batch_review",
                    "candidate_paths": ["module.py"],
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                    "signoffs": ["reviewer"],
                }
            ]
        }
    )

    assert receipt["status"] == "ready"
    assert receipt["items"][0]["receipt_key"] == "receipt-a"
    assert receipt["items"][0]["recommended_decision"] == "hold_for_batch_review"


def test_summarize_resolution_receipt_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Receipt:
        candidate_id: str
        receipt_key: str
        status: str
        recommended_decision: str
        candidate_paths: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]
        signoffs: tuple[str, ...]

    item = summarize_review_manifest_resolution_receipt_item(
        Receipt(
            candidate_id="candidate-a",
            receipt_key="receipt-a",
            status="ready",
            recommended_decision="prepare_candidate_for_mainline_evaluation",
            candidate_paths=("module.py",),
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
            signoffs=("reviewer",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.receipt_state == "review_ready"
