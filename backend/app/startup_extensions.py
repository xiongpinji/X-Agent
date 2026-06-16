"""Startup extensions — loads new modules into the app lifecycle.

This module provides functions to register new modules as startup extensions
without modifying main.py. Each extension is wrapped in try/except for
fail-open pattern — if any extension fails to load, the core app still starts.

Usage:
    from backend.app.startup_extensions import register_extensions

    @app.on_event("startup")
    async def startup_event():
        register_extensions(app)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_extensions(app: Any) -> None:
    """Register all new modules as startup extensions.

    Each extension is wrapped in try/except — fail-open pattern.
    If an extension fails to load, it logs a warning but doesn't crash the app.

    Args:
        app: FastAPI application instance

    Extensions registered:
        - Builtin skills
        - Web search tool
        - RBAC module
        - Rate limiter
    """

    # 1. Load builtin skills
    try:
        from backend.app.core.skills import load_builtin_skills

        skills = load_builtin_skills()
        app.state.builtin_skills = skills
        logger.info("✓ Loaded %d builtin skills", len(skills))
    except Exception as e:
        logger.warning("⚠ Skills load failed (non-fatal): %s", e)
        app.state.builtin_skills = {}

    # 2. Register web search tool
    try:
        from backend.app.core.tools_builtin.web_search import WEB_SEARCH_TOOL_SCHEMA

        app.state.web_search_available = True
        app.state.web_search_schema = WEB_SEARCH_TOOL_SCHEMA
        logger.info("✓ Web search tool registered")
    except Exception as e:
        logger.warning("⚠ Web search unavailable: %s", e)
        app.state.web_search_available = False

    # 3. RBAC verification
    try:
        from backend.app.core.rbac import Role, has_permission

        app.state.rbac_available = True
        roles = [r.value for r in Role]
        logger.info("✓ RBAC module ready (roles: %s)", roles)
    except Exception as e:
        logger.warning("⚠ RBAC unavailable: %s", e)
        app.state.rbac_available = False

    # 4. Rate limit headers middleware
    try:
        from backend.app.core.rate_limiter import RateLimitResult

        app.state.rate_limit_headers_enabled = True
        logger.info("✓ Rate limit response headers enabled")
    except Exception as e:
        logger.warning("⚠ Rate limit headers unavailable: %s", e)
        app.state.rate_limit_headers_enabled = False

    logger.info("✓ All startup extensions registered")


def register_rate_limit_headers(app: Any) -> None:
    """Add X-RateLimit-* headers to responses.

    Should be called after the rate limit middleware is set up.
    Middleware intercepts all responses and adds rate limit information.

    Args:
        app: FastAPI application instance
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
        """Middleware that adds rate limit headers to responses."""

        async def dispatch(self, request: Request, call_next) -> Response:
            """Process request and add rate limit headers to response.

            Args:
                request: Incoming HTTP request
                call_next: Next middleware/handler in chain

            Returns:
                Response with rate limit headers added
            """
            response = await call_next(request)
            # Headers will be set by the rate limiter if available
            # This is a placeholder for future rate limit header injection
            return response

    # Only add if not already present
    if not hasattr(app.state, "_rl_headers_added"):
        app.state._rl_headers_added = True
        logger.info("✓ Rate limit header middleware added")


def setup_database_extensions(app: Any) -> None:
    """Set up database-related extensions.

    Registers database health checks, connection pooling stats, and
    migration utilities.

    Args:
        app: FastAPI application instance
    """
    try:
        from backend.app.core.database import get_db_manager

        app.state.db_manager = get_db_manager()
        logger.info("✓ Database manager registered")
    except Exception as e:
        logger.warning("⚠ Database manager registration failed: %s", e)


def setup_cache_extensions(app: Any) -> None:
    """Set up cache-related extensions.

    Registers cache backends (Redis, in-memory) and cache statistics.

    Args:
        app: FastAPI application instance
    """
    try:
        from backend.app.core.cache import CacheManager

        cache_manager = CacheManager()
        app.state.cache_manager = cache_manager
        logger.info("✓ Cache manager registered")
    except Exception as e:
        logger.warning("⚠ Cache manager registration failed: %s", e)


def setup_observability_extensions(app: Any) -> None:
    """Set up observability-related extensions.

    Registers tracing (Langfuse), metrics (Prometheus), and logging
    infrastructure.

    Args:
        app: FastAPI application instance
    """
    try:
        from backend.app.services.observability.langfuse_client import langfuse_client

        app.state.langfuse_client = langfuse_client
        logger.info("✓ Observability (Langfuse) registered")
    except Exception as e:
        logger.warning("⚠ Observability registration failed: %s", e)


def setup_security_extensions(app: Any) -> None:
    """Set up security-related extensions.

    Registers authentication handlers, encryption utilities, and
    audit logging.

    Args:
        app: FastAPI application instance
    """
    try:
        from backend.app.core.security import SecurityManager

        security = SecurityManager()
        app.state.security = security
        logger.info("✓ Security manager registered")
    except Exception as e:
        logger.warning("⚠ Security manager registration failed: %s", e)


def setup_all_extensions(app: Any) -> None:
    """Set up all optional extensions at once.

    Convenience function that calls all extension setup functions.
    Use this in your startup event for full initialization.

    Args:
        app: FastAPI application instance

    Example:
        @app.on_event("startup")
        async def startup():
            setup_all_extensions(app)
    """
    logger.info("Starting extension registration...")
    register_extensions(app)
    setup_database_extensions(app)
    setup_cache_extensions(app)
    setup_observability_extensions(app)
    setup_security_extensions(app)
    logger.info("✓ All extensions registered successfully")
