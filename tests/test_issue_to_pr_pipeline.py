"""End-to-end test for IssueToPRPipeline using a LOCAL bare git repo as a
fake remote (no network, no real GitHub). Verifies the full flow:
clone -> branch -> fix -> test -> commit -> push.

PR creation + issue comment are stubbed via a fake GitHubAPIClient so we test
the orchestration without hitting the network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backend.app.core.github_integration import IssueEvent
from backend.app.core.pipelines.issue_to_pr import (
    IssueToPRPipeline,
    PipelineConfig,
)


class _FakeGitHub:
    """Stub GitHubAPIClient — records PR/comment calls, no network."""

    def __init__(self):
        self.created_prs = []
        self.comments = []

    def authenticated_clone_url(self, clone_url: str) -> str:
        return clone_url  # local path, no auth needed

    async def create_pull_request(self, repo_full_name, head, base, title, body):
        pr = {"html_url": f"file://fake-pr/{head}", "number": 999}
        self.created_prs.append({"head": head, "base": base, "title": title})
        return pr

    async def comment_on_issue(self, repo_full_name, issue_number, body):
        self.comments.append({"issue": issue_number, "body": body})
        return {"id": 1}


def _make_bare_remote(tmp_path: Path) -> str:
    """Create a bare repo with one commit on main, return its path as clone_url."""
    work = tmp_path / "seed"
    work.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=work, check=True)
    subprocess.run(["git", "config", "user.name", "Seed"], cwd=work, check=True)
    subprocess.run(["git", "config", "user.email", "seed@test.dev"], cwd=work, check=True)
    (work / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (work / "test_app.py").write_text(
        "from app import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=work, check=True)

    bare = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)], check=True)
    # allow pushes to the checked-out branch of a bare repo (bare repos are fine)
    return str(bare)


def _issue(clone_url: str) -> IssueEvent:
    return IssueEvent(
        action="assigned",
        repo_full_name="foo/bar",
        issue_number=7,
        title="Add multiply function",
        body="Please add a multiply function to app.py",
        labels=["enhancement"],
        clone_url=clone_url,
        default_branch="main",
    )


class TestIssueToPRPipeline:
    @pytest.mark.asyncio
    async def test_full_flow_opens_pr(self, tmp_path):
        clone_url = _make_bare_remote(tmp_path)

        async def fix_runner(sandbox, issue, workspace):
            # append a multiply function to app.py inside the cloned repo
            await sandbox.run(
                "printf 'def multiply(a, b):\\n    return a * b\\n' >> repo/app.py"
            )
            return True

        gh = _FakeGitHub()
        pipeline = IssueToPRPipeline(
            github=gh,
            fix_runner=fix_runner,
            config=PipelineConfig(
                test_command="python -m pytest -q || true",  # tolerate no pytest in sandbox
                install_command=None,  # skip dep install in test
                run_tests=False,  # we don't have pytest in the sandbox container
            ),
        )
        result = await pipeline.run(_issue(clone_url))
        assert result.status == "pr_opened", f"got {result.status}: {result.error} / {result.steps}"
        assert result.pr_url is not None
        assert len(gh.created_prs) == 1
        assert gh.created_prs[0]["head"] == "xagent/issue-7"
        assert len(gh.comments) == 1

    @pytest.mark.asyncio
    async def test_no_changes_short_circuits(self, tmp_path):
        clone_url = _make_bare_remote(tmp_path)

        async def noop_runner(sandbox, issue, workspace):
            return True  # claims success but changes nothing

        gh = _FakeGitHub()
        pipeline = IssueToPRPipeline(
            github=gh,
            fix_runner=noop_runner,
            config=PipelineConfig(install_command=None, run_tests=False),
        )
        result = await pipeline.run(_issue(clone_url))
        assert result.status == "no_changes"
        assert len(gh.created_prs) == 0

    @pytest.mark.asyncio
    async def test_fix_failed_short_circuits(self, tmp_path):
        clone_url = _make_bare_remote(tmp_path)

        async def failing_runner(sandbox, issue, workspace):
            return False  # fix could not be produced

        gh = _FakeGitHub()
        pipeline = IssueToPRPipeline(
            github=gh,
            fix_runner=failing_runner,
            config=PipelineConfig(install_command=None, run_tests=False),
        )
        result = await pipeline.run(_issue(clone_url))
        assert result.status == "fix_failed"
        assert len(gh.created_prs) == 0

    @pytest.mark.asyncio
    async def test_tests_failed_blocks_pr(self, tmp_path):
        clone_url = _make_bare_remote(tmp_path)

        async def breaking_runner(sandbox, issue, workspace):
            # write a file + a test that always fails
            await sandbox.run("printf 'def f():\\n    return 1\\n' >> repo/app.py")
            await sandbox.run(
                "printf 'def test_fail():\\n    assert False\\n' > repo/test_fail.py"
            )
            return True

        gh = _FakeGitHub()
        pipeline = IssueToPRPipeline(
            github=gh,
            fix_runner=breaking_runner,
            config=PipelineConfig(
                install_command=None,
                run_tests=True,
                test_command="python3 -c \"import sys; sys.exit(1)\"",  # simulate test failure
            ),
        )
        result = await pipeline.run(_issue(clone_url))
        assert result.status == "tests_failed"
        assert len(gh.created_prs) == 0
