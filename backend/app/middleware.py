"""Rate limiting and security middleware for X-Agent API.

P1-06 hardening notes
---------------------
* ``SecurityHeadersMiddleware`` now emits a strict Content-Security-Policy with
  NO ``'unsafe-inline'`` / ``'unsafe-eval'`` in ``script-src``. The single
  documented exception is ``style-src 'unsafe-inline'`` (see the class
  docstring for rationale and removal path).
* ``ProductionDocsGuardMiddleware`` returns 404 for the interactive API docs
  surfaces (``/docs``, ``/redoc``, ``/openapi.json``) when the app runs in
  ``app_mode=production``. Mounting it is a one-line change in
  ``backend/app/main.py`` — see the class docstring ("Integration wave wiring").
"""

from __future__ import annotations

import os
import secrets
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


# Documented CSP exception (P1-06):
#   style-src keeps 'unsafe-inline' because the built SPA applies inline
#   `style="..."` attributes from component libraries; blocking them without a
#   nonce/hash strategy breaks rendering. script-src is fully strict.
#   Removal path: once index.html is served through a template that injects a
#   per-request nonce (see `script_nonce` below), drop this exception.
_CSP_STYLE_EXCEPTION = "style-src 'self' 'unsafe-inline'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Args:
        app: ASGI application.
        script_nonce: When True, a per-request CSP nonce is generated, exposed
            as ``request.state.csp_nonce``, and added to ``script-src`` as
            ``'nonce-<value>'``. Only enable this when HTML is rendered
            server-side and embeds the nonce in every inline <script> tag;
            for the statically-served SPA keep it False (default), which yields
            a strict ``script-src 'self'`` with no inline-script allowance.
        extra_csp_directives: Optional extra CSP directives appended verbatim
            (e.g. a documented, time-boxed exception). Keep empty in
            production unless there is a written exception in
            SECURITY_DECISIONS.md.
    """

    def __init__(self, app, script_nonce: bool = False, extra_csp_directives: str = ""):
        super().__init__(app)
        self.script_nonce = script_nonce
        self.extra_csp_directives = extra_csp_directives.strip()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        if self.script_nonce:
            nonce = secrets.token_urlsafe(16)
            request.state.csp_nonce = nonce
            script_src = f"script-src 'self' 'nonce-{nonce}'"
        else:
            # Strict: no 'unsafe-inline', no 'unsafe-eval'.
            script_src = "script-src 'self'"

        response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy — strict by default (P1-06).
        csp_parts = [
            "default-src 'self'",
            script_src,
            _CSP_STYLE_EXCEPTION,
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        if self.extra_csp_directives:
            csp_parts.append(self.extra_csp_directives)
        response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS: force HTTPS for 1 year. Harmless behind a TLS-terminating
        # reverse proxy (see DEPLOYMENT.md "TLS termination"); browsers ignore
        # it over plain HTTP for first-party localhost dev.
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class ProductionDocsGuardMiddleware(BaseHTTPMiddleware):
    """Return 404 for interactive API-docs surfaces in production mode.

    FastAPI registers ``/docs``, ``/redoc``, ``/openapi.json`` (and
    ``/docs/oauth2-redirect``) by default. Exposing them in production leaks
    the full API schema to unauthenticated callers, so in
    ``app_mode=production`` this middleware intercepts those paths with a 404
    BEFORE routing — no schema content is ever rendered.

    Args:
        app: ASGI application.
        app_mode: Deployment mode. When None (default), read once at startup
            from ``XAGENT_APP_MODE`` (falling back to "development"), matching
            how ``backend/app/settings.py`` resolves the same variable.

    Integration wave wiring (P1-06):
        In ``backend/app/main.py``, after the existing ``app.add_middleware``
        block, add::

            from backend.app.middleware import ProductionDocsGuardMiddleware
            app.add_middleware(ProductionDocsGuardMiddleware, app_mode=settings.app_mode)

        (Passing ``settings.app_mode`` explicitly is preferred; omitting
        ``app_mode`` falls back to reading ``XAGENT_APP_MODE`` directly.)

        Alternative (also acceptable, same wave): construct FastAPI with
        ``docs_url=None, redoc_url=None, openapi_url=None`` when
        ``settings.app_mode == "production"``. Only one of the two mechanisms
        is needed; this middleware is the drop-in option that requires no
        change to the FastAPI() constructor call.
    """

    DOCS_PATHS: frozenset[str] = frozenset(
        {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
    )

    def __init__(self, app, app_mode: str | None = None):
        super().__init__(app)
        self.app_mode = (
            app_mode
            if app_mode is not None
            else os.getenv("XAGENT_APP_MODE", "development")
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Block docs surfaces with 404 when running in production."""
        if self.app_mode == "production" and request.url.path in self.DOCS_PATHS:
            return Response(
                content='{"detail": "Not Found"}',
                status_code=404,
                media_type="application/json",
            )
        return await call_next(request)
