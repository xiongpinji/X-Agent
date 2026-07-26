"""Goal Mode 目标记录的 JSON 文件持久化存储。

设计说明
========
- 复用仓内 ``admin_store_file`` 的原子写入先例: 先写临时文件再 rename,
  避免半写状态。
- 存储内容为 **可 JSON 序列化的目标快照** (由 api/goals.py 负责序列化
  运行时对象, 如 SubGoal / GoalControl)。
- 默认路径 ``data/goals.json``, 可用环境变量 ``X_AGENT_GOALS_STORE_PATH``
  覆盖 (测试隔离用)。
- 内存中以 list 持有全部目标记录, api 层直接引用同一 list, 保持与旧
  内存 stub 的 ``_goals`` 契约兼容 (单测可 ``_goals.clear()``)。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = "data/goals.json"
ENV_STORE_PATH = "X_AGENT_GOALS_STORE_PATH"


class GoalStore:
    """JSON 文件持久化的目标存储, 内存 list + 每次变更后原子落盘。"""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._path = Path(
            storage_path
            or os.environ.get(ENV_STORE_PATH)
            or DEFAULT_STORE_PATH
        )
        self._lock = RLock()
        self.goals: list[dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            goals = payload.get("goals", [])
            if isinstance(goals, list):
                self.goals = [g for g in goals if isinstance(g, dict)]
            logger.info(
                "GoalStore: loaded %d goals from %s", len(self.goals), self._path
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("GoalStore: failed to load %s: %s", self._path, exc)

    def save(self, snapshots: list[dict[str, Any]] | None = None) -> None:
        """原子写入目标快照列表。

        调用方传入 ``snapshots`` 时写入该序列化结果; 否则序列化 ``self.goals``
        中已是纯 dict 的记录原样写入。
        """
        with self._lock:
            payload = {"goals": snapshots if snapshots is not None else self.goals}
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=str(self._path.parent),
                suffix=".tmp",
            )
            try:
                with open(fd, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False, indent=2)
                Path(tmp_name).replace(self._path)
            except BaseException:
                try:
                    Path(tmp_name).unlink(missing_ok=True)
                except OSError:
                    pass
                raise

    # ------------------------------------------------------------------
    # 便捷查询
    # ------------------------------------------------------------------

    def find(self, goal_id: str) -> dict[str, Any] | None:
        with self._lock:
            for g in self.goals:
                if g.get("id") == goal_id:
                    return g
        return None
