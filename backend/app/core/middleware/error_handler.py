"""
Error handling middleware.

Provides:
- Unified exception catching
- Error classification (business/system/network)
- User-friendly error responses
- Error reporting integration (Sentry-ready)
"""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .base import BaseMiddleware

logger = logging.getLogger(__name__)


class ErrorCategory(StrEnum):
    """Error classification."""

    BUSINESS = "business"  # Expected business logic errors
    VALIDATION = "validation"  # Input validation errors
    AUTHENTICATION = "authentication"  # Auth/authz errors
    SYSTEM = "system"  # Unexpected system errors
    NETWORK = "network"  # Network/external service errors
    UNKNOWN = "unknown"  # Unknown error type


class ErrorHandlingMiddleware(BaseMiddleware):
    """
    Error handling middleware with classification and reporting.

    Configuration:
        include_traceback: Include stack trace in response (default: False)
        include_details: Include error details in response (default: False)
        report_errors: Report errors to external service (default: False)
        error_reporter: Callable for reporting errors
    """

    def __init__(self, app: Any, **config: Any) -> None:
        """Initialize error handling middleware."""
        super().__init__(app, **config)
        self.include_traceback = config.get("include_traceback", False)
        self.include_details = config.get("include_details", False)
        self.report_errors = config.get("report_errors", False)
        self.error_reporter = config.get("error_reporter")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle errors."""
        if not self.is_enabled():
            return await call_next(request)

        try:
            return await call_next(request)
        except Exception as e:
            return await self._handle_error(request, e)

    async def _handle_error(self, request: Request, error: Exception) -> Response:
        """Handle and format error response."""
        correlation_id = getattr(request.state, "correlation_id", None)
        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)

        # Classify error
        category = self._classify_error(error)
        status_code = self._get_status_code(error, category)

        # Build error response
        error_response = {
            "error": {
                "type": type(error).__name__,
                "category": category.value,
                "message": self._get_user_message(error, category),
            },
            "correlation_id": correlation_id,
        }

        # Add optional fields
        if self.include_details:
            error_response["error"]["details"] = str(error)

        if self.include_traceback:
            error_response["error"]["traceback"] = traceback.format_exc()

        # Log error
        log_data = {
            "event": "error_handled",
            "timestamp": time.time(),
            "error_type": type(error).__name__,
            "error_category": category.value,
            "status_code": status_code,
            "path": request.url.path,
            "method": request.method,
            "correlation_id": correlation_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
        }

        if category == ErrorCategory.SYSTEM:
            self.logger.error(json.dumps(log_data, ensure_ascii=False), exc_info=True)
        else:
            self.logger.warning(json.dumps(log_data, ensure_ascii=False))

        # Report error if configured
        if self.report_errors and self.error_reporter:
            try:
                await self._report_error(error, category, correlation_id, user_id, tenant_id)
            except Exception as e:
                self.logger.error(f"Failed to report error: {e}")

        return JSONResponse(
            status_code=status_code,
            content=error_response,
        )

    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error type."""
        error_name = type(error).__name__

        # Check for known error types
        if "Validation" in error_name or "ValueError" in error_name:
            return ErrorCategory.VALIDATION

        if "Auth" in error_name or "Permission" in error_name:
            return ErrorCategory.AUTHENTICATION

        if "Connection" in error_name or "Timeout" in error_name or "Network" in error_name:
            return ErrorCategory.NETWORK

        if "Business" in error_name or "Domain" in error_name:
            return ErrorCategory.BUSINESS

        # Default to system error
        return ErrorCategory.SYSTEM

    def _get_status_code(self, error: Exception, category: ErrorCategory) -> int:
        """Get HTTP status code for error."""
        # Check if error has status_code attribute
        if hasattr(error, "status_code"):
            return error.status_code

        # Map category to status code
        status_map = {
            ErrorCategory.VALIDATION: 422,
            ErrorCategory.AUTHENTICATION: 401,
            ErrorCategory.BUSINESS: 400,
            ErrorCategory.NETWORK: 503,
            ErrorCategory.SYSTEM: 500,
            ErrorCategory.UNKNOWN: 500,
        }

        return status_map.get(category, 500)

    def _get_user_message(self, error: Exception, category: ErrorCategory) -> str:
        """Get user-friendly error message."""
        # Check if error has user_message attribute
        if hasattr(error, "user_message"):
            return error.user_message

        # Map category to message
        message_map = {
            ErrorCategory.VALIDATION: "Invalid request data",
            ErrorCategory.AUTHENTICATION: "Authentication failed",
            ErrorCategory.BUSINESS: "Operation failed",
            ErrorCategory.NETWORK: "Service temporarily unavailable",
            ErrorCategory.SYSTEM: "Internal server error",
            ErrorCategory.UNKNOWN: "An error occurred",
        }

        return message_map.get(category, "An error occurred")

    async def _report_error(
        self,
        error: Exception,
        category: ErrorCategory,
        correlation_id: str | None,
        user_id: str | None,
        tenant_id: str | None,
    ) -> None:
        """Report error to external service."""
        if not self.error_reporter:
            return

        report_data = {
            "error_type": type(error).__name__,
            "error_category": category.value,
            "error_message": str(error),
            "correlation_id": correlation_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "traceback": traceback.format_exc(),
        }

        if callable(self.error_reporter):
            await self.error_reporter(report_data)


import time
