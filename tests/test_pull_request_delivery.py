from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.core.pull_request_delivery import (
    PullRequestApiResponse,
    PullRequestCommandResult,
    PullRequestDeliveryRequest,
    create_pull_request_delivery,
    plan_pull_request_delivery,
)


class FakeRunner:
    def __init__(
        self,
        *,
        remote_url: str = "https://github.com/acme/widget.git",
        branch: str = "feature/pr-delivery",
        push_exit_code: int = 0,
    ) -> None:
        self.remote_url = remote_url
        self.branch = branch
        self.push_exit_code = push_exit_code
        self.calls: list[tuple[list[str], str]] = []

    def run(self, args: list[str], *, cwd: str) -> PullRequestCommandResult:
        self.calls.append((args, cwd))
        if args[:3] == ["git", "remote", "get-url"]:
            if not self.remote_url:
                return PullRequestCommandResult(args=args, cwd=cwd, exit_code=2, stderr="missing")
            return PullRequestCommandResult(args=args, cwd=cwd, exit_code=0, stdout=self.remote_url)
        if args == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return PullRequestCommandResult(args=args, cwd=cwd, exit_code=0, stdout=self.branch)
        if args[:3] == ["git", "push", "-u"]:
            return PullRequestCommandResult(
                args=args,
                cwd=cwd,
                exit_code=self.push_exit_code,
                stderr="push rejected" if self.push_exit_code else "",
            )
        return PullRequestCommandResult(args=args, cwd=cwd, exit_code=1, stderr="unexpected")


class FakeHttpClient:
    def __init__(self, response: PullRequestApiResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> PullRequestApiResponse:
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.response


def request_for(tmp_path: Path, **overrides: Any) -> PullRequestDeliveryRequest:
    values = {
        "workspace_path": str(tmp_path),
        "title": "Ship PR delivery",
        "body": "Dry-run first, execute explicitly.",
        "target_branch": "main",
    }
    values.update(overrides)
    return PullRequestDeliveryRequest(**values)


def test_dry_run_is_default_and_does_not_push_or_call_provider(tmp_path: Path) -> None:
    runner = FakeRunner()
    http = FakeHttpClient(PullRequestApiResponse(status_code=201, body={"html_url": "created"}))

    result = create_pull_request_delivery(
        request_for(tmp_path),
        execute=True,
        runner=runner,
        http_client=http,
        environ={"GITHUB_TOKEN": "secret"},
    )

    assert result.dry_run is True
    assert result.status == "planned"
    assert result.plan.push_command == ["git", "push", "-u", "origin", "feature/pr-delivery"]
    assert result.plan.api_url == "https://api.github.com/repos/acme/widget/pulls"
    assert [call[0] for call in runner.calls] == [
        ["git", "remote", "get-url", "origin"],
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    ]
    assert http.calls == []


def test_plan_blocks_when_remote_is_absent(tmp_path: Path) -> None:
    result = create_pull_request_delivery(
        request_for(tmp_path),
        execute=False,
        runner=FakeRunner(remote_url=""),
        environ={"GITHUB_TOKEN": "secret"},
    )

    assert result.status == "blocked"
    assert result.dry_run is True
    assert [issue.code for issue in result.issues] == ["remote_missing"]


def test_plan_blocks_when_remote_provider_is_unsupported(tmp_path: Path) -> None:
    result = create_pull_request_delivery(
        request_for(tmp_path),
        execute=False,
        runner=FakeRunner(remote_url="https://example.com/acme/widget.git"),
        environ={"GITHUB_TOKEN": "secret"},
    )

    assert result.status == "blocked"
    assert result.dry_run is True
    assert [issue.code for issue in result.issues] == ["provider_unsupported"]
    assert result.plan.api_url == ""
    assert result.plan.push_command == ["git", "push", "-u", "origin", "feature/pr-delivery"]


def test_dry_run_plan_warns_without_credentials_but_remains_reviewable(tmp_path: Path) -> None:
    result = create_pull_request_delivery(
        request_for(tmp_path),
        execute=False,
        runner=FakeRunner(),
        environ={},
    )

    assert result.status == "planned"
    assert result.dry_run is True
    assert [(issue.code, issue.severity) for issue in result.issues] == [
        ("credential_missing", "warning")
    ]
    assert result.plan.api_payload["head"] == "feature/pr-delivery"


def test_execute_blocks_without_credentials(tmp_path: Path) -> None:
    result = create_pull_request_delivery(
        request_for(tmp_path, dry_run=False),
        execute=True,
        runner=FakeRunner(),
        environ={},
    )

    assert result.status == "blocked"
    assert result.dry_run is False
    assert [(issue.code, issue.severity) for issue in result.issues] == [
        ("credential_missing", "error")
    ]
    assert result.commands == []


def test_execute_creates_github_pull_request_with_injected_http_client(tmp_path: Path) -> None:
    runner = FakeRunner()
    http = FakeHttpClient(
        PullRequestApiResponse(
            status_code=201,
            body={"html_url": "https://github.com/acme/widget/pull/7"},
        )
    )

    result = create_pull_request_delivery(
        request_for(tmp_path, dry_run=False, draft=True),
        execute=True,
        runner=runner,
        http_client=http,
        environ={"GITHUB_TOKEN": "secret"},
    )

    assert result.status == "created"
    assert result.pr_url == "https://github.com/acme/widget/pull/7"
    assert result.commands[0].args == ["git", "push", "-u", "origin", "feature/pr-delivery"]
    assert http.calls == [
        {
            "url": "https://api.github.com/repos/acme/widget/pulls",
            "headers": {
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer secret",
            },
            "json": {
                "title": "Ship PR delivery",
                "head": "feature/pr-delivery",
                "base": "main",
                "body": "Dry-run first, execute explicitly.",
                "draft": True,
            },
        }
    ]


def test_execute_blocks_when_push_fails_before_provider_call(tmp_path: Path) -> None:
    http = FakeHttpClient(PullRequestApiResponse(status_code=201, body={"html_url": "created"}))

    result = create_pull_request_delivery(
        request_for(tmp_path, dry_run=False),
        execute=True,
        runner=FakeRunner(push_exit_code=1),
        http_client=http,
        environ={"GITHUB_TOKEN": "secret"},
    )

    assert result.status == "blocked"
    assert [issue.code for issue in result.issues] == ["push_failed"]
    assert result.commands[0].stderr == "push rejected"
    assert http.calls == []


def test_gitlab_plan_uses_merge_request_endpoint_and_payload(tmp_path: Path) -> None:
    plan = plan_pull_request_delivery(
        request_for(tmp_path, provider="gitlab", target_branch="develop"),
        runner=FakeRunner(remote_url="git@gitlab.com:acme/widget.git", branch="feature/gitlab"),
        environ={"GITLAB_TOKEN": "secret"},
    )

    assert plan.status == "planned"
    assert plan.provider == "gitlab"
    assert plan.api_url == "https://gitlab.com/api/v4/projects/acme%2Fwidget/merge_requests"
    assert plan.api_payload == {
        "title": "Ship PR delivery",
        "source_branch": "feature/gitlab",
        "target_branch": "develop",
        "description": "Dry-run first, execute explicitly.",
    }


def test_gitee_execute_sends_access_token_in_payload(tmp_path: Path) -> None:
    http = FakeHttpClient(
        PullRequestApiResponse(
            status_code=201,
            body={"html_url": "https://gitee.com/acme/widget/pulls/3"},
        )
    )

    result = create_pull_request_delivery(
        request_for(tmp_path, provider="gitee", dry_run=False),
        execute=True,
        runner=FakeRunner(remote_url="https://gitee.com/acme/widget.git", branch="feature/gitee"),
        http_client=http,
        environ={"GITEE_TOKEN": "secret"},
    )

    assert result.status == "created"
    assert result.pr_url == "https://gitee.com/acme/widget/pulls/3"
    assert http.calls[0]["url"] == "https://gitee.com/api/v5/repos/acme/widget/pulls"
    assert http.calls[0]["headers"] == {}
    assert http.calls[0]["json"] == {
        "title": "Ship PR delivery",
        "head": "feature/gitee",
        "base": "main",
        "body": "Dry-run first, execute explicitly.",
        "access_token": "secret",
    }
