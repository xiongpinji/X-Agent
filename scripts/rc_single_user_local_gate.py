#!/usr/bin/env python3
"""Run the single-machine, single-user commercial RC validation gate.

This gate is intentionally local and non-mutating. It validates the install
path, production frontend build, mock-provider runtime smoke, and focused
functional tests that represent the first-user product loop.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
SMOKE_DIR = ROOT / ".xagent_runtime" / "smoke"
DEFAULT_OUTPUT = REPORT_DIR / "rc-single-user-local-gate.json"
DEFAULT_INSTALL_REPORT = REPORT_DIR / "rc-install-release-gate.json"
DEFAULT_RUNTIME_REPORT = SMOKE_DIR / "rc-runtime-smoke.json"
DEFAULT_RC2_HANDOFF_REPORT = REPORT_DIR / "rc2-release-handoff.json"

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
SECRET_KEY_OUTPUT_RE = re.compile(
    r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+"
)
SECRET_VALUE_OUTPUT_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")


@dataclass(frozen=True)
class CommandRun:
    """Captured command result with sanitized report output handled elsewhere."""

    command: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


@dataclass(frozen=True)
class SingleUserCheck:
    """Single gate check result."""

    name: str
    status: str
    command: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    report_path: str | None = None
    duration_seconds: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class SingleUserLocalGateReport:
    """Machine-readable local single-user validation report."""

    status: str
    generated_at: str
    scope: str
    mode: str
    checks: list[SingleUserCheck]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _python_command(script: str, *args: str) -> list[str]:
    return [sys.executable, script, *args]


def _display_command(command: list[str]) -> list[str]:
    if command and Path(command[0]) == Path(sys.executable):
        return ["python", *command[1:]]
    return command


def _npm_executable() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _targeted_tests_cwd() -> Path:
    if os.name != "nt":
        return ROOT

    candidates = [os.environ.get("XAGENT_SHORT_REPO_ROOT"), "X:\\"]
    for value in candidates:
        if not value:
            continue
        candidate = Path(value)
        try:
            if candidate.exists() and candidate.samefile(ROOT):
                return candidate
        except OSError:
            continue
    return ROOT


def _sanitize_output_text(text: str) -> str:
    text = SECRET_KEY_OUTPUT_RE.sub(r"\1<redacted-output>", text)
    return SECRET_VALUE_OUTPUT_RE.sub("<redacted-secret>", text)


def _tail(text: str, *, lines: int = 30, max_chars: int = 3000) -> str:
    sanitized = _sanitize_output_text(text)
    return "\n".join(sanitized.splitlines()[-lines:])[-max_chars:]


def _clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in PROXY_KEYS:
        env.pop(key, None)
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else f"{ROOT}{os.pathsep}{python_path}"
    env.update(
        {
            "PYTHONUTF8": "1",
            "XAGENT_QDRANT_URL": "",
            "XAGENT_LLM_BACKEND": "mock",
            "XAGENT_E2E": "0",
            "XAGENT_REQUIRE_API_KEY": "false",
        }
    )
    if extra:
        env.update(extra)
    return env


def _run_command(
    command: list[str],
    *,
    cwd: Path = ROOT,
    timeout_seconds: float,
    env_overrides: dict[str, str] | None = None,
) -> CommandRun:
    start = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=_clean_env(env_overrides),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        return CommandRun(
            command=command,
            cwd=str(cwd),
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=round(time.perf_counter() - start, 3),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandRun(
            command=command,
            cwd=str(cwd),
            returncode=1,
            stdout="",
            stderr=str(exc),
            duration_seconds=round(time.perf_counter() - start, 3),
        )


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "report missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "report is not a JSON object"
    return payload, None


def check_existing_report(
    path: Path,
    *,
    name: str,
    expected: set[str],
    required: bool,
) -> SingleUserCheck:
    payload, error = _read_json(path)
    if error and not required:
        return SingleUserCheck(
            name=name,
            status="skipped",
            report_path=str(path),
            details={"reason": error},
        )
    status = str((payload or {}).get("status") or "missing")
    ok = error is None and status in expected
    return SingleUserCheck(
        name=name,
        status="passed" if ok else "failed",
        report_path=str(path),
        details={
            "report_status": status,
            "tag": (payload or {}).get("tag"),
            "commit": (payload or {}).get("commit"),
            "release_url": (payload or {}).get("release_url"),
        },
        error=error if error else None if ok else f"expected status in {sorted(expected)}, got {status}",
    )


def _report_status_check(
    *,
    name: str,
    run: CommandRun,
    report_path: Path | None,
    expected_report_status: set[str] | None,
) -> SingleUserCheck:
    details: dict[str, Any] = {
        "exit_code": run.returncode,
        "cwd": run.cwd,
        "stdout_tail": _tail(run.stdout),
        "stderr_tail": _tail(run.stderr),
    }
    if run.returncode != 0:
        return SingleUserCheck(
            name=name,
            status="failed",
            command=_display_command(run.command),
            details=details,
            report_path=str(report_path) if report_path else None,
            duration_seconds=run.duration_seconds,
            error="command exited nonzero",
        )

    if report_path is not None and expected_report_status is not None:
        payload, error = _read_json(report_path)
        report_status = str((payload or {}).get("status") or "missing")
        details["report_status"] = report_status
        if error or report_status not in expected_report_status:
            return SingleUserCheck(
                name=name,
                status="failed",
                command=_display_command(run.command),
                details=details,
                report_path=str(report_path),
                duration_seconds=run.duration_seconds,
                error=error
                if error
                else f"expected report status in {sorted(expected_report_status)}, got {report_status}",
            )

    return SingleUserCheck(
        name=name,
        status="passed",
        command=_display_command(run.command),
        details=details,
        report_path=str(report_path) if report_path else None,
        duration_seconds=run.duration_seconds,
    )


def run_install_release_gate(*, report_path: Path, timeout_seconds: float) -> SingleUserCheck:
    command = _python_command(
        "scripts/rc_install_release_gate.py",
        "--output",
        str(report_path),
        "--timeout",
        str(timeout_seconds),
    )
    run = _run_command(command, timeout_seconds=timeout_seconds + 20)
    return _report_status_check(
        name="install_release_gate",
        run=run,
        report_path=report_path,
        expected_report_status={"passed"},
    )


def run_frontend_build(*, timeout_seconds: float) -> SingleUserCheck:
    command = [_npm_executable(), "run", "build"]
    run = _run_command(command, cwd=ROOT / "frontend", timeout_seconds=timeout_seconds)
    return _report_status_check(
        name="frontend_production_build",
        run=run,
        report_path=None,
        expected_report_status=None,
    )


def run_runtime_smoke(
    *,
    report_path: Path,
    timeout_seconds: float,
    backend_only: bool,
) -> SingleUserCheck:
    command = _python_command(
        "scripts/rc_runtime_smoke.py",
        "--backend-port",
        "0",
        "--frontend-port",
        "0",
        "--startup-timeout",
        "60",
        "--request-timeout",
        "10",
        "--output",
        str(report_path),
    )
    if backend_only:
        command.append("--backend-only")
    run = _run_command(command, timeout_seconds=timeout_seconds)
    return _report_status_check(
        name="runtime_smoke",
        run=run,
        report_path=report_path,
        expected_report_status={"passed"},
    )


def run_targeted_tests(*, timeout_seconds: float) -> SingleUserCheck:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_first_release_entrypoints.py",
        "tests/test_rc_runtime_smoke.py",
        "tests/test_rc_install_release_gate.py",
        "tests/test_rc_single_user_local_gate.py",
        "-o",
        "addopts=",
        "-p",
        "no:cov",
        "-p",
        "no:cacheprovider",
        "--no-header",
        "-q",
    ]
    run = _run_command(command, cwd=_targeted_tests_cwd(), timeout_seconds=timeout_seconds)
    return _report_status_check(
        name="targeted_single_user_tests",
        run=run,
        report_path=None,
        expected_report_status=None,
    )


def run_single_user_local_gate(
    *,
    output_path: Path = DEFAULT_OUTPUT,
    install_report_path: Path = DEFAULT_INSTALL_REPORT,
    runtime_report_path: Path = DEFAULT_RUNTIME_REPORT,
    rc2_handoff_report_path: Path = DEFAULT_RC2_HANDOFF_REPORT,
    require_rc2_handoff: bool = False,
    skip_install_release: bool = False,
    skip_frontend_build: bool = False,
    skip_runtime_smoke: bool = False,
    skip_tests: bool = False,
    backend_only: bool = False,
    timeout_seconds: float = 180.0,
    stop_on_failure: bool = False,
) -> SingleUserLocalGateReport:
    checks: list[SingleUserCheck] = [
        check_existing_report(
            rc2_handoff_report_path,
            name="rc2_release_handoff_snapshot",
            expected={"created_and_validated"},
            required=require_rc2_handoff,
        )
    ]

    planned_steps: list[tuple[bool, str, Any]] = [
        (skip_install_release, "install_release_gate", lambda: run_install_release_gate(report_path=install_report_path, timeout_seconds=timeout_seconds)),
        (skip_frontend_build, "frontend_production_build", lambda: run_frontend_build(timeout_seconds=timeout_seconds)),
        (skip_runtime_smoke, "runtime_smoke", lambda: run_runtime_smoke(report_path=runtime_report_path, timeout_seconds=timeout_seconds, backend_only=backend_only)),
        (skip_tests, "targeted_single_user_tests", lambda: run_targeted_tests(timeout_seconds=timeout_seconds)),
    ]
    for skipped, name, runner in planned_steps:
        if skipped:
            checks.append(SingleUserCheck(name=name, status="skipped", details={"reason": "disabled by CLI flag"}))
            continue
        check = runner()
        checks.append(check)
        if stop_on_failure and check.status == "failed":
            break

    failed = [check for check in checks if check.status == "failed"]
    return SingleUserLocalGateReport(
        status="failed" if failed else "passed",
        generated_at=_utc_now(),
        scope="single-machine single-user local validation",
        mode="mock provider; no external Feishu/GitHub mutations",
        checks=checks,
        next_commands=_next_commands(output_path, failed),
    )


def _next_commands(output_path: Path, failed: list[SingleUserCheck]) -> list[str]:
    if failed:
        first = failed[0]
        if first.command:
            return [
                f"Inspect {output_path}.",
                "Rerun the first failing command after fixing the local environment or product issue:",
                " ".join(first.command),
            ]
        return [f"Inspect {output_path} and refresh the missing or stale report."]
    return [
        f"Use {output_path} as single-user local acceptance evidence.",
        "For owner-controlled commercial RC finalization, rerun scripts/rc_final_gate.py with the required owner env vars.",
    ]


def write_report(report: SingleUserLocalGateReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run X-Agent single-machine single-user local validation")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--install-report", type=Path, default=DEFAULT_INSTALL_REPORT)
    parser.add_argument("--runtime-report", type=Path, default=DEFAULT_RUNTIME_REPORT)
    parser.add_argument("--rc2-handoff-report", type=Path, default=DEFAULT_RC2_HANDOFF_REPORT)
    parser.add_argument("--require-rc2-handoff", action="store_true")
    parser.add_argument("--skip-install-release", action="store_true")
    parser.add_argument("--skip-frontend-build", action="store_true")
    parser.add_argument("--skip-runtime-smoke", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--backend-only", action="store_true", help="run backend smoke without Vite frontend")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--stop-on-failure", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_single_user_local_gate(
        output_path=args.output,
        install_report_path=args.install_report,
        runtime_report_path=args.runtime_report,
        rc2_handoff_report_path=args.rc2_handoff_report,
        require_rc2_handoff=args.require_rc2_handoff,
        skip_install_release=args.skip_install_release,
        skip_frontend_build=args.skip_frontend_build,
        skip_runtime_smoke=args.skip_runtime_smoke,
        skip_tests=args.skip_tests,
        backend_only=args.backend_only,
        timeout_seconds=args.timeout,
        stop_on_failure=args.stop_on_failure,
    )
    write_report(report, args.output)
    print(f"RC single-user local gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
