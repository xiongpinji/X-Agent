#!/usr/bin/env python3
"""Generate core-entrypoint evidence for the commercial pilot gate.

This script runs the targeted first-release entrypoint and security tests, then
writes a machine-readable evidence report consumed by
``scripts/commercial_pilot_readiness.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-core-entrypoints.json"
DEFAULT_TARGETS = ("tests/test_first_release_entrypoints.py", "tests/test_security.py")
DEFAULT_PYTEST_ARGS = ("-o", "addopts=", "-p", "no:cov", "-p", "no:cacheprovider", "-q")
PROXY_KEYS = (
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ftp_proxy",
    "grpc_proxy",
)


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str
    timeout_seconds: float
    timed_out: bool = False


@dataclass(frozen=True)
class EvidenceCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class CoreEntrypointsEvidence:
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


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tail_text(value: str | bytes | None, limit: int = 4000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    return text[-limit:]


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in PROXY_KEYS:
        env.pop(key, None)
    env.update(
        {
            "PYTHONUTF8": "1",
            "XAGENT_QDRANT_URL": "",
            "XAGENT_E2E": "0",
        }
    )
    return env


def run_pytest_targets(
    *,
    targets: Sequence[str],
    timeout_seconds: float = 180.0,
) -> CommandResult:
    command = [sys.executable, "-m", "pytest", *targets, *DEFAULT_PYTEST_ARGS]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=_clean_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            returncode=124,
            duration_seconds=round(time.perf_counter() - started, 3),
            stdout_tail=_tail_text(exc.stdout),
            stderr_tail=_tail_text(exc.stderr),
            timeout_seconds=timeout_seconds,
            timed_out=True,
        )
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        duration_seconds=round(time.perf_counter() - started, 3),
        stdout_tail=_tail_text(completed.stdout),
        stderr_tail=_tail_text(completed.stderr),
        timeout_seconds=timeout_seconds,
        timed_out=False,
    )


def run_core_entrypoint_tests(
    *,
    targets: Sequence[str] = DEFAULT_TARGETS,
    timeout_seconds: float = 180.0,
) -> CommandResult:
    return run_pytest_targets(targets=targets, timeout_seconds=timeout_seconds)


def build_core_entrypoints_evidence(
    *,
    command_result: CommandResult,
    targets: Sequence[str] = DEFAULT_TARGETS,
) -> CoreEntrypointsEvidence:
    passed = command_result.returncode == 0 and not command_result.timed_out
    check = EvidenceCheck(
        name="pytest_core_entrypoints",
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
        error=None if passed else "core entrypoint pytest command failed",
    )
    return CoreEntrypointsEvidence(
        status="passed" if passed else "failed",
        generated_at=_utc_now(),
        evidence_type="commercial_pilot_core_entrypoints",
        full_codex_parity_claimed=False,
        targets=list(targets),
        checks=[check],
        next_commands=[
            "python scripts\\commercial_pilot_readiness.py "
            "--core-entrypoints-report .xagent_runtime\\reports\\commercial-pilot-core-entrypoints.json"
        ],
        known_limits=[
            "This report proves targeted core-entrypoint tests only.",
            "Commercial pilot readiness still requires channel, skill governance, workbench, and approval/audit evidence.",
            "Full Codex parity is not claimed by this report.",
        ],
    )


def write_report(report: CoreEntrypointsEvidence, output_path: Path = DEFAULT_OUTPUT) -> None:
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
    command_result = run_core_entrypoint_tests(targets=targets, timeout_seconds=args.timeout_seconds)
    report = build_core_entrypoints_evidence(command_result=command_result, targets=targets)
    write_report(report, args.output)

    print(f"Commercial pilot core-entrypoints evidence status: {report.status}")
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
