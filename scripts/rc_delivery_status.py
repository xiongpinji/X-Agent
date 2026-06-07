#!/usr/bin/env python3
"""Summarize commercial RC delivery readiness from current evidence.

This script is read-only. It combines git state, hosted CI metadata when
provided, the owner-verified finalize report, and the selected RC tag gate into
one machine-readable status so stale evidence is harder to misread.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "rc-delivery-status.json"
DEFAULT_OWNER_FINALIZE_REPORT = REPORT_DIR / "rc-owner-verified-finalize.json"
DEFAULT_TAG_CONSISTENCY_REPORT = REPORT_DIR / "rc-tag-consistency-gate.json"
DEFAULT_REMOTE = "origin"
DEFAULT_BRANCH = "codex/codex-hermes-gap-closure"
DEFAULT_TAG_NAME = "x-agent-commercial-rc-20260608"
GIT_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
GITHUB_ACTIONS_RUN_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/actions/runs/(?P<run_id>[0-9]+)$"
)


@dataclass(frozen=True)
class DeliveryCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class DeliveryStatusReport:
    status: str
    generated_at: str
    expected_commit_sha: str | None
    remote: str
    branch: str
    tag_name: str
    owner_finalize_report_path: str
    tag_consistency_report_path: str
    checks: list[DeliveryCheck]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_git(args: list[str]) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", str(exc)
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "").strip()
        return "", error or f"git {' '.join(args)} exited {result.returncode}"
    return result.stdout.strip(), None


def _normalize_sha(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    normalized = value.strip().lower()
    if not GIT_COMMIT_SHA_RE.fullmatch(normalized):
        return None, "expected commit SHA must be a 40-character git SHA"
    return normalized, None


def _resolve_expected_commit_sha(expected_commit_sha: str | None) -> tuple[str | None, str | None]:
    normalized, error = _normalize_sha(expected_commit_sha)
    if normalized or error:
        return normalized, error
    stdout, git_error = _run_git(["rev-parse", "HEAD"])
    if git_error:
        return None, f"could not resolve current git HEAD: {git_error}"
    return _normalize_sha(stdout)


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"report not found: {path}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read report {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {path}"
    return payload, None


def _commit_check(expected_sha: str | None, expected_error: str | None) -> DeliveryCheck:
    if expected_error or expected_sha is None:
        return DeliveryCheck(
            name="expected_commit",
            status="failed",
            details={"expected_commit_sha": expected_sha},
            error=expected_error or "expected commit SHA could not be resolved",
        )
    stdout, error = _run_git(["rev-parse", "HEAD"])
    if error:
        return DeliveryCheck(
            name="expected_commit",
            status="failed",
            details={"expected_commit_sha": expected_sha},
            error=f"could not resolve current HEAD: {error}",
        )
    actual_sha = stdout.strip().lower()
    if actual_sha != expected_sha:
        return DeliveryCheck(
            name="expected_commit",
            status="failed",
            details={
                "expected_commit_sha": expected_sha,
                "current_head_sha": actual_sha,
                "matches_expected": False,
            },
            error=f"current HEAD {actual_sha} does not match expected commit {expected_sha}",
        )
    return DeliveryCheck(
        name="expected_commit",
        status="passed",
        details={
            "expected_commit_sha": expected_sha,
            "current_head_sha": actual_sha,
            "matches_expected": True,
        },
    )


def _remote_branch_check(*, expected_sha: str | None, remote: str, branch: str) -> DeliveryCheck:
    stdout, error = _run_git(["rev-parse", f"{remote}/{branch}"])
    if error:
        return DeliveryCheck(
            name="remote_branch",
            status="failed",
            details={"remote": remote, "branch": branch, "expected_commit_sha": expected_sha},
            error=f"could not resolve {remote}/{branch}: {error}",
        )
    actual_sha = stdout.strip().lower()
    matches = bool(expected_sha and actual_sha == expected_sha)
    return DeliveryCheck(
        name="remote_branch",
        status="passed" if matches else "failed",
        details={
            "remote": remote,
            "branch": branch,
            "expected_commit_sha": expected_sha,
            "actual_commit_sha": actual_sha,
            "matches_expected": matches,
        },
        error=None if matches else f"{remote}/{branch} points at {actual_sha}, expected {expected_sha}",
    )


def _hosted_ci_check(
    *,
    expected_sha: str | None,
    github_actions_run_url: str | None,
    github_actions_head_sha: str | None,
    fetch_github: bool,
) -> DeliveryCheck:
    details: dict[str, Any] = {
        "expected_commit_sha": expected_sha,
        "github_actions_run_url": github_actions_run_url,
        "github_actions_head_sha": github_actions_head_sha.lower() if github_actions_head_sha else None,
        "fetched": False,
    }
    if not github_actions_run_url:
        return DeliveryCheck(
            name="hosted_ci",
            status="action_required",
            details=details,
            error="hosted GitHub Actions run URL is missing",
        )
    if not GITHUB_ACTIONS_RUN_URL_RE.fullmatch(github_actions_run_url):
        return DeliveryCheck(
            name="hosted_ci",
            status="failed",
            details=details,
            error="hosted GitHub Actions run URL is not a GitHub Actions run URL",
        )
    if github_actions_head_sha and not GIT_COMMIT_SHA_RE.fullmatch(github_actions_head_sha):
        return DeliveryCheck(
            name="hosted_ci",
            status="failed",
            details=details,
            error="hosted GitHub Actions head SHA must be a 40-character git SHA",
        )
    if expected_sha and github_actions_head_sha and github_actions_head_sha.lower() != expected_sha:
        return DeliveryCheck(
            name="hosted_ci",
            status="failed",
            details=details,
            error=f"hosted GitHub Actions head SHA does not match expected commit {expected_sha}",
        )

    if fetch_github:
        fetched, fetch_error = _fetch_github_actions_run(github_actions_run_url)
        if fetch_error:
            details["fetch_error"] = fetch_error
            return DeliveryCheck(
                name="hosted_ci",
                status="action_required",
                details=details,
                error=f"could not fetch hosted GitHub Actions run: {fetch_error}",
            )
        if fetched:
            details["fetched"] = True
            details["fetched_head_sha"] = str(fetched.get("head_sha", "")).lower()
            details["fetched_status"] = fetched.get("status")
            details["fetched_conclusion"] = fetched.get("conclusion")
            if expected_sha and details["fetched_head_sha"] != expected_sha:
                return DeliveryCheck(
                    name="hosted_ci",
                    status="failed",
                    details=details,
                    error=f"hosted run head SHA {details['fetched_head_sha']} does not match {expected_sha}",
                )
            if fetched.get("status") != "completed" or fetched.get("conclusion") != "success":
                return DeliveryCheck(
                    name="hosted_ci",
                    status="failed",
                    details=details,
                    error="hosted GitHub Actions run is not completed successfully",
                )

    if expected_sha and github_actions_head_sha:
        return DeliveryCheck(name="hosted_ci", status="passed", details=details)
    return DeliveryCheck(
        name="hosted_ci",
        status="action_required",
        details=details,
        error="hosted GitHub Actions head SHA is missing",
    )


def _fetch_github_actions_run(run_url: str) -> tuple[dict[str, Any] | None, str | None]:
    match = GITHUB_ACTIONS_RUN_URL_RE.fullmatch(run_url)
    if not match:
        return None, "invalid GitHub Actions run URL"
    api_url = (
        "https://api.github.com/repos/"
        f"{match.group('owner')}/{match.group('repo')}/actions/runs/{match.group('run_id')}"
    )
    request = urllib.request.Request(api_url, headers={"User-Agent": "xagent-rc-delivery-status"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return None, str(exc)
    return payload if isinstance(payload, dict) else None, None


def _owner_finalize_check(*, expected_sha: str | None, report_path: Path) -> DeliveryCheck:
    payload, error = _read_json(report_path)
    if error or payload is None:
        return DeliveryCheck(
            name="owner_verified_finalize",
            status="action_required",
            details={"report_path": str(report_path), "expected_commit_sha": expected_sha},
            error=error,
        )
    details = {
        "report_path": str(report_path),
        "status": payload.get("status"),
        "expected_commit_sha": payload.get("expected_commit_sha"),
        "github_actions_run_url": payload.get("github_actions_run_url"),
        "github_actions_head_sha": payload.get("github_actions_head_sha"),
        "can_tag_rc_now": payload.get("can_tag_rc_now"),
        "refresh_chain_owner_verified": payload.get("refresh_chain_owner_verified"),
    }
    if payload.get("expected_commit_sha") != expected_sha:
        return DeliveryCheck(
            name="owner_verified_finalize",
            status="action_required",
            details=details,
            error="owner finalize report is missing or does not match expected commit SHA",
        )
    if payload.get("github_actions_head_sha") and payload.get("github_actions_head_sha") != expected_sha:
        return DeliveryCheck(
            name="owner_verified_finalize",
            status="failed",
            details=details,
            error="owner finalize hosted Actions head SHA does not match expected commit SHA",
        )
    if (
        payload.get("status") == "ready_for_rc_tag"
        and payload.get("can_tag_rc_now") is True
        and payload.get("refresh_chain_owner_verified") is True
    ):
        return DeliveryCheck(name="owner_verified_finalize", status="passed", details=details)
    return DeliveryCheck(
        name="owner_verified_finalize",
        status="action_required",
        details=details,
        error="owner-verified finalize is not ready_for_rc_tag for the expected commit",
    )


def _tag_consistency_check(
    *,
    expected_sha: str | None,
    tag_name: str,
    report_path: Path,
) -> DeliveryCheck:
    payload, error = _read_json(report_path)
    if error or payload is None:
        return DeliveryCheck(
            name="tag_consistency",
            status="action_required",
            details={"report_path": str(report_path), "tag_name": tag_name, "expected_commit_sha": expected_sha},
            error=error,
        )
    details = {
        "report_path": str(report_path),
        "status": payload.get("status"),
        "tag_name": payload.get("tag_name"),
        "expected_commit_sha": payload.get("expected_commit_sha"),
    }
    if payload.get("expected_commit_sha") != expected_sha or payload.get("tag_name") != tag_name:
        return DeliveryCheck(
            name="tag_consistency",
            status="action_required",
            details=details,
            error="tag consistency report does not match the requested tag and expected commit",
        )
    if payload.get("status") != "passed":
        return DeliveryCheck(
            name="tag_consistency",
            status="action_required",
            details=details,
            error="tag consistency report has not passed",
        )
    return DeliveryCheck(name="tag_consistency", status="passed", details=details)


def _overall_status(checks: list[DeliveryCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "failed"
    pending = {check.name for check in checks if check.status == "action_required"}
    if "owner_verified_finalize" in pending:
        return "owner_finalize_pending"
    if "tag_consistency" in pending:
        return "tag_action_required"
    if "hosted_ci" in pending:
        return "ci_evidence_pending"
    if pending:
        return "action_required"
    return "commercial_rc_ready"


def _next_commands(
    *,
    status: str,
    expected_sha: str | None,
    tag_name: str,
    github_actions_run_url: str | None,
    github_actions_head_sha: str | None,
) -> list[str]:
    expected = expected_sha or "<expected-release-commit-sha>"
    if status == "commercial_rc_ready":
        return [f"Commercial RC evidence is complete for {tag_name} at {expected}."]
    commands = []
    if status == "owner_finalize_pending":
        run_url = github_actions_run_url or "<hosted-commercial-rc-run-url>"
        head_sha = github_actions_head_sha or expected
        commands.append(
            "Rerun owner finalize with owner-controlled Feishu/GitHub env: "
            "python scripts\\rc_owner_verified_finalize.py --provider ollama "
            "--ollama-model qwen2.5:1.5b --ollama-base-url http://127.0.0.1:11435 "
            f"--github-actions-run-url {run_url} --github-actions-head-sha {head_sha} "
            f"--expected-commit-sha {expected}"
        )
    if status in {"tag_action_required", "owner_finalize_pending", "action_required"}:
        commands.append(
            "Refresh tag consistency: "
            f"python scripts\\rc_tag_consistency_gate.py --expected-commit-sha {expected} "
            f"--tag-name {tag_name} --require-match"
        )
    if status == "ci_evidence_pending":
        commands.append("Pass --github-actions-run-url and --github-actions-head-sha for the hosted RC run.")
    if not commands:
        commands.append("Inspect .xagent_runtime/reports/rc-delivery-status.json and resolve failed checks.")
    return commands


def build_delivery_status_report(
    *,
    expected_commit_sha: str | None = None,
    remote: str = DEFAULT_REMOTE,
    branch: str = DEFAULT_BRANCH,
    tag_name: str = DEFAULT_TAG_NAME,
    github_actions_run_url: str | None = None,
    github_actions_head_sha: str | None = None,
    owner_finalize_report_path: Path = DEFAULT_OWNER_FINALIZE_REPORT,
    tag_consistency_report_path: Path = DEFAULT_TAG_CONSISTENCY_REPORT,
    fetch_github: bool = False,
) -> DeliveryStatusReport:
    expected_sha, expected_error = _resolve_expected_commit_sha(expected_commit_sha)
    checks = [
        _commit_check(expected_sha, expected_error),
        _remote_branch_check(expected_sha=expected_sha, remote=remote, branch=branch),
        _hosted_ci_check(
            expected_sha=expected_sha,
            github_actions_run_url=github_actions_run_url,
            github_actions_head_sha=github_actions_head_sha,
            fetch_github=fetch_github,
        ),
        _owner_finalize_check(expected_sha=expected_sha, report_path=owner_finalize_report_path),
        _tag_consistency_check(
            expected_sha=expected_sha,
            tag_name=tag_name,
            report_path=tag_consistency_report_path,
        ),
    ]
    status = _overall_status(checks)
    return DeliveryStatusReport(
        status=status,
        generated_at=_utc_now(),
        expected_commit_sha=expected_sha,
        remote=remote,
        branch=branch,
        tag_name=tag_name,
        owner_finalize_report_path=str(owner_finalize_report_path),
        tag_consistency_report_path=str(tag_consistency_report_path),
        checks=checks,
        next_commands=_next_commands(
            status=status,
            expected_sha=expected_sha,
            tag_name=tag_name,
            github_actions_run_url=github_actions_run_url,
            github_actions_head_sha=github_actions_head_sha,
        ),
    )


def write_report(report: DeliveryStatusReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize commercial RC delivery readiness")
    parser.add_argument("--expected-commit-sha")
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--tag-name", default=DEFAULT_TAG_NAME)
    parser.add_argument("--github-actions-run-url")
    parser.add_argument("--github-actions-head-sha")
    parser.add_argument("--owner-finalize-report", type=Path, default=DEFAULT_OWNER_FINALIZE_REPORT)
    parser.add_argument("--tag-consistency-report", type=Path, default=DEFAULT_TAG_CONSISTENCY_REPORT)
    parser.add_argument("--fetch-github", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_delivery_status_report(
        expected_commit_sha=args.expected_commit_sha,
        remote=args.remote,
        branch=args.branch,
        tag_name=args.tag_name,
        github_actions_run_url=args.github_actions_run_url,
        github_actions_head_sha=args.github_actions_head_sha,
        owner_finalize_report_path=args.owner_finalize_report,
        tag_consistency_report_path=args.tag_consistency_report,
        fetch_github=args.fetch_github,
    )
    write_report(report, args.output)
    print(f"RC delivery status: {report.status}")
    print(f"Expected commit SHA: {report.expected_commit_sha or '<unresolved>'}")
    print(f"Branch: {report.remote}/{report.branch}")
    print(f"Tag: {report.tag_name}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "commercial_rc_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
