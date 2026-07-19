"""Bootstrap Key强制更换机制 - 确保首次登录时更换默认密钥。

SECURITY: 实现OWASP初始化安全最佳实践
- 检测默认Bootstrap Key的使用
- 首次登录时强制跳转到密钥更换页面
- 防止使用默认密钥进行生产操作
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BootstrapKeyStatus(BaseModel):
    """Bootstrap Key状态"""
    user_id: str
    has_changed_bootstrap_key: bool = False
    first_login_at: datetime | None = None
    bootstrap_key_changed_at: datetime | None = None
    is_bootstrap_key_required: bool = True  # 是否强制更换


class BootstrapKeyEnforcer:
    """Bootstrap Key强制更换执行器"""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._status_records: dict[str, BootstrapKeyStatus] = {}
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None

    def check_bootstrap_key_requirement(self, user_id: str) -> bool:
        """检查用户是否需要更换Bootstrap Key"""
        with self._lock:
            status = self._status_records.get(user_id)
            if status is None:
                # 新用户，需要更换
                status = BootstrapKeyStatus(
                    user_id=user_id,
                    first_login_at=datetime.now(UTC),
                    is_bootstrap_key_required=True,
                )
                self._status_records[user_id] = status
                logger.info(f"New user detected: {user_id}, Bootstrap Key change required")
                return True

            # 检查是否已更换
            if status.has_changed_bootstrap_key:
                return False

            return status.is_bootstrap_key_required

    def mark_bootstrap_key_changed(self, user_id: str) -> bool:
        """标记Bootstrap Key已更换"""
        with self._lock:
            status = self._status_records.get(user_id)
            if status is None:
                status = BootstrapKeyStatus(user_id=user_id)

            status.has_changed_bootstrap_key = True
            status.bootstrap_key_changed_at = datetime.now(UTC)
            status.is_bootstrap_key_required = False
            self._status_records[user_id] = status
            logger.info(f"Bootstrap Key changed for user: {user_id}")
            return True

    def get_status(self, user_id: str) -> BootstrapKeyStatus:
        """获取用户的Bootstrap Key状态"""
        with self._lock:
            status = self._status_records.get(user_id)
            if status is None:
                status = BootstrapKeyStatus(user_id=user_id)
                self._status_records[user_id] = status
            return status

    def list_users_requiring_change(self) -> list[BootstrapKeyStatus]:
        """列出需要更换Bootstrap Key的用户"""
        with self._lock:
            return [
                status
                for status in self._status_records.values()
                if status.is_bootstrap_key_required and not status.has_changed_bootstrap_key
            ]


# 全局实例
_bootstrap_key_enforcer: BootstrapKeyEnforcer | None = None


def get_bootstrap_key_enforcer(
    storage_path: str | Path | None = None,
) -> BootstrapKeyEnforcer:
    """获取Bootstrap Key强制更换执行器实例"""
    global _bootstrap_key_enforcer
    if _bootstrap_key_enforcer is None:
        _bootstrap_key_enforcer = BootstrapKeyEnforcer(storage_path=storage_path)
    return _bootstrap_key_enforcer
