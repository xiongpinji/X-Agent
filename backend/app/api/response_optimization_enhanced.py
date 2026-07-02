"""
API响应优化版 - 压缩、批处理、HTTP缓存

优化特性:
- gzip响应压缩
- 请求批处理
- HTTP缓存头
- 响应优化
- 性能监控
"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from collections import deque

logger = logging.getLogger(__name__)


class CompressionType(str, Enum):
    """压缩类型"""
    NONE = "none"
    GZIP = "gzip"
    DEFLATE = "deflate"
    BROTLI = "brotli"


@dataclass
class ResponseStats:
    """响应统计信息"""
    total_requests: int = 0
    total_responses: int = 0
    total_response_size: int = 0
    total_compressed_size: int = 0
    total_latency_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    batch_count: int = 0
    average_batch_size: float = 0.0

    @property
    def average_latency_ms(self) -> float:
        """平均延迟"""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def compression_ratio(self) -> float:
        """压缩比"""
        if self.total_response_size == 0:
            return 0.0
        return (1 - self.total_compressed_size / self.total_response_size) * 100

    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return (self.cache_hits / total) * 100


class ResponseCompressor:
    """响应压缩器"""

    @staticmethod
    def compress_gzip(data: bytes, level: int = 6) -> bytes:
        """gzip压缩"""
        return gzip.compress(data, compresslevel=level)

    @staticmethod
    def should_compress(data: bytes, threshold_bytes: int = 1024) -> bool:
        """判断是否应该压缩"""
        return len(data) > threshold_bytes

    @staticmethod
    def get_compression_ratio(original_size: int, compressed_size: int) -> float:
        """获取压缩比"""
        if original_size == 0:
            return 0.0
        return (1 - compressed_size / original_size) * 100


class HTTPCacheManager:
    """HTTP缓存管理"""

    def __init__(self):
        self.etag_cache: Dict[str, str] = {}
        self.last_modified_cache: Dict[str, float] = {}
        self.lock = asyncio.Lock()

    async def generate_etag(self, data: bytes) -> str:
        """生成ETag"""
        return hashlib.md5(data, usedforsecurity=False).hexdigest()

    async def get_cache_headers(
        self,
        resource_id: str,
        max_age: int = 3600,
    ) -> Dict[str, str]:
        """获取缓存头"""
        async with self.lock:
            etag = self.etag_cache.get(resource_id, "")
            last_modified = self.last_modified_cache.get(resource_id, time.time())

        return {
            "Cache-Control": f"public, max-age={max_age}",
            "ETag": etag,
            "Last-Modified": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last_modified)),
            "Vary": "Accept-Encoding",
        }

    async def update_cache_info(
        self,
        resource_id: str,
        data: bytes,
    ) -> None:
        """更新缓存信息"""
        async with self.lock:
            self.etag_cache[resource_id] = await self.generate_etag(data)
            self.last_modified_cache[resource_id] = time.time()

    async def is_modified(
        self,
        resource_id: str,
        etag: Optional[str] = None,
        last_modified: Optional[float] = None,
    ) -> bool:
        """检查资源是否被修改"""
        async with self.lock:
            if etag and etag == self.etag_cache.get(resource_id):
                return False

            if last_modified and last_modified >= self.last_modified_cache.get(resource_id, 0):
                return False

        return True


class BatchRequestProcessor:
    """批处理请求处理器"""

    def __init__(
        self,
        batch_size: int = 100,
        batch_timeout_ms: int = 100,
    ):
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.queue: deque[tuple[str, Dict[str, Any], asyncio.Future]] = deque()
        self.lock = asyncio.Lock()
        self.processing = False

    async def add_request(
        self,
        request_id: str,
        request_data: Dict[str, Any],
    ) -> Any:
        """添加请求到批处理队列"""
        future: asyncio.Future = asyncio.Future()

        async with self.lock:
            self.queue.append((request_id, request_data, future))

            # 如果达到批大小，立即处理
            if len(self.queue) >= self.batch_size:
                asyncio.create_task(self._process_batch())
            # 否则，安排延迟处理
            elif len(self.queue) == 1:
                asyncio.create_task(self._delayed_process())

        return await future

    async def _delayed_process(self) -> None:
        """延迟处理"""
        await asyncio.sleep(self.batch_timeout_ms / 1000.0)
        await self._process_batch()

    async def _process_batch(self) -> None:
        """处理批次"""
        async with self.lock:
            if not self.queue or self.processing:
                return

            self.processing = True
            batch = []
            while self.queue and len(batch) < self.batch_size:
                batch.append(self.queue.popleft())

        try:
            # 处理批次
            results = await self._batch_process(batch)

            # 返回结果
            for i, (request_id, request_data, future) in enumerate(batch):
                if not future.done():
                    future.set_result(results[i])

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            for request_id, request_data, future in batch:
                if not future.done():
                    future.set_exception(e)
        finally:
            self.processing = False

    async def _batch_process(self, batch: List[tuple]) -> List[Any]:
        """批量处理"""
        # 模拟处理
        await asyncio.sleep(0.01)
        return [{"status": "success", "data": f"result_{i}"} for i in range(len(batch))]


class APIResponseOptimizer:
    """API响应优化器"""

    def __init__(
        self,
        compression_type: CompressionType = CompressionType.GZIP,
        compression_threshold: int = 1024,
        batch_size: int = 100,
    ):
        self.compression_type = compression_type
        self.compression_threshold = compression_threshold
        self.compressor = ResponseCompressor()
        self.cache_manager = HTTPCacheManager()
        self.batch_processor = BatchRequestProcessor(batch_size=batch_size)
        self.stats = ResponseStats()

    async def optimize_response(
        self,
        data: Any,
        resource_id: Optional[str] = None,
        max_age: int = 3600,
    ) -> Dict[str, Any]:
        """优化响应"""
        start_time = time.time()

        try:
            # 序列化数据
            if isinstance(data, dict):
                json_data = json.dumps(data).encode("utf-8")
            else:
                json_data = json.dumps({"data": data}).encode("utf-8")

            original_size = len(json_data)
            self.stats.total_response_size += original_size

            # 压缩
            compressed_data = json_data
            compression_ratio = 0.0

            if self.compressor.should_compress(json_data, self.compression_threshold):
                if self.compression_type == CompressionType.GZIP:
                    compressed_data = self.compressor.compress_gzip(json_data)
                    compression_ratio = self.compressor.get_compression_ratio(
                        original_size,
                        len(compressed_data),
                    )

            self.stats.total_compressed_size += len(compressed_data)

            # 生成缓存头
            headers = {}
            if resource_id:
                await self.cache_manager.update_cache_info(resource_id, json_data)
                headers = await self.cache_manager.get_cache_headers(resource_id, max_age)

            # 添加压缩头
            if len(compressed_data) < len(json_data):
                headers["Content-Encoding"] = self.compression_type.value

            latency_ms = int((time.time() - start_time) * 1000)
            self.stats.total_requests += 1
            self.stats.total_latency_ms += latency_ms

            return {
                "success": True,
                "data": compressed_data,
                "headers": headers,
                "compression_ratio": compression_ratio,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            logger.error(f"Response optimization error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def batch_request(
        self,
        request_id: str,
        request_data: Dict[str, Any],
    ) -> Any:
        """批处理请求"""
        return await self.batch_processor.add_request(request_id, request_data)

    async def check_cache_validity(
        self,
        resource_id: str,
        etag: Optional[str] = None,
        last_modified: Optional[float] = None,
    ) -> bool:
        """检查缓存有效性"""
        is_modified = await self.cache_manager.is_modified(
            resource_id,
            etag,
            last_modified,
        )

        if is_modified:
            self.stats.cache_misses += 1
        else:
            self.stats.cache_hits += 1

        return is_modified

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": self.stats.total_requests,
            "total_responses": self.stats.total_responses,
            "average_latency_ms": self.stats.average_latency_ms,
            "total_response_size": self.stats.total_response_size,
            "total_compressed_size": self.stats.total_compressed_size,
            "compression_ratio": self.stats.compression_ratio,
            "cache_hit_rate": self.stats.cache_hit_rate,
            "cache_hits": self.stats.cache_hits,
            "cache_misses": self.stats.cache_misses,
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = ResponseStats()


# 全局优化器实例
_optimizer: Optional[APIResponseOptimizer] = None


def get_response_optimizer() -> APIResponseOptimizer:
    """获取全局API响应优化器"""
    global _optimizer
    if _optimizer is None:
        _optimizer = APIResponseOptimizer()
    return _optimizer


# 装饰器
def optimize_response(max_age: int = 3600):
    """响应优化装饰器"""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            optimizer = get_response_optimizer()
            resource_id = kwargs.get("resource_id")

            optimized = await optimizer.optimize_response(
                result,
                resource_id=resource_id,
                max_age=max_age,
            )

            return optimized

        return wrapper
    return decorator
