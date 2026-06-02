from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from backend.app.core.contracts import ErrorCode, ErrorResponse
from backend.app.settings import get_settings

logger = logging.getLogger(__name__)


class XAgentAPIError(Exception):
    """Standard API error with structured response format."""

    def __init__(
        self,
        *,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.trace_id = trace_id
        self.request_id = request_id


def api_error(
    status_code: int,
    code: ErrorCode,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    trace_id: str | None = None,
    request_id: str | None = None,
) -> XAgentAPIError:
    """Create a structured API error.

    Args:
        status_code: HTTP status code
        code: Error code enum
        message: Human-readable error message
        details: Additional error details
        trace_id: Trace ID for debugging
        request_id: Request ID for tracking

    Returns:
        XAgentAPIError instance
    """
    return XAgentAPIError(
        status_code=status_code,
        code=code,
        message=message,
        details=details,
        trace_id=trace_id,
        request_id=request_id,
    )


async def xagent_api_error_handler(request: Request, exc: XAgentAPIError) -> JSONResponse:
    """Handle XAgentAPIError exceptions with structured response."""
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=exc.request_id or request.headers.get("x-request-id"),
        trace_id=exc.trace_id,
        details=exc.details,
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle validation errors with sanitized output for production."""
    settings = get_settings()
    errors = exc.errors()

    # Sanitize error details in production
    if settings.app_mode == "production":
        # Hide detailed validation errors in production
        sanitized_errors = []
        for error in errors:
            sanitized_error = {
                "loc": error.get("loc", []),
                "type": error.get("type", "unknown"),
                # Don't include the actual input value in production
            }
            sanitized_errors.append(sanitized_error)
        errors = sanitized_errors
    else:
        # In development, redact sensitive input values
        for error in errors:
            if "input" in error:
                error["input"] = "<redacted>"
            # pydantic v2 在自定义 field_validator 抛 ValueError 时，errors() 条目
            # 会带 ctx={"error": ValueError(...)}，内含原始异常对象 → JSON 不可
            # 序列化，JSONResponse 会 500。把 ctx 内的异常统一转成字符串。
            ctx = error.get("ctx")
            if isinstance(ctx, dict):
                error["ctx"] = {
                    key: (str(val) if isinstance(val, BaseException) else val)
                    for key, val in ctx.items()
                }

    return _error_response(
        status_code=422,
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed." if settings.app_mode == "production" else "Request validation failed. Check error details.",
        request_id=request.headers.get("x-request-id"),
        details={"errors": errors} if settings.app_mode != "production" else {},
    )


def _error_response(
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    request_id: str | None = None,
    trace_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Generate error response with production-safe details."""
    settings = get_settings()

    # In production, don't expose internal details
    if settings.app_mode == "production":
        details = {}

    payload = ErrorResponse(
        code=code,
        message=message,
        request_id=request_id,
        trace_id=trace_id,
        details=details or {},
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


async def pydantic_validation_error_handler(
    request: Request,
    exc: PydanticValidationError,
) -> JSONResponse:
    """Handle raw pydantic ValidationError (raised by manual model_validate calls).

    Converts to a 422 response matching FastAPI's RequestValidationError semantics.
    """
    settings = get_settings()
    errors = exc.errors()

    # Sanitize error details in production
    if settings.app_mode == "production":
        sanitized_errors = []
        for error in errors:
            sanitized_error = {
                "loc": error.get("loc", []),
                "type": error.get("type", "unknown"),
            }
            sanitized_errors.append(sanitized_error)
        errors = sanitized_errors
    else:
        for error in errors:
            if "input" in error:
                error["input"] = "<redacted>"
            ctx = error.get("ctx")
            if isinstance(ctx, dict):
                error["ctx"] = {
                    key: (str(val) if isinstance(val, BaseException) else val)
                    for key, val in ctx.items()
                }

    return _error_response(
        status_code=422,
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed." if settings.app_mode == "production" else "Request validation failed. Check error details.",
        request_id=request.headers.get("x-request-id"),
        details={"errors": errors} if settings.app_mode != "production" else {},
    )
