#!/usr/bin/env python3
"""Local environment doctor for X-Agent."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CommandResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class DoctorCheck:
    name: str
    status: str
    details: dict[str, object] = field(default_factory=dict)
    next_commands: list[str] = field(default_factory=list)


Runner = Callable[[list[str], Path], CommandResult]


def run_command(command: list[str], cwd: Path) -> CommandResult:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return CommandResult(result.returncode, result.stdout, result.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(1, "", str(exc))


def check_python_version() -> DoctorCheck:
    version = sys.version_info
    ok = version >= (3, 11)
    return DoctorCheck(
        name="python",
        status="pass" if ok else "fail",
        details={"version": sys.version.split()[0], "executable": sys.executable},
        next_commands=[] if ok else ["Install Python 3.11+ and rerun the doctor."],
    )


def check_node_version(runner: Runner, root: Path) -> DoctorCheck:
    result = runner(["node", "--version"], root)
    ok = result.exit_code == 0
    return DoctorCheck(
        name="node",
        status="pass" if ok else "fail",
        details={"version": result.stdout.strip(), "stderr": result.stderr.strip()},
        next_commands=[] if ok else ["Install Node.js 20+ from https://nodejs.org/"],
    )


def check_backend_import() -> DoctorCheck:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            importlib.import_module("backend.app.main")
        return DoctorCheck(
            name="backend_import",
            status="pass",
            details={
                "stdout": stdout.getvalue().strip(),
                "stderr": stderr.getvalue().strip(),
            },
        )
    except Exception as exc:  # noqa: BLE001 - doctor reports import blockers
        return DoctorCheck(
            name="backend_import",
            status="fail",
            details={"error": str(exc)},
            next_commands=['python -m pip install -e ".[dev,cli]"'],
        )


def check_frontend_dependencies(root: Path) -> DoctorCheck:
    package_json = root / "frontend" / "package.json"
    node_modules = root / "frontend" / "node_modules"
    package_lock = root / "frontend" / "package-lock.json"
    ok = package_json.exists() and node_modules.exists()
    return DoctorCheck(
        name="frontend_dependencies",
        status="pass" if ok else "fail",
        details={
            "package_json": package_json.exists(),
            "node_modules": node_modules.exists(),
            "package_lock": package_lock.exists(),
        },
        next_commands=[] if ok else ["cd frontend", "npm install"],
    )


def check_env_vars() -> DoctorCheck:
    optional = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GITHUB_TOKEN",
        "XAGENT_FEISHU_APP_ID",
        "XAGENT_FEISHU_APP_SECRET",
        "XAGENT_FEISHU_ENCRYPT_KEY",
    ]
    present = [key for key in optional if os.getenv(key)]
    missing = [key for key in optional if key not in present]
    return DoctorCheck(
        name="optional_env",
        status="pass" if present else "warn",
        details={"present": present, "missing": missing},
        next_commands=["Set provider/channel tokens only when enabling those integrations."],
    )


def check_representative_tests(root: Path) -> DoctorCheck:
    required = [
        root / "tests" / "test_first_release_entrypoints.py",
        root / "tests" / "test_codex_hermes_gap_matrix.py",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    return DoctorCheck(
        name="representative_tests",
        status="pass" if not missing else "fail",
        details={"missing": missing},
        next_commands=[] if not missing else ["Restore missing representative tests."],
    )


def run_doctor(*, runner: Runner = run_command, root: Path = ROOT) -> dict[str, object]:
    checks = [
        check_python_version(),
        check_node_version(runner, root),
        check_backend_import(),
        check_frontend_dependencies(root),
        check_env_vars(),
        check_representative_tests(root),
    ]
    failed = [check for check in checks if check.status == "fail"]
    warned = [check for check in checks if check.status == "warn"]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "status": "fail" if failed else "warn" if warned else "pass",
        "checks": [asdict(check) for check in checks],
        "next_commands": [
            command
            for check in checks
            for command in check.next_commands
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local X-Agent environment")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    report = run_doctor()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"X-Agent doctor status: {report['status']}")
        for check in report["checks"]:
            print(f"- {check['name']}: {check['status']}")
    return 0 if report["status"] in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
