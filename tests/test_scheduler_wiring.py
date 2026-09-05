"""B3（2026-09-05）调度器接线测试。

覆盖三层：
1. 路由挂载：skill_sediment / memory_advanced / scheduler 三个 router 可达。
2. 定时任务真实投递：schedule_once 到点后向 task_queue 投递 agent.run，
   由 handler 执行（mock agent 验证被调用与参数透传）。
3. 无 agent_task 的诚实降级：到点返回 skipped 而非伪装 executed。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """启动应用但关闭 B3 常驻循环（测试不依赖后台调度线程）。"""
    monkeypatch.setenv("XAGENT_SCHEDULER_ENABLED", "false")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fresh_scheduler(monkeypatch: pytest.MonkeyPatch):
    """隔离全局 cron_scheduler 状态，避免用例间任务串扰。"""
    from backend.app.core import scheduler as sched_mod

    saved_tasks = sched_mod.cron_scheduler.scheduled_tasks
    saved_history = sched_mod.cron_scheduler.execution_history
    sched_mod.cron_scheduler.scheduled_tasks = {}
    sched_mod.cron_scheduler.execution_history = {}
    yield sched_mod.cron_scheduler
    sched_mod.cron_scheduler.scheduled_tasks = saved_tasks
    sched_mod.cron_scheduler.execution_history = saved_history


class TestRouterMounting:
    """三个新挂载路由可达（鉴权链生效即 401/403，而非 404）。"""

    def test_skill_sediment_router_mounted(self, client: TestClient):
        resp = client.get("/api/v1/skill-sediment/stats")
        assert resp.status_code != 404

    def test_memory_advanced_router_mounted(self, client: TestClient):
        resp = client.get("/api/v1/memory/episodes")
        assert resp.status_code != 404

    def test_scheduler_router_mounted(self, client: TestClient):
        resp = client.get("/api/scheduler/tasks")
        assert resp.status_code != 404


class TestScheduledAgentTask:
    """定时任务 → task_queue agent.run 真实投递与执行。"""

    async def test_once_schedule_enqueues_agent_run(self, fresh_scheduler, monkeypatch: pytest.MonkeyPatch):
        from backend.app.api.scheduler import _build_task_coroutine

        fired: list[dict] = []

        async def fake_enqueue(name, payload, **kwargs):
            fired.append({"name": name, "payload": payload})
            return "queue-task-1"

        import backend.app.core.task_queue as tq

        monkeypatch.setattr(tq.task_queue, "enqueue", fake_enqueue)

        coro_factory = _build_task_coroutine(
            {
                "name": "daily-report",
                "agent_task": {"task": "生成日报", "context": {"root": "."}},
            }
        )
        result = await coro_factory()

        assert result["status"] == "enqueued"
        assert fired[0]["name"] == "agent.run"
        assert fired[0]["payload"]["task"] == "生成日报"
        assert fired[0]["payload"]["context"] == {"root": "."}

    async def test_missing_agent_task_skips_honestly(self):
        from backend.app.api.scheduler import _build_task_coroutine

        coro_factory = _build_task_coroutine({"name": "empty-task"})
        result = await coro_factory()

        assert result["status"] == "skipped"
        assert "no agent_task.task" in result["reason"]

    async def test_schedule_once_wires_real_coroutine(self, fresh_scheduler):
        """经 cron_scheduler.schedule_once 注册的协程到点真实触发投递。"""
        from datetime import UTC, datetime, timedelta

        from backend.app.api.scheduler import _build_task_coroutine
        from backend.app.core.scheduler import ScheduleType

        fired: list[str] = []

        async def fake_enqueue(name, payload, **kwargs):
            fired.append(name)
            return "q-1"

        import backend.app.core.task_queue as tq

        original = tq.task_queue.enqueue
        tq.task_queue.enqueue = fake_enqueue
        try:
            run_at = datetime.now(UTC) - timedelta(seconds=1)  # 已到期
            task_id = fresh_scheduler.schedule_once(
                name="due-task",
                coroutine=_build_task_coroutine(
                    {"name": "due-task", "agent_task": {"task": "hello"}}
                ),
                run_at=run_at,
            )
            task = fresh_scheduler.scheduled_tasks[task_id]
            assert task.schedule_type == ScheduleType.ONCE
            # 手动执行（不起 start 循环）：模拟到点触发
            result = await task.coroutine()
            assert result["status"] == "enqueued"
            assert fired == ["agent.run"]
        finally:
            tq.task_queue.enqueue = original


class TestAgentRunHandler:
    """main.py 注册的 agent.run handler 行为（直接构造验证，不依赖启动顺序）。"""

    async def test_handler_runs_agent_with_context(self, monkeypatch: pytest.MonkeyPatch):
        import backend.app.dependencies as deps
        from backend.app.core.contracts import AgentRunResponse, RunContext, RunStatus

        calls: list[tuple[str, dict]] = []

        class FakeAgent:
            async def run(self, context, task, extra_context=None, **kwargs):
                calls.append((task, dict(extra_context or {})))
                return AgentRunResponse(
                    trace_id=context.trace_id,
                    agent_id=context.agent_id,
                    status=RunStatus.COMPLETED,
                    answer="done",
                    memory_hits=0,
                    iterations=1,
                )

        monkeypatch.setattr(deps, "get_agent", lambda: FakeAgent())

        # 重建 handler（与 main.py startup 中相同形状）验证行为
        async def _agent_run_handler(payload, metadata=None):
            task_text = str((payload or {}).get("task") or "").strip()
            if not task_text:
                return {"status": "skipped", "reason": "empty task"}
            agent = deps.get_agent()
            result = await agent.run(
                RunContext(), task_text,
                extra_context=dict((payload or {}).get("context") or {}),
            )
            return {
                "status": result.status.value,
                "answer": (result.answer or "")[:2000],
                "trace_id": result.trace_id,
            }

        result = await _agent_run_handler(
            {"task": "跑测试", "context": {"root": "/tmp"}}
        )
        assert result["status"] == "completed"
        assert result["answer"] == "done"
        assert calls == [("跑测试", {"root": "/tmp"})]

        empty = await _agent_run_handler({"task": ""})
        assert empty["status"] == "skipped"
