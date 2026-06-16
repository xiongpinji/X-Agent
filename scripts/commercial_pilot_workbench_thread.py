#!/usr/bin/env python3
"""Generate Workbench thread-loop evidence for the commercial pilot gate."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from scripts.commercial_pilot_core_entrypoints import (
    CommandResult,
    EvidenceCheck,
    REPORT_DIR,
    _utc_now,
    run_pytest_targets,
)

DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-workbench-thread.json"
DEFAULT_TARGETS = (
    "tests/test_chat_entrypoint_contract.py",
    "tests/test_workbench_thread_loop.py",
)


@dataclass(frozen=True)
class WorkbenchThreadEvidence:
    status: str
    generated_at: str
    evidence_type: str
    full_codex_parity_claimed: bool
    targets: list[str]
    checks: list[EvidenceCheck]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def run_workbench_thread_tests(
    *,
    targets: Sequence[str] = DEFAULT_TARGETS,
    timeout_seconds: float = 180.0,
) -> CommandResult:
    return run_pytest_targets(targets=targets, timeout_seconds=timeout_seconds)


def build_workbench_thread_evidence(
    *,
    command_result: CommandResult,
    targets: Sequence[str] = DEFAULT_TARGETS,
) -> WorkbenchThreadEvidence:
    passed = command_result.returncode == 0 and not command_result.timed_out
    check = EvidenceCheck(
        name="pytest_workbench_thread_loop",
        status="passed" if passed else "failed",
        details={
            "targets": list(targets),
            "command": command_result.command,
            "returncode": command_result.returncode,
            "duration_seconds": command_result.duration_seconds,
            "timeout_seconds": command_result.timeout_seconds,
            "timed_out": command_result.timed_out,
            "stdout_tail": command_result.stdout_tail,
            "stderr_tail": command_result.stderr_tail,
        },
        error=None if passed else "workbench thread-loop pytest command failed",
    )
    return WorkbenchThreadEvidence(
        status="passed" if passed else "failed",
        generated_at=_utc_now(),
        evidence_type="commercial_pilot_workbench_thread_loop",
        full_codex_parity_claimed=False,
        targets=list(targets),
        checks=[check],
        next_commands=[
            "python scripts\\commercial_pilot_readiness.py "
            "--workbench-thread-report .xagent_runtime\\reports\\commercial-pilot-workbench-thread.json"
        ],
        known_limits=[
            "This report proves local Workbench and workflow-chat contract tests only.",
            "It does not prove a native Codex-style desktop thread UI.",
            "Live multi-user collaboration and long-running cloud task continuity remain separate evidence gates.",
            "Full Codex parity is not claimed by this report.",
        ],
    )


def write_report(report: WorkbenchThreadEvidence, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--target", action="append", dest="targets", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = tuple(args.targets or DEFAULT_TARGETS)
    command_result = run_workbench_thread_tests(targets=targets, timeout_seconds=args.timeout_seconds)
    report = build_workbench_thread_evidence(command_result=command_result, targets=targets)
    write_report(report, args.output)

    print(f"Commercial pilot workbench-thread evidence status: {report.status}")
    print(f"Report written to {args.output}")
    print(f"Command return code: {command_result.returncode}")
    print(f"Duration seconds: {command_result.duration_seconds}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
