from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_observability_trace_readiness_packet import (
    build_codex_observability_trace_readiness_packet,
    summarize_codex_observability_trace,
)


PACKET_POLICIES = {
    "trace_schema_policy": "trace-schema-policy",
    "redaction_policy": "redaction-policy",
    "retention_policy": "retention-policy",
    "export_policy": "export-policy",
    "trace_manifest_ref": "trace-manifest",
    "audit_access_policy": "audit-access-policy",
}


def test_ready_auditable_agent_run_trace_has_all_codex_refs() -> None:
    packet = build_codex_observability_trace_readiness_packet(
        {
            **PACKET_POLICIES,
            "traces": [
                {
                    "trace_id": "trace-1",
                    "run_ref": "run-1",
                    "status": "completed",
                    "source": "agent-run",
                    "provider": "otel",
                    "run_trace_refs": ["run-trace"],
                    "tool_call_trace_refs": ["tool-call-trace"],
                    "model_decision_refs": ["model-decision"],
                    "permission_prompt_refs": ["permission-prompt"],
                    "sandbox_event_refs": ["sandbox-event"],
                    "validation_receipt_refs": ["validation-receipt"],
                    "redaction_refs": ["redaction"],
                    "error_taxonomy_refs": ["error-taxonomy"],
                    "retention_policy_refs": ["retention-policy"],
                    "export_policy_refs": ["export-policy"],
                    "telemetry_export_refs": ["otel-export"],
                    "audit_log_refs": ["audit-log"],
                    "replay_refs": ["replay"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_observability_trace_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["trace_count"] == 1
    assert packet["summary"]["tool_call_trace_ref_count"] == 1
    assert packet["next_actions"] == ["share_observability_trace_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_observability_trace_readiness_packet(
        {
            "traces": [
                {
                    "trace_id": "trace-1",
                    "run_ref": "run-1",
                    "status": "completed",
                    "source": "validation",
                    "provider": "local",
                    "run_trace_refs": ["run-trace"],
                    "tool_call_trace_refs": ["tool-call"],
                    "model_decision_refs": ["model"],
                    "validation_receipt_refs": ["validation"],
                    "redaction_refs": ["redaction"],
                    "retention_policy_refs": ["retention"],
                    "export_policy_refs": ["export"],
                    "audit_log_refs": ["audit"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_observability_trace_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "trace_schema_policy_ref",
        "redaction_policy_ref",
        "retention_policy_ref",
        "export_policy_ref",
        "trace_manifest_ref",
        "audit_access_policy_ref",
    ]


def test_failed_trace_without_error_taxonomy_blocks() -> None:
    packet = build_codex_observability_trace_readiness_packet(
        {
            **PACKET_POLICIES,
            "traces": [
                {
                    "trace_id": "trace-2",
                    "run_ref": "run-2",
                    "status": "failed",
                    "source": "agent_run",
                    "provider": "local",
                    "run_trace_refs": ["run-trace"],
                    "tool_call_trace_refs": ["tool-call"],
                    "model_decision_refs": ["model"],
                    "permission_prompt_refs": ["permission"],
                    "sandbox_event_refs": ["sandbox"],
                    "validation_receipt_refs": ["validation"],
                    "redaction_refs": ["redaction"],
                    "retention_policy_refs": ["retention"],
                    "export_policy_refs": ["export"],
                    "audit_log_refs": ["audit"],
                    "replay_refs": ["replay"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    trace = packet["traces"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_observability_trace_status_failed"
    assert "error_taxonomy_refs" in trace["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_observability_trace_blockers",
        "refresh_observability_trace_readiness",
    ]


def test_permission_and_sandbox_surfaces_require_specific_refs() -> None:
    trace = summarize_codex_observability_trace(
        {
            "trace_id": "trace-3",
            "run_ref": "run-3",
            "status": "completed",
            "source": "tool-call",
            "provider": "custom",
            "run_trace_refs": ["run-trace"],
            "tool_call_trace_refs": ["tool-call"],
            "model_decision_refs": ["model"],
            "validation_receipt_refs": ["validation"],
            "redaction_refs": ["redaction"],
            "retention_policy_refs": ["retention"],
            "export_policy_refs": ["export"],
            "audit_log_refs": ["audit"],
            "artifact_refs": ["artifact"],
        }
    )

    assert trace.readiness_state == "needs_review"
    assert "permission_prompt_refs" in trace.missing_refs
    assert "sandbox_event_refs" in trace.missing_refs


def test_live_export_or_mutation_attempt_blocks_secondary_candidate() -> None:
    packet = build_codex_observability_trace_readiness_packet(
        {
            **PACKET_POLICIES,
            "traces": [
                {
                    "trace_id": "trace-4",
                    "run_ref": "run-4",
                    "status": "completed",
                    "source": "validation",
                    "provider": "otel",
                    "run_trace_refs": ["run-trace"],
                    "tool_call_trace_refs": ["tool-call"],
                    "model_decision_refs": ["model"],
                    "validation_receipt_refs": ["validation"],
                    "redaction_refs": ["redaction"],
                    "error_taxonomy_refs": ["error-taxonomy"],
                    "retention_policy_refs": ["retention"],
                    "export_policy_refs": ["export"],
                    "audit_log_refs": ["audit"],
                    "artifact_refs": ["artifact"],
                    "live_export_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_observability_live_export_blocked"
    assert "live_export_or_mutation_attempted" in packet["traces"][0]["blockers"]


def test_empty_payload_requests_observability_trace_inventory() -> None:
    packet = build_codex_observability_trace_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_observability_trace_inventory"]


def test_dataclass_like_trace_is_accepted_by_summarizer() -> None:
    @dataclass
    class Trace:
        trace_id: str
        run_ref: str
        status: str
        source: str
        provider: str
        run_trace_refs: list[str]
        tool_call_trace_refs: list[str]
        model_decision_refs: list[str]
        permission_prompt_refs: list[str]
        sandbox_event_refs: list[str]
        validation_receipt_refs: list[str]
        redaction_refs: list[str]
        error_taxonomy_refs: list[str]
        retention_policy_refs: list[str]
        export_policy_refs: list[str]
        audit_log_refs: list[str]
        replay_refs: list[str]
        artifact_refs: list[str]

    trace = summarize_codex_observability_trace(
        Trace(
            "trace-5",
            "run-5",
            "audited",
            "agent_run",
            "codex",
            ["run-trace"],
            ["tool-call"],
            ["model"],
            ["permission"],
            ["sandbox"],
            ["validation"],
            ["redaction"],
            ["error-taxonomy"],
            ["retention"],
            ["export"],
            ["audit"],
            ["replay"],
            ["artifact"],
        )
    )

    assert trace.trace_id == "trace-5"
    assert trace.status == "audited"
    assert trace.readiness_state == "ready"
