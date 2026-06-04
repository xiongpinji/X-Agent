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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from backend.app.core.git_ops import GitOperations
from backend.app.core.github_integration import GitHubAPIClient, IssueEvent
from backend.app.core.sandbox.docker_sandbox import DockerSandbox, SandboxSpec

logger = logging.getLogger(__name__)

# fix_runner(sandbox, issue, workspace) -> bool (True = produced a fix)
FixRunner = Callable[[DockerSandbox, IssueEvent, str], Awaitable[bool]]


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
