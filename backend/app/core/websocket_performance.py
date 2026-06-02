"""WebSocket Performance Optimization

Optimizes WebSocket connections for real-time communication:
- Connection pooling and reuse
- Message batching and compression
- Latency monitoring (< 50ms target)
- Backpressure handling
- Memory-efficient streaming
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("xagent.websocket_perf")


@dataclass
class WebSocketMetrics:
    """WebSocket connection metrics."""
    connection_id: str
    connected_at: float = field(default_factory=time.time)
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    errors: int = 0
    last_activity: float = field(default_factory=time.time)

    @property
    def connection_duration_seconds(self) -> float:
        """Get connection duration in seconds."""
        return time.time() - self.connected_at

    @property
    def messages_per_second(self) -> float:
        """Calculate message throughput."""
        duration = self.connection_duration_seconds
        if duration == 0:
            return 0.0
        return (self.messages_sent + self.messages_received) / duration

    @property
    def bytes_per_second(self) -> float:
        """Calculate data throughput."""
        duration = self.connection_duration_seconds
        if duration == 0:
            return 0.0
        return (self.bytes_sent + self.bytes_received) / duration


class WebSocketConnectionPool:
    """Manage WebSocket connections efficiently."""

    def __init__(self, max_connections: int = 1000):
        self.max_connections = max_connections
        self.connections: dict[str, Any] = {}
        self.metrics: dict[str, WebSocketMetrics] = {}
        self._lock = asyncio.Lock()

    async def add_connection(self, connection_id: str, connection: Any) -> None:
        """Add connection to pool."""
        async with self._lock:
            if len(self.connections) >= self.max_connections:
                logger.warning(f"Connection pool full ({self.max_connections})")
                return

            self.connections[connection_id] = connection
            self.metrics[connection_id] = WebSocketMetrics(connection_id=connection_id)

    async def remove_connection(self, connection_id: str) -> None:
        """Remove connection from pool."""
        async with self._lock:
            if connection_id in self.connections:
                del self.connections[connection_id]

    async def get_connection(self, connection_id: str) -> Optional[Any]:
        """Get connection from pool."""
        async with self._lock:
            return self.connections.get(connection_id)

    async def broadcast_message(self, message: dict[str, Any], exclude_id: Optional[str] = None) -> int:
        """Broadcast message to all connections."""
        sent_count = 0
        async with self._lock:
            for conn_id, connection in self.connections.items():
                if exclude_id and conn_id == exclude_id:
                    continue

                try:
                    await connection.send_json(message)
                    sent_count += 1
                    if conn_id in self.metrics:
                        self.metrics[conn_id].messages_sent += 1
                        self.metrics[conn_id].bytes_sent += len(json.dumps(message))
                except Exception as e:
                    logger.error(f"Failed to send message to {conn_id}: {e}")
                    if conn_id in self.metrics:
                        self.metrics[conn_id].errors += 1

        return sent_count

    async def get_metrics(self, connection_id: str) -> Optional[WebSocketMetrics]:
        """Get metrics for a connection."""
        async with self._lock:
            return self.metrics.get(connection_id)

    async def get_pool_stats(self) -> dict[str, Any]:
        """Get overall pool statistics."""
        async with self._lock:
            if not self.metrics:
                return {}

            latencies = [m.avg_latency_ms for m in self.metrics.values() if m.avg_latency_ms > 0]
            return {
                "active_connections": len(self.connections),
                "max_connections": self.max_connections,
                "total_messages_sent": sum(m.messages_sent for m in self.metrics.values()),
                "total_messages_received": sum(m.messages_received for m in self.metrics.values()),
                "total_bytes_sent": sum(m.bytes_sent for m in self.metrics.values()),
                "total_bytes_received": sum(m.bytes_received for m in self.metrics.values()),
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
                "max_latency_ms": max(latencies) if latencies else 0.0,
                "total_errors": sum(m.errors for m in self.metrics.values()),
            }


class MessageBatcher:
    """Batch WebSocket messages for efficient transmission."""

    def __init__(self, batch_size: int = 10, batch_timeout_ms: int = 50):
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.pending_messages: list[dict[str, Any]] = []
        self.batch_event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def add_message(self, message: dict[str, Any]) -> None:
        """Add message to batch."""
        async with self._lock:
            self.pending_messages.append(message)

            if len(self.pending_messages) >= self.batch_size:
                self.batch_event.set()

    async def get_batch(self) -> list[dict[str, Any]]:
        """Get pending messages as a batch."""
        try:
            await asyncio.wait_for(
                self.batch_event.wait(),
                timeout=self.batch_timeout_ms / 1000,
            )
        except asyncio.TimeoutError:
            pass

        async with self._lock:
            batch = self.pending_messages.copy()
            self.pending_messages.clear()
            self.batch_event.clear()
            return batch


class LatencyMonitor:
    """Monitor WebSocket latency."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.latencies: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def record_latency(self, connection_id: str, latency_ms: float) -> None:
        """Record latency for a connection."""
        async with self._lock:
            if connection_id not in self.latencies:
                self.latencies[connection_id] = []

            self.latencies[connection_id].append(latency_ms)

            # Keep only recent measurements
            if len(self.latencies[connection_id]) > self.window_size:
                self.latencies[connection_id].pop(0)

            # Log if latency exceeds threshold
            if latency_ms > 50:
                logger.warning(f"High WebSocket latency for {connection_id}: {latency_ms}ms")

    async def get_stats(self, connection_id: str) -> dict[str, float]:
        """Get latency statistics for a connection."""
        async with self._lock:
            latencies = self.latencies.get(connection_id, [])

        if not latencies:
            return {}

        latencies_sorted = sorted(latencies)
        return {
            "avg_latency_ms": sum(latencies) / len(latencies),
            "p50_latency_ms": latencies_sorted[len(latencies_sorted) // 2],
            "p95_latency_ms": latencies_sorted[int(len(latencies_sorted) * 0.95)],
            "p99_latency_ms": latencies_sorted[int(len(latencies_sorted) * 0.99)],
            "max_latency_ms": max(latencies),
            "min_latency_ms": min(latencies),
        }


class BackpressureHandler:
    """Handle backpressure in WebSocket communication."""

    def __init__(self, buffer_size: int = 1000, high_water_mark: int = 800):
        self.buffer_size = buffer_size
        self.high_water_mark = high_water_mark
        self.buffers: dict[str, list[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def add_message(self, connection_id: str, message: dict[str, Any]) -> bool:
        """Add message to buffer. Returns False if buffer is full."""
        async with self._lock:
            if connection_id not in self.buffers:
                self.buffers[connection_id] = []

            buffer = self.buffers[connection_id]

            if len(buffer) >= self.buffer_size:
                logger.warning(f"Backpressure: buffer full for {connection_id}")
                return False

            buffer.append(message)
            return True

    async def get_buffer_status(self, connection_id: str) -> dict[str, Any]:
        """Get buffer status for a connection."""
        async with self._lock:
            buffer = self.buffers.get(connection_id, [])
            buffer_size = len(buffer)
            is_high_water = buffer_size >= self.high_water_mark

            return {
                "buffer_size": buffer_size,
                "max_size": self.buffer_size,
                "high_water_mark": self.high_water_mark,
                "is_high_water": is_high_water,
                "utilization_percent": (buffer_size / self.buffer_size) * 100,
            }

    async def flush_buffer(self, connection_id: str) -> list[dict[str, Any]]:
        """Flush buffer for a connection."""
        async with self._lock:
            buffer = self.buffers.get(connection_id, [])
            messages = buffer.copy()
            self.buffers[connection_id] = []
            return messages


class MessageCompressor:
    """Compress WebSocket messages."""

    @staticmethod
    def should_compress(message_size_bytes: int, threshold_bytes: int = 512) -> bool:
        """Determine if message should be compressed."""
        return message_size_bytes > threshold_bytes

    @staticmethod
    def estimate_compression_ratio(message: dict[str, Any]) -> float:
        """Estimate compression ratio for a message."""
        import zlib

        message_json = json.dumps(message)
        original_size = len(message_json.encode())
        compressed_size = len(zlib.compress(message_json.encode()))

        if original_size == 0:
            return 0.0

        return (original_size - compressed_size) / original_size


# Global WebSocket connection pool
_ws_pool = WebSocketConnectionPool()


async def get_websocket_pool() -> WebSocketConnectionPool:
    """Get global WebSocket connection pool."""
    return _ws_pool
