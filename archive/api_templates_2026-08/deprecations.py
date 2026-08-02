"""API deprecation middleware and utilities.

Adds deprecation warning headers to responses for endpoints that are
scheduled for removal. Clients should migrate to the replacement endpoint
before the sunset date.

Usage:
    from backend.app.api.deprecations import DeprecatedEndpointMiddleware, deprecated

    # Middleware approach (global)
    app.add_middleware(DeprecatedEndpointMiddleware)

    # Decorator approach (per-endpoint)
    @deprecated(sunset="2026-12-01", replacement="/api/v2/agents")
    async def old_agents_list():
        ...
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import wraps
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("xagent.deprecations")

# Registry of deprecated endpoints: path_pattern -> metadata
_DEPRECATED_ENDPOINTS: dict[str, dict[str, str]] = {
    # Example:
    # "/api/v1/legacy/agents": {
    #     "sunset": "2026-12-01",
    #     "replacement": "/api/v2/agents",
    #     "reason": "Consolidated into v2 agents API",
    # },
}


def register_deprecation(
    path: str,
    sunset: str,
    replacement: str | None = None,
    reason: str | None = None,
) -> None:
    """Register an endpoint as deprecated.

    Args:
        path: The endpoint path pattern (exact match).
        sunset: ISO date string when the endpoint will be removed.
        replacement: The replacement endpoint path.
        reason: Human-readable reason for deprecation.
    """
    _DEPRECATED_ENDPOINTS[path] = {
        "sunset": sunset,
        "replacement": replacement or "",
        "reason": reason or "",
    }
    logger.info(f"Registered deprecation: {path} (sunset={sunset})")


class DeprecatedEndpointMiddleware(BaseHTTPMiddleware):
    """Middleware that adds deprecation headers to deprecated endpoints.

    Headers added (per RFC 8594 / draft-ietf-httpapi-sunset-header):
    - Deprecation: true
    - Sunset: <ISO date>
    - Link: <replacement>; rel="successor-version"
    - X-Deprecation-Reason: <reason>
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        path = request.url.path
        if path in _DEPRECATED_ENDPOINTS:
            meta = _DEPRECATED_ENDPOINTS[path]
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = meta["sunset"]
            if meta["replacement"]:
                response.headers["Link"] = f'<{meta["replacement"]}>; rel="successor-version"'
            if meta["reason"]:
                response.headers["X-Deprecation-Reason"] = meta["reason"]

            # Log deprecated endpoint usage for migration tracking
            logger.debug(
                f"Deprecated endpoint accessed: {request.method} {path} "
                f"(sunset={meta['sunset']}, client={request.client.host if request.client else 'unknown'})"
            )

        return response


def deprecated(
    sunset: str,
    replacement: str | None = None,
    reason: str | None = None,
) -> Callable:
    """Decorator to mark an endpoint as deprecated.

    Adds Deprecation/Sunset/Link headers to the response.

    Args:
        sunset: ISO date when endpoint will be removed (e.g., "2026-12-01").
        replacement: Replacement endpoint path.
        reason: Reason for deprecation.

    Returns:
        Decorator function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            # If result is a Response, add headers directly
            if isinstance(result, Response):
                result.headers["Deprecation"] = "true"
                result.headers["Sunset"] = sunset
                if replacement:
                    result.headers["Link"] = f'<{replacement}>; rel="successor-version"'
                if reason:
                    result.headers["X-Deprecation-Reason"] = reason
                return result

            # For dict/JSON responses, we can't add headers here
            # The middleware approach handles this case globally
            return result

        # Mark function metadata for OpenAPI schema
        wrapper.__deprecated__ = True  # type: ignore[attr-defined]
        wrapper.__sunset__ = sunset  # type: ignore[attr-defined]
        wrapper.__replacement__ = replacement  # type: ignore[attr-defined]

        return wrapper
    return decorator


def get_deprecated_endpoints() -> dict[str, dict[str, str]]:
    """Get all registered deprecated endpoints."""
    return dict(_DEPRECATED_ENDPOINTS)


def is_past_sunset(path: str) -> bool:
    """Check if a deprecated endpoint is past its sunset date."""
    if path not in _DEPRECATED_ENDPOINTS:
        return False
    try:
        sunset_date = date.fromisoformat(_DEPRECATED_ENDPOINTS[path]["sunset"])
        return date.today() > sunset_date
    except (ValueError, KeyError):
        return False
