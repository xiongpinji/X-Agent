"""
CSRF令牌存储 - Redis实现
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis.asyncio as redis

from backend.app.core.database import get_db_manager

logger = logging.getLogger(__name__)


class CSRFTokenStoreRedis:
    """Redis CSRF令牌存储实现"""

    def __init__(self, redis_client: redis.Redis | None = None):
        self.redis_client = redis_client
        self.default_ttl_seconds = 3600  # 1小时

    @staticmethod
    def _to_str(value) -> str:
        """将 Redis 返回值统一转为 str（兼容 bytes/str）"""
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value) if value is not None else ""

    async def _get_redis(self) -> redis.Redis:
        """获取Redis客户端"""
        if self.redis_client:
            return self.redis_client

        db_manager = get_db_manager()
        redis_client = db_manager.redis
        if not redis_client:
            raise RuntimeError("Redis未初始化")
        return redis_client

    def _make_key(self, token_hash: str) -> str:
        """生成Redis键"""
        return f"csrf_token:{token_hash}"

    def _make_session_key(self, session_id: str) -> str:
        """生成会话键"""
        return f"csrf_session:{session_id}"

    async def create_token(
        self,
        token_id: str,
        token_hash: str,
        tenant_id: str,
        user_id: str,
        session_id: str,
        ttl_seconds: int | None = None,
    ) -> bool:
        """创建CSRF令牌"""
        redis_client = await self._get_redis()
        ttl = ttl_seconds or self.default_ttl_seconds

        try:
            key = self._make_key(token_hash)
            session_key = self._make_session_key(session_id)

            # 存储令牌信息
            token_data = {
                "token_id": token_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "created_at": datetime.now(UTC).isoformat(),
            }

            # 使用管道原子操作
            pipe = redis_client.pipeline()
            pipe.hset(key, mapping=token_data)
            pipe.expire(key, ttl)
            pipe.sadd(session_key, token_hash)
            pipe.expire(session_key, ttl)
            await pipe.execute()

            logger.info(f"CSRF令牌创建成功: {token_id}")
            return True

        except Exception as e:
            logger.error(f"创建CSRF令牌失败: {e}")
            return False

    async def validate_token(
        self,
        token_hash: str,
        session_id: str,
    ) -> tuple[bool, dict | None]:
        """验证CSRF令牌"""
        redis_client = await self._get_redis()

        try:
            key = self._make_key(token_hash)
            session_key = self._make_session_key(session_id)

            # 检查令牌是否存在
            token_data = await redis_client.hgetall(key)
            if not token_data:
                logger.warning(f"CSRF令牌不存在或已过期: {token_hash}")
                return False, None

            # 检查会话是否匹配（兼容 fakeredis 返回 bytes 的情况）
            stored_session = self._to_str(token_data.get(b"session_id") or token_data.get("session_id"))
            if stored_session != session_id:
                logger.warning(f"CSRF令牌会话不匹配: {token_hash}")
                return False, None

            # 统一将 token_data 的 key/value 转为 str
            token_data = {self._to_str(k): self._to_str(v) for k, v in token_data.items()}

            # 检查令牌是否在会话中
            is_in_session = await redis_client.sismember(session_key, token_hash)
            if not is_in_session:
                logger.warning(f"CSRF令牌不在会话中: {token_hash}")
                return False, None

            logger.info(f"CSRF令牌验证成功: {token_hash}")
            return True, token_data

        except Exception as e:
            logger.error(f"验证CSRF令牌失败: {e}")
            return False, None

    async def revoke_token(self, token_hash: str) -> bool:
        """撤销CSRF令牌"""
        redis_client = await self._get_redis()

        try:
            key = self._make_key(token_hash)

            # 获取令牌信息以获取会话ID
            token_data = await redis_client.hgetall(key)
            if token_data:
                session_id = self._to_str(token_data.get(b"session_id") or token_data.get("session_id"))
                if session_id:
                    session_key = self._make_session_key(session_id)
                    await redis_client.srem(session_key, token_hash)

            # 删除令牌
            await redis_client.delete(key)
            logger.info(f"CSRF令牌已撤销: {token_hash}")
            return True

        except Exception as e:
            logger.error(f"撤销CSRF令牌失败: {e}")
            return False

    async def revoke_session_tokens(self, session_id: str) -> int:
        """撤销会话的所有令牌"""
        redis_client = await self._get_redis()

        try:
            session_key = self._make_session_key(session_id)

            # 获取会话中的所有令牌
            token_hashes = await redis_client.smembers(session_key)

            # 删除所有令牌
            for token_hash in token_hashes:
                key = self._make_key(token_hash)
                await redis_client.delete(key)

            # 删除会话键
            await redis_client.delete(session_key)

            logger.info(f"会话令牌已撤销: {session_id} ({len(token_hashes)}个)")
            return len(token_hashes)

        except Exception as e:
            logger.error(f"撤销会话令牌失败: {e}")
            return 0

    async def get_token_info(self, token_hash: str) -> dict | None:
        """获取令牌信息"""
        redis_client = await self._get_redis()

        try:
            key = self._make_key(token_hash)
            token_data = await redis_client.hgetall(key)
            return token_data if token_data else None

        except Exception as e:
            logger.error(f"获取令牌信息失败: {e}")
            return None

    async def get_session_tokens(self, session_id: str) -> list[str]:
        """获取会话的所有令牌"""
        redis_client = await self._get_redis()

        try:
            session_key = self._make_session_key(session_id)
            token_hashes = await redis_client.smembers(session_key)
            return list(token_hashes)

        except Exception as e:
            logger.error(f"获取会话令牌失败: {e}")
            return []

    async def cleanup_expired(self) -> int:
        """清理过期的令牌"""
        redis_client = await self._get_redis()

        try:
            # Redis会自动过期，这里只是统计
            pattern = "csrf_token:*"
            cursor = 0
            count = 0

            while True:
                cursor, keys = await redis_client.scan(cursor, match=pattern)
                count += len(keys)

                if cursor == 0:
                    break

            logger.info(f"CSRF令牌清理完成: {count}个活跃令牌")
            return count

        except Exception as e:
            logger.error(f"清理过期令牌失败: {e}")
            return 0

    async def get_stats(self) -> dict:
        """获取统计信息"""
        redis_client = await self._get_redis()

        try:
            token_pattern = "csrf_token:*"
            session_pattern = "csrf_session:*"

            cursor = 0
            token_count = 0
            session_count = 0

            while True:
                cursor, keys = await redis_client.scan(cursor, match=token_pattern)
                token_count += len(keys)
                if cursor == 0:
                    break

            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match=session_pattern)
                session_count += len(keys)
                if cursor == 0:
                    break

            return {
                "total_tokens": token_count,
                "total_sessions": session_count,
            }

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}


# 全局实例
_csrf_token_store: CSRFTokenStoreRedis | None = None


def get_csrf_token_store() -> CSRFTokenStoreRedis:
    """获取全局CSRF令牌存储实例"""
    global _csrf_token_store
    if _csrf_token_store is None:
        _csrf_token_store = CSRFTokenStoreRedis()
    return _csrf_token_store
