#!/usr/bin/env python3
"""Validate installation and release-artifact gates for the commercial RC.

This gate is intentionally non-mutating. It runs installer dry-runs, collects
doctor output, and verifies source-bundle/staging-plan reports so the final RC
gate is based on machine-readable release evidence instead of checklist text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_SOURCE_BUNDLE = REPORT_DIR / "rc-source-bundle.json"
DEFAULT_STAGING_PLAN = REPORT_DIR / "rc-staging-plan.json"
DEFAULT_ARTIFACT_INTEGRITY = REPORT_DIR / "rc-artifact-integrity-gate.json"
DEFAULT_OUTPUT = REPORT_DIR / "rc-install-release-gate.json"
SECRET_KEY_OUTPUT_RE = re.compile(r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+")
SECRET_VALUE_OUTPUT_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")


@dataclass(frozen=True)
class InstallReleaseCheck:
    name: str
    status: str
    command: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class InstallReleaseGateReport:
    status: str
    generated_at: str
    checks: list[InstallReleaseCheck]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_command(command: list[str], *, timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    root_value = str(ROOT)
    env["PYTHONPATH"] = root_value if not python_path else f"{root_value}{os.pathsep}{python_path}"
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout_seconds,
        check=False,
    )


def _tail(text: str, max_chars: int = 2000) -> str:
    sanitized = _sanitize_output_text(text)
    return sanitized[-max_chars:]


def _sanitize_output_text(text: str) -> str:
    text = SECRET_KEY_OUTPUT_RE.sub(r"\1<redacted-output>", text)
    return SECRET_VALUE_OUTPUT_RE.sub("<redacted-secret>", text)


def _json_load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "report missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "report is not a JSON object"
    return payload, None


def _powershell_executable() -> str:
    found = shutil.which("powershell") or shutil.which("pwsh")
    if found:
        return found
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    fallback = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if fallback.exists():
        return str(fallback)
    return "powershell"


def _is_windows_wsl_relay(path: str | None) -> bool:
    if not path:
        return False
    normalized = path.replace("/", "\\").lower()
    return normalized.endswith("\\windows\\system32\\bash.exe") or normalized.endswith("\\windowsapps\\bash.exe")


def _posix_shell_executable() -> str:
    candidates = [
        shutil.which("bash"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\sh.exe",
        shutil.which("sh"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists() and not _is_windows_wsl_relay(candidate):
            return candidate
    return "sh"


def check_windows_installer_dry_run(*, timeout_seconds: float = 60.0) -> InstallReleaseCheck:
    command = [
        _powershell_executable(),
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "scripts\\install-xagent.ps1",
        "-DryRun",
    ]
    try:
        result = _run_command(command, timeout_seconds=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return InstallReleaseCheck("windows_installer_dry_run", "failed", command=command, error=str(exc))
    ok = (
        result.returncode == 0
        and "Dry-run only" in result.stdout
        and "xagent_doctor.py --json" in result.stdout
        and "npm ci" in result.stdout
        and "npm install" not in result.stdout
    )
    return InstallReleaseCheck(
        name="windows_installer_dry_run",
        status="passed" if ok else "failed",
        command=command,
        details={
            "exit_code": result.returncode,
            "stdout_tail": _tail(result.stdout),
            "stderr_tail": _tail(result.stderr),
        },
        error=None
        if ok
        else "Windows installer dry-run did not produce the expected non-mutating lockfile install plan.",
    )


def check_posix_installer_dry_run(*, timeout_seconds: float = 60.0) -> InstallReleaseCheck:
    command = [_posix_shell_executable(), "scripts/install-xagent.sh", "--dry-run"]
    try:
        result = _run_command(command, timeout_seconds=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return InstallReleaseCheck("posix_installer_dry_run", "failed", command=command, error=str(exc))
    ok = (
        result.returncode == 0
        and "Dry-run only" in result.stdout
        and "xagent_doctor.py --json" in result.stdout
        and "npm ci" in result.stdout
        and "npm install" not in result.stdout
    )
    return InstallReleaseCheck(
        name="posix_installer_dry_run",
        status="passed" if ok else "failed",
        command=command,
        details={
            "exit_code": result.returncode,
            "stdout_tail": _tail(result.stdout),
            "stderr_tail": _tail(result.stderr),
        },
        error=None
        if ok
        else "POSIX installer dry-run did not produce the expected non-mutating lockfile install plan.",
    )


def check_doctor(*, timeout_seconds: float = 90.0) -> InstallReleaseCheck:
    command = [sys.executable, "scripts/xagent_doctor.py", "--json"]
    display_command = ["python", "scripts/xagent_doctor.py", "--json"]
    try:
        result = _run_command(command, timeout_seconds=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return InstallReleaseCheck("doctor", "failed", command=display_command, error=str(exc))
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return InstallReleaseCheck(
            "doctor",
            "failed",
            command=display_command,
            details={"exit_code": result.returncode, "stdout_tail": _tail(result.stdout), "stderr_tail": _tail(result.stderr)},
            error=f"doctor did not emit valid JSON: {exc}",
        )
    status = str(payload.get("status") or "")
    ok = result.returncode == 0 and status in {"pass", "warn"}
    return InstallReleaseCheck(
        name="doctor",
        status="passed" if ok else "failed",
        command=display_command,
        details={
            "doctor_status": status,
            "failed_checks": [check for check in payload.get("checks", []) if isinstance(check, dict) and check.get("status") == "fail"],
            "warn_checks": [check.get("name") for check in payload.get("checks", []) if isinstance(check, dict) and check.get("status") == "warn"],
        },
        error=None if ok else "doctor returned fail or nonzero exit",
    )


def check_report_status(path: Path, *, name: str, expected: set[str]) -> InstallReleaseCheck:
    payload, error = _json_load(path)
    status = str((payload or {}).get("status") or "missing")
    return InstallReleaseCheck(
        name=name,
        status="passed" if error is None and status in expected else "failed",
        details={
            "path": str(path),
            "report_status": status,
            "file_count": (payload or {}).get("file_count"),
            "errors": (payload or {}).get("errors", []),
        },
        error=error if error else None if status in expected else f"expected status in {sorted(expected)}, got {status}",
    )


def _bundle_paths(payload: dict[str, Any] | None) -> set[str]:
    paths: set[str] = set()
    for item in (payload or {}).get("files", []):
        if isinstance(item, dict) and item.get("path"):
            paths.add(str(item["path"]).replace("\\", "/"))
    return paths


def check_release_artifact_consistency(
    source_bundle_report: Path,
    staging_plan_report: Path,
    artifact_integrity_report: Path,
) -> InstallReleaseCheck:
    source_payload, source_error = _json_load(source_bundle_report)
    staging_payload, staging_error = _json_load(staging_plan_report)
    artifact_payload, artifact_error = _json_load(artifact_integrity_report)
    problems: list[str] = []
    required_bundle_files = {
        "scripts/install-xagent.ps1",
        "scripts/install-xagent.sh",
        "scripts/xagent_doctor.py",
    }

    if source_error:
        problems.append(f"source_bundle_report: {source_error}")
    if staging_error:
        problems.append(f"staging_plan_report: {staging_error}")
    if artifact_error:
        problems.append(f"artifact_integrity_report: {artifact_error}")

    source_count = (source_payload or {}).get("file_count")
    staging_count = (staging_payload or {}).get("file_count")
    artifact_count = (artifact_payload or {}).get("file_count")
    if None in {source_count, staging_count, artifact_count}:
        problems.append("source/staging/artifact file_count fields must all be present")
    elif len({source_count, staging_count, artifact_count}) != 1:
        problems.append(
            "source/staging/artifact file_count mismatch: "
            f"source={source_count}, staging={staging_count}, artifact={artifact_count}"
        )

    source_output_path = str((source_payload or {}).get("output_path") or "")
    artifact_path = str((artifact_payload or {}).get("artifact_path") or "")
    if not source_output_path:
        problems.append("source_bundle.output_path is missing")
    if not artifact_path:
        problems.append("artifact_integrity_gate.artifact_path is missing")
    if source_output_path and artifact_path and Path(source_output_path) != Path(artifact_path):
        problems.append("source_bundle.output_path does not match artifact_integrity_gate.artifact_path")

    bundle_paths = _bundle_paths(source_payload)
    missing_required = sorted(required_bundle_files.difference(bundle_paths))
    if missing_required:
        problems.append(f"source bundle is missing installer/doctor files: {missing_required}")

    return InstallReleaseCheck(
        name="release_artifact_consistency",
        status="passed" if not problems else "failed",
        details={
            "source_bundle_report": str(source_bundle_report),
            "staging_plan_report": str(staging_plan_report),
            "artifact_integrity_report": str(artifact_integrity_report),
            "file_counts": {
                "source_bundle": source_count,
                "staging_plan": staging_count,
                "artifact_integrity_gate": artifact_count,
            },
            "source_output_path": source_output_path,
            "artifact_path": artifact_path,
            "required_bundle_files": sorted(required_bundle_files),
            "missing_required_bundle_files": missing_required,
        },
        error="; ".join(problems) if problems else None,
    )


def run_install_release_gate(
    *,
    source_bundle_report: Path = DEFAULT_SOURCE_BUNDLE,
    staging_plan_report: Path = DEFAULT_STAGING_PLAN,
    artifact_integrity_report: Path = DEFAULT_ARTIFACT_INTEGRITY,
    timeout_seconds: float = 90.0,
) -> InstallReleaseGateReport:
    checks = [
        check_windows_installer_dry_run(timeout_seconds=timeout_seconds),
        check_posix_installer_dry_run(timeout_seconds=timeout_seconds),
        check_doctor(timeout_seconds=timeout_seconds),
        check_report_status(source_bundle_report, name="source_bundle_report", expected={"created"}),
        check_report_status(artifact_integrity_report, name="artifact_integrity_report", expected={"passed"}),
        check_report_status(staging_plan_report, name="staging_plan_report", expected={"planned"}),
        check_release_artifact_consistency(source_bundle_report, staging_plan_report, artifact_integrity_report),
    ]
    failed = [check for check in checks if check.status != "passed"]
    return InstallReleaseGateReport(
        status="failed" if failed else "passed",
        generated_at=_utc_now(),
        checks=checks,
        next_commands=[
            "Review .xagent_runtime/reports/rc-install-release-gate.json.",
            "Archive the generated .xagent_runtime/release/*.zip artifact and SHA-256 outside source control.",
            "Run scripts/rc_final_gate.py after regenerating all RC reports.",
        ],
    )


def write_report(report: InstallReleaseGateReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate X-Agent commercial RC install and release artifact gates")
    parser.add_argument("--source-bundle-report", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--staging-plan-report", type=Path, default=DEFAULT_STAGING_PLAN)
    parser.add_argument("--artifact-integrity-report", type=Path, default=DEFAULT_ARTIFACT_INTEGRITY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=90.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_install_release_gate(
        source_bundle_report=args.source_bundle_report,
        staging_plan_report=args.staging_plan_report,
        artifact_integrity_report=args.artifact_integrity_report,
        timeout_seconds=args.timeout,
    )
    write_report(report, args.output)
    print(f"RC install/release gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
