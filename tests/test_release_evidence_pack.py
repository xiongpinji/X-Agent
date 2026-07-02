from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.release_evidence_pack import (
    assess_evidence_matrix,
    build_release_evidence_pack,
)


def test_release_evidence_pack_marks_all_ready_matrices_ready() -> None:
    pack = build_release_evidence_pack(
        {
            "release_id": "rel-1",
            "required_kinds": ["agent_eval_matrix", "mcp_tool_readiness"],
            "matrices": [
                {
                    "kind": "agent_eval_matrix",
                    "status": "accepted",
                    "ok": True,
                    "summary": {"score": 0.92},
                    "issues": [],
                    "next_actions": ["prepare_release_or_review_handoff"],
                },
                {
                    "kind": "mcp_tool_readiness",
                    "status": "ready",
                    "ok": True,
                    "summary": {"tool_count": 1},
                    "issues": [],
                    "next_actions": ["prepare_mcp_tool_integration_review"],
                },
            ],
        }
    )

    assert pack["kind"] == "release_evidence_pack"
    assert pack["ok"] is True
    assert pack["status"] == "ready"
    assert pack["summary"]["ready_count"] == 2
    assert pack["next_actions"] == ["prepare_mainline_integration_review"]


def test_blocked_matrix_blocks_release_evidence_pack() -> None:
    pack = build_release_evidence_pack(
        {
            "matrices": [
                {
                    "kind": "channel_integration_readiness",
                    "status": "blocked",
                    "ok": False,
                    "issues": [{"code": "channel_owner_missing", "severity": "high"}],
                    "next_actions": ["obtain_owner_approval_before_outbound_send"],
                }
            ]
        }
    )

    assert pack["status"] == "blocked"
    assert pack["summary"]["blocked_count"] == 1
    assert pack["issues"][0]["code"] == "release_evidence_matrix_blocked"
    assert pack["next_actions"] == ["resolve_blocking_evidence_matrices", "rebuild_release_evidence_pack"]


def test_review_matrix_bubbles_next_actions() -> None:
    pack = build_release_evidence_pack(
        {
            "matrices": [
                {
                    "kind": "browser_task_readiness",
                    "status": "needs_review",
                    "ok": False,
                    "issues": [{"code": "browser_screenshot_missing", "severity": "medium"}],
                    "next_actions": ["collect_browser_evidence", "rerun_browser_readiness"],
                }
            ]
        }
    )

    assert pack["status"] == "needs_review"
    assert pack["issues"][0]["code"] == "release_evidence_matrix_needs_review"
    assert pack["next_actions"] == ["collect_browser_evidence", "rerun_browser_readiness"]


def test_missing_required_kind_needs_review() -> None:
    pack = build_release_evidence_pack(
        {
            "required_kinds": ["agent_eval_matrix", "subagent_handoff_matrix"],
            "matrices": [{"kind": "agent_eval_matrix", "status": "accepted", "ok": True}],
        }
    )

    assert pack["status"] == "needs_review"
    assert pack["missing_required_kinds"] == ["subagent_handoff_matrix"]
    assert pack["issues"][0]["code"] == "release_evidence_required_matrix_missing"
    assert pack["next_actions"] == ["collect_missing_required_matrices", "rebuild_release_evidence_pack"]


def test_empty_pack_requests_evidence_matrices() -> None:
    pack = build_release_evidence_pack({})

    assert pack["status"] == "empty"
    assert pack["ok"] is False
    assert pack["next_actions"] == ["provide_evidence_matrices"]


def test_assess_evidence_matrix_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Matrix:
        kind: str
        status: str
        ok: bool
        issues: list[dict[str, str]]
        next_actions: list[str]
        summary: dict[str, int]

    item = assess_evidence_matrix(
        Matrix(
            "open_source_adoption_matrix",
            "adopt_ready",
            True,
            [],
            ["prepare_integration_design_review"],
            {"candidate_count": 1},
        )
    )

    assert item.kind == "open_source_adoption_matrix"
    assert item.decision == "ready"
    assert item.summary == {"candidate_count": 1}


def test_high_severity_issue_blocks_even_if_status_is_review() -> None:
    item = assess_evidence_matrix(
        {
            "kind": "mcp_tool_readiness",
            "status": "needs_review",
            "ok": False,
            "issues": [{"code": "mcp_tool_high_risk_without_manual_approval", "severity": "high"}],
        }
    )

    assert item.decision == "blocked"
    assert "high severity issues present" in item.reasons
