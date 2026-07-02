from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_collaboration_subagent_readiness_packet import (
    build_codex_collaboration_subagent_readiness_packet,
    summarize_codex_collaboration_subagent,
)


PACKET_POLICIES = {
    "collaboration_policy": "collaboration-policy",
    "assignment_policy": "assignment-policy",
    "handoff_policy": "handoff-policy",
    "aggregation_policy": "aggregation-policy",
    "collaboration_manifest_ref": "collaboration-manifest",
    "coordination_governance_ref": "coordination-governance",
}


def test_ready_collaboration_subagent_has_coordination_evidence() -> None:
    packet = build_codex_collaboration_subagent_readiness_packet(
        {
            **PACKET_POLICIES,
            "collaborations": [
                {
                    "collaboration_id": "collab-1",
                    "status": "aggregated",
                    "subagent_request_ref": "request",
                    "assignment_refs": ["assignment"],
                    "worker_thread_refs": ["worker"],
                    "handoff_refs": ["handoff"],
                    "partial_result_refs": ["partial"],
                    "aggregation_refs": ["aggregation"],
                    "timeout_refs": ["timeout"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_collaboration_subagent_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["collaboration_count"] == 1
    assert packet["summary"]["aggregation_ref_count"] == 1
    assert packet["next_actions"] == ["share_collaboration_subagent_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_collaboration_subagent_readiness_packet(
        {
            "collaborations": [
                {
                    "collaboration_id": "collab-1",
                    "status": "recorded",
                    "subagent_request_ref": "request",
                    "assignment_refs": ["assignment"],
                    "worker_thread_refs": ["worker"],
                    "handoff_refs": ["handoff"],
                    "partial_result_refs": ["partial"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_collaboration_subagent_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "collaboration_policy_ref",
        "assignment_policy_ref",
        "handoff_policy_ref",
        "aggregation_policy_ref",
        "collaboration_manifest_ref",
        "coordination_governance_ref",
    ]


def test_timeout_or_failed_collaboration_requires_timeout_refs_and_blocks() -> None:
    packet = build_codex_collaboration_subagent_readiness_packet(
        {
            **PACKET_POLICIES,
            "collaborations": [
                {
                    "collaboration_id": "collab-2",
                    "status": "timed-out",
                    "subagent_request_ref": "request",
                    "assignment_refs": ["assignment"],
                    "worker_thread_refs": ["worker"],
                    "handoff_refs": ["handoff"],
                    "partial_result_refs": ["partial"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    collaboration = packet["collaborations"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_collaboration_subagent_status_failed"
    assert "timeout_refs" in collaboration["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_collaboration_subagent_blockers",
        "refresh_collaboration_subagent_readiness",
    ]


def test_ready_collaboration_requires_aggregation_refs() -> None:
    collaboration = summarize_codex_collaboration_subagent(
        {
            "collaboration_id": "collab-3",
            "status": "passed",
            "subagent_request_ref": "request",
            "assignment_refs": ["assignment"],
            "worker_thread_refs": ["worker"],
            "handoff_refs": ["handoff"],
            "partial_result_refs": ["partial"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert collaboration.readiness_state == "needs_review"
    assert "aggregation_refs" in collaboration.missing_refs


def test_missing_assignment_worker_handoff_and_partial_refs_needs_review() -> None:
    collaboration = summarize_codex_collaboration_subagent(
        {
            "collaboration_id": "collab-4",
            "status": "recorded",
            "subagent_request_ref": "request",
            "artifact_refs": ["artifact"],
        }
    )

    assert collaboration.readiness_state == "needs_review"
    assert "assignment_refs" in collaboration.missing_refs
    assert "worker_thread_refs" in collaboration.missing_refs
    assert "handoff_refs" in collaboration.missing_refs
    assert "partial_result_refs" in collaboration.missing_refs
    assert "validation_receipt_refs" in collaboration.missing_refs


def test_live_subagent_spawn_or_handoff_attempt_blocks_candidate() -> None:
    packet = build_codex_collaboration_subagent_readiness_packet(
        {
            **PACKET_POLICIES,
            "collaborations": [
                {
                    "collaboration_id": "collab-5",
                    "status": "recorded",
                    "subagent_request_ref": "request",
                    "assignment_refs": ["assignment"],
                    "worker_thread_refs": ["worker"],
                    "handoff_refs": ["handoff"],
                    "partial_result_refs": ["partial"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "subagent_spawn_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_collaboration_subagent_live_execution_blocked"
    assert "live_collaboration_subagent_execution_attempted" in packet["collaborations"][0]["blockers"]


def test_empty_payload_requests_collaboration_subagent_inventory() -> None:
    packet = build_codex_collaboration_subagent_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_collaboration_subagent_inventory"]


def test_dataclass_like_collaboration_is_accepted_by_summarizer() -> None:
    @dataclass
    class Collaboration:
        collaboration_id: str
        status: str
        subagent_request_ref: str
        assignment_refs: list[str]
        worker_thread_refs: list[str]
        handoff_refs: list[str]
        partial_result_refs: list[str]
        aggregation_refs: list[str]
        timeout_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    collaboration = summarize_codex_collaboration_subagent(
        Collaboration(
            "collab-6",
            "passed",
            "request",
            ["assignment"],
            ["worker"],
            ["handoff"],
            ["partial"],
            ["aggregation"],
            ["timeout"],
            ["validation"],
            ["artifact"],
        )
    )

    assert collaboration.collaboration_id == "collab-6"
    assert collaboration.status == "passed"
    assert collaboration.readiness_state == "ready"
