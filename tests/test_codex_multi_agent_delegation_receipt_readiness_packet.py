from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_multi_agent_delegation_receipt_readiness_packet import (
    build_codex_multi_agent_delegation_receipt_readiness_packet,
    summarize_codex_multi_agent_delegation_receipt,
)


PACKET_POLICIES = {
    "delegation_policy": "delegation-policy",
    "scope_policy": "scope-policy",
    "handoff_policy": "handoff-policy",
    "completion_policy": "completion-policy",
    "delegation_manifest_ref": "delegation-manifest",
    "multi_agent_governance_ref": "multi-agent-governance",
}


def test_ready_multi_agent_delegation_receipt_has_handoff_and_completion_evidence() -> None:
    packet = build_codex_multi_agent_delegation_receipt_readiness_packet(
        {
            **PACKET_POLICIES,
            "delegations": [
                {
                    "delegation_id": "delegation-1",
                    "status": "completed",
                    "delegation_ref": "delegation",
                    "source_thread_ref": "source-thread",
                    "target_thread_refs": ["target-thread"],
                    "scope_refs": ["scope"],
                    "handoff_refs": ["handoff"],
                    "completion_receipt_refs": ["completion"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_multi_agent_delegation_receipt_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["delegation_count"] == 1
    assert packet["summary"]["completion_receipt_ref_count"] == 1
    assert packet["next_actions"] == ["share_multi_agent_delegation_receipt_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_multi_agent_delegation_receipt_readiness_packet(
        {
            "delegations": [
                {
                    "delegation_id": "delegation-2",
                    "status": "delegated",
                    "delegation_ref": "delegation",
                    "source_thread_ref": "source-thread",
                    "target_thread_refs": ["target-thread"],
                    "scope_refs": ["scope"],
                    "handoff_refs": ["handoff"],
                    "completion_receipt_refs": ["completion"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_multi_agent_delegation_receipt_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "delegation_policy_ref",
        "scope_policy_ref",
        "handoff_policy_ref",
        "completion_policy_ref",
        "delegation_manifest_ref",
        "multi_agent_governance_ref",
    ]


def test_timeout_or_failed_delegation_blocks_candidate() -> None:
    packet = build_codex_multi_agent_delegation_receipt_readiness_packet(
        {
            **PACKET_POLICIES,
            "delegations": [
                {
                    "delegation_id": "delegation-3",
                    "status": "timed-out",
                    "delegation_ref": "delegation",
                    "source_thread_ref": "source-thread",
                    "target_thread_refs": ["target-thread"],
                    "scope_refs": ["scope"],
                    "handoff_refs": ["handoff"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    delegation = packet["delegations"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_multi_agent_delegation_receipt_status_failed"
    assert "multi_agent_delegation_status_failed" in delegation["blockers"]
    assert packet["next_actions"] == [
        "resolve_multi_agent_delegation_receipt_blockers",
        "refresh_multi_agent_delegation_receipt_readiness",
    ]


def test_missing_delegation_source_target_scope_handoff_validation_artifact_owner_refs_needs_review() -> None:
    delegation = summarize_codex_multi_agent_delegation_receipt(
        {
            "delegation_id": "delegation-4",
            "status": "delegated",
        }
    )

    assert delegation.readiness_state == "needs_review"
    assert "delegation_ref" in delegation.missing_refs
    assert "source_thread_ref" in delegation.missing_refs
    assert "target_thread_refs" in delegation.missing_refs
    assert "scope_refs" in delegation.missing_refs
    assert "handoff_refs" in delegation.missing_refs
    assert "validation_receipt_refs" in delegation.missing_refs
    assert "artifact_refs" in delegation.missing_refs
    assert "owner_refs" in delegation.missing_refs


def test_completed_or_validated_delegation_requires_completion_receipts() -> None:
    delegation = summarize_codex_multi_agent_delegation_receipt(
        {
            "delegation_id": "delegation-5",
            "status": "validated",
            "delegation_ref": "delegation",
            "source_thread_ref": "source-thread",
            "target_thread_refs": ["target-thread"],
            "scope_refs": ["scope"],
            "handoff_refs": ["handoff"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "owner_refs": ["owner"],
        }
    )

    assert delegation.readiness_state == "needs_review"
    assert "completion_receipt_refs" in delegation.missing_refs


def test_open_delegation_waits_for_completion() -> None:
    packet = build_codex_multi_agent_delegation_receipt_readiness_packet(
        {
            **PACKET_POLICIES,
            "delegations": [
                {
                    "delegation_id": "delegation-6",
                    "status": "running",
                    "delegation_ref": "delegation",
                    "source_thread_ref": "source-thread",
                    "target_thread_refs": ["target-thread"],
                    "scope_refs": ["scope"],
                    "handoff_refs": ["handoff"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_multi_agent_delegation_receipt_still_open"
    assert packet["next_actions"] == [
        "wait_for_multi_agent_delegation_completion",
        "attach_multi_agent_delegation_receipts",
    ]


def test_live_thread_creation_agent_dispatch_or_delegation_mutation_blocks_candidate() -> None:
    packet = build_codex_multi_agent_delegation_receipt_readiness_packet(
        {
            **PACKET_POLICIES,
            "delegations": [
                {
                    "delegation_id": "delegation-7",
                    "status": "delegated",
                    "delegation_ref": "delegation",
                    "source_thread_ref": "source-thread",
                    "target_thread_refs": ["target-thread"],
                    "scope_refs": ["scope"],
                    "handoff_refs": ["handoff"],
                    "completion_receipt_refs": ["completion"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "agent_dispatch_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_multi_agent_delegation_receipt_live_operation_blocked"
    assert "live_multi_agent_delegation_operation_attempted" in packet["delegations"][0]["blockers"]


def test_empty_payload_requests_multi_agent_delegation_receipt_inventory() -> None:
    packet = build_codex_multi_agent_delegation_receipt_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_multi_agent_delegation_receipt_inventory"]


def test_dataclass_like_multi_agent_delegation_receipt_is_accepted_by_summarizer() -> None:
    @dataclass
    class MultiAgentDelegationReceipt:
        delegation_id: str
        status: str
        delegation_ref: str
        source_thread_ref: str
        target_thread_refs: list[str]
        scope_refs: list[str]
        handoff_refs: list[str]
        completion_receipt_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]

    delegation = summarize_codex_multi_agent_delegation_receipt(
        MultiAgentDelegationReceipt(
            "delegation-8",
            "accepted",
            "delegation",
            "source-thread",
            ["target-thread"],
            ["scope"],
            ["handoff"],
            ["completion"],
            ["validation"],
            ["artifact"],
            ["owner"],
        )
    )

    assert delegation.delegation_id == "delegation-8"
    assert delegation.status == "accepted"
    assert delegation.readiness_state == "ready"
