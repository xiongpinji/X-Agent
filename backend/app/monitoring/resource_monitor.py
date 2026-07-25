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

    def start(self) -> None:
        """Start resource monitoring loop."""
        self.running = True
        logger.info(f"Resource monitoring started with {self.interval}s interval")

        while self.running:
            try:
                self._collect_metrics()
            except Exception as e:
                logger.error(f"Error collecting resource metrics: {e}")

            time.sleep(self.interval)

    def stop(self) -> None:
        """Stop resource monitoring."""
        self.running = False
        logger.info("Resource monitoring stopped")

    def _collect_metrics(self) -> None:
        """Collect and update resource metrics."""
        try:
            import psutil

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics_collector.cpu_usage_percent.set(cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            metrics_collector.memory_usage_bytes.set(memory.used)

            # Disk usage
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.mountpoint] = usage.used
                except (OSError, PermissionError):
                    pass

            if disk_usage:
                metrics_collector.set_resource_metrics(
                    cpu_percent=cpu_percent,
                    memory_bytes=memory.used,
                    disk_bytes=disk_usage,
                )

            logger.debug(
                f"Resource metrics: CPU={cpu_percent}%, Memory={memory.percent}%, "
                f"Disk partitions={len(disk_usage)}"
            )

        except ImportError:
            logger.warning("psutil not installed, resource monitoring disabled")
            self.running = False


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
