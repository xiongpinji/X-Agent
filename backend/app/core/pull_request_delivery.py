from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import quote_plus

from pydantic import BaseModel, Field

PullRequestProvider = Literal["github", "gitlab", "gitee"]
ProviderSelection = PullRequestProvider | Literal["auto"]
DeliveryStatus = Literal["blocked", "planned", "created"]


class PullRequestDeliveryIssue(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "error"


class PullRequestCommandResult(BaseModel):
    args: list[str]
    cwd: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""


class PullRequestApiResponse(BaseModel):
    status_code: int
    body: dict[str, Any] = Field(default_factory=dict)
    text: str = ""


class PullRequestDeliveryRequest(BaseModel):
    workspace_path: str
    title: str
    body: str = ""
    provider: ProviderSelection = "auto"
    remote: str = "origin"
    source_branch: str = ""
    target_branch: str = "main"
    draft: bool = False
    dry_run: bool = True
    token: str = ""


class PullRequestRemote(BaseModel):
    provider: PullRequestProvider
    owner: str
    repo: str
    remote_url: str
    web_url: str


class PullRequestDeliveryPlan(BaseModel):
    status: DeliveryStatus = "planned"
    dry_run: bool = True
    provider: PullRequestProvider | None = None
    remote: PullRequestRemote | None = None
    workspace_path: str
    source_branch: str = ""
    target_branch: str = "main"
    title: str
    body: str = ""
    draft: bool = False
    remote_name: str = "origin"
    push_command: list[str] = Field(default_factory=list)
    api_method: str = "POST"
    api_url: str = ""
    api_payload: dict[str, Any] = Field(default_factory=dict)
    token_env_candidates: list[str] = Field(default_factory=list)
    credential_present: bool = False
    issues: list[PullRequestDeliveryIssue] = Field(default_factory=list)


class PullRequestDeliveryResult(BaseModel):
    status: DeliveryStatus
    dry_run: bool
    plan: PullRequestDeliveryPlan
    pr_url: str = ""
    provider_response: dict[str, Any] = Field(default_factory=dict)
    commands: list[PullRequestCommandResult] = Field(default_factory=list)
    issues: list[PullRequestDeliveryIssue] = Field(default_factory=list)


class PullRequestCommandRunner(Protocol):
    def run(self, args: list[str], *, cwd: str) -> PullRequestCommandResult:
        ...


class PullRequestHttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> PullRequestApiResponse:
        ...


class SubprocessPullRequestCommandRunner:
    def run(self, args: list[str], *, cwd: str) -> PullRequestCommandResult:
        completed = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        return PullRequestCommandResult(
            args=args,
            cwd=cwd,
            exit_code=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )


class UrlLibPullRequestHttpClient:
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> PullRequestApiResponse:
        import json as json_module
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        data = json_module.dumps(json).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                text = response.read().decode("utf-8")
                body = json_module.loads(text) if text else {}
                return PullRequestApiResponse(
                    status_code=response.status,
                    body=body,
                    text=text,
                )
        except HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            try:
                body = json_module.loads(text) if text else {}
            except ValueError:
                body = {}
            return PullRequestApiResponse(status_code=exc.code, body=body, text=text)


def plan_pull_request_delivery(
    request: PullRequestDeliveryRequest,
    *,
    runner: PullRequestCommandRunner | None = None,
    environ: dict[str, str] | None = None,
) -> PullRequestDeliveryPlan:
    workspace = Path(request.workspace_path).resolve()
    runner = runner or SubprocessPullRequestCommandRunner()
    environ = environ if environ is not None else dict(os.environ)
    issues: list[PullRequestDeliveryIssue] = []

    if not workspace.exists() or not workspace.is_dir():
        issues.append(
            PullRequestDeliveryIssue(
                code="workspace_missing",
                message="Workspace path must exist before PR delivery planning.",
            )
        )

    remote_result = _run_git(runner, ["git", "remote", "get-url", request.remote], cwd=str(workspace))
    if remote_result.exit_code != 0 or not remote_result.stdout:
        issues.append(
            PullRequestDeliveryIssue(
                code="remote_missing",
                message=f"Git remote '{request.remote}' is required for PR delivery.",
            )
        )
        remote_url = ""
    else:
        remote_url = remote_result.stdout.strip()

    source_branch = request.source_branch.strip()
    if not source_branch:
        branch_result = _run_git(
            runner,
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(workspace),
        )
        if branch_result.exit_code == 0 and branch_result.stdout:
            source_branch = branch_result.stdout.strip()
        else:
            issues.append(
                PullRequestDeliveryIssue(
                    code="source_branch_missing",
                    message="Source branch is required and could not be inferred from git.",
                )
            )

    remote = _parse_remote(remote_url, request.provider) if remote_url else None
    if remote is None and remote_url:
        issues.append(
            PullRequestDeliveryIssue(
                code="provider_unsupported",
                message="Remote URL must be a supported GitHub, GitLab, or Gitee repository.",
            )
        )

    token_candidates = _token_env_candidates(remote.provider if remote else request.provider)
    credential_present = bool(request.token) or any(environ.get(name) for name in token_candidates)
    if remote and not credential_present:
        issues.append(
            PullRequestDeliveryIssue(
                code="credential_missing",
                message=f"{remote.provider} credentials are required before execute.",
                severity="warning",
            )
        )

    push_command = ["git", "push", "-u", request.remote, source_branch] if source_branch else []
    api_url = _api_url(remote) if remote else ""
    api_payload = (
        _api_payload(
            remote.provider,
            source_branch=source_branch,
            target_branch=request.target_branch,
            title=request.title,
            body=request.body,
            draft=request.draft,
        )
        if remote and source_branch
        else {}
    )

    blocking_errors = [issue for issue in issues if issue.severity == "error"]
    return PullRequestDeliveryPlan(
        status="blocked" if blocking_errors else "planned",
        dry_run=True,
        provider=remote.provider if remote else None,
        remote=remote,
        workspace_path=str(workspace),
        source_branch=source_branch,
        target_branch=request.target_branch,
        title=request.title,
        body=request.body,
        draft=request.draft,
        remote_name=request.remote,
        push_command=push_command,
        api_url=api_url,
        api_payload=api_payload,
        token_env_candidates=token_candidates,
        credential_present=credential_present,
        issues=issues,
    )


def create_pull_request_delivery(
    request: PullRequestDeliveryRequest,
    *,
    execute: bool = False,
    runner: PullRequestCommandRunner | None = None,
    http_client: PullRequestHttpClient | None = None,
    environ: dict[str, str] | None = None,
) -> PullRequestDeliveryResult:
    runner = runner or SubprocessPullRequestCommandRunner()
    environ = environ if environ is not None else dict(os.environ)
    plan = plan_pull_request_delivery(request, runner=runner, environ=environ)
    issues = list(plan.issues)
    commands: list[PullRequestCommandResult] = []

    if request.dry_run or not execute:
        return PullRequestDeliveryResult(
            status=plan.status,
            dry_run=True,
            plan=plan,
            issues=issues,
        )

    if plan.status == "blocked":
        return PullRequestDeliveryResult(
            status="blocked",
            dry_run=False,
            plan=plan,
            issues=issues,
        )

    if not plan.push_command or not plan.api_url or plan.provider is None:
        issues.append(
            PullRequestDeliveryIssue(
                code="plan_incomplete",
                message="PR delivery plan is incomplete and cannot be executed.",
            )
        )
        return PullRequestDeliveryResult(
            status="blocked",
            dry_run=False,
            plan=plan,
            issues=issues,
        )

    token = _resolve_token(request, plan, environ)
    if not token:
        issues = [issue for issue in issues if issue.code != "credential_missing"]
        issues.append(
            PullRequestDeliveryIssue(
                code="credential_missing",
                message="Credentials are required for explicit PR delivery execute.",
            )
        )
        return PullRequestDeliveryResult(status="blocked", dry_run=False, plan=plan, issues=issues)

    push_result = runner.run(plan.push_command, cwd=plan.workspace_path)
    commands.append(push_result)
    if push_result.exit_code != 0:
        issues.append(
            PullRequestDeliveryIssue(
                code="push_failed",
                message=push_result.stderr or "Git push failed before PR creation.",
            )
        )
        return PullRequestDeliveryResult(
            status="blocked",
            dry_run=False,
            plan=plan,
            commands=commands,
            issues=issues,
        )

    http_client = http_client or UrlLibPullRequestHttpClient()
    response = http_client.post(
        plan.api_url,
        headers=_auth_headers(plan.provider, token),
        json=_payload_with_provider_token(plan.provider, plan.api_payload, token),
    )
    if response.status_code < 200 or response.status_code >= 300:
        issues.append(
            PullRequestDeliveryIssue(
                code="provider_request_failed",
                message=response.text or f"Provider returned HTTP {response.status_code}.",
            )
        )
        return PullRequestDeliveryResult(
            status="blocked",
            dry_run=False,
            plan=plan,
            provider_response=response.body,
            commands=commands,
            issues=issues,
        )

    return PullRequestDeliveryResult(
        status="created",
        dry_run=False,
        plan=plan,
        pr_url=_response_url(plan.provider, response.body),
        provider_response=response.body,
        commands=commands,
        issues=issues,
    )


def _run_git(
    runner: PullRequestCommandRunner,
    args: list[str],
    *,
    cwd: str,
) -> PullRequestCommandResult:
    try:
        return runner.run(args, cwd=cwd)
    except OSError as exc:
        return PullRequestCommandResult(args=args, cwd=cwd, exit_code=1, stderr=str(exc))


def _parse_remote(remote_url: str, provider: ProviderSelection) -> PullRequestRemote | None:
    normalized = remote_url.strip()
    match = re.search(
        r"(?:https://|git@)(github\.com|gitlab\.com|gitee\.com)[:/](?P<owner>[^/]+)/(?P<repo>[^/\s]+?)(?:\.git)?$",
        normalized,
    )
    if not match:
        return None

    host = match.group(1)
    inferred_provider: PullRequestProvider = {
        "github.com": "github",
        "gitlab.com": "gitlab",
        "gitee.com": "gitee",
    }[host]
    if provider != "auto" and provider != inferred_provider:
        return None

    owner = match.group("owner")
    repo = match.group("repo")
    return PullRequestRemote(
        provider=inferred_provider,
        owner=owner,
        repo=repo,
        remote_url=normalized,
        web_url=f"https://{host}/{owner}/{repo}",
    )


def _token_env_candidates(provider: ProviderSelection) -> list[str]:
    if provider == "github":
        return ["GITHUB_TOKEN", "GH_TOKEN"]
    if provider == "gitlab":
        return ["GITLAB_TOKEN"]
    if provider == "gitee":
        return ["GITEE_TOKEN"]
    return ["GITHUB_TOKEN", "GH_TOKEN", "GITLAB_TOKEN", "GITEE_TOKEN"]


def _api_url(remote: PullRequestRemote) -> str:
    if remote.provider == "github":
        return f"https://api.github.com/repos/{remote.owner}/{remote.repo}/pulls"
    if remote.provider == "gitlab":
        project = quote_plus(f"{remote.owner}/{remote.repo}")
        return f"https://gitlab.com/api/v4/projects/{project}/merge_requests"
    return f"https://gitee.com/api/v5/repos/{remote.owner}/{remote.repo}/pulls"


def _api_payload(
    provider: PullRequestProvider,
    *,
    source_branch: str,
    target_branch: str,
    title: str,
    body: str,
    draft: bool,
) -> dict[str, Any]:
    if provider == "github":
        return {
            "title": title,
            "head": source_branch,
            "base": target_branch,
            "body": body,
            "draft": draft,
        }
    if provider == "gitlab":
        return {
            "title": title,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "description": body,
        }
    return {
        "title": title,
        "head": source_branch,
        "base": target_branch,
        "body": body,
    }


def _resolve_token(
    request: PullRequestDeliveryRequest,
    plan: PullRequestDeliveryPlan,
    environ: dict[str, str],
) -> str:
    if request.token:
        return request.token
    for name in plan.token_env_candidates:
        token = environ.get(name, "")
        if token:
            return token
    return ""


def _auth_headers(provider: PullRequestProvider, token: str) -> dict[str, str]:
    if provider == "github":
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
        }
    if provider == "gitlab":
        return {"PRIVATE-TOKEN": token}
    return {}


def _payload_with_provider_token(
    provider: PullRequestProvider,
    payload: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    if provider == "gitee":
        return {**payload, "access_token": token}
    return payload


def _response_url(provider: PullRequestProvider, body: dict[str, Any]) -> str:
    if provider == "github":
        return str(body.get("html_url", ""))
    if provider == "gitlab":
        return str(body.get("web_url", ""))
    return str(body.get("html_url") or body.get("url") or "")
