from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_ci_gate_readiness_packet import (
    build_codex_ci_gate_readiness_packet,
    summarize_codex_ci_gate,
)


PACKET_POLICIES = {
    "required_check_policy": "required-check-policy",
    "workflow_policy": "workflow-policy",
    "artifact_policy": "artifact-policy",
    "review_posting_policy": "review-posting-policy",
    "ci_manifest_ref": "ci-manifest",
}


def test_ready_github_actions_gate_with_checks_artifacts_and_review_posting() -> None:
    packet = build_codex_ci_gate_readiness_packet(
        {
            **PACKET_POLICIES,
            "gates": [
                {
                    "gate_id": "gate-1",
                    "provider": "github-actions",
                    "gate_status": "success",
                    "workflow_refs": ["codex-review.yml"],
                    "check_run_refs": ["check-run-1"],
                    "status_contexts": ["Codex Review"],
                    "check_states": ["success", "passed"],
                    "artifact_refs": ["codex-review.json"],
                    "required_check_refs": ["required-checks"],
                    "review_result_posting_refs": ["posted-review"],
                    "validation_refs": ["validation-receipt"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_ci_gate_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["gate_count"] == 1
    assert packet["summary"]["review_posting_ref_count"] == 1
    assert packet["next_actions"] == ["share_ci_gate_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_ci_gate_readiness_packet(
        {
            "gates": [
                {
                    "gate_id": "gate-1",
                    "provider": "github-actions",
                    "gate_status": "success",
                    "workflow_refs": ["workflow"],
                    "check_run_refs": ["check"],
                    "status_contexts": ["context"],
                    "check_states": ["success"],
                    "artifact_refs": ["artifact"],
                    "required_check_refs": ["required"],
                    "review_result_posting_refs": ["posted"],
                    "validation_refs": ["validation"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_ci_gate_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "required_check_policy_ref",
        "workflow_policy_ref",
        "artifact_policy_ref",
        "review_posting_policy_ref",
        "ci_manifest_ref",
    ]


def test_failed_check_state_blocks_gate_and_requires_failure_summary() -> None:
    packet = build_codex_ci_gate_readiness_packet(
        {
            **PACKET_POLICIES,
            "gates": [
                {
                    "gate_id": "gate-2",
                    "provider": "github-actions",
                    "gate_status": "success",
                    "workflow_refs": ["workflow"],
                    "check_run_refs": ["check"],
                    "status_contexts": ["context"],
                    "check_states": ["failed"],
                    "artifact_refs": ["artifact"],
                    "required_check_refs": ["required"],
                    "review_result_posting_refs": ["posted"],
                    "validation_refs": ["validation"],
                }
            ],
        }
    )

    gate = packet["gates"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_ci_gate_check_failed"
    assert "failure_summaries" in gate["missing_refs"]
    assert "retry_or_rerun_refs" in gate["missing_refs"]


def test_running_gate_needs_review_until_completion() -> None:
    gate = summarize_codex_ci_gate(
        {
            "gate_id": "gate-3",
            "provider": "github-actions",
            "gate_status": "running",
            "workflow_refs": ["workflow"],
            "check_run_refs": ["check"],
            "status_contexts": ["context"],
            "check_states": ["running"],
            "artifact_refs": ["artifact"],
            "required_check_refs": ["required"],
            "retry_refs": ["retry"],
            "review_result_posting_refs": ["posted"],
            "validation_refs": ["validation"],
        }
    )

    assert gate.readiness_state == "needs_review"
    assert "ci_gate_still_running" in gate.warnings
    assert "ci_check_state_needs_review" in gate.warnings


def test_missing_workflow_check_status_artifact_and_posting_refs_needs_review() -> None:
    packet = build_codex_ci_gate_readiness_packet(
        {
            **PACKET_POLICIES,
            "gates": [{"gate_id": "gate-4", "provider": "github-actions", "gate_status": "success"}],
        }
    )

    gate = packet["gates"][0]
    assert packet["status"] == "needs_review"
    assert "workflow_refs" in gate["missing_refs"]
    assert "check_run_refs" in gate["missing_refs"]
    assert "status_contexts" in gate["missing_refs"]
    assert "artifact_refs" in gate["missing_refs"]
    assert "review_result_posting_refs" in gate["missing_refs"]


def test_empty_payload_requests_ci_gate_inventory() -> None:
    packet = build_codex_ci_gate_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_ci_gate_inventory"]


def test_dataclass_like_gate_is_accepted_by_summarizer() -> None:
    @dataclass
    class Gate:
        gate_id: str
        provider: str
        gate_status: str
        workflow_refs: list[str]
        check_run_refs: list[str]
        status_contexts: list[str]
        check_states: list[str]
        artifact_refs: list[str]
        required_check_refs: list[str]
        review_result_posting_refs: list[str]
        validation_refs: list[str]

    gate = summarize_codex_ci_gate(
        Gate(
            "gate-5",
            "github-actions",
            "success",
            ["workflow"],
            ["check"],
            ["context"],
            ["success"],
            ["artifact"],
            ["required"],
            ["posted"],
            ["validation"],
        )
    )

    assert gate.gate_id == "gate-5"
    assert gate.provider == "github_actions"
    assert gate.readiness_state == "ready"
