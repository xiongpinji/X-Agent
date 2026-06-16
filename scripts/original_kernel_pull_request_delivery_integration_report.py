#!/usr/bin/env python3
"""Validate the original-kernel pull request delivery contract.

This module-level probe uses fake git and HTTP adapters to verify dry-run
planning, execute guards, provider payloads, and unsupported remote blocking.
It never pushes a branch, calls a provider API, or creates a real pull request.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.pull_request_delivery import (
    PullRequestApiResponse,
    PullRequestCommandResult,
    PullRequestDeliveryRequest,
    create_pull_request_delivery,
    plan_pull_request_delivery,
)
from backend.app.core.storage import atomic_write_json

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "original-kernel-pull-request-delivery-integration.json"


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class _FakeRunner:
    def __init__(
        self,
        *,
        remote_url: str = "https://github.com/acme/widget.git",
        branch: str = "feature/original-kernel-delivery",
    ) -> None:
        self.remote_url = remote_url
        self.branch = branch
        self.calls: list[tuple[list[str], str]] = []
        self.push_attempted = False

    def run(self, args: list[str], *, cwd: str) -> PullRequestCommandResult:
        self.calls.append((args, cwd))
        if args[:3] == ["git", "remote", "get-url"]:
            if not self.remote_url:
                return PullRequestCommandResult(args=args, cwd=cwd, exit_code=2, stderr="missing")
            return PullRequestCommandResult(args=args, cwd=cwd, exit_code=0, stdout=self.remote_url)
        if args == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return PullRequestCommandResult(args=args, cwd=cwd, exit_code=0, stdout=self.branch)
        if args[:3] == ["git", "push", "-u"]:
            self.push_attempted = True
            return PullRequestCommandResult(args=args, cwd=cwd, exit_code=1, stderr="push should not run")
        return PullRequestCommandResult(args=args, cwd=cwd, exit_code=1, stderr="unexpected fake runner command")


class _FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> PullRequestApiResponse:
        self.calls.append({"url": url, "headers": headers, "json": json})
        return PullRequestApiResponse(status_code=201, body={"html_url": "https://example.invalid/pull/1"})


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _request(workspace: Path, **overrides: Any) -> PullRequestDeliveryRequest:
    values: dict[str, Any] = {
        "workspace_path": str(workspace),
        "title": "Original kernel delivery contract",
        "body": "Dry-run first; explicit execute required.",
        "target_branch": "main",
    }
    values.update(overrides)
    return PullRequestDeliveryRequest(**values)


def _dry_run_default_check(workspace: Path) -> IntegrationCheck:
    runner = _FakeRunner()
    http = _FakeHttpClient()
    result = create_pull_request_delivery(
        _request(workspace),
        execute=True,
        runner=runner,
        http_client=http,
        environ={"GITHUB_TOKEN": "secret"},
    )

    expected_git_reads = [
        ["git", "remote", "get-url", "origin"],
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    ]
    passed = all(
        [
            result.status == "planned",
            result.dry_run is True,
            result.commands == [],
            http.calls == [],
            runner.push_attempted is False,
            [call[0] for call in runner.calls] == expected_git_reads,
            result.plan.provider == "github",
            result.plan.api_url == "https://api.github.com/repos/acme/widget/pulls",
            result.plan.push_command == [
                "git",
                "push",
                "-u",
                "origin",
                "feature/original-kernel-delivery",
            ],
        ]
    )
    return IntegrationCheck(
        name="dry_run_default_contract",
        status="passed" if passed else "failed",
        details={
            "result_status": result.status,
            "result_dry_run": result.dry_run,
            "provider": result.plan.provider,
            "api_url": result.plan.api_url,
            "runner_call_count": len(runner.calls),
            "push_attempted": runner.push_attempted,
            "http_call_count": len(http.calls),
            "command_result_count": len(result.commands),
        },
        error=None if passed else "dry-run default did not prevent push/provider calls",
    )


def _explicit_execute_guard_check(workspace: Path) -> IntegrationCheck:
    no_execute_runner = _FakeRunner()
    no_execute_http = _FakeHttpClient()
    no_execute = create_pull_request_delivery(
        _request(workspace, dry_run=False),
        execute=False,
        runner=no_execute_runner,
        http_client=no_execute_http,
        environ={"GITHUB_TOKEN": "secret"},
    )

    no_credentials_runner = _FakeRunner()
    no_credentials_http = _FakeHttpClient()
    no_credentials = create_pull_request_delivery(
        _request(workspace, dry_run=False),
        execute=True,
        runner=no_credentials_runner,
        http_client=no_credentials_http,
        environ={},
    )
    issue_codes = [issue.code for issue in no_credentials.issues]

    passed = all(
        [
            no_execute.status == "planned",
            no_execute.dry_run is True,
            no_execute.commands == [],
            no_execute_runner.push_attempted is False,
            no_execute_http.calls == [],
            no_credentials.status == "blocked",
            no_credentials.dry_run is False,
            issue_codes == ["credential_missing"],
            no_credentials.commands == [],
            no_credentials_runner.push_attempted is False,
            no_credentials_http.calls == [],
        ]
    )
    return IntegrationCheck(
        name="explicit_execute_guard_contract",
        status="passed" if passed else "failed",
        details={
            "execute_false_result_status": no_execute.status,
            "execute_false_dry_run": no_execute.dry_run,
            "execute_false_push_attempted": no_execute_runner.push_attempted,
            "execute_false_http_call_count": len(no_execute_http.calls),
            "missing_credentials_status": no_credentials.status,
            "missing_credentials_issues": issue_codes,
            "missing_credentials_push_attempted": no_credentials_runner.push_attempted,
            "missing_credentials_http_call_count": len(no_credentials_http.calls),
        },
        error=None if passed else "explicit execute guard allowed mutation without required boundary or credentials",
    )


def _provider_plan_check(workspace: Path) -> IntegrationCheck:
    gitlab_plan = plan_pull_request_delivery(
        _request(workspace, provider="gitlab", target_branch="develop"),
        runner=_FakeRunner(remote_url="git@gitlab.com:acme/widget.git", branch="feature/gitlab"),
        environ={"GITLAB_TOKEN": "secret"},
    )
    gitee_plan = plan_pull_request_delivery(
        _request(workspace, provider="gitee"),
        runner=_FakeRunner(remote_url="https://gitee.com/acme/widget.git", branch="feature/gitee"),
        environ={"GITEE_TOKEN": "secret"},
    )

    passed = all(
        [
            gitlab_plan.status == "planned",
            gitlab_plan.provider == "gitlab",
            gitlab_plan.api_url == "https://gitlab.com/api/v4/projects/acme%2Fwidget/merge_requests",
            gitlab_plan.api_payload.get("source_branch") == "feature/gitlab",
            gitlab_plan.api_payload.get("target_branch") == "develop",
            gitee_plan.status == "planned",
            gitee_plan.provider == "gitee",
            gitee_plan.api_url == "https://gitee.com/api/v5/repos/acme/widget/pulls",
            gitee_plan.api_payload.get("head") == "feature/gitee",
            gitee_plan.api_payload.get("base") == "main",
        ]
    )
    return IntegrationCheck(
        name="provider_plan_contract",
        status="passed" if passed else "failed",
        details={
            "gitlab_status": gitlab_plan.status,
            "gitlab_api_url": gitlab_plan.api_url,
            "gitlab_payload_keys": sorted(gitlab_plan.api_payload),
            "gitee_status": gitee_plan.status,
            "gitee_api_url": gitee_plan.api_url,
            "gitee_payload_keys": sorted(gitee_plan.api_payload),
        },
        error=None if passed else "provider planning did not build expected GitLab/Gitee endpoints or payloads",
    )


def _unsupported_remote_check(workspace: Path) -> IntegrationCheck:
    runner = _FakeRunner(remote_url="https://example.com/acme/widget.git")
    http = _FakeHttpClient()
    result = create_pull_request_delivery(
        _request(workspace),
        execute=True,
        runner=runner,
        http_client=http,
        environ={"GITHUB_TOKEN": "secret"},
    )
    issue_codes = [issue.code for issue in result.issues]

    passed = all(
        [
            result.status == "blocked",
            result.dry_run is True,
            issue_codes == ["provider_unsupported"],
            result.plan.api_url == "",
            result.commands == [],
            runner.push_attempted is False,
            http.calls == [],
        ]
    )
    return IntegrationCheck(
        name="unsupported_remote_contract",
        status="passed" if passed else "failed",
        details={
            "result_status": result.status,
            "result_dry_run": result.dry_run,
            "issue_codes": issue_codes,
            "api_url": result.plan.api_url,
            "push_attempted": runner.push_attempted,
            "http_call_count": len(http.calls),
        },
        error=None if passed else "unsupported remote was not blocked before provider execution",
    )


def build_report(*, workspace_path: str | Path = ROOT) -> dict[str, Any]:
    workspace = Path(workspace_path).resolve()
    checks = [
        _dry_run_default_check(workspace),
        _explicit_execute_guard_check(workspace),
        _provider_plan_check(workspace),
        _unsupported_remote_check(workspace),
    ]
    all_passed = all(check.status == "passed" for check in checks)

    return {
        "status": "original_kernel_pull_request_delivery_integration_ready" if all_passed else "failed",
        "generated_at": _utc_now(),
        "evidence_type": "original_kernel_pull_request_delivery_integration",
        "modules": ["pull_request_delivery"],
        "workspace_path": str(workspace),
        "entrypoints_modified": False,
        "api_router_modified": False,
        "control_plane_modified": False,
        "frontend_modified": False,
        "agent_loop_modified": False,
        "backend_core_init_modified": False,
        "mutation_performed": False,
        "report_file_written": False,
        "network_mutation_performed": False,
        "external_provider_http_performed": False,
        "git_push_performed": False,
        "real_pull_request_created": False,
        "command_execution_performed": False,
        "subprocess_execution_performed": False,
        "fake_runner_used": True,
        "fake_http_client_used": True,
        "dry_run_first_contract_verified": True,
        "explicit_execute_required": True,
        "supported_providers": ["github", "gitlab", "gitee"],
        "checks": [asdict(check) for check in checks],
        "known_limits": [
            "This report proves pull_request_delivery planning and execute-guard contracts only.",
            "Git and HTTP interactions are simulated through injected fake adapters.",
            "No git push, provider HTTP call, or real pull request creation is performed.",
            "No API router, agent loop, control plane, frontend, or backend core package entrypoint is wired by this report.",
            "No full Codex parity claim is made by this report.",
        ],
        "next_actions": [
            "After review, stage only the pull_request_delivery integration files explicitly.",
            "Use report hygiene and pytest evidence scripts as the next module-level integration slice.",
        ],
    }


def write_report(output_path: Path = DEFAULT_OUTPUT, *, workspace_path: str | Path = ROOT) -> dict[str, Any]:
    report = build_report(workspace_path=workspace_path)
    report["report_file_written"] = True
    report["report_path"] = str(output_path)
    atomic_write_json(output_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-path",
        type=Path,
        default=ROOT,
        help="Workspace path used only as the fake git command cwd.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the JSON integration evidence report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = write_report(args.output, workspace_path=args.workspace_path)

    print(f"Original kernel pull request delivery integration status: {report['status']}")
    print(f"Report written to {args.output}")
    for check in report["checks"]:
        print(f"- {check['name']}: {check['status']}")
        if check.get("error"):
            print(f"  error: {check['error']}")

    return 0 if report["status"] == "original_kernel_pull_request_delivery_integration_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
