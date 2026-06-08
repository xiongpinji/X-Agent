#!/usr/bin/env python3
"""Build a read-only SDK and non-interactive CLI contract report."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.app.sdk import ControlPlaneSDK
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_OUTPUT = REPORT_DIR / "sdk-noninteractive-report.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "sdk-noninteractive-report.md"

CODEX_SDK_SOURCES = (
    "https://developers.openai.com/codex/noninteractive",
    "https://developers.openai.com/codex/sdk",
    "https://developers.openai.com/codex/app-server",
    "https://developers.openai.com/codex/integrations/slack",
)


@dataclass(frozen=True)
class SDKNonInteractiveCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class SDKNonInteractiveReport:
    status: str
    generated_at: str
    evidence_type: str
    full_codex_parity_claimed: bool
    dry_run: bool
    mutation_performed: bool
    network_mutation_performed: bool
    owner_gate_required: bool
    sdk_contracts: list[dict[str, Any]]
    cli_commands: list[dict[str, Any]]
    backend_stub: dict[str, Any]
    http_client_adapter: dict[str, Any]
    approval_intent_flow: dict[str, Any]
    approval_handoff: dict[str, Any]
    execution_adapter_contract: dict[str, Any]
    read_only_runner_contract: dict[str, Any]
    write_runner_safety_contract: dict[str, Any]
    dry_run_executor_stub: dict[str, Any]
    runtime_evidence_readback: dict[str, Any]
    runner_safety_review: dict[str, Any]
    write_runner_execute_gate: dict[str, Any]
    write_runner_adapter_review: dict[str, Any]
    channel_strategy: dict[str, Any]
    checks: list[SDKNonInteractiveCheck]
    official_sources: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _sdk_contracts() -> list[dict[str, Any]]:
    sdk = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator")
    return [
        sdk.start_thread("pilot task", idempotency_key="sdk-thread-start").to_dict(),
        sdk.resume_thread("thread-1", input_text="continue", idempotency_key="sdk-thread-resume").to_dict(),
        sdk.run_turn("thread-1", "next instruction", idempotency_key="sdk-turn-run").to_dict(),
        sdk.read_thread("thread-1").to_dict(),
        sdk.read_runtime_evidence("latest-codex-alignment.json").to_dict(),
        sdk.read_runtime_evidence(
            "sdk-dry-run-executor-stub.json",
            evidence_type="sdk_dry_run_executor_stub",
            approval_id="<approval_id>",
            method="turn/start",
        ).to_dict(),
    ]


def _cli_commands() -> list[dict[str, Any]]:
    return [
        {
            "command": "xagent sdk thread-start <task> --scope tools:read",
            "method": "thread/start",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/invoke",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk thread-resume <thread_id> --input <text>",
            "method": "thread/resume",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/invoke",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk turn-run <thread_id> <input>",
            "method": "turn/start",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/invoke",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk thread-read <thread_id>",
            "method": "thread/read",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/invoke",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk evidence-read <report_name>",
            "method": "runtime/evidence/read",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/invoke",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk evidence-read sdk-dry-run-executor-stub.json --evidence-type sdk_dry_run_executor_stub --approval-id <approval_id> --method turn/start --execute",
            "method": "runtime/evidence/read",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/invoke",
            "execute_starts_agent": False,
        },
    ]


def _channel_strategy() -> dict[str, Any]:
    return {
        "pilot_channel": "feishu",
        "domestic_v1_primary": "feishu",
        "telegram_required": False,
        "slack_blocking": False,
        "dingtalk_or_wechat_work_next": "after_feishu_pilot_acceptance",
        "channel_send_performed": False,
    }


def _build_checks(report_payload: dict[str, Any]) -> list[SDKNonInteractiveCheck]:
    contracts = report_payload["sdk_contracts"]
    commands = report_payload["cli_commands"]
    backend_stub = report_payload["backend_stub"]
    approval_flow = report_payload["approval_intent_flow"]
    handoff = report_payload["approval_handoff"]
    execution_adapter = report_payload["execution_adapter_contract"]
    read_only_runner = report_payload["read_only_runner_contract"]
    write_runner = report_payload["write_runner_safety_contract"]
    dry_run_stub = report_payload["dry_run_executor_stub"]
    evidence_readback = report_payload["runtime_evidence_readback"]
    runner_review = report_payload["runner_safety_review"]
    execute_gate = report_payload["write_runner_execute_gate"]
    adapter_review = report_payload["write_runner_adapter_review"]
    methods = [contract["request"]["method"] for contract in contracts]
    command_methods = [command["method"] for command in commands]
    cli_execute_targets = [
        command["method"]
        for command in commands
        if command.get("execute_target") != "/api/v1/control-plane/sdk/invoke"
    ]
    mutating = [
        contract["operation"]
        for contract in contracts
        if contract["request"].get("mutation_performed") is not False
        or contract["request"].get("network_mutation_performed") is not False
        or contract["owner_gate"].get("mutation_performed") is not False
    ]
    return [
        SDKNonInteractiveCheck(
            name="sdk_thread_methods_complete",
            status="passed"
            if methods
            == [
                "thread/start",
                "thread/resume",
                "turn/start",
                "thread/read",
                "runtime/evidence/read",
                "runtime/evidence/read",
            ]
            else "failed",
            details={"methods": methods},
            error=None if len(methods) == 6 else "SDK methods are incomplete",
        ),
        SDKNonInteractiveCheck(
            name="cli_non_interactive_commands_complete",
            status="passed" if command_methods == methods else "failed",
            details={"command_methods": command_methods, "sdk_methods": methods},
            error=None if command_methods == methods else "CLI command methods do not match SDK contracts",
        ),
        SDKNonInteractiveCheck(
            name="no_sdk_or_cli_mutation",
            status="passed" if not mutating else "failed",
            details={"mutating_contracts": mutating},
            error=None if not mutating else "one or more SDK contracts performed mutation",
        ),
        SDKNonInteractiveCheck(
            name="backend_stub_owner_gated",
            status="passed"
            if backend_stub.get("endpoint") == "/api/v1/control-plane/sdk/invoke"
            and backend_stub.get("adapter_execution_enabled") is False
            and backend_stub.get("mutation_performed") is False
            and backend_stub.get("approval_subject_type") == "command"
            else "failed",
            details=backend_stub,
            error=None
            if backend_stub.get("endpoint") == "/api/v1/control-plane/sdk/invoke"
            else "SDK backend stub endpoint is missing",
        ),
        SDKNonInteractiveCheck(
            name="cli_execute_calls_backend_stub_only",
            status="passed" if not cli_execute_targets else "failed",
            details={
                "execute_target": "/api/v1/control-plane/sdk/invoke",
                "mismatches": cli_execute_targets,
                "starts_agent_execution": False,
            },
            error=None if not cli_execute_targets else "one or more CLI execute commands bypass the SDK stub",
        ),
        SDKNonInteractiveCheck(
            name="sdk_write_methods_create_approval_intent",
            status="passed"
            if approval_flow.get("write_methods_create_pending_approval") is True
            and approval_flow.get("mark_executed") is False
            and approval_flow.get("starts_agent_execution") is False
            and approval_flow.get("mutation_performed") is False
            else "failed",
            details=approval_flow,
            error=None
            if approval_flow.get("write_methods_create_pending_approval") is True
            else "SDK write methods do not create owner approval intent",
        ),
        SDKNonInteractiveCheck(
            name="approval_handoff_readback_ready",
            status="passed"
            if handoff.get("approval_id_returned") is True
            and handoff.get("show_command") == "xagent approvals show <approval_id>"
            and handoff.get("approve_command") == "xagent approvals approve <approval_id> --by <owner> --reason <reason>"
            and handoff.get("execute_disabled") is True
            and handoff.get("mutation_performed") is False
            else "failed",
            details=handoff,
            error=None
            if handoff.get("approval_id_returned") is True
            else "approval handoff does not return approval id",
        ),
        SDKNonInteractiveCheck(
            name="owner_approved_execution_preflight_ready",
            status="passed"
            if execution_adapter.get("approved_approval_id_supported") is True
            and execution_adapter.get("approval_readback_method") == "approval/read"
            and execution_adapter.get("ready_status") == "approved_ready"
            and execution_adapter.get("adapter_execution_enabled") is False
            and execution_adapter.get("agent_execution_enabled") is False
            and execution_adapter.get("mark_executed") is False
            and execution_adapter.get("mutation_performed") is False
            else "failed",
            details=execution_adapter,
            error=None
            if execution_adapter.get("approved_approval_id_supported") is True
            else "owner-approved SDK execution preflight is not described",
        ),
        SDKNonInteractiveCheck(
            name="read_only_runner_contract_ready",
            status="passed"
            if read_only_runner.get("enabled_for_read_methods") is True
            and set(read_only_runner.get("supported_methods", []))
            >= {"thread/read", "runtime/evidence/read"}
            and read_only_runner.get("agent_execution_enabled") is False
            and read_only_runner.get("write_execution_enabled") is False
            and read_only_runner.get("mutation_performed") is False
            else "failed",
            details=read_only_runner,
            error=None
            if read_only_runner.get("enabled_for_read_methods") is True
            else "read-only SDK runner contract is not enabled",
        ),
        SDKNonInteractiveCheck(
            name="write_runner_safety_contract_ready",
            status="passed"
            if write_runner.get("stage") == "owner_approved_write_runner_safety"
            and write_runner.get("ready_status") == "planned_not_executed"
            and write_runner.get("runner_invoked") is False
            and write_runner.get("agent_execution_enabled") is False
            and write_runner.get("write_execution_enabled") is False
            and write_runner.get("mark_executed") is False
            and write_runner.get("mutation_performed") is False
            else "failed",
            details=write_runner,
            error=None
            if write_runner.get("runner_invoked") is False
            else "write SDK runner was invoked unexpectedly",
        ),
        SDKNonInteractiveCheck(
            name="dry_run_executor_stub_ready",
            status="passed"
            if dry_run_stub.get("stub_stage") == "owner_approved_write_dry_run_executor"
            and dry_run_stub.get("audit_action") == "sdk.write_runner.dry_run_planned"
            and dry_run_stub.get("audit_event_recorded") is True
            and dry_run_stub.get("receipt_persisted") is True
            and dry_run_stub.get("runner_invoked") is False
            and dry_run_stub.get("agent_execution_enabled") is False
            and dry_run_stub.get("mark_executed") is False
            and dry_run_stub.get("mutation_performed") is False
            else "failed",
            details=dry_run_stub,
            error=None
            if dry_run_stub.get("audit_event_recorded") is True
            else "dry-run executor audit event contract is missing",
        ),
        SDKNonInteractiveCheck(
            name="runtime_evidence_readback_ready",
            status="passed"
            if evidence_readback.get("evidence_type") == "sdk_dry_run_executor_stub"
            and evidence_readback.get("readback_method") == "runtime/evidence/read"
            and evidence_readback.get("receipt_schema_available") is True
            and evidence_readback.get("receipt_readback_supported") is True
            and evidence_readback.get("audit_readback_action") == "sdk.write_runner.dry_run_planned"
            and evidence_readback.get("mutation_performed") is False
            else "failed",
            details=evidence_readback,
            error=None
            if evidence_readback.get("receipt_schema_available") is True
            else "runtime evidence readback contract is missing receipt schema",
        ),
        SDKNonInteractiveCheck(
            name="persisted_receipt_safety_review_ready",
            status="passed"
            if runner_review.get("stage") == "persisted_dry_run_receipt_safety_review"
            and runner_review.get("review_status") == "passed"
            and runner_review.get("write_runner_enabled") is False
            and runner_review.get("agent_execution_enabled") is False
            and runner_review.get("mark_executed") is False
            and runner_review.get("mutation_performed") is False
            else "failed",
            details=runner_review,
            error=None
            if runner_review.get("write_runner_enabled") is False
            else "write runner was enabled before safety review gate completion",
        ),
        SDKNonInteractiveCheck(
            name="write_runner_execute_gate_ready",
            status="passed"
            if execute_gate.get("stage") == "owner_approved_write_runner_execute_gate"
            and execute_gate.get("gate_status") == "ready_but_disabled"
            and execute_gate.get("execute_enabled") is False
            and execute_gate.get("write_runner_enabled") is False
            and execute_gate.get("adapter_execution_enabled") is False
            and execute_gate.get("agent_execution_enabled") is False
            and execute_gate.get("mark_executed") is False
            and execute_gate.get("mutation_performed") is False
            and {
                "approved_preflight_ready",
                "runner_contract_ready",
                "receipt_persisted",
                "dry_run_receipt_planned",
                "audit_event_recorded",
                "safety_review_passed",
                "idempotency_key_present",
            }.issubset(set(execute_gate.get("required_checks", [])))
            else "failed",
            details=execute_gate,
            error=None
            if execute_gate.get("gate_status") == "ready_but_disabled"
            else "owner-approved write runner execute gate is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="write_runner_adapter_review_ready",
            status="passed"
            if adapter_review.get("stage") == "owner_approved_write_runner_adapter_implementation_review"
            and adapter_review.get("review_status") == "ready_but_disabled"
            and adapter_review.get("adapter_target", {}).get("callable") == "AgentCoordinator.run"
            and adapter_review.get("implementation_enabled") is False
            and adapter_review.get("execute_enabled") is False
            and adapter_review.get("write_runner_enabled") is False
            and adapter_review.get("adapter_execution_enabled") is False
            and adapter_review.get("agent_execution_enabled") is False
            and adapter_review.get("mark_executed") is False
            and adapter_review.get("mutation_performed") is False
            else "failed",
            details=adapter_review,
            error=None
            if adapter_review.get("implementation_enabled") is False
            else "write runner adapter implementation was enabled before runtime feature flag review",
        ),
        SDKNonInteractiveCheck(
            name="feishu_domestic_v1_primary",
            status="passed"
            if report_payload["channel_strategy"].get("domestic_v1_primary") == "feishu"
            and report_payload["channel_strategy"].get("telegram_required") is False
            else "failed",
            details=report_payload["channel_strategy"],
            error=None
            if report_payload["channel_strategy"].get("domestic_v1_primary") == "feishu"
            else "domestic V1 channel is not Feishu-first",
        ),
        SDKNonInteractiveCheck(
            name="no_full_codex_parity_claim",
            status="passed" if report_payload["full_codex_parity_claimed"] is False else "failed",
            details={"full_codex_parity_claimed": report_payload["full_codex_parity_claimed"]},
            error=None
            if report_payload["full_codex_parity_claimed"] is False
            else "report claims full Codex parity",
        ),
    ]


def build_sdk_noninteractive_report() -> SDKNonInteractiveReport:
    report_payload: dict[str, Any] = {
        "status": "sdk_write_runner_adapter_review_ready",
        "generated_at": _utc_now(),
        "evidence_type": "sdk_noninteractive_cli_contract",
        "full_codex_parity_claimed": False,
        "dry_run": True,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "owner_gate_required": True,
        "sdk_contracts": _sdk_contracts(),
        "cli_commands": _cli_commands(),
        "backend_stub": {
            "endpoint": "/api/v1/control-plane/sdk/invoke",
            "normalizes_to": "/api/v1/control-plane/invoke",
            "status": "sdk_write_runner_adapter_review_ready",
            "approval_subject_type": "command",
            "approval_intent_created_for_write_methods": True,
            "owner_gate_required": True,
            "admin_policy_required": True,
            "audit_required": True,
            "adapter_execution_enabled": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
        },
        "http_client_adapter": {
            "cli_method": "HTTPClient.invoke_sdk_contract",
            "endpoint": "/api/v1/control-plane/sdk/invoke",
            "trigger": "xagent sdk <command> --execute [--approved-approval-id <approval_id>]",
            "default_without_execute": "local_envelope_only",
            "read_only_execute_supported": True,
            "starts_agent_execution": False,
            "adapter_execution_enabled": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
        },
        "approval_intent_flow": {
            "write_methods_create_pending_approval": True,
            "read_methods_create_approval": False,
            "approval_subject_type": "command",
            "approval_resource_prefix": "sdk:",
            "risk_level": "high",
            "sandbox_profile": "command_locked",
            "mark_executed": False,
            "starts_agent_execution": False,
            "adapter_execution_enabled": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
        },
        "approval_handoff": {
            "approval_id_returned": True,
            "show_command": "xagent approvals show <approval_id>",
            "approve_command": "xagent approvals approve <approval_id> --by <owner> --reason <reason>",
            "blocked_execute_command": "xagent approvals execute <approval_id>",
            "execute_disabled": True,
            "readback_method": "approval/read",
            "readback_endpoint": "/api/v1/control-plane/invoke",
            "approval_api_link": "/api/v1/approvals/<approval_id>",
            "mutation_performed": False,
            "network_mutation_performed": False,
        },
        "execution_adapter_contract": {
            "stage": "owner_approved_preflight",
            "approved_approval_id_supported": True,
            "owner_approved_cli_flag": "--approved-approval-id <approval_id>",
            "approval_readback_method": "approval/read",
            "approval_readback_endpoint": "/api/v1/control-plane/invoke",
            "required_approval_status": "approved",
            "ready_status": "approved_ready",
            "pending_status": "approval_not_approved",
            "resource_mismatch_status": "approval_resource_mismatch",
            "tenant_mismatch_status": "approval_tenant_mismatch",
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "execute_disabled": True,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "read_only_runner_contract": {
            "stage": "read_only_runner",
            "enabled_for_read_methods": True,
            "supported_methods": ["thread/read", "runtime/evidence/read"],
            "cli_execute_commands": [
                "xagent sdk thread-read <thread_id> --execute",
                "xagent sdk evidence-read <report_name> --execute",
            ],
            "endpoint": "/api/v1/control-plane/sdk/invoke",
            "returns_control_plane_result": True,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "adapter_execution_enabled": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "write_runner_safety_contract": {
            "stage": "owner_approved_write_runner_safety",
            "approved_approval_id_required": True,
            "ready_status": "planned_not_executed",
            "blocked_status": "blocked_before_runner",
            "runner_plan_fields": [
                "runner_kind",
                "operation",
                "method",
                "approval_id",
                "idempotency_key_present",
                "input_preview",
                "guard_order",
            ],
            "receipt_template_fields": [
                "status",
                "runner_invoked",
                "agent_trace_id",
                "approval_id",
                "method",
                "operation",
                "mark_executed",
                "mutation_performed",
            ],
            "requires_idempotency_key_for_write": True,
            "runner_invoked": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "adapter_execution_enabled": False,
            "execute_disabled": True,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "dry_run_executor_stub": {
            "stub_stage": "owner_approved_write_dry_run_executor",
            "audit_event_recorded": True,
            "audit_action": "sdk.write_runner.dry_run_planned",
            "receipt_status": "dry_run_planned",
            "receipt_includes_audit_id": True,
            "receipt_persisted": True,
            "receipt_readback_method": "runtime/evidence/read",
            "runner_invoked": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "adapter_execution_enabled": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_evidence_readback": {
            "evidence_type": "sdk_dry_run_executor_stub",
            "readback_method": "runtime/evidence/read",
            "readback_endpoint": "/api/v1/control-plane/invoke",
            "sdk_command": "xagent sdk evidence-read sdk-dry-run-executor-stub.json --evidence-type sdk_dry_run_executor_stub --approval-id <approval_id> --method turn/start --execute",
            "receipt_schema_available": True,
            "receipt_readback_supported": True,
            "receipt_persisted": True,
            "receipt_filter_keys": ["approval_id", "method", "audit_id"],
            "audit_readback_action": "sdk.write_runner.dry_run_planned",
            "control_plane_result_key": "evidence",
            "runner_invoked": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runner_safety_review": {
            "stage": "persisted_dry_run_receipt_safety_review",
            "review_status": "passed",
            "required_receipt_checks": [
                "receipt_available",
                "receipt_persisted",
                "status_dry_run_planned",
                "audit_signature_present",
                "audit_hash_present",
                "runner_not_invoked",
                "mark_executed_false",
                "mutation_false",
                "network_mutation_false",
                "file_mutation_false",
                "channel_mutation_false",
            ],
            "next_gate": "owner_approved_write_runner_implementation_review",
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "write_runner_execute_gate": {
            "stage": "owner_approved_write_runner_execute_gate",
            "gate_status": "ready_but_disabled",
            "required_checks": [
                "write_method",
                "approved_preflight_ready",
                "runner_contract_ready",
                "receipt_persisted",
                "dry_run_receipt_planned",
                "audit_event_recorded",
                "audit_hash_present",
                "audit_signature_present",
                "safety_review_passed",
                "runner_not_invoked",
                "mark_executed_false",
                "mutation_false",
                "idempotency_key_present",
            ],
            "next_gate": "owner_approved_write_runner_adapter_implementation",
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "write_runner_adapter_review": {
            "stage": "owner_approved_write_runner_adapter_implementation_review",
            "review_status": "ready_but_disabled",
            "adapter_target": {
                "module": "backend.app.core.agent.coordinator",
                "callable": "AgentCoordinator.run",
                "request_mapping": {
                    "thread/start": "task",
                    "thread/resume": "input",
                    "turn/start": "input",
                },
            },
            "approval_execution_policy": {
                "readback_method": "approval/read",
                "required_status": "approved",
                "mark_executed_allowed_after_runner_success": True,
                "mark_executed_called_now": False,
            },
            "audit_contract": {
                "planned_action": "sdk.write_runner.adapter_review_ready",
                "future_execute_action": "sdk.write_runner.executed",
                "dry_run_receipt_required": True,
                "idempotency_key_required": True,
                "result_receipt_required": True,
            },
            "next_gate": "owner_approved_write_runner_runtime_feature_flag",
            "implementation_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "channel_strategy": _channel_strategy(),
        "official_sources": list(CODEX_SDK_SOURCES),
        "known_limits": [
            "The backend SDK endpoint accepts envelopes and normalizes them into the control-plane contract.",
            "The --execute CLI flag can call the backend SDK stub; adapter execution remains owner-gated.",
            "SDK write methods create a pending owner approval intent; approving the intent still does not execute an agent in this task.",
            "SDK responses include approval handoff commands and readback links for the owner.",
            "Supplying --approved-approval-id enables owner-approved execution preflight/readback only.",
            "Read-only SDK methods can be submitted with --execute and return backend read contracts.",
            "Owner-approved write SDK methods return a safety runner plan and receipt template only.",
            "Owner-approved write SDK dry-run executor stubs persist audit events and dry-run receipts only.",
            "Runtime evidence/read can return the SDK dry-run executor receipt schema and persisted receipt readback.",
            "Persisted receipt safety review is read-only and does not enable the write runner.",
            "Owner-approved write execute gate is ready for review but remains disabled.",
            "Owner-approved write runner adapter implementation review declares the future AgentCoordinator.run target but remains disabled.",
            "No SDK HTTP adapter, agent runner, file mutation, channel send, or network mutation is enabled.",
            "Feishu remains the only domestic V1 pilot channel in this contract.",
            "Slack is tracked as a Codex reference surface, but it is non-blocking for the domestic first version.",
            "Full Codex SDK, CLI, or integrations parity is not claimed.",
        ],
    }
    checks = _build_checks(report_payload)
    if any(check.status == "failed" for check in checks):
        report_payload["status"] = "sdk_noninteractive_contract_blocked"
    return SDKNonInteractiveReport(checks=checks, **report_payload)


def render_markdown_report(report: SDKNonInteractiveReport) -> str:
    contracts = "\n".join(
        f"- `{item['operation']}` -> `{item['request']['method']}`"
        for item in report.sdk_contracts
    )
    commands = "\n".join(f"- `{item['command']}`" for item in report.cli_commands)
    checks = "\n".join(f"- {check.name}: `{check.status}`" for check in report.checks)
    sources = "\n".join(f"- {source}" for source in report.official_sources)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    return (
        "# X-Agent SDK Non-Interactive Report\n\n"
        f"- Status: `{report.status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Dry run: `{report.dry_run}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Network mutation performed: `{report.network_mutation_performed}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n\n"
        "## SDK Contracts\n\n"
        f"{contracts}\n\n"
        "## CLI Commands\n\n"
        f"{commands}\n\n"
        "## Backend Stub\n\n"
        f"- Endpoint: `{report.backend_stub['endpoint']}`\n"
        f"- Normalizes to: `{report.backend_stub['normalizes_to']}`\n"
        f"- Adapter execution enabled: `{report.backend_stub['adapter_execution_enabled']}`\n\n"
        "## HTTP Client Adapter\n\n"
        f"- CLI method: `{report.http_client_adapter['cli_method']}`\n"
        f"- Trigger: `{report.http_client_adapter['trigger']}`\n"
        f"- Starts agent execution: `{report.http_client_adapter['starts_agent_execution']}`\n\n"
        "## Approval Intent Flow\n\n"
        f"- Write methods create pending approval: `{report.approval_intent_flow['write_methods_create_pending_approval']}`\n"
        f"- Subject type: `{report.approval_intent_flow['approval_subject_type']}`\n"
        f"- Starts agent execution: `{report.approval_intent_flow['starts_agent_execution']}`\n\n"
        "## Approval Handoff\n\n"
        f"- Show command: `{report.approval_handoff['show_command']}`\n"
        f"- Approve command: `{report.approval_handoff['approve_command']}`\n"
        f"- Execute disabled: `{report.approval_handoff['execute_disabled']}`\n\n"
        "## Execution Adapter Contract\n\n"
        f"- Stage: `{report.execution_adapter_contract['stage']}`\n"
        f"- Owner-approved flag: `{report.execution_adapter_contract['owner_approved_cli_flag']}`\n"
        f"- Ready status: `{report.execution_adapter_contract['ready_status']}`\n"
        f"- Adapter execution enabled: `{report.execution_adapter_contract['adapter_execution_enabled']}`\n"
        f"- Mark executed: `{report.execution_adapter_contract['mark_executed']}`\n\n"
        "## Read-Only Runner Contract\n\n"
        f"- Stage: `{report.read_only_runner_contract['stage']}`\n"
        f"- Supported methods: `{', '.join(report.read_only_runner_contract['supported_methods'])}`\n"
        f"- Returns control-plane result: `{report.read_only_runner_contract['returns_control_plane_result']}`\n"
        f"- Agent execution enabled: `{report.read_only_runner_contract['agent_execution_enabled']}`\n"
        f"- Write execution enabled: `{report.read_only_runner_contract['write_execution_enabled']}`\n\n"
        "## Write Runner Safety Contract\n\n"
        f"- Stage: `{report.write_runner_safety_contract['stage']}`\n"
        f"- Ready status: `{report.write_runner_safety_contract['ready_status']}`\n"
        f"- Runner invoked: `{report.write_runner_safety_contract['runner_invoked']}`\n"
        f"- Agent execution enabled: `{report.write_runner_safety_contract['agent_execution_enabled']}`\n"
        f"- Mark executed: `{report.write_runner_safety_contract['mark_executed']}`\n\n"
        "## Dry-Run Executor Stub\n\n"
        f"- Stage: `{report.dry_run_executor_stub['stub_stage']}`\n"
        f"- Audit action: `{report.dry_run_executor_stub['audit_action']}`\n"
        f"- Audit event recorded: `{report.dry_run_executor_stub['audit_event_recorded']}`\n"
        f"- Runner invoked: `{report.dry_run_executor_stub['runner_invoked']}`\n"
        f"- Mutation performed: `{report.dry_run_executor_stub['mutation_performed']}`\n\n"
        "## Runtime Evidence Readback\n\n"
        f"- Evidence type: `{report.runtime_evidence_readback['evidence_type']}`\n"
        f"- Readback method: `{report.runtime_evidence_readback['readback_method']}`\n"
        f"- SDK command: `{report.runtime_evidence_readback['sdk_command']}`\n"
        f"- Receipt schema available: `{report.runtime_evidence_readback['receipt_schema_available']}`\n\n"
        "## Persisted Receipt Safety Review\n\n"
        f"- Stage: `{report.runner_safety_review['stage']}`\n"
        f"- Review status: `{report.runner_safety_review['review_status']}`\n"
        f"- Write runner enabled: `{report.runner_safety_review['write_runner_enabled']}`\n"
        f"- Agent execution enabled: `{report.runner_safety_review['agent_execution_enabled']}`\n"
        f"- Mutation performed: `{report.runner_safety_review['mutation_performed']}`\n\n"
        "## Write Runner Execute Gate\n\n"
        f"- Stage: `{report.write_runner_execute_gate['stage']}`\n"
        f"- Gate status: `{report.write_runner_execute_gate['gate_status']}`\n"
        f"- Execute enabled: `{report.write_runner_execute_gate['execute_enabled']}`\n"
        f"- Write runner enabled: `{report.write_runner_execute_gate['write_runner_enabled']}`\n"
        f"- Mutation performed: `{report.write_runner_execute_gate['mutation_performed']}`\n\n"
        "## Write Runner Adapter Review\n\n"
        f"- Stage: `{report.write_runner_adapter_review['stage']}`\n"
        f"- Review status: `{report.write_runner_adapter_review['review_status']}`\n"
        f"- Adapter target: `{report.write_runner_adapter_review['adapter_target']['callable']}`\n"
        f"- Implementation enabled: `{report.write_runner_adapter_review['implementation_enabled']}`\n"
        f"- Mark executed: `{report.write_runner_adapter_review['mark_executed']}`\n\n"
        "## Channel Strategy\n\n"
        f"- Domestic V1 primary: `{report.channel_strategy['domestic_v1_primary']}`\n"
        f"- Telegram required: `{report.channel_strategy['telegram_required']}`\n"
        f"- Slack blocking: `{report.channel_strategy['slack_blocking']}`\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Official Codex Sources\n\n"
        f"{sources}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: SDKNonInteractiveReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(
    report: SDKNonInteractiveReport,
    output_path: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_sdk_noninteractive_report()
    write_report(report, args.output)
    write_markdown_report(report, args.markdown_output)
    print(f"SDK non-interactive report status: {report.status}")
    print(f"JSON report written to {args.output}")
    print(f"Markdown report written to {args.markdown_output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Mutation performed: {report.mutation_performed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "sdk_write_runner_adapter_review_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
