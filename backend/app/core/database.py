"""
数据库连接管理 - PostgreSQL和Redis连接池
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库连接管理器"""

    def __init__(
        self,
        database_url: str,
        redis_url: str | None = None,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_recycle: int = 3600,
        echo: bool = False,
    ):
        self.database_url = database_url
        self.redis_url = redis_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_recycle = pool_recycle
        self.echo = echo

        self._engine: AsyncEngine | None = None
        self._session_factory: sessionmaker | None = None
        self._redis_client: redis.Redis | None = None

    async def initialize(self) -> None:
        """初始化数据库连接"""
        try:
            # 创建异步引擎
            #
            # 注意：不能给 async engine 显式传同步的 QueuePool —— SQLAlchemy 会在
            # 引擎构造期就抛 "QueuePool cannot be used with asyncio engine"。
            # async engine 的默认池已是 AsyncAdaptedQueuePool，无需显式指定。
            # SQLite(含 aiosqlite) 用 NullPool 规避跨事件循环复用连接的问题，
            # 且 NullPool 不接受 pool_size/max_overflow 等并发参数。
            is_sqlite = self.database_url.startswith("sqlite") or "sqlite" in self.database_url
            engine_kwargs: dict[str, object] = {"echo": self.echo}
            if is_sqlite:
                engine_kwargs["poolclass"] = NullPool
                # busy_timeout (via connect_args timeout): with NullPool each session
                # opens its own file handle, so concurrent writers contend on SQLite's
                # file lock. Default busy_timeout=0 fails contending writers instantly
                # with "database is locked"; 30s makes them wait their turn instead.
                engine_kwargs["connect_args"] = {"timeout": 30}
            else:
                engine_kwargs.update(
                    {
                        "pool_size": self.pool_size,
                        "max_overflow": self.max_overflow,
                        "pool_recycle": self.pool_recycle,
                        "pool_pre_ping": True,  # 连接前检查
                    }
                )
            self._engine = create_async_engine(self.database_url, **engine_kwargs)

            # 创建会话工厂
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )

            # 初始化Redis连接
            if self.redis_url:
                try:
                    self._redis_client = await redis.from_url(
                        self.redis_url,
                        encoding="utf8",
                        decode_responses=True,
                    )
                    await self._redis_client.ping()
                    logger.info("Redis连接成功")
                except Exception as e:
                    logger.warning(f"Redis连接失败: {e}，将使用内存存储")
                    self._redis_client = None

            logger.info("数据库连接初始化成功")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
        if self._redis_client:
            await self._redis_client.close()
        logger.info("数据库连接已关闭")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        if not self._session_factory:
            raise RuntimeError("数据库未初始化")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def health_check(self) -> dict[str, bool]:
        """健康检查"""
        result = {
            "database": False,
            "redis": False,
        }

        # 检查数据库
        try:
            if self._engine:
                async with self._engine.begin() as conn:
                    await conn.execute("SELECT 1")
                result["database"] = True
        except Exception as e:
            logger.warning(f"数据库健康检查失败: {e}")

        # 检查Redis
        try:
            if self._redis_client:
                await self._redis_client.ping()
                result["redis"] = True
        except Exception as e:
            logger.warning(f"Redis健康检查失败: {e}")

        return result

    @property
    def engine(self) -> AsyncEngine | None:
        """获取引擎"""
        return self._engine

    @property
    def redis(self) -> redis.Redis | None:
        """获取Redis客户端"""
        return self._redis_client


# 全局数据库管理器实例
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """获取全局数据库管理器"""
    if _db_manager is None:
        raise RuntimeError("数据库管理器未初始化")
    return _db_manager


async def init_db_manager(
    database_url: str,
    redis_url: str | None = None,
    **kwargs,
) -> DatabaseManager:
    """初始化全局数据库管理器"""
    global _db_manager
    _db_manager = DatabaseManager(database_url, redis_url, **kwargs)
    await _db_manager.initialize()
    return _db_manager
