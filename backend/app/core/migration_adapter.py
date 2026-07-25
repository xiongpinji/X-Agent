"""
双写模式适配器 - 支持从旧存储到新存储的平滑迁移
"""
from __future__ import annotations

import logging
from typing import Any

from backend.app.models.api_key_store import get_api_key_store
from backend.app.models.approval_store import get_approval_store
from backend.app.models.csrf_token_store import get_csrf_token_store
from backend.app.models.rate_limiter import get_rate_limiter
from backend.app.models.user_store import get_user_store

logger = logging.getLogger(__name__)


class MigrationAdapter:
    """双写模式适配器"""

    def __init__(
        self,
        old_user_store: Any = None,
        old_api_key_store: Any = None,
        old_approval_store: Any = None,
        old_rate_limiter: Any = None,
        old_csrf_token_store: Any = None,
        enable_dual_write: bool = True,
        read_from_new: bool = False,
    ):
        """
        初始化适配器

        Args:
            old_*_store: 旧存储实现
            enable_dual_write: 是否启用双写模式
            read_from_new: 是否从新存储读取（旧存储作为备份）
        """
        self.old_user_store = old_user_store
        self.old_api_key_store = old_api_key_store
        self.old_approval_store = old_approval_store
        self.old_rate_limiter = old_rate_limiter
        self.old_csrf_token_store = old_csrf_token_store

        self.new_user_store = get_user_store()
        self.new_api_key_store = get_api_key_store()
        self.new_approval_store = get_approval_store()
        self.new_rate_limiter = get_rate_limiter()
        self.new_csrf_token_store = get_csrf_token_store()

        self.enable_dual_write = enable_dual_write
        self.read_from_new = read_from_new

        self.stats = {
            "user_writes": 0,
            "api_key_writes": 0,
            "approval_writes": 0,
            "rate_limit_writes": 0,
            "csrf_token_writes": 0,
            "write_failures": 0,
        }

    # ==================== 用户存储 ====================

    async def create_user(self, **kwargs) -> Any:
        """创建用户 - 双写"""
        try:
            # 写入新存储
            result = await self.new_user_store.create_user(**kwargs)

            # 双写到旧存储
            if self.enable_dual_write and self.old_user_store:
                try:
                    await self.old_user_store.create_user(**kwargs)
                except Exception as e:
                    logger.warning(f"旧存储写入失败: {e}")
                    self.stats["write_failures"] += 1

            self.stats["user_writes"] += 1
            return result
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            raise

    async def get_user_by_id(self, user_id: str) -> Any:
        """获取用户 - 从新存储读取"""
        if self.read_from_new:
            return await self.new_user_store.get_user_by_id(user_id)
        else:
            # 从旧存储读取，新存储作为备份
            if self.old_user_store:
                return await self.old_user_store.get_user_by_id(user_id)
            return await self.new_user_store.get_user_by_id(user_id)

    async def update_user(self, user_id: str, **kwargs) -> Any:
        """更新用户 - 双写"""
        try:
            # 写入新存储
            result = await self.new_user_store.update_user(user_id, **kwargs)

            # 双写到旧存储
            if self.enable_dual_write and self.old_user_store:
                try:
                    await self.old_user_store.update_user(user_id, **kwargs)
                except Exception as e:
                    logger.warning(f"旧存储写入失败: {e}")
                    self.stats["write_failures"] += 1

            self.stats["user_writes"] += 1
            return result
        except Exception as e:
            logger.error(f"更新用户失败: {e}")
            raise

    # ==================== API密钥存储 ====================

    async def create_api_key(self, **kwargs) -> Any:
        """创建API密钥 - 双写"""
        try:
            result = await self.new_api_key_store.create_api_key(**kwargs)

            if self.enable_dual_write and self.old_api_key_store:
                try:
                    await self.old_api_key_store.create_api_key(**kwargs)
                except Exception as e:
                    logger.warning(f"旧存储写入失败: {e}")
                    self.stats["write_failures"] += 1

            self.stats["api_key_writes"] += 1
            return result
        except Exception as e:
            logger.error(f"创建API密钥失败: {e}")
            raise

    async def get_api_key_by_hash(self, key_hash: str) -> Any:
        """获取API密钥 - 从新存储读取"""
        if self.read_from_new:
            return await self.new_api_key_store.get_api_key_by_hash(key_hash)
        else:
            if self.old_api_key_store:
                return await self.old_api_key_store.get_api_key_by_hash(key_hash)
            return await self.new_api_key_store.get_api_key_by_hash(key_hash)

    async def revoke_api_key(self, key_id: str) -> Any:
        """撤销API密钥 - 双写"""
        try:
            result = await self.new_api_key_store.revoke_api_key(key_id)

            if self.enable_dual_write and self.old_api_key_store:
                try:
                    await self.old_api_key_store.revoke_api_key(key_id)
                except Exception as e:
                    logger.warning(f"旧存储写入失败: {e}")
                    self.stats["write_failures"] += 1

            self.stats["api_key_writes"] += 1
            return result
        except Exception as e:
            logger.error(f"撤销API密钥失败: {e}")
            raise

    # ==================== 审批存储 ====================

    async def create_approval(self, **kwargs) -> Any:
        """创建审批 - 双写"""
        try:
            result = await self.new_approval_store.create_approval(**kwargs)

            if self.enable_dual_write and self.old_approval_store:
                try:
                    await self.old_approval_store.create_approval(**kwargs)
                except Exception as e:
                    logger.warning(f"旧存储写入失败: {e}")
                    self.stats["write_failures"] += 1

            self.stats["approval_writes"] += 1
            return result
        except Exception as e:
            logger.error(f"创建审批失败: {e}")
            raise

    async def approve(self, approval_id: str, **kwargs) -> Any:
        """批准审批 - 双写"""
        try:
            result = await self.new_approval_store.approve(approval_id, **kwargs)

            if self.enable_dual_write and self.old_approval_store:
                try:
                    await self.old_approval_store.approve(approval_id, **kwargs)
                except Exception as e:
                    logger.warning(f"旧存储写入失败: {e}")
                    self.stats["write_failures"] += 1

            self.stats["approval_writes"] += 1
            return result
        except Exception as e:
            logger.error(f"批准审批失败: {e}")
            raise

    # ==================== 速率限制 ====================

    async def check_rate_limit(self, **kwargs) -> tuple[bool, int, int]:
        """检查速率限制 - 从新存储读取"""
        return await self.new_rate_limiter.check_rate_limit(**kwargs)

    # ==================== CSRF令牌 ====================

    async def create_csrf_token(self, **kwargs) -> bool:
        """创建CSRF令牌 - 双写"""
        try:
            result = await self.new_csrf_token_store.create_token(**kwargs)

            if self.enable_dual_write and self.old_csrf_token_store:
                try:
                    await self.old_csrf_token_store.create_token(**kwargs)
                except Exception as e:
                    logger.warning(f"旧存储写入失败: {e}")
                    self.stats["write_failures"] += 1

            self.stats["csrf_token_writes"] += 1
            return result
        except Exception as e:
            logger.error(f"创建CSRF令牌失败: {e}")
            raise

    async def validate_csrf_token(self, **kwargs) -> tuple[bool, dict | None]:
        """验证CSRF令牌 - 从新存储读取"""
        return await self.new_csrf_token_store.validate_token(**kwargs)

    # ==================== 配置管理 ====================

    def enable_new_storage_reads(self) -> None:
        """启用从新存储读取"""
        self.read_from_new = True
        logger.info("已启用从新存储读取")

    def disable_dual_write(self) -> None:
        """禁用双写模式"""
        self.enable_dual_write = False
        logger.info("已禁用双写模式")

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """重置统计信息"""
        for key in self.stats:
            self.stats[key] = 0


# 全局实例
_migration_adapter: MigrationAdapter | None = None


def get_migration_adapter() -> MigrationAdapter:
    """获取全局迁移适配器实例"""
    global _migration_adapter
    if _migration_adapter is None:
        _migration_adapter = MigrationAdapter()
    return _migration_adapter


def init_migration_adapter(
    old_user_store: Any = None,
    old_api_key_store: Any = None,
    old_approval_store: Any = None,
    old_rate_limiter: Any = None,
    old_csrf_token_store: Any = None,
    **kwargs,
) -> MigrationAdapter:
    """初始化全局迁移适配器"""
    global _migration_adapter
    _migration_adapter = MigrationAdapter(
        old_user_store=old_user_store,
        old_api_key_store=old_api_key_store,
        old_approval_store=old_approval_store,
        old_rate_limiter=old_rate_limiter,
        old_csrf_token_store=old_csrf_token_store,
        **kwargs,
    )
    return _migration_adapter
