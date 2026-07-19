"""
Middleware system for cross-cutting concerns.

Implements:
- Security middleware (authentication, authorization)
- Logging middleware (structured logging)
- Caching middleware (response caching)
- Error handling middleware
- Performance monitoring middleware
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class MiddlewareChain:
    """Chain multiple middleware together."""

    def __init__(self) -> None:
        self._middlewares: list[Callable] = []

    def add(self, middleware: Callable) -> MiddlewareChain:
        """Add middleware to the chain."""
        self._middlewares.append(middleware)
        return self

    async def execute(self, request: Request, call_next: Callable) -> Response:
        """Execute middleware chain."""
        if not self._middlewares:
            return await call_next(request)

        async def chain(index: int) -> Response:
            if index >= len(self._middlewares):
                return await call_next(request)

            middleware = self._middlewares[index]
            return await middleware(request, lambda: chain(index + 1))

        return await chain(0)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Add request context (correlation ID, user info, etc.).

    Adds to request.state:
    - correlation_id: Unique request ID
    - request_start_time: Request start time
    - user_id: Authenticated user ID (if available)
    - tenant_id: Tenant ID (if available)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request context."""
        # Generate correlation ID
        correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        # Record start time
        request.state.request_start_time = time.time()

        # Extract user info from principal (if available)
        if hasattr(request.state, "principal"):
            principal = request.state.principal
            request.state.user_id = principal.user_id
            request.state.tenant_id = principal.tenant_id

        # Add correlation ID to response headers
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id

        return response


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured logging middleware.

    Logs:
    - Request method, path, query string
    - Response status code
    - Request duration
    - User ID and tenant ID (if available)
    """

    # Paths to exclude from logging
    EXCLUDED_PATHS = {"/health", "/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response."""
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        start_time = time.time()

        # Extract request info
        method = request.method
        path = request.url.path
        query_string = request.url.query
        client_ip = request.client.host if request.client else "unknown"

        # Get context info
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log request
            log_data = {
                "event": "http_request",
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": duration * 1000,
                "client_ip": client_ip,
                "correlation_id": correlation_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
            }

            if response.status_code >= 400:
                logger.warning(json.dumps(log_data))
            else:
                logger.info(json.dumps(log_data))

            return response

        except Exception as e:
            duration = time.time() - start_time
            log_data = {
                "event": "http_error",
                "method": method,
                "path": path,
                "error": str(e),
                "duration_ms": duration * 1000,
                "client_ip": client_ip,
                "correlation_id": correlation_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
            }
            logger.error(json.dumps(log_data))
            raise


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Performance monitoring middleware.

    Tracks:
    - Request duration
    - Slow requests (> 1 second)
    - Request throughput
    """

    SLOW_REQUEST_THRESHOLD = 1.0  # seconds

    def __init__(self, app) -> None:
        super().__init__(app)
        self._request_count = 0
        self._total_duration = 0.0
        self._slow_requests = []

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor performance."""
        start_time = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            self._request_count += 1
            self._total_duration += duration

            if duration > self.SLOW_REQUEST_THRESHOLD:
                self._slow_requests.append(
                    {
                        "path": request.url.path,
                        "method": request.method,
                        "duration": duration,
                        "timestamp": time.time(),
                    }
                )
                # Keep only last 100 slow requests
                if len(self._slow_requests) > 100:
                    self._slow_requests.pop(0)

                logger.warning(
                    f"Slow request: {request.method} {request.url.path} took {duration:.2f}s"
                )

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Request failed after {duration:.2f}s: {e}")
            raise

    def get_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        avg_duration = self._total_duration / self._request_count if self._request_count > 0 else 0
        return {
            "total_requests": self._request_count,
            "average_duration_ms": avg_duration * 1000,
            "slow_requests": len(self._slow_requests),
            "recent_slow_requests": self._slow_requests[-10:],
        }


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Error handling middleware.

    Catches exceptions and returns appropriate error responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle errors."""
        try:
            return await call_next(request)
        except Exception as e:
            correlation_id = getattr(request.state, "correlation_id", "unknown")

            # Log error
            logger.error(
                f"Unhandled error: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "path": request.url.path,
                    "method": request.method,
                },
                exc_info=True,
            )

            # Return error response
            return Response(
                content=json.dumps(
                    {
                        "error": "Internal server error",
                        "correlation_id": correlation_id,
                    }
                ),
                status_code=500,
                media_type="application/json",
            )


class CachingMiddleware(BaseHTTPMiddleware):
    """
    Response caching middleware.

    Caches GET requests based on path and query string.
    """

    # Methods to cache
    CACHEABLE_METHODS = {"GET", "HEAD"}

    # Paths to cache
    CACHEABLE_PATHS = {"/api/v1/memory", "/api/v1/workflows", "/api/v1/agents"}

    def __init__(self, app, cache_manager=None) -> None:
        super().__init__(app)
        self._cache_manager = cache_manager
        self._cache = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Cache responses."""
        if not self._should_cache(request):
            return await call_next(request)

        # Generate cache key
        cache_key = f"{request.method}:{request.url.path}:{request.url.query}"

        # Check cache
        if cache_key in self._cache:
            cached_response = self._cache[cache_key]
            if time.time() - cached_response["timestamp"] < 300:  # 5 minute TTL
                logger.debug(f"Cache hit: {cache_key}")
                return Response(
                    content=cached_response["content"],
                    status_code=cached_response["status_code"],
                    headers=dict(cached_response["headers"]),
                    media_type=cached_response["media_type"],
                )

        # Get response
        response = await call_next(request)

        # Cache if successful
        if response.status_code == 200:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            self._cache[cache_key] = {
                "content": body,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
                "timestamp": time.time(),
            }

            # Return cached response
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response

    def _should_cache(self, request: Request) -> bool:
        """Check if request should be cached."""
        if request.method not in self.CACHEABLE_METHODS:
            return False

        for path in self.CACHEABLE_PATHS:
            if request.url.path.startswith(path):
                return True

        return False


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.

    Limits requests per IP address.
    """

    def __init__(self, app, requests_per_minute: int = 60) -> None:
        super().__init__(app)
        self._requests_per_minute = requests_per_minute
        self._request_times: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Rate limit requests."""
        client_ip = request.client.host if request.client else "unknown"

        # Check rate limit
        now = time.time()
        if client_ip not in self._request_times:
            self._request_times[client_ip] = []

        # Remove old requests (older than 1 minute)
        self._request_times[client_ip] = [
            t for t in self._request_times[client_ip] if now - t < 60
        ]

        # Check if limit exceeded
        if len(self._request_times[client_ip]) >= self._requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return Response(
                content=json.dumps({"error": "Rate limit exceeded"}),
                status_code=429,
                media_type="application/json",
            )

        # Record request
        self._request_times[client_ip].append(now)

        return await call_next(request)
