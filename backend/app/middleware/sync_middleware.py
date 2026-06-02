"""
X-Agent Sync Middleware

Handles sync-related middleware for request/response processing.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.local.database import LocalDatabase, DatabaseConfig
from backend.local.config import ConfigManager

logger = logging.getLogger(__name__)


class SyncMiddleware(BaseHTTPMiddleware):
    """Middleware for sync operations."""

    def __init__(self, app, db: LocalDatabase = None):
        """Initialize sync middleware.

        Args:
            app: FastAPI application
            db: Local database instance
        """
        super().__init__(app)
        self.db = db
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Initialize local database if not provided."""
        if self.db is None:
            try:
                config = ConfigManager.get_config()
                db_config = DatabaseConfig(
                    db_path=config.db_path,
                    timeout=config.db_timeout,
                    enable_wal=config.db_enable_wal,
                    enable_foreign_keys=config.db_enable_foreign_keys,
                )
                self.db = LocalDatabase(db_config)
                self.db.initialize()
                logger.info("Local database initialized in middleware")
            except Exception as e:
                logger.error(f"Failed to initialize local database: {e}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Skip sync endpoints
        if request.url.path.startswith("/api/v1/sync"):
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Add sync client to request state
        if self.db:
            request.state.local_db = self.db

        try:
            # Process request
            response = await call_next(request)

            # Record sync metrics
            duration_ms = int((time.time() - start_time) * 1000)
            if duration_ms > 1000:  # Log slow requests
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} "
                    f"took {duration_ms}ms"
                )

            return response

        except Exception as e:
            logger.error(f"Middleware error: {e}")
            raise


class OfflineModeMiddleware(BaseHTTPMiddleware):
    """Middleware to detect and handle offline mode."""

    def __init__(self, app, db: LocalDatabase = None):
        """Initialize offline mode middleware.

        Args:
            app: FastAPI application
            db: Local database instance
        """
        super().__init__(app)
        self.db = db
        self._offline_mode = False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request in offline mode.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Check if offline mode should be enabled
        # (e.g., based on network connectivity)
        try:
            # Add offline mode flag to request state
            request.state.offline_mode = self._offline_mode

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Offline mode middleware error: {e}")
            raise

    def set_offline_mode(self, offline: bool) -> None:
        """Set offline mode.

        Args:
            offline: Whether in offline mode
        """
        self._offline_mode = offline
        logger.info(f"Offline mode set to {offline}")


class SyncMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect sync metrics."""

    def __init__(self, app, db: LocalDatabase = None):
        """Initialize sync metrics middleware.

        Args:
            app: FastAPI application
            db: Local database instance
        """
        super().__init__(app)
        self.db = db
        self._metrics = {
            "total_requests": 0,
            "total_sync_operations": 0,
            "total_conflicts": 0,
            "total_errors": 0,
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collect metrics for request.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        self._metrics["total_requests"] += 1

        try:
            response = await call_next(request)

            # Track sync operations
            if request.url.path.startswith("/api/v1/sync"):
                self._metrics["total_sync_operations"] += 1

            return response

        except Exception as e:
            self._metrics["total_errors"] += 1
            logger.error(f"Metrics middleware error: {e}")
            raise

    def get_metrics(self) -> dict:
        """Get collected metrics.

        Returns:
            Metrics dictionary
        """
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        """Reset metrics."""
        self._metrics = {
            "total_requests": 0,
            "total_sync_operations": 0,
            "total_conflicts": 0,
            "total_errors": 0,
        }


class SyncErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to handle sync-related errors."""

    def __init__(self, app):
        """Initialize sync error handler middleware.

        Args:
            app: FastAPI application
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle errors in sync operations.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        try:
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)

            # Return error response
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=500,
                content={
                    "error": "Sync operation failed",
                    "detail": str(e),
                },
            )
