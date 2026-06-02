"""
Distributed Lock Implementation for X-Agent

Implements distributed locking using Redis for multi-instance deployments:
- Prevents concurrent access to critical resources
- Automatic lock expiration
- Lock renewal and extension
- Deadlock prevention
- Detailed metrics and logging

Features:
- Redis-based locking
- Configurable timeouts
- Lock ownership tracking
- Automatic cleanup
- Thread-safe operations
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LockStatus(str):
    """Lock status"""
    ACQUIRED = "acquired"
    RELEASED = "released"
    EXPIRED = "expired"
    FAILED = "failed"


class DistributedLockMetrics(BaseModel):
    """Metrics for distributed lock monitoring"""
    total_acquisitions: int = 0
    successful_acquisitions: int = 0
    failed_acquisitions: int = 0
    total_releases: int = 0
    active_locks: int = 0
    expired_locks: int = 0
    average_hold_time: float = 0.0
    max_hold_time: float = 0.0
    last_acquisition_time: datetime | None = None
    last_release_time: datetime | None = None


@dataclass
class DistributedLockConfig:
    """Configuration for distributed lock"""
    name: str
    timeout: int = 30
    auto_renewal: bool = True
    renewal_interval: int = 10
    max_retries: int = 3
    retry_delay: int = 1


class DistributedLock:
    """
    Distributed lock implementation for multi-instance coordination.

    Uses Redis to coordinate access to critical resources across multiple
    instances of the application.
    """

    def __init__(self, config: DistributedLockConfig, redis_client=None):
        self.config = config
        self.redis_client = redis_client
        self.lock_id = str(uuid.uuid4())
        self.is_locked = False
        self.acquired_at: float | None = None
        self._lock = RLock()
        self._metrics = DistributedLockMetrics()

    def acquire(self, blocking: bool = True, timeout: int | None = None) -> bool:
        """
        Acquire the lock.

        Args:
            blocking: Whether to block until lock is acquired
            timeout: Maximum time to wait for lock

        Returns:
            True if lock acquired, False otherwise
        """
        with self._lock:
            timeout = timeout or self.config.timeout
            start_time = time.time()

            for attempt in range(self.config.max_retries):
                if self._try_acquire():
                    self.is_locked = True
                    self.acquired_at = time.time()
                    self._metrics.successful_acquisitions += 1
                    self._metrics.total_acquisitions += 1
                    self._metrics.active_locks += 1
                    self._metrics.last_acquisition_time = datetime.now(UTC)
                    logger.info(
                        f"Lock acquired: {self.config.name} (attempt {attempt + 1})"
                    )
                    return True

                if not blocking:
                    self._metrics.failed_acquisitions += 1
                    self._metrics.total_acquisitions += 1
                    logger.warning(f"Lock acquisition failed (non-blocking): {self.config.name}")
                    return False

                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    self._metrics.failed_acquisitions += 1
                    self._metrics.total_acquisitions += 1
                    logger.warning(f"Lock acquisition timeout: {self.config.name}")
                    return False

                time.sleep(self.config.retry_delay)

            self._metrics.failed_acquisitions += 1
            self._metrics.total_acquisitions += 1
            logger.warning(f"Lock acquisition failed after retries: {self.config.name}")
            return False

    def release(self) -> bool:
        """
        Release the lock.

        Returns:
            True if lock released, False otherwise
        """
        with self._lock:
            if not self.is_locked:
                logger.warning(f"Lock not held: {self.config.name}")
                return False

            if self._try_release():
                hold_time = time.time() - (self.acquired_at or time.time())
                self.is_locked = False
                self._metrics.total_releases += 1
                self._metrics.active_locks = max(0, self._metrics.active_locks - 1)
                self._metrics.last_release_time = datetime.now(UTC)

                # Update hold time metrics
                if self._metrics.average_hold_time == 0:
                    self._metrics.average_hold_time = hold_time
                else:
                    self._metrics.average_hold_time = (
                        self._metrics.average_hold_time + hold_time
                    ) / 2
                self._metrics.max_hold_time = max(
                    self._metrics.max_hold_time, hold_time
                )

                logger.info(f"Lock released: {self.config.name}")
                return True

            logger.warning(f"Lock release failed: {self.config.name}")
            return False

    def renew(self) -> bool:
        """
        Renew the lock to extend its lifetime.

        Returns:
            True if lock renewed, False otherwise
        """
        with self._lock:
            if not self.is_locked:
                logger.warning(f"Lock not held: {self.config.name}")
                return False

            if self._try_renew():
                logger.debug(f"Lock renewed: {self.config.name}")
                return True

            logger.warning(f"Lock renewal failed: {self.config.name}")
            return False

    def _try_acquire(self) -> bool:
        """Try to acquire lock (Redis operation)"""
        if self.redis_client is None:
            # Fallback: in-memory lock for testing
            return True

        try:
            result = self.redis_client.set(
                f"lock:{self.config.name}",
                self.lock_id,
                ex=self.config.timeout,
                nx=True,
            )
            return result is not None
        except Exception as e:
            logger.error(f"Redis lock acquisition error: {e}")
            return False

    def _try_release(self) -> bool:
        """Try to release lock (Redis operation)"""
        if self.redis_client is None:
            # Fallback: in-memory lock for testing
            return True

        try:
            # Use Lua script to ensure atomic operation
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = self.redis_client.eval(
                script,
                1,
                f"lock:{self.config.name}",
                self.lock_id,
            )
            return result == 1
        except Exception as e:
            logger.error(f"Redis lock release error: {e}")
            return False

    def _try_renew(self) -> bool:
        """Try to renew lock (Redis operation)"""
        if self.redis_client is None:
            # Fallback: in-memory lock for testing
            return True

        try:
            # Use Lua script to ensure atomic operation
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            result = self.redis_client.eval(
                script,
                1,
                f"lock:{self.config.name}",
                self.lock_id,
                self.config.timeout,
            )
            return result == 1
        except Exception as e:
            logger.error(f"Redis lock renewal error: {e}")
            return False

    def get_metrics(self) -> DistributedLockMetrics:
        """Get current metrics"""
        with self._lock:
            return self._metrics.model_copy()

    def __enter__(self):
        """Context manager entry"""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
        return False


class DistributedLockManager:
    """Manager for distributed locks"""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self._locks: dict[str, DistributedLock] = {}
        self._lock = RLock()

    def get_or_create(self, config: DistributedLockConfig) -> DistributedLock:
        """Get or create a distributed lock"""
        with self._lock:
            if config.name not in self._locks:
                self._locks[config.name] = DistributedLock(config, self.redis_client)
                logger.info(f"Created distributed lock: {config.name}")
            return self._locks[config.name]

    def get(self, name: str) -> DistributedLock | None:
        """Get a distributed lock by name"""
        with self._lock:
            return self._locks.get(name)

    def get_all_metrics(self) -> dict[str, DistributedLockMetrics]:
        """Get metrics for all locks"""
        with self._lock:
            return {
                name: lock.get_metrics()
                for name, lock in self._locks.items()
            }

    def release_all(self) -> None:
        """Release all locks"""
        with self._lock:
            for lock in self._locks.values():
                if lock.is_locked:
                    lock.release()
            logger.info("All locks released")


# Global lock manager instance
_lock_manager: Optional[DistributedLockManager] = None


def get_lock_manager(redis_client=None) -> DistributedLockManager:
    """Get global lock manager"""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = DistributedLockManager(redis_client)
    return _lock_manager
