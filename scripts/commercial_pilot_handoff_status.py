#!/usr/bin/env python3
"""Summarize Feishu commercial pilot handoff readiness.

This script is read-only. It binds the post-RC Feishu pilot handoff to a
specific RC baseline, pilot commit, hosted CI run, live Feishu inbound evidence,
and pilot tag without moving or overwriting commercial RC evidence.
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
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-handoff-status.json"
DEFAULT_RC_DELIVERY_REPORT = REPORT_DIR / "rc-delivery-status.json"
DEFAULT_FEISHU_LIVE_REPORT = REPORT_DIR / "commercial-pilot-feishu-live.json"
DEFAULT_PILOT_READINESS_REPORT = REPORT_DIR / "commercial-pilot-readiness.json"
DEFAULT_REFRESH_CHAIN_REPORT = REPORT_DIR / "commercial-pilot-refresh-chain.json"
DEFAULT_REMOTE = "origin"
DEFAULT_BRANCH = "codex/codex-hermes-gap-closure"
GIT_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
GITHUB_ACTIONS_RUN_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/actions/runs/(?P<run_id>[0-9]+)$"
)


@dataclass(frozen=True)
class HandoffCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class HandoffStatusReport:
    status: str
    generated_at: str
    expected_pilot_commit_sha: str | None
    pilot_tag_name: str
    expected_rc_commit_sha: str | None
    rc_tag_name: str
    remote: str
    branch: str
    github_actions_run_url: str | None
    github_actions_head_sha: str | None
    rc_delivery_report_path: str
    feishu_live_report_path: str
    pilot_readiness_report_path: str
    refresh_chain_report_path: str
    full_codex_parity_claimed: bool
    checks: list[HandoffCheck]
    next_commands: list[str]
    known_limits: list[str]

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


def _normalize_sha(value: str | None, *, label: str) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    normalized = value.strip().lower()
    if not GIT_COMMIT_SHA_RE.fullmatch(normalized):
        return None, f"{label} must be a 40-character git SHA"
    return normalized, None


def _resolve_expected_pilot_commit_sha(expected_pilot_commit_sha: str | None) -> tuple[str | None, str | None]:
    normalized, error = _normalize_sha(expected_pilot_commit_sha, label="expected pilot commit SHA")
    if normalized or error:
        return normalized, error
    stdout, git_error = _run_git(["rev-parse", "HEAD"])
    if git_error:
        return None, f"could not resolve current git HEAD: {git_error}"
    return _normalize_sha(stdout, label="current git HEAD")


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


def _pilot_commit_check(
    *,
    expected_sha: str | None,
    expected_error: str | None,
    require_pilot_head: bool,
) -> HandoffCheck:
    if expected_error or expected_sha is None:
        return HandoffCheck(
            name="pilot_commit",
            status="failed",
            details={"expected_pilot_commit_sha": expected_sha},
            error=expected_error or "expected pilot commit SHA could not be resolved",
        )

    stdout, head_error = _run_git(["rev-parse", "HEAD"])
    current_head = stdout.strip().lower() if not head_error else None
    exists_stdout, exists_error = _run_git(["cat-file", "-e", f"{expected_sha}^{{commit}}"])
    details = {
        "expected_pilot_commit_sha": expected_sha,
        "current_head_sha": current_head,
        "current_head_matches_expected": current_head == expected_sha,
        "require_pilot_head": require_pilot_head,
        "commit_exists": exists_error is None,
    }
    if head_error:
        return HandoffCheck(
            name="pilot_commit",
            status="failed",
            details=details,
            error=f"could not resolve current HEAD: {head_error}",
        )
    if exists_error:
        return HandoffCheck(
            name="pilot_commit",
            status="failed",
            details=details | {"git_output": exists_stdout},
            error=f"expected pilot commit is not present locally: {exists_error}",
        )
    if require_pilot_head and current_head != expected_sha:
        return HandoffCheck(
            name="pilot_commit",
            status="failed",
            details=details,
            error=f"current HEAD {current_head} does not match expected pilot commit {expected_sha}",
        )
    return HandoffCheck(name="pilot_commit", status="passed", details=details)


def _remote_branch_check(
    *,
    expected_sha: str | None,
    remote: str,
    branch: str,
    require_remote_head: bool,
) -> HandoffCheck:
    stdout, error = _run_git(["ls-remote", "--heads", remote, f"refs/heads/{branch}"])
    if error:
        return HandoffCheck(
            name="remote_branch",
            status="failed",
            details={"remote": remote, "branch": branch, "expected_pilot_commit_sha": expected_sha},
            error=f"could not resolve remote branch {remote}/{branch}: {error}",
        )
    remote_head = _select_remote_head_sha(stdout, branch)
    if remote_head is None:
        return HandoffCheck(
            name="remote_branch",
            status="failed",
            details={"remote": remote, "branch": branch, "expected_pilot_commit_sha": expected_sha},
            error=f"remote branch {remote}/{branch} is missing",
        )
    details = {
        "remote": remote,
        "branch": branch,
        "expected_pilot_commit_sha": expected_sha,
        "remote_head_sha": remote_head,
        "remote_head_matches_expected": bool(expected_sha and remote_head == expected_sha),
        "require_remote_head": require_remote_head,
    }
    if not expected_sha:
        return HandoffCheck(
            name="remote_branch",
            status="failed",
            details=details,
            error="expected pilot commit SHA is missing",
        )
    if require_remote_head and remote_head != expected_sha:
        return HandoffCheck(
            name="remote_branch",
            status="failed",
            details=details,
            error=f"{remote}/{branch} points at {remote_head}, expected {expected_sha}",
        )
    _, ancestor_error = _run_git(["merge-base", "--is-ancestor", expected_sha, remote_head])
    details["remote_branch_contains_expected"] = ancestor_error is None
    if ancestor_error:
        return HandoffCheck(
            name="remote_branch",
            status="failed",
            details=details,
            error=f"{remote}/{branch} does not contain expected pilot commit {expected_sha}",
        )
    return HandoffCheck(name="remote_branch", status="passed", details=details)


def _select_remote_head_sha(stdout: str, branch: str) -> str | None:
    exact_ref = f"refs/heads/{branch}"
    for line in stdout.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        sha, ref = parts
        if ref == exact_ref and GIT_COMMIT_SHA_RE.fullmatch(sha):
            return sha.lower()
    return None


def _hosted_ci_check(
    *,
    expected_sha: str | None,
    github_actions_run_url: str | None,
    github_actions_head_sha: str | None,
    fetch_github: bool,
) -> HandoffCheck:
    normalized_head_sha = github_actions_head_sha.lower() if github_actions_head_sha else None
    details: dict[str, Any] = {
        "expected_pilot_commit_sha": expected_sha,
        "github_actions_run_url": github_actions_run_url,
        "github_actions_head_sha": normalized_head_sha,
        "fetched": False,
    }
    if not github_actions_run_url:
        return HandoffCheck(
            name="hosted_ci",
            status="action_required",
            details=details,
            error="hosted GitHub Actions run URL is missing",
        )
    if not GITHUB_ACTIONS_RUN_URL_RE.fullmatch(github_actions_run_url):
        return HandoffCheck(
            name="hosted_ci",
            status="failed",
            details=details,
            error="hosted GitHub Actions run URL is not a GitHub Actions run URL",
        )
    if github_actions_head_sha and not GIT_COMMIT_SHA_RE.fullmatch(github_actions_head_sha):
        return HandoffCheck(
            name="hosted_ci",
            status="failed",
            details=details,
            error="hosted GitHub Actions head SHA must be a 40-character git SHA",
        )
    if expected_sha and normalized_head_sha and normalized_head_sha != expected_sha:
        return HandoffCheck(
            name="hosted_ci",
            status="failed",
            details=details,
            error=f"hosted GitHub Actions head SHA does not match expected pilot commit {expected_sha}",
        )

    if fetch_github:
        fetched, fetch_error = _fetch_github_actions_run(github_actions_run_url)
        if fetch_error:
            details["fetch_error"] = fetch_error
            return HandoffCheck(
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
                return HandoffCheck(
                    name="hosted_ci",
                    status="failed",
                    details=details,
                    error=f"hosted run head SHA {details['fetched_head_sha']} does not match {expected_sha}",
                )
            if fetched.get("status") != "completed" or fetched.get("conclusion") != "success":
                return HandoffCheck(
                    name="hosted_ci",
                    status="failed",
                    details=details,
                    error="hosted GitHub Actions run is not completed successfully",
                )

    if expected_sha and normalized_head_sha:
        return HandoffCheck(name="hosted_ci", status="passed", details=details)
    return HandoffCheck(
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
    request = urllib.request.Request(api_url, headers={"User-Agent": "xagent-commercial-pilot-handoff-status"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return None, str(exc)
    return payload if isinstance(payload, dict) else None, None


def _rc_baseline_check(*, path: Path, expected_rc_commit_sha: str | None, rc_tag_name: str) -> HandoffCheck:
    payload, error = _read_json(path)
    if error or payload is None:
        return HandoffCheck(
            name="rc_baseline",
            status="failed",
            details={"report_path": str(path), "expected_rc_commit_sha": expected_rc_commit_sha},
            error=error or "RC delivery report is missing",
        )
    details = {
        "report_path": str(path),
        "status": payload.get("status"),
        "tag_name": payload.get("tag_name"),
        "expected_commit_sha": payload.get("expected_commit_sha"),
    }
    if payload.get("status") != "commercial_rc_ready":
        return HandoffCheck(
            name="rc_baseline",
            status="failed",
            details=details,
            error="RC delivery report is not commercial_rc_ready",
        )
    if payload.get("tag_name") != rc_tag_name:
        return HandoffCheck(
            name="rc_baseline",
            status="failed",
            details=details | {"expected_rc_tag_name": rc_tag_name},
            error="RC delivery tag does not match expected pilot baseline",
        )
    if expected_rc_commit_sha and payload.get("expected_commit_sha") != expected_rc_commit_sha:
        return HandoffCheck(
            name="rc_baseline",
            status="failed",
            details=details | {"expected_rc_commit_sha": expected_rc_commit_sha},
            error="RC delivery commit does not match expected pilot baseline",
        )
    return HandoffCheck(name="rc_baseline", status="passed", details=details)


def _feishu_live_evidence_check(path: Path) -> HandoffCheck:
    payload, error = _read_json(path)
    if error or payload is None:
        return HandoffCheck(
            name="feishu_live_evidence",
            status="action_required",
            details={"report_path": str(path)},
            error=error or "Feishu live evidence report is missing",
        )
    required_equals = {
        "status": "passed",
        "channel": "feishu",
        "evidence_type": "commercial_pilot_feishu_live",
        "event_type": "im.message.receive_v1",
        "signature_mode": "lark_sha256",
        "encrypted_callback": True,
        "tenant_key_present": True,
        "message_id_present": True,
        "chat_id_present": True,
        "content_present": True,
        "app_id_configured": True,
        "app_secret_configured": True,
        "encrypt_key_configured": True,
        "mutation_performed": False,
        "outbound_message_sent": False,
    }
    details = {
        "report_path": str(path),
        **{key: payload.get(key) for key in required_equals},
        "event_id": payload.get("event_id"),
    }
    mismatches = {
        key: {"expected": expected, "actual": payload.get(key)}
        for key, expected in required_equals.items()
        if payload.get(key) != expected
    }
    if mismatches:
        return HandoffCheck(
            name="feishu_live_evidence",
            status="failed",
            details=details | {"mismatches": mismatches},
            error="Feishu live evidence does not match the required inbound-only owner-verified contract",
        )

    nested_checks = payload.get("checks")
    if isinstance(nested_checks, list):
        failed_nested = [
            item
            for item in nested_checks
            if isinstance(item, dict) and item.get("status") not in {"passed", "ready"}
        ]
        if failed_nested:
            return HandoffCheck(
                name="feishu_live_evidence",
                status="failed",
                details=details | {"failed_nested_checks": failed_nested},
                error="one or more nested Feishu evidence checks did not pass",
            )
    return HandoffCheck(name="feishu_live_evidence", status="passed", details=details)


def _pilot_readiness_check(
    *,
    path: Path,
    expected_rc_commit_sha: str | None,
    rc_tag_name: str,
    pilot_channel: str,
) -> HandoffCheck:
    payload, error = _read_json(path)
    if error or payload is None:
        return HandoffCheck(
            name="pilot_readiness",
            status="action_required",
            details={"report_path": str(path)},
            error=error or "pilot readiness report is missing",
        )
    details = {
        "report_path": str(path),
        "status": payload.get("status"),
        "pilot_channel": payload.get("pilot_channel"),
        "rc_tag": payload.get("rc_tag"),
        "rc_commit": payload.get("rc_commit"),
        "full_codex_parity_claimed": payload.get("full_codex_parity_claimed"),
    }
    if payload.get("full_codex_parity_claimed") is not False:
        return HandoffCheck(
            name="pilot_readiness",
            status="failed",
            details=details,
            error="pilot readiness must not claim full Codex parity",
        )
    if payload.get("pilot_channel") != pilot_channel:
        return HandoffCheck(
            name="pilot_readiness",
            status="failed",
            details=details | {"expected_pilot_channel": pilot_channel},
            error="pilot readiness channel does not match expected handoff channel",
        )
    if payload.get("rc_tag") != rc_tag_name:
        return HandoffCheck(
            name="pilot_readiness",
            status="failed",
            details=details | {"expected_rc_tag_name": rc_tag_name},
            error="pilot readiness RC tag does not match expected baseline",
        )
    if expected_rc_commit_sha and payload.get("rc_commit") != expected_rc_commit_sha:
        return HandoffCheck(
            name="pilot_readiness",
            status="failed",
            details=details | {"expected_rc_commit_sha": expected_rc_commit_sha},
            error="pilot readiness RC commit does not match expected baseline",
        )
    if payload.get("status") != "pilot_ready":
        return HandoffCheck(
            name="pilot_readiness",
            status="action_required",
            details=details,
            error="pilot readiness report is not pilot_ready",
        )
    return HandoffCheck(name="pilot_readiness", status="passed", details=details)


def _refresh_chain_check(*, path: Path, pilot_channel: str) -> HandoffCheck:
    payload, error = _read_json(path)
    if error or payload is None:
        return HandoffCheck(
            name="refresh_chain",
            status="action_required",
            details={"report_path": str(path)},
            error=error or "commercial pilot refresh chain report is missing",
        )
    steps = payload.get("steps")
    failed_steps = [
        item
        for item in steps
        if isinstance(item, dict) and item.get("status") not in {"passed", "ready"}
    ] if isinstance(steps, list) else []
    details = {
        "report_path": str(path),
        "status": payload.get("status"),
        "pilot_channel": payload.get("pilot_channel"),
        "full_codex_parity_claimed": payload.get("full_codex_parity_claimed"),
        "step_count": len(steps) if isinstance(steps, list) else None,
    }
    if payload.get("full_codex_parity_claimed") is not False:
        return HandoffCheck(
            name="refresh_chain",
            status="failed",
            details=details,
            error="refresh chain must not claim full Codex parity",
        )
    if payload.get("pilot_channel") != pilot_channel:
        return HandoffCheck(
            name="refresh_chain",
            status="failed",
            details=details | {"expected_pilot_channel": pilot_channel},
            error="refresh chain channel does not match expected handoff channel",
        )
    if payload.get("status") != "pilot_ready":
        return HandoffCheck(
            name="refresh_chain",
            status="action_required",
            details=details,
            error="commercial pilot refresh chain is not pilot_ready",
        )
    if not isinstance(steps, list) or not steps:
        return HandoffCheck(
            name="refresh_chain",
            status="action_required",
            details=details,
            error="commercial pilot refresh chain has no recorded steps",
        )
    if failed_steps:
        return HandoffCheck(
            name="refresh_chain",
            status="failed",
            details=details | {"failed_steps": failed_steps},
            error="one or more refresh-chain steps did not pass",
        )
    return HandoffCheck(name="refresh_chain", status="passed", details=details)


def _pilot_tag_consistency_check(*, expected_sha: str | None, tag_name: str, remote: str) -> HandoffCheck:
    details: dict[str, Any] = {
        "tag_name": tag_name,
        "expected_pilot_commit_sha": expected_sha,
        "remote": remote,
    }
    if expected_sha is None:
        return HandoffCheck(
            name="pilot_tag_consistency",
            status="failed",
            details=details,
            error="expected pilot commit SHA is missing",
        )

    local_stdout, local_error = _run_git(["rev-parse", "--verify", f"refs/tags/{tag_name}^{{commit}}"])
    local_sha = local_stdout.strip().lower() if not local_error else None
    remote_stdout, remote_error = _run_git(
        ["ls-remote", "--tags", remote, f"refs/tags/{tag_name}", f"refs/tags/{tag_name}^{{}}"]
    )
    remote_sha = _select_remote_tag_sha(remote_stdout, tag_name) if not remote_error else None
    details.update(
        {
            "local_tag_sha": local_sha,
            "remote_tag_sha": remote_sha,
            "local_tag_matches_expected": local_sha == expected_sha,
            "remote_tag_matches_expected": remote_sha == expected_sha,
        }
    )
    if local_error or remote_error or local_sha is None or remote_sha is None:
        missing = []
        if local_error or local_sha is None:
            missing.append("local")
            details["local_error"] = local_error
        if remote_error or remote_sha is None:
            missing.append("remote")
            details["remote_error"] = remote_error
        return HandoffCheck(
            name="pilot_tag_consistency",
            status="action_required",
            details=details,
            error=f"pilot handoff tag is missing or unresolved for: {', '.join(missing)}",
        )
    if local_sha != expected_sha or remote_sha != expected_sha:
        return HandoffCheck(
            name="pilot_tag_consistency",
            status="failed",
            details=details,
            error="pilot handoff tag does not point at the expected pilot commit",
        )
    return HandoffCheck(name="pilot_tag_consistency", status="passed", details=details)


def _select_remote_tag_sha(stdout: str, tag_name: str) -> str | None:
    exact_ref = f"refs/tags/{tag_name}"
    peeled_ref = f"{exact_ref}^{{}}"
    exact_sha: str | None = None
    peeled_sha: str | None = None
    for line in stdout.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        sha, ref = parts
        if not GIT_COMMIT_SHA_RE.fullmatch(sha):
            continue
        if ref == peeled_ref:
            peeled_sha = sha.lower()
        elif ref == exact_ref:
            exact_sha = sha.lower()
    return peeled_sha or exact_sha


def _overall_status(checks: list[HandoffCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "failed"
    pending = {check.name for check in checks if check.status == "action_required"}
    if "pilot_tag_consistency" in pending:
        return "pilot_tag_action_required"
    if "hosted_ci" in pending:
        return "ci_evidence_pending"
    if pending:
        return "action_required"
    return "pilot_handoff_ready"


def _next_commands(
    *,
    status: str,
    expected_pilot_sha: str | None,
    pilot_tag_name: str,
    github_actions_run_url: str | None,
    github_actions_head_sha: str | None,
) -> list[str]:
    expected = expected_pilot_sha or "<expected-pilot-commit-sha>"
    if status == "pilot_handoff_ready":
        return [f"Feishu commercial pilot handoff evidence is complete for {pilot_tag_name} at {expected}."]
    commands: list[str] = []
    if status == "pilot_tag_action_required":
        commands.extend(
            [
                f"git tag {pilot_tag_name} {expected}",
                f"git push origin {pilot_tag_name}",
            ]
        )
    if status == "ci_evidence_pending":
        run_url = github_actions_run_url or "<hosted-commercial-pilot-run-url>"
        head_sha = github_actions_head_sha or expected
        commands.append(
            "Rerun with hosted CI evidence: "
            "python scripts\\commercial_pilot_handoff_status.py "
            f"--expected-pilot-commit-sha {expected} --pilot-tag-name {pilot_tag_name} "
            f"--github-actions-run-url {run_url} --github-actions-head-sha {head_sha} --fetch-github"
        )
    if not commands:
        commands.append("Inspect .xagent_runtime/reports/commercial-pilot-handoff-status.json and resolve failed checks.")
    return commands


def build_handoff_status_report(
    *,
    expected_pilot_commit_sha: str | None = None,
    pilot_tag_name: str | None = None,
    expected_rc_commit_sha: str | None = None,
    rc_tag_name: str | None = None,
    remote: str = DEFAULT_REMOTE,
    branch: str = DEFAULT_BRANCH,
    github_actions_run_url: str | None = None,
    github_actions_head_sha: str | None = None,
    rc_delivery_report_path: Path = DEFAULT_RC_DELIVERY_REPORT,
    feishu_live_report_path: Path = DEFAULT_FEISHU_LIVE_REPORT,
    pilot_readiness_report_path: Path = DEFAULT_PILOT_READINESS_REPORT,
    refresh_chain_report_path: Path = DEFAULT_REFRESH_CHAIN_REPORT,
    pilot_channel: str = "feishu",
    require_pilot_head: bool = False,
    require_remote_head: bool = False,
    fetch_github: bool = False,
) -> HandoffStatusReport:
    if not pilot_tag_name:
        raise ValueError("pilot_tag_name is required; pass the selected pilot handoff tag explicitly")
    if not rc_tag_name:
        raise ValueError("rc_tag_name is required; pass the selected RC baseline tag explicitly")

    expected_pilot_sha, expected_pilot_error = _resolve_expected_pilot_commit_sha(expected_pilot_commit_sha)
    expected_rc_sha, expected_rc_error = _normalize_sha(expected_rc_commit_sha, label="expected RC commit SHA")
    if expected_rc_error:
        checks = [
            HandoffCheck(
                name="rc_commit_input",
                status="failed",
                details={"expected_rc_commit_sha": expected_rc_commit_sha},
                error=expected_rc_error,
            )
        ]
    else:
        checks = []

    checks.extend(
        [
            _pilot_commit_check(
                expected_sha=expected_pilot_sha,
                expected_error=expected_pilot_error,
                require_pilot_head=require_pilot_head,
            ),
            _remote_branch_check(
                expected_sha=expected_pilot_sha,
                remote=remote,
                branch=branch,
                require_remote_head=require_remote_head,
            ),
            _hosted_ci_check(
                expected_sha=expected_pilot_sha,
                github_actions_run_url=github_actions_run_url,
                github_actions_head_sha=github_actions_head_sha,
                fetch_github=fetch_github,
            ),
            _rc_baseline_check(path=rc_delivery_report_path, expected_rc_commit_sha=expected_rc_sha, rc_tag_name=rc_tag_name),
            _feishu_live_evidence_check(feishu_live_report_path),
            _pilot_readiness_check(
                path=pilot_readiness_report_path,
                expected_rc_commit_sha=expected_rc_sha,
                rc_tag_name=rc_tag_name,
                pilot_channel=pilot_channel,
            ),
            _refresh_chain_check(path=refresh_chain_report_path, pilot_channel=pilot_channel),
            _pilot_tag_consistency_check(expected_sha=expected_pilot_sha, tag_name=pilot_tag_name, remote=remote),
        ]
    )
    status = _overall_status(checks)
    return HandoffStatusReport(
        status=status,
        generated_at=_utc_now(),
        expected_pilot_commit_sha=expected_pilot_sha,
        pilot_tag_name=pilot_tag_name,
        expected_rc_commit_sha=expected_rc_sha,
        rc_tag_name=rc_tag_name,
        remote=remote,
        branch=branch,
        github_actions_run_url=github_actions_run_url,
        github_actions_head_sha=github_actions_head_sha.lower() if github_actions_head_sha else None,
        rc_delivery_report_path=str(rc_delivery_report_path),
        feishu_live_report_path=str(feishu_live_report_path),
        pilot_readiness_report_path=str(pilot_readiness_report_path),
        refresh_chain_report_path=str(refresh_chain_report_path),
        full_codex_parity_claimed=False,
        checks=checks,
        next_commands=_next_commands(
            status=status,
            expected_pilot_sha=expected_pilot_sha,
            pilot_tag_name=pilot_tag_name,
            github_actions_run_url=github_actions_run_url,
            github_actions_head_sha=github_actions_head_sha,
        ),
        known_limits=[
            "This report proves Feishu commercial pilot handoff readiness, not full Codex parity.",
            "The selected pilot tag is separate from the commercial RC tag and must not move RC evidence.",
            "Feishu live evidence proves inbound encrypted event delivery only; outbound send remains owner-gated.",
            "Runtime reports under .xagent_runtime are generated evidence and are not staged by default.",
        ],
    )


def write_report(report: HandoffStatusReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-pilot-commit-sha")
    parser.add_argument("--pilot-tag-name", required=True)
    parser.add_argument("--expected-rc-commit-sha")
    parser.add_argument("--rc-tag-name", required=True)
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--github-actions-run-url")
    parser.add_argument("--github-actions-head-sha")
    parser.add_argument("--rc-delivery-report", type=Path, default=DEFAULT_RC_DELIVERY_REPORT)
    parser.add_argument("--feishu-live-report", type=Path, default=DEFAULT_FEISHU_LIVE_REPORT)
    parser.add_argument("--pilot-readiness-report", type=Path, default=DEFAULT_PILOT_READINESS_REPORT)
    parser.add_argument("--refresh-chain-report", type=Path, default=DEFAULT_REFRESH_CHAIN_REPORT)
    parser.add_argument("--pilot-channel", default="feishu")
    parser.add_argument("--require-pilot-head", action="store_true")
    parser.add_argument("--require-remote-head", action="store_true")
    parser.add_argument("--fetch-github", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_handoff_status_report(
        expected_pilot_commit_sha=args.expected_pilot_commit_sha,
        pilot_tag_name=args.pilot_tag_name,
        expected_rc_commit_sha=args.expected_rc_commit_sha,
        rc_tag_name=args.rc_tag_name,
        remote=args.remote,
        branch=args.branch,
        github_actions_run_url=args.github_actions_run_url,
        github_actions_head_sha=args.github_actions_head_sha,
        rc_delivery_report_path=args.rc_delivery_report,
        feishu_live_report_path=args.feishu_live_report,
        pilot_readiness_report_path=args.pilot_readiness_report,
        refresh_chain_report_path=args.refresh_chain_report,
        pilot_channel=args.pilot_channel,
        require_pilot_head=args.require_pilot_head,
        require_remote_head=args.require_remote_head,
        fetch_github=args.fetch_github,
    )
    write_report(report, args.output)
    print(f"Commercial pilot handoff status: {report.status}")
    print(f"Expected pilot commit SHA: {report.expected_pilot_commit_sha or '<unresolved>'}")
    print(f"Pilot tag: {report.pilot_tag_name}")
    print(f"Expected RC commit SHA: {report.expected_rc_commit_sha or '<unresolved>'}")
    print(f"RC tag: {report.rc_tag_name}")
    print(f"Branch: {report.remote}/{report.branch}")
    if report.github_actions_run_url:
        print(f"Hosted GitHub Actions run: {report.github_actions_run_url}")
    if report.github_actions_head_sha:
        print(f"Hosted GitHub Actions head SHA: {report.github_actions_head_sha}")
    print(f"Report written to {args.output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "pilot_handoff_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
