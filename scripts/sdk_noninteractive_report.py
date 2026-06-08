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
    write_runner_runtime_flag: dict[str, Any]
    owner_acceptance_evidence: dict[str, Any]
    owner_acceptance_record_workflow: dict[str, Any]
    runtime_enablement_review: dict[str, Any]
    write_runner_implementation_plan: dict[str, Any]
    runtime_smoke_runbook: dict[str, Any]
    runtime_enablement_receipt: dict[str, Any]
    runtime_implementation_preflight: dict[str, Any]
    runtime_enablement_receipt_record_workflow: dict[str, Any]
    runtime_enablement_owner_pack: dict[str, Any]
    runtime_enablement_owner_pack_decision_workflow: dict[str, Any]
    runtime_implementation_readiness_lock_workflow: dict[str, Any]
    runtime_implementation_owner_pack: dict[str, Any]
    runtime_implementation_final_decision_workflow: dict[str, Any]
    runtime_flag_enablement_record_workflow: dict[str, Any]
    runtime_flag_application_preflight_workflow: dict[str, Any]
    runtime_flag_application_owner_approval_workflow: dict[str, Any]
    runtime_flag_application_execute_contract_workflow: dict[str, Any]
    runtime_flag_application_execute_contract_owner_review: dict[str, Any]
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
        sdk.read_runtime_evidence(
            "sdk-write-runner-owner-acceptance.json",
            evidence_type="sdk_write_runner_owner_acceptance",
            approval_id="<approval_id>",
            owner_acceptance_id="<owner_acceptance_id>",
            audit_id="<audit_id>",
        ).to_dict(),
        sdk.read_runtime_evidence(
            "sdk-write-runner-runtime-enable-readiness.json",
            evidence_type="sdk_write_runner_runtime_enablement_readiness",
            readiness_receipt_id="<readiness_receipt_id>",
            approval_id="<approval_id>",
            owner_acceptance_id="<owner_acceptance_id>",
            audit_id="<audit_id>",
        ).to_dict(),
        sdk.read_runtime_evidence(
            "sdk-write-runner-runtime-implementation-readiness-lock.json",
            evidence_type="sdk_write_runner_runtime_implementation_readiness_lock",
            implementation_lock_id="<implementation_lock_id>",
            approval_id="<approval_id>",
            readiness_receipt_id="<readiness_receipt_id>",
            owner_pack_decision_id="<owner_pack_decision_id>",
            audit_id="<implementation_lock_audit_id>",
        ).to_dict(),
        sdk.record_runtime_enablement_receipt(
            readiness_receipt_id="<readiness_receipt_id>",
            approval_id="<approval_id>",
            owner_acceptance_id="<owner_acceptance_id>",
            owner_acceptance_audit_id="<owner_acceptance_audit_id>",
            smoke_runbook_version="v1",
            rollback_runbook_version="v1",
            accepted_by="<owner>",
            accepted_at="2026-06-08T00:00:00Z",
            expires_at="2026-06-09T00:00:00Z",
            smoke_runbook_acknowledged=True,
            rollback_runbook_acknowledged=True,
            failure_receipt_reviewed=True,
            acceptance_hash="<acceptance_hash>",
        ).to_dict(),
        sdk.record_runtime_enablement_owner_pack_decision(
            owner_pack_decision_id="<owner_pack_decision_id>",
            decision="accepted",
            approval_id="<approval_id>",
            readiness_receipt_id="<readiness_receipt_id>",
            readiness_receipt_audit_id="<readiness_receipt_audit_id>",
            owner_acceptance_id="<owner_acceptance_id>",
            owner_acceptance_audit_id="<owner_acceptance_audit_id>",
            decided_by="<owner>",
            decided_at="2026-06-08T00:00:00Z",
            reason="<reason>",
            decision_hash="<decision_hash>",
        ).to_dict(),
        sdk.record_runtime_implementation_readiness_lock(
            implementation_lock_id="<implementation_lock_id>",
            idempotency_key="<idempotency_key>",
            idempotency_hash="<idempotency_hash>",
            approval_id="<approval_id>",
            readiness_receipt_id="<readiness_receipt_id>",
            readiness_receipt_audit_id="<readiness_receipt_audit_id>",
            owner_pack_decision_id="<owner_pack_decision_id>",
            owner_pack_decision_audit_id="<owner_pack_decision_audit_id>",
            operator_id="<operator>",
            locked_at="2026-06-08T00:00:00Z",
            lock_reason="<lock_reason>",
            lock_hash="<lock_hash>",
        ).to_dict(),
        sdk.record_runtime_implementation_final_decision(
            final_decision_id="<final_decision_id>",
            decision="accepted",
            approval_id="<approval_id>",
            implementation_lock_id="<implementation_lock_id>",
            implementation_lock_audit_id="<implementation_lock_audit_id>",
            readiness_receipt_id="<readiness_receipt_id>",
            owner_pack_decision_id="<owner_pack_decision_id>",
            decided_by="<owner>",
            decided_at="2026-06-08T00:00:00Z",
            reason="<reason>",
            decision_hash="<decision_hash>",
        ).to_dict(),
        sdk.record_runtime_flag_enablement(
            runtime_flag_enablement_id="<runtime_flag_enablement_id>",
            approval_id="<approval_id>",
            final_decision_id="<final_decision_id>",
            final_decision_audit_id="<final_decision_audit_id>",
            implementation_lock_id="<implementation_lock_id>",
            readiness_receipt_id="<readiness_receipt_id>",
            requested_by="<owner>",
            requested_at="2026-06-08T00:00:00Z",
            enablement_reason="<reason>",
            enablement_hash="<enablement_hash>",
        ).to_dict(),
        sdk.record_runtime_flag_application_preflight(
            runtime_flag_preflight_id="<runtime_flag_preflight_id>",
            approval_id="<approval_id>",
            runtime_flag_enablement_id="<runtime_flag_enablement_id>",
            runtime_flag_enablement_audit_id="<runtime_flag_enablement_audit_id>",
            final_decision_id="<final_decision_id>",
            requested_by="<owner>",
            requested_at="2026-06-08T00:00:00Z",
            preflight_reason="<reason>",
            rollback_plan_ref="<rollback_plan_ref>",
            smoke_runbook_ref="<smoke_runbook_ref>",
            preflight_hash="<preflight_hash>",
        ).to_dict(),
        sdk.record_runtime_flag_application_owner_approval(
            runtime_flag_approval_id="<runtime_flag_approval_id>",
            approval_id="<approval_id>",
            runtime_flag_preflight_id="<runtime_flag_preflight_id>",
            runtime_flag_preflight_audit_id="<runtime_flag_preflight_audit_id>",
            runtime_flag_enablement_id="<runtime_flag_enablement_id>",
            final_decision_id="<final_decision_id>",
            decision="accepted",
            decided_by="<owner>",
            decided_at="2026-06-08T00:00:00Z",
            approval_reason="<reason>",
            approval_hash="<approval_hash>",
        ).to_dict(),
        sdk.record_runtime_flag_application_execute_contract(
            runtime_flag_execute_contract_id="<runtime_flag_execute_contract_id>",
            approval_id="<approval_id>",
            runtime_flag_approval_id="<runtime_flag_approval_id>",
            runtime_flag_approval_audit_id="<runtime_flag_approval_audit_id>",
            runtime_flag_preflight_id="<runtime_flag_preflight_id>",
            runtime_flag_enablement_id="<runtime_flag_enablement_id>",
            final_decision_id="<final_decision_id>",
            operator_id="<operator>",
            locked_at="2026-06-08T00:00:00Z",
            execute_contract_reason="<reason>",
            idempotency_key="<idempotency_key>",
            idempotency_hash="<idempotency_hash>",
            rollback_plan_ref="<rollback_plan_ref>",
            smoke_runbook_ref="<smoke_runbook_ref>",
            execute_contract_hash="<execute_contract_hash>",
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
        {
            "command": "xagent sdk evidence-read sdk-write-runner-owner-acceptance.json --evidence-type sdk_write_runner_owner_acceptance --approval-id <approval_id> --acceptance-id <owner_acceptance_id> --audit-id <audit_id> --execute",
            "method": "runtime/evidence/read",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/invoke",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk evidence-read sdk-write-runner-runtime-enable-readiness.json --evidence-type sdk_write_runner_runtime_enablement_readiness --readiness-receipt-id <readiness_receipt_id> --approval-id <approval_id> --acceptance-id <owner_acceptance_id> --audit-id <audit_id> --execute",
            "method": "runtime/evidence/read",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/invoke",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk evidence-read sdk-write-runner-runtime-implementation-readiness-lock.json --evidence-type sdk_write_runner_runtime_implementation_readiness_lock --implementation-lock-id <implementation_lock_id> --approval-id <approval_id> --readiness-receipt-id <readiness_receipt_id> --decision-id <owner_pack_decision_id> --audit-id <implementation_lock_audit_id> --execute",
            "method": "runtime/evidence/read",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/invoke",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk runtime-enable-receipt-record --approval-id <approval_id> --readiness-receipt-id <readiness_receipt_id> --acceptance-id <owner_acceptance_id> --acceptance-audit-id <owner_acceptance_audit_id> --execute",
            "method": "runtime_enablement_receipt_record",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/runtime-enablement/receipt/record",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk runtime-enable-owner-pack-decision-record --decision accepted --decision-id <owner_pack_decision_id> --approval-id <approval_id> --readiness-receipt-id <readiness_receipt_id> --readiness-receipt-audit-id <readiness_receipt_audit_id> --execute",
            "method": "runtime_enablement_owner_pack_decision_record",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk runtime-implementation-readiness-lock-record --implementation-lock-id <implementation_lock_id> --idempotency-key <idempotency_key> --idempotency-hash <idempotency_hash> --decision-id <owner_pack_decision_id> --decision-audit-id <owner_pack_decision_audit_id> --execute",
            "method": "runtime_implementation_readiness_lock_record",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk runtime-implementation-final-decision-record --final-decision-id <final_decision_id> --decision accepted --implementation-lock-id <implementation_lock_id> --implementation-lock-audit-id <implementation_lock_audit_id> --execute",
            "method": "runtime_implementation_final_decision_record",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk runtime-flag-enable-record --runtime-flag-enablement-id <runtime_flag_enablement_id> --final-decision-id <final_decision_id> --final-decision-audit-id <final_decision_audit_id> --execute",
            "method": "runtime_flag_enablement_record",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/runtime-flag/enablement/record",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk runtime-flag-application-preflight-record --runtime-flag-preflight-id <runtime_flag_preflight_id> --runtime-flag-enablement-id <runtime_flag_enablement_id> --runtime-flag-enablement-audit-id <runtime_flag_enablement_audit_id> --execute",
            "method": "runtime_flag_application_preflight_record",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/runtime-flag/application-preflight/record",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk runtime-flag-application-approval-record --runtime-flag-approval-id <runtime_flag_approval_id> --runtime-flag-preflight-id <runtime_flag_preflight_id> --runtime-flag-preflight-audit-id <runtime_flag_preflight_audit_id> --decision accepted --execute",
            "method": "runtime_flag_application_owner_approval_record",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/runtime-flag/application-approval/record",
            "execute_starts_agent": False,
        },
        {
            "command": "xagent sdk runtime-flag-application-execute-contract-record --runtime-flag-execute-contract-id <runtime_flag_execute_contract_id> --runtime-flag-approval-id <runtime_flag_approval_id> --runtime-flag-approval-audit-id <runtime_flag_approval_audit_id> --idempotency-key <idempotency_key> --idempotency-hash <idempotency_hash> --execute",
            "method": "runtime_flag_application_execute_contract_record",
            "non_interactive": True,
            "dry_run_default": True,
            "execute_target": "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record",
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


def _sdk_contract_method(contract: dict[str, Any]) -> str | None:
    request = contract.get("request") or {}
    return request.get("method") or contract.get("operation")


def _sdk_contract_performed_mutation(contract: dict[str, Any]) -> bool:
    request = contract.get("request") or {}
    owner_gate = contract.get("owner_gate") or {}
    mutation_flags = [
        request.get("mutation_performed", contract.get("mutation_performed", False)),
        request.get("network_mutation_performed", contract.get("network_mutation_performed", False)),
        request.get("file_mutation_performed", contract.get("file_mutation_performed", False)),
        request.get("channel_mutation_performed", contract.get("channel_mutation_performed", False)),
        owner_gate.get("mutation_performed", False),
        owner_gate.get("network_mutation_performed", False),
    ]
    return any(flag is not False for flag in mutation_flags)


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
    runtime_flag = report_payload["write_runner_runtime_flag"]
    owner_acceptance = report_payload["owner_acceptance_evidence"]
    owner_acceptance_workflow = report_payload["owner_acceptance_record_workflow"]
    runtime_enablement_review = report_payload["runtime_enablement_review"]
    implementation_plan = report_payload["write_runner_implementation_plan"]
    runtime_smoke = report_payload["runtime_smoke_runbook"]
    enablement_receipt = report_payload["runtime_enablement_receipt"]
    implementation_preflight = report_payload["runtime_implementation_preflight"]
    receipt_record_workflow = report_payload["runtime_enablement_receipt_record_workflow"]
    owner_pack = report_payload["runtime_enablement_owner_pack"]
    owner_pack_decision = report_payload["runtime_enablement_owner_pack_decision_workflow"]
    readiness_lock = report_payload["runtime_implementation_readiness_lock_workflow"]
    implementation_owner_pack = report_payload["runtime_implementation_owner_pack"]
    final_decision = report_payload["runtime_implementation_final_decision_workflow"]
    runtime_flag_enablement = report_payload["runtime_flag_enablement_record_workflow"]
    runtime_flag_preflight = report_payload["runtime_flag_application_preflight_workflow"]
    runtime_flag_approval = report_payload["runtime_flag_application_owner_approval_workflow"]
    runtime_flag_execute_contract = report_payload["runtime_flag_application_execute_contract_workflow"]
    runtime_flag_execute_contract_review = report_payload[
        "runtime_flag_application_execute_contract_owner_review"
    ]
    methods = [_sdk_contract_method(contract) for contract in contracts]
    command_methods = [command["method"] for command in commands]
    allowed_execute_targets = {
        "/api/v1/control-plane/sdk/invoke",
        "/api/v1/control-plane/sdk/runtime-enablement/receipt/record",
        "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record",
        "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
        "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
        "/api/v1/control-plane/sdk/runtime-flag/enablement/record",
        "/api/v1/control-plane/sdk/runtime-flag/application-preflight/record",
        "/api/v1/control-plane/sdk/runtime-flag/application-approval/record",
        "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record",
    }
    cli_execute_targets = [
        command["method"]
        for command in commands
        if command.get("execute_target") not in allowed_execute_targets
    ]
    mutating = [
        contract["operation"]
        for contract in contracts
        if _sdk_contract_performed_mutation(contract)
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
                "runtime/evidence/read",
                "runtime/evidence/read",
                "runtime/evidence/read",
                "runtime_enablement_receipt_record",
                "runtime_enablement_owner_pack_decision_record",
                "runtime_implementation_readiness_lock_record",
                "runtime_implementation_final_decision_record",
                "runtime_flag_enablement_record",
                "runtime_flag_application_preflight_record",
                "runtime_flag_application_owner_approval_record",
                "runtime_flag_application_execute_contract_record",
            ]
            else "failed",
            details={"methods": methods},
            error=None if len(methods) == 17 else "SDK methods are incomplete",
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
            name="write_runner_runtime_flag_contract_ready",
            status="passed"
            if runtime_flag.get("stage") == "owner_approved_write_runner_runtime_feature_flag"
            and runtime_flag.get("flag_name") == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
            and runtime_flag.get("flag_status") == "declared_disabled"
            and runtime_flag.get("default_enabled") is False
            and runtime_flag.get("runtime_flag_enabled") is False
            and runtime_flag.get("owner_acceptance_evidence_required") is True
            and runtime_flag.get("implementation_enabled") is False
            and runtime_flag.get("write_runner_enabled") is False
            and runtime_flag.get("agent_execution_enabled") is False
            and runtime_flag.get("mutation_performed") is False
            else "failed",
            details=runtime_flag,
            error=None
            if runtime_flag.get("runtime_flag_enabled") is False
            else "SDK write runner runtime flag is enabled before owner acceptance",
        ),
        SDKNonInteractiveCheck(
            name="owner_acceptance_evidence_recording_contract_ready",
            status="passed"
            if owner_acceptance.get("stage") == "owner_acceptance_evidence_record"
            and owner_acceptance.get("evidence_status") == "recording_contract_ready_not_provided"
            and owner_acceptance.get("recording_contract_ready") is True
            and owner_acceptance.get("recording_action") == "sdk.write_runner.owner_acceptance_recorded"
            and owner_acceptance.get("evidence_type") == "sdk_write_runner_owner_acceptance"
            and owner_acceptance.get("readback_contract", {}).get("returns_schema") is True
            and owner_acceptance.get("recording_contract", {}).get("created_by_sdk_invoke") is False
            and "owner_acceptance_id" in owner_acceptance.get("required_fields", [])
            and owner_acceptance.get("runtime_flag_enabled") is False
            and owner_acceptance.get("execute_enabled") is False
            and owner_acceptance.get("write_runner_enabled") is False
            and owner_acceptance.get("agent_execution_enabled") is False
            and owner_acceptance.get("mutation_performed") is False
            else "failed",
            details=owner_acceptance,
            error=None
            if owner_acceptance.get("evidence_status") == "recording_contract_ready_not_provided"
            else "owner acceptance evidence unexpectedly enables execution",
        ),
        SDKNonInteractiveCheck(
            name="owner_acceptance_record_workflow_ready",
            status="passed"
            if owner_acceptance_workflow.get("stage") == "owner_acceptance_evidence_record_workflow"
            and owner_acceptance_workflow.get("endpoint") == "/api/v1/control-plane/sdk/owner-acceptance/record"
            and owner_acceptance_workflow.get("audit_action") == "sdk.write_runner.owner_acceptance_recorded"
            and owner_acceptance_workflow.get("requires_approved_sdk_approval") is True
            and owner_acceptance_workflow.get("requires_signature_or_hash") is True
            and owner_acceptance_workflow.get("marks_approval_executed") is False
            and owner_acceptance_workflow.get("runtime_flag_enabled") is False
            and owner_acceptance_workflow.get("write_runner_enabled") is False
            and owner_acceptance_workflow.get("agent_execution_enabled") is False
            and owner_acceptance_workflow.get("mutation_performed") is False
            else "failed",
            details=owner_acceptance_workflow,
            error=None
            if owner_acceptance_workflow.get("write_runner_enabled") is False
            else "owner acceptance workflow unexpectedly enables write runner",
        ),
        SDKNonInteractiveCheck(
            name="runtime_enablement_review_contract_ready",
            status="passed"
            if runtime_enablement_review.get("stage") == "owner_approved_write_runner_runtime_enablement_review"
            and runtime_enablement_review.get("review_status") == "ready_but_disabled"
            and runtime_enablement_review.get("required_evidence_type") == "sdk_write_runner_owner_acceptance"
            and runtime_enablement_review.get("runtime_flag_enabled") is False
            and runtime_enablement_review.get("execute_enabled") is False
            and runtime_enablement_review.get("write_runner_enabled") is False
            and runtime_enablement_review.get("agent_execution_enabled") is False
            and runtime_enablement_review.get("mark_executed") is False
            and runtime_enablement_review.get("mutation_performed") is False
            else "failed",
            details=runtime_enablement_review,
            error=None
            if runtime_enablement_review.get("review_status") == "ready_but_disabled"
            else "runtime enablement review is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="write_runner_implementation_plan_ready",
            status="passed"
            if implementation_plan.get("stage") == "owner_approved_write_runner_concrete_implementation_plan"
            and implementation_plan.get("plan_status") == "ready_but_disabled"
            and implementation_plan.get("adapter_target", {}).get("callable") == "AgentCoordinator.run"
            and implementation_plan.get("idempotency_contract", {}).get("required") is True
            and implementation_plan.get("rollback_plan", {}).get("disable_runtime_flag") is True
            and implementation_plan.get("audit_result_shape", {}).get("planned_action")
            == "sdk.write_runner.implementation_plan_ready"
            and implementation_plan.get("implementation_enabled") is False
            and implementation_plan.get("runtime_flag_enabled") is False
            and implementation_plan.get("execute_enabled") is False
            and implementation_plan.get("write_runner_enabled") is False
            and implementation_plan.get("adapter_execution_enabled") is False
            and implementation_plan.get("agent_execution_enabled") is False
            and implementation_plan.get("runner_invoked") is False
            and implementation_plan.get("mark_executed") is False
            and implementation_plan.get("mutation_performed") is False
            else "failed",
            details=implementation_plan,
            error=None
            if implementation_plan.get("plan_status") == "ready_but_disabled"
            else "write runner implementation plan is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_smoke_runbook_contract_ready",
            status="passed"
            if runtime_smoke.get("stage") == "owner_approved_write_runner_runtime_smoke_runbook"
            and runtime_smoke.get("contract_status") == "ready_but_disabled"
            and runtime_smoke.get("smoke_plan", {}).get("requires_runtime_flag")
            == "XAGENT_SDK_WRITE_RUNNER_ENABLED=true"
            and runtime_smoke.get("rollback_plan", {}).get("failure_receipt_required") is True
            and runtime_smoke.get("failure_receipt_contract", {}).get("audit_action") == "sdk.write_runner.failed"
            and runtime_smoke.get("failure_receipt_contract", {}).get("mark_executed_must_be_false_on_failure")
            is True
            and runtime_smoke.get("implementation_enabled") is False
            and runtime_smoke.get("runtime_flag_enabled") is False
            and runtime_smoke.get("execute_enabled") is False
            and runtime_smoke.get("write_runner_enabled") is False
            and runtime_smoke.get("adapter_execution_enabled") is False
            and runtime_smoke.get("agent_execution_enabled") is False
            and runtime_smoke.get("runner_invoked") is False
            and runtime_smoke.get("mark_executed") is False
            and runtime_smoke.get("mutation_performed") is False
            else "failed",
            details=runtime_smoke,
            error=None
            if runtime_smoke.get("contract_status") == "ready_but_disabled"
            else "runtime smoke/runbook contract is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_enablement_receipt_contract_ready",
            status="passed"
            if enablement_receipt.get("stage") == "owner_approved_write_runner_runtime_enablement_receipt"
            and enablement_receipt.get("receipt_status") == "ready_but_disabled"
            and enablement_receipt.get("receipt_type") == "sdk_write_runner_runtime_enablement_readiness"
            and enablement_receipt.get("receipt_schema", {}).get("runtime_flag_name")
            == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
            and enablement_receipt.get("review_readback", {}).get("query_keys")
            == ["readiness_receipt_id", "approval_id", "owner_acceptance_id"]
            and enablement_receipt.get("owner_review_policy", {}).get("requires_expiry") is True
            and enablement_receipt.get("audit_contract", {}).get("planned_action")
            == "sdk.write_runner.runtime_enablement_receipt_ready"
            and enablement_receipt.get("implementation_enabled") is False
            and enablement_receipt.get("runtime_flag_enabled") is False
            and enablement_receipt.get("execute_enabled") is False
            and enablement_receipt.get("write_runner_enabled") is False
            and enablement_receipt.get("adapter_execution_enabled") is False
            and enablement_receipt.get("agent_execution_enabled") is False
            and enablement_receipt.get("runner_invoked") is False
            and enablement_receipt.get("mark_executed") is False
            and enablement_receipt.get("mutation_performed") is False
            else "failed",
            details=enablement_receipt,
            error=None
            if enablement_receipt.get("receipt_status") == "ready_but_disabled"
            else "runtime enablement readiness receipt contract is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_implementation_preflight_contract_ready",
            status="passed"
            if implementation_preflight.get("stage")
            == "owner_approved_write_runner_runtime_implementation_preflight"
            and implementation_preflight.get("preflight_status") == "ready_but_disabled"
            and implementation_preflight.get("adapter_module_boundary", {}).get("module")
            == "backend.app.core.agent.coordinator"
            and implementation_preflight.get("adapter_module_boundary", {}).get("callable")
            == "AgentCoordinator.run"
            and implementation_preflight.get("adapter_module_boundary", {}).get("import_allowed") is False
            and implementation_preflight.get("dependency_injection_contract", {}).get("required") is True
            and implementation_preflight.get("dependency_injection_contract", {}).get("default_factory_enabled")
            is False
            and implementation_preflight.get("idempotency_lock_contract", {}).get("required") is True
            and implementation_preflight.get("idempotency_lock_contract", {}).get("lock_enabled") is False
            and implementation_preflight.get("receipt_persistence_interface", {}).get("required") is True
            and implementation_preflight.get("receipt_persistence_interface", {}).get("persistence_enabled")
            is False
            and implementation_preflight.get("approval_postcondition_contract", {}).get("mark_executed_enabled")
            is False
            and implementation_preflight.get("failure_handling_contract", {}).get("mark_executed_on_failure")
            is False
            and implementation_preflight.get("implementation_enabled") is False
            and implementation_preflight.get("runtime_flag_enabled") is False
            and implementation_preflight.get("execute_enabled") is False
            and implementation_preflight.get("write_runner_enabled") is False
            and implementation_preflight.get("adapter_execution_enabled") is False
            and implementation_preflight.get("agent_execution_enabled") is False
            and implementation_preflight.get("runner_invoked") is False
            and implementation_preflight.get("mark_executed") is False
            and implementation_preflight.get("mutation_performed") is False
            else "failed",
            details=implementation_preflight,
            error=None
            if implementation_preflight.get("preflight_status") == "ready_but_disabled"
            else "runtime implementation preflight is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_enablement_receipt_record_workflow_ready",
            status="passed"
            if receipt_record_workflow.get("stage") == "runtime_enablement_readiness_receipt_record_workflow"
            and receipt_record_workflow.get("workflow_status") == "ready_but_disabled"
            and receipt_record_workflow.get("endpoint")
            == "/api/v1/control-plane/sdk/runtime-enablement/receipt/record"
            and receipt_record_workflow.get("audit_action")
            == "sdk.write_runner.runtime_enablement_receipt_recorded"
            and receipt_record_workflow.get("requires_approved_sdk_approval") is True
            and receipt_record_workflow.get("requires_owner_acceptance_audit_record") is True
            and receipt_record_workflow.get("requires_signature_or_hash") is True
            and receipt_record_workflow.get("readback_contract", {}).get("evidence_type")
            == "sdk_write_runner_runtime_enablement_readiness"
            and receipt_record_workflow.get("readback_contract", {}).get("query_keys")
            == ["readiness_receipt_id", "approval_id", "owner_acceptance_id", "audit_id"]
            and receipt_record_workflow.get("runtime_flag_enabled") is False
            and receipt_record_workflow.get("execute_enabled") is False
            and receipt_record_workflow.get("write_runner_enabled") is False
            and receipt_record_workflow.get("adapter_execution_enabled") is False
            and receipt_record_workflow.get("agent_execution_enabled") is False
            and receipt_record_workflow.get("runner_invoked") is False
            and receipt_record_workflow.get("mark_executed") is False
            and receipt_record_workflow.get("mutation_performed") is False
            else "failed",
            details=receipt_record_workflow,
            error=None
            if receipt_record_workflow.get("workflow_status") == "ready_but_disabled"
            else "runtime enablement readiness receipt record workflow is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_enablement_owner_pack_ready",
            status="passed"
            if owner_pack.get("stage") == "runtime_enablement_owner_acceptance_pack"
            and owner_pack.get("pack_status") == "ready_but_disabled"
            and owner_pack.get("pack_type") == "sdk_write_runner_runtime_enablement_owner_review_pack"
            and "runtime_enablement_readiness_receipt_record" in owner_pack.get("required_evidence", [])
            and owner_pack.get("readback_contract", {}).get("evidence_type")
            == "sdk_write_runner_runtime_enablement_readiness"
            and owner_pack.get("readback_contract", {}).get("query_keys")
            == ["readiness_receipt_id", "approval_id", "owner_acceptance_id", "audit_id"]
            and owner_pack.get("audit_contract", {}).get("audit_event_recorded_now") is False
            and owner_pack.get("owner_decision_policy", {}).get("manual_review_required") is True
            and owner_pack.get("owner_decision_policy", {}).get("can_enable_runtime_flag_after_pack") is False
            and owner_pack.get("implementation_enabled") is False
            and owner_pack.get("runtime_flag_enabled") is False
            and owner_pack.get("execute_enabled") is False
            and owner_pack.get("write_runner_enabled") is False
            and owner_pack.get("adapter_execution_enabled") is False
            and owner_pack.get("agent_execution_enabled") is False
            and owner_pack.get("runner_invoked") is False
            and owner_pack.get("mark_executed") is False
            and owner_pack.get("mutation_performed") is False
            else "failed",
            details=owner_pack,
            error=None
            if owner_pack.get("pack_status") == "ready_but_disabled"
            else "runtime enablement owner pack is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_enablement_owner_pack_decision_workflow_ready",
            status="passed"
            if owner_pack_decision.get("stage") == "runtime_enablement_owner_pack_decision_record_workflow"
            and owner_pack_decision.get("workflow_status") == "ready_but_disabled"
            and owner_pack_decision.get("endpoint")
            == "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record"
            and owner_pack_decision.get("audit_action")
            == "sdk.write_runner.runtime_enablement_owner_pack_decision_recorded"
            and owner_pack_decision.get("requires_approved_sdk_approval") is True
            and owner_pack_decision.get("requires_runtime_enablement_readiness_receipt") is True
            and owner_pack_decision.get("requires_decision_accept_or_reject") is True
            and owner_pack_decision.get("requires_signature_or_hash") is True
            and owner_pack_decision.get("audit_event_recorded_by_sdk_invoke") is False
            and owner_pack_decision.get("runtime_flag_enabled") is False
            and owner_pack_decision.get("execute_enabled") is False
            and owner_pack_decision.get("write_runner_enabled") is False
            and owner_pack_decision.get("adapter_execution_enabled") is False
            and owner_pack_decision.get("agent_execution_enabled") is False
            and owner_pack_decision.get("runner_invoked") is False
            and owner_pack_decision.get("mark_executed") is False
            and owner_pack_decision.get("mutation_performed") is False
            else "failed",
            details=owner_pack_decision,
            error=None
            if owner_pack_decision.get("workflow_status") == "ready_but_disabled"
            else "runtime enablement owner pack decision workflow is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_implementation_readiness_lock_workflow_ready",
            status="passed"
            if readiness_lock.get("stage") == "runtime_implementation_readiness_lock_record_workflow"
            and readiness_lock.get("workflow_status") == "ready_but_disabled"
            and readiness_lock.get("endpoint")
            == "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record"
            and readiness_lock.get("audit_action")
            == "sdk.write_runner.runtime_implementation_readiness_lock_recorded"
            and readiness_lock.get("requires_approved_sdk_approval") is True
            and readiness_lock.get("requires_runtime_enablement_readiness_receipt") is True
            and readiness_lock.get("requires_accepted_owner_pack_decision") is True
            and readiness_lock.get("requires_idempotency_key") is True
            and readiness_lock.get("requires_idempotency_hash") is True
            and readiness_lock.get("requires_signature_or_hash") is True
            and readiness_lock.get("audit_event_recorded_by_sdk_invoke") is False
            and readiness_lock.get("runtime_flag_enabled") is False
            and readiness_lock.get("execute_enabled") is False
            and readiness_lock.get("write_runner_enabled") is False
            and readiness_lock.get("adapter_execution_enabled") is False
            and readiness_lock.get("agent_execution_enabled") is False
            and readiness_lock.get("runner_invoked") is False
            and readiness_lock.get("mark_executed") is False
            and readiness_lock.get("mutation_performed") is False
            else "failed",
            details=readiness_lock,
            error=None
            if readiness_lock.get("workflow_status") == "ready_but_disabled"
            else "runtime implementation readiness lock workflow is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_implementation_owner_pack_ready",
            status="passed"
            if implementation_owner_pack.get("stage") == "runtime_implementation_owner_acceptance_pack"
            and implementation_owner_pack.get("pack_status") == "ready_but_disabled"
            and implementation_owner_pack.get("pack_type")
            == "sdk_write_runner_runtime_implementation_owner_review_pack"
            and "runtime_implementation_readiness_lock_record"
            in implementation_owner_pack.get("required_evidence", [])
            and "runtime_implementation_readiness_lock_readback"
            in implementation_owner_pack.get("required_evidence", [])
            and implementation_owner_pack.get("readback_contract", {}).get("evidence_type")
            == "sdk_write_runner_runtime_implementation_readiness_lock"
            and implementation_owner_pack.get("owner_decision_policy", {}).get(
                "can_enable_runtime_flag_after_pack"
            )
            is False
            and implementation_owner_pack.get("owner_decision_policy", {}).get(
                "can_invoke_write_runner_after_pack"
            )
            is False
            and implementation_owner_pack.get("implementation_enabled") is False
            and implementation_owner_pack.get("runtime_flag_enabled") is False
            and implementation_owner_pack.get("execute_enabled") is False
            and implementation_owner_pack.get("write_runner_enabled") is False
            and implementation_owner_pack.get("adapter_execution_enabled") is False
            and implementation_owner_pack.get("agent_execution_enabled") is False
            and implementation_owner_pack.get("runner_invoked") is False
            and implementation_owner_pack.get("mark_executed") is False
            and implementation_owner_pack.get("mutation_performed") is False
            else "failed",
            details=implementation_owner_pack,
            error=None
            if implementation_owner_pack.get("pack_status") == "ready_but_disabled"
            else "runtime implementation owner pack is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_implementation_final_decision_workflow_ready",
            status="passed"
            if final_decision.get("stage") == "runtime_implementation_final_decision_record_workflow"
            and final_decision.get("workflow_status") == "ready_but_disabled"
            and final_decision.get("endpoint")
            == "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record"
            and final_decision.get("audit_action")
            == "sdk.write_runner.runtime_implementation_final_decision_recorded"
            and final_decision.get("requires_approved_sdk_approval") is True
            and final_decision.get("requires_runtime_implementation_readiness_lock") is True
            and final_decision.get("requires_decision_accept_or_reject") is True
            and final_decision.get("requires_signature_or_hash") is True
            and final_decision.get("audit_event_recorded_by_sdk_invoke") is False
            and final_decision.get("decision_effect", {}).get("enables_runtime_flag") is False
            and final_decision.get("decision_effect", {}).get("starts_agent_execution") is False
            and final_decision.get("decision_effect", {}).get("marks_approval_executed") is False
            and final_decision.get("implementation_enabled") is False
            and final_decision.get("runtime_flag_enabled") is False
            and final_decision.get("execute_enabled") is False
            and final_decision.get("write_runner_enabled") is False
            and final_decision.get("adapter_execution_enabled") is False
            and final_decision.get("agent_execution_enabled") is False
            and final_decision.get("runner_invoked") is False
            and final_decision.get("mark_executed") is False
            and final_decision.get("mutation_performed") is False
            else "failed",
            details=final_decision,
            error=None
            if final_decision.get("workflow_status") == "ready_but_disabled"
            else "runtime implementation final decision workflow is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_flag_enablement_record_workflow_ready",
            status="passed"
            if runtime_flag_enablement.get("stage") == "runtime_flag_enablement_record_workflow"
            and runtime_flag_enablement.get("workflow_status") == "ready_but_disabled"
            and runtime_flag_enablement.get("endpoint")
            == "/api/v1/control-plane/sdk/runtime-flag/enablement/record"
            and runtime_flag_enablement.get("audit_action")
            == "sdk.write_runner.runtime_flag_enablement_requested"
            and runtime_flag_enablement.get("requires_approved_sdk_approval") is True
            and runtime_flag_enablement.get("requires_runtime_implementation_final_decision") is True
            and runtime_flag_enablement.get("requires_final_decision_accepted") is True
            and runtime_flag_enablement.get("requires_runtime_flag_name")
            == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
            and runtime_flag_enablement.get("requires_signature_or_hash") is True
            and runtime_flag_enablement.get("audit_event_recorded_by_sdk_invoke") is False
            and runtime_flag_enablement.get("decision_effect", {}).get("enables_runtime_flag") is False
            and runtime_flag_enablement.get("decision_effect", {}).get("starts_agent_execution") is False
            and runtime_flag_enablement.get("decision_effect", {}).get("marks_approval_executed") is False
            and runtime_flag_enablement.get("implementation_enabled") is False
            and runtime_flag_enablement.get("runtime_flag_enabled") is False
            and runtime_flag_enablement.get("execute_enabled") is False
            and runtime_flag_enablement.get("write_runner_enabled") is False
            and runtime_flag_enablement.get("adapter_execution_enabled") is False
            and runtime_flag_enablement.get("agent_execution_enabled") is False
            and runtime_flag_enablement.get("runner_invoked") is False
            and runtime_flag_enablement.get("mark_executed") is False
            and runtime_flag_enablement.get("mutation_performed") is False
            else "failed",
            details=runtime_flag_enablement,
            error=None
            if runtime_flag_enablement.get("workflow_status") == "ready_but_disabled"
            else "runtime flag enablement record workflow is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_flag_application_preflight_workflow_ready",
            status="passed"
            if runtime_flag_preflight.get("stage") == "runtime_flag_application_preflight_record_workflow"
            and runtime_flag_preflight.get("workflow_status") == "ready_but_disabled"
            and runtime_flag_preflight.get("endpoint")
            == "/api/v1/control-plane/sdk/runtime-flag/application-preflight/record"
            and runtime_flag_preflight.get("audit_action")
            == "sdk.write_runner.runtime_flag_application_preflight_recorded"
            and runtime_flag_preflight.get("requires_approved_sdk_approval") is True
            and runtime_flag_preflight.get("requires_runtime_flag_enablement_intent") is True
            and runtime_flag_preflight.get("requires_runtime_flag_name")
            == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
            and runtime_flag_preflight.get("requires_target_state") == "enabled"
            and runtime_flag_preflight.get("requires_rollback_plan") is True
            and runtime_flag_preflight.get("requires_smoke_runbook") is True
            and runtime_flag_preflight.get("requires_signature_or_hash") is True
            and runtime_flag_preflight.get("audit_event_recorded_by_sdk_invoke") is False
            and runtime_flag_preflight.get("decision_effect", {}).get("enables_runtime_flag") is False
            and runtime_flag_preflight.get("decision_effect", {}).get("starts_agent_execution") is False
            and runtime_flag_preflight.get("decision_effect", {}).get("marks_approval_executed") is False
            and runtime_flag_preflight.get("implementation_enabled") is False
            and runtime_flag_preflight.get("runtime_flag_enabled") is False
            and runtime_flag_preflight.get("flag_application_performed") is False
            and runtime_flag_preflight.get("execute_enabled") is False
            and runtime_flag_preflight.get("write_runner_enabled") is False
            and runtime_flag_preflight.get("adapter_execution_enabled") is False
            and runtime_flag_preflight.get("agent_execution_enabled") is False
            and runtime_flag_preflight.get("runner_invoked") is False
            and runtime_flag_preflight.get("mark_executed") is False
            and runtime_flag_preflight.get("mutation_performed") is False
            else "failed",
            details=runtime_flag_preflight,
            error=None
            if runtime_flag_preflight.get("workflow_status") == "ready_but_disabled"
            else "runtime flag application preflight workflow is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_flag_application_owner_approval_workflow_ready",
            status="passed"
            if runtime_flag_approval.get("stage") == "runtime_flag_application_owner_approval_record_workflow"
            and runtime_flag_approval.get("workflow_status") == "ready_but_disabled"
            and runtime_flag_approval.get("endpoint")
            == "/api/v1/control-plane/sdk/runtime-flag/application-approval/record"
            and runtime_flag_approval.get("audit_action")
            == "sdk.write_runner.runtime_flag_application_owner_approval_recorded"
            and runtime_flag_approval.get("requires_approved_sdk_approval") is True
            and runtime_flag_approval.get("requires_runtime_flag_application_preflight") is True
            and runtime_flag_approval.get("requires_decision_accept_or_reject") is True
            and runtime_flag_approval.get("requires_runtime_flag_name")
            == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
            and runtime_flag_approval.get("requires_signature_or_hash") is True
            and runtime_flag_approval.get("audit_event_recorded_by_sdk_invoke") is False
            and runtime_flag_approval.get("decision_effect", {}).get("accepted_enables_runtime_flag") is False
            and runtime_flag_approval.get("decision_effect", {}).get("starts_agent_execution") is False
            and runtime_flag_approval.get("decision_effect", {}).get("marks_approval_executed") is False
            and runtime_flag_approval.get("implementation_enabled") is False
            and runtime_flag_approval.get("runtime_flag_enabled") is False
            and runtime_flag_approval.get("flag_application_performed") is False
            and runtime_flag_approval.get("execute_enabled") is False
            and runtime_flag_approval.get("write_runner_enabled") is False
            and runtime_flag_approval.get("adapter_execution_enabled") is False
            and runtime_flag_approval.get("agent_execution_enabled") is False
            and runtime_flag_approval.get("runner_invoked") is False
            and runtime_flag_approval.get("mark_executed") is False
            and runtime_flag_approval.get("mutation_performed") is False
            else "failed",
            details=runtime_flag_approval,
            error=None
            if runtime_flag_approval.get("workflow_status") == "ready_but_disabled"
            else "runtime flag application owner approval workflow is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_flag_application_execute_contract_workflow_ready",
            status="passed"
            if runtime_flag_execute_contract.get("stage")
            == "runtime_flag_application_execute_contract_record_workflow"
            and runtime_flag_execute_contract.get("workflow_status") == "ready_but_disabled"
            and runtime_flag_execute_contract.get("endpoint")
            == "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record"
            and runtime_flag_execute_contract.get("audit_action")
            == "sdk.write_runner.runtime_flag_application_execute_contract_recorded"
            and runtime_flag_execute_contract.get("requires_approved_sdk_approval") is True
            and runtime_flag_execute_contract.get("requires_runtime_flag_application_owner_approval") is True
            and runtime_flag_execute_contract.get("requires_owner_approval_decision") == "accepted"
            and runtime_flag_execute_contract.get("requires_runtime_flag_name")
            == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
            and runtime_flag_execute_contract.get("requires_idempotency_key") is True
            and runtime_flag_execute_contract.get("requires_idempotency_hash") is True
            and runtime_flag_execute_contract.get("requires_rollback_plan") is True
            and runtime_flag_execute_contract.get("requires_smoke_runbook") is True
            and runtime_flag_execute_contract.get("requires_signature_or_hash") is True
            and runtime_flag_execute_contract.get("audit_event_recorded_by_sdk_invoke") is False
            and runtime_flag_execute_contract.get("decision_effect", {}).get("applies_runtime_flag") is False
            and runtime_flag_execute_contract.get("decision_effect", {}).get("starts_agent_execution") is False
            and runtime_flag_execute_contract.get("decision_effect", {}).get("marks_approval_executed") is False
            and runtime_flag_execute_contract.get("decision_effect", {}).get("invokes_write_runner") is False
            and runtime_flag_execute_contract.get("implementation_enabled") is False
            and runtime_flag_execute_contract.get("runtime_flag_enabled") is False
            and runtime_flag_execute_contract.get("flag_application_performed") is False
            and runtime_flag_execute_contract.get("execute_enabled") is False
            and runtime_flag_execute_contract.get("write_runner_enabled") is False
            and runtime_flag_execute_contract.get("adapter_execution_enabled") is False
            and runtime_flag_execute_contract.get("agent_execution_enabled") is False
            and runtime_flag_execute_contract.get("runner_invoked") is False
            and runtime_flag_execute_contract.get("mark_executed") is False
            and runtime_flag_execute_contract.get("mutation_performed") is False
            else "failed",
            details=runtime_flag_execute_contract,
            error=None
            if runtime_flag_execute_contract.get("workflow_status") == "ready_but_disabled"
            else "runtime flag application execute contract workflow is not ready but disabled",
        ),
        SDKNonInteractiveCheck(
            name="runtime_flag_application_execute_contract_owner_review_ready",
            status="passed"
            if runtime_flag_execute_contract_review.get("stage")
            == "runtime_flag_application_execute_contract_owner_review"
            and runtime_flag_execute_contract_review.get("review_status") == "ready_but_disabled"
            and runtime_flag_execute_contract_review.get("review_pack_type")
            == "sdk_write_runner_runtime_flag_application_execute_contract_owner_review"
            and runtime_flag_execute_contract_review.get("source_workflow")
            == "runtime_flag_application_execute_contract_record_workflow"
            and runtime_flag_execute_contract_review.get("owner_review_policy", {}).get(
                "manual_review_required"
            )
            is True
            and runtime_flag_execute_contract_review.get("owner_review_policy", {}).get(
                "independent_review_required"
            )
            is True
            and runtime_flag_execute_contract_review.get("owner_review_policy", {}).get(
                "requires_live_application_request"
            )
            is True
            and runtime_flag_execute_contract_review.get("owner_review_policy", {}).get(
                "can_apply_runtime_flag_after_review"
            )
            is False
            and runtime_flag_execute_contract_review.get("owner_review_policy", {}).get(
                "can_invoke_write_runner_after_review"
            )
            is False
            and runtime_flag_execute_contract_review.get("review_readback", {}).get("method")
            == "runtime/evidence/read"
            and runtime_flag_execute_contract_review.get("runtime_flag_enabled") is False
            and runtime_flag_execute_contract_review.get("flag_application_performed") is False
            and runtime_flag_execute_contract_review.get("execute_enabled") is False
            and runtime_flag_execute_contract_review.get("write_runner_enabled") is False
            and runtime_flag_execute_contract_review.get("adapter_execution_enabled") is False
            and runtime_flag_execute_contract_review.get("agent_execution_enabled") is False
            and runtime_flag_execute_contract_review.get("runner_invoked") is False
            and runtime_flag_execute_contract_review.get("mark_executed") is False
            and runtime_flag_execute_contract_review.get("mutation_performed") is False
            else "failed",
            details=runtime_flag_execute_contract_review,
            error=None
            if runtime_flag_execute_contract_review.get("review_status") == "ready_but_disabled"
            else "runtime flag application execute contract owner review is not ready but disabled",
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
        "status": "sdk_runtime_flag_application_execute_contract_owner_review_ready",
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
            "status": "sdk_runtime_flag_application_execute_contract_owner_review_ready",
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
        "write_runner_runtime_flag": {
            "stage": "owner_approved_write_runner_runtime_feature_flag",
            "flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "flag_status": "declared_disabled",
            "default_enabled": False,
            "env_var": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "owner_acceptance_evidence_required": True,
            "required_owner_evidence": [
                "owner_acceptance_id",
                "accepted_by",
                "accepted_at",
                "approval_id",
                "runbook_acknowledged",
                "rollback_plan_acknowledged",
            ],
            "required_runtime_guards": [
                "runtime_flag_enabled",
                "owner_acceptance_evidence_present",
                "adapter_review_ready",
                "approval_status_approved",
                "idempotency_key_present",
                "dry_run_receipt_persisted",
                "audit_hmac_available",
            ],
            "next_gate": "owner_acceptance_evidence_record",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
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
        "owner_acceptance_evidence": {
            "stage": "owner_acceptance_evidence_record",
            "evidence_status": "recording_contract_ready_not_provided",
            "recording_contract_ready": True,
            "recording_action": "sdk.write_runner.owner_acceptance_recorded",
            "resource_type": "sdk_write_runner_owner_acceptance",
            "required_fields": [
                "owner_acceptance_id",
                "accepted_by",
                "accepted_at",
                "approval_id",
                "runbook_acknowledged",
                "rollback_plan_acknowledged",
            ],
            "schema": {
                "type": "object",
                "required": [
                    "owner_acceptance_id",
                    "accepted_by",
                    "accepted_at",
                    "approval_id",
                    "runbook_acknowledged",
                    "rollback_plan_acknowledged",
                ],
                "properties": {
                    "owner_acceptance_id": "string",
                    "accepted_by": "string",
                    "accepted_at": "RFC3339 timestamp",
                    "approval_id": "string",
                    "runbook_acknowledged": "boolean true",
                    "rollback_plan_acknowledged": "boolean true",
                    "acceptance_signature": "string optional",
                    "acceptance_hash": "string optional",
                    "notes": "string optional",
                },
            },
            "evidence_readback_method": "runtime/evidence/read",
            "evidence_type": "sdk_write_runner_owner_acceptance",
            "acceptance_report_name": "sdk-write-runner-owner-acceptance.json",
            "readback_contract": {
                "endpoint": "/api/v1/control-plane/invoke",
                "method": "runtime/evidence/read",
                "query_keys": ["approval_id", "owner_acceptance_id", "audit_id"],
                "returns_schema": True,
                "returns_record_if_present": True,
            },
            "recording_contract": {
                "audit_action": "sdk.write_runner.owner_acceptance_recorded",
                "resource_type": "sdk_write_runner_owner_acceptance",
                "signature_or_hash_required": True,
                "valid_record_requires": [
                    "all_required_fields_present",
                    "accepted_at_rfc3339",
                    "runbook_acknowledged_true",
                    "rollback_plan_acknowledged_true",
                    "acceptance_signature_or_hash_present",
                ],
                "created_by_sdk_invoke": False,
            },
            "next_gate": "owner_approved_write_runner_runtime_enablement",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
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
        "owner_acceptance_record_workflow": {
            "stage": "owner_acceptance_evidence_record_workflow",
            "endpoint": "/api/v1/control-plane/sdk/owner-acceptance/record",
            "http_method": "POST",
            "cli_command": "xagent sdk acceptance-record --approval-id <approval_id> --acceptance-id <owner_acceptance_id> --accepted-by <owner> --accepted-at <rfc3339> --acceptance-hash <hash> --runbook-acknowledged --rollback-plan-acknowledged --execute",
            "audit_action": "sdk.write_runner.owner_acceptance_recorded",
            "resource_type": "sdk_write_runner_owner_acceptance",
            "requires_approved_sdk_approval": True,
            "requires_signature_or_hash": True,
            "requires_runbook_acknowledged": True,
            "requires_rollback_plan_acknowledged": True,
            "requires_strict_readback_keys": ["approval_id", "owner_acceptance_id", "audit_id"],
            "readback_method": "runtime/evidence/read",
            "marks_approval_executed": False,
            "runtime_flag_enabled": False,
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
        "runtime_enablement_review": {
            "stage": "owner_approved_write_runner_runtime_enablement_review",
            "review_status": "ready_but_disabled",
            "required_evidence_type": "sdk_write_runner_owner_acceptance",
            "required_audit_action": "sdk.write_runner.owner_acceptance_recorded",
            "required_readback_keys": ["approval_id", "owner_acceptance_id", "audit_id"],
            "required_runtime_guards": [
                "runtime_flag_enabled",
                "owner_acceptance_audit_record_valid",
                "approval_status_approved",
                "adapter_review_ready",
                "execute_gate_ready",
                "dry_run_receipt_safety_review_passed",
                "idempotency_key_present",
            ],
            "next_gate": "owner_approved_write_runner_concrete_runner_implementation",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
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
        "write_runner_implementation_plan": {
            "stage": "owner_approved_write_runner_concrete_implementation_plan",
            "plan_status": "ready_but_disabled",
            "adapter_target": {
                "module": "backend.app.core.agent.coordinator",
                "callable": "AgentCoordinator.run",
                "request_mapping": {
                    "thread/start": "task",
                    "thread/resume": "input",
                    "turn/start": "input",
                },
                "expected_context_fields": [
                    "tenant_id",
                    "user_id",
                    "request_id",
                    "permission_scope",
                    "risk_level",
                ],
            },
            "implementation_steps": [
                "resolve_owner_acceptance_record_by_strict_keys",
                "read_approved_sdk_approval",
                "verify_runtime_flag_enabled",
                "build_agent_run_request_from_sdk_envelope",
                "invoke_agent_runner_once_with_idempotency_key",
                "persist_result_receipt_and_audit_hash",
                "mark_approval_executed_after_runner_success",
                "return_control_plane_result_receipt",
            ],
            "rollback_plan": {
                "disable_runtime_flag": True,
                "do_not_mark_approval_executed_on_failure": True,
                "persist_failure_receipt": True,
                "restore_owner_gate_required": True,
                "operator_runbook": "docs/runbooks/sdk-write-runner-runtime-enable.md",
            },
            "idempotency_contract": {
                "required": True,
                "key_source": "ControlPlaneInvokeRequest.idempotency_key",
                "dedupe_scope": ["tenant_id", "method", "approved_approval_id", "idempotency_key"],
                "duplicate_behavior": "return_existing_result_receipt_without_reinvoking_runner",
            },
            "audit_result_shape": {
                "planned_action": "sdk.write_runner.implementation_plan_ready",
                "future_start_action": "sdk.write_runner.execution_started",
                "future_success_action": "sdk.write_runner.executed",
                "future_failure_action": "sdk.write_runner.failed",
                "required_result_fields": [
                    "result_receipt_id",
                    "approval_id",
                    "owner_acceptance_id",
                    "audit_id",
                    "agent_trace_id",
                    "idempotency_key_hash",
                    "runner_status",
                    "mutation_summary",
                ],
            },
            "owner_enablement_steps": [
                "approve_sdk_command",
                "record_owner_acceptance_evidence",
                "verify_runtime_enablement_review",
                "set_XAGENT_SDK_WRITE_RUNNER_ENABLED_true",
                "run_sdk_write_runner_smoke",
                "review_result_receipt_before_general_availability",
            ],
            "next_gate": "owner_approved_write_runner_runtime_implementation",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_smoke_runbook": {
            "stage": "owner_approved_write_runner_runtime_smoke_runbook",
            "contract_status": "ready_but_disabled",
            "runbook_path": "docs/runbooks/sdk-write-runner-runtime-enable.md",
            "smoke_plan": {
                "command": "xagent sdk turn-run <thread_id> <input> --execute --approved-approval-id <approval_id> --idempotency-key <key>",
                "requires_runtime_flag": "XAGENT_SDK_WRITE_RUNNER_ENABLED=true",
                "requires_owner_acceptance_evidence": True,
                "requires_result_receipt_review": True,
                "expected_receipt_status": "dry_run_until_runtime_enabled",
            },
            "rollback_plan": {
                "first_step": "set XAGENT_SDK_WRITE_RUNNER_ENABLED=false",
                "second_step": "verify approvals remain unexecuted for failed runs",
                "third_step": "read sdk.write_runner.failed audit receipt",
                "failure_receipt_required": True,
                "operator_runbook": "docs/runbooks/sdk-write-runner-runtime-enable.md",
            },
            "failure_receipt_contract": {
                "audit_action": "sdk.write_runner.failed",
                "required_fields": [
                    "approval_id",
                    "owner_acceptance_id",
                    "idempotency_key_hash",
                    "failure_reason",
                    "rollback_required",
                    "mark_executed",
                    "mutation_summary",
                ],
                "mark_executed_must_be_false_on_failure": True,
                "runner_reinvoke_allowed": False,
            },
            "owner_checklist": [
                "confirm_owner_acceptance_record_readback",
                "confirm_runtime_enablement_review_ready",
                "confirm_implementation_plan_ready",
                "enable_runtime_flag_for_smoke_only",
                "run_single_idempotent_smoke",
                "review_success_or_failure_receipt",
                "disable_runtime_flag_after_smoke",
            ],
            "next_gate": "owner_approved_write_runner_runtime_implementation",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_enablement_receipt": {
            "stage": "owner_approved_write_runner_runtime_enablement_receipt",
            "receipt_status": "ready_but_disabled",
            "receipt_type": "sdk_write_runner_runtime_enablement_readiness",
            "receipt_schema": {
                "required_fields": [
                    "readiness_receipt_id",
                    "approval_id",
                    "owner_acceptance_id",
                    "runtime_flag_name",
                    "smoke_runbook_version",
                    "rollback_runbook_version",
                    "expires_at",
                    "accepted_by",
                    "acceptance_hash",
                ],
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "expires_at_required": True,
                "acceptance_hash_required": True,
            },
            "review_readback": {
                "method": "runtime/evidence/read",
                "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
                "query_keys": ["readiness_receipt_id", "approval_id", "owner_acceptance_id"],
                "returns_schema": True,
                "returns_record_if_present": True,
            },
            "owner_review_policy": {
                "requires_smoke_runbook_acknowledged": True,
                "requires_rollback_runbook_acknowledged": True,
                "requires_failure_receipt_review": True,
                "requires_expiry": True,
                "revoke_command": "xagent sdk runtime-enable revoke <readiness_receipt_id>",
            },
            "audit_contract": {
                "planned_action": "sdk.write_runner.runtime_enablement_receipt_ready",
                "future_record_action": "sdk.write_runner.runtime_enablement_receipt_recorded",
                "future_revoke_action": "sdk.write_runner.runtime_enablement_receipt_revoked",
                "resource_type": "sdk_write_runner_runtime_enablement_readiness",
            },
            "next_gate": "owner_approved_write_runner_runtime_implementation",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_implementation_preflight": {
            "stage": "owner_approved_write_runner_runtime_implementation_preflight",
            "preflight_status": "ready_but_disabled",
            "adapter_module_boundary": {
                "module": "backend.app.core.agent.coordinator",
                "class": "AgentCoordinator",
                "callable": "AgentCoordinator.run",
                "import_allowed": False,
                "instantiation_allowed": False,
                "execution_allowed": False,
            },
            "dependency_injection_contract": {
                "required": True,
                "factory_name": "sdk_write_runner_factory",
                "injects": [
                    "approval_store",
                    "audit_store",
                    "agent_coordinator",
                    "receipt_store",
                    "runtime_flag_reader",
                ],
                "default_factory_enabled": False,
                "runtime_override_allowed": False,
            },
            "idempotency_lock_contract": {
                "required": True,
                "lock_scope": ["tenant_id", "approval_id", "owner_acceptance_id", "idempotency_key"],
                "lock_action": "sdk.write_runner.idempotency_lock_acquired",
                "duplicate_behavior": "return_existing_result_receipt_without_runner_invocation",
                "lock_enabled": False,
            },
            "receipt_persistence_interface": {
                "required": True,
                "interface": "SDKWriteRunnerReceiptStore",
                "success_action": "sdk.write_runner.executed",
                "failure_action": "sdk.write_runner.failed",
                "readback_method": "runtime/evidence/read",
                "required_result_fields": [
                    "result_receipt_id",
                    "readiness_receipt_id",
                    "approval_id",
                    "owner_acceptance_id",
                    "agent_trace_id",
                    "runner_status",
                    "idempotency_key_hash",
                    "mutation_summary",
                ],
                "persistence_enabled": False,
            },
            "approval_postcondition_contract": {
                "mark_executed_action": "approval.mark_executed",
                "allowed_only_after": [
                    "runtime_flag_enabled",
                    "idempotency_lock_acquired",
                    "agent_runner_success",
                    "success_receipt_persisted",
                    "audit_success_recorded",
                ],
                "failure_postcondition": "mark_executed_must_remain_false",
                "mark_executed_enabled": False,
            },
            "failure_handling_contract": {
                "failure_action": "sdk.write_runner.failed",
                "persist_failure_receipt": True,
                "release_idempotency_lock_on_failure": True,
                "disable_runtime_flag_on_operator_rollback": True,
                "runner_reinvoke_allowed": False,
                "mark_executed_on_failure": False,
            },
            "next_gate": "owner_approved_write_runner_runtime_implementation",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_enablement_receipt_record_workflow": {
            "stage": "runtime_enablement_readiness_receipt_record_workflow",
            "workflow_status": "ready_but_disabled",
            "endpoint": "/api/v1/control-plane/sdk/runtime-enablement/receipt/record",
            "sdk_operation": "runtime_enablement_receipt_record",
            "cli_command": "xagent sdk runtime-enable-receipt-record --execute",
            "requires_approved_sdk_approval": True,
            "requires_owner_acceptance_audit_record": True,
            "requires_signature_or_hash": True,
            "requires_expiry": True,
            "requires_smoke_runbook_acknowledged": True,
            "requires_rollback_runbook_acknowledged": True,
            "requires_failure_receipt_reviewed": True,
            "audit_action": "sdk.write_runner.runtime_enablement_receipt_recorded",
            "resource_type": "sdk_write_runner_runtime_enablement_readiness",
            "readback_contract": {
                "method": "runtime/evidence/read",
                "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
                "report_name": "sdk-write-runner-runtime-enable-readiness.json",
                "query_keys": ["readiness_receipt_id", "approval_id", "owner_acceptance_id", "audit_id"],
                "returns_schema": True,
                "returns_record_if_present": True,
            },
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_enablement_owner_pack": {
            "stage": "runtime_enablement_owner_acceptance_pack",
            "pack_status": "ready_but_disabled",
            "pack_type": "sdk_write_runner_runtime_enablement_owner_review_pack",
            "source_workflow": "runtime_enablement_readiness_receipt_record_workflow",
            "required_evidence": [
                "approved_sdk_approval",
                "owner_acceptance_audit_record",
                "runtime_enablement_readiness_receipt_record",
                "runtime_enablement_readiness_receipt_readback",
                "smoke_runbook_acknowledgement",
                "rollback_runbook_acknowledgement",
                "failure_receipt_review",
                "expiry_window",
            ],
            "owner_review_sections": [
                "approval",
                "owner_acceptance",
                "readiness_receipt",
                "readback",
                "smoke_runbook",
                "rollback",
                "failure_receipt",
                "expiry",
                "disabled_execution_invariants",
            ],
            "readback_contract": {
                "method": "runtime/evidence/read",
                "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
                "query_keys": ["readiness_receipt_id", "approval_id", "owner_acceptance_id", "audit_id"],
                "record_required_before_runtime_flag": True,
            },
            "audit_contract": {
                "review_action": "sdk.write_runner.runtime_enablement_owner_pack_reviewed",
                "source_record_action": "sdk.write_runner.runtime_enablement_receipt_recorded",
                "resource_type": "sdk_write_runner_runtime_enablement_owner_review_pack",
                "audit_event_recorded_now": False,
            },
            "owner_decision_policy": {
                "manual_review_required": True,
                "can_enable_runtime_flag_after_pack": False,
                "next_gate": "owner_approved_write_runner_runtime_implementation",
                "rollback_required_before_any_smoke": True,
            },
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_enablement_owner_pack_decision_workflow": {
            "stage": "runtime_enablement_owner_pack_decision_record_workflow",
            "workflow_status": "ready_but_disabled",
            "endpoint": "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record",
            "sdk_operation": "runtime_enablement_owner_pack_decision_record",
            "cli_command": "xagent sdk runtime-enable-owner-pack-decision-record --execute",
            "requires_approved_sdk_approval": True,
            "requires_runtime_enablement_readiness_receipt": True,
            "requires_decision_accept_or_reject": True,
            "requires_signature_or_hash": True,
            "audit_action": "sdk.write_runner.runtime_enablement_owner_pack_decision_recorded",
            "resource_type": "sdk_write_runner_runtime_enablement_owner_review_pack",
            "audit_event_recorded_by_sdk_invoke": False,
            "allowed_decisions": ["accepted", "rejected"],
            "decision_effect": {
                "accepted_enables_runtime_flag": False,
                "rejected_rolls_back_runtime": False,
                "marks_approval_executed": False,
            },
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_implementation_readiness_lock_workflow": {
            "stage": "runtime_implementation_readiness_lock_record_workflow",
            "workflow_status": "ready_but_disabled",
            "endpoint": "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
            "sdk_operation": "runtime_implementation_readiness_lock_record",
            "cli_command": "xagent sdk runtime-implementation-readiness-lock-record --execute",
            "requires_approved_sdk_approval": True,
            "requires_runtime_enablement_readiness_receipt": True,
            "requires_accepted_owner_pack_decision": True,
            "requires_idempotency_key": True,
            "requires_idempotency_hash": True,
            "requires_signature_or_hash": True,
            "audit_action": "sdk.write_runner.runtime_implementation_readiness_lock_recorded",
            "resource_type": "sdk_write_runner_runtime_implementation_readiness_lock",
            "audit_event_recorded_by_sdk_invoke": False,
            "lock_effect": {
                "enables_runtime_flag": False,
                "starts_agent_execution": False,
                "marks_approval_executed": False,
                "persists_runner_default": False,
            },
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_implementation_owner_pack": {
            "stage": "runtime_implementation_owner_acceptance_pack",
            "pack_status": "ready_but_disabled",
            "pack_type": "sdk_write_runner_runtime_implementation_owner_review_pack",
            "source_workflow": "runtime_implementation_readiness_lock_record_workflow",
            "required_evidence": [
                "approved_sdk_approval",
                "runtime_enablement_readiness_receipt_record",
                "accepted_owner_pack_decision",
                "runtime_implementation_readiness_lock_record",
                "runtime_implementation_readiness_lock_readback",
                "idempotency_key_and_hash",
                "disabled_execution_invariants",
            ],
            "owner_review_sections": [
                "approval",
                "readiness_receipt",
                "owner_pack_decision",
                "readiness_lock",
                "readback",
                "idempotency",
                "disabled_execution_invariants",
            ],
            "readback_contract": {
                "method": "runtime/evidence/read",
                "evidence_type": "sdk_write_runner_runtime_implementation_readiness_lock",
                "report_name": "sdk-write-runner-runtime-implementation-readiness-lock.json",
                "query_keys": [
                    "implementation_lock_id",
                    "approval_id",
                    "readiness_receipt_id",
                    "owner_pack_decision_id",
                    "audit_id",
                ],
                "record_required_before_runtime_implementation": True,
            },
            "audit_contract": {
                "review_action": "sdk.write_runner.runtime_implementation_owner_pack_reviewed",
                "source_record_action": "sdk.write_runner.runtime_implementation_readiness_lock_recorded",
                "resource_type": "sdk_write_runner_runtime_implementation_owner_review_pack",
                "audit_event_recorded_now": False,
            },
            "owner_decision_policy": {
                "manual_review_required": True,
                "can_enable_runtime_flag_after_pack": False,
                "can_invoke_write_runner_after_pack": False,
                "next_gate": "owner_approved_write_runner_runtime_implementation_final_decision",
            },
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_implementation_final_decision_workflow": {
            "stage": "runtime_implementation_final_decision_record_workflow",
            "workflow_status": "ready_but_disabled",
            "endpoint": "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
            "sdk_operation": "runtime_implementation_final_decision_record",
            "cli_command": "xagent sdk runtime-implementation-final-decision-record --execute",
            "requires_approved_sdk_approval": True,
            "requires_runtime_implementation_readiness_lock": True,
            "requires_decision_accept_or_reject": True,
            "requires_signature_or_hash": True,
            "audit_action": "sdk.write_runner.runtime_implementation_final_decision_recorded",
            "resource_type": "sdk_write_runner_runtime_implementation_final_decision",
            "audit_event_recorded_by_sdk_invoke": False,
            "decision_effect": {
                "enables_runtime_flag": False,
                "starts_agent_execution": False,
                "marks_approval_executed": False,
                "persists_runner_default": False,
            },
            "next_gate": "owner_explicit_runtime_flag_enablement_and_live_runner_implementation",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_flag_enablement_record_workflow": {
            "stage": "runtime_flag_enablement_record_workflow",
            "workflow_status": "ready_but_disabled",
            "endpoint": "/api/v1/control-plane/sdk/runtime-flag/enablement/record",
            "sdk_operation": "runtime_flag_enablement_record",
            "cli_command": "xagent sdk runtime-flag-enable-record --execute",
            "requires_approved_sdk_approval": True,
            "requires_runtime_implementation_final_decision": True,
            "requires_final_decision_accepted": True,
            "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "requires_signature_or_hash": True,
            "audit_action": "sdk.write_runner.runtime_flag_enablement_requested",
            "resource_type": "sdk_write_runner_runtime_flag_enablement_request",
            "audit_event_recorded_by_sdk_invoke": False,
            "decision_effect": {
                "enables_runtime_flag": False,
                "starts_agent_execution": False,
                "marks_approval_executed": False,
                "persists_runner_default": False,
            },
            "next_gate": "owner_requested_live_runtime_flag_application_and_write_runner_implementation",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_flag_application_preflight_workflow": {
            "stage": "runtime_flag_application_preflight_record_workflow",
            "workflow_status": "ready_but_disabled",
            "endpoint": "/api/v1/control-plane/sdk/runtime-flag/application-preflight/record",
            "sdk_operation": "runtime_flag_application_preflight_record",
            "cli_command": "xagent sdk runtime-flag-application-preflight-record --execute",
            "requires_approved_sdk_approval": True,
            "requires_runtime_flag_enablement_intent": True,
            "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "requires_target_state": "enabled",
            "requires_rollback_plan": True,
            "requires_smoke_runbook": True,
            "requires_signature_or_hash": True,
            "audit_action": "sdk.write_runner.runtime_flag_application_preflight_recorded",
            "resource_type": "sdk_write_runner_runtime_flag_application_preflight",
            "audit_event_recorded_by_sdk_invoke": False,
            "decision_effect": {
                "enables_runtime_flag": False,
                "starts_agent_execution": False,
                "marks_approval_executed": False,
                "persists_runner_default": False,
            },
            "next_gate": "owner_requested_live_runtime_flag_application",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_flag_application_owner_approval_workflow": {
            "stage": "runtime_flag_application_owner_approval_record_workflow",
            "workflow_status": "ready_but_disabled",
            "endpoint": "/api/v1/control-plane/sdk/runtime-flag/application-approval/record",
            "sdk_operation": "runtime_flag_application_owner_approval_record",
            "cli_command": "xagent sdk runtime-flag-application-approval-record --execute",
            "requires_approved_sdk_approval": True,
            "requires_runtime_flag_application_preflight": True,
            "requires_decision_accept_or_reject": True,
            "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "requires_signature_or_hash": True,
            "audit_action": "sdk.write_runner.runtime_flag_application_owner_approval_recorded",
            "resource_type": "sdk_write_runner_runtime_flag_application_owner_approval",
            "audit_event_recorded_by_sdk_invoke": False,
            "allowed_decisions": ["accepted", "rejected"],
            "decision_effect": {
                "accepted_enables_runtime_flag": False,
                "rejected_rolls_back_runtime": False,
                "starts_agent_execution": False,
                "marks_approval_executed": False,
                "persists_runner_default": False,
            },
            "next_gate": "owner_requested_live_runtime_flag_application_execute_contract",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_flag_application_execute_contract_workflow": {
            "stage": "runtime_flag_application_execute_contract_record_workflow",
            "workflow_status": "ready_but_disabled",
            "endpoint": "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record",
            "sdk_operation": "runtime_flag_application_execute_contract_record",
            "cli_command": "xagent sdk runtime-flag-application-execute-contract-record --execute",
            "requires_approved_sdk_approval": True,
            "requires_runtime_flag_application_owner_approval": True,
            "requires_owner_approval_decision": "accepted",
            "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "requires_idempotency_key": True,
            "requires_idempotency_hash": True,
            "requires_rollback_plan": True,
            "requires_smoke_runbook": True,
            "requires_signature_or_hash": True,
            "audit_action": "sdk.write_runner.runtime_flag_application_execute_contract_recorded",
            "resource_type": "sdk_write_runner_runtime_flag_application_execute_contract",
            "audit_event_recorded_by_sdk_invoke": False,
            "decision_effect": {
                "applies_runtime_flag": False,
                "starts_agent_execution": False,
                "marks_approval_executed": False,
                "persists_runner_default": False,
                "invokes_write_runner": False,
            },
            "next_gate": "owner_requested_live_runtime_flag_application_implementation",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "file_mutation_performed": False,
            "channel_mutation_performed": False,
        },
        "runtime_flag_application_execute_contract_owner_review": {
            "stage": "runtime_flag_application_execute_contract_owner_review",
            "review_status": "ready_but_disabled",
            "review_pack_type": "sdk_write_runner_runtime_flag_application_execute_contract_owner_review",
            "source_workflow": "runtime_flag_application_execute_contract_record_workflow",
            "required_evidence": [
                "approved_sdk_approval",
                "runtime_flag_application_preflight_record",
                "runtime_flag_application_owner_approval_record",
                "runtime_flag_application_execute_contract_record",
                "idempotency_key_hash",
                "rollback_plan_ref",
                "smoke_runbook_ref",
                "audit_hash",
            ],
            "required_audit_actions": [
                "sdk.write_runner.runtime_flag_application_preflight_recorded",
                "sdk.write_runner.runtime_flag_application_owner_approval_recorded",
                "sdk.write_runner.runtime_flag_application_execute_contract_recorded",
            ],
            "owner_review_policy": {
                "manual_review_required": True,
                "independent_review_required": True,
                "requires_live_application_request": True,
                "can_apply_runtime_flag_after_review": False,
                "can_invoke_write_runner_after_review": False,
                "next_required_owner_request": "implement_live_runtime_flag_application",
            },
            "review_readback": {
                "method": "runtime/evidence/read",
                "evidence_type": "sdk_write_runner_runtime_flag_application_execute_contract",
                "query_keys": [
                    "runtime_flag_execute_contract_id",
                    "approval_id",
                    "runtime_flag_approval_id",
                    "audit_id",
                ],
                "returns_schema": True,
                "returns_record_if_present": False,
            },
            "next_gate": "owner_requested_live_runtime_flag_application_implementation",
            "implementation_enabled": False,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
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
            "Runtime feature flag remains disabled; owner acceptance evidence can be recorded and read back through an audit-backed owner-controlled workflow.",
            "Recording owner acceptance evidence does not execute the SDK write runner or mark the approval executed.",
            "Runtime enablement review is contract-ready but remains disabled and does not implement the concrete runner.",
            "Concrete write-runner implementation plan is ready for owner review but remains disabled.",
            "Runtime smoke/runbook, rollback, and failure receipt contracts are ready for owner review but remain disabled.",
            "Runtime enablement readiness receipt contract is ready for owner review but remains disabled.",
            "Runtime implementation preflight adapter boundaries are ready for owner review but remain disabled.",
            "Runtime enablement readiness receipt recording/readback workflow is owner-gated and remains disabled for execution.",
            "Runtime enablement owner review pack is ready for audit but remains disabled for execution.",
            "Runtime enablement owner pack accept/reject decisions can be recorded, but they do not enable execution.",
            "Runtime implementation owner pack is ready for audit but remains disabled for execution.",
            "Runtime implementation final decisions can be recorded, but they do not enable execution.",
            "Runtime flag enablement intent can be recorded, but it does not set the runtime flag.",
            "Runtime flag application preflight can be recorded, but it does not apply the runtime flag.",
            "Runtime flag application owner approval can be recorded, but it does not apply the runtime flag.",
            "Runtime flag application execute contract can be recorded, but it does not apply the runtime flag or invoke the write runner.",
            "Runtime flag application execute contract owner review is ready, but it does not enable runtime effects.",
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
        f"- `{item['operation']}` -> `{_sdk_contract_method(item)}`"
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
        "## Write Runner Runtime Flag\n\n"
        f"- Stage: `{report.write_runner_runtime_flag['stage']}`\n"
        f"- Flag name: `{report.write_runner_runtime_flag['flag_name']}`\n"
        f"- Flag status: `{report.write_runner_runtime_flag['flag_status']}`\n"
        f"- Runtime flag enabled: `{report.write_runner_runtime_flag['runtime_flag_enabled']}`\n\n"
        "## Owner Acceptance Evidence\n\n"
        f"- Stage: `{report.owner_acceptance_evidence['stage']}`\n"
        f"- Evidence status: `{report.owner_acceptance_evidence['evidence_status']}`\n"
        f"- Acceptance report: `{report.owner_acceptance_evidence['acceptance_report_name']}`\n"
        f"- Execute enabled: `{report.owner_acceptance_evidence['execute_enabled']}`\n\n"
        "## Owner Acceptance Record Workflow\n\n"
        f"- Stage: `{report.owner_acceptance_record_workflow['stage']}`\n"
        f"- Endpoint: `{report.owner_acceptance_record_workflow['endpoint']}`\n"
        f"- Audit action: `{report.owner_acceptance_record_workflow['audit_action']}`\n"
        f"- Marks approval executed: `{report.owner_acceptance_record_workflow['marks_approval_executed']}`\n"
        f"- Write runner enabled: `{report.owner_acceptance_record_workflow['write_runner_enabled']}`\n\n"
        "## Runtime Enablement Review\n\n"
        f"- Stage: `{report.runtime_enablement_review['stage']}`\n"
        f"- Review status: `{report.runtime_enablement_review['review_status']}`\n"
        f"- Required evidence type: `{report.runtime_enablement_review['required_evidence_type']}`\n"
        f"- Runtime flag enabled: `{report.runtime_enablement_review['runtime_flag_enabled']}`\n"
        f"- Write runner enabled: `{report.runtime_enablement_review['write_runner_enabled']}`\n\n"
        "## Write Runner Implementation Plan\n\n"
        f"- Stage: `{report.write_runner_implementation_plan['stage']}`\n"
        f"- Plan status: `{report.write_runner_implementation_plan['plan_status']}`\n"
        f"- Adapter target: `{report.write_runner_implementation_plan['adapter_target']['callable']}`\n"
        f"- Runtime flag enabled: `{report.write_runner_implementation_plan['runtime_flag_enabled']}`\n"
        f"- Write runner enabled: `{report.write_runner_implementation_plan['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.write_runner_implementation_plan['runner_invoked']}`\n\n"
        "## Runtime Smoke Runbook\n\n"
        f"- Stage: `{report.runtime_smoke_runbook['stage']}`\n"
        f"- Contract status: `{report.runtime_smoke_runbook['contract_status']}`\n"
        f"- Runbook path: `{report.runtime_smoke_runbook['runbook_path']}`\n"
        f"- Runtime flag enabled: `{report.runtime_smoke_runbook['runtime_flag_enabled']}`\n"
        f"- Write runner enabled: `{report.runtime_smoke_runbook['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_smoke_runbook['runner_invoked']}`\n\n"
        "## Runtime Enablement Receipt\n\n"
        f"- Stage: `{report.runtime_enablement_receipt['stage']}`\n"
        f"- Receipt status: `{report.runtime_enablement_receipt['receipt_status']}`\n"
        f"- Receipt type: `{report.runtime_enablement_receipt['receipt_type']}`\n"
        f"- Runtime flag enabled: `{report.runtime_enablement_receipt['runtime_flag_enabled']}`\n"
        f"- Write runner enabled: `{report.runtime_enablement_receipt['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_enablement_receipt['runner_invoked']}`\n\n"
        "## Runtime Implementation Preflight\n\n"
        f"- Stage: `{report.runtime_implementation_preflight['stage']}`\n"
        f"- Preflight status: `{report.runtime_implementation_preflight['preflight_status']}`\n"
        f"- Adapter module: `{report.runtime_implementation_preflight['adapter_module_boundary']['module']}`\n"
        f"- Dependency injection required: `{report.runtime_implementation_preflight['dependency_injection_contract']['required']}`\n"
        f"- Idempotency lock enabled: `{report.runtime_implementation_preflight['idempotency_lock_contract']['lock_enabled']}`\n"
        f"- Write runner enabled: `{report.runtime_implementation_preflight['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_implementation_preflight['runner_invoked']}`\n\n"
        "## Runtime Enablement Receipt Record Workflow\n\n"
        f"- Stage: `{report.runtime_enablement_receipt_record_workflow['stage']}`\n"
        f"- Workflow status: `{report.runtime_enablement_receipt_record_workflow['workflow_status']}`\n"
        f"- Endpoint: `{report.runtime_enablement_receipt_record_workflow['endpoint']}`\n"
        f"- Audit action: `{report.runtime_enablement_receipt_record_workflow['audit_action']}`\n"
        f"- Write runner enabled: `{report.runtime_enablement_receipt_record_workflow['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_enablement_receipt_record_workflow['runner_invoked']}`\n\n"
        "## Runtime Enablement Owner Pack\n\n"
        f"- Stage: `{report.runtime_enablement_owner_pack['stage']}`\n"
        f"- Pack status: `{report.runtime_enablement_owner_pack['pack_status']}`\n"
        f"- Pack type: `{report.runtime_enablement_owner_pack['pack_type']}`\n"
        f"- Manual review required: `{report.runtime_enablement_owner_pack['owner_decision_policy']['manual_review_required']}`\n"
        f"- Can enable runtime flag after pack: `{report.runtime_enablement_owner_pack['owner_decision_policy']['can_enable_runtime_flag_after_pack']}`\n"
        f"- Write runner enabled: `{report.runtime_enablement_owner_pack['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_enablement_owner_pack['runner_invoked']}`\n\n"
        "## Runtime Enablement Owner Pack Decision Workflow\n\n"
        f"- Stage: `{report.runtime_enablement_owner_pack_decision_workflow['stage']}`\n"
        f"- Workflow status: `{report.runtime_enablement_owner_pack_decision_workflow['workflow_status']}`\n"
        f"- Endpoint: `{report.runtime_enablement_owner_pack_decision_workflow['endpoint']}`\n"
        f"- Audit action: `{report.runtime_enablement_owner_pack_decision_workflow['audit_action']}`\n"
        f"- Write runner enabled: `{report.runtime_enablement_owner_pack_decision_workflow['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_enablement_owner_pack_decision_workflow['runner_invoked']}`\n\n"
        "## Runtime Implementation Readiness Lock Workflow\n\n"
        f"- Stage: `{report.runtime_implementation_readiness_lock_workflow['stage']}`\n"
        f"- Workflow status: `{report.runtime_implementation_readiness_lock_workflow['workflow_status']}`\n"
        f"- Endpoint: `{report.runtime_implementation_readiness_lock_workflow['endpoint']}`\n"
        f"- Audit action: `{report.runtime_implementation_readiness_lock_workflow['audit_action']}`\n"
        f"- Write runner enabled: `{report.runtime_implementation_readiness_lock_workflow['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_implementation_readiness_lock_workflow['runner_invoked']}`\n\n"
        "## Runtime Implementation Owner Pack\n\n"
        f"- Stage: `{report.runtime_implementation_owner_pack['stage']}`\n"
        f"- Pack status: `{report.runtime_implementation_owner_pack['pack_status']}`\n"
        f"- Pack type: `{report.runtime_implementation_owner_pack['pack_type']}`\n"
        f"- Readback evidence type: `{report.runtime_implementation_owner_pack['readback_contract']['evidence_type']}`\n"
        f"- Can enable runtime flag after pack: `{report.runtime_implementation_owner_pack['owner_decision_policy']['can_enable_runtime_flag_after_pack']}`\n"
        f"- Can invoke write runner after pack: `{report.runtime_implementation_owner_pack['owner_decision_policy']['can_invoke_write_runner_after_pack']}`\n"
        f"- Write runner enabled: `{report.runtime_implementation_owner_pack['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_implementation_owner_pack['runner_invoked']}`\n\n"
        "## Runtime Implementation Final Decision Workflow\n\n"
        f"- Stage: `{report.runtime_implementation_final_decision_workflow['stage']}`\n"
        f"- Workflow status: `{report.runtime_implementation_final_decision_workflow['workflow_status']}`\n"
        f"- Endpoint: `{report.runtime_implementation_final_decision_workflow['endpoint']}`\n"
        f"- Audit action: `{report.runtime_implementation_final_decision_workflow['audit_action']}`\n"
        f"- Next gate: `{report.runtime_implementation_final_decision_workflow['next_gate']}`\n"
        f"- Write runner enabled: `{report.runtime_implementation_final_decision_workflow['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_implementation_final_decision_workflow['runner_invoked']}`\n\n"
        "## Runtime Flag Enablement Record Workflow\n\n"
        f"- Stage: `{report.runtime_flag_enablement_record_workflow['stage']}`\n"
        f"- Workflow status: `{report.runtime_flag_enablement_record_workflow['workflow_status']}`\n"
        f"- Endpoint: `{report.runtime_flag_enablement_record_workflow['endpoint']}`\n"
        f"- Audit action: `{report.runtime_flag_enablement_record_workflow['audit_action']}`\n"
        f"- Runtime flag enabled: `{report.runtime_flag_enablement_record_workflow['runtime_flag_enabled']}`\n"
        f"- Write runner enabled: `{report.runtime_flag_enablement_record_workflow['write_runner_enabled']}`\n"
        f"- Runner invoked: `{report.runtime_flag_enablement_record_workflow['runner_invoked']}`\n\n"
        "## Runtime Flag Application Preflight Workflow\n\n"
        f"- Stage: `{report.runtime_flag_application_preflight_workflow['stage']}`\n"
        f"- Workflow status: `{report.runtime_flag_application_preflight_workflow['workflow_status']}`\n"
        f"- Endpoint: `{report.runtime_flag_application_preflight_workflow['endpoint']}`\n"
        f"- Audit action: `{report.runtime_flag_application_preflight_workflow['audit_action']}`\n"
        f"- Runtime flag enabled: `{report.runtime_flag_application_preflight_workflow['runtime_flag_enabled']}`\n"
        f"- Flag application performed: `{report.runtime_flag_application_preflight_workflow['flag_application_performed']}`\n"
        f"- Runner invoked: `{report.runtime_flag_application_preflight_workflow['runner_invoked']}`\n\n"
        "## Runtime Flag Application Owner Approval Workflow\n\n"
        f"- Stage: `{report.runtime_flag_application_owner_approval_workflow['stage']}`\n"
        f"- Workflow status: `{report.runtime_flag_application_owner_approval_workflow['workflow_status']}`\n"
        f"- Endpoint: `{report.runtime_flag_application_owner_approval_workflow['endpoint']}`\n"
        f"- Audit action: `{report.runtime_flag_application_owner_approval_workflow['audit_action']}`\n"
        f"- Runtime flag enabled: `{report.runtime_flag_application_owner_approval_workflow['runtime_flag_enabled']}`\n"
        f"- Flag application performed: `{report.runtime_flag_application_owner_approval_workflow['flag_application_performed']}`\n"
        f"- Runner invoked: `{report.runtime_flag_application_owner_approval_workflow['runner_invoked']}`\n\n"
        "## Runtime Flag Application Execute Contract Workflow\n\n"
        f"- Stage: `{report.runtime_flag_application_execute_contract_workflow['stage']}`\n"
        f"- Workflow status: `{report.runtime_flag_application_execute_contract_workflow['workflow_status']}`\n"
        f"- Endpoint: `{report.runtime_flag_application_execute_contract_workflow['endpoint']}`\n"
        f"- Audit action: `{report.runtime_flag_application_execute_contract_workflow['audit_action']}`\n"
        f"- Runtime flag enabled: `{report.runtime_flag_application_execute_contract_workflow['runtime_flag_enabled']}`\n"
        f"- Flag application performed: `{report.runtime_flag_application_execute_contract_workflow['flag_application_performed']}`\n"
        f"- Runner invoked: `{report.runtime_flag_application_execute_contract_workflow['runner_invoked']}`\n\n"
        "## Runtime Flag Application Execute Contract Owner Review\n\n"
        f"- Stage: `{report.runtime_flag_application_execute_contract_owner_review['stage']}`\n"
        f"- Review status: `{report.runtime_flag_application_execute_contract_owner_review['review_status']}`\n"
        f"- Review pack type: `{report.runtime_flag_application_execute_contract_owner_review['review_pack_type']}`\n"
        f"- Manual review required: `{report.runtime_flag_application_execute_contract_owner_review['owner_review_policy']['manual_review_required']}`\n"
        f"- Can apply runtime flag after review: `{report.runtime_flag_application_execute_contract_owner_review['owner_review_policy']['can_apply_runtime_flag_after_review']}`\n"
        f"- Runner invoked: `{report.runtime_flag_application_execute_contract_owner_review['runner_invoked']}`\n\n"
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
    return 0 if report.status == "sdk_runtime_flag_application_execute_contract_owner_review_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
