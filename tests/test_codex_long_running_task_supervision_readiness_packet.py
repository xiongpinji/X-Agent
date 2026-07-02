from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_long_running_task_supervision_readiness_packet import (
    build_codex_long_running_task_supervision_readiness_packet,
    summarize_codex_long_running_task_supervision,
)


PACKET_POLICIES = {
    "heartbeat_policy": "heartbeat-policy",
    "progress_policy": "progress-policy",
    "timeout_policy": "timeout-policy",
    "escalation_policy": "escalation-policy",
    "task_supervision_manifest_ref": "task_example_token_redacted",
    "durable_task_governance_ref": "durable-task-governance",
}


def test_ready_long_running_task_has_supervision_evidence() -> None:
    packet = build_codex_long_running_task_supervision_readiness_packet(
        {
            **PACKET_POLICIES,
            "tasks": [
                {
                    "task_id": "task-1",
                    "status": "supervised",
                    "task_ref": "task",
                    "heartbeat_refs": ["heartbeat"],
                    "progress_refs": ["progress"],
                    "supervision_refs": ["supervision"],
                    "timeout_refs": ["timeout"],
                    "escalation_refs": ["escalation"],
                    "checkpoint_refs": ["checkpoint"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_long_running_task_supervision_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["task_count"] == 1
    assert packet["summary"]["heartbeat_ref_count"] == 1
    assert packet["next_actions"] == ["share_long_running_task_supervision_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_long_running_task_supervision_readiness_packet(
        {
            "tasks": [
                {
                    "task_id": "task-2",
                    "status": "healthy",
                    "task_ref": "task",
                    "heartbeat_refs": ["heartbeat"],
                    "progress_refs": ["progress"],
                    "supervision_refs": ["supervision"],
                    "timeout_refs": ["timeout"],
                    "escalation_refs": ["escalation"],
                    "checkpoint_refs": ["checkpoint"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_long_running_task_supervision_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "heartbeat_policy_ref",
        "progress_policy_ref",
        "timeout_policy_ref",
        "escalation_policy_ref",
        "task_supervision_manifest_ref",
        "durable_task_governance_ref",
    ]


def test_failed_or_timed_out_task_requires_escalation_refs_and_blocks() -> None:
    packet = build_codex_long_running_task_supervision_readiness_packet(
        {
            **PACKET_POLICIES,
            "tasks": [
                {
                    "task_id": "task-3",
                    "status": "timed_out",
                    "task_ref": "task",
                    "heartbeat_refs": ["heartbeat"],
                    "progress_refs": ["progress"],
                    "supervision_refs": ["supervision"],
                    "timeout_refs": ["timeout"],
                    "checkpoint_refs": ["checkpoint"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    task = packet["tasks"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_long_running_task_supervision_status_failed"
    assert "escalation_refs" in task["missing_refs"]


def test_missing_heartbeat_progress_supervision_timeout_checkpoint_validation_artifact_needs_review() -> None:
    task = summarize_codex_long_running_task_supervision(
        {
            "task_id": "task-4",
            "status": "running",
            "task_ref": "task",
            "owner_refs": ["owner"],
        }
    )

    assert task.readiness_state == "needs_review"
    assert "heartbeat_refs" in task.missing_refs
    assert "progress_refs" in task.missing_refs
    assert "supervision_refs" in task.missing_refs
    assert "timeout_refs" in task.missing_refs
    assert "checkpoint_refs" in task.missing_refs
    assert "validation_receipt_refs" in task.missing_refs
    assert "artifact_refs" in task.missing_refs


def test_live_scheduler_worker_or_heartbeat_write_attempt_blocks_candidate() -> None:
    packet = build_codex_long_running_task_supervision_readiness_packet(
        {
            **PACKET_POLICIES,
            "tasks": [
                {
                    "task_id": "task-5",
                    "status": "healthy",
                    "task_ref": "task",
                    "heartbeat_refs": ["heartbeat"],
                    "progress_refs": ["progress"],
                    "supervision_refs": ["supervision"],
                    "timeout_refs": ["timeout"],
                    "escalation_refs": ["escalation"],
                    "checkpoint_refs": ["checkpoint"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "worker_dispatch_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_long_running_task_supervision_live_operation_blocked"
    assert "live_long_running_task_supervision_operation_attempted" in packet["tasks"][0]["blockers"]


def test_empty_payload_requests_long_running_task_supervision_inventory() -> None:
    packet = build_codex_long_running_task_supervision_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_long_running_task_supervision_inventory"]


def test_stale_heartbeat_or_timeout_detection_blocks_candidate() -> None:
    task = summarize_codex_long_running_task_supervision(
        {
            "task_id": "task-6",
            "status": "healthy",
            "task_ref": "task",
            "heartbeat_refs": ["heartbeat"],
            "progress_refs": ["progress"],
            "supervision_refs": ["supervision"],
            "timeout_refs": ["timeout"],
            "escalation_refs": ["escalation"],
            "checkpoint_refs": ["checkpoint"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "owner_refs": ["owner"],
            "heartbeat_stale": True,
        }
    )

    assert task.readiness_state == "blocked"
    assert "long_running_task_heartbeat_stale" in task.blockers


def test_dataclass_like_task_supervision_is_accepted_by_summarizer() -> None:
    @dataclass
    class TaskSupervision:
        task_id: str
        status: str
        task_ref: str
        heartbeat_refs: list[str]
        progress_refs: list[str]
        supervision_refs: list[str]
        timeout_refs: list[str]
        escalation_refs: list[str]
        checkpoint_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]

    task = summarize_codex_long_running_task_supervision(
        TaskSupervision(
            "task-7",
            "closed",
            "task",
            ["heartbeat"],
            ["progress"],
            ["supervision"],
            ["timeout"],
            ["escalation"],
            ["checkpoint"],
            ["validation"],
            ["artifact"],
            ["owner"],
        )
    )

    assert task.task_id == "task-7"
    assert task.status == "closed"
    assert task.readiness_state == "ready"
