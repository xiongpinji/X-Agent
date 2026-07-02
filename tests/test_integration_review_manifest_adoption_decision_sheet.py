from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_decision_sheet import (
    build_integration_review_manifest_adoption_decision_sheet,
    summarize_review_manifest_adoption_decision_row,
)


def test_decision_sheet_marks_ready_receipt_for_adoption() -> None:
    sheet = build_integration_review_manifest_adoption_decision_sheet(
        {
            "manifest_resolution_receipt": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "receipt_key": "receipt-a",
                        "status": "ready",
                        "receipt_state": "review_ready",
                        "recommended_decision": "prepare_candidate_for_mainline_evaluation",
                        "owner": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert sheet["kind"] == "integration_review_manifest_adoption_decision_sheet"
    assert sheet["ok"] is True
    assert sheet["status"] == "ready"
    assert sheet["adopt_candidates"] == ["candidate-a"]
    assert sheet["rows"][0]["recommended_outcome"] == "adopt"
    assert sheet["rows"][0]["stage_label"] == "secondary_integration_candidate"
    assert sheet["next_actions"] == ["share_manifest_adoption_decision_sheet_with_mainline"]


def test_decision_sheet_marks_incomplete_receipt_for_review() -> None:
    sheet = build_integration_review_manifest_adoption_decision_sheet(
        {
            "manifest_resolution_receipt": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "receipt_key": "receipt-a",
                        "status": "needs_review",
                        "receipt_state": "incomplete",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "handoff_refs": ["handoff"],
                        "evidence_gaps": ["validation refs missing"],
                    }
                ]
            },
            "owner_context": {"candidate-a": "backend-owner"},
            "reviewer_context": {"candidate-a": "mainline-reviewer"},
        }
    )

    assert sheet["status"] == "needs_review"
    assert sheet["review_candidates"] == ["candidate-a"]
    assert sheet["rows"][0]["recommended_outcome"] == "review"
    assert "resolution receipt still needs review" in sheet["rows"][0]["evidence_gaps"]
    assert "complete_manifest_resolution_receipt" in sheet["next_actions"]


def test_decision_sheet_defers_blocked_receipt() -> None:
    sheet = build_integration_review_manifest_adoption_decision_sheet(
        {
            "manifest_resolution_receipt": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "receipt_key": "receipt-a",
                        "status": "blocked",
                        "recommended_decision": "defer_candidate_until_blockers_resolved",
                        "owner": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "candidate_paths": ["backend/app/api/router.py"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            }
        }
    )

    assert sheet["status"] == "blocked"
    assert sheet["blocked_candidates"] == ["candidate-a"]
    assert sheet["defer_candidates"] == ["candidate-a"]
    assert sheet["rows"][0]["stage_label"] == "secondary_deferred"
    assert sheet["next_actions"][0] == "resolve_manifest_adoption_decision_blockers"


def test_manifest_preview_can_supply_manifest_refs_and_paths() -> None:
    sheet = build_integration_review_manifest_adoption_decision_sheet(
        {
            "manifest_resolution_receipt": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "receipt_key": "receipt-a",
                        "status": "ready",
                        "owner": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "adoption_manifest_preview": {
                "entries": [
                    {
                        "candidate_id": "candidate-a",
                        "manifest_key": "manifest-a",
                        "include_paths": ["backend/app/core/candidate_a.py"],
                    }
                ]
            },
        }
    )

    assert sheet["status"] == "ready"
    assert sheet["rows"][0]["candidate_paths"] == ["backend/app/core/candidate_a.py"]
    assert "manifest-a" in sheet["rows"][0]["manifest_refs"]


def test_explicit_decision_can_override_outcome() -> None:
    sheet = build_integration_review_manifest_adoption_decision_sheet(
        {
            "decisions": [
                {
                    "candidate_id": "candidate-a",
                    "decision_key": "decision-a",
                    "status": "ready",
                    "recommended_outcome": "reject",
                    "owner": "backend-owner",
                    "reviewer": "mainline-reviewer",
                    "candidate_paths": ["module.py"],
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert sheet["status"] == "ready"
    assert sheet["reject_candidates"] == ["candidate-a"]
    assert sheet["rows"][0]["decision_key"] == "decision-a"
    assert sheet["rows"][0]["stage_label"] == "secondary_rejected"


def test_empty_decision_sheet_requests_inputs() -> None:
    sheet = build_integration_review_manifest_adoption_decision_sheet({})

    assert sheet["ok"] is False
    assert sheet["status"] == "empty"
    assert sheet["next_actions"] == ["provide_review_manifest_adoption_decision_inputs"]


def test_summarize_decision_row_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Decision:
        candidate_id: str
        decision_key: str
        status: str
        recommended_outcome: str
        owner: str
        reviewer: str
        candidate_paths: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    row = summarize_review_manifest_adoption_decision_row(
        Decision(
            candidate_id="candidate-a",
            decision_key="decision-a",
            status="ready",
            recommended_outcome="adopt",
            owner="backend-owner",
            reviewer="mainline-reviewer",
            candidate_paths=("module.py",),
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert row.candidate_id == "candidate-a"
    assert row.decision_status == "ready"
    assert row.recommended_outcome == "adopt"
