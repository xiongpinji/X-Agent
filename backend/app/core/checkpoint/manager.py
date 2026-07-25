"""检查点管理器。"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.app.core.checkpoint.snapshot import ExecutionSnapshot

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path("data/checkpoints")


class CheckpointManager:
    """管理检查点的创建、查询、清理。

    策略：
    - 自动：每 N 次工具调用 / 每 M 秒 / 阶段切换时
    - 手动：API 触发
    - 触发：检测到即将超时 / 资源压力
    """

    def __init__(
        self,
        store_dir: Path | str | None = None,
        auto_interval: int = 5,
        max_checkpoints_per_run: int = 50,
        ttl_hours: int = 72,
    ) -> None:
        self._dir = Path(store_dir) if store_dir else _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._auto_interval = auto_interval
        self._max_per_run = max_checkpoints_per_run
        self._ttl = timedelta(hours=ttl_hours)
        self._call_counters: dict[str, int] = {}

    def should_checkpoint(self, run_id: str, tool_call_count: int) -> bool:
        """判断是否应自动创建检查点。"""
        return tool_call_count > 0 and tool_call_count % self._auto_interval == 0

    def create_checkpoint(
        self,
        run_id: str,
        step_index: int,
        trajectory: list[dict[str, Any]] | None = None,
        plan: list[dict[str, Any]] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        partial_results: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ExecutionSnapshot:
        """创建检查点。"""
        checkpoint_id = f"ckpt-{uuid.uuid4().hex[:8]}"
        snapshot = ExecutionSnapshot(
            run_id=run_id,
            checkpoint_id=checkpoint_id,
            step_index=step_index,
            trajectory=trajectory or [],
            plan=plan or [],
            tool_calls=tool_calls or [],
            partial_results=partial_results or {},
            context=context or {},
        )
        self._save(snapshot)
        logger.info(f"[{run_id}] 检查点已创建: {checkpoint_id} (step={step_index})")
        return snapshot

    def get_latest(self, run_id: str) -> ExecutionSnapshot | None:
        """获取最新有效检查点。"""
        checkpoints = self.list_checkpoints(run_id)
        active = [c for c in checkpoints if c.status == "active"]
        if not active:
            return None
        return max(active, key=lambda c: c.created_at)

    def list_checkpoints(self, run_id: str) -> list[ExecutionSnapshot]:
        """列出某次运行的所有检查点。"""
        run_dir = self._dir / run_id.replace("/", "_").replace("\\", "_")
        if not run_dir.exists():
            return []
        results = []
        for f in run_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append(ExecutionSnapshot.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue
        return sorted(results, key=lambda c: c.created_at)

    def cleanup_expired(self) -> int:
        """清理过期检查点。"""
        now = datetime.now(UTC)
        removed = 0
        for run_dir in self._dir.iterdir():
            if not run_dir.is_dir():
                continue
            for f in run_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    created = datetime.fromisoformat(data.get("created_at", now.isoformat()))
                    if now - created > self._ttl:
                        f.unlink()
                        removed += 1
                except (json.JSONDecodeError, ValueError):
                    continue
            # 删除空目录
            if not any(run_dir.iterdir()):
                run_dir.rmdir()
        if removed:
            logger.info(f"清理过期检查点: {removed} 个")
        return removed

    def _save(self, snapshot: ExecutionSnapshot) -> None:
        run_dir = self._dir / snapshot.run_id.replace("/", "_").replace("\\", "_")
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / f"{snapshot.checkpoint_id}.json"
        path.write_text(snapshot.to_json(), encoding="utf-8")
