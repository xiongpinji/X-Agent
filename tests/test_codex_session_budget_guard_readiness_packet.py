from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_session_budget_guard_readiness_packet import (
    build_codex_session_budget_guard_readiness_packet,
    summarize_codex_session_budget_guard,
)


PACKET_POLICIES = {
    "token_budget_policy": "token-budget-policy",
    "elapsed_time_policy": "elapsed-time-policy",
    "retry_budget_policy": "retry-budget-policy",
    "tool_call_budget_policy": "tool-call-budget-policy",
    "session_budget_manifest_ref": "session-budget-manifest",
    "bounded_execution_governance_ref": "bounded-execution-governance",
}


def test_ready_session_budget_guard_has_bounded_execution_evidence() -> None:
    packet = build_codex_session_budget_guard_readiness_packet(
        {
            **PACKET_POLICIES,
            "budgets": [
                {
                    "budget_id": "budget-1",
                    "status": "guarded",
                    "session_ref": "session",
                    "token_budget_refs": ["tokens"],
                    "elapsed_time_refs": ["elapsed"],
                    "retry_budget_refs": ["retry"],
                    "tool_call_budget_refs": ["tools"],
                    "context_compaction_threshold_refs": ["compaction"],
                    "interruption_refs": ["interrupt"],
                    "cancellation_policy_refs": ["cancel"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_session_budget_guard_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["budget_count"] == 1
    assert packet["summary"]["tool_call_budget_ref_count"] == 1
    assert packet["next_actions"] == ["share_session_budget_guard_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_session_budget_guard_readiness_packet(
        {
            "budgets": [
                {
                    "budget_id": "budget-2",
                    "status": "guarded",
                    "session_ref": "session",
                    "token_budget_refs": ["tokens"],
                    "elapsed_time_refs": ["elapsed"],
                    "retry_budget_refs": ["retry"],
                    "tool_call_budget_refs": ["tools"],
                    "context_compaction_threshold_refs": ["compaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_session_budget_guard_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "token_budget_policy_ref",
        "elapsed_time_policy_ref",
        "retry_budget_policy_ref",
        "tool_call_budget_policy_ref",
        "session_budget_manifest_ref",
        "bounded_execution_governance_ref",
    ]


def test_missing_token_time_retry_tool_and_compaction_refs_needs_review() -> None:
    budget = summarize_codex_session_budget_guard(
        {
            "budget_id": "budget-3",
            "status": "guarded",
            "session_ref": "session",
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert budget.readiness_state == "needs_review"
    assert "token_budget_refs" in budget.missing_refs
    assert "elapsed_time_refs" in budget.missing_refs
    assert "retry_budget_refs" in budget.missing_refs
    assert "tool_call_budget_refs" in budget.missing_refs
    assert "context_compaction_threshold_refs" in budget.missing_refs


def test_failed_or_exhausted_budget_requires_interruption_and_cancellation_refs() -> None:
    packet = build_codex_session_budget_guard_readiness_packet(
        {
            **PACKET_POLICIES,
            "budgets": [
                {
                    "budget_id": "budget-4",
                    "status": "exhausted",
                    "session_ref": "session",
                    "token_budget_refs": ["tokens"],
                    "elapsed_time_refs": ["elapsed"],
                    "retry_budget_refs": ["retry"],
                    "tool_call_budget_refs": ["tools"],
                    "context_compaction_threshold_refs": ["compaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    budget = packet["budgets"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_session_budget_guard_status_failed"
    assert "interruption_refs" in budget["missing_refs"]
    assert "cancellation_policy_refs" in budget["missing_refs"]


def test_detected_over_budget_condition_blocks_candidate() -> None:
    packet = build_codex_session_budget_guard_readiness_packet(
        {
            **PACKET_POLICIES,
            "budgets": [
                {
                    "budget_id": "budget-5",
                    "status": "guarded",
                    "session_ref": "session",
                    "token_budget_refs": ["tokens"],
                    "elapsed_time_refs": ["elapsed"],
                    "retry_budget_refs": ["retry"],
                    "tool_call_budget_refs": ["tools"],
                    "context_compaction_threshold_refs": ["compaction"],
                    "interruption_refs": ["interrupt"],
                    "cancellation_policy_refs": ["cancel"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "over_budget_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_session_budget_guard_exhausted"
    assert "session_budget_exhausted" in packet["budgets"][0]["blockers"]


def test_live_budget_enforcement_or_scheduler_mutation_blocks_candidate() -> None:
    packet = build_codex_session_budget_guard_readiness_packet(
        {
            **PACKET_POLICIES,
            "budgets": [
                {
                    "budget_id": "budget-6",
                    "status": "guarded",
                    "session_ref": "session",
                    "token_budget_refs": ["tokens"],
                    "elapsed_time_refs": ["elapsed"],
                    "retry_budget_refs": ["retry"],
                    "tool_call_budget_refs": ["tools"],
                    "context_compaction_threshold_refs": ["compaction"],
                    "interruption_refs": ["interrupt"],
                    "cancellation_policy_refs": ["cancel"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "scheduler_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_session_budget_guard_live_operation_blocked"
    assert "live_session_budget_guard_operation_attempted" in packet["budgets"][0]["blockers"]


def test_empty_payload_requests_session_budget_inventory() -> None:
    packet = build_codex_session_budget_guard_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_session_budget_guard_inventory"]


def test_dataclass_like_session_budget_guard_is_accepted_by_summarizer() -> None:
    @dataclass
    class SessionBudget:
        budget_id: str
        status: str
        session_ref: str
        token_budget_refs: list[str]
        elapsed_time_refs: list[str]
        retry_budget_refs: list[str]
        tool_call_budget_refs: list[str]
        context_compaction_threshold_refs: list[str]
        interruption_refs: list[str]
        cancellation_policy_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    budget = summarize_codex_session_budget_guard(
        SessionBudget(
            "budget-7",
            "validated",
            "session",
            ["tokens"],
            ["elapsed"],
            ["retry"],
            ["tools"],
            ["compaction"],
            ["interrupt"],
            ["cancel"],
            ["validation"],
            ["artifact"],
        )
    )

    assert budget.budget_id == "budget-7"
    assert budget.status == "validated"
    assert budget.readiness_state == "ready"
