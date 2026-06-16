#!/usr/bin/env python3
"""Refresh all commercial pilot evidence and the aggregate readiness gate."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from scripts.commercial_pilot_approval_audit import (
    DEFAULT_OUTPUT as APPROVAL_AUDIT_OUTPUT,
    build_approval_audit_evidence,
    run_approval_audit_tests,
    write_report as write_approval_audit_report,
)
from scripts.commercial_pilot_channel_loop import (
    DEFAULT_OUTPUT as CHANNEL_LOOP_OUTPUT,
    build_channel_loop_evidence,
    run_channel_loop_tests,
    write_report as write_channel_loop_report,
)
from scripts.commercial_pilot_channel_readiness import (
    DEFAULT_OUTPUT as CHANNEL_READINESS_OUTPUT,
    build_channel_readiness_matrix,
    write_report as write_channel_readiness_report,
)
from scripts.commercial_pilot_core_entrypoints import (
    DEFAULT_OUTPUT as CORE_ENTRYPOINTS_OUTPUT,
    REPORT_DIR,
    _utc_now,
    build_core_entrypoints_evidence,
    run_core_entrypoint_tests,
    write_report as write_core_entrypoints_report,
)
from scripts.commercial_pilot_readiness import (
    DEFAULT_OUTPUT as READINESS_OUTPUT,
    PilotReadinessReport,
    build_pilot_readiness_report,
    write_report as write_readiness_report,
)
from scripts.commercial_pilot_skill_governance import (
    DEFAULT_OUTPUT as SKILL_GOVERNANCE_OUTPUT,
    build_skill_governance_evidence,
    run_skill_governance_tests,
    write_report as write_skill_governance_report,
)
from scripts.commercial_pilot_workbench_thread import (
    DEFAULT_OUTPUT as WORKBENCH_THREAD_OUTPUT,
    build_workbench_thread_evidence,
    run_workbench_thread_tests,
    write_report as write_workbench_thread_report,
)

DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-refresh-chain.json"
READY_STATUSES = {"passed", "pilot_ready", "ready_with_owner_gates"}


@dataclass(frozen=True)
class RefreshStep:
    name: str
    status: str
    report_path: str
    duration_seconds: float
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class RefreshChainReport:
    status: str
    generated_at: str
    pilot_channel: str
    readiness_report_path: str
    full_codex_parity_claimed: bool
    steps: list[RefreshStep]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


EvidenceRunner = Callable[[], tuple[str, Path, dict[str, Any]]]


def _status_from_payload(payload: dict[str, Any]) -> str:
    status = str(payload.get("status", ""))
    return "passed" if status in READY_STATUSES else "failed"


def _error_from_payload(payload: dict[str, Any]) -> str | None:
    status = str(payload.get("status", ""))
    if status in READY_STATUSES:
        return None
    checks = payload.get("checks")
    if isinstance(checks, list):
        errors = [str(check.get("error")) for check in checks if isinstance(check, dict) and check.get("error")]
        if errors:
            return "; ".join(errors)
    return f"report status is {status or '<missing>'}"


def _run_step(name: str, runner: EvidenceRunner) -> RefreshStep:
    started = time.perf_counter()
    try:
        source_status, report_path, payload = runner()
    except Exception as exc:  # noqa: BLE001 - refresh chain records failing step evidence
        return RefreshStep(
            name=name,
            status="failed",
            report_path="",
            duration_seconds=round(time.perf_counter() - started, 3),
            error=str(exc),
        )
    return RefreshStep(
        name=name,
        status=_status_from_payload(payload),
        report_path=str(report_path),
        duration_seconds=round(time.perf_counter() - started, 3),
        details={"source_status": source_status},
        error=_error_from_payload(payload),
    )


def refresh_commercial_pilot_chain(
    *,
    pilot_channel: str = "feishu",
    output_path: Path = DEFAULT_OUTPUT,
    readiness_output_path: Path = READINESS_OUTPUT,
) -> RefreshChainReport:
    steps: list[RefreshStep] = []

    def core_entrypoints() -> tuple[str, Path, dict[str, Any]]:
        result = run_core_entrypoint_tests()
        report = build_core_entrypoints_evidence(command_result=result)
        write_core_entrypoints_report(report, CORE_ENTRYPOINTS_OUTPUT)
        return report.status, CORE_ENTRYPOINTS_OUTPUT, report.to_dict()

    def workbench_thread() -> tuple[str, Path, dict[str, Any]]:
        result = run_workbench_thread_tests()
        report = build_workbench_thread_evidence(command_result=result)
        write_workbench_thread_report(report, WORKBENCH_THREAD_OUTPUT)
        return report.status, WORKBENCH_THREAD_OUTPUT, report.to_dict()

    def pilot_channel_loop() -> tuple[str, Path, dict[str, Any]]:
        result = run_channel_loop_tests()
        report = build_channel_loop_evidence(command_result=result, pilot_channel=pilot_channel)
        write_channel_loop_report(report, CHANNEL_LOOP_OUTPUT)
        return report.status, CHANNEL_LOOP_OUTPUT, report.to_dict()

    def channel_readiness() -> tuple[str, Path, dict[str, Any]]:
        report = build_channel_readiness_matrix(pilot_channel=pilot_channel)
        write_channel_readiness_report(report, CHANNEL_READINESS_OUTPUT)
        return report.status, CHANNEL_READINESS_OUTPUT, report.to_dict()

    def skill_governance() -> tuple[str, Path, dict[str, Any]]:
        result = run_skill_governance_tests()
        report = build_skill_governance_evidence(command_result=result)
        write_skill_governance_report(report, SKILL_GOVERNANCE_OUTPUT)
        return report.status, SKILL_GOVERNANCE_OUTPUT, report.to_dict()

    def approval_audit() -> tuple[str, Path, dict[str, Any]]:
        result = run_approval_audit_tests()
        report = build_approval_audit_evidence(command_result=result)
        write_approval_audit_report(report, APPROVAL_AUDIT_OUTPUT)
        return report.status, APPROVAL_AUDIT_OUTPUT, report.to_dict()

    runners: list[tuple[str, EvidenceRunner]] = [
        ("core_entrypoints", core_entrypoints),
        ("workbench_thread_loop", workbench_thread),
        ("pilot_channel_loop", pilot_channel_loop),
        ("channel_readiness_matrix", channel_readiness),
        ("skill_governance", skill_governance),
        ("approval_audit", approval_audit),
    ]
    for name, runner in runners:
        step = _run_step(name, runner)
        steps.append(step)
        if step.status != "passed":
            break

    readiness_report: PilotReadinessReport | None = None
    if all(step.status == "passed" for step in steps) and len(steps) == len(runners):
        readiness_report = build_pilot_readiness_report(
            output_path=readiness_output_path,
            pilot_channel=pilot_channel,
            core_entrypoints_report_path=CORE_ENTRYPOINTS_OUTPUT,
            workbench_thread_report_path=WORKBENCH_THREAD_OUTPUT,
            pilot_channel_report_path=CHANNEL_LOOP_OUTPUT,
            skill_governance_report_path=SKILL_GOVERNANCE_OUTPUT,
            approval_audit_report_path=APPROVAL_AUDIT_OUTPUT,
        )
        write_readiness_report(readiness_report, readiness_output_path)
        steps.append(
            RefreshStep(
                name="commercial_pilot_readiness",
                status="passed" if readiness_report.status == "pilot_ready" else "failed",
                report_path=str(readiness_output_path),
                duration_seconds=0,
                details={"source_status": readiness_report.status},
                error=None if readiness_report.status == "pilot_ready" else "aggregate readiness is not pilot_ready",
            )
        )

    status = "pilot_ready" if steps and all(step.status == "passed" for step in steps) else "pilot_blocked"
    next_commands = [f"Review {readiness_output_path} and {output_path} before making any commercial pilot claim."]
    if status != "pilot_ready":
        next_commands.insert(0, "Fix the first failed refresh-chain step, then rerun python scripts\\commercial_pilot_refresh_chain.py.")
    return RefreshChainReport(
        status=status,
        generated_at=_utc_now(),
        pilot_channel=pilot_channel,
        readiness_report_path=str(readiness_output_path),
        full_codex_parity_claimed=False,
        steps=steps,
        next_commands=next_commands,
        known_limits=[
            "Commercial pilot readiness is separate from commercial RC readiness.",
            "Full Codex parity is not claimed by this refresh chain.",
            "ready_with_owner_gates means local pilot planning evidence exists but live credentials remain owner-gated.",
            "Live channel credentials and owner-controlled external checks remain separate gates.",
            "Runtime reports under .xagent_runtime are generated evidence and are not staged by default.",
        ],
    )


def write_report(report: RefreshChainReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--readiness-output", type=Path, default=READINESS_OUTPUT)
    parser.add_argument("--pilot-channel", default="feishu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = refresh_commercial_pilot_chain(
        pilot_channel=args.pilot_channel,
        output_path=args.output,
        readiness_output_path=args.readiness_output,
    )
    write_report(report, args.output)

    print(f"Commercial pilot refresh chain status: {report.status}")
    print(f"Pilot channel: {report.pilot_channel}")
    print(f"Readiness report: {report.readiness_report_path}")
    print(f"Refresh chain report written to {args.output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    for step in report.steps:
        print(f"- {step.name}: {step.status}")
        if step.error:
            print(f"  error: {step.error}")
    return 0 if report.status == "pilot_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
