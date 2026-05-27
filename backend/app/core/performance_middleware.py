"""
Performance Optimization Middleware.

Integrates performance monitoring, caching, and optimization into FastAPI.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.api_optimization import ResponseCompressor
from backend.app.core.performance_monitor import APIMetric, record_metric

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for monitoring API performance."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request/response performance."""
        start_time = time.time()
        request_size = len(await request.body())

        try:
            response = await call_next(request)
            response_time = time.time() - start_time

            # Record metric
            metric = APIMetric(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                response_time=response_time,
                request_size=request_size,
                response_size=response.headers.get("content-length", 0),
            )
            record_metric(metric)

            # Add performance headers
            response.headers["X-Response-Time"] = str(response_time)
            response.headers["X-Request-Size"] = str(request_size)

            return response
        except Exception as e:
            response_time = time.time() - start_time
            metric = APIMetric(
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                response_time=response_time,
                request_size=request_size,
                error=str(e),
            )
            record_metric(metric)
            raise


class ResponseCompressionMiddleware(BaseHTTPMiddleware):
    """Middleware for compressing responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Compress response if applicable."""
        response = await call_next(request)

        # Compress response
        response = await ResponseCompressor.compress_response(response, request)

        return response


class CacheHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware for setting cache headers."""

    # Cache policies for different endpoints
    CACHE_POLICIES = {
        "/api/v1/workflows": 300,  # 5 minutes
        "/api/v1/workflows/status": 60,  # 1 minute
        "/api/v1/runs": 60,  # 1 minute
        "/api/v1/memory/search": 300,  # 5 minutes
        "/api/v1/overview": 60,  # 1 minute
        "/api/v1/tools": 3600,  # 1 hour
        "/api/v1/agents": 3600,  # 1 hour
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add cache headers to response."""
        response = await call_next(request)

        # Only cache GET requests
        if request.method != "GET":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response

        # Check if endpoint has cache policy
        for path, ttl in self.CACHE_POLICIES.items():
            if request.url.path.startswith(path):
                response.headers["Cache-Control"] = f"public, max-age={ttl}"
                break
        else:
            response.headers["Cache-Control"] = "no-cache"

        return response


class RequestDeduplicationMiddleware(BaseHTTPMiddleware):
    """Middleware for deduplicating concurrent identical requests."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._pending_requests: dict[str, Any] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Deduplicate identical concurrent requests."""
        # Only deduplicate GET requests
        if request.method != "GET":
            return await call_next(request)

        # Create request key
        request_key = f"{request.method}:{request.url.path}:{request.url.query}"

        # Check if request is already pending
        if request_key in self._pending_requests:
            # Wait for pending request to complete
            return await self._pending_requests[request_key]

        # Create future for this request
        import asyncio

        future: asyncio.Future[Response] = asyncio.Future()
        self._pending_requests[request_key] = future

        try:
            response = await call_next(request)
            future.set_result(response)
            return response
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            del self._pending_requests[request_key]


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting."""

    def __init__(
        self,
        app: Any,
        requests_per_second: int = 100,
        burst_size: int = 200,
    ) -> None:
        super().__init__(app)
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self._request_counts: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Rate limit requests."""
        client_id = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Initialize request list for client
        if client_id not in self._request_counts:
            self._request_counts[client_id] = []

        # Remove old requests (older than 1 second)
        self._request_counts[client_id] = [
            t for t in self._request_counts[client_id] if current_time - t < 1.0
        ]

        # Check rate limit
        if len(self._request_counts[client_id]) >= self.requests_per_second:
            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={"Retry-After": "1"},
            )

        # Record request
        self._request_counts[client_id].append(current_time)

        return await call_next(request)


from typing import Any
