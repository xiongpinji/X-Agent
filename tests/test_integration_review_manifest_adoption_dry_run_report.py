from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_dry_run_report import (
    build_integration_review_manifest_adoption_dry_run_report,
    summarize_review_manifest_adoption_dry_run_report_item,
)


def test_dry_run_report_marks_ready_execution_preview_ready() -> None:
    report = build_integration_review_manifest_adoption_dry_run_report(
        {
            "manifest_adoption_execution_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "preview_key": "preview-a",
                        "status": "ready",
                        "recommended_outcome": "adopt",
                        "operation": "preview_stage_candidate_for_adoption",
                        "touched_paths": ["backend/app/core/candidate_a.py", "stage_include:backend/app/core/candidate_a.py"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert report["kind"] == "integration_review_manifest_adoption_dry_run_report"
    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["ready_candidates"] == ["candidate-a"]
    assert "stage_include:backend/app/core/candidate_a.py" in report["report_sections"]["touched_paths"]
    assert report["next_actions"] == ["share_manifest_adoption_dry_run_report_with_mainline"]


def test_dry_run_report_surfaces_execution_warnings() -> None:
    report = build_integration_review_manifest_adoption_dry_run_report(
        {
            "manifest_adoption_execution_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "preview_key": "preview-a",
                        "status": "needs_review",
                        "recommended_outcome": "adopt",
                        "touched_paths": ["backend/app/core/candidate_a.py"],
                        "handoff_refs": ["handoff"],
                        "warnings": ["validation refs missing"],
                    }
                ]
            }
        }
    )

    assert report["status"] == "needs_review"
    assert report["review_candidates"] == ["candidate-a"]
    assert "validation refs missing" in report["report_sections"]["warnings"]
    assert "review_manifest_adoption_dry_run_warnings" in report["next_actions"]


def test_dry_run_report_blocks_blocked_execution_preview() -> None:
    report = build_integration_review_manifest_adoption_dry_run_report(
        {
            "manifest_adoption_execution_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "preview_key": "preview-a",
                        "status": "blocked",
                        "recommended_outcome": "defer",
                        "touched_paths": ["backend/app/api/router.py"],
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            }
        }
    )

    assert report["status"] == "blocked"
    assert report["blocked_candidates"] == ["candidate-a"]
    assert "forbidden scope overlap" in report["report_sections"]["blockers"]
    assert report["next_actions"][0] == "resolve_manifest_adoption_dry_run_report_blockers"


def test_decision_sheet_can_supply_fallback_refs() -> None:
    report = build_integration_review_manifest_adoption_dry_run_report(
        {
            "manifest_adoption_execution_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "preview_key": "preview-a",
                        "status": "ready",
                        "recommended_outcome": "adopt",
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "manifest_adoption_decision_sheet": {
                "rows": [
                    {
                        "candidate_id": "candidate-a",
                        "candidate_paths": ["backend/app/core/candidate_a.py"],
                        "validation_refs": ["pytest candidate-a"],
                    }
                ]
            },
        }
    )

    assert report["status"] == "ready"
    assert report["items"][0]["touched_paths"] == ["backend/app/core/candidate_a.py"]
    assert report["items"][0]["validation_refs"] == ["pytest candidate-a"]


def test_explicit_report_item_can_seed_report() -> None:
    report = build_integration_review_manifest_adoption_dry_run_report(
        {
            "report_items": [
                {
                    "candidate_id": "candidate-a",
                    "report_key": "report-a",
                    "status": "ready",
                    "recommended_outcome": "reject",
                    "operation": "preview_mark_candidate_rejected",
                    "touched_paths": ["module.py"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert report["status"] == "ready"
    assert report["items"][0]["report_key"] == "report-a"
    assert report["items"][0]["recommended_outcome"] == "reject"


def test_empty_dry_run_report_requests_inputs() -> None:
    report = build_integration_review_manifest_adoption_dry_run_report({})

    assert report["ok"] is False
    assert report["status"] == "empty"
    assert report["next_actions"] == ["provide_review_manifest_adoption_dry_run_report_inputs"]


def test_summarize_dry_run_report_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class ReportItem:
        candidate_id: str
        report_key: str
        status: str
        recommended_outcome: str
        operation: str
        touched_paths: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_dry_run_report_item(
        ReportItem(
            candidate_id="candidate-a",
            report_key="report-a",
            status="ready",
            recommended_outcome="adopt",
            operation="preview_stage_candidate_for_adoption",
            touched_paths=("module.py",),
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.operation == "preview_stage_candidate_for_adoption"
