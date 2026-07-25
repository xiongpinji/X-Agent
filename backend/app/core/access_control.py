"""
Access Control Middleware and Permission Enforcement System.

Provides:
- API key extraction and validation
- Permission checking
- Resource-level access control
- Rate limit enforcement
- Audit logging
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.core.api_key_manager import APIKeyManager, PermissionLevel
from backend.app.core.security import Principal

logger = logging.getLogger(__name__)


class AccessControlMiddleware(BaseHTTPMiddleware):
    """Middleware for API key validation and access control."""

    # Paths that don't require authentication
    EXEMPT_PATHS = {
        "/",
        "/health",
        "/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/logout",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    def __init__(self, app, api_key_manager: APIKeyManager) -> None:
        super().__init__(app)
        self.api_key_manager = api_key_manager

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate API key."""
        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Extract API key
        api_key = self._extract_api_key(request)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Authenticate
        ip_address = self._get_client_ip(request)
        config = self.api_key_manager.authenticate(api_key, ip_address)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
            )

        # Store in request state for later use
        request.state.api_key_config = config
        request.state.principal = self._create_principal(config)

        response = await call_next(request)
        return response

    @staticmethod
    def _extract_api_key(request: Request) -> str | None:
        """Extract API key from request."""
        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Check X-API-Key header
        if "X-API-Key" in request.headers:
            return request.headers["X-API-Key"]

        # Check query parameter (less secure, for testing only)
        if "api_key" in request.query_params:
            return request.query_params["api_key"]

        return None

    @staticmethod
    def _get_client_ip(request: Request) -> str | None:
        """Get client IP address."""
        # Check X-Forwarded-For header (for proxies)
        if "X-Forwarded-For" in request.headers:
            return request.headers["X-Forwarded-For"].split(",")[0].strip()

        # Check X-Real-IP header
        if "X-Real-IP" in request.headers:
            return request.headers["X-Real-IP"]

        # Fall back to client connection
        return request.client.host if request.client else None

    @staticmethod
    def _create_principal(config) -> Principal:
        """Create Principal from API key config."""
        # Convert PermissionLevel enums to strings
        scopes = [p.value for p in config.permissions]

        return Principal(
            tenant_id=config.tenant_id,
            user_id=config.user_id,
            role="api_key",
            scopes=scopes,
            api_key_id=config.id,
            authenticated=True,
        )


class PermissionChecker:
    """Helper for checking permissions."""

    def __init__(self, api_key_manager: APIKeyManager) -> None:
        self.api_key_manager = api_key_manager

    def require_permission(
        self,
        request: Request,
        permission: PermissionLevel,
        resource_id: str | None = None,
    ) -> None:
        """Check if request has required permission.

        Raises HTTPException if permission denied.
        """
        config = getattr(request.state, "api_key_config", None)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        if not self.api_key_manager.check_permission(config, permission, resource_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}",
            )

    def require_any_permission(
        self,
        request: Request,
        permissions: list[PermissionLevel],
    ) -> None:
        """Check if request has any of the required permissions."""
        config = getattr(request.state, "api_key_config", None)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        for permission in permissions:
            if self.api_key_manager.check_permission(config, permission):
                return

        permission_str = ", ".join(p.value for p in permissions)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied. Required one of: {permission_str}",
        )

    def require_all_permissions(
        self,
        request: Request,
        permissions: list[PermissionLevel],
    ) -> None:
        """Check if request has all required permissions."""
        config = getattr(request.state, "api_key_config", None)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        for permission in permissions:
            if not self.api_key_manager.check_permission(config, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value}",
                )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting."""

    def __init__(self, app, api_key_manager: APIKeyManager) -> None:
        super().__init__(app)
        self.api_key_manager = api_key_manager

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limits."""
        config = getattr(request.state, "api_key_config", None)
        if not config:
            return await call_next(request)

        # Rate limit is checked during authentication
        # This middleware is here for additional checks if needed
        response = await call_next(request)

        # Add rate limit headers
        if hasattr(request.state, "rate_limit_stats"):
            stats = request.state.rate_limit_stats
            response.headers["X-RateLimit-Remaining-Minute"] = str(
                stats.get("minute_remaining", 0)
            )
            response.headers["X-RateLimit-Remaining-Hour"] = str(
                stats.get("hour_remaining", 0)
            )
            response.headers["X-RateLimit-Remaining-Day"] = str(
                stats.get("day_remaining", 0)
            )

        return response


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for audit logging."""

    def __init__(self, app, api_key_manager: APIKeyManager) -> None:
        super().__init__(app)
        self.api_key_manager = api_key_manager

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request details."""
        config = getattr(request.state, "api_key_config", None)
        if not config:
            return await call_next(request)

        # Log request
        logger.info(
            f"API request: {request.method} {request.url.path} "
            f"from {self._get_client_ip(request)} "
            f"with key {config.key_prefix}"
        )

        response = await call_next(request)

        # Log response
        logger.info(
            f"API response: {request.method} {request.url.path} "
            f"status={response.status_code}"
        )

        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str | None:
        """Get client IP address."""
        if "X-Forwarded-For" in request.headers:
            return request.headers["X-Forwarded-For"].split(",")[0].strip()
        if "X-Real-IP" in request.headers:
            return request.headers["X-Real-IP"]
        return request.client.host if request.client else None
