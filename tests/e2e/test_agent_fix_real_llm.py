"""End-to-end smoke test for AgentFixRunner with a REAL LLM (DeepSeek).

This is NOT a unit test — it requires a live DeepSeek API key and network.
It is skipped automatically unless XAGENT_DEEPSEEK_API_KEY (or
XAGENT_E2E_LLM=1) is set, so it never runs in CI/sandbox by accident.

What it does:
  1. Creates a tiny local git repo with a function that has a known gap.
  2. Builds a real AgentLoop (DeepSeek backend) via the production factory.
  3. Runs AgentFixRunner against a synthetic IssueEvent describing the fix.
  4. Asserts the agent actually mutated a file in the repo.

Run it explicitly:
  XAGENT_E2E_LLM=1 python -m pytest tests/e2e/test_agent_fix_real_llm.py -s -q
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

_E2E_ENABLED = bool(os.environ.get("XAGENT_E2E_LLM")) or bool(
    os.environ.get("XAGENT_DEEPSEEK_API_KEY")
)

pytestmark = pytest.mark.skipif(
    not _E2E_ENABLED,
    reason="real-LLM e2e: set XAGENT_E2E_LLM=1 (and DeepSeek key) to run",
)


@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_agent_fix_runner_real_llm(tmp_path):
    from dataclasses import dataclass

    from backend.app.core.pipelines import AgentFixRunner

    # 1. Seed a tiny repo with a deliberate gap: only add() exists.
    workspace = tmp_path / "ws"
    repo = workspace / "repo"
    repo.mkdir(parents=True)
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.dev"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    @dataclass
    class _Issue:
        issue_number: int = 1
        title: str = "Add a subtract function to calc.py"
        body: str = (
            "calc.py has add() but no subtract(). Please add a "
            "subtract(a, b) function that returns a - b."
        )

    # 2+3. Real AgentLoop via production factory (reads DeepSeek settings).
    runner = AgentFixRunner()  # lazily builds get_agent()
    mutated = await runner(sandbox=None, issue=_Issue(), workspace=str(workspace))

    # 4. Assert the agent actually changed a file.
    after = (repo / "calc.py").read_text()
    print("\n--- calc.py after agent ---\n" + after)
    assert mutated is True, "AgentFixRunner reported no file mutation"
    assert "subtract" in after, "agent did not add a subtract function"
