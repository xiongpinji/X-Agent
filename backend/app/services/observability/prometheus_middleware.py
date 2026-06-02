"""Prometheus metrics middleware for FastAPI."""

from __future__ import annotations

import time
from typing import Callable

from fastapi import Request
from prometheus_client import generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.services.observability.prometheus_metrics import (
    http_requests_total,
    http_request_duration_seconds,
    http_request_size_bytes,
    http_response_size_bytes,
    errors_total,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting Prometheus metrics."""

    def __init__(self, app, group_paths: bool = False):
        super().__init__(app)
        self.group_paths = group_paths

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        method = request.method
        path = request.url.path

        # Group paths if enabled
        if self.group_paths:
            path = self._group_path(path)

        # Record request size
        if request.headers.get("content-length"):
            try:
                request_size = int(request.headers["content-length"])
                http_request_size_bytes.labels(method=method, endpoint=path).observe(
                    request_size
                )
            except (ValueError, TypeError):
                pass

        # Measure request duration
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as e:
            # Record error
            errors_total.labels(error_type=type(e).__name__, endpoint=path).inc()
            raise

        duration = time.perf_counter() - start_time

        # Record metrics
        status_code = response.status_code
        http_requests_total.labels(
            method=method, endpoint=path, status=status_code
        ).inc()
        http_request_duration_seconds.labels(method=method, endpoint=path).observe(
            duration
        )

        # Record response size
        if response.headers.get("content-length"):
            try:
                response_size = int(response.headers["content-length"])
                http_response_size_bytes.labels(
                    method=method, endpoint=path
                ).observe(response_size)
            except (ValueError, TypeError):
                pass

        return response

    @staticmethod
    def _group_path(path: str) -> str:
        """Group similar paths together."""
        # Group UUID paths
        import re

        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path,
        )

        # Group numeric IDs
        path = re.sub(r"/\d+", "/{id}", path)

        return path


async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type="text/plain; charset=utf-8")
