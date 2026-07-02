from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.subagent_handoff_matrix import (
    build_subagent_handoff_matrix,
    evaluate_subagent_handoff,
)


def test_subagent_handoff_matrix_marks_complete_handoffs_ready() -> None:
    matrix = build_subagent_handoff_matrix(
        {
            "parent_task_id": "parent-1",
            "goal": "parallel implementation",
            "handoffs": [
                {
                    "handoff_id": "h1",
                    "agent_id": "agent-a",
                    "status": "succeeded",
                    "summary": "implemented backend helper",
                    "artifacts": ["backend/app/core/a.py"],
                    "validation_evidence": [{"cmd": "pytest tests/test_a.py", "result": "passed"}],
                    "changed_files": ["backend/app/core/a.py"],
                    "owner": "agent-a",
                    "parent_acceptance_refs": ["tests"],
                },
                {
                    "handoff_id": "h2",
                    "agent_id": "agent-b",
                    "status": "completed",
                    "summary": "implemented docs",
                    "artifacts": ["docs/a.md"],
                    "validation": {"passed": True},
                    "changed_files": ["docs/a.md"],
                    "owner": "agent-b",
                    "acceptance_refs": ["handoff"],
                },
            ],
        }
    )

    assert matrix["kind"] == "subagent_handoff_matrix"
    assert matrix["ok"] is True
    assert matrix["status"] == "ready"
    assert matrix["summary"]["ready_count"] == 2
    assert matrix["next_actions"] == ["prepare_parent_merge_review"]


def test_blocked_handoff_blocks_parent_merge_readiness() -> None:
    matrix = build_subagent_handoff_matrix(
        {
            "handoffs": [
                {
                    "handoff_id": "blocked",
                    "agent_id": "agent-a",
                    "status": "blocked",
                    "summary": "cannot proceed",
                    "artifacts": ["report.md"],
                    "validation_evidence": ["manual review"],
                    "blockers": ["missing upstream API"],
                    "owner": "agent-a",
                    "parent_acceptance_refs": ["api"],
                }
            ]
        }
    )

    assert matrix["ok"] is False
    assert matrix["status"] == "blocked"
    assert matrix["rows"][0]["decision"] == "blocked"
    assert matrix["issues"][0]["code"] == "subagent_handoff_status_blocked"
    assert matrix["next_actions"] == ["resolve_blocked_handoffs", "request_subagent_updates"]


def test_missing_validation_or_artifacts_needs_review() -> None:
    matrix = build_subagent_handoff_matrix(
        {
            "handoffs": [
                {
                    "handoff_id": "h1",
                    "agent_id": "agent-a",
                    "status": "succeeded",
                    "summary": "done",
                    "changed_files": ["a.py"],
                    "owner": "agent-a",
                    "parent_acceptance_refs": ["tests"],
                }
            ]
        }
    )

    assert matrix["status"] == "needs_review"
    assert matrix["rows"][0]["decision"] == "needs_review"
    assert "artifacts missing" in matrix["rows"][0]["reasons"]
    assert "validation evidence missing" in matrix["rows"][0]["reasons"]
    assert matrix["issues"][0]["code"] == "subagent_handoff_validation_missing"


def test_changed_file_conflicts_are_reported() -> None:
    matrix = build_subagent_handoff_matrix(
        {
            "handoffs": [
                {
                    "handoff_id": "h1",
                    "agent_id": "agent-a",
                    "status": "succeeded",
                    "summary": "changed shared file",
                    "artifacts": ["a"],
                    "validation": {"passed": True},
                    "changed_files": ["backend/app/core/shared.py"],
                    "owner": "agent-a",
                    "parent_acceptance_refs": ["tests"],
                },
                {
                    "handoff_id": "h2",
                    "agent_id": "agent-b",
                    "status": "succeeded",
                    "summary": "also changed shared file",
                    "artifacts": ["b"],
                    "validation": {"passed": True},
                    "changed_files": ["backend/app/core/shared.py"],
                    "owner": "agent-b",
                    "parent_acceptance_refs": ["tests"],
                },
            ]
        }
    )

    assert matrix["status"] == "needs_review"
    assert matrix["summary"]["conflict_count"] == 1
    assert matrix["conflicts"] == {"backend/app/core/shared.py": ["agent-a", "agent-b"]}
    assert matrix["issues"][0]["code"] == "subagent_handoff_changed_file_conflict"
    assert matrix["next_actions"] == ["resolve_changed_file_conflicts", "refresh_parent_handoff"]


def test_missing_owner_or_parent_refs_needs_review() -> None:
    row = evaluate_subagent_handoff(
        {
            "handoff_id": "h1",
            "agent_id": "agent-a",
            "status": "succeeded",
            "summary": "done",
            "artifacts": ["artifact"],
            "validation_evidence": ["pytest passed"],
        }
    )

    assert row.decision == "needs_review"
    assert "owner missing" in row.reasons
    assert "parent acceptance refs missing" in row.reasons


def test_accepts_dataclass_like_handoff_payload() -> None:
    @dataclass
    class Handoff:
        handoff_id: str
        agent_id: str
        status: str
        summary: str
        artifacts: list[str]
        validation_evidence: list[str]
        changed_files: list[str]
        owner: str
        parent_acceptance_refs: list[str]

    matrix = build_subagent_handoff_matrix(
        {
            "handoffs": [
                Handoff(
                    "h1",
                    "agent-a",
                    "ok",
                    "finished",
                    ["artifact"],
                    ["pytest passed"],
                    ["backend/app/core/x.py"],
                    "agent-a",
                    ["tests"],
                )
            ]
        }
    )

    assert matrix["status"] == "ready"
    assert matrix["rows"][0]["handoff_id"] == "h1"
    assert matrix["rows"][0]["validation_count"] == 1


def test_empty_matrix_requests_handoffs() -> None:
    matrix = build_subagent_handoff_matrix({})

    assert matrix["status"] == "empty"
    assert matrix["ok"] is False
    assert matrix["next_actions"] == ["provide_subagent_handoffs"]
