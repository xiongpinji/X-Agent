"""通知投递记录存储 - JSON 文件持久化。

为什么需要它
============
``ConsoleNotificationProvider.is_configured()`` 恒返回 True、``send()`` 恒返回
``success=True``, 但它只写一行日志。于是「用户在 Notifications tab 配了一个渠道 →
按要求的事件发生了 → 什么都没发出去 → 界面上毫无痕迹」是一条真实可达的路径。

这张表是那条路径**唯一**可见的出口: 每次分发落一条记录, 含
``delivered=False`` 与**人话原因**。只打日志不够 —— 用户不会去翻服务端日志。

机密与隐私
==========
``target`` 可能是收件邮箱或 Slack Incoming Webhook URL —— 后者本身就是凭据。
所以本模块**只接受已经脱敏的** ``target_hint`` (由 ``notification_dispatch`` 生成),
不存原文。落盘前的最后一道保险是单测: 断言持久化文件里既不含明文邮箱也不含
完整 webhook URL。

与 ``notification_config_store`` 同款
====================================
JSON 文件 + 每次写操作原子重写整个文件 + 环境变量覆盖路径 + 惰性全局单例。
上限裁剪 (``MAX_RECORDS``) 是新增的一条: 投递记录是只增不减的流水, 无上限会
让文件无限长。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = "data/notification_deliveries.json"

# 只保留最近 N 条。流水会一直增长, 而查询端点只需要「最近发生了什么」。
MAX_RECORDS = 500


class DeliveryRecord(BaseModel):
    """一次事件分发对**一个渠道**的投递结果。

    - ``delivered``: 真的投出去了吗。这是本记录唯一有意义的字段 —— 它不允许
      因为 provider 自称成功就为 True (见模块 docstring)。
    - ``detail``: 人话说明。失败时必须说清**为什么**, 而不是只给一个 False。
    - ``target_hint``: 脱敏后的投递目标。**不是**原文。
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    trigger: str
    config_id: str = ""
    channel: Literal["email", "slack"] = "email"
    provider: str = ""
    target_hint: str = ""
    delivered: bool = False
    detail: str = ""
    subject: str = ""
    feedback_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NotificationDispatchStore:
    """JSON 文件持久化的投递记录存储 (只追加 + 上限裁剪)。"""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        env_path = os.environ.get("XAGENT_NOTIFICATION_DISPATCH_STORE_PATH")
        self._storage_path = Path(storage_path or env_path or DEFAULT_STORE_PATH)
        self._records: list[DeliveryRecord] = []
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
            # 与 notification_config_store 同口径: 整个文件不可读 -> 从空开始,
            # 不阻断服务启动。投递记录是观测数据, 不是业务事实。
            logger.warning(
                "NotificationDispatchStore: failed to load %s: %s",
                self._storage_path,
                exc,
            )
            return

        # 逐条容错: 单条坏掉只丢它自己。
        skipped = 0
        for item in payload.get("deliveries", []):
            try:
                self._records.append(DeliveryRecord.model_validate(item))
            except ValidationError as exc:
                skipped += 1
                logger.warning(
                    "NotificationDispatchStore: skipping invalid record in %s: %s",
                    self._storage_path,
                    exc,
                )
        logger.info(
            "NotificationDispatchStore: loaded %d deliveries from %s (skipped %d)",
            len(self._records),
            self._storage_path,
            skipped,
        )

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "deliveries": [r.model_dump(mode="json") for r in self._records],
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

    def append(self, record: DeliveryRecord) -> DeliveryRecord:
        """追加一条记录, 超出 ``MAX_RECORDS`` 时丢弃最旧的那些。"""
        with self._lock:
            self._records.append(record)
            if len(self._records) > MAX_RECORDS:
                del self._records[: len(self._records) - MAX_RECORDS]
            self._persist()
            return record

    def list_for_tenant(
        self,
        tenant_id: str,
        limit: int = 50,
        trigger: str | None = None,
        config_id: str | None = None,
    ) -> list[DeliveryRecord]:
        """按租户取最近的记录 (最新在前)。

        先按条件过滤再切片 —— 反过来会先丢掉窗口外的匹配项, 让「最近 50 条」
        在有过滤条件时变成「最近 50 条里恰好匹配的」, 两者不是一回事。
        """
        with self._lock:
            matched = [
                r
                for r in self._records
                if r.tenant_id == tenant_id
                and (trigger is None or r.trigger == trigger)
                and (config_id is None or r.config_id == config_id)
            ]
            return list(reversed(matched))[:limit]

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def clear(self) -> None:
        """清空 (测试隔离用)。"""
        with self._lock:
            self._records = []
            self._persist()


# 全局存储实例(惰性初始化, 便于测试用环境变量覆盖路径)
_dispatch_store: NotificationDispatchStore | None = None


def get_notification_dispatch_store() -> NotificationDispatchStore:
    """获取全局投递记录存储实例。"""
    global _dispatch_store
    if _dispatch_store is None:
        _dispatch_store = NotificationDispatchStore()
    return _dispatch_store


def reset_notification_dispatch_store() -> None:
    """重置全局实例(测试隔离用)。"""
    global _dispatch_store
    _dispatch_store = None


__all__ = [
    "DEFAULT_STORE_PATH",
    "MAX_RECORDS",
    "DeliveryRecord",
    "NotificationDispatchStore",
    "get_notification_dispatch_store",
    "reset_notification_dispatch_store",
]
