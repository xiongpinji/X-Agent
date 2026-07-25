"""P2-09: Checkpoint / 断点续跑单元测试."""

import pytest

from backend.app.core.checkpoint.store import (
    CheckpointData,
    CheckpointStore,
    CheckpointSummary,
)


# ─── CheckpointStore 测试 ─────────────────────────────────────────────────────


class TestCheckpointStore:
    """CheckpointStore 基本操作测试."""

    @pytest.fixture
    def store(self, tmp_path):
        return CheckpointStore(storage_path=tmp_path / "checkpoints", max_per_run=3)

    def _make_checkpoint(self, trace_id: str = "trace-1", iteration: int = 1, **kwargs) -> CheckpointData:
        return CheckpointData(
            checkpoint_id=f"{trace_id}-iter{iteration}",
            trace_id=trace_id,
            agent_id="agent-1",
            tenant_id="tenant-1",
            user_id="user-1",
            task="test task",
            iteration=iteration,
            max_iterations=4,
            status=kwargs.get("status", "running"),
            remaining_steps=kwargs.get("remaining_steps", [{"kind": "tool", "instruction": "do something"}]),
            completed_steps=kwargs.get("completed_steps", []),
            tool_calls=kwargs.get("tool_calls", []),
            observations=kwargs.get("observations", ["obs1"]),
            answer_so_far=kwargs.get("answer_so_far", ""),
            memory_hits=kwargs.get("memory_hits", 1),
            trajectory_goal=kwargs.get("trajectory_goal", "test goal"),
            trajectory_stage=kwargs.get("trajectory_stage", f"step_{iteration}_tool"),
        )

    def test_save_and_get_latest(self, store):
        cp = self._make_checkpoint(iteration=1)
        store.save(cp)

        latest = store.get_latest("trace-1")
        assert latest is not None
        assert latest.iteration == 1
        assert latest.trace_id == "trace-1"

    def test_multiple_checkpoints_latest_wins(self, store):
        store.save(self._make_checkpoint(iteration=1))
        store.save(self._make_checkpoint(iteration=2))
        store.save(self._make_checkpoint(iteration=3))

        latest = store.get_latest("trace-1")
        assert latest.iteration == 3

    def test_max_per_run_limit(self, store):
        """超过 max_per_run 时旧的被清理."""
        for i in range(5):
            store.save(self._make_checkpoint(iteration=i + 1))

        checkpoints = store.list_for_run("trace-1")
        assert len(checkpoints) == 3  # max_per_run=3
        assert checkpoints[0].iteration == 3  # 最旧的被清理

    def test_get_by_checkpoint_id(self, store):
        cp = self._make_checkpoint(iteration=2)
        store.save(cp)

        found = store.get("trace-1-iter2")
        assert found is not None
        assert found.iteration == 2

    def test_get_nonexistent(self, store):
        assert store.get_latest("nonexistent") is None
        assert store.get("nonexistent") is None

    def test_list_resumable(self, store):
        store.save(self._make_checkpoint(trace_id="t1", iteration=1, status="running"))
        store.save(self._make_checkpoint(trace_id="t2", iteration=2, status="failed"))
        store.save(self._make_checkpoint(trace_id="t3", iteration=3, status="completed"))

        resumable = store.list_resumable()
        trace_ids = {s.trace_id for s in resumable}
        assert "t1" in trace_ids
        assert "t2" in trace_ids
        assert "t3" not in trace_ids  # completed 不可恢复

    def test_mark_completed(self, store):
        store.save(self._make_checkpoint(iteration=1))
        store.save(self._make_checkpoint(iteration=2))

        store.mark_completed("trace-1")

        checkpoints = store.list_for_run("trace-1")
        assert len(checkpoints) == 1  # 只保留最新一个
        assert checkpoints[0].status == "completed"

        # 不再出现在 resumable 列表
        resumable = store.list_resumable()
        assert all(s.trace_id != "trace-1" for s in resumable)

    def test_delete(self, store):
        store.save(self._make_checkpoint(iteration=1))
        store.save(self._make_checkpoint(iteration=2))

        deleted = store.delete("trace-1")
        assert deleted == 2
        assert store.get_latest("trace-1") is None

    def test_count(self, store):
        store.save(self._make_checkpoint(trace_id="t1", iteration=1))
        store.save(self._make_checkpoint(trace_id="t2", iteration=1))
        assert store.count() == 2

    def test_persistence(self, tmp_path):
        """数据持久化: 新实例可加载旧数据."""
        path = tmp_path / "cp"
        store1 = CheckpointStore(storage_path=path)
        store1.save(self._make_checkpoint(iteration=1))
        store1.save(self._make_checkpoint(iteration=2))

        # 新实例
        store2 = CheckpointStore(storage_path=path)
        latest = store2.get_latest("trace-1")
        assert latest is not None
        assert latest.iteration == 2

    def test_multiple_traces_isolated(self, store):
        store.save(self._make_checkpoint(trace_id="t1", iteration=1))
        store.save(self._make_checkpoint(trace_id="t2", iteration=1))
        store.save(self._make_checkpoint(trace_id="t1", iteration=2))

        assert store.get_latest("t1").iteration == 2
        assert store.get_latest("t2").iteration == 1


# ─── CheckpointData 模型测试 ──────────────────────────────────────────────────


class TestCheckpointData:
    """Checkpoint 数据模型测试."""

    def test_serialization_roundtrip(self):
        cp = CheckpointData(
            checkpoint_id="cp-1",
            trace_id="trace-1",
            agent_id="agent-1",
            task="test",
            iteration=2,
            max_iterations=4,
            status="running",
            remaining_steps=[{"kind": "tool", "instruction": "run test", "tool_name": "execute", "arguments": {}}],
            observations=["obs1", "obs2"],
            trajectory_goal="goal",
            trajectory_stage="step_2_tool",
        )
        json_str = cp.model_dump_json()
        restored = CheckpointData.model_validate_json(json_str)
        assert restored.checkpoint_id == "cp-1"
        assert restored.iteration == 2
        assert restored.remaining_steps == cp.remaining_steps

    def test_default_values(self):
        cp = CheckpointData(
            checkpoint_id="cp-min",
            trace_id="t",
            agent_id="a",
        )
        assert cp.iteration == 0
        assert cp.status == "running"
        assert cp.remaining_steps == []
        assert cp.observations == []
        assert cp.version == 1
