"""
X-Agent 后端性能全面优化模块

优化范围:
1. API响应时间优化 (目标: <100ms P95)
2. 数据库查询优化 (目标: <50ms)
3. 缓存策略优化 (目标: >90% 命中率)
4. 并发处理优化 (目标: >1000 RPS)
5. 内存使用优化 (目标: <500MB)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from typing import Any, Callable, Optional, TypeVar, Generic
from collections import defaultdict
import functools
import psutil
import gc

logger = logging.getLogger(__name__)

T = TypeVar("T")
K = TypeVar("K")


# ============================================================================
# 1. API响应时间优化 - 请求级缓存和响应压缩
# ============================================================================

@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    created_at: datetime
    ttl_seconds: int
    hit_count: int = 0
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """检查是否过期"""
        return datetime.now(UTC) - self.created_at > timedelta(seconds=self.ttl_seconds)


class ResponseCache:
    """API响应缓存 - 支持多层缓存策略"""

    def __init__(self, max_size_mb: int = 100):
        self.cache: dict[str, CacheEntry] = {}
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.current_size_bytes = 0
        self.hits = 0
        self.misses = 0
        self.lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if not entry.is_expired():
                    entry.hit_count += 1
                    self.hits += 1
                    return entry.value
                else:
                    # 删除过期条目
                    self.current_size_bytes -= entry.size_bytes
                    del self.cache[key]
            self.misses += 1
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """设置缓存值"""
        async with self.lock:
            # 计算大小
            import sys
            size_bytes = sys.getsizeof(value)

            # 检查是否需要清理
            while self.current_size_bytes + size_bytes > self.max_size_bytes and self.cache:
                # 删除最少使用的条目
                lru_key = min(self.cache.keys(), key=lambda k: self.cache[k].hit_count)
                self.current_size_bytes -= self.cache[lru_key].size_bytes
                del self.cache[lru_key]

            entry = CacheEntry(
                value=value,
                created_at=datetime.now(UTC),
                ttl_seconds=ttl_seconds,
                size_bytes=size_bytes,
            )
            self.cache[key] = entry
            self.current_size_bytes += size_bytes

    async def invalidate(self, pattern: str) -> int:
        """按模式失效缓存"""
        async with self.lock:
            keys_to_delete = [k for k in self.cache.keys() if pattern in k]
            for key in keys_to_delete:
                self.current_size_bytes -= self.cache[key].size_bytes
                del self.cache[key]
            return len(keys_to_delete)

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 2),
            "entries": len(self.cache),
            "size_mb": round(self.current_size_bytes / 1024 / 1024, 2),
            "max_size_mb": self.max_size_bytes / 1024 / 1024,
        }


def cached_response(ttl_seconds: int = 300, key_builder: Optional[Callable] = None):
    """API响应缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        cache = ResponseCache()

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 构建缓存键
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # 尝试从缓存获取
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 执行函数
            result = await func(*args, **kwargs)

            # 缓存结果
            await cache.set(cache_key, result, ttl_seconds)
            return result

        wrapper.cache = cache
        return wrapper
    return decorator


# ============================================================================
# 2. 数据库查询优化 - 批量加载和查询优化
# ============================================================================

class QueryOptimizer:
    """数据库查询优化器"""

    def __init__(self):
        self.query_times: list[float] = []
        self.slow_queries: list[tuple[str, float]] = []
        self.slow_query_threshold_ms = 50

    def record_query(self, query: str, duration_ms: float) -> None:
        """记录查询时间"""
        self.query_times.append(duration_ms)

        if duration_ms > self.slow_query_threshold_ms:
            self.slow_queries.append((query, duration_ms))
            if len(self.slow_queries) > 100:
                self.slow_queries = self.slow_queries[-100:]

    def get_percentile(self, percentile: float) -> float:
        """获取百分位数"""
        if not self.query_times:
            return 0.0
        sorted_times = sorted(self.query_times)
        index = int(len(sorted_times) * percentile / 100)
        return sorted_times[min(index, len(sorted_times) - 1)]

    def get_stats(self) -> dict[str, Any]:
        """获取查询统计"""
        if not self.query_times:
            return {
                "avg_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "slow_queries": 0,
            }

        return {
            "avg_ms": round(sum(self.query_times) / len(self.query_times), 2),
            "p50_ms": round(self.get_percentile(50), 2),
            "p95_ms": round(self.get_percentile(95), 2),
            "p99_ms": round(self.get_percentile(99), 2),
            "slow_queries": len(self.slow_queries),
            "total_queries": len(self.query_times),
        }


class BatchLoader(Generic[K, T]):
    """批量加载器 - 防止N+1查询"""

    def __init__(
        self,
        batch_fn: Callable[[list[K]], Any],
        batch_size: int = 100,
        cache_ttl_seconds: int = 300,
    ):
        self.batch_fn = batch_fn
        self.batch_size = batch_size
        self.cache_ttl_seconds = cache_ttl_seconds
        self._queue: list[tuple[K, asyncio.Future]] = []
        self._cache: dict[K, T] = {}
        self._processing = False
        self._lock = asyncio.Lock()

    async def load(self, key: K) -> T:
        """加载单个项"""
        # 检查缓存
        if key in self._cache:
            return self._cache[key]

        # 添加到队列
        future: asyncio.Future = asyncio.Future()
        async with self._lock:
            self._queue.append((key, future))

            # 如果队列满或这是第一个项，处理批次
            if len(self._queue) >= self.batch_size or len(self._queue) == 1:
                asyncio.create_task(self._process_batch())

        return await future

    async def load_many(self, keys: list[K]) -> list[T]:
        """加载多个项"""
        return await asyncio.gather(*[self.load(key) for key in keys])

    async def _process_batch(self) -> None:
        """处理批次"""
        if self._processing or not self._queue:
            return

        self._processing = True
        try:
            async with self._lock:
                queue = self._queue[:]
                self._queue = []

            keys = [key for key, _ in queue]
            futures = [future for _, future in queue]

            try:
                results = await self.batch_fn(keys)
                result_map = {key: result for key, result in zip(keys, results)}

                for key, future in zip(keys, futures):
                    result = result_map.get(key)
                    self._cache[key] = result
                    if not future.done():
                        future.set_result(result)
            except Exception as e:
                logger.error(f"批量加载失败: {e}")
                for future in futures:
                    if not future.done():
                        future.set_exception(e)
        finally:
            self._processing = False

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()


# ============================================================================
# 3. 缓存策略优化 - 多层缓存
# ============================================================================

class MultiLayerCache:
    """多层缓存系统 - L1内存缓存 + L2 Redis缓存"""

    def __init__(self, redis_client: Optional[Any] = None, l1_max_size_mb: int = 50):
        self.l1_cache = ResponseCache(max_size_mb=l1_max_size_mb)
        self.redis_client = redis_client
        self.l1_hits = 0
        self.l2_hits = 0
        self.misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """获取值 - 先查L1，再查L2"""
        # L1缓存
        value = await self.l1_cache.get(key)
        if value is not None:
            self.l1_hits += 1
            return value

        # L2缓存 (Redis)
        if self.redis_client:
            try:
                import json
                cached = await self.redis_client.get(key)
                if cached:
                    value = json.loads(cached)
                    # 回写到L1
                    await self.l1_cache.set(key, value, ttl_seconds=300)
                    self.l2_hits += 1
                    return value
            except Exception as e:
                logger.warning(f"Redis获取失败: {e}")

        self.misses += 1
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """设置值 - 同时写入L1和L2"""
        await self.l1_cache.set(key, value, ttl_seconds)

        if self.redis_client:
            try:
                import json
                await self.redis_client.setex(
                    key,
                    ttl_seconds,
                    json.dumps(value, default=str),
                )
            except Exception as e:
                logger.warning(f"Redis设置失败: {e}")

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        total = self.l1_hits + self.l2_hits + self.misses
        hit_rate = ((self.l1_hits + self.l2_hits) / total * 100) if total > 0 else 0
        return {
            "l1_hits": self.l1_hits,
            "l2_hits": self.l2_hits,
            "misses": self.misses,
            "total_hit_rate": round(hit_rate, 2),
            "l1_stats": self.l1_cache.get_stats(),
        }


# ============================================================================
# 4. 并发处理优化 - 连接池和速率限制
# ============================================================================

@dataclass
class PoolStats:
    """连接池统计"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    waiting_tasks: int = 0
    total_acquired: int = 0
    total_released: int = 0
    peak_active: int = 0
    errors: int = 0


class OptimizedConnectionPool:
    """优化的连接池 - 支持动态扩展和健康检查"""

    def __init__(
        self,
        factory: Callable,
        min_size: int = 10,
        max_size: int = 50,
        timeout: float = 30.0,
        health_check_interval: float = 60.0,
    ):
        self._factory = factory
        self._min_size = min_size
        self._max_size = max_size
        self._timeout = timeout
        self._health_check_interval = health_check_interval

        self._available: asyncio.Queue = asyncio.Queue()
        self._all_connections: set = set()
        self._active_connections: set = set()
        self._lock = asyncio.Lock()
        self._stats = PoolStats()
        self._initialized = False

    async def initialize(self) -> None:
        """初始化连接池"""
        if self._initialized:
            return

        async with self._lock:
            for _ in range(self._min_size):
                try:
                    conn = await self._factory()
                    self._all_connections.add(conn)
                    await self._available.put(conn)
                    self._stats.total_connections += 1
                except Exception as e:
                    logger.error(f"创建连接失败: {e}")
                    self._stats.errors += 1

        self._initialized = True
        logger.info(f"连接池初始化完成，连接数: {self._stats.total_connections}")

    async def acquire(self) -> Any:
        """获取连接"""
        await self.initialize()

        try:
            conn = self._available.get_nowait()
        except asyncio.QueueEmpty:
            async with self._lock:
                if self._stats.total_connections < self._max_size:
                    try:
                        conn = await self._factory()
                        self._all_connections.add(conn)
                        self._stats.total_connections += 1
                    except Exception as e:
                        logger.error(f"创建连接失败: {e}")
                        self._stats.errors += 1
                        raise
                else:
                    try:
                        conn = await asyncio.wait_for(
                            self._available.get(),
                            timeout=self._timeout,
                        )
                    except asyncio.TimeoutError:
                        logger.error("获取连接超时")
                        self._stats.errors += 1
                        raise

        self._active_connections.add(conn)
        self._stats.active_connections = len(self._active_connections)
        self._stats.total_acquired += 1
        self._stats.peak_active = max(
            self._stats.peak_active,
            self._stats.active_connections,
        )

        return conn

    async def release(self, conn: Any) -> None:
        """释放连接"""
        if conn in self._active_connections:
            self._active_connections.remove(conn)

        self._stats.active_connections = len(self._active_connections)
        self._stats.idle_connections = self._available.qsize()
        self._stats.total_released += 1

        await self._available.put(conn)

    async def close(self) -> None:
        """关闭连接池"""
        async with self._lock:
            for conn in self._all_connections:
                try:
                    if hasattr(conn, "close"):
                        if asyncio.iscoroutinefunction(conn.close):
                            await conn.close()
                        else:
                            conn.close()
                except Exception as e:
                    logger.error(f"关闭连接失败: {e}")

            self._all_connections.clear()
            self._active_connections.clear()
            self._initialized = False

    def get_stats(self) -> PoolStats:
        """获取连接池统计"""
        return self._stats


class AdaptiveRateLimiter:
    """自适应速率限制器 - 根据系统负载动态调整"""

    def __init__(self, base_rps: int = 1000, window_seconds: int = 1):
        self.base_rps = base_rps
        self.window_seconds = window_seconds
        self.request_times: list[float] = []
        self.lock = asyncio.Lock()
        self.current_limit = base_rps

    async def acquire(self) -> None:
        """获取速率限制许可"""
        async with self.lock:
            now = time.time()

            # 清理过期的请求记录
            self.request_times = [
                t for t in self.request_times
                if now - t < self.window_seconds
            ]

            # 检查是否超过限制
            if len(self.request_times) >= self.current_limit:
                # 计算需要等待的时间
                oldest_request = self.request_times[0]
                wait_time = self.window_seconds - (now - oldest_request)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    self.request_times = []

            self.request_times.append(time.time())

    def adjust_limit(self, cpu_percent: float, memory_percent: float) -> None:
        """根据系统资源调整限制"""
        if cpu_percent > 80 or memory_percent > 80:
            # 降低限制
            self.current_limit = max(100, int(self.current_limit * 0.8))
        elif cpu_percent < 30 and memory_percent < 30:
            # 提高限制
            self.current_limit = min(self.base_rps * 2, int(self.current_limit * 1.2))


# ============================================================================
# 5. 内存使用优化
# ============================================================================

class MemoryOptimizer:
    """内存优化器 - 监控和优化内存使用"""

    def __init__(self, target_memory_mb: int = 500):
        self.target_memory_mb = target_memory_mb
        self.memory_samples: list[float] = []
        self.gc_count = 0

    def get_memory_usage_mb(self) -> float:
        """获取当前内存使用量"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024

    def optimize(self) -> dict[str, Any]:
        """执行内存优化"""
        before_mb = self.get_memory_usage_mb()

        # 执行垃圾回收
        gc.collect()
        self.gc_count += 1

        after_mb = self.get_memory_usage_mb()
        freed_mb = before_mb - after_mb

        self.memory_samples.append(after_mb)
        if len(self.memory_samples) > 1000:
            self.memory_samples = self.memory_samples[-1000:]

        return {
            "before_mb": round(before_mb, 2),
            "after_mb": round(after_mb, 2),
            "freed_mb": round(freed_mb, 2),
            "gc_count": self.gc_count,
            "avg_memory_mb": round(sum(self.memory_samples) / len(self.memory_samples), 2),
        }

    def get_stats(self) -> dict[str, Any]:
        """获取内存统计"""
        current_mb = self.get_memory_usage_mb()
        return {
            "current_mb": round(current_mb, 2),
            "target_mb": self.target_memory_mb,
            "utilization_percent": round(current_mb / self.target_memory_mb * 100, 2),
            "gc_count": self.gc_count,
            "avg_memory_mb": round(
                sum(self.memory_samples) / len(self.memory_samples), 2
            ) if self.memory_samples else 0,
        }


# ============================================================================
# 性能监控和报告
# ============================================================================

@dataclass
class PerformanceMetrics:
    """性能指标"""
    api_response_time_p95_ms: float = 0.0
    database_query_time_p95_ms: float = 0.0
    cache_hit_rate_percent: float = 0.0
    concurrent_requests_rps: float = 0.0
    memory_usage_mb: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def meets_targets(self) -> bool:
        """检查是否满足目标"""
        return (
            self.api_response_time_p95_ms < 100
            and self.database_query_time_p95_ms < 50
            and self.cache_hit_rate_percent > 90
            and self.concurrent_requests_rps > 1000
            and self.memory_usage_mb < 500
        )


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.metrics_history: list[PerformanceMetrics] = []
        self.query_optimizer = QueryOptimizer()
        self.memory_optimizer = MemoryOptimizer()
        self.response_cache = ResponseCache()
        self.rate_limiter = AdaptiveRateLimiter()

    def record_metrics(self, metrics: PerformanceMetrics) -> None:
        """记录性能指标"""
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]

    def get_current_metrics(self) -> PerformanceMetrics:
        """获取当前性能指标"""
        return PerformanceMetrics(
            api_response_time_p95_ms=0.0,  # 由中间件填充
            database_query_time_p95_ms=self.query_optimizer.get_percentile(95),
            cache_hit_rate_percent=self.response_cache.get_stats()["hit_rate"],
            concurrent_requests_rps=0.0,  # 由中间件填充
            memory_usage_mb=self.memory_optimizer.get_memory_usage_mb(),
        )

    def generate_report(self) -> str:
        """生成性能报告"""
        report = []
        report.append("=" * 80)
        report.append("X-AGENT 性能优化报告")
        report.append("=" * 80)
        report.append("")

        if not self.metrics_history:
            report.append("暂无性能数据")
            return "\n".join(report)

        # 最新指标
        latest = self.metrics_history[-1]
        report.append("最新性能指标:")
        report.append(f"  API响应时间 (P95): {latest.api_response_time_p95_ms:.2f}ms (目标: <100ms)")
        report.append(f"  数据库查询时间 (P95): {latest.database_query_time_p95_ms:.2f}ms (目标: <50ms)")
        report.append(f"  缓存命中率: {latest.cache_hit_rate_percent:.2f}% (目标: >90%)")
        report.append(f"  并发处理: {latest.concurrent_requests_rps:.2f} RPS (目标: >1000)")
        report.append(f"  内存使用: {latest.memory_usage_mb:.2f}MB (目标: <500MB)")
        report.append("")

        # 目标达成情况
        report.append("目标达成情况:")
        if latest.meets_targets():
            report.append("  ✓ 所有性能目标已达成")
        else:
            if latest.api_response_time_p95_ms >= 100:
                report.append(f"  ✗ API响应时间未达成 ({latest.api_response_time_p95_ms:.2f}ms >= 100ms)")
            if latest.database_query_time_p95_ms >= 50:
                report.append(f"  ✗ 数据库查询时间未达成 ({latest.database_query_time_p95_ms:.2f}ms >= 50ms)")
            if latest.cache_hit_rate_percent <= 90:
                report.append(f"  ✗ 缓存命中率未达成 ({latest.cache_hit_rate_percent:.2f}% <= 90%)")
            if latest.concurrent_requests_rps <= 1000:
                report.append(f"  ✗ 并发处理未达成 ({latest.concurrent_requests_rps:.2f} RPS <= 1000)")
            if latest.memory_usage_mb >= 500:
                report.append(f"  ✗ 内存使用未达成 ({latest.memory_usage_mb:.2f}MB >= 500MB)")
        report.append("")

        # 缓存统计
        cache_stats = self.response_cache.get_stats()
        report.append("缓存统计:")
        report.append(f"  命中: {cache_stats['hits']}")
        report.append(f"  未命中: {cache_stats['misses']}")
        report.append(f"  命中率: {cache_stats['hit_rate']:.2f}%")
        report.append(f"  条目数: {cache_stats['entries']}")
        report.append(f"  大小: {cache_stats['size_mb']:.2f}MB / {cache_stats['max_size_mb']:.2f}MB")
        report.append("")

        # 查询统计
        query_stats = self.query_optimizer.get_stats()
        report.append("数据库查询统计:")
        report.append(f"  平均时间: {query_stats['avg_ms']:.2f}ms")
        report.append(f"  P50: {query_stats['p50_ms']:.2f}ms")
        report.append(f"  P95: {query_stats['p95_ms']:.2f}ms")
        report.append(f"  P99: {query_stats['p99_ms']:.2f}ms")
        report.append(f"  慢查询: {query_stats['slow_queries']}")
        report.append(f"  总查询数: {query_stats['total_queries']}")
        report.append("")

        # 内存统计
        memory_stats = self.memory_optimizer.get_stats()
        report.append("内存统计:")
        report.append(f"  当前: {memory_stats['current_mb']:.2f}MB")
        report.append(f"  目标: {memory_stats['target_mb']}MB")
        report.append(f"  利用率: {memory_stats['utilization_percent']:.2f}%")
        report.append(f"  GC次数: {memory_stats['gc_count']}")
        report.append(f"  平均: {memory_stats['avg_memory_mb']:.2f}MB")
        report.append("")

        report.append("=" * 80)
        return "\n".join(report)


# 全局性能监控实例
performance_monitor = PerformanceMonitor()
