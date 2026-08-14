#!/usr/bin/env python3
"""Generate the Codex/Hermes gap-closure acceptance matrix.

The matrix is intentionally evidence-first: dry-run prints the planned checks,
while report mode records command results plus missing evidence. It must not be
used as a broad "full parity" claim unless every required category has fresh
passing evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".xagent_runtime" / "reports" / "codex-hermes-gap-closure.json"
SECRET_KEY_OUTPUT_RE = re.compile(r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+")
SECRET_VALUE_OUTPUT_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")

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
class MatrixCheck:
    """One acceptance check in the Codex/Hermes gap matrix."""

    category: str
    name: str
    command: list[str]
    cwd: str = "."
    timeout_seconds: int = 120
    required: bool = True
    evidence_paths: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class CommandOutcome:
    """Serializable result of one matrix command."""

    category: str
    name: str
    command: list[str]
    cwd: str
    status: str
    exit_code: int | None
    duration_seconds: float
    timeout_seconds: int
    stdout_tail: str = ""
    stderr_tail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "name": self.name,
            "command": self.command,
            "cwd": self.cwd,
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 3),
            "timeout_seconds": self.timeout_seconds,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


Runner = Callable[[MatrixCheck, Path], CommandOutcome]


def _pytest_command(paths: Iterable[str]) -> list[str]:
    return [
        "python",
        "-m",
        "pytest",
        *paths,
        "-o",
        "addopts=",
        "-o",
        "timeout=0",
        "-o",
        "faulthandler_timeout=0",
        "-p",
        "no:cov",
        "-q",
    ]


def _npm_command(*args: str) -> list[str]:
    executable = "npm.cmd" if os.name == "nt" else "npm"
    return [executable, *args]


def build_checks() -> list[MatrixCheck]:
    """Return the fixed matrix categories required by the gap-closure plan."""

    return [
        MatrixCheck(
            category="first_release",
            name="first release API and security contract",
            command=_pytest_command(["tests/test_first_release_entrypoints.py", "tests/test_security.py"]),
            evidence_paths=("tests/test_first_release_entrypoints.py", "tests/test_security.py"),
        ),
        MatrixCheck(
            category="web_chat",
            name="web chat and workbench product loop",
            command=_pytest_command(
                ["tests/test_chat_entrypoint_contract.py", "tests/test_first_release_entrypoints.py"]
            ),
            evidence_paths=("tests/test_chat_entrypoint_contract.py",),
        ),
        MatrixCheck(
            category="telegram_loop",
            name="telegram inbound event to dispatch to reply loop",
            command=_pytest_command(
                ["tests/test_channels.py", "tests/test_channel_router.py", "tests/test_telegram_channel_api.py"]
            ),
            evidence_paths=("tests/test_channel_router.py", "tests/test_telegram_channel_api.py"),
        ),
        MatrixCheck(
            category="github_issue_to_pr",
            name="GitHub issue-to-PR guarded dry-run workflow",
            command=_pytest_command(
                ["tests/test_issue_to_pr_pipeline.py", "tests/test_issue_to_pr_api.py", "tests/test_cli_github.py"]
            ),
            timeout_seconds=420,
            evidence_paths=("tests/test_issue_to_pr_api.py", "tests/test_cli_github.py"),
        ),
        MatrixCheck(
            category="skill_curator",
            name="Hermes-style deterministic skill curator MVP",
            command=_pytest_command(
                [
                    "tests/test_skill_curator_models.py",
                    "tests/test_skill_curator_scoring.py",
                    "tests/test_skill_curator_api.py",
                ]
            ),
            evidence_paths=(
                "tests/test_skill_curator_models.py",
                "tests/test_skill_curator_scoring.py",
                "tests/test_skill_curator_api.py",
            ),
        ),
        MatrixCheck(
            category="gateway",
            name="scheduler and always-available gateway dry-run mode",
            command=_pytest_command(["tests/test_scheduler.py", "tests/test_gateway_mode.py"]),
            evidence_paths=("tests/test_gateway_mode.py",),
        ),
        MatrixCheck(
            category="installer",
            name="one-command installer and doctor",
            command=_pytest_command(["tests/test_xagent_doctor.py"]),
            evidence_paths=("scripts/xagent_doctor.py", "tests/test_xagent_doctor.py"),
        ),
        MatrixCheck(
            category="frontend",
            name="frontend chat/workbench type contract",
            command=_npm_command("run", "type-check"),
            cwd="frontend",
            timeout_seconds=180,
            evidence_paths=("frontend/src/pages/ChatPage.tsx", "frontend/package.json"),
        ),
        MatrixCheck(
            category="docs",
            name="gap closure docs and IDE roadmap",
            command=[
                "python",
                "-c",
                (
                    "from pathlib import Path; "
                    "required=['docs/developer/reports/CODEX_HERMES_GAP_CLOSURE_REPORT.md',"
                    "'docs/concepts/planning/IDE_EXTENSION_ROADMAP.md',"
                    "'docs/developer/specs/vscode-extension-mvp.md']; "
                    "missing=[p for p in required if not Path(p).exists()]; "
                    "assert not missing, missing"
                ),
            ],
            evidence_paths=(
                "docs/developer/reports/CODEX_HERMES_GAP_CLOSURE_REPORT.md",
                "docs/concepts/planning/IDE_EXTENSION_ROADMAP.md",
                "docs/developer/specs/vscode-extension-mvp.md",
            ),
        ),
    ]


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in PROXY_KEYS:
        env.pop(key, None)
    env.setdefault("XAGENT_QDRANT_URL", "")
    env.setdefault("XAGENT_LLM_BACKEND", "mock")
    env.setdefault("XAGENT_E2E", "0")
    return env


def _tail(value: str | None, limit: int = 4000) -> str:
    if not value:
        return ""
    sanitized = _sanitize_output_text(value)
    if len(sanitized) <= limit:
        return sanitized
    return sanitized[-limit:]


def _sanitize_output_text(value: str) -> str:
    value = SECRET_KEY_OUTPUT_RE.sub(r"\1<redacted-output>", value)
    return SECRET_VALUE_OUTPUT_RE.sub("<redacted-secret>", value)


def run_command(check: MatrixCheck, root: Path = ROOT) -> CommandOutcome:
    """Run one check with a clean local-test environment."""

    start = time.perf_counter()
    execution_command = [sys.executable, *check.command[1:]] if check.command[:1] == ["python"] else check.command
    try:
        completed = subprocess.run(
            execution_command,
            cwd=root / check.cwd,
            env=_clean_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=check.timeout_seconds,
            check=False,
        )
        duration = time.perf_counter() - start
        return CommandOutcome(
            category=check.category,
            name=check.name,
            command=check.command,
            cwd=check.cwd,
            status="passed" if completed.returncode == 0 else "failed",
            exit_code=completed.returncode,
            duration_seconds=duration,
            timeout_seconds=check.timeout_seconds,
            stdout_tail=_tail(completed.stdout),
            stderr_tail=_tail(completed.stderr),
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - start
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr
        return CommandOutcome(
            category=check.category,
            name=check.name,
            command=check.command,
            cwd=check.cwd,
            status="timeout",
            exit_code=None,
            duration_seconds=duration,
            timeout_seconds=check.timeout_seconds,
            stdout_tail=_tail(stdout or ""),
            stderr_tail=_tail(stderr or ""),
        )
    except OSError as exc:
        duration = time.perf_counter() - start
        return CommandOutcome(
            category=check.category,
            name=check.name,
            command=check.command,
            cwd=check.cwd,
            status="failed",
            exit_code=None,
            duration_seconds=duration,
            timeout_seconds=check.timeout_seconds,
            stderr_tail=str(exc),
        )


def collect_git_status(root: Path = ROOT) -> dict[str, object]:
    """Collect compact git status without failing the matrix outside git."""

    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc), "branch": None, "status_short": []}

    return {
        "available": branch.returncode == 0 and status.returncode == 0,
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "status_short": [line for line in status.stdout.splitlines() if line.strip()],
    }


def planned_outcome(check: MatrixCheck) -> CommandOutcome:
    """Return a non-executed outcome for dry-run mode."""

    return CommandOutcome(
        category=check.category,
        name=check.name,
        command=check.command,
        cwd=check.cwd,
        status="planned",
        exit_code=None,
        duration_seconds=0.0,
        timeout_seconds=check.timeout_seconds,
    )


def missing_evidence_for(checks: Iterable[MatrixCheck], root: Path = ROOT) -> list[dict[str, str]]:
    """Find required evidence files that do not exist yet."""

    missing: list[dict[str, str]] = []
    for check in checks:
        for relative_path in check.evidence_paths:
            if not (root / relative_path).exists():
                missing.append(
                    {
                        "category": check.category,
                        "path": relative_path,
                        "reason": "required evidence file is missing",
                    }
                )
    return missing


def summarize(
    checks: list[MatrixCheck],
    outcomes: list[CommandOutcome],
    missing_evidence: list[dict[str, str]],
    dry_run: bool,
) -> dict[str, object]:
    """Summarize matrix results without making parity claims."""

    by_category: dict[str, dict[str, object]] = {}
    for check in checks:
        category_outcomes = [outcome for outcome in outcomes if outcome.category == check.category]
        category_missing = [
            item for item in missing_evidence if item["category"] == check.category
        ]
        passed = bool(category_outcomes) and all(
            outcome.status == "passed" for outcome in category_outcomes
        )
        by_category[check.category] = {
            "required": check.required,
            "status": "planned"
            if dry_run
            else "passed"
            if passed and not category_missing
            else "missing_evidence"
            if category_missing
            else "failed",
            "missing_evidence": category_missing,
        }

    failed_or_timeout = [
        outcome for outcome in outcomes if outcome.status in {"failed", "timeout"}
    ]
    if dry_run:
        overall_status = "dry_run"
    elif missing_evidence:
        overall_status = "missing_evidence"
    elif failed_or_timeout:
        overall_status = "failed"
    else:
        overall_status = "passed"

    return {
        "overall_status": overall_status,
        "categories": by_category,
        "counts": {
            "total_checks": len(checks),
            "passed": sum(1 for outcome in outcomes if outcome.status == "passed"),
            "failed": sum(1 for outcome in outcomes if outcome.status == "failed"),
            "timeout": sum(1 for outcome in outcomes if outcome.status == "timeout"),
            "planned": sum(1 for outcome in outcomes if outcome.status == "planned"),
            "missing_evidence": len(missing_evidence),
        },
        "competitive_parity": {
            "full_parity_claimed": False,
            "claim": "not_claimed"
            if overall_status != "passed"
            else "p0_gap_closure_evidence_available",
            "reason": "full Codex/Hermes parity requires broader external-product and production evidence"
            if overall_status == "passed"
            else "one or more required P0 evidence categories are not passing",
        },
    }


def build_report(
    *,
    checks: list[MatrixCheck],
    outcomes: list[CommandOutcome],
    missing_evidence: list[dict[str, str]],
    dry_run: bool,
    root: Path = ROOT,
) -> dict[str, object]:
    """Build the JSON-serializable matrix report."""

    return {
        "schema_version": "2026-06-05.codex-hermes-gap-matrix.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "python": {
            "executable": "python",
            "version": sys.version,
        },
        "git": collect_git_status(root),
        "dry_run": dry_run,
        "summary": summarize(checks, outcomes, missing_evidence, dry_run),
        "checks": [outcome.to_dict() for outcome in outcomes],
        "missing_evidence": missing_evidence,
    }


def run_matrix(
    *,
    dry_run: bool = False,
    runner: Runner = run_command,
    root: Path = ROOT,
) -> dict[str, object]:
    """Run or plan the matrix and return a complete report object."""

    checks = build_checks()
    outcomes = [planned_outcome(check) for check in checks] if dry_run else [
        runner(check, root) for check in checks
    ]
    missing = missing_evidence_for(checks, root)
    return build_report(
        checks=checks,
        outcomes=outcomes,
        missing_evidence=missing,
        dry_run=dry_run,
        root=root,
    )


def write_report(report: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_plan(report: dict[str, object]) -> None:
    print("Codex/Hermes gap matrix planned checks:")
    for check in report["checks"]:
        command = " ".join(str(part) for part in check["command"])
        print(f"- [{check['category']}] {check['name']} (cwd={check['cwd']}): {command}")

    missing = report["missing_evidence"]
    if missing:
        print("\nMissing evidence files:")
        for item in missing:
            print(f"- [{item['category']}] {item['path']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the X-Agent Codex/Hermes gap matrix")
    parser.add_argument("--dry-run", action="store_true", help="print planned checks without executing")
    parser.add_argument("--write-report", action="store_true", help="write the JSON report")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="report output path",
    )
    args = parser.parse_args()

    report = run_matrix(dry_run=args.dry_run)

    if args.dry_run:
        print_plan(report)
    else:
        summary = report["summary"]
        print(f"Codex/Hermes gap matrix status: {summary['overall_status']}")
        for category, data in summary["categories"].items():
            print(f"- {category}: {data['status']}")

    if args.write_report:
        write_report(report, args.output)
        print(f"Report written to {args.output}")

    return 0 if report["summary"]["overall_status"] in {"passed", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
