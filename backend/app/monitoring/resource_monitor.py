"""Resource monitoring for CPU, memory, and disk usage."""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.app.core.metrics import metrics_collector

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Monitor system resources and update metrics."""

    def __init__(self, interval: int = 30) -> None:
        """Initialize resource monitor.

        Args:
            interval: Monitoring interval in seconds
        """
        self.interval = interval
        self.running = False
        self._psutil_warned = False

    def start(self) -> None:
        """Start resource monitoring loop (blocking; run it in a worker thread)."""
        self.running = True
        logger.info(f"Resource monitoring started with {self.interval}s interval")

        while self.running:
            try:
                self.collect_once()
            except Exception as e:
                logger.error(f"Error collecting resource metrics: {e}")

            time.sleep(self.interval)

    def stop(self) -> None:
        """Stop resource monitoring."""
        self.running = False
        logger.info("Resource monitoring stopped")

    def collect_once(self) -> dict[str, Any]:
        """Collect system resources once and publish saturation metrics (P1-4).

        与 ``start()`` 的区别：不 sleep、不循环，可由 ``/metrics`` scrape 或任何
        定时器反复调用。使用 ``psutil.cpu_percent(interval=None)`` —— **非阻塞**，
        返回自上次调用以来的使用率（首个样本仅用于打点）。

        关键修复（P1-4）：
        - CPU / 内存**无条件写入**，不再挂在 ``if disk_usage:`` 之下 —— 旧实现里
          磁盘枚举失败或为空时，会把 CPU / 内存饱和度一起拖没。
        - 配合 ``set_resource_metrics`` 的 ``is not None`` 语义，合法的 0 值
          （空闲 CPU）也能落位，而不是被静默丢弃。

        Returns:
            本次采集快照；psutil 缺失时返回空 dict。
        """
        try:
            import psutil
        except ImportError:
            if not self._psutil_warned:
                logger.warning("psutil not installed, resource monitoring disabled")
                self._psutil_warned = True
            return {}

        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()

        disk_usage: dict[str, int] = {}
        for partition in psutil.disk_partitions():
            try:
                disk_usage[partition.mountpoint] = psutil.disk_usage(partition.mountpoint).used
            except (OSError, PermissionError):
                continue

        metrics_collector.set_resource_metrics(
            cpu_percent=cpu_percent,
            memory_bytes=memory.used,
            disk_bytes=disk_usage or None,
        )

        logger.debug(
            "Resource metrics: CPU=%s%%, Memory=%s%%, Disk partitions=%s",
            cpu_percent,
            memory.percent,
            len(disk_usage),
        )
        return {
            "cpu_percent": cpu_percent,
            "memory_used": memory.used,
            "memory_percent": memory.percent,
            "disk_partitions": len(disk_usage),
        }

    # 向后兼容别名（旧名 ``_collect_metrics``）；新代码请用 ``collect_once``。
    _collect_metrics = collect_once


class DatabaseConnectionMonitor:
    """Monitor database connection pool."""

    def __init__(self, pool: Any, interval: int = 30) -> None:
        """Initialize database connection monitor.

        Args:
            pool: Database connection pool
            interval: Monitoring interval in seconds
        """
        self.pool = pool
        self.interval = interval
        self.running = False

    def start(self) -> None:
        """Start monitoring."""
        self.running = True
        logger.info("Database connection monitoring started")

        while self.running:
            try:
                self._collect_metrics()
            except Exception as e:
                logger.error(f"Error collecting database metrics: {e}")

            time.sleep(self.interval)

    def stop(self) -> None:
        """Stop monitoring."""
        self.running = False

    def _collect_metrics(self) -> None:
        """Collect database connection metrics."""
        try:
            # Get pool size and active connections
            pool_size = getattr(self.pool, "size", 0)
            active_connections = getattr(self.pool, "checked_out", 0)

            metrics_collector.set_db_connection_pool_size(pool_size)
            metrics_collector.set_db_active_connections(active_connections)

            logger.debug(f"Database pool: size={pool_size}, active={active_connections}")

        except Exception as e:
            logger.error(f"Error collecting database pool metrics: {e}")


class CacheMonitor:
    """Monitor cache performance."""

    def __init__(self, cache: Any, cache_name: str, interval: int = 60) -> None:
        """Initialize cache monitor.

        Args:
            cache: Cache instance
            cache_name: Name of the cache
            interval: Monitoring interval in seconds
        """
        self.cache = cache
        self.cache_name = cache_name
        self.interval = interval
        self.running = False

    def start(self) -> None:
        """Start monitoring."""
        self.running = True
        logger.info(f"Cache monitoring started for {self.cache_name}")

        while self.running:
            try:
                self._collect_metrics()
            except Exception as e:
                logger.error(f"Error collecting cache metrics: {e}")

            time.sleep(self.interval)

    def stop(self) -> None:
        """Stop monitoring."""
        self.running = False

    def _collect_metrics(self) -> None:
        """Collect cache metrics."""
        try:
            # Get cache size
            cache_size = self._get_cache_size()
            if cache_size > 0:
                metrics_collector.set_cache_size(self.cache_name, cache_size)

            logger.debug(f"Cache {self.cache_name} size: {cache_size} bytes")

        except Exception as e:
            logger.error(f"Error collecting cache metrics: {e}")

    def _get_cache_size(self) -> int:
        """Get cache size in bytes."""
        try:
            if hasattr(self.cache, "info"):
                info = self.cache.info()
                return info.get("size", 0)
            elif hasattr(self.cache, "size"):
                return self.cache.size()
            else:
                return 0
        except Exception:
            return 0


class PerformanceMonitor:
    """Monitor application performance metrics."""

    def __init__(self, interval: int = 60) -> None:
        """Initialize performance monitor.

        Args:
            interval: Monitoring interval in seconds
        """
        self.interval = interval
        self.running = False
        self.start_time = time.time()

    def start(self) -> None:
        """Start monitoring."""
        self.running = True
        logger.info("Performance monitoring started")

        while self.running:
            try:
                self._collect_metrics()
            except Exception as e:
                logger.error(f"Error collecting performance metrics: {e}")

            time.sleep(self.interval)

    def stop(self) -> None:
        """Stop monitoring."""
        self.running = False

    def _collect_metrics(self) -> None:
        """Collect performance metrics."""
        try:
            uptime = time.time() - self.start_time
            logger.debug(f"Application uptime: {uptime:.0f}s")

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")


# ─── P1-4：saturation 刷新入口（供 /metrics scrape 调用）─────────────────────

_saturation_monitor: ResourceMonitor | None = None


def refresh_saturation_metrics() -> dict[str, Any]:
    """刷新 saturation metrics 并返回采集快照（P1-4）。

    ``/metrics`` 被 Prometheus scrape 时调用。这里刻意采用 **pull 模型**，而不是
    再往 lifespan 里塞一个后台常驻循环：
    1. gauge 的语义本就是"scrape 时刻的瞬时值"，scrape 时取最新读数最准确；
    2. 避免新增一个需要在 shutdown 里清理的后台任务 —— 现有测试已存在
       lifespan 后台任务未清理导致的顺序相关 flake，不宜再加重。
    ``psutil.cpu_percent(interval=None)`` 非阻塞，可直接在异步路由中调用。
    """
    global _saturation_monitor
    if _saturation_monitor is None:
        _saturation_monitor = ResourceMonitor()
    try:
        return _saturation_monitor.collect_once()
    except Exception as e:  # 观测能力故障绝不能让 /metrics 整体挂掉
        logger.warning("saturation refresh failed: %s", e)
        return {}

