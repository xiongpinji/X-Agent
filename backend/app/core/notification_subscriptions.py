"""Web Push 订阅存储 - JSON 文件持久化。

设计说明
========
- 存储前端 ``pushNotificationManager`` 上报的 Web Push subscription
  (endpoint + p256dh/auth keys)。
- 写入策略与 ``admin_store_file`` 先例一致: 每次写操作后原子写入整个
  JSON 文件(先写临时文件再 ``os.replace``), 避免半写状态。
- 路径通过环境变量 ``XAGENT_NOTIFICATION_SUBSCRIPTION_STORE_PATH`` 覆盖,
  默认 ``data/notification_subscriptions.json``。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = "data/notification_subscriptions.json"


class PushSubscriptionKeys(BaseModel):
    """Web Push subscription keys"""

    p256dh: str
    auth: str


class PushSubscriptionRecord(BaseModel):
    """一条 push subscription 记录"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    endpoint: str
    keys: PushSubscriptionKeys
    user_id: str = "anonymous"
    tenant_id: str = "default"
    user_agent: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NotificationSubscriptionStore:
    """JSON 文件持久化的 push subscription 存储。"""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        env_path = os.environ.get("XAGENT_NOTIFICATION_SUBSCRIPTION_STORE_PATH")
        self._storage_path = Path(storage_path or env_path or DEFAULT_STORE_PATH)
        self._records: dict[str, PushSubscriptionRecord] = {}
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
            for item in payload.get("subscriptions", []):
                record = PushSubscriptionRecord.model_validate(item)
                self._records[record.id] = record
            logger.info(
                "NotificationSubscriptionStore: loaded %d subscriptions from %s",
                len(self._records),
                self._storage_path,
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "NotificationSubscriptionStore: failed to load %s: %s",
                self._storage_path,
                exc,
            )

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "subscriptions": [
                record.model_dump(mode="json") for record in self._records.values()
            ],
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

    def add(self, record: PushSubscriptionRecord) -> PushSubscriptionRecord:
        """新增订阅; 同一 endpoint 去重(更新归属与时间)。"""
        with self._lock:
            for existing in self._records.values():
                if existing.endpoint == record.endpoint:
                    existing.keys = record.keys
                    existing.user_id = record.user_id
                    existing.tenant_id = record.tenant_id
                    existing.user_agent = record.user_agent
                    self._persist()
                    return existing
            self._records[record.id] = record
            self._persist()
            return record

    def get(self, subscription_id: str) -> PushSubscriptionRecord | None:
        with self._lock:
            return self._records.get(subscription_id)

    def remove(self, subscription_id: str) -> bool:
        with self._lock:
            if subscription_id not in self._records:
                return False
            del self._records[subscription_id]
            self._persist()
            return True

    def remove_by_endpoint(self, endpoint: str) -> bool:
        with self._lock:
            for sid, record in list(self._records.items()):
                if record.endpoint == endpoint:
                    del self._records[sid]
                    self._persist()
                    return True
            return False

    def list_for_user(self, user_id: str) -> list[PushSubscriptionRecord]:
        with self._lock:
            return [r for r in self._records.values() if r.user_id == user_id]

    def count(self) -> int:
        with self._lock:
            return len(self._records)


# 全局存储实例(惰性初始化, 便于测试用环境变量覆盖路径)
_subscription_store: NotificationSubscriptionStore | None = None


def get_subscription_store() -> NotificationSubscriptionStore:
    """获取全局 push subscription 存储实例。"""
    global _subscription_store
    if _subscription_store is None:
        _subscription_store = NotificationSubscriptionStore()
    return _subscription_store


def reset_subscription_store() -> None:
    """重置全局实例(测试隔离用)。"""
    global _subscription_store
    _subscription_store = None
