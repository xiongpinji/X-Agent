"""P2-09: 迭代级 Checkpoint Store — 运行态快照持久化.

在 Agent Loop 每次迭代结束时保存运行态快照 (checkpoint),
崩溃/超时后可从最近的 checkpoint 恢复执行, 而非从头重跑。

与 CheckpointManager (工具调用级) 互补:
- CheckpointManager: 每 N 次工具调用创建快照 (细粒度, 面向单次 run 内部)
- CheckpointStore: 每次迭代结束保存完整运行态 (面向跨进程恢复)
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_DEFAULT_CHECKPOINT_DIR = "data/checkpoints"


# ─── 数据模型 ─────────────────────────────────────────────────────────────────


class CheckpointData(BaseModel):
    """单次 checkpoint 快照."""

    checkpoint_id: str
    trace_id: str
    agent_id: str
    tenant_id: str = ""
    user_id: str = ""
    task: str = ""
    iteration: int = 0
    max_iterations: int = 4
    status: str = "running"  # running | paused | failed | completed
    # 执行状态
    remaining_steps: list[dict[str, Any]] = Field(default_factory=list)
    completed_steps: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    answer_so_far: str = ""
    memory_hits: int = 0
    # Trajectory 状态
    trajectory_goal: str = ""
    trajectory_stage: str = ""
    trajectory_reflections: list[str] = Field(default_factory=list)
    # 上下文
    extra_context: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    # 元数据
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1


class CheckpointSummary(BaseModel):
    """Checkpoint 摘要 (列表展示用)."""

    checkpoint_id: str
    trace_id: str
    agent_id: str
    iteration: int
    status: str
    created_at: datetime
    task_preview: str = ""


# ─── CheckpointStore ──────────────────────────────────────────────────────────


class CheckpointStore:
    """Checkpoint 持久化存储.

    线程安全, 支持 JSONL 文件持久化。
    每个 trace_id 保留最近 N 个 checkpoint (默认 5), 旧的自动清理。
    """

    def __init__(self, storage_path: str | Path | None = None, max_per_run: int = 5):
        self._checkpoints: dict[str, list[CheckpointData]] = {}  # trace_id -> [checkpoints]
        self._lock = threading.RLock()
        self._max_per_run = max_per_run
        self._storage_path = Path(storage_path) if storage_path else Path(_DEFAULT_CHECKPOINT_DIR)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    def save(self, checkpoint: CheckpointData) -> CheckpointData:
        """保存 checkpoint."""
        with self._lock:
            trace_id = checkpoint.trace_id
            if trace_id not in self._checkpoints:
                self._checkpoints[trace_id] = []

            self._checkpoints[trace_id].append(checkpoint)

            # 限制每个 run 的 checkpoint 数量
            if len(self._checkpoints[trace_id]) > self._max_per_run:
                self._checkpoints[trace_id] = self._checkpoints[trace_id][-self._max_per_run:]

            self._append_to_disk(checkpoint)

        logger.debug(
            "Checkpoint saved: trace=%s iter=%d/%d status=%s",
            checkpoint.trace_id, checkpoint.iteration, checkpoint.max_iterations, checkpoint.status,
        )
        return checkpoint

    def get_latest(self, trace_id: str) -> CheckpointData | None:
        """获取指定 run 的最新 checkpoint."""
        with self._lock:
            checkpoints = self._checkpoints.get(trace_id)
            if not checkpoints:
                return None
            return checkpoints[-1]

    def get(self, checkpoint_id: str) -> CheckpointData | None:
        """按 checkpoint_id 精确查找."""
        with self._lock:
            for checkpoints in self._checkpoints.values():
                for cp in checkpoints:
                    if cp.checkpoint_id == checkpoint_id:
                        return cp
            return None

    def list_for_run(self, trace_id: str) -> list[CheckpointData]:
        """列出指定 run 的所有 checkpoint (按时间升序)."""
        with self._lock:
            return list(self._checkpoints.get(trace_id, []))

    def list_resumable(self, limit: int = 20) -> list[CheckpointSummary]:
        """列出可恢复的 run (status=running/failed, 取每个 run 的最新 checkpoint)."""
        with self._lock:
            summaries = []
            for _trace_id, checkpoints in self._checkpoints.items():
                if not checkpoints:
                    continue
                latest = checkpoints[-1]
                if latest.status in ("running", "paused", "failed"):
                    summaries.append(CheckpointSummary(
                        checkpoint_id=latest.checkpoint_id,
                        trace_id=latest.trace_id,
                        agent_id=latest.agent_id,
                        iteration=latest.iteration,
                        status=latest.status,
                        created_at=latest.created_at,
                        task_preview=latest.task[:80],
                    ))
            summaries.sort(key=lambda s: s.created_at, reverse=True)
            return summaries[:limit]

    def mark_completed(self, trace_id: str) -> None:
        """标记 run 已完成 (清理 checkpoint)."""
        with self._lock:
            if trace_id in self._checkpoints:
                for cp in self._checkpoints[trace_id]:
                    cp.status = "completed"
                # 完成后保留最新一个用于审计, 删除其余
                self._checkpoints[trace_id] = self._checkpoints[trace_id][-1:]

    def delete(self, trace_id: str) -> int:
        """删除指定 run 的所有 checkpoint. 返回删除数量."""
        with self._lock:
            removed = len(self._checkpoints.pop(trace_id, []))
            self._remove_from_disk(trace_id)
            return removed

    def count(self) -> int:
        """总 checkpoint 数量."""
        with self._lock:
            return sum(len(v) for v in self._checkpoints.values())

    # ─── 持久化 ───────────────────────────────────────────────────

    def _append_to_disk(self, checkpoint: CheckpointData) -> None:
        """追加写入 JSONL 文件."""
        try:
            file_path = self._storage_path / f"{checkpoint.trace_id}.jsonl"
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(checkpoint.model_dump_json() + "\n")
        except OSError as e:
            logger.warning("Failed to persist checkpoint: %s", e)

    def _load_from_disk(self) -> None:
        """从磁盘加载所有 checkpoint."""
        if not self._storage_path.exists():
            return
        for file_path in self._storage_path.glob("*.jsonl"):
            trace_id = file_path.stem
            checkpoints = []
            try:
                with open(file_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            cp = CheckpointData.model_validate_json(line)
                            checkpoints.append(cp)
            except (OSError, ValueError) as e:
                logger.warning("Failed to load checkpoint file %s: %s", file_path, e)
                continue
            if checkpoints:
                # 只保留最近 N 个
                self._checkpoints[trace_id] = checkpoints[-self._max_per_run:]

    def _remove_from_disk(self, trace_id: str) -> None:
        """删除磁盘文件."""
        try:
            file_path = self._storage_path / f"{trace_id}.jsonl"
            if file_path.exists():
                file_path.unlink()
        except OSError as e:
            logger.warning("Failed to remove checkpoint file: %s", e)


# ─── 全局单例 ─────────────────────────────────────────────────────────────────

_checkpoint_store: CheckpointStore | None = None
_cp_lock = threading.Lock()


def get_checkpoint_store() -> CheckpointStore:
    """获取全局 CheckpointStore 单例."""
    global _checkpoint_store
    if _checkpoint_store is None:
        with _cp_lock:
            if _checkpoint_store is None:
                _checkpoint_store = CheckpointStore()
    return _checkpoint_store
