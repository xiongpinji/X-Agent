"""P2-08: 移动端 Agent 触发/监控 API 测试.

覆盖:
- 远程触发 Agent 执行
- 列出移动端 runs
- 查询 run 状态
- 取消执行
- 推送 token 注册/注销
- MobileRunManager 内部逻辑
"""

import pytest

from backend.app.api.mobile import (
    MobileRunManager,
    MobileRunRecord,
    PushRegisterRequest,
    TriggerRequest,
    _estimate_progress,
    _current_step_desc,
    get_mobile_manager,
)
from backend.app.core.security import Principal


# ─── MobileRunManager 单元测试 ────────────────────────────────────────────────


class TestMobileRunManager:
    def setup_method(self):
        self.manager = MobileRunManager()
        self.principal = Principal(user_id="test-user", tenant_id="test-tenant", roles=["user"])

    def _make_trigger(self, task="测试任务", **kwargs) -> TriggerRequest:
        return TriggerRequest(task=task, **kwargs)

    def test_create_run(self):
        req = self._make_trigger("分析数据")
        record = self.manager.create_run(req, self.principal)
        assert record.run_id.startswith("mob-")
        assert record.task == "分析数据"
        assert record.status == "pending"
        assert record.trace_id

    def test_get_run(self):
        req = self._make_trigger()
        record = self.manager.create_run(req, self.principal)
        fetched = self.manager.get_run(record.run_id)
        assert fetched is not None
        assert fetched.run_id == record.run_id

    def test_get_run_not_found(self):
        assert self.manager.get_run("nonexistent") is None

    def test_list_runs(self):
        for i in range(5):
            self.manager.create_run(self._make_trigger(f"task-{i}"), self.principal)
        runs = self.manager.list_runs()
        assert len(runs) == 5

    def test_list_runs_with_limit(self):
        for i in range(10):
            self.manager.create_run(self._make_trigger(f"task-{i}"), self.principal)
        runs = self.manager.list_runs(limit=3)
        assert len(runs) == 3

    def test_list_runs_by_device(self):
        req1 = TriggerRequest(task="t1", metadata={"device_id": "dev-a"})
        req2 = TriggerRequest(task="t2", metadata={"device_id": "dev-b"})
        self.manager.create_run(req1, self.principal)
        self.manager.create_run(req2, self.principal)
        runs_a = self.manager.list_runs(device_id="dev-a")
        assert len(runs_a) == 1
        assert runs_a[0].device_id == "dev-a"

    def test_update_status(self):
        record = self.manager.create_run(self._make_trigger(), self.principal)
        updated = self.manager.update_status(record.run_id, "running", started_at="2026-01-01T00:00:00")
        assert updated.status == "running"
        assert updated.started_at == "2026-01-01T00:00:00"

    def test_update_status_not_found(self):
        result = self.manager.update_status("nonexistent", "running")
        assert result is None

    def test_register_push(self):
        req = PushRegisterRequest(
            device_id="iphone-123",
            platform="ios",
            push_token="apns-token-abc",
            topics=["agent_complete"],
        )
        self.manager.register_push(req)
        assert "iphone-123" in self.manager._push_tokens
        assert self.manager._push_tokens["iphone-123"]["platform"] == "ios"

    def test_unregister_push(self):
        req = PushRegisterRequest(device_id="dev-1", platform="android", push_token="fcm-xyz")
        self.manager.register_push(req)
        assert self.manager.unregister_push("dev-1")
        assert "dev-1" not in self.manager._push_tokens

    def test_unregister_push_not_found(self):
        assert not self.manager.unregister_push("nonexistent")

    def test_priority_field(self):
        req = TriggerRequest(task="urgent task", priority="urgent")
        record = self.manager.create_run(req, self.principal)
        assert record.priority == "urgent"

    def test_notify_flag(self):
        req = TriggerRequest(task="t", notify_on_complete=False)
        record = self.manager.create_run(req, self.principal)
        assert record.notify_on_complete is False


# ─── 辅助函数测试 ─────────────────────────────────────────────────────────────


class TestHelpers:
    def _make_record(self, status="running", **kwargs) -> MobileRunRecord:
        return MobileRunRecord(
            run_id="mob-test",
            trace_id="trace-1",
            task="test",
            agent_id="default",
            priority="normal",
            status=status,
            created_at="2026-01-01T00:00:00+00:00",
            **kwargs,
        )

    def test_progress_completed(self):
        record = self._make_record("completed")
        assert _estimate_progress(record) == 100.0

    def test_progress_pending(self):
        record = self._make_record("pending")
        assert _estimate_progress(record) == 0.0

    def test_progress_failed(self):
        record = self._make_record("failed")
        assert _estimate_progress(record) == 0.0

    def test_progress_running(self):
        record = self._make_record("running", started_at="2026-01-01T00:00:00+00:00")
        progress = _estimate_progress(record)
        assert 0.0 <= progress <= 90.0

    def test_current_step_desc(self):
        assert _current_step_desc(self._make_record("pending")) == "Waiting to start"
        assert _current_step_desc(self._make_record("running")) == "Agent executing"
        assert _current_step_desc(self._make_record("completed")) == "Done"
        assert _current_step_desc(self._make_record("failed")) == "Failed"
        assert _current_step_desc(self._make_record("cancelled")) == "Cancelled"


# ─── TriggerRequest 验证 ──────────────────────────────────────────────────────


class TestTriggerRequestValidation:
    def test_valid_request(self):
        req = TriggerRequest(task="分析销售数据")
        assert req.task == "分析销售数据"
        assert req.priority == "normal"
        assert req.timeout_seconds == 300
        assert req.notify_on_complete is True

    def test_empty_task_rejected(self):
        with pytest.raises(Exception):
            TriggerRequest(task="")

    def test_timeout_bounds(self):
        req = TriggerRequest(task="t", timeout_seconds=10)
        assert req.timeout_seconds == 10
        with pytest.raises(Exception):
            TriggerRequest(task="t", timeout_seconds=5)  # < 10

    def test_metadata_passthrough(self):
        req = TriggerRequest(task="t", metadata={"device_id": "dev-x", "os": "iOS 18"})
        assert req.metadata["device_id"] == "dev-x"


# ─── 单例测试 ─────────────────────────────────────────────────────────────────


class TestSingleton:
    def test_get_mobile_manager_returns_same_instance(self):
        m1 = get_mobile_manager()
        m2 = get_mobile_manager()
        assert m1 is m2
