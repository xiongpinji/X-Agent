"""Analytics middleware for automatic metric collection."""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.core.analytics.collector import AnalyticsCollector


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting analytics metrics."""

    def __init__(self, app, collector: AnalyticsCollector):
        """Initialize middleware.

        Args:
            app: FastAPI application
            collector: Analytics collector
        """
        super().__init__(app)
        self.collector = collector

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Skip metrics collection for health checks and metrics endpoints
        if request.url.path in ["/health", "/metrics", "/api/v1/metrics"]:
            return await call_next(request)

        start_time = time.time()
        request_size = len(await request.body())

        try:
            response = await call_next(request)
            response_time_ms = (time.time() - start_time) * 1000

            # Record metric
            tenant_id = getattr(request.state, "tenant_id", None) or "default"
            user_id = getattr(request.state, "user_id", None) or "anonymous"

            await self.collector.record_api_call(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                request_size_bytes=request_size,
                response_size_bytes=response.headers.get("content-length", 0),
                error_message=None if response.status_code < 400 else "HTTP Error",
                tags={
                    "path": request.url.path,
                    "query": str(request.url.query),
                },
            )

            return response
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            tenant_id = getattr(request.state, "tenant_id", None) or "default"
            user_id = getattr(request.state, "user_id", None) or "anonymous"

            # Record error
            await self.collector.record_error(
                tenant_id=tenant_id,
                user_id=user_id,
                error_type=type(e).__name__,
                error_message=str(e),
                endpoint=request.url.path,
                tags={"method": request.method},
            )

            raise
