"""
用户存储 - PostgreSQL实现
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import UserStoreModel
from backend.app.core.session import SessionManager

logger = logging.getLogger(__name__)


class UserStorePostgres:
    """PostgreSQL用户存储实现"""

    async def create_user(
        self,
        user_id: str,
        email: str,
        password_hash: str,
        tenant_id: str = "default",
        full_name: Optional[str] = None,
        role: str = "user",
        metadata: Optional[dict] = None,
    ) -> UserStoreModel:
        """创建用户"""
        async with SessionManager.get_session() as session:
            user = UserStoreModel(
                user_id=user_id,
                email=email,
                password_hash=password_hash,
                tenant_id=tenant_id,
                full_name=full_name,
                role=role,
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            session.add(user)
            await session.flush()
            logger.info(f"用户创建成功: {user_id}")
            return user

    async def get_user_by_id(self, user_id: str) -> Optional[UserStoreModel]:
        """根据ID获取用户"""
        async with SessionManager.get_session() as session:
            stmt = select(UserStoreModel).where(UserStoreModel.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str, tenant_id: str = "default") -> Optional[UserStoreModel]:
        """根据邮箱获取用户"""
        async with SessionManager.get_session() as session:
            stmt = select(UserStoreModel).where(
                (UserStoreModel.email == email) & (UserStoreModel.tenant_id == tenant_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_user(
        self,
        user_id: str,
        **kwargs,
    ) -> Optional[UserStoreModel]:
        """更新用户"""
        async with SessionManager.get_session() as session:
            stmt = select(UserStoreModel).where(UserStoreModel.user_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"用户不存在: {user_id}")
                return None

            # 更新允许的字段
            allowed_fields = {
                "full_name",
                "role",
                "is_active",
                "is_verified",
                "password_hash",
                "last_login_at",
                "metadata_json",
            }

            for key, value in kwargs.items():
                if key in allowed_fields:
                    if key == "metadata_json" and isinstance(value, dict):
                        setattr(user, key, json.dumps(value))
                    else:
                        setattr(user, key, value)

            user.updated_at = datetime.now(UTC)
            await session.flush()
            logger.info(f"用户更新成功: {user_id}")
            return user

    async def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        async with SessionManager.get_session() as session:
            stmt = select(UserStoreModel).where(UserStoreModel.user_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"用户不存在: {user_id}")
                return False

            await session.delete(user)
            await session.flush()
            logger.info(f"用户删除成功: {user_id}")
            return True

    async def list_users(
        self,
        tenant_id: str = "default",
        skip: int = 0,
        limit: int = 100,
    ) -> list[UserStoreModel]:
        """列出用户"""
        async with SessionManager.get_session() as session:
            stmt = (
                select(UserStoreModel)
                .where(UserStoreModel.tenant_id == tenant_id)
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def count_users(self, tenant_id: str = "default") -> int:
        """统计用户数"""
        async with SessionManager.get_session() as session:
            stmt = select(UserStoreModel).where(UserStoreModel.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return len(result.scalars().all())

    async def update_last_login(self, user_id: str) -> Optional[UserStoreModel]:
        """更新最后登录时间"""
        return await self.update_user(
            user_id,
            last_login_at=datetime.now(UTC),
        )

    async def verify_user(self, user_id: str) -> Optional[UserStoreModel]:
        """验证用户"""
        return await self.update_user(
            user_id,
            is_verified=True,
        )

    async def deactivate_user(self, user_id: str) -> Optional[UserStoreModel]:
        """停用用户"""
        return await self.update_user(
            user_id,
            is_active=False,
        )

    async def activate_user(self, user_id: str) -> Optional[UserStoreModel]:
        """激活用户"""
        return await self.update_user(
            user_id,
            is_active=True,
        )

    async def get_metadata(self, user_id: str) -> Optional[dict]:
        """获取用户元数据"""
        user = await self.get_user_by_id(user_id)
        if not user or not user.metadata_json:
            return None
        return json.loads(user.metadata_json)

    async def set_metadata(self, user_id: str, metadata: dict) -> Optional[UserStoreModel]:
        """设置用户元数据"""
        return await self.update_user(
            user_id,
            metadata_json=json.dumps(metadata),
        )


# 全局实例
_user_store: UserStorePostgres | None = None


def get_user_store() -> UserStorePostgres:
    """获取全局用户存储实例"""
    global _user_store
    if _user_store is None:
        _user_store = UserStorePostgres()
    return _user_store
