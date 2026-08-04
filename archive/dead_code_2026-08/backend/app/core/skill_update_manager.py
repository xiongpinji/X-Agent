"""技能更新管理系统 - 支持检查更新、一键更新、自动更新、更新通知"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class UpdateStatus(StrEnum):
    """更新状态"""
    AVAILABLE = "available"  # 有可用更新
    CHECKING = "checking"  # 检查中
    DOWNLOADING = "downloading"  # 下载中
    INSTALLING = "installing"  # 安装中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    UP_TO_DATE = "up_to_date"  # 已是最新版本


class UpdatePriority(StrEnum):
    """更新优先级"""
    LOW = "low"  # 低 - 新功能
    MEDIUM = "medium"  # 中 - 改进
    HIGH = "high"  # 高 - 错误修复
    CRITICAL = "critical"  # 严重 - 安全补丁


@dataclass
class SkillUpdate:
    """技能更新信息"""
    skill_id: str
    current_version: str
    new_version: str
    release_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    changelog: str = ""
    priority: UpdatePriority = UpdatePriority.MEDIUM
    breaking_changes: list[str] = field(default_factory=list)
    migration_guide: str = ""
    download_url: str = ""
    file_size_bytes: int = 0
    checksum: str = ""
    status: UpdateStatus = UpdateStatus.AVAILABLE
    progress: int = 0  # 0-100
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "skill_id": self.skill_id,
            "current_version": self.current_version,
            "new_version": self.new_version,
            "release_date": self.release_date.isoformat(),
            "changelog": self.changelog,
            "priority": self.priority.value,
            "breaking_changes": self.breaking_changes,
            "migration_guide": self.migration_guide,
            "download_url": self.download_url,
            "file_size_bytes": self.file_size_bytes,
            "checksum": self.checksum,
            "status": self.status.value,
            "progress": self.progress,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class UpdateNotification:
    """更新通知"""
    id: str
    skill_id: str
    user_id: str
    update: SkillUpdate
    read: bool = False
    dismissed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "user_id": self.user_id,
            "update": self.update.to_dict(),
            "read": self.read,
            "dismissed": self.dismissed,
            "created_at": self.created_at.isoformat(),
        }


class SkillUpdateManager:
    """技能更新管理器"""

    def __init__(self):
        self.available_updates: dict[str, SkillUpdate] = {}  # skill_id -> update
        self.update_history: dict[str, list[SkillUpdate]] = {}  # skill_id -> [updates]
        self.auto_update_enabled: dict[str, bool] = {}  # skill_id -> enabled
        self.notifications: dict[str, UpdateNotification] = {}  # notification_id -> notification
        self.user_notifications: dict[str, list[str]] = {}  # user_id -> [notification_ids]
        self.installed_versions: dict[str, str] = {}  # skill_id -> version

    def check_updates(self, skill_id: str) -> tuple[bool, str | None, SkillUpdate | None]:
        """检查更新"""
        try:
            # 获取当前版本
            current_version = self.installed_versions.get(skill_id)
            if not current_version:
                return False, "技能未安装", None

            # 模拟检查更新（实际应该从服务器获取）
            # 这里简化实现
            if skill_id in self.available_updates:
                update = self.available_updates[skill_id]
                logger.info(f"检查更新: {skill_id} -> {update.new_version}")
                return True, None, update

            return True, None, None

        except Exception as e:
            error = f"检查更新失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error, None

    def check_all_updates(self) -> tuple[bool, str | None, list[SkillUpdate]]:
        """检查所有技能的更新"""
        try:
            updates = []

            for skill_id in self.installed_versions:
                success, error, update = self.check_updates(skill_id)
                if success and update:
                    updates.append(update)

            logger.info(f"检查完成，发现 {len(updates)} 个更新")
            return True, None, updates

        except Exception as e:
            error = f"检查所有更新失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error, []

    def update_skill(
        self,
        skill_id: str,
        new_version: str,
        user_id: str = "",
    ) -> tuple[bool, str | None, SkillUpdate | None]:
        """更新技能"""
        try:
            # 获取更新信息
            update = self.available_updates.get(skill_id)
            if not update:
                return False, "没有可用的更新", None

            if update.new_version != new_version:
                return False, f"版本不匹配: 期望 {update.new_version}, 得到 {new_version}", None

            # 更新状态
            update.status = UpdateStatus.DOWNLOADING
            update.progress = 0

            # 模拟下载和安装
            update.progress = 50
            update.status = UpdateStatus.INSTALLING

            # 更新版本
            self.installed_versions[skill_id] = new_version
            update.status = UpdateStatus.COMPLETED
            update.progress = 100
            update.updated_at = datetime.now(UTC)

            # 记录到历史
            if skill_id not in self.update_history:
                self.update_history[skill_id] = []
            self.update_history[skill_id].append(update)

            # 移除可用更新
            del self.available_updates[skill_id]

            logger.info(f"更新技能: {skill_id} -> {new_version} (用户: {user_id})")
            return True, None, update

        except Exception as e:
            error = f"更新技能失败: {e!s}"
            logger.error(error, exc_info=True)
            if skill_id in self.available_updates:
                self.available_updates[skill_id].status = UpdateStatus.FAILED
                self.available_updates[skill_id].error_message = error
            return False, error, None

    def enable_auto_update(self, skill_id: str) -> tuple[bool, str | None]:
        """启用自动更新"""
        try:
            self.auto_update_enabled[skill_id] = True
            logger.info(f"启用自动更新: {skill_id}")
            return True, None
        except Exception as e:
            error = f"启用自动更新失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def disable_auto_update(self, skill_id: str) -> tuple[bool, str | None]:
        """禁用自动更新"""
        try:
            self.auto_update_enabled[skill_id] = False
            logger.info(f"禁用自动更新: {skill_id}")
            return True, None
        except Exception as e:
            error = f"禁用自动更新失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def is_auto_update_enabled(self, skill_id: str) -> bool:
        """检查自动更新是否启用"""
        return self.auto_update_enabled.get(skill_id, False)

    def get_update_history(
        self,
        skill_id: str,
        limit: int = 20,
    ) -> list[SkillUpdate]:
        """获取更新历史"""
        history = self.update_history.get(skill_id, [])
        return history[-limit:]

    def get_all_update_history(self, limit: int = 50) -> list[SkillUpdate]:
        """获取所有更新历史"""
        all_updates = []
        for updates in self.update_history.values():
            all_updates.extend(updates)

        # 按时间排序
        all_updates.sort(key=lambda u: u.updated_at, reverse=True)
        return all_updates[:limit]

    def create_notification(
        self,
        skill_id: str,
        user_id: str,
        update: SkillUpdate,
    ) -> tuple[bool, str | None, UpdateNotification | None]:
        """创建更新通知"""
        try:
            import uuid
            notification = UpdateNotification(
                id=str(uuid.uuid4()),
                skill_id=skill_id,
                user_id=user_id,
                update=update,
            )

            self.notifications[notification.id] = notification

            # 添加到用户通知列表
            if user_id not in self.user_notifications:
                self.user_notifications[user_id] = []
            self.user_notifications[user_id].append(notification.id)

            logger.info(f"创建通知: {skill_id} for {user_id}")
            return True, None, notification

        except Exception as e:
            error = f"创建通知失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error, None

    def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 20,
    ) -> list[UpdateNotification]:
        """获取用户通知"""
        notification_ids = self.user_notifications.get(user_id, [])
        notifications = [
            self.notifications[nid] for nid in notification_ids
            if nid in self.notifications
        ]

        if unread_only:
            notifications = [n for n in notifications if not n.read]

        # 按时间排序
        notifications.sort(key=lambda n: n.created_at, reverse=True)
        return notifications[:limit]

    def mark_notification_as_read(self, notification_id: str) -> tuple[bool, str | None]:
        """标记通知为已读"""
        try:
            notification = self.notifications.get(notification_id)
            if not notification:
                return False, "通知不存在"

            notification.read = True
            logger.info(f"标记通知为已读: {notification_id}")
            return True, None

        except Exception as e:
            error = f"标记通知失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def dismiss_notification(self, notification_id: str) -> tuple[bool, str | None]:
        """忽略通知"""
        try:
            notification = self.notifications.get(notification_id)
            if not notification:
                return False, "通知不存在"

            notification.dismissed = True
            logger.info(f"忽略通知: {notification_id}")
            return True, None

        except Exception as e:
            error = f"忽略通知失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def get_unread_count(self, user_id: str) -> int:
        """获取未读通知数"""
        notifications = self.get_notifications(user_id, unread_only=True)
        return len([n for n in notifications if not n.dismissed])

    def register_available_update(
        self,
        skill_id: str,
        current_version: str,
        new_version: str,
        changelog: str = "",
        priority: UpdatePriority = UpdatePriority.MEDIUM,
        breaking_changes: list[str] | None = None,
        migration_guide: str = "",
    ) -> tuple[bool, str | None]:
        """注册可用更新"""
        try:
            update = SkillUpdate(
                skill_id=skill_id,
                current_version=current_version,
                new_version=new_version,
                changelog=changelog,
                priority=priority,
                breaking_changes=breaking_changes or [],
                migration_guide=migration_guide,
            )

            self.available_updates[skill_id] = update

            logger.info(f"注册更新: {skill_id}@{new_version}")
            return True, None

        except Exception as e:
            error = f"注册更新失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def get_critical_updates(self) -> list[SkillUpdate]:
        """获取严重更新"""
        return [
            u for u in self.available_updates.values()
            if u.priority == UpdatePriority.CRITICAL
        ]

    def get_update_stats(self) -> dict[str, Any]:
        """获取更新统计"""
        return {
            "available_updates": len(self.available_updates),
            "critical_updates": len(self.get_critical_updates()),
            "auto_update_enabled_count": sum(1 for v in self.auto_update_enabled.values() if v),
            "total_updates_installed": sum(len(h) for h in self.update_history.values()),
        }


# 全局实例
_skill_update_manager: SkillUpdateManager | None = None


def get_skill_update_manager() -> SkillUpdateManager:
    """获取技能更新管理器实例"""
    global _skill_update_manager
    if _skill_update_manager is None:
        _skill_update_manager = SkillUpdateManager()
    return _skill_update_manager


__all__ = [
    "SkillUpdate",
    "SkillUpdateManager",
    "UpdateNotification",
    "UpdatePriority",
    "UpdateStatus",
    "get_skill_update_manager",
]
