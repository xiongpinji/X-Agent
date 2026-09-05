"""统一异步任务层测试（2026-09-06）— /api/v1/agent/tasks + tasks_store。

覆盖四块：
1. API 契约：提交 agent_run（mock agent）→ 轮询到 completed 且 result/trace_id
   回填；失败映射 failed；needs_approval 映射 awaiting_approval；列表过滤。
2. 取消语义：queued → 直接 cancelled；running → cancel_requested 协作式
   （agent 完成后落 cancelled）；终态 → 409。
3. 持久化：JSONL 重启回灌（最新行生效）、损坏行跳过、每 kind 容量压缩。
4. 诚实边界：kind=shell/issue_to_pr → 501 指引既有端点；未鉴权 → 401。
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.contracts import AgentRunResponse, RunStatus
from backend.app.core.security import ROLE_SCOPES
from backend.app.main import app

AUTH = {"x-api-key": "bootstrap"}
BASE = "/api/v1/agent/tasks"
TERMINAL = ("completed", "failed", "cancelled")


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """把 TasksStore 隔离到 per-test 临时目录（惯例同 checkpoint store 测试）。"""
    import backend.app.core.tasks_store as ts

    monkeypatch.setenv("XAGENT_TASKS_STORE_PATH", str(tmp_path / "tasks"))
    ts.reset_tasks_store()
    yield ts
    ts.reset_tasks_store()


@pytest.fixture
def client(isolated_store) -> TestClient:
    with TestClient(app, headers=AUTH) as c:
        yield c


class FakeAgent:
    """可控的假 AgentLoop：延迟/异常/审批状态可配，并记录调用参数。"""

    def __init__(
        self,
        answer: str = "任务完成",
        status: RunStatus = RunStatus.COMPLETED,
        error: str | None = None,
        raise_exc: Exception | None = None,
        delay: float = 0.0,
        wait_for_cancel: bool = False,
    ):
        self.answer = answer
        self.status = status
        self.error = error
        self.raise_exc = raise_exc
        self.delay = delay
        self.wait_for_cancel = wait_for_cancel
        self.calls: list[dict] = []

    async def run(self, context, task, extra_context=None, **kwargs):
        from backend.app.core.tasks_store import get_tasks_store

        self.calls.append({"task": task, "context": dict(extra_context or {})})
        if self.wait_for_cancel:
            # 阻塞直到任务被请求取消（或超时）——模拟无法硬杀的长运行 agent
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                running = get_tasks_store().list(status="running", limit=10)
                if any(r.cancel_requested for r in running):
                    break
                await asyncio.sleep(0.02)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raise_exc is not None:
            raise self.raise_exc
        return AgentRunResponse(
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            status=self.status,
            answer=self.answer,
            iterations=2,
            memory_hits=1,
            error=self.error,
        )


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    """把 dependencies.get_agent 换成可配置的 FakeAgent。"""

    def _install(agent: FakeAgent) -> FakeAgent:
        import backend.app.dependencies as deps

        monkeypatch.setattr(deps, "get_agent", lambda: agent)
        return agent

    return _install


def _poll(
    client: TestClient,
    task_id: str,
    timeout: float = 8.0,
    terminal: tuple[str, ...] = TERMINAL,
) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        resp = client.get(f"{BASE}/{task_id}")
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["status"] in terminal:
            return last
        time.sleep(0.05)
    pytest.fail(f"task {task_id} not terminal within {timeout}s: {last}")


# ─── API：提交 → 轮询 → 终态回填 ─────────────────────────────────────────────


class TestSubmitAndPoll:
    def test_submit_agent_run_completes_with_result_and_trace(self, client, patch_agent):
        agent = patch_agent(FakeAgent(answer="分析结果：一切正常"))

        resp = client.post(
            BASE, json={"kind": "agent_run", "task": "分析当前目录", "context": {"root": "."}}
        )
        assert resp.status_code == 200, resp.text
        created = resp.json()
        assert created["status"] == "queued"
        assert created["kind"] == "agent_run"
        assert created["source"] == "unified"
        task_id = created["task_id"]

        final = _poll(client, task_id)
        assert final["status"] == "completed"
        assert final["result"]["answer"] == "分析结果：一切正常"
        assert final["result"]["iterations"] == 2
        assert final["trace_id"]
        assert final["error"] is None
        assert final["completed_at"] is not None
        # agent 收到任务文本与上下文（principal 透传）
        assert agent.calls == [{"task": "分析当前目录", "context": {"root": "."}}]

    def test_agent_exception_maps_to_failed(self, client, patch_agent):
        patch_agent(FakeAgent(raise_exc=RuntimeError("llm 路由不可用")))

        resp = client.post(BASE, json={"task": "必失败任务"})
        assert resp.status_code == 200
        final = _poll(client, resp.json()["task_id"])
        assert final["status"] == "failed"
        assert "llm 路由不可用" in final["error"]

    def test_agent_failed_status_maps_to_failed(self, client, patch_agent):
        patch_agent(FakeAgent(status=RunStatus.FAILED, error="预算超限"))

        resp = client.post(BASE, json={"task": "超预算任务"})
        final = _poll(client, resp.json()["task_id"])
        assert final["status"] == "failed"
        assert final["error"] == "预算超限"

    def test_needs_approval_maps_to_awaiting_approval(self, client, patch_agent):
        patch_agent(FakeAgent(status=RunStatus.NEEDS_APPROVAL))

        resp = client.post(BASE, json={"task": "需要审批的高危任务"})
        final = _poll(
            client, resp.json()["task_id"], terminal=(*TERMINAL, "awaiting_approval")
        )
        assert final["status"] == "awaiting_approval"

    def test_list_filters_by_status_and_kind(self, client, patch_agent):
        patch_agent(FakeAgent())
        done_id = client.post(BASE, json={"task": "完成任务"}).json()["task_id"]
        _poll(client, done_id)

        listed = client.get(BASE, params={"status": "completed", "kind": "agent_run"})
        assert listed.status_code == 200
        body = listed.json()
        assert body["total"] >= 1
        assert all(t["status"] == "completed" for t in body["tasks"])
        assert all(t["kind"] == "agent_run" for t in body["tasks"])
        assert any(t["task_id"] == done_id for t in body["tasks"])
        # source 字段预留（当前恒 unified）
        assert all(t["source"] == "unified" for t in body["tasks"])

    def test_get_unknown_task_404(self, client):
        assert client.get(f"{BASE}/utask-nope").status_code == 404

    def test_blank_task_rejected(self, client):
        resp = client.post(BASE, json={"task": "   "})
        assert resp.status_code == 422


# ─── API：取消语义 ───────────────────────────────────────────────────────────


class TestCancel:
    def test_cancel_queued_task_immediately_cancelled(self, client, isolated_store):
        # 直接种一条 queued 记录（未经后台执行），验证 queued → cancelled
        record = isolated_store.TaskRecord(
            kind="agent_run", payload={"task": "排队中"}
        )
        isolated_store.get_tasks_store().create(record)

        resp = client.post(f"{BASE}/{record.task_id}/cancel")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"
        assert body["completed_at"] is not None

    def test_cancel_running_marks_cancel_requested_then_lands_cancelled(
        self, client, patch_agent
    ):
        # agent 阻塞直到收到取消请求（协作式取消，agent loop 无法硬杀）
        patch_agent(FakeAgent(wait_for_cancel=True))

        task_id = client.post(BASE, json={"task": "长任务"}).json()["task_id"]
        _poll(client, task_id, terminal=("running",))  # 等执行体真正跑起来

        resp = client.post(f"{BASE}/{task_id}/cancel")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"  # 诚实语义：不能谎报已取消
        assert body["cancel_requested"] is True

        final = _poll(client, task_id)
        assert final["status"] == "cancelled"
        # agent 实际跑完了，结果摘要保留供审计，且注明取消原因
        assert "cancel_note" in final["result"]

    def test_cancel_terminal_task_409(self, client, patch_agent):
        patch_agent(FakeAgent())
        task_id = client.post(BASE, json={"task": "快任务"}).json()["task_id"]
        _poll(client, task_id)

        resp = client.post(f"{BASE}/{task_id}/cancel")
        assert resp.status_code == 409

    def test_cancel_unknown_task_404(self, client):
        assert client.post(f"{BASE}/utask-nope/cancel").status_code == 404


# ─── 诚实边界 ────────────────────────────────────────────────────────────────


class TestHonestBoundaries:
    @pytest.mark.parametrize(
        "kind,hint",
        [
            ("shell", "/api/v1/sandbox/tasks"),
            ("issue_to_pr", "/api/v1/sandbox/webhook/github"),
        ],
    )
    def test_unsupported_kinds_501_with_hint(self, client, kind, hint):
        resp = client.post(BASE, json={"kind": kind, "task": "x"})
        assert resp.status_code == 501
        assert hint in resp.json()["message"]

    def test_requires_auth(self, isolated_store):
        with TestClient(app) as anon:  # 无凭证
            # 安全链：GET 直达鉴权层 → 401（匿名主体被拒）
            assert anon.get(BASE).status_code == 401
            # POST 无凭证先被 CSRF 中间件拦截（403），同样不可达业务逻辑
            assert anon.post(BASE, json={"task": "x"}).status_code == 403

    def test_tasks_manage_scope_granted_to_admin_and_developer(self):
        assert "tasks:manage" in ROLE_SCOPES["admin"]
        assert "tasks:manage" in ROLE_SCOPES["developer"]


# ─── tasks_store：持久化 / 回灌 / 容错 / 压缩 ────────────────────────────────


class TestTasksStorePersistence:
    def test_restart_rehydrates_latest_state(self, tmp_path: Path):
        from backend.app.core.tasks_store import TaskRecord, TasksStore

        store = TasksStore(storage_dir=tmp_path / "t1")
        rec = TaskRecord(kind="agent_run", payload={"task": "重启任务"})
        store.create(rec)
        store.update(rec.task_id, status="running")
        store.update(rec.task_id, status="completed", result={"answer": "ok"})

        # 模拟重启：新实例从同一目录回灌，同一 task_id 取最新一行
        revived = TasksStore(storage_dir=tmp_path / "t1")
        got = revived.get(rec.task_id)
        assert got is not None
        assert got.status == "completed"
        assert got.result == {"answer": "ok"}
        assert got.started_at is not None
        assert got.completed_at is not None

    def test_corrupt_lines_skipped_good_records_kept(self, tmp_path: Path):
        from backend.app.core.tasks_store import TaskRecord, TasksStore

        store = TasksStore(storage_dir=tmp_path / "t2")
        good = TaskRecord(kind="agent_run", payload={"task": "好记录"})
        store.create(good)
        store.update(good.task_id, status="failed", error="boom")

        # 手动注入损坏行（模拟崩溃撕裂写入）：中间夹垃圾，末尾再压一行好记录
        file_path = tmp_path / "t2" / "agent_run.jsonl"
        lines = file_path.read_text(encoding="utf-8").splitlines()
        another = TaskRecord(kind="agent_run", payload={"task": "晚来的"})
        file_path.write_text(
            "\n".join([lines[0], "{not-json", lines[1], another.model_dump_json()]) + "\n",
            encoding="utf-8",
        )

        revived = TasksStore(storage_dir=tmp_path / "t2")
        assert revived.get(good.task_id).status == "failed"
        assert revived.get(another.task_id) is not None

    def test_per_kind_capacity_compacts_atomically(self, tmp_path: Path):
        from backend.app.core.tasks_store import TaskRecord, TasksStore

        store = TasksStore(storage_dir=tmp_path / "t3", max_per_kind=3)
        ids = []
        for i in range(6):
            rec = TaskRecord(kind="agent_run", payload={"task": f"t{i}"})
            store.create(rec)
            ids.append(rec.task_id)

        # 内存：只剩最新 3 条
        kept = store.list(kind="agent_run", limit=100)
        assert len(kept) == 3
        kept_ids = {t.task_id for t in kept}
        assert kept_ids == set(ids[3:])

        # 磁盘：压缩重写后同样只剩 3 行（重启不复活旧记录）
        file_lines = (tmp_path / "t3" / "agent_run.jsonl").read_text(
            encoding="utf-8"
        ).strip().splitlines()
        assert len(file_lines) == 3
        revived = TasksStore(storage_dir=tmp_path / "t3")
        assert {t.task_id for t in revived.list(kind="agent_run", limit=100)} == kept_ids

    def test_invalid_transition_rejected(self, tmp_path: Path):
        from backend.app.core.tasks_store import (
            InvalidTaskTransition,
            TaskRecord,
            TasksStore,
        )

        store = TasksStore(storage_dir=tmp_path / "t4")
        rec = TaskRecord(kind="agent_run", payload={"task": "x"})
        store.create(rec)
        store.update(rec.task_id, status="cancelled")

        with pytest.raises(InvalidTaskTransition):
            store.update(rec.task_id, status="running")

    def test_jsonl_record_shape(self, tmp_path: Path):
        """落盘行为可直接被外部工具消费（每行一个完整 JSON 记录）。"""
        from backend.app.core.tasks_store import TaskRecord, TasksStore

        store = TasksStore(storage_dir=tmp_path / "t5")
        rec = TaskRecord(kind="shell", payload={"task": "ls"})
        store.create(rec)

        line = json.loads(
            (tmp_path / "t5" / "shell.jsonl").read_text(encoding="utf-8").splitlines()[0]
        )
        assert line["task_id"] == rec.task_id
        assert line["kind"] == "shell"
        assert line["status"] == "queued"
        assert line["source"] == "unified"
