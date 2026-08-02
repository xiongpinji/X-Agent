"""Track D1: parallel sub-agent wiring (对标 Codex MultiAgent V2).

Covers:
- API fan-out: POST /api/v1/agents/parallel/spawn executes >=3 subtasks
  concurrently (wall time < serial sum), aggregates results, and returns
  an independent trace per subtask; status/results endpoints + 404.
- Executor concurrency cap: max_parallel=1 degenerates to serial.
- CLI: ``xagent agent run "t1; t2; t3" --parallel N --mode local`` parsing,
  per-subtask status table + evidence, exit codes.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from backend.app.core.parallel_agent_executor import (
    AgentTask,
    IsolationMode,
    ParallelAgentExecutor,
)
from backend.app.main import app
from cli.main import app as cli_app
from cli.main import set_current_config
from cli.config import CLIConfig

AUTH_HEADERS = {"x-api-key": "bootstrap"}  # conftest sets XAGENT_BOOTSTRAP_API_KEY


# ─── Shared test doubles ─────────────────────────────────────────────────────


class _DelayedAgent:
    """Mock agent satisfying the executor's factory protocol with real latency."""

    def __init__(self, agent_id: str, isolation: IsolationMode, delay: float = 0.3) -> None:
        self.agent_id = agent_id
        self.isolation = isolation
        self._delay = delay

    async def execute(self, task: AgentTask) -> dict[str, Any]:
        await asyncio.sleep(self._delay)
        return {
            "status": "completed",
            "answer": f"done: {task.goal}",
            "trace_id": f"trace-{self.agent_id}",
        }


def _delayed_factory(delay: float):
    def factory(agent_id: str, isolation: IsolationMode) -> _DelayedAgent:
        return _DelayedAgent(agent_id, isolation, delay)

    return factory


# ─── API: parallel fan-out via TestClient ────────────────────────────────────


class TestApiParallelFanOut:
    """POST /spawn wiring: executor concurrency + aggregation + traces."""

    @pytest.fixture
    def client(self):
        return TestClient(app, raise_server_exceptions=False)

    def test_spawn_fanout_aggregation_and_traces(self, client, monkeypatch):
        monkeypatch.setattr(
            "backend.app.api.parallel_agents.build_agent_loop_factory",
            lambda principal: _delayed_factory(0.3),
        )
        started = time.monotonic()
        resp = client.post(
            "/api/v1/agents/parallel/spawn",
            headers=AUTH_HEADERS,
            json={
                "tasks": [{"goal": f"subtask {i}", "timeout_seconds": 30} for i in range(3)],
                "max_parallel": 3,
                "aggregate_results": True,
            },
        )
        wall = time.monotonic() - started

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_tasks"] == 3
        assert body["completed_tasks"] == 3
        assert body["failed_tasks"] == 0

        # Concurrency proof: 3 x 0.3s serial would be ~0.9s; parallel ~0.3s.
        sum_duration = sum(r["duration"] for r in body["results"])
        assert sum_duration >= 0.85  # delay really applied per subtask
        assert wall < 0.85, f"not parallel: wall={wall:.2f}s >= serial sum"
        assert body["total_duration_seconds"] < sum_duration

        # Each subtask carries an independent agent_id + trace_id.
        agent_ids = {r["agent_id"] for r in body["results"]}
        trace_ids = {r["result"]["trace_id"] for r in body["results"]}
        assert len(agent_ids) == 3
        assert len(trace_ids) == 3
        assert all(r["status"] == "completed" for r in body["results"])

        # Aggregation returned.
        assert body["aggregated"]["total_results"] == 3

        # Status / results endpoints work against the stored batch.
        batch_id = body["batch_id"]
        status = client.get(
            f"/api/v1/agents/parallel/{batch_id}/status", headers=AUTH_HEADERS
        )
        assert status.status_code == 200
        assert status.json()["completed_results"] == 3
        assert status.json()["is_active"] is False

        results = client.get(
            f"/api/v1/agents/parallel/{batch_id}/results?aggregate=true",
            headers=AUTH_HEADERS,
        )
        assert results.status_code == 200
        rbody = results.json()
        assert rbody["completed_tasks"] == 3
        assert len(rbody["results"]) == 3
        assert all(r["agent_id"] for r in rbody["results"])

    def test_spawn_max_parallel_1_runs_serial(self, client, monkeypatch):
        monkeypatch.setattr(
            "backend.app.api.parallel_agents.build_agent_loop_factory",
            lambda principal: _delayed_factory(0.2),
        )
        started = time.monotonic()
        resp = client.post(
            "/api/v1/agents/parallel/spawn",
            headers=AUTH_HEADERS,
            json={
                "tasks": [{"goal": f"subtask {i}", "timeout_seconds": 30} for i in range(3)],
                "max_parallel": 1,
                "aggregate_results": False,
            },
        )
        wall = time.monotonic() - started

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["completed_tasks"] == 3
        # Serial: 3 x 0.2s = 0.6s wall (a parallel run would finish in ~0.2s).
        assert wall >= 0.55, f"expected serial execution, wall={wall:.2f}s"

    def test_unknown_batch_returns_404(self, client):
        resp = client.get(
            "/api/v1/agents/parallel/does-not-exist/status", headers=AUTH_HEADERS
        )
        assert resp.status_code == 404
        resp = client.get(
            "/api/v1/agents/parallel/does-not-exist/results", headers=AUTH_HEADERS
        )
        assert resp.status_code == 404


# ─── Executor: concurrency cap semantics ─────────────────────────────────────


class TestExecutorConcurrencyCap:
    @pytest.mark.asyncio
    async def test_max_parallel_1_degenerates_to_serial(self):
        executor = ParallelAgentExecutor(max_workers=4)
        tasks = [AgentTask(goal=f"t{i}", max_retries=0) for i in range(3)]

        started = time.monotonic()
        batch = await executor.spawn_agents(
            tasks=tasks,
            isolation=IsolationMode.ISOLATED,
            max_parallel=1,
            agent_factory=_delayed_factory(0.15),
        )
        wall = time.monotonic() - started

        assert batch.completed_tasks == 3
        assert wall >= 0.42, f"expected serial, wall={wall:.2f}s"
        assert batch.metadata["max_parallel"] == 1

    @pytest.mark.asyncio
    async def test_max_parallel_3_runs_concurrently(self):
        executor = ParallelAgentExecutor(max_workers=4)
        tasks = [AgentTask(goal=f"t{i}", max_retries=0) for i in range(3)]

        started = time.monotonic()
        batch = await executor.spawn_agents(
            tasks=tasks,
            isolation=IsolationMode.ISOLATED,
            max_parallel=3,
            agent_factory=_delayed_factory(0.15),
        )
        wall = time.monotonic() - started

        assert batch.completed_tasks == 3
        assert wall < 0.42, f"expected parallel, wall={wall:.2f}s"
        # Distinct agent per task, retry counters present.
        assert len({r.agent_id for r in batch.results}) == 3
        assert all(r.retry_attempts == 0 for r in batch.results)
        assert all(r.status == "completed" for r in batch.results)


# ─── CLI: --parallel parsing / rendering / exit codes ────────────────────────


def _fake_batch(subtasks: list[str], max_parallel: int, fail_index: int | None = None):
    results = []
    for i, goal in enumerate(subtasks):
        failed = i == fail_index
        results.append(
            SimpleNamespace(
                task_id=f"task-{i}",
                agent_id=f"agent-{i}",
                status="failed" if failed else "completed",
                error="boom" if failed else None,
                duration_seconds=0.1,
                result={} if failed else {"status": "completed", "trace_id": f"trace-{i}"},
            )
        )
    return SimpleNamespace(
        batch_id="batch-fake-1",
        total_tasks=len(subtasks),
        completed_tasks=sum(1 for r in results if r.status == "completed"),
        failed_tasks=sum(1 for r in results if r.status == "failed"),
        timeout_tasks=0,
        total_duration_seconds=0.1 * len(subtasks),
        metadata={"max_parallel": max_parallel},
        results=results,
    )


class TestCliParallelOption:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture(autouse=True)
    def _local_config(self):
        set_current_config(CLIConfig(mode="local", output_format="plain"))
        yield

    def test_parallel_splits_subtasks_and_exit_0(self, runner):
        with patch(
            "cli.commands.agent_cmd._run_parallel_batch",
            new=AsyncMock(return_value=_fake_batch(["task1", "task2", "task3"], 3)),
        ) as mock_run:
            result = runner.invoke(
                cli_app,
                ["agent", "run", "task1; task2; task3", "--parallel", "3",
                 "--mode", "local", "--headless"],
            )

        assert result.exit_code == 0, result.output
        mock_run.assert_awaited_once()
        kwargs = mock_run.await_args.kwargs
        assert kwargs["subtasks"] == ["task1", "task2", "task3"]
        assert kwargs["max_parallel"] == 3

        payload = json.loads(result.output)
        assert payload["total_tasks"] == 3
        assert payload["completed_tasks"] == 3
        assert [s["subtask"] for s in payload["subtasks"]] == ["task1", "task2", "task3"]
        assert len({s["trace_id"] for s in payload["subtasks"]}) == 3
        assert all("evidence" in s for s in payload["subtasks"])

    def test_parallel_1_degenerates_to_serial_option(self, runner):
        with patch(
            "cli.commands.agent_cmd._run_parallel_batch",
            new=AsyncMock(return_value=_fake_batch(["a", "b"], 1)),
        ) as mock_run:
            result = runner.invoke(
                cli_app,
                ["agent", "run", "a; b", "--parallel", "1", "--mode", "local", "--headless"],
            )

        assert result.exit_code == 0, result.output
        assert mock_run.await_args.kwargs["max_parallel"] == 1
        assert json.loads(result.output)["max_parallel"] == 1

    def test_parallel_failed_subtask_exit_1(self, runner):
        with patch(
            "cli.commands.agent_cmd._run_parallel_batch",
            new=AsyncMock(return_value=_fake_batch(["a", "b"], 2, fail_index=1)),
        ):
            result = runner.invoke(
                cli_app,
                ["agent", "run", "a; b", "--parallel", "2", "--mode", "local", "--headless"],
            )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["failed_tasks"] == 1

    def test_parallel_rejected_in_http_mode(self, runner):
        set_current_config(CLIConfig(mode="http", output_format="plain"))
        result = runner.invoke(
            cli_app,
            ["agent", "run", "a; b", "--parallel", "2", "--headless"],
        )
        assert result.exit_code == 2
        assert "local" in result.output

    def test_parallel_rich_output_status_table(self, runner):
        with patch(
            "cli.commands.agent_cmd._run_parallel_batch",
            new=AsyncMock(return_value=_fake_batch(["alpha", "beta"], 2)),
        ):
            result = runner.invoke(
                cli_app,
                ["agent", "run", "alpha; beta", "--parallel", "2", "--mode", "local"],
            )

        assert result.exit_code == 0, result.output
        assert "Parallel Subtasks" in result.output
        assert "completed" in result.output
        assert "Completion Evidence" in result.output or "完成证据" in result.output
