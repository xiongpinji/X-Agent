"""Issue-to-PR pipeline — the Codex-style end-to-end flow.

    GitHub issue assigned
        -> clone repo into sandbox workspace (authenticated)
        -> create a working branch
        -> run an agent/fix step inside the isolated sandbox
        -> run tests
        -> if changes + tests pass: commit, push, open PR
        -> comment back on the issue with the PR link (or the failure reason)

The pipeline is deliberately decoupled from *how* the fix is produced: the
`fix_runner` callable receives the live sandbox + issue context and is
responsible for mutating the working tree (e.g. by invoking an AgentLoop,
or a shell command). This keeps the orchestration testable without an LLM.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from backend.app.core.git_ops import GitOperations
from backend.app.core.github_integration import GitHubAPIClient, IssueEvent
from backend.app.core.sandbox.docker_sandbox import DockerSandbox, SandboxSpec

logger = logging.getLogger(__name__)

# fix_runner(sandbox, issue, workspace) -> bool (True = produced a fix)
FixRunner = Callable[[DockerSandbox, IssueEvent, str], Awaitable[bool]]

GITHUB_ISSUE_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/issues/(?P<number>\d+)(?:[?#].*)?$"
)


@dataclass
class PipelineResult:
    """Outcome of one issue-to-PR run."""

    issue_number: int
    status: str  # "pr_opened" | "no_changes" | "tests_failed" | "fix_failed" | "error"
    pr_url: Optional[str] = None
    branch: Optional[str] = None
    test_output: str = ""
    error: Optional[str] = None
    steps: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.steps.append(msg)
        logger.info("[issue #%s] %s", self.issue_number, msg)


@dataclass
class PipelineConfig:
    """Configuration for the pipeline."""

    test_command: str = "pytest -q"
    install_command: Optional[str] = "pip install -r requirements.txt"
    base_branch_override: Optional[str] = None
    bot_name: str = "X-Agent Bot"
    bot_email: str = "bot@xagent.dev"
    sandbox_image: str = "python:3.11-slim"
    sandbox_timeout: float = 600.0
    run_tests: bool = True
    open_pr: bool = True


@dataclass
class IssueToPRPlan:
    """Deterministic plan for an issue-to-PR dry run."""

    repo_full_name: str
    issue_number: int
    title: str
    base_branch: str
    branch_name: str
    touched_file_candidates: list[str]
    steps: list[str]
    risk_flags: list[str]
    test_command: str
    install_command: str | None


@dataclass
class IssueToPRDryRunResult:
    """No-write issue-to-PR planning result."""

    status: str
    dry_run: bool
    issue: dict[str, Any]
    plan: IssueToPRPlan
    branch_name: str
    commit_title: str
    pr_title: str
    pr_body: str
    execute_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["plan"] = asdict(self.plan)
        return payload


@dataclass
class IssueToPRExecutionResult:
    """Guarded execute response for API/CLI callers."""

    status: str
    execute: bool
    dry_run: IssueToPRDryRunResult
    pipeline_result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "execute": self.execute,
            "dry_run": self.dry_run.to_dict(),
            "pipeline_result": self.pipeline_result,
            "error": self.error,
        }


def parse_github_issue_url(issue_url: str) -> tuple[str, int]:
    """Parse a GitHub issue URL into repo full name and issue number."""

    match = GITHUB_ISSUE_URL_RE.match(issue_url.strip())
    if not match:
        raise ValueError("Issue URL must look like https://github.com/owner/repo/issues/123")
    return f"{match.group('owner')}/{match.group('repo')}", int(match.group("number"))


def build_issue_event(payload: dict[str, Any]) -> IssueEvent:
    """Build an IssueEvent from a URL or structured issue payload."""

    issue_data = dict(payload.get("issue") or payload)
    issue_url = str(payload.get("issue_url") or issue_data.get("issue_url") or "")
    if issue_url:
        repo_full_name, issue_number = parse_github_issue_url(issue_url)
    else:
        repo_full_name = str(
            issue_data.get("repo_full_name")
            or issue_data.get("repository")
            or issue_data.get("repo")
            or ""
        )
        issue_number = int(issue_data.get("issue_number") or issue_data.get("number") or 0)
    if not repo_full_name or not issue_number:
        raise ValueError("repo_full_name and issue_number are required")

    clone_url = str(
        issue_data.get("clone_url")
        or payload.get("clone_url")
        or f"https://github.com/{repo_full_name}.git"
    )
    return IssueEvent(
        action=str(issue_data.get("action") or "opened"),
        repo_full_name=repo_full_name,
        issue_number=issue_number,
        title=str(issue_data.get("title") or f"Issue #{issue_number}"),
        body=str(issue_data.get("body") or ""),
        labels=[
            str(label.get("name", ""))
            if isinstance(label, dict)
            else str(label)
            for label in issue_data.get("labels", [])
        ],
        clone_url=clone_url,
        default_branch=str(issue_data.get("default_branch") or payload.get("default_branch") or "main"),
    )


def _file_candidates(issue: IssueEvent) -> list[str]:
    text = f"{issue.title}\n{issue.body}"
    explicit = re.findall(r"[\w./-]+\.(?:py|ts|tsx|js|jsx|md|json|yaml|yml)", text)
    candidates = list(dict.fromkeys(explicit))
    label_text = " ".join(issue.labels).lower()
    if "doc" in label_text or "documentation" in text.lower():
        candidates.append("docs/")
    if "test" in label_text or "test" in text.lower():
        candidates.append("tests/")
    if not candidates:
        candidates.extend(["README.md", "backend/app/"])
    return candidates


def _risk_flags(issue: IssueEvent) -> list[str]:
    text = f"{issue.title}\n{issue.body}".lower()
    flags: list[str] = []
    for keyword, flag in (
        ("secret", "touches_secret_or_credentials"),
        ("password", "touches_secret_or_credentials"),
        ("token", "touches_secret_or_credentials"),
        ("migration", "may_require_database_migration"),
        ("auth", "may_affect_authentication"),
        ("security", "security_sensitive"),
    ):
        if keyword in text and flag not in flags:
            flags.append(flag)
    return flags


def plan_issue_to_pr(issue: IssueEvent, config: PipelineConfig | None = None) -> IssueToPRPlan:
    config = config or PipelineConfig()
    branch = f"xagent/issue-{issue.issue_number}"
    return IssueToPRPlan(
        repo_full_name=issue.repo_full_name,
        issue_number=issue.issue_number,
        title=issue.title,
        base_branch=config.base_branch_override or issue.default_branch,
        branch_name=branch,
        touched_file_candidates=_file_candidates(issue),
        risk_flags=_risk_flags(issue),
        test_command=config.test_command,
        install_command=config.install_command,
        steps=[
            "parse_issue",
            "inspect_repository",
            "create_branch_metadata",
            "draft_patch_plan",
            "prepare_test_command",
            "draft_pull_request_payload",
        ],
    )


def dry_run_issue_to_pr(
    payload: dict[str, Any] | IssueEvent,
    config: PipelineConfig | None = None,
) -> IssueToPRDryRunResult:
    issue = payload if isinstance(payload, IssueEvent) else build_issue_event(payload)
    plan = plan_issue_to_pr(issue, config)
    commit_title = f"fix: resolve #{issue.issue_number} - {issue.title}"
    pr_title = f"Fix #{issue.issue_number}: {issue.title}"
    pr_body = (
        f"Dry-run PR draft generated by X-Agent for #{issue.issue_number}.\n\n"
        "No repository writes, pushes, comments, or network mutations were performed.\n\n"
        f"Planned branch: `{plan.branch_name}`\n"
        f"Risk flags: {', '.join(plan.risk_flags) if plan.risk_flags else 'none'}"
    )
    return IssueToPRDryRunResult(
        status="planned",
        dry_run=True,
        issue={
            "repo_full_name": issue.repo_full_name,
            "issue_number": issue.issue_number,
            "title": issue.title,
            "labels": issue.labels,
            "default_branch": issue.default_branch,
            "clone_url": issue.clone_url,
        },
        plan=plan,
        branch_name=plan.branch_name,
        commit_title=commit_title,
        pr_title=pr_title,
        pr_body=pr_body,
    )


class IssueToPRPipeline:
    """Orchestrates the full issue -> PR flow inside an isolated sandbox."""

    def __init__(
        self,
        github: GitHubAPIClient,
        fix_runner: FixRunner,
        config: Optional[PipelineConfig] = None,
    ):
        self._github = github
        self._fix_runner = fix_runner
        self._config = config or PipelineConfig()

    async def run(self, issue: IssueEvent) -> PipelineResult:
        result = PipelineResult(issue_number=issue.issue_number, status="error")
        spec = SandboxSpec(
            image=self._config.sandbox_image,
            timeout_seconds=self._config.sandbox_timeout,
            enable_network=True,  # needed for clone + dep install
        )
        sandbox = DockerSandbox(spec)
        try:
            await sandbox.start()
            workspace = str(sandbox._workspace)  # provisioned dir
            branch = f"xagent/issue-{issue.issue_number}"
            base = self._config.base_branch_override or issue.default_branch
            result.branch = branch

            git = GitOperations(cwd=workspace)
            await git.configure_identity(self._config.bot_name, self._config.bot_email)

            # 1. Clone (authenticated) into the workspace
            auth_url = self._github.authenticated_clone_url(issue.clone_url)
            clone_dir = str(Path(workspace) / "repo")
            clone = await git.clone(auth_url, clone_dir, depth=1)
            if not clone.success:
                result.status = "error"
                result.error = "clone failed"
                result.log("clone failed")
                return result
            git.cwd = clone_dir
            await git.configure_identity(self._config.bot_name, self._config.bot_email)
            result.log("cloned repo")

            # 2. Branch
            await git.create_branch(branch)
            result.log(f"created branch {branch}")

            # 3. Install deps (best-effort)
            if self._config.install_command:
                inst = await sandbox.run(
                    f"cd repo && {self._config.install_command}",
                    timeout=self._config.sandbox_timeout,
                )
                result.log(f"install exit={inst.exit_code}")

            # 4. Produce the fix
            fixed = await self._fix_runner(sandbox, issue, clone_dir)
            if not fixed:
                result.status = "fix_failed"
                result.log("fix_runner produced no fix")
                return result

            # 5. Bail early if nothing changed
            if not await git.has_changes():
                result.status = "no_changes"
                result.log("no changes after fix")
                return result

            # 6. Run tests
            if self._config.run_tests:
                test = await sandbox.run(
                    f"cd repo && {self._config.test_command}",
                    timeout=self._config.sandbox_timeout,
                )
                result.test_output = (test.stdout + test.stderr)[-4000:]
                if not test.success:
                    result.status = "tests_failed"
                    result.log(f"tests failed exit={test.exit_code}")
                    return result
                result.log("tests passed")

            # 7. Commit + push
            await git.add_all()
            await git.commit(f"fix: resolve #{issue.issue_number} - {issue.title}")
            if self._config.open_pr:
                push = await git.push(branch)
                if not push.success:
                    result.status = "error"
                    result.error = "push failed"
                    result.log("push failed")
                    return result
                result.log("pushed branch")

                # 8. Open PR
                pr = await self._github.create_pull_request(
                    repo_full_name=issue.repo_full_name,
                    head=branch,
                    base=base,
                    title=f"Fix #{issue.issue_number}: {issue.title}",
                    body=(
                        f"Automated fix by X-Agent for #{issue.issue_number}.\n\n"
                        f"Closes #{issue.issue_number}."
                    ),
                )
                result.pr_url = pr.get("html_url")
                result.status = "pr_opened"
                result.log(f"opened PR {result.pr_url}")

                # 9. Comment back on the issue
                try:
                    await self._github.comment_on_issue(
                        issue.repo_full_name,
                        issue.issue_number,
                        f"X-Agent opened a pull request: {result.pr_url}",
                    )
                except Exception as e:
                    result.log(f"comment failed (non-fatal): {e}")
            else:
                result.status = "no_changes" if not await git.has_changes() else "pr_opened"

            return result
        except Exception as e:
            logger.exception("Pipeline failed for issue #%s", issue.issue_number)
            result.status = "error"
            result.error = str(e)
            return result
        finally:
            await sandbox.stop()
