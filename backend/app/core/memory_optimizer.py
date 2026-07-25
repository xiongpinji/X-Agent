"""Memory optimization for X-Agent.

Implements strategies for:
- Object pooling and reuse
- Streaming large files
- Memory leak detection
- Resource cleanup
"""

from __future__ import annotations

import asyncio
import gc
import logging
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

import psutil

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class MemoryStats:
    """Memory usage statistics."""

    rss: int  # Resident set size
    vms: int  # Virtual memory size
    percent: float  # Percentage of total memory
    available: int  # Available memory
    timestamp: datetime


class MemoryMonitor:
    """Monitors memory usage and detects leaks."""

    def __init__(self, threshold_percent: float = 80.0):
        """Initialize memory monitor.

        Args:
            threshold_percent: Memory usage threshold percentage
        """
        self.threshold_percent = threshold_percent
        self.process = psutil.Process()
        self.baseline_memory: int | None = None
        self.memory_samples: list[MemoryStats] = []

    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics.

        Returns:
            Memory statistics
        """
        mem_info = self.process.memory_info()
        mem_percent = self.process.memory_percent()
        available = psutil.virtual_memory().available

        stats = MemoryStats(
            rss=mem_info.rss,
            vms=mem_info.vms,
            percent=mem_percent,
            available=available,
            timestamp=datetime.now(UTC),
        )

        self.memory_samples.append(stats)

        # Keep only last 100 samples
        if len(self.memory_samples) > 100:
            self.memory_samples = self.memory_samples[-100:]

        return stats

    def check_memory_threshold(self) -> bool:
        """Check if memory usage exceeds threshold.

        Returns:
            True if threshold exceeded
        """
        stats = self.get_memory_stats()
        exceeded = stats.percent > self.threshold_percent

        if exceeded:
            logger.warning(
                f"Memory usage exceeds threshold: {stats.percent:.1f}% > {self.threshold_percent}%"
            )

        return exceeded

    def detect_memory_leak(self, window_size: int = 10) -> bool:
        """Detect potential memory leak using trend analysis.

        Args:
            window_size: Number of samples to analyze

        Returns:
            True if potential leak detected
        """
        if len(self.memory_samples) < window_size:
            return False

        recent_samples = self.memory_samples[-window_size:]
        rss_values = [s.rss for s in recent_samples]

        # Check if memory is consistently increasing
        increasing_count = sum(
            1 for i in range(1, len(rss_values))
            if rss_values[i] > rss_values[i - 1]
        )

        # If 80% of samples show increase, likely a leak
        leak_detected = increasing_count >= (window_size * 0.8)

        if leak_detected:
            logger.warning(
                f"Potential memory leak detected: "
                f"{increasing_count}/{window_size} samples increasing"
            )

        return leak_detected

    def get_top_objects(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get top memory-consuming objects.

        Args:
            limit: Number of top objects to return

        Returns:
            List of (object_type, count) tuples
        """
        gc.collect()
        objects = gc.get_objects()

        type_counts: dict[str, int] = {}
        for obj in objects:
            obj_type = type(obj).__name__
            type_counts[obj_type] = type_counts.get(obj_type, 0) + 1

        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_types[:limit]

    def stats(self) -> dict[str, Any]:
        """Get memory monitor statistics.

        Returns:
            Statistics dictionary
        """
        current = self.get_memory_stats()
        return {
            "current_rss_mb": current.rss / (1024 * 1024),
            "current_vms_mb": current.vms / (1024 * 1024),
            "percent": current.percent,
            "available_mb": current.available / (1024 * 1024),
            "samples": len(self.memory_samples),
            "threshold_percent": self.threshold_percent,
        }


class ObjectPool(Generic[T]):
    """Object pool for reusing expensive objects."""

    def __init__(
        self,
        factory: Callable[[], T],
        reset_fn: Callable[[T], None] | None = None,
        initial_size: int = 10,
        max_size: int = 100,
    ):
        """Initialize object pool.

        Args:
            factory: Function to create new objects
            reset_fn: Optional function to reset objects for reuse
            initial_size: Initial pool size
            max_size: Maximum pool size
        """
        self.factory = factory
        self.reset_fn = reset_fn
        self.max_size = max_size
        self._pool: list[T] = [factory() for _ in range(initial_size)]
        self._in_use: set[int] = set()

    def acquire(self) -> T:
        """Acquire object from pool.

        Returns:
            Object from pool or newly created
        """
        obj = self._pool.pop() if self._pool else self.factory()

        obj_id = id(obj)
        self._in_use.add(obj_id)
        return obj

    def release(self, obj: T) -> None:
        """Release object back to pool.

        Args:
            obj: Object to release
        """
        obj_id = id(obj)
        if obj_id in self._in_use:
            self._in_use.remove(obj_id)

        # Reset object if reset function provided
        if self.reset_fn:
            self.reset_fn(obj)

        # Add back to pool if not at max size
        if len(self._pool) < self.max_size:
            self._pool.append(obj)

    @asynccontextmanager
    async def acquire_async(self):
        """Async context manager for acquiring and releasing objects.

        Yields:
            Object from pool
        """
        obj = self.acquire()
        try:
            yield obj
        finally:
            self.release(obj)

    def stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "available": len(self._pool),
            "in_use": len(self._in_use),
            "max_size": self.max_size,
        }


class StreamingFileReader:
    """Efficiently reads large files in chunks."""

    def __init__(self, chunk_size: int = 8192):
        """Initialize streaming file reader.

        Args:
            chunk_size: Size of chunks to read
        """
        self.chunk_size = chunk_size

    def read_file(self, file_path: str) -> Generator[bytes, None, None]:
        """Read file in chunks.

        Args:
            file_path: Path to file

        Yields:
            File chunks
        """
        try:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except OSError as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise

    async def read_file_async(self, file_path: str) -> AsyncGenerator[bytes, None]:
        """Read file asynchronously in chunks.

        Args:
            file_path: Path to file

        Yields:
            File chunks
        """
        loop = asyncio.get_event_loop()

        def read_chunk():
            with open(file_path, "rb") as f:
                return f.read(self.chunk_size)

        try:
            with open(file_path, "rb"):
                while True:
                    chunk = await loop.run_in_executor(None, read_chunk)
                    if not chunk:
                        break
                    yield chunk
        except OSError as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise

    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes.

        Args:
            file_path: Path to file

        Returns:
            File size
        """
        try:
            return len(open(file_path, "rb").read())
        except OSError as e:
            logger.error(f"Error getting file size: {e}")
            return 0


class ResourceCleaner:
    """Manages resource cleanup and garbage collection."""

    def __init__(self, gc_threshold: int = 1000):
        """Initialize resource cleaner.

        Args:
            gc_threshold: Number of objects before triggering GC
        """
        self.gc_threshold = gc_threshold
        self.object_count = 0

    async def cleanup(self) -> dict[str, Any]:
        """Perform cleanup operations.

        Returns:
            Cleanup statistics
        """
        # Force garbage collection
        collected = gc.collect()

        # Get memory stats
        process = psutil.Process()
        mem_info = process.memory_info()

        stats = {
            "objects_collected": collected,
            "rss_mb": mem_info.rss / (1024 * 1024),
            "vms_mb": mem_info.vms / (1024 * 1024),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info(f"Cleanup completed: {stats}")
        return stats

    async def periodic_cleanup(self, interval: float = 60.0) -> None:
        """Periodically perform cleanup.

        Args:
            interval: Cleanup interval in seconds
        """
        while True:
            await asyncio.sleep(interval)
            await self.cleanup()

    def should_cleanup(self) -> bool:
        """Check if cleanup should be triggered.

        Returns:
            True if cleanup should be triggered
        """
        self.object_count = len(gc.get_objects())
        return self.object_count > self.gc_threshold


class WeakRefCache(Generic[T]):
    """Cache using weak references to allow garbage collection."""

    def __init__(self):
        """Initialize weak reference cache."""
        import weakref
        self._cache: dict[str, weakref.ref] = {}

    def set(self, key: str, value: T) -> None:
        """Set value in cache using weak reference.

        Args:
            key: Cache key
            value: Value to cache
        """
        import weakref
        self._cache[key] = weakref.ref(value)

    def get(self, key: str) -> T | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if garbage collected
        """
        if key in self._cache:
            ref = self._cache[key]
            value = ref()
            if value is None:
                # Object was garbage collected
                del self._cache[key]
            return value
        return None

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Statistics dictionary
        """
        # Clean up dead references
        dead_refs = [k for k, v in self._cache.items() if v() is None]
        for k in dead_refs:
            del self._cache[k]

        return {
            "size": len(self._cache),
            "dead_refs_cleaned": len(dead_refs),
        }
