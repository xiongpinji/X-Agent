#!/usr/bin/env python3
"""Validate original-kernel long-task module contracts.

This module-level probe exercises long-task models, state transitions, and
parallel merge gates with simulated records only. It does not start a real
long-task worker, subagent run, workflow, or merge execution.
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

from backend.app.core.long_task_merge_gates import (
    build_completion_report_merge_gate,
    build_merge_authorization,
    build_validation_evidence_gate,
    decide_parent_acceptance_gate,
)
from backend.app.core.long_task_models import (
    LongTaskCreateRequest,
    LongTaskEvent,
    LongTaskNextAction,
    LongTaskNextActionDecision,
    LongTaskPhaseState,
    LongTaskPhaseStatus,
    LongTaskRecord,
    LongTaskStatus,
)
from backend.app.core.long_task_state_machine import (
    IllegalLongTaskStateTransition,
    LongTaskState,
    LongTaskStateSnapshot,
    is_terminal_long_task_state,
    transition_long_task_state,
)
from backend.app.core.storage import atomic_write_json

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "original-kernel-long-task-integration.json"


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _models_check() -> IntegrationCheck:
    request = LongTaskCreateRequest(
        title="Commercial RC evidence",
        task="Prepare long-task merge gate evidence",
        priority=3,
        context={"source": "original_kernel_integration_probe"},
    )
    phase = LongTaskPhaseState(
        id="phase-validation",
        title="Validation",
        owner="backend",
        status=LongTaskPhaseStatus.ACTIVE,
    )
    event = LongTaskEvent(
        kind="long_task.created",
        status=LongTaskStatus.QUEUED,
        detail="Simulated model contract event.",
    )
    record = LongTaskRecord(
        title=request.title,
        task=request.task,
        priority=request.priority,
        phases=[phase],
        timeline=[event],
    )
    decision = LongTaskNextActionDecision(
        action=LongTaskNextAction.ADVANCE_PHASE,
        reason="Model contract can represent the next long-task step.",
        phase_id=phase.id,
        phase_title=phase.title,
    )

    passed = all(
        [
            request.requires_approval is True,
            request.auto_plan is True,
            record.status == LongTaskStatus.QUEUED,
            record.priority == 3,
            record.phases[0].status == LongTaskPhaseStatus.ACTIVE,
            record.timeline[0].created_at.tzinfo is UTC,
            decision.action == LongTaskNextAction.ADVANCE_PHASE,
            record.context == {},
            record.metadata == {},
        ]
    )
    return IntegrationCheck(
        name="long_task_models_contract",
        status="passed" if passed else "failed",
        details={
            "request_priority": request.priority,
            "requires_approval": request.requires_approval,
            "auto_plan": request.auto_plan,
            "record_status": record.status.value,
            "phase_status": record.phases[0].status.value,
            "timeline_count": len(record.timeline),
            "decision_action": decision.action.value,
        },
        error=None if passed else "long-task Pydantic model contract did not match expected defaults",
    )


def _state_machine_check() -> IntegrationCheck:
    started_at = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    blocked_at = datetime(2026, 6, 1, 10, 30, tzinfo=UTC)
    resumed_at = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
    completed_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    queued = LongTaskStateSnapshot()
    running = transition_long_task_state(
        queued,
        LongTaskState.RUNNING,
        kind="long_task.started",
        detail="Worker claimed simulated task.",
        payload={"worker_id": "worker-contract"},
        now=started_at,
    )
    blocked = transition_long_task_state(
        running,
        LongTaskState.BLOCKED,
        kind="long_task.blocked",
        detail="Waiting for validation evidence.",
        now=blocked_at,
    )
    resumed = transition_long_task_state(
        blocked,
        LongTaskState.RUNNING,
        kind="long_task.resumed",
        detail="Validation evidence supplied.",
        now=resumed_at,
    )
    succeeded = transition_long_task_state(
        resumed,
        LongTaskState.SUCCEEDED,
        kind="long_task.succeeded",
        detail="All simulated acceptance checks passed.",
        now=completed_at,
    )

    illegal_transition_blocked = False
    try:
        transition_long_task_state(succeeded, LongTaskState.RUNNING)
    except IllegalLongTaskStateTransition:
        illegal_transition_blocked = True

    passed = all(
        [
            queued.state == LongTaskState.QUEUED,
            running.state == LongTaskState.RUNNING,
            blocked.state == LongTaskState.BLOCKED,
            resumed.state == LongTaskState.RUNNING,
            succeeded.state == LongTaskState.SUCCEEDED,
            is_terminal_long_task_state(succeeded.state) is True,
            succeeded.completed_at == completed_at,
            len(succeeded.events) == 4,
            illegal_transition_blocked,
            queued.events == (),
        ]
    )
    return IntegrationCheck(
        name="long_task_state_machine_contract",
        status="passed" if passed else "failed",
        details={
            "initial_state": queued.state.value,
            "final_state": succeeded.state.value,
            "event_count": len(succeeded.events),
            "completed_at": succeeded.completed_at.isoformat() if succeeded.completed_at else None,
            "terminal_state": is_terminal_long_task_state(succeeded.state),
            "illegal_terminal_transition_blocked": illegal_transition_blocked,
        },
        error=None if passed else "long-task state machine transition contract did not match expected behavior",
    )


def _merge_gate_check() -> IntegrationCheck:
    validation_gate = build_validation_evidence_gate(
        status="completed",
        validation_passed=True,
        changed_files=[
            "backend/app/core/long_task_models.py",
            "backend/app/core/long_task_models.py",
            "tests/test_long_task_models.py",
        ],
        validation_commands=[
            "python -m pytest tests/test_long_task_models.py tests/test_long_task_state_machine.py tests/test_long_task_merge_gates.py -q"
        ],
        validation_evidence=[
            {
                "command": "python -m pytest tests/test_long_task_models.py tests/test_long_task_state_machine.py tests/test_long_task_merge_gates.py -q",
                "status": "passed",
                "exit_code": 0,
                "output_excerpt": "long-task focused tests passed",
            }
        ],
        audit={"fingerprint": "audit-long-task-contract"},
        merge_plan={"fingerprint": "plan-long-task-contract", "merge_step_count": 2, "status": "ready"},
        source_matrix={"fingerprint": "matrix-long-task-contract"},
    )
    completion_gate = build_completion_report_merge_gate(validation_gate)
    parent_gate = decide_parent_acceptance_gate(
        matrix={
            "merge_ready": True,
            "merge_authorized": True,
            "fingerprint": "matrix-long-task-contract",
        },
        audit={"status": "completed"},
        parent_package={
            "requires_parent_acceptance": True,
            "parent_acceptance": {"decision": "accepted", "id": "acceptance-long-task-contract"},
        },
        merge_authorization={"id": "auth-long-task-contract", "status": "authorized"},
        final_validation_gate=validation_gate,
    )
    authorization = build_merge_authorization(
        parent_decision="accepted",
        phase_id="phase-validation",
        phase_title="Validation",
        parent_acceptance_id="acceptance-long-task-contract",
        matrix={"fingerprint": "matrix-long-task-contract"},
        audit={"status": "completed"},
        parent_gate=parent_gate,
        merge_plan={"fingerprint": "plan-long-task-contract", "merge_step_count": 2, "status": "ready"},
        authorized_at="2026-06-01T12:00:00+00:00",
        authorization_id="auth-long-task-contract",
    )
    missing_gate = build_validation_evidence_gate(
        status="completed",
        validation_passed=None,
        validation_commands=["python -m pytest tests/test_long_task_models.py -q"],
        validation_evidence=[],
    )
    blocked_parent_gate = decide_parent_acceptance_gate(
        matrix={"status": "waiting_parent_acceptance"},
        audit={"status": "completed"},
        parent_package={"requires_parent_acceptance": True, "parent_acceptance": {"decision": "accepted"}},
        final_validation_gate=missing_gate,
    )

    passed = all(
        [
            validation_gate.get("status") == "passed",
            validation_gate.get("changed_files") == [
                "backend/app/core/long_task_models.py",
                "tests/test_long_task_models.py",
            ],
            completion_gate.get("completion_allowed") is True,
            completion_gate.get("merge_allowed") is True,
            parent_gate.get("status") == "ready_to_merge",
            parent_gate.get("next_action") == "execute_parallel_subagent_merge_sequence",
            authorization.get("status") == "authorized",
            authorization.get("next_action") == "execute_parallel_subagent_merge_sequence",
            missing_gate.get("status") == "missing_evidence",
            blocked_parent_gate.get("status") == "validation_evidence_blocked",
        ]
    )
    return IntegrationCheck(
        name="long_task_merge_gates_contract",
        status="passed" if passed else "failed",
        details={
            "validation_gate_status": validation_gate.get("status"),
            "completion_allowed": completion_gate.get("completion_allowed"),
            "merge_allowed": completion_gate.get("merge_allowed"),
            "parent_gate_status": parent_gate.get("status"),
            "authorization_status": authorization.get("status"),
            "missing_gate_status": missing_gate.get("status"),
            "blocked_parent_gate_status": blocked_parent_gate.get("status"),
            "changed_file_count": validation_gate.get("changed_file_count"),
        },
        error=None if passed else "long-task merge gate decisions did not match expected delivery guardrails",
    )


def build_report() -> dict[str, Any]:
    checks = [_models_check(), _state_machine_check(), _merge_gate_check()]
    all_passed = all(check.status == "passed" for check in checks)

    return {
        "status": "original_kernel_long_task_integration_ready" if all_passed else "failed",
        "generated_at": _utc_now(),
        "evidence_type": "original_kernel_long_task_integration",
        "modules": [
            "long_task_models",
            "long_task_state_machine",
            "long_task_merge_gates",
        ],
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
        "long_task_worker_enabled": False,
        "subagent_execution_enabled": False,
        "workflow_execution_enabled": False,
        "merge_execution_enabled": False,
        "command_execution_enabled": False,
        "real_validation_execution_performed": False,
        "simulated_records_only": True,
        "checks": [asdict(check) for check in checks],
        "known_limits": [
            "This report proves long-task model, state-machine, and merge-gate contracts only.",
            "Validation evidence, parent acceptance, and merge authorization are simulated records.",
            "No real long-task worker, subagent run, workflow, merge execution, or command execution is started.",
            "No API router, agent loop, control plane, frontend, or backend core package entrypoint is wired by this report.",
            "No full Codex parity claim is made by this report.",
        ],
        "next_actions": [
            "After review, stage only the long-task integration files explicitly.",
            "Use shell_job_runner as the next module-level integration slice, still dry-run/contract-first.",
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

    print(f"Original kernel long-task integration status: {report['status']}")
    print(f"Report written to {args.output}")
    for check in report["checks"]:
        print(f"- {check['name']}: {check['status']}")
        if check.get("error"):
            print(f"  error: {check['error']}")

    return 0 if report["status"] == "original_kernel_long_task_integration_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
