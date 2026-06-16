#!/usr/bin/env python3
"""Validate that an RC tag points at the expected release commit.

This gate is intentionally read-only. It does not create, delete, move, or push
tags. In normal CI it can record ``action_required`` without failing the build;
release owners can pass ``--require-match`` for the final handoff check.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "rc-tag-consistency-gate.json"
DEFAULT_TAG_NAME = "x-agent-commercial-rc-20260608"
DEFAULT_REMOTE = "origin"
GIT_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class TagConsistencyCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class TagConsistencyReport:
    status: str
    generated_at: str
    expected_commit_sha: str | None
    tag_name: str
    remote: str | None
    require_match: bool
    checks: list[TagConsistencyCheck]
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


def _local_tag_check(tag_name: str, expected_sha: str, *, require_match: bool) -> TagConsistencyCheck:
    stdout, error = _run_git(["rev-parse", "--verify", f"refs/tags/{tag_name}^{{commit}}"])
    if error:
        status = "failed" if require_match else "action_required"
        return TagConsistencyCheck(
            name="local_tag",
            status=status,
            details={"tag_name": tag_name, "expected_commit_sha": expected_sha},
            error=f"local tag is missing or unresolved: {error}",
        )
    actual_sha = stdout.strip().lower()
    if actual_sha != expected_sha:
        status = "failed" if require_match else "action_required"
        return TagConsistencyCheck(
            name="local_tag",
            status=status,
            details={
                "tag_name": tag_name,
                "expected_commit_sha": expected_sha,
                "actual_commit_sha": actual_sha,
                "matches_expected": False,
            },
            error=f"local tag {tag_name} points at {actual_sha}, expected {expected_sha}",
        )
    return TagConsistencyCheck(
        name="local_tag",
        status="passed",
        details={
            "tag_name": tag_name,
            "expected_commit_sha": expected_sha,
            "actual_commit_sha": actual_sha,
            "matches_expected": True,
        },
    )


def _remote_tag_check(
    tag_name: str,
    expected_sha: str,
    *,
    remote: str,
    require_match: bool,
) -> TagConsistencyCheck:
    stdout, error = _run_git(["ls-remote", "--tags", remote, f"refs/tags/{tag_name}*"])
    if error:
        status = "failed" if require_match else "action_required"
        return TagConsistencyCheck(
            name="remote_tag",
            status=status,
            details={"tag_name": tag_name, "remote": remote, "expected_commit_sha": expected_sha},
            error=f"remote tag could not be resolved: {error}",
        )
    actual_sha = _select_remote_tag_sha(stdout, tag_name)
    if actual_sha is None:
        status = "failed" if require_match else "action_required"
        return TagConsistencyCheck(
            name="remote_tag",
            status=status,
            details={"tag_name": tag_name, "remote": remote, "expected_commit_sha": expected_sha},
            error=f"remote tag {remote}/{tag_name} is missing",
        )
    if actual_sha != expected_sha:
        status = "failed" if require_match else "action_required"
        return TagConsistencyCheck(
            name="remote_tag",
            status=status,
            details={
                "tag_name": tag_name,
                "remote": remote,
                "expected_commit_sha": expected_sha,
                "actual_commit_sha": actual_sha,
                "matches_expected": False,
            },
            error=f"remote tag {remote}/{tag_name} points at {actual_sha}, expected {expected_sha}",
        )
    return TagConsistencyCheck(
        name="remote_tag",
        status="passed",
        details={
            "tag_name": tag_name,
            "remote": remote,
            "expected_commit_sha": expected_sha,
            "actual_commit_sha": actual_sha,
            "matches_expected": True,
        },
    )


def _select_remote_tag_sha(stdout: str, tag_name: str) -> str | None:
    exact_ref = f"refs/tags/{tag_name}"
    peeled_ref = f"{exact_ref}^{{}}"
    refs: dict[str, str] = {}
    for line in stdout.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        sha, ref = parts
        if GIT_COMMIT_SHA_RE.fullmatch(sha):
            refs[ref] = sha.lower()
    return refs.get(peeled_ref) or refs.get(exact_ref)


def _overall_status(checks: list[TagConsistencyCheck], *, require_match: bool) -> str:
    if any(check.status == "failed" for check in checks):
        return "failed"
    if any(check.status == "action_required" for check in checks):
        return "failed" if require_match else "action_required"
    return "passed"


def _next_commands(status: str, *, tag_name: str, expected_sha: str | None, remote: str | None) -> list[str]:
    if expected_sha is None:
        return ["Rerun with --expected-commit-sha <40-character-release-commit-sha>."]
    if status == "passed":
        return [f"RC tag {tag_name} resolves to expected release commit {expected_sha}."]
    remote_name = remote or DEFAULT_REMOTE
    return [
        f"Owner decision required: create a new RC tag at {expected_sha}, or explicitly approve correcting {tag_name}.",
        f"Non-destructive verification: git rev-parse {tag_name}; git ls-remote --tags {remote_name} {tag_name}.",
        f"Final check: python scripts\\rc_tag_consistency_gate.py --expected-commit-sha {expected_sha} --tag-name {tag_name} --require-match.",
    ]


def build_tag_consistency_report(
    *,
    expected_commit_sha: str | None = None,
    tag_name: str = DEFAULT_TAG_NAME,
    remote: str | None = DEFAULT_REMOTE,
    require_match: bool = False,
) -> TagConsistencyReport:
    expected_sha, expected_error = _resolve_expected_commit_sha(expected_commit_sha)
    checks: list[TagConsistencyCheck] = []
    if expected_error or expected_sha is None:
        checks.append(
            TagConsistencyCheck(
                name="expected_commit",
                status="failed",
                details={"expected_commit_sha": expected_commit_sha},
                error=expected_error or "expected commit SHA could not be resolved",
            )
        )
    else:
        checks.append(
            TagConsistencyCheck(
                name="expected_commit",
                status="passed",
                details={"expected_commit_sha": expected_sha},
            )
        )
        checks.append(_local_tag_check(tag_name, expected_sha, require_match=require_match))
        if remote:
            checks.append(_remote_tag_check(tag_name, expected_sha, remote=remote, require_match=require_match))

    status = _overall_status(checks, require_match=require_match)
    return TagConsistencyReport(
        status=status,
        generated_at=_utc_now(),
        expected_commit_sha=expected_sha,
        tag_name=tag_name,
        remote=remote,
        require_match=require_match,
        checks=checks,
        next_commands=_next_commands(status, tag_name=tag_name, expected_sha=expected_sha, remote=remote),
    )


def write_report(report: TagConsistencyReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate commercial RC tag consistency")
    parser.add_argument("--expected-commit-sha")
    parser.add_argument("--tag-name", default=DEFAULT_TAG_NAME)
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--no-remote", action="store_true")
    parser.add_argument("--require-match", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_tag_consistency_report(
        expected_commit_sha=args.expected_commit_sha,
        tag_name=args.tag_name,
        remote=None if args.no_remote else args.remote,
        require_match=args.require_match,
    )
    write_report(report, args.output)
    print(f"RC tag consistency status: {report.status}")
    print(f"Expected commit SHA: {report.expected_commit_sha or '<unresolved>'}")
    print(f"Tag: {report.tag_name}")
    if report.remote:
        print(f"Remote: {report.remote}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" or (report.status == "action_required" and not args.require_match) else 1


if __name__ == "__main__":
    raise SystemExit(main())
