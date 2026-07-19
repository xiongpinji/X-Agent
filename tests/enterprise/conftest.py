"""
backend/tests 共享 fixtures

为直接使用 SessionManager.get_session() 的测试（订阅/计费等）提供一个
已初始化的全局 DatabaseManager，底层是临时文件 SQLite（NullPool）。

设计要点：
- autouse：订阅测试方法不显式请求 fixture，必须自动注入。
- 临时文件 SQLite + NullPool（见根级 conftest 与 Task #109 死锁根因）：与生产
  DatabaseManager.initialize() 对 sqlite 的做法一致。早先用 :memory: + StaticPool
  会把唯一一条 aiosqlite 连接跨 yield 长期持有，其后台线程绑定创建它的 event loop；
  pytest-asyncio 0.23.0 每测试新建 loop，teardown 的 dispose() 落到另一 loop 去关
  那条连接 → call_soon_threadsafe 回投到没在跑的 loop → 永久挂起 → 进程被强杀。
  NullPool 不跨 yield 持连接 → dispose() 空操作 → 不死锁；共享可见性改由磁盘文件保证。
- 复用真实 DatabaseManager.get_session 代码路径（含 commit/rollback）。
- 每个测试用独立临时库并在结束后 dispose + 删目录，保证测试间隔离。
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path as _Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import backend.app.core.database as db_module
from backend.app.core.database import DatabaseManager
from backend.app.models.billing import Base


@pytest_asyncio.fixture(autouse=True)
async def _init_global_db():
    """初始化全局 _db_manager，使 SessionManager.get_session() 可用。"""
    _tmpdir = tempfile.mkdtemp(prefix="xagent_ent_testdb_")
    _db_path = _Path(_tmpdir) / "test.db"
    _db_url = f"sqlite+aiosqlite:///{_db_path.as_posix()}"

    engine = create_async_engine(
        _db_url,
        poolclass=NullPool,
        connect_args={"check_same_thread": False},
    )
    # 建表（billing 下所有模型共用同一个 Base）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 构造真实 DatabaseManager 并直接注入引擎/会话工厂，绕开 initialize()
    # （initialize 强制使用 QueuePool，不适用于内存 SQLite 的连接共享）
    manager = DatabaseManager(_db_url)
    manager._engine = engine
    manager._session_factory = factory

    original = db_module._db_manager
    db_module._db_manager = manager
    try:
        yield manager
    finally:
        db_module._db_manager = original
        await engine.dispose()
        shutil.rmtree(_tmpdir, ignore_errors=True)
