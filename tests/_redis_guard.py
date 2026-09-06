"""分布式（Redis 依赖）测试的密闭性守卫。

这些测试此前隐式依赖"某个更早的用例已初始化 db_manager.redis"（本地顺序
恰好满足；CI xdist 分发不同则 RuntimeError("Redis未初始化") 批量失败）。
注入 XAGENT_REDIS_URL 会改变其他测试的会话存储路径（ASGITransport 用例
不跑 startup、Redis 池未建 → 401 批量失败），故不用 env 注入，而是在
Redis 不可用时显式 skip——blocking 的 unit job 不应要求 Redis service。

用法：测试/夹具开头调用 require_redis()。
"""

from __future__ import annotations

import asyncio

import pytest

_probe_cache: bool | None = None


def redis_available() -> bool:
    """探测全局 db_manager 是否已配置可用 Redis client（进程内缓存）。"""
    global _probe_cache
    if _probe_cache is None:
        async def _probe():
            from backend.app.models.rate_limiter import RateLimiterRedis

            await RateLimiterRedis()._get_redis()

        try:
            asyncio.run(_probe())
            _probe_cache = True
        except Exception:
            _probe_cache = False
    return _probe_cache


def require_redis() -> None:
    """Redis 未初始化时 skip 当前用例（可诊断，不失败）。"""
    if not redis_available():
        pytest.skip("requires initialized Redis (not configured in this environment)")
