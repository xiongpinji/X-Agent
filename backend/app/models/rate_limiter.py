"""
速率限制器 - Redis实现（滑动窗口算法）
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis.asyncio as redis

from backend.app.core.database import get_db_manager

logger = logging.getLogger(__name__)


class RateLimiterRedis:
    """Redis速率限制器实现 - 使用滑动窗口算法"""

    def __init__(self, redis_client: redis.Redis | None = None):
        self.redis_client = redis_client

    async def _get_redis(self) -> redis.Redis:
        """获取Redis客户端"""
        if self.redis_client:
            return self.redis_client

        db_manager = get_db_manager()
        redis_client = db_manager.redis
        if not redis_client:
            raise RuntimeError("Redis未初始化")
        return redis_client

    def _make_key(
        self,
        tenant_id: str,
        user_id: str,
        endpoint: str,
    ) -> str:
        """生成Redis键"""
        return f"rate_limit:{tenant_id}:{user_id}:{endpoint}"

    async def check_rate_limit(
        self,
        tenant_id: str,
        user_id: str,
        endpoint: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        检查是否超过速率限制

        返回: (是否允许, 当前计数, 剩余配额)
        """
        redis_client = await self._get_redis()
        key = self._make_key(tenant_id, user_id, endpoint)
        now = datetime.now(UTC).timestamp()
        window_start = now - window_seconds

        try:
            # 使用Lua脚本实现原子操作
            lua_script = """
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window_start = tonumber(ARGV[2])
            local limit = tonumber(ARGV[3])
            local window_seconds = tonumber(ARGV[4])

            -- 删除窗口外的记录
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

            -- 获取当前窗口内的请求数
            local current_count = redis.call('ZCARD', key)

            -- 检查是否超限
            if current_count < limit then
                -- 添加当前请求
                redis.call('ZADD', key, now, now)
                redis.call('EXPIRE', key, window_seconds + 1)
                return {1, current_count + 1, limit - current_count - 1}
            else
                return {0, current_count, 0}
            end
            """

            result = await redis_client.eval(
                lua_script,
                1,
                key,
                now,
                window_start,
                limit,
                window_seconds,
            )

            allowed = bool(result[0])
            current_count = int(result[1])
            remaining = int(result[2])

            if not allowed:
                logger.warning(
                    f"速率限制触发: {tenant_id}/{user_id}/{endpoint} "
                    f"({current_count}/{limit})"
                )

            return allowed, current_count, remaining

        except Exception as e:
            logger.error(f"速率限制检查失败: {e}")
            # 失败开放 - 允许请求通过
            return True, 0, limit

    async def get_current_count(
        self,
        tenant_id: str,
        user_id: str,
        endpoint: str,
        window_seconds: int,
    ) -> int:
        """获取当前窗口内的请求数"""
        redis_client = await self._get_redis()
        key = self._make_key(tenant_id, user_id, endpoint)
        now = datetime.now(UTC).timestamp()
        window_start = now - window_seconds

        try:
            # 删除窗口外的记录
            await redis_client.zremrangebyscore(key, 0, window_start)
            # 获取当前计数
            count = await redis_client.zcard(key)
            return count
        except Exception as e:
            logger.error(f"获取请求计数失败: {e}")
            return 0

    async def reset_limit(
        self,
        tenant_id: str,
        user_id: str,
        endpoint: str,
    ) -> bool:
        """重置速率限制"""
        redis_client = await self._get_redis()
        key = self._make_key(tenant_id, user_id, endpoint)

        try:
            await redis_client.delete(key)
            logger.info(f"速率限制已重置: {tenant_id}/{user_id}/{endpoint}")
            return True
        except Exception as e:
            logger.error(f"重置速率限制失败: {e}")
            return False

    async def cleanup_expired(self) -> int:
        """清理过期的限制记录"""
        redis_client = await self._get_redis()

        try:
            # 获取所有rate_limit键
            pattern = "rate_limit:*"
            cursor = 0
            deleted_count = 0

            while True:
                cursor, keys = await redis_client.scan(cursor, match=pattern)
                for key in keys:
                    # Redis会自动过期，这里只是确保
                    ttl = await redis_client.ttl(key)
                    if ttl == -1:  # 没有过期时间
                        await redis_client.expire(key, 3600)  # 设置1小时过期
                        deleted_count += 1

                if cursor == 0:
                    break

            logger.info(f"清理了 {deleted_count} 个过期的限制记录")
            return deleted_count

        except Exception as e:
            logger.error(f"清理过期记录失败: {e}")
            return 0

    async def get_stats(
        self,
        tenant_id: str,
        user_id: str,
    ) -> dict:
        """获取用户的速率限制统计"""
        redis_client = await self._get_redis()
        pattern = f"rate_limit:{tenant_id}:{user_id}:*"

        try:
            cursor = 0
            stats = {}

            while True:
                cursor, keys = await redis_client.scan(cursor, match=pattern)
                for key in keys:
                    endpoint = key.split(":")[-1]
                    count = await redis_client.zcard(key)
                    stats[endpoint] = count

                if cursor == 0:
                    break

            return stats

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}


# 全局实例
_rate_limiter: RateLimiterRedis | None = None


def get_rate_limiter() -> RateLimiterRedis:
    """获取全局速率限制器实例"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiterRedis()
    return _rate_limiter
