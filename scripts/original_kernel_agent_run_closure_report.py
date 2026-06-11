#!/usr/bin/env python3
"""Validate the original-kernel agent run closure contract.

This module-level probe builds simulated tool-call and trace records, then
checks that the closure decision contract can distinguish ready handoff from
follow-up-required runs without starting a real agent execution.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.agent_run_closure import build_agent_run_closure_report
from backend.app.core.contracts import (
    RiskLevel,
    RunStatus,
    ToolCallRecord,
    ToolPolicyVerdict,
    TraceEvent,
)
from backend.app.core.storage import atomic_write_json

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "original-kernel-agent-run-closure-integration.json"


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _policy(approval_id: str | None = None) -> ToolPolicyVerdict:
    return ToolPolicyVerdict(
        allowed=True,
        reason="original-kernel closure integration probe",
        approval_id=approval_id,
    )


def _tool(
    name: str,
    *,
    success: bool = True,
    output: Any = None,
    error: str | None = None,
    arguments_preview: dict[str, Any] | None = None,
    approval_id: str | None = None,
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=name,
        success=success,
        output=output,
        error=error,
        policy=_policy(approval_id=approval_id),
        risk_level=RiskLevel.LOW,
        arguments_preview=arguments_preview or {},
        trace_id="trace-agent-run-closure",
        request_id="original-kernel-agent-run-closure",
    )


def _trace(event: str, **data: Any) -> TraceEvent:
    return TraceEvent(
        trace_id="trace-agent-run-closure",
        event=event,
        data=data,
        request_id="original-kernel-agent-run-closure",
        agent_id="closure-contract-probe",
        tenant_id="tenant-original-kernel",
        user_id="owner-verifier",
    )


def _ready_report() -> dict[str, Any]:
    return build_agent_run_closure_report(
        task="Apply an approved patch and run focused validation.",
        status=RunStatus.COMPLETED,
        iterations=2,
        memory_hits=1,
        events=[_trace("context.pack")],
        tool_calls=[
            _tool(
                "engineering_stage_patch_approval",
                output={
                    "changed_files": ["backend/app/core/example.py", "tests/test_example.py"],
                    "approval_id": "approval-closure-1",
                    "summary": "simulated approved patch evidence",
                },
                approval_id="approval-closure-1",
            ),
            _tool(
                "engineering_run_validation",
                output={
                    "command": "python -m pytest tests/test_example.py -q",
                    "exit_code": 0,
                    "timed_out": False,
                    "stdout": "1 passed",
                    "stderr": "",
                },
            ),
        ],
        answer="Focused validation passed; ready for handoff.",
    )


def _missing_validation_report() -> dict[str, Any]:
    return build_agent_run_closure_report(
        task="Attempt to claim completion after a patch without validation.",
        status=RunStatus.COMPLETED,
        iterations=1,
        memory_hits=0,
        events=[_trace("context.pack")],
        tool_calls=[
            _tool(
                "engineering_stage_patch_approval",
                output={
                    "changed_files": ["backend/app/core/example.py"],
                    "summary": "simulated patch without validation",
                },
            )
        ],
        answer="Patch applied.",
    )


def _failed_validation_report() -> dict[str, Any]:
    return build_agent_run_closure_report(
        task="Surface validation failure and next repair action.",
        status=RunStatus.FAILED,
        iterations=3,
        memory_hits=1,
        events=[],
        tool_calls=[
            _tool(
                "engineering_run_validation",
                success=False,
                output={
                    "command": "python -m pytest tests/test_example.py -q",
                    "exit_code": 1,
                    "timed_out": False,
                    "stdout": "",
                    "stderr": "assert False",
                    "failure_attribution": {
                        "category": "test_failed",
                        "next_action": "fix_validation_failure_and_rerun",
                    },
                },
                error="validation failed",
            )
        ],
        error="agent stopped after validation failure",
    )


def _ready_handoff_check(report: dict[str, Any]) -> IntegrationCheck:
    phase_states = report.get("phase_states") if isinstance(report.get("phase_states"), dict) else {}
    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    passed = all(
        [
            report.get("kind") == "agent_run_closure_report",
            report.get("version") == 1,
            report.get("status") == "ready_for_handoff",
            report.get("ready_for_handoff") is True,
            report.get("blocking_reasons") == [],
            phase_states.get("execute") == "completed",
            phase_states.get("test") == "passed",
            phase_states.get("report") == "completed",
            evidence.get("tool_call_count") == 2,
        ]
    )
    return IntegrationCheck(
        name="ready_handoff_contract",
        status="passed" if passed else "failed",
        details={
            "status": report.get("status"),
            "ready_for_handoff": report.get("ready_for_handoff"),
            "phase_states": phase_states,
            "blocking_reasons": report.get("blocking_reasons"),
            "tool_call_count": evidence.get("tool_call_count"),
        },
        error=None if passed else "ready handoff closure report did not match expected contract",
    )


def _missing_validation_check(report: dict[str, Any]) -> IntegrationCheck:
    phase_states = report.get("phase_states") if isinstance(report.get("phase_states"), dict) else {}
    blocking_reasons = report.get("blocking_reasons") if isinstance(report.get("blocking_reasons"), list) else []
    next_actions = report.get("next_actions") if isinstance(report.get("next_actions"), list) else []
    passed = all(
        [
            report.get("status") == "needs_followup",
            report.get("ready_for_handoff") is False,
            phase_states.get("test") == "not_started",
            "validation_missing" in blocking_reasons,
            "run_targeted_validation" in next_actions,
        ]
    )
    return IntegrationCheck(
        name="missing_validation_contract",
        status="passed" if passed else "failed",
        details={
            "status": report.get("status"),
            "ready_for_handoff": report.get("ready_for_handoff"),
            "test_phase": phase_states.get("test"),
            "blocking_reasons": blocking_reasons,
            "next_actions": next_actions,
        },
        error=None if passed else "missing validation closure report did not require follow-up",
    )


def _failed_validation_check(report: dict[str, Any]) -> IntegrationCheck:
    phase_states = report.get("phase_states") if isinstance(report.get("phase_states"), dict) else {}
    blocking_reasons = report.get("blocking_reasons") if isinstance(report.get("blocking_reasons"), list) else []
    suggestions = report.get("failure_suggestions") if isinstance(report.get("failure_suggestions"), list) else []
    next_actions = report.get("next_actions") if isinstance(report.get("next_actions"), list) else []
    first_suggestion = suggestions[0] if suggestions and isinstance(suggestions[0], dict) else {}
    passed = all(
        [
            report.get("status") == "needs_followup",
            report.get("ready_for_handoff") is False,
            phase_states.get("test") == "failed",
            "validation_failed" in blocking_reasons,
            "tool_failure" in blocking_reasons,
            first_suggestion.get("category") == "test_failed",
            first_suggestion.get("next_action") == "fix_validation_failure_and_rerun",
            "fix_validation_failure_and_rerun" in next_actions,
        ]
    )
    return IntegrationCheck(
        name="failed_validation_repair_contract",
        status="passed" if passed else "failed",
        details={
            "status": report.get("status"),
            "ready_for_handoff": report.get("ready_for_handoff"),
            "test_phase": phase_states.get("test"),
            "blocking_reasons": blocking_reasons,
            "first_suggestion": first_suggestion,
            "next_actions": next_actions,
        },
        error=None if passed else "failed validation closure report did not expose repair guidance",
    )


def build_report() -> dict[str, Any]:
    ready_report = _ready_report()
    missing_validation_report = _missing_validation_report()
    failed_validation_report = _failed_validation_report()
    checks = [
        _ready_handoff_check(ready_report),
        _missing_validation_check(missing_validation_report),
        _failed_validation_check(failed_validation_report),
    ]
    all_passed = all(check.status == "passed" for check in checks)

    return {
        "status": "original_kernel_agent_run_closure_integration_ready" if all_passed else "failed",
        "generated_at": _utc_now(),
        "evidence_type": "original_kernel_agent_run_closure_integration",
        "modules": ["agent_run_closure"],
        "entrypoints_modified": False,
        "api_router_modified": False,
        "control_plane_modified": False,
        "frontend_modified": False,
        "agent_loop_modified": False,
        "backend_core_init_modified": False,
        "mutation_performed": False,
        "report_file_written": False,
        "network_mutation_performed": False,
        "agent_execution_enabled": False,
        "command_execution_enabled": False,
        "write_runner_invoked": False,
        "real_tool_execution_performed": False,
        "simulated_tool_records_only": True,
        "checks": [asdict(check) for check in checks],
        "artifacts": {
            "ready_handoff": {
                "status": ready_report.get("status"),
                "ready_for_handoff": ready_report.get("ready_for_handoff"),
                "next_actions": ready_report.get("next_actions"),
            },
            "missing_validation": {
                "status": missing_validation_report.get("status"),
                "blocking_reasons": missing_validation_report.get("blocking_reasons"),
                "next_actions": missing_validation_report.get("next_actions"),
            },
            "failed_validation": {
                "status": failed_validation_report.get("status"),
                "blocking_reasons": failed_validation_report.get("blocking_reasons"),
                "failure_suggestions": failed_validation_report.get("failure_suggestions"),
            },
        },
        "known_limits": [
            "This report proves the agent_run_closure decision contract only.",
            "Tool calls and trace events are simulated records; no real agent execution or tool execution is started.",
            "No API router, agent loop, control plane, frontend, or backend core package entrypoint is wired by this report.",
            "No full Codex parity claim is made by this report.",
        ],
        "next_actions": [
            "After review, stage only the agent_run_closure integration files explicitly.",
            "Use long_task_models, long_task_state_machine, and long_task_merge_gates as the next module-level integration slice.",
        ],
    }


def write_report(output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    report = build_report()
    report["report_file_written"] = True
    report["report_path"] = str(output_path)
    atomic_write_json(output_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the JSON integration evidence report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = write_report(args.output)

    print(f"Original kernel agent run closure integration status: {report['status']}")
    print(f"Report written to {args.output}")
    for check in report["checks"]:
        print(f"- {check['name']}: {check['status']}")
        if check.get("error"):
            print(f"  error: {check['error']}")

    return 0 if report["status"] == "original_kernel_agent_run_closure_integration_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
