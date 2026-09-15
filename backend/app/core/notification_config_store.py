"""通知渠道配置存储 - JSON 文件持久化。

设计说明
========
- 存储 ``/feedback`` 页 Notifications tab 里的「通知渠道配置」(email / slack)。
- 这是 ``core/notification_subscriptions.py`` 的同胞: 同一条「JSON 文件 + 每次写
  操作后原子重写整个文件」的模式, 不发明新轮子。
- 路径通过环境变量 ``XAGENT_NOTIFICATION_CONFIG_STORE_PATH`` 覆盖,
  默认 ``data/notification_configs.json``。
- 与 ``core/notification_system.NotificationPreference`` 的区别: 后者是
  「用户 × 事件类型 → 频道列表」的偏好矩阵, 本模块存的是「一条条投递目标」。
  两者概念不同, 不能互相替代。

范围说明
========
本模块只负责「存取」。``triggers`` 只作为**被校验的枚举**存下来, 本版本
不做事件分发 (那是第二个功能: 需要 hook 反馈写入路径 + 队列/重试/去重)。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Literal, get_args
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = "data/notification_configs.json"

# 唯一的枚举定义 —— 前端 ``components/feedback/NotificationSettings.tsx``
# 里硬编码的 6 个 trigger 必须与这里逐字一致 (由单测锁定)。
NotificationTrigger = Literal[
    "new_feedback",
    "feedback_resolved",
    "high_priority_feedback",
    "critical_feedback",
    "sentiment_negative",
    "daily_summary",
]

# 由 Literal 反推, 保证「枚举」与「可列举的清单」不会各写一份而漂移。
NOTIFICATION_TRIGGERS: tuple[str, ...] = get_args(NotificationTrigger)


class NotificationConfigRecord(BaseModel):
    """一条通知渠道配置。

    字段口径对齐前端 ``NotificationConfig`` (services/feedback.ts), 但保持
    Python 侧的 snake_case: ``created_at`` / ``updated_at`` 由 service 层的
    adapter 转成 camelCase, 与 ``adaptFeedback`` 的做法一致。

    - ``target``: ``email`` 时是收件邮箱, ``slack`` 时是 Incoming Webhook URL。
    - ``triggers``: 允许为空列表 (前端自己要求 >=1, 后端不做过度约束);
      但**成员**必须是 ``NotificationTrigger`` 之一。
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["email", "slack"]
    enabled: bool = True
    target: str = Field(min_length=1)
    triggers: list[NotificationTrigger] = Field(default_factory=list)
    tenant_id: str = "default"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# 允许通过 update() 修改的字段。id / tenant_id / created_at 不在其中:
# 它们由 store 负责, 不交给调用方 (见 update() 的 ValueError 分支)。
_MUTABLE_FIELDS = frozenset({"type", "enabled", "target", "triggers"})


class NotificationConfigStore:
    """JSON 文件持久化的通知渠道配置存储。"""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        env_path = os.environ.get("XAGENT_NOTIFICATION_CONFIG_STORE_PATH")
        self._storage_path = Path(storage_path or env_path or DEFAULT_STORE_PATH)
        self._records: dict[str, NotificationConfigRecord] = {}
        self._lock = RLock()
        self._load_from_disk()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            with self._storage_path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            # 整个文件不可读 -> 从空开始, 不阻断服务启动。
            logger.warning(
                "NotificationConfigStore: failed to load %s: %s",
                self._storage_path,
                exc,
            )
            return

        # 逐条容错: 单条记录坏掉只丢它自身, 不牵连同文件里的其它渠道。
        # (配置文件是手可编辑的, 一处手误不该清空全部配置。)
        skipped = 0
        for item in payload.get("configs", []):
            try:
                record = NotificationConfigRecord.model_validate(item)
            except ValidationError as exc:
                skipped += 1
                logger.warning(
                    "NotificationConfigStore: skipping invalid record in %s: %s",
                    self._storage_path,
                    exc,
                )
                continue
            self._records[record.id] = record
        logger.info(
            "NotificationConfigStore: loaded %d configs from %s (skipped %d)",
            len(self._records),
            self._storage_path,
            skipped,
        )

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "configs": [record.model_dump(mode="json") for record in self._records.values()],
        }
        # 原子写入: 先写同目录临时文件再 os.replace
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._storage_path.parent),
            prefix=self._storage_path.name + ".",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self._storage_path)
        except OSError:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, record: NotificationConfigRecord) -> NotificationConfigRecord:
        """新增配置。

        刻意**不做去重**: 样板 push subscription 按 endpoint 去重, 是因为浏览器
        会反复上报同一个 endpoint。这里是一次显式创建, 静默合并会吞掉用户意图。
        """
        with self._lock:
            self._records[record.id] = record
            self._persist()
            return record

    def get(self, config_id: str) -> NotificationConfigRecord | None:
        with self._lock:
            return self._records.get(config_id)

    def update(
        self, config_id: str, changes: dict[str, Any]
    ) -> NotificationConfigRecord | None:
        """局部更新; 返回更新后的记录, 记录不存在时返回 ``None``。

        - 只接受 ``_MUTABLE_FIELDS`` 内的键, 其余一律 ``ValueError``。
          用 ``model_copy(update=...)`` 直接落未知键会把它悄悄写进记录
          (不校验、不报错), 那比抛错更难查。
        - ``updated_at`` 由 store 无条件刷新。
        """
        unknown = set(changes) - _MUTABLE_FIELDS
        if unknown:
            raise ValueError(
                f"field(s) not updatable: {sorted(unknown)}; "
                f"allowed: {sorted(_MUTABLE_FIELDS)}"
            )
        with self._lock:
            record = self._records.get(config_id)
            if record is None:
                return None
            merged = record.model_dump()
            merged.update(changes)
            merged["updated_at"] = datetime.now(UTC)
            updated = NotificationConfigRecord.model_validate(merged)
            self._records[config_id] = updated
            self._persist()
            return updated

    def remove(self, config_id: str) -> bool:
        with self._lock:
            if config_id not in self._records:
                return False
            del self._records[config_id]
            self._persist()
            return True

    def list_for_tenant(self, tenant_id: str) -> list[NotificationConfigRecord]:
        with self._lock:
            return [r for r in self._records.values() if r.tenant_id == tenant_id]

    def list_tenants(self) -> list[str]:
        """返回「出现过配置」的租户 id（去重 + 排序）。

        存在的理由：``list_for_tenant`` 要求**已知**租户，但定时类任务（每日摘要）
        没有 ``principal`` —— 它必须先知道「有哪些租户」才能决定给谁跑。此前全仓
        没有任何枚举租户的能力（``api/tenants.py`` 是另一套，不读这张表）。

        只返回 id、不返回记录：调用方一般还要按 ``enabled`` / ``triggers`` 再过滤，
        那个过滤留在各自的语义层（见 ``core/daily_summary.py``），不在这里预判。
        """
        with self._lock:
            return sorted({r.tenant_id for r in self._records.values()})

    def count(self) -> int:
        with self._lock:
            return len(self._records)


# 全局存储实例(惰性初始化, 便于测试用环境变量覆盖路径)
_notification_config_store: NotificationConfigStore | None = None


def get_notification_config_store() -> NotificationConfigStore:
    """获取全局通知渠道配置存储实例。"""
    global _notification_config_store
    if _notification_config_store is None:
        _notification_config_store = NotificationConfigStore()
    return _notification_config_store


def reset_notification_config_store() -> None:
    """重置全局实例(测试隔离用)。"""
    global _notification_config_store
    _notification_config_store = None
