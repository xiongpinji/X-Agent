"""
backend/tests 共享 fixtures

为直接使用 SessionManager.get_session() 的测试（订阅/计费等）提供一个
已初始化的全局 DatabaseManager，底层是共享连接的内存 SQLite。

设计要点：
- autouse：订阅测试方法不显式请求 fixture，必须自动注入。
- StaticPool + check_same_thread=False：保证一个测试内多次 get_session()
  命中同一个内存库（否则 commit 的数据在下一次 get_session 中不可见）。
- 复用真实 DatabaseManager.get_session 代码路径（含 commit/rollback）。
- 每个测试用独立引擎并在结束后 dispose，保证测试间隔离。
"""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import backend.app.core.database as db_module
from backend.app.core.database import DatabaseManager
from backend.app.models.billing import Base


@pytest_asyncio.fixture(autouse=True)
async def _init_global_db():
    """初始化全局 _db_manager，使 SessionManager.get_session() 可用。"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    # 建表（billing 下所有模型共用同一个 Base）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 构造真实 DatabaseManager 并直接注入引擎/会话工厂，绕开 initialize()
    # （initialize 强制使用 QueuePool，不适用于内存 SQLite 的连接共享）
    manager = DatabaseManager("sqlite+aiosqlite:///:memory:")
    manager._engine = engine
    manager._session_factory = factory

    original = db_module._db_manager
    db_module._db_manager = manager
    try:
        yield manager
    finally:
        db_module._db_manager = original
        await engine.dispose()
