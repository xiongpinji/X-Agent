"""
API密钥存储 - PostgreSQL实现
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import APIKeyStoreModel
from backend.app.core.session import SessionManager

logger = logging.getLogger(__name__)


class APIKeyStorePostgres:
    """PostgreSQL API密钥存储实现"""

    async def create_api_key(
        self,
        key_id: str,
        key_prefix: str,
        key_hash: str,
        user_id: str,
        tenant_id: str,
        name: str,
        role: str = "developer",
        scopes: Optional[list[str]] = None,
        expires_at: Optional[datetime] = None,
    ) -> APIKeyStoreModel:
        """创建API密钥"""
        async with SessionManager.get_session() as session:
            api_key = APIKeyStoreModel(
                key_id=key_id,
                key_prefix=key_prefix,
                key_hash=key_hash,
                user_id=user_id,
                tenant_id=tenant_id,
                name=name,
                role=role,
                scopes=json.dumps(scopes or []),
                expires_at=expires_at,
            )
            session.add(api_key)
            await session.flush()
            logger.info(f"API密钥创建成功: {key_prefix}")
            return api_key

    async def get_api_key_by_id(self, key_id: str) -> Optional[APIKeyStoreModel]:
        """根据ID获取API密钥"""
        async with SessionManager.get_session() as session:
            stmt = select(APIKeyStoreModel).where(APIKeyStoreModel.key_id == key_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_api_key_by_hash(self, key_hash: str) -> Optional[APIKeyStoreModel]:
        """根据哈希获取API密钥"""
        async with SessionManager.get_session() as session:
            stmt = select(APIKeyStoreModel).where(APIKeyStoreModel.key_hash == key_hash)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_api_key_by_prefix(self, key_prefix: str) -> Optional[APIKeyStoreModel]:
        """根据前缀获取API密钥"""
        async with SessionManager.get_session() as session:
            stmt = select(APIKeyStoreModel).where(APIKeyStoreModel.key_prefix == key_prefix)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_api_keys(
        self,
        user_id: str,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[APIKeyStoreModel]:
        """列出用户的API密钥"""
        async with SessionManager.get_session() as session:
            stmt = (
                select(APIKeyStoreModel)
                .where(
                    (APIKeyStoreModel.user_id == user_id)
                    & (APIKeyStoreModel.tenant_id == tenant_id)
                )
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def revoke_api_key(self, key_id: str) -> Optional[APIKeyStoreModel]:
        """撤销API密钥"""
        async with SessionManager.get_session() as session:
            stmt = select(APIKeyStoreModel).where(APIKeyStoreModel.key_id == key_id)
            result = await session.execute(stmt)
            api_key = result.scalar_one_or_none()

            if not api_key:
                logger.warning(f"API密钥不存在: {key_id}")
                return None

            api_key.revoked = True
            api_key.revoked_at = datetime.now(UTC)
            await session.flush()
            logger.info(f"API密钥已撤销: {key_id}")
            return api_key

    async def update_last_used(self, key_id: str) -> Optional[APIKeyStoreModel]:
        """更新最后使用时间"""
        async with SessionManager.get_session() as session:
            stmt = select(APIKeyStoreModel).where(APIKeyStoreModel.key_id == key_id)
            result = await session.execute(stmt)
            api_key = result.scalar_one_or_none()

            if not api_key:
                return None

            api_key.last_used_at = datetime.now(UTC)
            await session.flush()
            return api_key

    async def delete_api_key(self, key_id: str) -> bool:
        """删除API密钥"""
        async with SessionManager.get_session() as session:
            stmt = select(APIKeyStoreModel).where(APIKeyStoreModel.key_id == key_id)
            result = await session.execute(stmt)
            api_key = result.scalar_one_or_none()

            if not api_key:
                logger.warning(f"API密钥不存在: {key_id}")
                return False

            await session.delete(api_key)
            await session.flush()
            logger.info(f"API密钥已删除: {key_id}")
            return True

    async def is_valid(self, key_id: str) -> bool:
        """检查API密钥是否有效"""
        api_key = await self.get_api_key_by_id(key_id)
        if not api_key:
            return False

        # 检查是否被撤销
        if api_key.revoked:
            return False

        # 检查是否过期
        if api_key.expires_at and datetime.now(UTC) > api_key.expires_at:
            return False

        return True

    async def get_scopes(self, key_id: str) -> list[str]:
        """获取API密钥的权限范围"""
        api_key = await self.get_api_key_by_id(key_id)
        if not api_key:
            return []
        return json.loads(api_key.scopes)

    async def cleanup_expired_keys(self) -> int:
        """清理过期的API密钥"""
        async with SessionManager.get_session() as session:
            stmt = select(APIKeyStoreModel).where(
                (APIKeyStoreModel.expires_at.isnot(None))
                & (APIKeyStoreModel.expires_at < datetime.now(UTC))
            )
            result = await session.execute(stmt)
            expired_keys = result.scalars().all()

            for key in expired_keys:
                await session.delete(key)

            await session.flush()
            logger.info(f"清理了 {len(expired_keys)} 个过期的API密钥")
            return len(expired_keys)


# 全局实例
_api_key_store: APIKeyStorePostgres | None = None


def get_api_key_store() -> APIKeyStorePostgres:
    """获取全局API密钥存储实例"""
    global _api_key_store
    if _api_key_store is None:
        _api_key_store = APIKeyStorePostgres()
    return _api_key_store
