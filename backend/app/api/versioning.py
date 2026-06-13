"""API versioning middleware and utilities (Phase 6).

Provides:
  - Version negotiation via Accept header or URL prefix (v1, v2)
  - Deprecation warnings via response headers (Deprecation, Sunset, Link)
  - Version routing helpers
  - API version management for smooth transitions

Design:
  - APIVersionMiddleware: adds X-API-Version, X-API-Supported-Versions headers.
  - Deprecation tracking: marks endpoints that will be removed.
  - Version routes: separate versioned blueprints (v1/ vs v2/).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class APIVersionStatus(str, Enum):
    """Version lifecycle status."""

    STABLE = "stable"  # Production-ready, actively supported
    PREVIEW = "preview"  # Experimental, subject to breaking changes
    DEPRECATED = "deprecated"  # Will be removed; use alternative
    SUNSET = "sunset"  # Imminent removal; no longer accept new clients


# ============================================================================
# Version Registry
# ============================================================================

API_VERSIONS = {
    "v1": APIVersionStatus.STABLE,
    "v2": APIVersionStatus.PREVIEW,
}

CURRENT_VERSION = "v1"

# Endpoint deprecation map: path_pattern -> (status, sunset_date, alternative)
DEPRECATED_ENDPOINTS: dict[str, tuple[APIVersionStatus, datetime, Optional[str]]] = {
    # Example: "/api/v1/agents/list" -> (DEPRECATED, datetime(2026, 9, 1), "/api/v2/agents")
    # "/api/v1/agents/list": (APIVersionStatus.DEPRECATED, datetime(2026, 9, 1), "/api/v2/agents"),
}

# Version-specific feature flags: version -> set of features
VERSION_FEATURES = {
    "v1": {
        "agents_run",
        "tools_execute",
        "memory_store",
        "skills_marketplace",
    },
    "v2": {
        "agents_run",
        "agents_parallel",
        "tools_execute",
        "tools_batch",
        "memory_store",
        "memory_fusion",
        "skills_marketplace",
        "channels_multi",
        "workflows_advanced",
    },
}

# Breaking changes documented between versions
BREAKING_CHANGES = {
    "v1->v2": [
        {
            "endpoint": "/api/v1/agents/run",
            "change": "agent_type parameter renamed to role_type",
            "migration": "Rename request field: {'agent_type': 'x'} -> {'role_type': 'x'}",
        },
        {
            "endpoint": "/api/v1/memory/store",
            "change": "response_format field format changed from string to enum",
            "migration": "Use MemoryFormat.JSON | MemoryFormat.VECTOR instead of 'json' | 'vector'",
        },
        {
            "endpoint": "/api/v1/tools/execute",
            "change": "tool_id field is now required (was optional with name fallback)",
            "migration": "Always provide tool_id; use /api/v2/tools/search if you need to lookup by name",
        },
    ],
}


# ============================================================================
# Middleware
# ============================================================================


class APIVersionMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for API versioning.

    Adds response headers:
      - X-API-Version: current stable version (v1)
      - X-API-Supported-Versions: comma-separated list (v1, v2)
      - Deprecation: "true" if endpoint is deprecated
      - Sunset: RFC 7231 date when deprecated endpoint is removed
      - Link: rel="successor-version" pointing to v2 alternative
      - X-API-Migration-Guide: URL to migration documentation

    Optionally enforces minimum API version (config-driven).
    """

    def __init__(self, app: ASGIApp, min_version: str = "v1", max_version: str = "v2"):
        super().__init__(app)
        self.min_version = min_version
        self.max_version = max_version

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Negotiate version from URL or header
        version = self._negotiate_version(request)
        request.state.api_version = version

        # Call handler
        response = await call_next(request)

        # Add version headers
        response.headers["X-API-Version"] = CURRENT_VERSION
        response.headers["X-API-Supported-Versions"] = ", ".join(API_VERSIONS.keys())

        # Add deprecation headers if applicable
        path = request.url.path
        if self._is_deprecated(path):
            status, sunset_date, alternative = DEPRECATED_ENDPOINTS[path]
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = self._format_sunset_date(sunset_date)
            if alternative:
                response.headers["Link"] = f"<{alternative}>; rel=\"successor-version\""
            response.headers["X-API-Migration-Guide"] = (
                "https://docs.xagent.ai/api/migration-guides"
            )

        # Warn if version is not stable
        if version in API_VERSIONS:
            if API_VERSIONS[version] != APIVersionStatus.STABLE:
                response.headers["X-API-Warning"] = (
                    f"API version {version} is {API_VERSIONS[version].value}; "
                    f"use {CURRENT_VERSION} for stable features"
                )

        return response

    def _negotiate_version(self, request: Request) -> str:
        """Determine API version from request.

        Priority:
          1. URL path prefix (/api/v2/... -> v2)
          2. Accept header (application/vnd.xagent.v2+json -> v2)
          3. X-API-Version header
          4. Default (CURRENT_VERSION)
        """
        # Check URL path
        path = request.url.path
        for version in API_VERSIONS.keys():
            if f"/api/{version}/" in path:
                return version

        # Check Accept header
        accept = request.headers.get("Accept", "")
        for version in API_VERSIONS.keys():
            if f"vnd.xagent.{version}" in accept:
                return version

        # Check X-API-Version header
        version = request.headers.get("X-API-Version", "").strip()
        if version in API_VERSIONS:
            return version

        # Default
        return CURRENT_VERSION

    def _is_deprecated(self, path: str) -> bool:
        """Check if endpoint is in deprecation list."""
        for pattern in DEPRECATED_ENDPOINTS.keys():
            if path == pattern or path.startswith(pattern.rstrip("*")):
                return True
        return False

    def _format_sunset_date(self, dt: datetime) -> str:
        """Format datetime as RFC 7231 (HTTP-date)."""
        # Format: Sun, 06 Nov 1994 08:49:37 GMT
        return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


# ============================================================================
# Version utilities
# ============================================================================


def get_supported_features(version: str) -> set[str]:
    """Get feature set for a given API version."""
    return VERSION_FEATURES.get(version, set())


def is_feature_available(version: str, feature: str) -> bool:
    """Check if a feature is available in a version."""
    return feature in get_supported_features(version)


def get_breaking_changes(from_version: str, to_version: str) -> list[dict[str, str]]:
    """Get list of breaking changes between versions."""
    key = f"{from_version}->{to_version}"
    return BREAKING_CHANGES.get(key, [])


def mark_endpoint_deprecated(
    path: str,
    sunset_date: datetime,
    alternative: Optional[str] = None,
    status: APIVersionStatus = APIVersionStatus.DEPRECATED,
) -> None:
    """Register an endpoint as deprecated.

    Args:
        path: URL path pattern (e.g., "/api/v1/agents/list").
        sunset_date: When endpoint will stop accepting requests.
        alternative: Suggested replacement endpoint (e.g., "/api/v2/agents").
        status: Deprecation status (deprecated, sunset).
    """
    DEPRECATED_ENDPOINTS[path] = (status, sunset_date, alternative)
    logger.warning(
        f"Endpoint deprecated: {path} -> sunset {sunset_date.date()} "
        f"-> use {alternative or 'v2'}"
    )


def get_version_info() -> dict[str, Any]:
    """Get current API versioning state (for /api/health or /api/versions)."""
    return {
        "current_stable": CURRENT_VERSION,
        "supported_versions": {
            version: {
                "status": status.value,
                "features": sorted(get_supported_features(version)),
            }
            for version, status in API_VERSIONS.items()
        },
        "deprecated_endpoints": [
            {
                "path": path,
                "status": status.value,
                "sunset": sunset_date.isoformat(),
                "alternative": alternative,
            }
            for path, (status, sunset_date, alternative) in DEPRECATED_ENDPOINTS.items()
        ],
        "breaking_changes": {
            key: changes for key, changes in BREAKING_CHANGES.items()
        },
    }


# ============================================================================
# Decorators for version-gated endpoints
# ============================================================================


def version_required(min_version: str) -> Callable:
    """Decorator to gate endpoint to minimum API version.

    Example:
        @app.get("/api/v2/agents/parallel-run")
        @version_required("v2")
        async def parallel_run(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            current = getattr(request.state, "api_version", CURRENT_VERSION)
            if _compare_versions(current, min_version) < 0:
                return {
                    "error": f"Feature requires API {min_version} or later (using {current})",
                    "upgrade_link": "https://docs.xagent.ai/api/upgrade",
                }
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def feature_flag(feature: str) -> Callable:
    """Decorator to gate endpoint by feature flag.

    Example:
        @app.post("/api/v2/workflows/advanced")
        @feature_flag("workflows_advanced")
        async def create_advanced_workflow(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            current = getattr(request.state, "api_version", CURRENT_VERSION)
            if not is_feature_available(current, feature):
                return {
                    "error": f"Feature '{feature}' not available in API {current}",
                    "available_in": [v for v in API_VERSIONS if is_feature_available(v, feature)],
                }
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def _compare_versions(v1: str, v2: str) -> int:
    """Compare semantic versions (v1, v2, v3, ...).

    Returns:
        -1 if v1 < v2
        0 if v1 == v2
        1 if v1 > v2
    """
    try:
        n1 = int(v1.lstrip("v"))
        n2 = int(v2.lstrip("v"))
        return -1 if n1 < n2 else (1 if n1 > n2 else 0)
    except (ValueError, AttributeError):
        return 0


# ============================================================================
# Setup helper
# ============================================================================


def setup_api_versioning(app: Any) -> None:
    """Install versioning middleware on FastAPI app.

    Usage:
        from fastapi import FastAPI
        from backend.app.api.versioning import setup_api_versioning

        app = FastAPI()
        setup_api_versioning(app)
    """
    app.add_middleware(APIVersionMiddleware)
    logger.info(f"API versioning initialized: stable={CURRENT_VERSION}, versions={list(API_VERSIONS.keys())}")
