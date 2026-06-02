"""
会话和事务管理
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db_manager

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SessionManager:
    """会话管理器"""

    @staticmethod
    @asynccontextmanager
    async def get_session() -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            yield session

    @staticmethod
    @asynccontextmanager
    async def transaction() -> AsyncGenerator[AsyncSession, None]:
        """获取事务会话"""
        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"事务失败: {e}")
                raise

    @staticmethod
    async def execute_in_transaction(
        func,
        *args,
        **kwargs,
    ):
        """在事务中执行函数"""
        async with SessionManager.transaction() as session:
            return await func(session, *args, **kwargs)


class TransactionContext:
    """事务上下文"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._savepoint = None

    async def __aenter__(self) -> AsyncSession:
        """进入事务"""
        self._savepoint = await self.session.begin_nested()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出事务"""
        if exc_type is not None:
            await self._savepoint.rollback()
            logger.error(f"嵌套事务回滚: {exc_val}")
        else:
            await self._savepoint.commit()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """依赖注入 - 获取会话"""
    async with SessionManager.get_session() as session:
        yield session
