from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.core.contracts import ErrorCode, ErrorResponse


class XAgentAPIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.trace_id = trace_id


def api_error(
    status_code: int,
    code: ErrorCode,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> XAgentAPIError:
    return XAgentAPIError(
        status_code=status_code,
        code=code,
        message=message,
        details=details,
        trace_id=trace_id,
    )


async def xagent_api_error_handler(request: Request, exc: XAgentAPIError) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=request.headers.get("x-request-id"),
        trace_id=exc.trace_id,
        details=exc.details,
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()
    for error in errors:
        if "input" in error:
            error["input"] = "<redacted>"
    return _error_response(
        status_code=422,
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed.",
        request_id=request.headers.get("x-request-id"),
        details={"errors": errors},
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
    payload = ErrorResponse(
        code=code,
        message=message,
        request_id=request_id,
        trace_id=trace_id,
        details=details or {},
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))
