from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_action_status_export import (
    build_integration_review_action_status_export,
    summarize_review_action_status_export_row,
)


def test_review_action_status_export_builds_ready_export_view() -> None:
    export = build_integration_review_action_status_export(
        {
            "export_id": "export-1",
            "formats": ["markdown", "json"],
            "action_status_board": {
                "items": [
                    {
                        "candidate_id": "integration_review_action_status_board",
                        "status_key": "status-a",
                        "status": "ready",
                        "lane": "ready",
                        "priority": "low",
                        "evidence_refs": ["6 passed", "handoff"],
                        "owner": "mainline",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
        }
    )

    assert export["kind"] == "integration_review_action_status_export"
    assert export["ok"] is True
    assert export["status"] == "ready"
    assert export["formats"] == ["markdown", "json"]
    assert export["summary"]["row_count"] == 1
    assert export["sections"]["ready"][0]["status_key"] == "status-a"
    assert export["render_hints"]["write_files"] is False
    assert export["next_actions"] == ["share_review_action_status_export_with_mainline"]


def test_missing_owner_reviewer_and_evidence_need_review() -> None:
    export = build_integration_review_action_status_export(
        {
            "action_status_board": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "status_key": "status-a",
                        "status": "needs_review",
                        "lane": "needs_review",
                    }
                ]
            }
        }
    )

    assert export["status"] == "needs_review"
    assert export["missing_inputs"] == {
        "status-a": ["export evidence missing", "owner missing", "reviewer missing"]
    }
    assert "complete_review_action_status_export" in export["next_actions"]
    assert "attach_export_evidence" in export["next_actions"]


def test_blocked_validation_blocks_export_view() -> None:
    export = build_integration_review_action_status_export(
        {
            "action_status_board": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "status_key": "status-a",
                        "status": "ready",
                        "lane": "ready",
                        "evidence_refs": ["blocked evidence"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "validation_evidence": [
                {
                    "candidate_id": "candidate-a",
                    "status": "blocked",
                    "refs": ["blocked evidence"],
                    "blockers": ["validation timeout"],
                }
            ],
        }
    )

    assert export["status"] == "blocked"
    assert export["rows"][0]["status"] == "blocked"
    assert export["rows"][0]["priority"] == "high"
    assert export["rows"][0]["blockers"] == ["validation timeout"]
    assert export["next_actions"] == [
        "resolve_review_action_status_export_blockers",
        "attach_export_evidence",
        "rebuild_integration_review_action_status_export",
    ]


def test_export_formats_are_filtered_and_defaulted() -> None:
    export = build_integration_review_action_status_export(
        {
            "formats": ["markdown", "xlsx", "csv", "markdown"],
            "rows": [
                {
                    "candidate_id": "candidate-a",
                    "status_key": "status-a",
                    "status": "ready",
                    "lane": "ready",
                    "evidence_refs": ["manual evidence"],
                    "owner": "owner-a",
                    "reviewer": "reviewer-a",
                }
            ],
        }
    )

    assert export["formats"] == ["markdown", "csv"]
    assert export["rows"][0]["export_formats"] == ["markdown", "csv"]


def test_empty_review_action_status_export_requests_inputs() -> None:
    export = build_integration_review_action_status_export({})

    assert export["ok"] is False
    assert export["status"] == "empty"
    assert export["next_actions"] == ["provide_review_action_status_export_inputs"]


def test_summarize_review_action_status_export_row_accepts_dataclass_like_payload() -> None:
    @dataclass
    class ExportRow:
        candidate_id: str
        status_key: str
        status: str
        lane: str
        evidence_refs: tuple[str, ...]
        owner: str
        reviewer: str
        priority: str

    row = summarize_review_action_status_export_row(
        ExportRow(
            candidate_id="candidate-a",
            status_key="status-a",
            status="ready",
            lane="ready",
            evidence_refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
            priority="low",
        )
    )

    assert row.candidate_id == "candidate-a"
    assert row.status == "ready"
    assert row.export_formats == ("summary",)
    assert row.evidence_refs == ("handoff",)
