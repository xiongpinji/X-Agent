from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_interruption_recovery_readiness_packet import (
    build_codex_interruption_recovery_readiness_packet,
    summarize_codex_interruption_recovery,
)


PACKET_POLICIES = {
    "interruption_policy": "interruption-policy",
    "recovery_policy": "recovery-policy",
    "resume_policy": "resume-policy",
    "partial_progress_policy": "partial-progress-policy",
    "interruption_recovery_manifest_ref": "interruption-recovery-manifest",
    "failure_recovery_governance_ref": "failure-recovery-governance",
}


def test_ready_interruption_recovery_has_resume_evidence() -> None:
    packet = build_codex_interruption_recovery_readiness_packet(
        {
            **PACKET_POLICIES,
            "recoveries": [
                {
                    "recovery_id": "recovery-1",
                    "status": "ready",
                    "task_ref": "task",
                    "interruption_refs": ["interruption"],
                    "resumability_refs": ["resumability"],
                    "failure_recovery_refs": ["failure-recovery"],
                    "partial_progress_refs": ["partial-progress"],
                    "recovery_validation_refs": ["validation"],
                    "resume_token_refs": ["resume-token"],
                    "recovery_plan_refs": ["recovery-plan"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_interruption_recovery_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["recovery_count"] == 1
    assert packet["summary"]["interruption_ref_count"] == 1
    assert packet["next_actions"] == ["share_interruption_recovery_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_interruption_recovery_readiness_packet(
        {
            "recoveries": [
                {
                    "recovery_id": "recovery-2",
                    "status": "ready",
                    "task_ref": "task",
                    "interruption_refs": ["interruption"],
                    "resumability_refs": ["resumability"],
                    "failure_recovery_refs": ["failure-recovery"],
                    "partial_progress_refs": ["partial-progress"],
                    "recovery_validation_refs": ["validation"],
                    "resume_token_refs": ["resume-token"],
                    "recovery_plan_refs": ["recovery-plan"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_interruption_recovery_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "interruption_policy_ref",
        "recovery_policy_ref",
        "resume_policy_ref",
        "partial_progress_policy_ref",
        "interruption_recovery_manifest_ref",
        "failure_recovery_governance_ref",
    ]


def test_failed_recovery_requires_validation_and_blocks() -> None:
    packet = build_codex_interruption_recovery_readiness_packet(
        {
            **PACKET_POLICIES,
            "recoveries": [
                {
                    "recovery_id": "recovery-3",
                    "status": "failed",
                    "task_ref": "task",
                    "interruption_refs": ["interruption"],
                    "resumability_refs": ["resumability"],
                    "failure_recovery_refs": ["failure-recovery"],
                    "partial_progress_refs": ["partial-progress"],
                    "resume_token_refs": ["resume-token"],
                    "recovery_plan_refs": ["recovery-plan"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    recovery = packet["recoveries"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_interruption_recovery_status_failed"
    assert "recovery_validation_refs" in recovery["missing_refs"]


def test_missing_interruption_resumability_failure_partial_progress_and_resume_refs_needs_review() -> None:
    recovery = summarize_codex_interruption_recovery(
        {
            "recovery_id": "recovery-4",
            "status": "interrupted",
            "task_ref": "task",
            "artifact_refs": ["artifact"],
        }
    )

    assert recovery.readiness_state == "needs_review"
    assert "interruption_refs" in recovery.missing_refs
    assert "resumability_refs" in recovery.missing_refs
    assert "failure_recovery_refs" in recovery.missing_refs
    assert "partial_progress_refs" in recovery.missing_refs
    assert "resume_token_refs" in recovery.missing_refs
    assert "recovery_plan_refs" in recovery.missing_refs


def test_live_resume_or_recovery_execution_attempt_blocks_candidate() -> None:
    packet = build_codex_interruption_recovery_readiness_packet(
        {
            **PACKET_POLICIES,
            "recoveries": [
                {
                    "recovery_id": "recovery-5",
                    "status": "ready",
                    "task_ref": "task",
                    "interruption_refs": ["interruption"],
                    "resumability_refs": ["resumability"],
                    "failure_recovery_refs": ["failure-recovery"],
                    "partial_progress_refs": ["partial-progress"],
                    "recovery_validation_refs": ["validation"],
                    "resume_token_refs": ["resume-token"],
                    "recovery_plan_refs": ["recovery-plan"],
                    "artifact_refs": ["artifact"],
                    "resume_execution_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_interruption_recovery_live_operation_blocked"
    assert "live_interruption_recovery_operation_attempted" in packet["recoveries"][0]["blockers"]


def test_empty_payload_requests_interruption_recovery_inventory() -> None:
    packet = build_codex_interruption_recovery_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_interruption_recovery_inventory"]


def test_recovery_failure_flag_blocks_candidate() -> None:
    recovery = summarize_codex_interruption_recovery(
        {
            "recovery_id": "recovery-6",
            "status": "resumable",
            "task_ref": "task",
            "interruption_refs": ["interruption"],
            "resumability_refs": ["resumability"],
            "failure_recovery_refs": ["failure-recovery"],
            "partial_progress_refs": ["partial-progress"],
            "recovery_validation_refs": ["validation"],
            "resume_token_refs": ["resume-token"],
            "recovery_plan_refs": ["recovery-plan"],
            "artifact_refs": ["artifact"],
            "recovery_failed": True,
        }
    )

    assert recovery.readiness_state == "blocked"
    assert "interruption_recovery_failed" in recovery.blockers


def test_dataclass_like_recovery_is_accepted_by_summarizer() -> None:
    @dataclass
    class Recovery:
        recovery_id: str
        status: str
        task_ref: str
        interruption_refs: list[str]
        resumability_refs: list[str]
        failure_recovery_refs: list[str]
        partial_progress_refs: list[str]
        recovery_validation_refs: list[str]
        resume_token_refs: list[str]
        recovery_plan_refs: list[str]
        artifact_refs: list[str]

    recovery = summarize_codex_interruption_recovery(
        Recovery(
            "recovery-7",
            "closed",
            "task",
            ["interruption"],
            ["resumability"],
            ["failure-recovery"],
            ["partial-progress"],
            ["validation"],
            ["resume-token"],
            ["recovery-plan"],
            ["artifact"],
        )
    )

    assert recovery.recovery_id == "recovery-7"
    assert recovery.status == "closed"
    assert recovery.readiness_state == "ready"
