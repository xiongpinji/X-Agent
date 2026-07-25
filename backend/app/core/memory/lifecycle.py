"""
记忆生命周期管理模块 - 归档、冷热分离和自动清理。

实现功能:
- 记忆归档策略
- 冷热数据分离
- 自动清理过期记忆
- 记忆恢复机制
- 生命周期事件追踪
- 存储优化
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

logger = logging.getLogger(__name__)


class MemoryState(StrEnum):
    """记忆状态。"""
    ACTIVE = "active"
    WARM = "warm"
    COLD = "cold"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class LifecyclePolicy:
    """记忆生命周期策略。"""
    # 时间阈值（天数）
    warm_threshold_days: int = 7
    cold_threshold_days: int = 30
    archive_threshold_days: int = 90
    delete_threshold_days: int = 365

    # 访问频率阈值
    warm_access_threshold: int = 10
    cold_access_threshold: int = 1

    # 重要性阈值
    preserve_importance_threshold: float = 0.7

    # 存储配置
    hot_storage_max_size_mb: int = 1000
    warm_storage_max_size_mb: int = 5000
    cold_storage_max_size_mb: int = 50000


@dataclass
class LifecycleEvent:
    """生命周期事件。"""
    memory_id: str
    event_type: str  # "created", "accessed", "archived", "restored", "deleted"
    old_state: MemoryState
    new_state: MemoryState
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class LifecycleStats:
    """生命周期统计信息。"""
    total_memories: int = 0
    active_count: int = 0
    warm_count: int = 0
    cold_count: int = 0
    archived_count: int = 0
    deleted_count: int = 0
    total_storage_mb: float = 0.0
    hot_storage_mb: float = 0.0
    warm_storage_mb: float = 0.0
    cold_storage_mb: float = 0.0
    last_cleanup_time: datetime | None = None
    cleanup_frequency_hours: int = 24


class MemoryLifecycleManager:
    """
    记忆生命周期管理系统。

    管理记忆的状态转换、存储分层和自动清理。
    """

    def __init__(
        self,
        policy: LifecyclePolicy | None = None,
        enable_auto_cleanup: bool = True,
        cleanup_interval_hours: int = 24,
    ):
        """
        初始化生命周期管理器。

        Args:
            policy: 生命周期策略
            enable_auto_cleanup: 是否启用自动清理
            cleanup_interval_hours: 清理间隔（小时）
        """
        self.policy = policy or LifecyclePolicy()
        self.enable_auto_cleanup = enable_auto_cleanup
        self.cleanup_interval_hours = cleanup_interval_hours

        # 记忆状态追踪
        self.memory_states: dict[str, MemoryState] = {}
        self.memory_metadata: dict[str, dict] = {}

        # 生命周期事件
        self._events: list[LifecycleEvent] = []

        # 统计信息
        self.stats = LifecycleStats()

        # 最后清理时间
        self._last_cleanup_time = datetime.now(UTC)

    async def process_memory_access(
        self,
        memory_id: str,
        current_time: datetime | None = None,
    ) -> None:
        """
        处理记忆访问。

        Args:
            memory_id: 记忆ID
            current_time: 当前时间
        """
        if current_time is None:
            current_time = datetime.now(UTC)

        if memory_id not in self.memory_metadata:
            self.memory_metadata[memory_id] = {
                "created_at": current_time,
                "last_accessed_at": current_time,
                "access_count": 1,
            }
            self.memory_states[memory_id] = MemoryState.ACTIVE
        else:
            self.memory_metadata[memory_id]["last_accessed_at"] = current_time
            self.memory_metadata[memory_id]["access_count"] += 1

        # 检查是否需要状态转换
        await self._check_state_transition(memory_id, current_time)

    async def _check_state_transition(
        self,
        memory_id: str,
        current_time: datetime,
    ) -> None:
        """
        检查并执行状态转换。

        Args:
            memory_id: 记忆ID
            current_time: 当前时间
        """
        current_state = self.memory_states.get(memory_id, MemoryState.ACTIVE)
        metadata = self.memory_metadata.get(memory_id, {})

        created_at = metadata.get("created_at", current_time)
        last_accessed = metadata.get("last_accessed_at", current_time)
        access_count = metadata.get("access_count", 0)
        importance = metadata.get("importance", 0.5)

        # 计算时间差（天数）
        days_since_creation = (current_time - created_at).days
        days_since_access = (current_time - last_accessed).days

        # 确定新状态
        new_state = current_state

        # 检查是否应该删除
        if (
            days_since_creation > self.policy.delete_threshold_days
            and importance < self.policy.preserve_importance_threshold
        ):
            new_state = MemoryState.DELETED
        # 检查是否应该归档
        elif (
            days_since_creation > self.policy.archive_threshold_days
            and access_count < self.policy.cold_access_threshold
        ):
            new_state = MemoryState.ARCHIVED
        # 检查是否应该转为冷存储
        elif (
            days_since_access > self.policy.cold_threshold_days
            and access_count < self.policy.cold_access_threshold
        ):
            new_state = MemoryState.COLD
        # 检查是否应该转为温存储
        elif (
            days_since_access > self.policy.warm_threshold_days
            and access_count < self.policy.warm_access_threshold
        ):
            new_state = MemoryState.WARM
        # 检查是否应该恢复为活跃
        elif (
            current_state in [MemoryState.WARM, MemoryState.COLD]
            and access_count > self.policy.warm_access_threshold
        ):
            new_state = MemoryState.ACTIVE

        # 执行状态转换
        if new_state != current_state:
            await self._transition_state(
                memory_id, current_state, new_state, current_time
            )

    async def _transition_state(
        self,
        memory_id: str,
        old_state: MemoryState,
        new_state: MemoryState,
        current_time: datetime,
    ) -> None:
        """
        执行状态转换。

        Args:
            memory_id: 记忆ID
            old_state: 旧状态
            new_state: 新状态
            current_time: 当前时间
        """
        self.memory_states[memory_id] = new_state

        # 记录事件
        event = LifecycleEvent(
            memory_id=memory_id,
            event_type="state_transition",
            old_state=old_state,
            new_state=new_state,
            timestamp=current_time,
            reason=f"Transitioned from {old_state} to {new_state}",
        )
        self._events.append(event)

        logger.info(
            f"Memory {memory_id} transitioned from {old_state} to {new_state}"
        )

    async def archive_memory(
        self,
        memory_id: str,
        reason: str = "",
    ) -> None:
        """
        归档记忆。

        Args:
            memory_id: 记忆ID
            reason: 归档原因
        """
        old_state = self.memory_states.get(memory_id, MemoryState.ACTIVE)

        if old_state != MemoryState.ARCHIVED:
            self.memory_states[memory_id] = MemoryState.ARCHIVED

            event = LifecycleEvent(
                memory_id=memory_id,
                event_type="archived",
                old_state=old_state,
                new_state=MemoryState.ARCHIVED,
                reason=reason,
            )
            self._events.append(event)

            logger.info(f"Memory {memory_id} archived: {reason}")

    async def restore_memory(
        self,
        memory_id: str,
        reason: str = "",
    ) -> None:
        """
        恢复记忆。

        Args:
            memory_id: 记忆ID
            reason: 恢复原因
        """
        old_state = self.memory_states.get(memory_id, MemoryState.ARCHIVED)

        if old_state in [MemoryState.ARCHIVED, MemoryState.COLD]:
            self.memory_states[memory_id] = MemoryState.ACTIVE

            event = LifecycleEvent(
                memory_id=memory_id,
                event_type="restored",
                old_state=old_state,
                new_state=MemoryState.ACTIVE,
                reason=reason,
            )
            self._events.append(event)

            logger.info(f"Memory {memory_id} restored: {reason}")

    async def delete_memory(
        self,
        memory_id: str,
        reason: str = "",
    ) -> None:
        """
        删除记忆。

        Args:
            memory_id: 记忆ID
            reason: 删除原因
        """
        old_state = self.memory_states.get(memory_id, MemoryState.ACTIVE)

        if old_state != MemoryState.DELETED:
            self.memory_states[memory_id] = MemoryState.DELETED

            event = LifecycleEvent(
                memory_id=memory_id,
                event_type="deleted",
                old_state=old_state,
                new_state=MemoryState.DELETED,
                reason=reason,
            )
            self._events.append(event)

            logger.info(f"Memory {memory_id} deleted: {reason}")

    async def cleanup_expired_memories(
        self,
        current_time: datetime | None = None,
    ) -> dict[str, int]:
        """
        清理过期的记忆。

        Args:
            current_time: 当前时间

        Returns:
            清理统计信息
        """
        if current_time is None:
            current_time = datetime.now(UTC)

        # 检查是否需要清理
        time_since_last_cleanup = (
            current_time - self._last_cleanup_time
        ).total_seconds() / 3600

        if time_since_last_cleanup < self.cleanup_interval_hours:
            return {"skipped": True}

        archived_count = 0
        deleted_count = 0

        for memory_id, metadata in self.memory_metadata.items():
            created_at = metadata.get("created_at", current_time)
            days_since_creation = (current_time - created_at).days

            # 删除过期的归档记忆
            if (
                self.memory_states.get(memory_id) == MemoryState.ARCHIVED
                and days_since_creation > self.policy.delete_threshold_days
            ):
                await self.delete_memory(
                    memory_id,
                    reason="Expired archived memory",
                )
                deleted_count += 1

        self._last_cleanup_time = current_time
        self.stats.last_cleanup_time = current_time

        logger.info(
            f"Cleanup complete: {archived_count} archived, "
            f"{deleted_count} deleted"
        )

        return {
            "archived": archived_count,
            "deleted": deleted_count,
        }

    def update_memory_metadata(
        self,
        memory_id: str,
        importance: float,
        tags: list[str] | None = None,
        custom_metadata: dict | None = None,
    ) -> None:
        """
        更新记忆元数据。

        Args:
            memory_id: 记忆ID
            importance: 重要性分数
            tags: 标签列表
            custom_metadata: 自定义元数据
        """
        if memory_id not in self.memory_metadata:
            self.memory_metadata[memory_id] = {}

        self.memory_metadata[memory_id]["importance"] = importance
        if tags:
            self.memory_metadata[memory_id]["tags"] = tags
        if custom_metadata:
            self.memory_metadata[memory_id].update(custom_metadata)

    def compute_stats(self) -> LifecycleStats:
        """
        计算生命周期统计信息。

        Returns:
            LifecycleStats 对象
        """
        stats = LifecycleStats()

        stats.total_memories = len(self.memory_states)
        stats.active_count = sum(
            1 for s in self.memory_states.values()
            if s == MemoryState.ACTIVE
        )
        stats.warm_count = sum(
            1 for s in self.memory_states.values()
            if s == MemoryState.WARM
        )
        stats.cold_count = sum(
            1 for s in self.memory_states.values()
            if s == MemoryState.COLD
        )
        stats.archived_count = sum(
            1 for s in self.memory_states.values()
            if s == MemoryState.ARCHIVED
        )
        stats.deleted_count = sum(
            1 for s in self.memory_states.values()
            if s == MemoryState.DELETED
        )

        # 计算存储大小（假设每个记忆平均1KB）
        avg_memory_size_kb = 1.0
        stats.hot_storage_mb = stats.active_count * avg_memory_size_kb / 1024
        stats.warm_storage_mb = stats.warm_count * avg_memory_size_kb / 1024
        stats.cold_storage_mb = (
            (stats.cold_count + stats.archived_count) * avg_memory_size_kb / 1024
        )
        stats.total_storage_mb = (
            stats.hot_storage_mb + stats.warm_storage_mb + stats.cold_storage_mb
        )

        stats.last_cleanup_time = self._last_cleanup_time
        stats.cleanup_frequency_hours = self.cleanup_interval_hours

        self.stats = stats
        return stats

    def get_events(
        self,
        memory_id: str | None = None,
        limit: int = 100,
    ) -> list[LifecycleEvent]:
        """
        获取生命周期事件。

        Args:
            memory_id: 可选的记忆ID过滤
            limit: 返回事件数量

        Returns:
            事件列表
        """
        events = self._events

        if memory_id:
            events = [e for e in events if e.memory_id == memory_id]

        return events[-limit:]

    def get_memory_state(self, memory_id: str) -> MemoryState:
        """获取记忆状态。"""
        return self.memory_states.get(memory_id, MemoryState.ACTIVE)

    def get_memory_metadata(self, memory_id: str) -> dict:
        """获取记忆元数据。"""
        return self.memory_metadata.get(memory_id, {})
