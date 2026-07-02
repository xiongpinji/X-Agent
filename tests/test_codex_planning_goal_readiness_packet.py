from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_planning_goal_readiness_packet import (
    build_codex_planning_goal_readiness_packet,
    summarize_codex_planning_goal,
)


PACKET_POLICIES = {
    "planning_policy": "planning-policy",
    "goal_policy": "goal-policy",
    "approval_policy": "approval-policy",
    "completion_policy": "completion-policy",
    "planning_manifest_ref": "planning-manifest",
    "goal_matrix_ref": "goal-matrix",
}


def test_ready_planning_goal_has_execution_evidence() -> None:
    packet = build_codex_planning_goal_readiness_packet(
        {
            **PACKET_POLICIES,
            "goals": [
                {
                    "goal_id": "goal-1",
                    "status": "approved",
                    "owner_ref": "owner-a",
                    "plan_refs": ["plan"],
                    "goal_refs": ["goal"],
                    "task_decomposition_refs": ["tasks"],
                    "progress_checkpoint_refs": ["checkpoint"],
                    "user_approval_refs": ["approval"],
                    "interruption_resume_refs": ["resume-policy"],
                    "completion_criteria_refs": ["done-criteria"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_planning_goal_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["goal_count"] == 1
    assert packet["summary"]["approval_ref_count"] == 1
    assert packet["next_actions"] == ["share_planning_goal_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_planning_goal_readiness_packet(
        {
            "goals": [
                {
                    "goal_id": "goal-1",
                    "status": "approved",
                    "owner_ref": "owner-a",
                    "plan_refs": ["plan"],
                    "goal_refs": ["goal"],
                    "task_decomposition_refs": ["tasks"],
                    "progress_checkpoint_refs": ["checkpoint"],
                    "user_approval_refs": ["approval"],
                    "completion_criteria_refs": ["criteria"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_planning_goal_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "planning_policy_ref",
        "goal_policy_ref",
        "approval_policy_ref",
        "completion_policy_ref",
        "planning_manifest_ref",
        "goal_matrix_ref",
    ]


def test_blocked_goal_requires_resume_refs_and_blocks() -> None:
    packet = build_codex_planning_goal_readiness_packet(
        {
            **PACKET_POLICIES,
            "goals": [
                {
                    "goal_id": "goal-2",
                    "status": "blocked",
                    "owner_ref": "owner-a",
                    "plan_refs": ["plan"],
                    "goal_refs": ["goal"],
                    "task_decomposition_refs": ["tasks"],
                    "progress_checkpoint_refs": ["checkpoint"],
                    "user_approval_refs": ["approval"],
                    "completion_criteria_refs": ["criteria"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    goal = packet["goals"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_planning_goal_status_failed"
    assert "interruption_resume_refs" in goal["missing_refs"]
    assert packet["next_actions"] == ["resolve_planning_goal_blockers", "refresh_planning_goal_readiness"]


def test_missing_plan_task_checkpoint_approval_and_completion_refs_needs_review() -> None:
    goal = summarize_codex_planning_goal(
        {
            "goal_id": "goal-3",
            "status": "planned",
            "owner_ref": "owner-a",
            "goal_refs": ["goal"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert goal.readiness_state == "needs_review"
    assert "plan_refs" in goal.missing_refs
    assert "task_decomposition_refs" in goal.missing_refs
    assert "progress_checkpoint_refs" in goal.missing_refs
    assert "user_approval_refs" in goal.missing_refs
    assert "completion_criteria_refs" in goal.missing_refs


def test_live_planner_or_goal_state_mutation_attempt_blocks_candidate() -> None:
    packet = build_codex_planning_goal_readiness_packet(
        {
            **PACKET_POLICIES,
            "goals": [
                {
                    "goal_id": "goal-4",
                    "status": "validated",
                    "owner_ref": "owner-a",
                    "plan_refs": ["plan"],
                    "goal_refs": ["goal"],
                    "task_decomposition_refs": ["tasks"],
                    "progress_checkpoint_refs": ["checkpoint"],
                    "user_approval_refs": ["approval"],
                    "interruption_resume_refs": ["resume"],
                    "completion_criteria_refs": ["criteria"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "goal_state_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_planning_goal_live_mutation_blocked"
    assert "live_planning_goal_mutation_attempted" in packet["goals"][0]["blockers"]


def test_empty_payload_requests_planning_goal_inventory() -> None:
    packet = build_codex_planning_goal_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_planning_goal_inventory"]


def test_dataclass_like_goal_is_accepted_by_summarizer() -> None:
    @dataclass
    class Goal:
        goal_id: str
        status: str
        owner_ref: str
        plan_refs: list[str]
        goal_refs: list[str]
        task_decomposition_refs: list[str]
        progress_checkpoint_refs: list[str]
        user_approval_refs: list[str]
        interruption_resume_refs: list[str]
        completion_criteria_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    goal = summarize_codex_planning_goal(
        Goal(
            "goal-5",
            "checkpointed",
            "owner-a",
            ["plan"],
            ["goal"],
            ["tasks"],
            ["checkpoint"],
            ["approval"],
            ["resume"],
            ["criteria"],
            ["validation"],
            ["artifact"],
        )
    )

    assert goal.goal_id == "goal-5"
    assert goal.status == "checkpointed"
    assert goal.readiness_state == "ready"
