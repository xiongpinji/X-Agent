"""Tests for AgentFixRunner — verifies it correctly drives an AgentLoop and
judges success by actual file-mutating tool calls (not prose).

Uses a fake agent (no real LLM) so the logic is tested deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from backend.app.core.contracts import RunStatus
from backend.app.core.pipelines import AgentFixRunner


@dataclass
class _FakeToolCall:
    tool_name: str
    success: bool = True
    error: Any = None


@dataclass
class _FakeResult:
    status: Any
    tool_calls: list = field(default_factory=list)
    answer: str = "done"


class _FakeAgent:
    """Records the run() call and returns a canned result."""

    def __init__(self, result):
        self._result = result
        self.max_iterations = 2
        self.max_iterations_seen = None
        self.last_context = None
        self.last_task = None
        self.last_extra = None

    async def run(self, context, task, extra_context=None, event_callback=None):
        self.max_iterations_seen = self.max_iterations
        self.last_context = context
        self.last_task = task
        self.last_extra = extra_context
        return self._result


@dataclass
class _Issue:
    issue_number: int = 7
    title: str = "Add multiply to calc.py"
    body: str = (
        "calc.py has add() but no multiply(). Please add a "
        "multiply(a, b) function that returns a * b."
    )


class TestAgentFixRunner:
    @pytest.mark.asyncio
    async def test_success_when_completed_and_file_mutated(self, tmp_path):
        workspace = tmp_path / "ws"
        repo = workspace / "repo"
        repo.mkdir(parents=True)
        (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        result = _FakeResult(
            status=RunStatus.COMPLETED,
            tool_calls=[_FakeToolCall("write_file", success=True)],
        )
        agent = _FakeAgent(result)
        runner = AgentFixRunner(agent=agent)
        ok = await runner(sandbox=None, issue=_Issue(), workspace=str(workspace))
        assert ok is True
        # the agent was pointed at <workspace>/repo
        assert agent.last_extra["root"].endswith("repo")
        assert agent.last_extra["path"].endswith("repo/calc.py") or agent.last_extra[
            "path"
        ].endswith("repo\\calc.py")
        assert "def multiply" in agent.last_extra["new_text"]
        # task includes the issue title + body
        assert "Add multiply" in agent.last_task
        assert "multiply" in agent.last_task

    @pytest.mark.asyncio
    async def test_fail_when_completed_but_no_file_mutation(self):
        # Agent completed but only called a read-only tool → no real fix.
        result = _FakeResult(
            status=RunStatus.COMPLETED,
            tool_calls=[_FakeToolCall("read_file", success=True)],
        )
        runner = AgentFixRunner(agent=_FakeAgent(result))
        ok = await runner(sandbox=None, issue=_Issue(), workspace="/tmp/ws")
        assert ok is False

    @pytest.mark.asyncio
    async def test_fail_when_mutating_tool_errored(self):
        result = _FakeResult(
            status=RunStatus.COMPLETED,
            tool_calls=[_FakeToolCall("write_file", success=False, error="denied")],
        )
        runner = AgentFixRunner(agent=_FakeAgent(result))
        ok = await runner(sandbox=None, issue=_Issue(), workspace="/tmp/ws")
        assert ok is False

    @pytest.mark.asyncio
    async def test_fail_when_agent_not_completed(self):
        result = _FakeResult(
            status=RunStatus.FAILED,
            tool_calls=[_FakeToolCall("write_file", success=True)],
        )
        runner = AgentFixRunner(agent=_FakeAgent(result))
        ok = await runner(sandbox=None, issue=_Issue(), workspace="/tmp/ws")
        assert ok is False

    @pytest.mark.asyncio
    async def test_fail_when_agent_raises(self):
        class _RaisingAgent:
            async def run(self, *a, **k):
                raise RuntimeError("llm down")

        runner = AgentFixRunner(agent=_RaisingAgent())
        ok = await runner(sandbox=None, issue=_Issue(), workspace="/tmp/ws")
        assert ok is False

    @pytest.mark.asyncio
    async def test_apply_text_patch_also_counts(self):
        result = _FakeResult(
            status=RunStatus.COMPLETED,
            tool_calls=[_FakeToolCall("apply_text_patch", success=True)],
        )
        runner = AgentFixRunner(agent=_FakeAgent(result))
        ok = await runner(sandbox=None, issue=_Issue(), workspace="/tmp/ws")
        assert ok is True

    @pytest.mark.asyncio
    async def test_temporarily_raises_agent_iteration_budget(self):
        result = _FakeResult(
            status=RunStatus.COMPLETED,
            tool_calls=[_FakeToolCall("write_file", success=True)],
        )
        agent = _FakeAgent(result)
        runner = AgentFixRunner(agent=agent, max_iterations=6)
        ok = await runner(sandbox=None, issue=_Issue(), workspace="/tmp/ws")
        assert ok is True
        assert agent.max_iterations_seen == 6
        assert agent.max_iterations == 2
