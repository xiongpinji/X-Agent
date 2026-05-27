"""Rate limiting and security middleware for X-Agent API."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware to prevent brute force and DoS attacks.

    Implements per-IP and per-endpoint rate limiting.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_times: dict[str, list[float]] = defaultdict(list)
        self.sensitive_endpoints = {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
        }
        self.sensitive_rate_limit = 10  # 10 requests per minute for sensitive endpoints

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting based on client IP and endpoint."""
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        now = time.time()

        # Determine rate limit based on endpoint sensitivity
        if endpoint in self.sensitive_endpoints:
            rate_limit = self.sensitive_rate_limit
        else:
            rate_limit = self.requests_per_minute

        # Create key for tracking
        key = f"{client_ip}:{endpoint}"

        # Clean up old requests (older than 1 minute)
        self.request_times[key] = [ts for ts in self.request_times[key] if now - ts < 60]

        # Check rate limit
        if len(self.request_times[key]) >= rate_limit:
            return Response(
                content='{"error": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        # Record this request
        self.request_times[key].append(now)

        # Process request
        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response
