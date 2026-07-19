"""
统一错误处理模块 - 集中管理所有错误响应和异常处理。

这个模块提供：
- 标准化的错误响应格式
- 自定义异常类
- 错误代码定义
- 错误日志记录
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """标准错误代码定义。"""
    # 认证和授权错误
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # 验证错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # 资源错误
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # 业务逻辑错误
    INVALID_STATE = "INVALID_STATE"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # 系统错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"

    # 工具执行错误
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_INVALID_ARGUMENTS = "TOOL_INVALID_ARGUMENTS"

    # 工作流错误
    WORKFLOW_EXECUTION_FAILED = "WORKFLOW_EXECUTION_FAILED"
    WORKFLOW_NOT_FOUND = "WORKFLOW_NOT_FOUND"
    WORKFLOW_INVALID_STATE = "WORKFLOW_INVALID_STATE"


class ErrorResponse(BaseModel):
    """标准错误响应格式。"""
    error_code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    request_id: str | None = None


class AppException(Exception):
    """应用程序基础异常类。"""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.trace_id = trace_id
        self.request_id = request_id
        super().__init__(message)

    def to_http_exception(self) -> HTTPException:
        """转换为FastAPI HTTPException。"""
        return HTTPException(
            status_code=self.status_code,
            detail=self.message,
            headers={"X-Error-Code": self.error_code.value}
        )

    def to_response(self) -> ErrorResponse:
        """转换为标准错误响应。"""
        return ErrorResponse(
            error_code=self.error_code,
            message=self.message,
            details=self.details,
            trace_id=self.trace_id,
            request_id=self.request_id,
        )


class AuthenticationError(AppException):
    """认证错误。"""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code=ErrorCode.UNAUTHORIZED,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
            trace_id=trace_id,
            request_id=request_id,
        )


class AuthorizationError(AppException):
    """授权错误。"""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code=ErrorCode.FORBIDDEN,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
            trace_id=trace_id,
            request_id=request_id,
        )


class ValidationError(AppException):
    """验证错误。"""

    def __init__(
        self,
        message: str = "Validation failed",
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            trace_id=trace_id,
            request_id=request_id,
        )


class NotFoundError(AppException):
    """资源未找到错误。"""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            message=f"{resource_type} not found: {resource_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id},
            trace_id=trace_id,
            request_id=request_id,
        )


class ConflictError(AppException):
    """冲突错误。"""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code=ErrorCode.CONFLICT,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
            trace_id=trace_id,
            request_id=request_id,
        )


class ToolExecutionError(AppException):
    """工具执行错误。"""

    def __init__(
        self,
        tool_name: str,
        message: str,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code=ErrorCode.TOOL_EXECUTION_FAILED,
            message=f"Tool '{tool_name}' execution failed: {message}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"tool_name": tool_name, **(details or {})},
            trace_id=trace_id,
            request_id=request_id,
        )


class WorkflowExecutionError(AppException):
    """工作流执行错误。"""

    def __init__(
        self,
        workflow_id: str,
        message: str,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            error_code=ErrorCode.WORKFLOW_EXECUTION_FAILED,
            message=f"Workflow '{workflow_id}' execution failed: {message}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"workflow_id": workflow_id, **(details or {})},
            trace_id=trace_id,
            request_id=request_id,
        )


class ErrorHandler:
    """错误处理器 - 集中管理错误处理逻辑。"""

    @staticmethod
    def handle_validation_error(
        field: str,
        value: Any,
        reason: str,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> ValidationError:
        """
        处理验证错误。

        Args:
            field: 字段名
            value: 字段值
            reason: 错误原因
            trace_id: Trace ID
            request_id: Request ID

        Returns:
            ValidationError: 验证错误异常
        """
        logger.warning(f"Validation error for field '{field}': {reason}")
        return ValidationError(
            message=f"Invalid value for field '{field}': {reason}",
            details={"field": field, "value": str(value)[:100], "reason": reason},
            trace_id=trace_id,
            request_id=request_id,
        )

    @staticmethod
    def handle_tool_error(
        tool_name: str,
        error: Exception,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> ToolExecutionError:
        """
        处理工具执行错误。

        Args:
            tool_name: 工具名称
            error: 原始异常
            trace_id: Trace ID
            request_id: Request ID

        Returns:
            ToolExecutionError: 工具执行错误异常
        """
        logger.error(f"Tool '{tool_name}' execution error: {error}", exc_info=True)
        return ToolExecutionError(
            tool_name=tool_name,
            message=str(error),
            details={"error_type": type(error).__name__},
            trace_id=trace_id,
            request_id=request_id,
        )

    @staticmethod
    def handle_workflow_error(
        workflow_id: str,
        error: Exception,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> WorkflowExecutionError:
        """
        处理工作流执行错误。

        Args:
            workflow_id: 工作流ID
            error: 原始异常
            trace_id: Trace ID
            request_id: Request ID

        Returns:
            WorkflowExecutionError: 工作流执行错误异常
        """
        logger.error(f"Workflow '{workflow_id}' execution error: {error}", exc_info=True)
        return WorkflowExecutionError(
            workflow_id=workflow_id,
            message=str(error),
            details={"error_type": type(error).__name__},
            trace_id=trace_id,
            request_id=request_id,
        )

    @staticmethod
    def handle_not_found(
        resource_type: str,
        resource_id: str,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> NotFoundError:
        """
        处理资源未找到错误。

        Args:
            resource_type: 资源类型
            resource_id: 资源ID
            trace_id: Trace ID
            request_id: Request ID

        Returns:
            NotFoundError: 资源未找到错误异常
        """
        logger.warning(f"{resource_type} not found: {resource_id}")
        return NotFoundError(
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=trace_id,
            request_id=request_id,
        )
