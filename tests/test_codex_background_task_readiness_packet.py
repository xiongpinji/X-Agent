from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_background_task_readiness_packet import (
    build_codex_background_task_readiness_packet,
    summarize_codex_background_task,
)


PACKET_POLICIES = {
    "retry_policy": "retry-v1",
    "resumability_policy": "resume-v1",
    "artifact_policy": "artifact-v1",
    "queue_ref": "queue/main",
    "handoff_policy_ref": "handoff-policy",
    "notification_policy_ref": "notification-policy",
}


def test_ready_cloud_task_with_worktree_remote_handoff_and_receipts() -> None:
    packet = build_codex_background_task_readiness_packet(
        {
            **PACKET_POLICIES,
            "tasks": [
                {
                    "task_id": "task-1",
                    "task_type": "cloud",
                    "state": "queued",
                    "queue_state": "queued",
                    "resumable": True,
                    "retry_policy": "retry-v1",
                    "branch_ref": "xagent/codex-parity",
                    "worktree_ref": "worktrees/task-1",
                    "remote_execution_ref": "cloud/run-1",
                    "handoff_ref": "docs/handoff.md#task-1",
                    "notification_ref": "thread/main",
                    "artifact_refs": ["artifact/result.json"],
                    "validation_refs": ["pytest receipt"],
                    "diff_refs": ["diff/task-1.patch"],
                    "pr_refs": ["PR-42"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_background_task_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["task_count"] == 1
    assert packet["summary"]["remote_task_count"] == 1
    assert packet["next_actions"] == ["share_background_task_readiness_with_mainline"]


def test_missing_packet_policies_needs_review_before_mainline_adoption() -> None:
    packet = build_codex_background_task_readiness_packet(
        {
            "tasks": [
                {
                    "task_id": "task-1",
                    "task_type": "background",
                    "state": "queued",
                    "queue_state": "queued",
                    "resumable": True,
                    "retry_policy": "retry",
                    "branch_ref": "branch",
                    "worktree_ref": "worktree",
                    "handoff_ref": "handoff",
                    "notification_ref": "notification",
                    "artifact_refs": ["artifact"],
                    "validation_refs": ["validation"],
                    "diff_refs": ["diff"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_background_task_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "retry_policy_ref",
        "resumability_policy_ref",
        "artifact_policy_ref",
        "task_queue_ref",
        "handoff_policy_ref",
        "notification_policy_ref",
    ]


def test_cloud_task_missing_remote_resume_artifacts_and_validation_needs_review() -> None:
    packet = build_codex_background_task_readiness_packet(
        {
            **PACKET_POLICIES,
            "tasks": [
                {
                    "task_id": "task-2",
                    "task_type": "cloud",
                    "state": "queued",
                    "queue_state": "queued",
                    "retry_policy": "retry-v1",
                    "branch_ref": "branch",
                    "worktree_ref": "worktree",
                    "notification_ref": "notification",
                }
            ],
        }
    )

    task = packet["tasks"][0]
    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_background_task_missing_evidence"
    assert "resumability_ref" in task["missing_refs"]
    assert "remote_execution_ref" in task["missing_refs"]
    assert "handoff_ref" in task["missing_refs"]
    assert "artifact_refs" in task["missing_refs"]
    assert "validation_refs" in task["missing_refs"]
    assert "diff_or_pr_refs" in task["missing_refs"]


def test_failed_task_blocks_packet() -> None:
    packet = build_codex_background_task_readiness_packet(
        {
            **PACKET_POLICIES,
            "tasks": [
                {
                    "task_id": "task-3",
                    "task_type": "background",
                    "state": "failed",
                    "queue_state": "queued",
                    "resumable": True,
                    "retry_policy": "retry",
                    "branch_ref": "branch",
                    "worktree_ref": "worktree",
                    "handoff_ref": "handoff",
                    "notification_ref": "notification",
                    "artifact_refs": ["artifact"],
                    "validation_refs": ["validation"],
                    "diff_refs": ["diff"],
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_background_task_terminal_failure"
    assert packet["next_actions"] == [
        "resolve_background_task_blockers",
        "refresh_background_task_readiness",
    ]


def test_orphaned_queue_state_blocks_packet() -> None:
    task = summarize_codex_background_task(
        {
            "task_id": "task-4",
            "task_type": "background",
            "state": "running",
            "queue_state": "orphaned",
            "resumable": True,
            "retry_policy": "retry",
            "branch_ref": "branch",
            "worktree_ref": "worktree",
            "handoff_ref": "handoff",
            "notification_ref": "notification",
            "artifact_refs": ["artifact"],
            "validation_refs": ["validation"],
            "diff_refs": ["diff"],
        }
    )

    assert task.readiness_state == "blocked"
    assert "queue_state_not_recoverable" in task.blockers


def test_empty_payload_requests_background_task_inventory() -> None:
    packet = build_codex_background_task_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_background_task_inventory"]


def test_dataclass_like_task_is_accepted_by_summarizer() -> None:
    @dataclass
    class Task:
        task_id: str
        task_type: str
        state: str
        queue_state: str
        resumable: bool
        retry_policy: str
        branch_ref: str
        worktree_ref: str
        handoff_ref: str
        notification_ref: str
        artifact_refs: list[str]
        validation_refs: list[str]
        diff_refs: list[str]

    task = summarize_codex_background_task(
        Task(
            "task-5",
            "background",
            "queued",
            "queued",
            True,
            "retry",
            "branch",
            "worktree",
            "handoff",
            "notification",
            ["artifact"],
            ["validation"],
            ["diff"],
        )
    )

    assert task.task_id == "task-5"
    assert task.task_type == "background"
    assert task.readiness_state == "ready"
