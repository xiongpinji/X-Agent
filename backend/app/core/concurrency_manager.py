"""
Concurrency management initialization and lifecycle for X-Agent.

Implements:
- Unified initialization of all concurrency components
- Graceful shutdown
- Configuration management
- Integration with FastAPI
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from backend.app.core.pools import (
    PoolConfig,
    close_all_pools,
    get_http_pool,
    get_postgres_pool,
    get_redis_pool,
)
from backend.app.core.concurrency_limiter import (
    close_all_limiters,
    close_all_queues,
    get_adaptive_limiter,
    get_limiter,
    get_rate_limiter,
    get_task_queue,
)
from backend.app.core.http_client import close_http_client, get_http_client
from backend.app.core.resource_monitor import close_resource_monitor, get_resource_monitor

logger = logging.getLogger(__name__)


class ConcurrencyConfig:
    """Configuration for concurrency management."""

    def __init__(
        self,
        # Pool configuration
        pool_min_size: int = 5,
        pool_max_size: int = 20,
        pool_timeout: float = 30.0,
        pool_idle_timeout: float = 300.0,
        # Concurrency limiting
        default_concurrency_limit: int = 10,
        adaptive_concurrency_enabled: bool = True,
        adaptive_min_limit: int = 5,
        adaptive_max_limit: int = 50,
        # Rate limiting
        rate_limit_enabled: bool = True,
        rate_limit_rate: float = 100.0,
        rate_limit_burst: int = 100,
        # Task queue
        task_queue_enabled: bool = True,
        task_queue_max_size: int = 1000,
        task_queue_workers: int = 4,
        # Monitoring
        monitoring_enabled: bool = True,
        monitoring_interval: float = 10.0,
    ) -> None:
        self.pool_min_size = pool_min_size
        self.pool_max_size = pool_max_size
        self.pool_timeout = pool_timeout
        self.pool_idle_timeout = pool_idle_timeout

        self.default_concurrency_limit = default_concurrency_limit
        self.adaptive_concurrency_enabled = adaptive_concurrency_enabled
        self.adaptive_min_limit = adaptive_min_limit
        self.adaptive_max_limit = adaptive_max_limit

        self.rate_limit_enabled = rate_limit_enabled
        self.rate_limit_rate = rate_limit_rate
        self.rate_limit_burst = rate_limit_burst

        self.task_queue_enabled = task_queue_enabled
        self.task_queue_max_size = task_queue_max_size
        self.task_queue_workers = task_queue_workers

        self.monitoring_enabled = monitoring_enabled
        self.monitoring_interval = monitoring_interval

    def get_pool_config(self) -> PoolConfig:
        """Get pool configuration."""
        return PoolConfig(
            min_size=self.pool_min_size,
            max_size=self.pool_max_size,
            timeout=self.pool_timeout,
            idle_timeout=self.pool_idle_timeout,
        )


class ConcurrencyManager:
    """
    Manages all concurrency components for X-Agent.

    Features:
    - Unified initialization
    - Graceful shutdown
    - Component lifecycle management
    - Metrics collection
    """

    def __init__(self, config: Optional[ConcurrencyConfig] = None) -> None:
        self._config = config or ConcurrencyConfig()
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(
        self,
        database_url: Optional[str] = None,
        redis_url: Optional[str] = None,
    ) -> None:
        """Initialize all concurrency components."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            logger.info("Initializing concurrency management...")

            try:
                # Initialize connection pools
                pool_config = self._config.get_pool_config()

                if database_url:
                    postgres_pool = get_postgres_pool(database_url, pool_config)
                    await postgres_pool.initialize()
                    logger.info("PostgreSQL pool initialized")

                if redis_url:
                    redis_pool = get_redis_pool(redis_url, pool_config)
                    await redis_pool.initialize()
                    logger.info("Redis pool initialized")

                # Initialize HTTP client
                http_client = get_http_client()
                await http_client.initialize()
                logger.info("HTTP client initialized")

                # Initialize concurrency limiters
                if self._config.adaptive_concurrency_enabled:
                    adaptive_limiter = get_adaptive_limiter(
                        "default",
                        initial_limit=self._config.default_concurrency_limit,
                        min_limit=self._config.adaptive_min_limit,
                        max_limit=self._config.adaptive_max_limit,
                    )
                    await adaptive_limiter.initialize()
                    logger.info("Adaptive concurrency limiter initialized")
                else:
                    limiter = get_limiter(
                        "default",
                        max_concurrent=self._config.default_concurrency_limit,
                    )
                    logger.info("Concurrency limiter initialized")

                # Initialize rate limiters
                if self._config.rate_limit_enabled:
                    rate_limiter = get_rate_limiter(
                        "default",
                        rate=self._config.rate_limit_rate,
                        burst=self._config.rate_limit_burst,
                    )
                    logger.info("Rate limiter initialized")

                # Initialize task queues
                if self._config.task_queue_enabled:
                    task_queue = get_task_queue(
                        "default",
                        max_queue_size=self._config.task_queue_max_size,
                        worker_count=self._config.task_queue_workers,
                    )
                    await task_queue.start()
                    logger.info("Task queue initialized")

                # Initialize resource monitor
                if self._config.monitoring_enabled:
                    monitor = get_resource_monitor()
                    await monitor.start()
                    logger.info("Resource monitor initialized")

                self._initialized = True
                logger.info("Concurrency management initialized successfully")

            except Exception as e:
                logger.error(f"Failed to initialize concurrency management: {e}")
                await self.shutdown()
                raise

    async def shutdown(self) -> None:
        """Shutdown all concurrency components."""
        if not self._initialized:
            return

        async with self._lock:
            if not self._initialized:
                return

            logger.info("Shutting down concurrency management...")

            try:
                # Stop resource monitor
                await close_resource_monitor()

                # Close task queues
                await close_all_queues()

                # Close limiters
                await close_all_limiters()

                # Close HTTP client
                await close_http_client()

                # Close connection pools
                await close_all_pools()

                self._initialized = False
                logger.info("Concurrency management shutdown complete")

            except Exception as e:
                logger.error(f"Error during concurrency management shutdown: {e}")

    def get_metrics(self) -> dict[str, Any]:
        """Get metrics from all components."""
        metrics = {
            "timestamp": asyncio.get_event_loop().time(),
            "components": {},
        }

        try:
            # Get resource monitor report
            monitor = get_resource_monitor()
            metrics["components"]["resource_monitor"] = monitor.get_report()
        except Exception as e:
            logger.error(f"Error getting resource monitor metrics: {e}")

        return metrics

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of all components."""
        try:
            monitor = get_resource_monitor()
            return monitor.get_health_status()
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {"healthy": False, "issues": [{"message": str(e)}]}


# Global concurrency manager
_concurrency_manager: Optional[ConcurrencyManager] = None


def get_concurrency_manager(
    config: Optional[ConcurrencyConfig] = None,
) -> ConcurrencyManager:
    """Get or create the global concurrency manager."""
    global _concurrency_manager
    if _concurrency_manager is None:
        _concurrency_manager = ConcurrencyManager(config)
    return _concurrency_manager


async def initialize_concurrency(
    database_url: Optional[str] = None,
    redis_url: Optional[str] = None,
    config: Optional[ConcurrencyConfig] = None,
) -> ConcurrencyManager:
    """Initialize concurrency management."""
    manager = get_concurrency_manager(config)
    await manager.initialize(database_url=database_url, redis_url=redis_url)
    return manager


async def shutdown_concurrency() -> None:
    """Shutdown concurrency management."""
    global _concurrency_manager
    if _concurrency_manager is not None:
        await _concurrency_manager.shutdown()
        _concurrency_manager = None
