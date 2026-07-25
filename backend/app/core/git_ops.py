"""Git operations for the Issue-to-PR pipeline.

Uses the `git` CLI via async subprocess (no gitpython dependency). Each
operation runs in a given working directory so multiple pipeline tasks can
operate on separate clones concurrently without interfering.

Auth: clone/push URLs may embed a token (https://x-access-token:TOKEN@github.com/...).
The token is never logged — we redact it from any surfaced command string.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"(https://)([^@/]+)(@)")


def _redact(text: str) -> str:
    """Strip embedded credentials from a string before logging."""
    return _TOKEN_RE.sub(r"\1***\3", text)


@dataclass
class GitResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


class GitOperations:
    """Thin async wrapper over the git CLI scoped to a working directory."""

    def __init__(self, cwd: str | None = None, timeout: float = 120.0):
        self.cwd = cwd
        self.timeout = timeout

    async def _run(self, *args: str, cwd: str | None = None) -> GitResult:
        work_dir = cwd or self.cwd
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )
        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return GitResult(success=False, exit_code=124, stderr="git command timed out")
        out = out_b.decode("utf-8", errors="replace")
        err = err_b.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            logger.warning("git %s failed: %s", _redact(" ".join(args)), _redact(err.strip()))
        return GitResult(
            success=proc.returncode == 0,
            stdout=out,
            stderr=err,
            exit_code=proc.returncode or 0,
        )

    async def clone(self, repo_url: str, dest: str, depth: int | None = 1) -> GitResult:
        """Clone a repo (shallow by default) into dest."""
        args = ["clone"]
        if depth:
            args += ["--depth", str(depth)]
        args += [repo_url, dest]
        result = await self._run(*args, cwd=".")
        if result.success:
            self.cwd = dest
        return result

    async def create_branch(self, branch: str) -> GitResult:
        return await self._run("checkout", "-b", branch)

    async def add_all(self) -> GitResult:
        return await self._run("add", "-A")

    async def commit(self, message: str, author: str | None = None) -> GitResult:
        args = ["commit", "-m", message]
        if author:
            args += ["--author", author]
        return await self._run(*args)

    async def push(self, branch: str, remote: str = "origin", set_upstream: bool = True) -> GitResult:
        args = ["push"]
        if set_upstream:
            args += ["-u"]
        args += [remote, branch]
        return await self._run(*args)

    async def current_branch(self) -> str:
        result = await self._run("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    async def has_changes(self) -> bool:
        """True if there are staged or unstaged changes."""
        result = await self._run("status", "--porcelain")
        return bool(result.stdout.strip())

    async def configure_identity(self, name: str, email: str) -> GitResult:
        await self._run("config", "user.name", name)
        return await self._run("config", "user.email", email)
