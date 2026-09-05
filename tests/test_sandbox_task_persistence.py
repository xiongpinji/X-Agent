"""A3（2026-09-05）sandbox 任务结果持久化测试。

此前 _results/_status 纯内存：重启即丢，"assign and come back" 变 404。
覆盖：状态转换落盘 → 新进程（重新 import 模块）回灌 → GET 回退持久化记录。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.api import sandbox_tasks as st


@pytest.fixture
def isolated_persist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """隔离持久化目录并复位模块级状态。"""
    monkeypatch.setattr(st, "_PERSIST_DIR", tmp_path)
    monkeypatch.setattr(st, "_PERSIST_FILE", tmp_path / "tasks.jsonl")
    monkeypatch.setattr(st, "_status", {})
    monkeypatch.setattr(st, "_results", {})
    monkeypatch.setattr(st, "_persisted_records", {})
    return tmp_path


class FakeResult:
    backend = "docker"
    error = None
    steps = [{"name": "command", "success": True}]
    success = True


def test_persist_and_rehydrate(isolated_persist: Path):
    st._persist_task("t-1", "queued", name="demo")
    st._persist_task("t-1", "completed", result=FakeResult(), name="demo")

    lines = (isolated_persist / "tasks.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    last = json.loads(lines[-1])
    assert last["status"] == "completed"
    assert last["backend"] == "docker"
    assert last["steps"][0]["success"] is True

    # 模拟重启：清空内存后重新回灌
    st._status.clear()
    st._persisted_records.clear()
    st._load_persisted()
    assert st._status["t-1"] == "completed"          # 最新一条生效
    assert st._persisted_records["t-1"]["backend"] == "docker"


def test_corrupt_line_skipped(isolated_persist: Path):
    (isolated_persist / "tasks.jsonl").write_text(
        '{"task_id":"good","status":"failed"}\nnot-json\n', encoding="utf-8"
    )
    st._load_persisted()
    assert st._status == {"good": "failed"}
    assert "good" in st._persisted_records


async def test_get_task_falls_back_to_persisted_record(isolated_persist: Path):
    import asyncio

    from fastapi.testclient import TestClient
    from backend.app.main import app

    st._persist_task("t-2", "failed", result=None, name="x")
    st._status["t-2"] = "failed"
    st._results.clear()  # 模拟重启后内存结果丢失

    with TestClient(app, headers={"x-api-key": "bootstrap"}) as client:
        resp = client.get("/api/v1/sandbox/tasks/t-2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
