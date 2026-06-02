"""
装饰器和中间件模块 - 提取重复的认证、授权和错误处理逻辑。

这个模块集中管理所有API层的横切关注点，包括：
- 权限检查
- 错误处理
- 审计日志
- 性能监控
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, TypeVar, cast

from fastapi import HTTPException, status

from backend.app.core.security import Principal

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def require_scope(required_scope: str) -> Callable[[F], F]:
    """
    装饰器：检查用户是否具有所需的权限范围。

    使用方式：
        @require_scope("agent:run")
        async def run_agent(principal: Principal, ...):
            ...

    Args:
        required_scope: 所需的权限范围，如 "agent:run", "agent:read"

    Raises:
        HTTPException: 如果用户没有所需的权限
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # 从kwargs中提取principal
            principal = kwargs.get("principal")
            if not principal:
                # 尝试从位置参数中查找
                for arg in args:
                    if isinstance(arg, Principal):
                        principal = arg
                        break

            if not principal:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not _has_scope(principal, required_scope):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required scope: {required_scope}"
                )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            principal = kwargs.get("principal")
            if not principal:
                for arg in args:
                    if isinstance(arg, Principal):
                        principal = arg
                        break

            if not principal:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not _has_scope(principal, required_scope):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required scope: {required_scope}"
                )

            return func(*args, **kwargs)

        # 返回适当的包装器
        if hasattr(func, "__await__"):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def handle_errors(
    default_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    log_errors: bool = True,
) -> Callable[[F], F]:
    """
    装饰器：统一处理函数中的异常。

    使用方式：
        @handle_errors(default_status=status.HTTP_400_BAD_REQUEST)
        async def create_resource(data: dict):
            ...

    Args:
        default_status: 默认的HTTP状态码
        log_errors: 是否记录错误日志

    Raises:
        HTTPException: 转换后的HTTP异常
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except ValueError as e:
                if log_errors:
                    logger.warning(f"Validation error in {func.__name__}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                raise HTTPException(
                    status_code=default_status,
                    detail="An error occurred processing your request"
                )

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except ValueError as e:
                if log_errors:
                    logger.warning(f"Validation error in {func.__name__}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                raise HTTPException(
                    status_code=default_status,
                    detail="An error occurred processing your request"
                )

        if hasattr(func, "__await__"):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def validate_input(**validators: Callable[[Any], bool]) -> Callable[[F], F]:
    """
    装饰器：验证函数输入参数。

    使用方式：
        @validate_input(
            task=lambda x: isinstance(x, str) and len(x) > 0,
            max_iterations=lambda x: isinstance(x, int) and x > 0
        )
        async def run_agent(task: str, max_iterations: int):
            ...

    Args:
        **validators: 参数名到验证函数的映射

    Raises:
        ValueError: 如果验证失败
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            for param_name, validator in validators.items():
                if param_name in kwargs:
                    value = kwargs[param_name]
                    if not validator(value):
                        raise ValueError(f"Invalid value for parameter '{param_name}': {value}")
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            for param_name, validator in validators.items():
                if param_name in kwargs:
                    value = kwargs[param_name]
                    if not validator(value):
                        raise ValueError(f"Invalid value for parameter '{param_name}': {value}")
            return func(*args, **kwargs)

        if hasattr(func, "__await__"):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def _has_scope(principal: Principal, required_scope: str) -> bool:
    """
    检查principal是否具有所需的权限范围。

    Args:
        principal: 安全主体
        required_scope: 所需的权限范围

    Returns:
        True如果principal具有所需的权限，否则False
    """
    if not hasattr(principal, "scopes"):
        return False

    scopes = getattr(principal, "scopes", [])
    if not isinstance(scopes, (list, set)):
        return False

    # 检查精确匹配或通配符匹配
    for scope in scopes:
        if scope == required_scope or scope == "*":
            return True
        # 支持通配符，如 "agent:*" 匹配 "agent:run"
        if scope.endswith(":*"):
            prefix = scope[:-2]
            if required_scope.startswith(prefix + ":"):
                return True

    return False
