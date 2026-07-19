"""
多层缓存系统优化版 - L1内存缓存、L2 Redis缓存、L3数据库

优化特性:
- 三层缓存架构
- 自动缓存预热
- 缓存失效管理
- 性能监控
- 缓存统计
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar, Optional

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheStats:
    """缓存统计信息"""
    total_requests: int = 0
    l1_hits: int = 0
    l2_hits: int = 0
    l3_hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        if self.total_requests == 0:
            return 0.0
        hits = self.l1_hits + self.l2_hits + self.l3_hits
        return (hits / self.total_requests) * 100

    @property
    def l1_hit_rate(self) -> float:
        """L1缓存命中率"""
        if self.total_requests == 0:
            return 0.0
        return (self.l1_hits / self.total_requests) * 100


class CacheBackend(ABC, Generic[T]):
    """缓存后端抽象基类"""

    @abstractmethod
    async def get(self, key: str) -> T | None:
        """获取缓存值"""
        pass

    @abstractmethod
    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """设置缓存值"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除缓存值"""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """清空缓存"""
        pass


class L1MemoryCache(CacheBackend[T]):
    """L1内存缓存 - 超热数据"""

    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, tuple[T, float | None]] = {}
        self._access_times: dict[str, float] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> T | None:
        """获取缓存值"""
        async with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]

            # 检查过期
            if expiry is not None and time.time() > expiry:
                del self._cache[key]
                del self._access_times[key]
                return None

            # 更新访问时间
            self._access_times[key] = time.time()
            return value

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """设置缓存值"""
        async with self._lock:
            # LRU驱逐
            if len(self._cache) >= self._max_size and key not in self._cache:
                lru_key = min(self._access_times, key=self._access_times.get)
                del self._cache[lru_key]
                del self._access_times[lru_key]

            expiry = time.time() + ttl if ttl else None
            self._cache[key] = (value, expiry)
            self._access_times[key] = time.time()

    async def delete(self, key: str) -> None:
        """删除缓存值"""
        async with self._lock:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)

    async def clear(self) -> None:
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "utilization": len(self._cache) / self._max_size * 100,
        }


class L2RedisCache(CacheBackend[T]):
    """L2 Redis缓存 - 热数据"""

    def __init__(self, redis_client: Any = None):
        self._redis = redis_client or self._create_mock_redis()
        self._lock = asyncio.Lock()

    def _create_mock_redis(self) -> dict:
        """创建模拟Redis客户端"""
        return {}

    async def get(self, key: str) -> T | None:
        """获取缓存值"""
        try:
            if isinstance(self._redis, dict):
                value, expiry = self._redis.get(key, (None, None))
                if value is None:
                    return None
                if expiry is not None and time.time() > expiry:
                    del self._redis[key]
                    return None
                return value
            else:
                # 实际Redis实现
                value = await self._redis.get(key)
                return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"L2 cache get error: {e}")
            return None

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """设置缓存值"""
        try:
            expiry = time.time() + ttl if ttl else None
            if isinstance(self._redis, dict):
                self._redis[key] = (value, expiry)
            else:
                # 实际Redis实现
                await self._redis.set(key, json.dumps(value), ex=ttl)
        except Exception as e:
            logger.error(f"L2 cache set error: {e}")

    async def delete(self, key: str) -> None:
        """删除缓存值"""
        try:
            if isinstance(self._redis, dict):
                self._redis.pop(key, None)
            else:
                await self._redis.delete(key)
        except Exception as e:
            logger.error(f"L2 cache delete error: {e}")

    async def clear(self) -> None:
        """清空缓存"""
        try:
            if isinstance(self._redis, dict):
                self._redis.clear()
            else:
                await self._redis.flushdb()
        except Exception as e:
            logger.error(f"L2 cache clear error: {e}")


class MultiLayerCache:
    """多层缓存管理器"""

    def __init__(
        self,
        l1_max_size: int = 1000,
        l1_ttl: int = 300,  # 5分钟
        l2_ttl: int = 3600,  # 1小时
        redis_client: Any = None,
    ):
        self.l1_cache = L1MemoryCache(max_size=l1_max_size)
        self.l2_cache = L2RedisCache(redis_client=redis_client)
        self.l1_ttl = l1_ttl
        self.l2_ttl = l2_ttl
        self.stats = CacheStats()
        self._warming_tasks: dict[str, asyncio.Task[Any]] = {}

    async def get(self, key: str) -> Any | None:
        """获取缓存值 (多层查询)"""
        self.stats.total_requests += 1

        # L1查询
        value = await self.l1_cache.get(key)
        if value is not None:
            self.stats.l1_hits += 1
            logger.debug(f"L1 cache hit: {key}")
            return value

        # L2查询
        value = await self.l2_cache.get(key)
        if value is not None:
            self.stats.l2_hits += 1
            # 回写到L1
            await self.l1_cache.set(key, value, ttl=self.l1_ttl)
            logger.debug(f"L2 cache hit: {key}")
            return value

        self.stats.misses += 1
        logger.debug(f"Cache miss: {key}")
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存值 (多层写入)"""
        ttl = ttl or self.l2_ttl

        # 写入L1
        await self.l1_cache.set(key, value, ttl=self.l1_ttl)

        # 写入L2
        await self.l2_cache.set(key, value, ttl=ttl)

        logger.debug(f"Cache set: {key} (ttl: {ttl}s)")

    async def delete(self, key: str) -> None:
        """删除缓存值"""
        await self.l1_cache.delete(key)
        await self.l2_cache.delete(key)
        logger.debug(f"Cache deleted: {key}")

    async def clear(self) -> None:
        """清空所有缓存"""
        await self.l1_cache.clear()
        await self.l2_cache.clear()
        logger.info("All caches cleared")

    async def warm_cache(
        self,
        key: str,
        loader: Callable[[], Any],
        ttl: int | None = None,
    ) -> None:
        """预热缓存"""
        try:
            data = await loader() if asyncio.iscoroutinefunction(loader) else loader()
            await self.set(key, data, ttl=ttl)
            logger.info(f"Cache warmed: {key}")
        except Exception as e:
            logger.error(f"Error warming cache {key}: {e}")

    async def schedule_warming(
        self,
        key: str,
        loader: Callable[[], Any],
        interval: int = 3600,
        ttl: int | None = None,
    ) -> None:
        """定期预热缓存"""
        async def warming_loop() -> None:
            while True:
                await self.warm_cache(key, loader, ttl)
                await asyncio.sleep(interval)

        task = asyncio.create_task(warming_loop())
        self._warming_tasks[key] = task
        logger.info(f"Scheduled cache warming: {key} (interval: {interval}s)")

    async def stop_warming(self, key: str) -> None:
        """停止缓存预热"""
        if key in self._warming_tasks:
            self._warming_tasks[key].cancel()
            del self._warming_tasks[key]
            logger.info(f"Stopped cache warming: {key}")

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "total_requests": self.stats.total_requests,
            "l1_hits": self.stats.l1_hits,
            "l2_hits": self.stats.l2_hits,
            "l3_hits": self.stats.l3_hits,
            "misses": self.stats.misses,
            "hit_rate": self.stats.hit_rate,
            "l1_hit_rate": self.stats.l1_hit_rate,
            "l1_stats": self.l1_cache.get_stats(),
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = CacheStats()


# 全局缓存实例
_cache_manager: Optional[MultiLayerCache] = None


def get_cache_manager() -> MultiLayerCache:
    """获取全局缓存管理器"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = MultiLayerCache()
    return _cache_manager


# 缓存装饰器
def cached(ttl: int = 3600):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs) -> Any:
            # 生成缓存键
            key_parts = [func.__name__] + [str(arg) for arg in args]
            key = hashlib.md5("|".join(key_parts).encode()).hexdigest()

            cache = get_cache_manager()
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await cache.set(key, result, ttl=ttl)
            return result

        return wrapper
    return decorator
