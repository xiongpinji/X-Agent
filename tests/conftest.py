from __future__ import annotations

import os
import asyncio
import tempfile

os.environ.setdefault("APP_MODE", "development")
os.environ.setdefault("XAGENT_AUDIT_HMAC_SECRET", "test-audit-secret")
os.environ.setdefault("XAGENT_BOOTSTRAP_API_KEY", "bootstrap")
os.environ.setdefault("XAGENT_QDRANT_URL", "")

# Per-worker isolated data directory for xdist parallel runs.
# Prevents PermissionError when multiple workers write to the same
# data/audit.jsonl, data/runs.jsonl, etc. on Windows.
def _set_worker_data_dir() -> None:
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "")
    if worker_id:
        _tmpdir = tempfile.mkdtemp(prefix=f"xagent_data_{worker_id}_")
        # Settings reads these via XAGENT_ prefix before app imports
        for key, rel in [
            ("XAGENT_AUDIT_STORE_PATH", f"{_tmpdir}/audit.jsonl"),
            ("XAGENT_RUN_STORE_PATH", f"{_tmpdir}/runs.jsonl"),
            ("XAGENT_WORKFLOW_STORE_PATH", f"{_tmpdir}/workflows.json"),
            ("XAGENT_WORKFLOW_RUN_STORE_PATH", f"{_tmpdir}/workflow_runs.jsonl"),
            ("XAGENT_WORKFLOW_SCHEDULE_STORE_PATH", f"{_tmpdir}/workflow_schedules.json"),
            ("XAGENT_APPROVAL_STORE_PATH", f"{_tmpdir}/approvals.json"),
            ("XAGENT_TOOL_EXECUTION_STORE_PATH", f"{_tmpdir}/tool_executions.json"),
        ]:
            os.environ.setdefault(key, rel)

_set_worker_data_dir()

# ---------------------------------------------------------------------------
# A 类契约对齐（2026-07-26 回归）：商用修复将路由注册移入 FastAPI startup
# 钩子（backend.app.main.startup_event -> _register_all_routers()）。
# 大量测试直接 TestClient(app) 而不进入 lifespan，startup 不触发，
# 导致全部 API 路由 404。此处幂等地在测试会话导入期完成注册，
# 并用守卫包装避免 startup 二次注册重复路由。
# ---------------------------------------------------------------------------
try:  # pragma: no cover - 测试环境引导代码
    import backend.app.main as _main_mod

    _orig_register_routers = _main_mod._register_all_routers

    def _guarded_register_routers() -> None:
        if getattr(_main_mod.app, "_xagent_routers_registered", False):
            return
        _orig_register_routers()
        _main_mod.app._xagent_routers_registered = True

    _main_mod._register_all_routers = _guarded_register_routers
    _guarded_register_routers()
except Exception:
    pass

import pytest
import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def _init_global_db():
    """为根级测试初始化全局 DatabaseManager（临时文件 SQLite）。

    根级的 *StorePostgres（UserStore/APIKeyStore/ApprovalStore/FeedbackStore）
    都走 SessionManager.get_session()，需要一个已初始化的全局 _db_manager。
    enterprise 子树有自己的同名 fixture（只建 billing.Base）；这里覆盖
    根级用到的两套独立 Base：
      - backend.app.models.Base   → users / api_keys / approvals / rate_limit_logs / csrf_tokens
      - backend.app.models.feedback.Base → feedback / feedback_analysis

    连接池策略（关键，见 Task #109 死锁根因）：用临时文件 SQLite + NullPool，
    与生产 DatabaseManager.initialize() 对 sqlite 的做法一致（database.py 也强制
    NullPool 规避跨事件循环复用连接的问题）。

    早先用 :memory: + StaticPool 是为了让一个测试内多次 get_session() 看到同一份
    数据——但 StaticPool 会把唯一一条 aiosqlite 连接跨 yield 长期持有，该连接的
    后台线程绑定在创建它的那个 event loop 上；pytest-asyncio 0.23.0 每个测试函数新建
    loop，teardown 的 await engine.dispose() 可能落在另一个 loop 上去关那条连接，
    aiosqlite 后台线程 call_soon_threadsafe 把结果回投到没在跑的 loop → 永久挂起 →
    被 --timeout-method=thread 的 os._exit 强杀 → xdist 报 node down（连累所有 autouse
    命中本 fixture 的无辜测试，如 test_context_management_system）。

    改用 NullPool 后：setup 的 create_all 连接在 async with 块结束即关闭，yield 期间
    不持有任何连接；测试内 get_session() 各自在本测试 loop 上开/关连接；teardown
    的 dispose() 池里无连接可关→空操作→不再跨 loop 等待→不再死锁。共享可见性改由
    磁盘文件保证（比 StaticPool 的共享连接更强：commit 落盘后下次连接必可见）。
    """
    import shutil
    import tempfile
    from pathlib import Path as _Path

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import NullPool

    import backend.app.core.database as db_module
    from backend.app.core.database import DatabaseManager
    from backend.app.models import Base as ModelsBase
    from backend.app.models.feedback import Base as FeedbackBase

    _tmpdir = tempfile.mkdtemp(prefix="xagent_root_testdb_")
    _db_path = _Path(_tmpdir) / "test.db"
    _db_url = f"sqlite+aiosqlite:///{_db_path.as_posix()}"

    engine = create_async_engine(
        _db_url,
        poolclass=NullPool,
        # check_same_thread=False: NullPool opens a fresh connection per session and
        # async work can hop threads, so the single-thread guard must be off.
        # timeout=30: sets SQLite's busy_timeout. With NullPool every concurrent
        # writer holds its own file handle; under the high-concurrency perf tests
        # (500 concurrent create_user, 200 mixed ops) SQLite serializes writes via a
        # file lock. Default busy_timeout=0 makes contending writers fail instantly
        # with "database is locked"; 30s makes them wait their turn so all succeed.
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.run_sync(ModelsBase.metadata.create_all)
        await conn.run_sync(FeedbackBase.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    manager = DatabaseManager(_db_url)
    manager._engine = engine
    manager._session_factory = factory

    # 注入内存 Redis（fakeredis），让 RateLimiterRedis / CSRFTokenStoreRedis 等
    # 依赖 db_manager.redis 的 store 可在无真实 Redis 的测试环境跑通。
    # 注意：check_rate_limit 用 Lua eval，fakeredis 执行 Lua 需 lupa；未装 lupa 时
    # 该路径走 store 内部的“失败开放”分支，不影响其余标准命令路径。
    try:
        import fakeredis.aioredis as _fakeredis_aio

        # 与生产 DatabaseManager.initialize() 的 redis.from_url 配置保持一致
        # （encoding=utf8, decode_responses=True），否则 fakeredis 默认返回 bytes，
        # 会让 csrf_token_store.validate_token 等按 str key 取值的逻辑失配。
        manager._redis_client = _fakeredis_aio.FakeRedis(
            encoding="utf8", decode_responses=True
        )
    except ImportError:
        pass

    original = db_module._db_manager
    db_module._db_manager = manager
    try:
        yield manager
    finally:
        db_module._db_manager = original
        if manager._redis_client is not None:
            _closer = getattr(manager._redis_client, "aclose", None) or getattr(
                manager._redis_client, "close", None
            )
            if _closer is not None:
                await _closer()
        await engine.dispose()
        shutil.rmtree(_tmpdir, ignore_errors=True)


@pytest.fixture(autouse=True)
def _isolate_checkpoint_store(tmp_path, monkeypatch):
    """把 CheckpointStore 隔离到 per-test 临时目录。

    CheckpointStore 启动时 _load_from_disk() 会全量加载 data/checkpoints/
    （本仓已堆积 300+ 文件/39MB），严重拖慢甚至拖垮涉及 agent loop 的测试。
    这里通过 XAGENT_CHECKPOINT_STORE_PATH 指到 tmp_path，并重置全局单例，
    保证每个测试拿到空 store；不触碰 data/ 下的存量文件。
    """
    import backend.app.core.checkpoint.store as cp_store

    monkeypatch.setenv(
        "XAGENT_CHECKPOINT_STORE_PATH", str(tmp_path / "checkpoints")
    )
    cp_store._checkpoint_store = None
    try:
        yield
    finally:
        cp_store._checkpoint_store = None


@pytest.fixture(autouse=True)
def _reset_global_state():
    """Reset global in-memory state before each test to avoid cross-test pollution."""
    from backend.app.main import _rate_limiter
    _rate_limiter._windows.clear()

    from backend.app.api import auth
    with getattr(auth, "_token_lock", pytest.importorskip("threading").Lock()):
        auth._revoked_tokens.clear()
        auth._token_expiry.clear()
        auth._token_users.clear()

    from backend.app.core.admin import tenant_store, user_store
    user_store._records.clear()
    tenant_store._records.clear()

    yield


def pytest_configure(config):
    """Pytest configuration hook."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
