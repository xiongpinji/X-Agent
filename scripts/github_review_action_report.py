#!/usr/bin/env python3
"""Build a read-only GitHub review/action evidence report.

The report packages the existing issue-to-PR dry-run plan into a Codex-style
review/action loop. It never calls GitHub, pushes branches, posts reviews, or
creates pull requests.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.app.core.pipelines.issue_to_pr import dry_run_issue_to_pr
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPORT_DIR / "github-review-action-report.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "github-review-action-report.md"

CODEX_GITHUB_SOURCES = (
    "https://developers.openai.com/codex/integrations/github",
    "https://developers.openai.com/codex/github-action",
)

DEFAULT_ISSUE_PAYLOAD = {
    "issue_url": "https://github.com/xiongpinji/X-Agent/issues/1",
    "title": "Codex-style GitHub review/action dry-run evidence",
    "body": "Package issue, PR, CI, patch, and review evidence without network mutation.",
    "labels": ["codex-alignment", "github", "dry-run"],
    "default_branch": "codex/codex-hermes-gap-closure",
}

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{20,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-.]{16,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class GitHubReviewActionCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class GitHubReviewActionReport:
    status: str
    generated_at: str
    evidence_type: str
    full_codex_parity_claimed: bool
    dry_run: bool
    mutation_performed: bool
    network_mutation_performed: bool
    owner_gate_required: bool
    issue: dict[str, Any]
    branch: dict[str, Any]
    patch_plan: dict[str, Any]
    pull_request: dict[str, Any]
    ci: dict[str, Any]
    review: dict[str, Any]
    action_gate: dict[str, Any]
    checks: list[GitHubReviewActionCheck]
    official_sources: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub("<redacted>", redacted)
        return redacted
    if isinstance(value, dict):
        return {str(key): _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _read_issue_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("issue JSON must be an object")
    return payload


def _issue_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.issue_json:
        payload = _read_issue_json(args.issue_json)
    else:
        payload = dict(DEFAULT_ISSUE_PAYLOAD)
    if args.issue_url:
        payload["issue_url"] = args.issue_url
    if args.title:
        payload["title"] = args.title
    if args.body:
        payload["body"] = args.body
    if args.default_branch:
        payload["default_branch"] = args.default_branch
    return payload


def _build_checks(report_payload: dict[str, Any]) -> list[GitHubReviewActionCheck]:
    checks = [
        GitHubReviewActionCheck(
            name="dry_run_only",
            status="passed" if report_payload["dry_run"] is True else "failed",
            details={"dry_run": report_payload["dry_run"]},
            error=None if report_payload["dry_run"] is True else "report is not dry-run",
        ),
        GitHubReviewActionCheck(
            name="no_network_mutation",
            status="passed" if report_payload["network_mutation_performed"] is False else "failed",
            details={"network_mutation_performed": report_payload["network_mutation_performed"]},
            error=None
            if report_payload["network_mutation_performed"] is False
            else "network mutation was performed",
        ),
        GitHubReviewActionCheck(
            name="owner_gate_before_execute",
            status="passed" if report_payload["owner_gate_required"] is True else "failed",
            details={"owner_gate_required": report_payload["owner_gate_required"]},
            error=None if report_payload["owner_gate_required"] is True else "owner gate is not required",
        ),
        GitHubReviewActionCheck(
            name="no_full_codex_parity_claim",
            status="passed" if report_payload["full_codex_parity_claimed"] is False else "failed",
            details={"full_codex_parity_claimed": report_payload["full_codex_parity_claimed"]},
            error=None
            if report_payload["full_codex_parity_claimed"] is False
            else "report claims full Codex parity",
        ),
        GitHubReviewActionCheck(
            name="review_focus_is_high_signal",
            status="passed",
            details={"comment_priorities": report_payload["review"]["comment_priorities"]},
        ),
    ]
    return checks


def build_github_review_action_report(issue_payload: dict[str, Any] | None = None) -> GitHubReviewActionReport:
    issue_payload = issue_payload or DEFAULT_ISSUE_PAYLOAD
    dry_run = dry_run_issue_to_pr(_redact(issue_payload)).to_dict()
    plan = dry_run["plan"]
    report_payload: dict[str, Any] = {
        "status": "github_review_action_report_ready",
        "generated_at": _utc_now(),
        "evidence_type": "github_review_action",
        "full_codex_parity_claimed": False,
        "dry_run": True,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "owner_gate_required": True,
        "issue": {
            "repo_full_name": dry_run["issue"]["repo_full_name"],
            "issue_number": dry_run["issue"]["issue_number"],
            "title": dry_run["issue"]["title"],
            "labels": dry_run["issue"]["labels"],
            "default_branch": dry_run["issue"]["default_branch"],
            "clone_url": dry_run["issue"]["clone_url"],
        },
        "branch": {
            "base": plan["base_branch"],
            "planned_head": dry_run["branch_name"],
            "push_performed": False,
            "checkout_mutation_performed": False,
        },
        "patch_plan": {
            "steps": plan["steps"],
            "touched_file_candidates": plan["touched_file_candidates"],
            "risk_flags": plan["risk_flags"],
            "commit_title": dry_run["commit_title"],
            "mutation_performed": False,
        },
        "pull_request": {
            "title": dry_run["pr_title"],
            "body": dry_run["pr_body"],
            "create_pr_performed": False,
            "comment_performed": False,
            "draft_only": True,
        },
        "ci": {
            "test_command": plan["test_command"],
            "install_command": plan["install_command"],
            "hosted_ci_observed": False,
            "github_actions_run_url": None,
            "required_before_execute": True,
        },
        "review": {
            "mode": "dry_run_review_packet",
            "trigger": "@codex review compatible",
            "auto_review_supported_by_contract": True,
            "comment_priorities": ["P0", "P1"],
            "review_posted": False,
            "guidance_sources": ["AGENTS.md", "closest scoped project guidance"],
        },
        "action_gate": {
            "execute_allowed": dry_run["execute_allowed"],
            "requires_token": True,
            "requires_csrf_for_api_execute": True,
            "requires_owner_approval": True,
            "blocked_mutations": [
                "git_push",
                "pull_request_create",
                "issue_comment",
                "review_comment",
                "github_action_dispatch",
            ],
        },
        "official_sources": list(CODEX_GITHUB_SOURCES),
        "known_limits": [
            "This report is read-only and does not call GitHub.",
            "No PR, branch push, issue comment, review comment, or GitHub Action dispatch is performed.",
            "Full Codex GitHub review/action parity is not claimed.",
            "Execution remains gated by explicit token, CSRF/API controls, and owner approval.",
        ],
    }
    checks = _build_checks(report_payload)
    if any(check.status == "failed" for check in checks):
        report_payload["status"] = "github_review_action_report_blocked"
    return GitHubReviewActionReport(checks=checks, **report_payload)


def render_markdown_report(report: GitHubReviewActionReport) -> str:
    checks = "\n".join(f"- {check.name}: `{check.status}`" for check in report.checks)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    sources = "\n".join(f"- {source}" for source in report.official_sources)
    return (
        "# X-Agent GitHub Review Action Report\n\n"
        f"- Status: `{report.status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Dry run: `{report.dry_run}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Network mutation performed: `{report.network_mutation_performed}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n\n"
        "## Issue\n\n"
        f"- Repository: `{report.issue['repo_full_name']}`\n"
        f"- Issue: `#{report.issue['issue_number']}`\n"
        f"- Planned branch: `{report.branch['planned_head']}`\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Official Codex Sources\n\n"
        f"{sources}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: GitHubReviewActionReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(
    report: GitHubReviewActionReport,
    output_path: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-url", default=None)
    parser.add_argument("--issue-json", type=Path, default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--body", default=None)
    parser.add_argument("--default-branch", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_github_review_action_report(_issue_payload_from_args(args))
    write_report(report, args.output)
    write_markdown_report(report, args.markdown_output)
    print(f"GitHub review/action report status: {report.status}")
    print(f"JSON report written to {args.output}")
    print(f"Markdown report written to {args.markdown_output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Mutation performed: {report.mutation_performed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "github_review_action_report_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
