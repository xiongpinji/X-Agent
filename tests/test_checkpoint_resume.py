"""断点续跑/失败恢复模块测试。"""
import pytest

from backend.app.core.checkpoint.snapshot import ExecutionSnapshot
from backend.app.core.checkpoint.manager import CheckpointManager
from backend.app.core.checkpoint.restorer import StateRestorer


class TestExecutionSnapshot:
    """快照数据模型测试。"""

    def test_create_snapshot(self):
        snap = ExecutionSnapshot(run_id="run-1", checkpoint_id="ckpt-1", step_index=5)
        assert snap.run_id == "run-1"
        assert snap.step_index == 5
        assert snap.status == "active"

    def test_serialization_roundtrip(self):
        snap = ExecutionSnapshot(
            run_id="run-2",
            checkpoint_id="ckpt-2",
            step_index=3,
            trajectory=[{"type": "tool_call", "tool": "search"}],
            partial_results={"answer": "42"},
        )
        d = snap.to_dict()
        restored = ExecutionSnapshot.from_dict(d)
        assert restored.run_id == "run-2"
        assert restored.step_index == 3
        assert restored.trajectory == [{"type": "tool_call", "tool": "search"}]
        assert restored.partial_results == {"answer": "42"}

    def test_json_roundtrip(self):
        snap = ExecutionSnapshot(run_id="run-3", checkpoint_id="ckpt-3")
        raw = snap.to_json()
        restored = ExecutionSnapshot.from_json(raw)
        assert restored.run_id == "run-3"


class TestCheckpointManager:
    """检查点管理器测试。"""

    def test_should_checkpoint(self, tmp_path):
        mgr = CheckpointManager(store_dir=tmp_path, auto_interval=5)
        assert not mgr.should_checkpoint("r1", 0)
        assert not mgr.should_checkpoint("r1", 3)
        assert mgr.should_checkpoint("r1", 5)
        assert mgr.should_checkpoint("r1", 10)

    def test_create_and_get_latest(self, tmp_path):
        mgr = CheckpointManager(store_dir=tmp_path)
        mgr.create_checkpoint("run-10", step_index=1, partial_results={"a": 1})
        mgr.create_checkpoint("run-10", step_index=5, partial_results={"a": 1, "b": 2})
        latest = mgr.get_latest("run-10")
        assert latest is not None
        assert latest.step_index == 5

    def test_list_checkpoints(self, tmp_path):
        mgr = CheckpointManager(store_dir=tmp_path)
        mgr.create_checkpoint("run-11", step_index=1)
        mgr.create_checkpoint("run-11", step_index=2)
        mgr.create_checkpoint("run-11", step_index=3)
        checkpoints = mgr.list_checkpoints("run-11")
        assert len(checkpoints) == 3

    def test_get_latest_nonexistent(self, tmp_path):
        mgr = CheckpointManager(store_dir=tmp_path)
        assert mgr.get_latest("nope") is None

    def test_cleanup_expired(self, tmp_path):
        mgr = CheckpointManager(store_dir=tmp_path, ttl_hours=0)
        mgr.create_checkpoint("run-12", step_index=1)
        # ttl=0 意味着立即过期
        import time
        time.sleep(0.01)
        removed = mgr.cleanup_expired()
        assert removed >= 1


class TestStateRestorer:
    """状态恢复器测试。"""

    def test_restore(self):
        restorer = StateRestorer()
        snap = ExecutionSnapshot(
            run_id="run-20",
            checkpoint_id="ckpt-20",
            step_index=7,
            trajectory=[{"type": "tool_call"}],
            partial_results={"x": 1},
        )
        state = restorer.restore(snap)
        assert state["is_resumed"] is True
        assert state["resume_from_step"] == 7
        assert state["partial_results"] == {"x": 1}

    def test_validate_context_ok(self):
        restorer = StateRestorer()
        snap = ExecutionSnapshot(
            run_id="r", checkpoint_id="c",
            context={"model_version": "v1", "available_tools": ["search", "write"]},
        )
        valid, issues = restorer.validate_context(snap, {"model_version": "v1", "available_tools": ["search", "write", "read"]})
        assert valid
        assert issues == []

    def test_validate_context_model_mismatch(self):
        restorer = StateRestorer()
        snap = ExecutionSnapshot(
            run_id="r", checkpoint_id="c",
            context={"model_version": "v1"},
        )
        valid, issues = restorer.validate_context(snap, {"model_version": "v2"})
        assert not valid
        assert "模型版本不一致" in issues[0]

    def test_validate_context_missing_tools(self):
        restorer = StateRestorer()
        snap = ExecutionSnapshot(
            run_id="r", checkpoint_id="c",
            context={"available_tools": ["search", "deploy"]},
        )
        valid, issues = restorer.validate_context(snap, {"available_tools": ["search"]})
        assert not valid
        assert "deploy" in issues[0]

    def test_merge_partial_results(self):
        restorer = StateRestorer()
        merged = restorer.merge_partial_results({"a": 1, "b": 2}, {"b": 3, "c": 4})
        assert merged == {"a": 1, "b": 3, "c": 4, "_merged_from_checkpoint": True}
