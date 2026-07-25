"""
Performance monitoring middleware.

Provides:
- Request duration tracking
- Slow request detection and alerting
- Resource usage monitoring
- Prometheus metrics export
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Callable
from threading import Lock
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

from .base import BaseMiddleware

logger = logging.getLogger(__name__)


class PerformanceMonitorMiddleware(BaseMiddleware):
    """
    Performance monitoring middleware.

    Configuration:
        slow_request_threshold: Duration threshold for slow requests (seconds, default: 1.0)
        max_slow_requests_history: Maximum slow requests to keep (default: 100)
        enable_metrics: Enable Prometheus metrics (default: False)
    """

    DEFAULT_SLOW_REQUEST_THRESHOLD = 1.0  # seconds
    DEFAULT_MAX_SLOW_REQUESTS_HISTORY = 100

    def __init__(self, app: Any, **config: Any) -> None:
        """Initialize performance monitoring middleware."""
        super().__init__(app, **config)
        self.slow_request_threshold = config.get(
            "slow_request_threshold", self.DEFAULT_SLOW_REQUEST_THRESHOLD
        )
        self.max_slow_requests_history = config.get(
            "max_slow_requests_history", self.DEFAULT_MAX_SLOW_REQUESTS_HISTORY
        )
        self.enable_metrics = config.get("enable_metrics", False)

        # Statistics
        self._lock = Lock()
        self._request_count = 0
        self._total_duration = 0.0
        self._slow_requests: deque = deque(maxlen=self.max_slow_requests_history)
        self._error_count = 0
        self._path_stats: dict[str, dict[str, Any]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor performance."""
        if not self.is_enabled():
            return await call_next(request)

        start_time = time.time()
        path = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Update statistics
            self._update_stats(path, method, duration, response.status_code, False)

            # Detect slow requests
            if duration > self.slow_request_threshold:
                self._record_slow_request(path, method, duration, response.status_code)

            return response

        except Exception as e:
            duration = time.time() - start_time
            self._update_stats(path, method, duration, 500, True)
            self.logger.error(f"Request failed after {duration:.2f}s: {e}")
            raise

    def _update_stats(
        self,
        path: str,
        method: str,
        duration: float,
        status_code: int,
        is_error: bool,
    ) -> None:
        """Update statistics."""
        with self._lock:
            self._request_count += 1
            self._total_duration += duration

            if is_error:
                self._error_count += 1

            # Update path statistics
            key = f"{method} {path}"
            if key not in self._path_stats:
                self._path_stats[key] = {
                    "count": 0,
                    "total_duration": 0.0,
                    "min_duration": float("inf"),
                    "max_duration": 0.0,
                    "error_count": 0,
                }

            stats = self._path_stats[key]
            stats["count"] += 1
            stats["total_duration"] += duration
            stats["min_duration"] = min(stats["min_duration"], duration)
            stats["max_duration"] = max(stats["max_duration"], duration)

            if is_error:
                stats["error_count"] += 1

    def _record_slow_request(
        self,
        path: str,
        method: str,
        duration: float,
        status_code: int,
    ) -> None:
        """Record slow request."""
        slow_request = {
            "path": path,
            "method": method,
            "duration": duration,
            "status_code": status_code,
            "timestamp": time.time(),
        }

        with self._lock:
            self._slow_requests.append(slow_request)

        # Log slow request
        log_data = {
            "event": "slow_request",
            "timestamp": time.time(),
            "path": path,
            "method": method,
            "duration_ms": round(duration * 1000, 2),
            "status_code": status_code,
            "threshold_ms": round(self.slow_request_threshold * 1000, 2),
        }

        self.logger.warning(json.dumps(log_data, ensure_ascii=False))

    def get_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        with self._lock:
            avg_duration = (
                self._total_duration / self._request_count if self._request_count > 0 else 0
            )

            # Calculate path statistics
            path_stats = {}
            for key, stats in self._path_stats.items():
                path_stats[key] = {
                    "count": stats["count"],
                    "avg_duration_ms": round(
                        (stats["total_duration"] / stats["count"] * 1000)
                        if stats["count"] > 0
                        else 0,
                        2,
                    ),
                    "min_duration_ms": round(stats["min_duration"] * 1000, 2),
                    "max_duration_ms": round(stats["max_duration"] * 1000, 2),
                    "error_count": stats["error_count"],
                }

            return {
                "total_requests": self._request_count,
                "total_errors": self._error_count,
                "error_rate": (
                    round(self._error_count / self._request_count * 100, 2)
                    if self._request_count > 0
                    else 0
                ),
                "average_duration_ms": round(avg_duration * 1000, 2),
                "slow_requests_count": len(self._slow_requests),
                "recent_slow_requests": list(self._slow_requests)[-10:],
                "path_statistics": path_stats,
            }

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics."""
        stats = self.get_stats()

        metrics = []
        metrics.append("# HELP http_requests_total Total HTTP requests")
        metrics.append("# TYPE http_requests_total counter")
        metrics.append(f"http_requests_total {stats['total_requests']}")

        metrics.append("# HELP http_errors_total Total HTTP errors")
        metrics.append("# TYPE http_errors_total counter")
        metrics.append(f"http_errors_total {stats['total_errors']}")

        metrics.append("# HELP http_request_duration_ms Average request duration")
        metrics.append("# TYPE http_request_duration_ms gauge")
        metrics.append(f"http_request_duration_ms {stats['average_duration_ms']}")

        metrics.append("# HELP http_slow_requests_total Total slow requests")
        metrics.append("# TYPE http_slow_requests_total counter")
        metrics.append(f"http_slow_requests_total {stats['slow_requests_count']}")

        return "\n".join(metrics)
