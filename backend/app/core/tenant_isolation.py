"""租户隔离中间件 - 统一的跨租户过滤和校验。

SECURITY: 实现OWASP多租户隔离最佳实践
- 统一的tenant_id校验
- 防止跨租户数据访问
- 完整的审计日志
- 租户隔离违规检测
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.security import Principal

logger = logging.getLogger(__name__)


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """租户隔离中间件 - 确保所有请求都在正确的租户上下文中"""

    # 不需要租户隔离的路径前缀
    EXEMPT_PATHS = {
        "/api/v1/auth",
        "/api/v1/health",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        """处理请求并应用租户隔离"""
        # 检查是否是豁免路径
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)

        # SECURITY: 租户上下文只能派生自已认证的 principal。
        # 绝不信任客户端提供的 x-tenant-id 头 —— 伪造该头即可跨租户访问。
        principal: Principal | None = None
        try:
            from backend.app.dependencies import get_current_principal

            principal = get_current_principal(request)
        except Exception:
            # 凭证缺失/无效时不在中间件层阻断：交由路由层的
            # get_current_principal 依赖抛出标准 401。此时不写入任何
            # 租户上下文，避免隐式回落到 "default" 租户造成越权。
            principal = None

        if principal is None:
            return await call_next(request)

        tenant_id = principal.tenant_id

        # 记录并忽略与 principal 不符的 x-tenant-id 头（疑似伪造/越权尝试）
        header_tenant_id = request.headers.get("x-tenant-id")
        if header_tenant_id and header_tenant_id != tenant_id:
            logger.warning(
                "Ignoring client-supplied x-tenant-id header: user=%s, "
                "principal_tenant=%s, header_tenant=%s, path=%s",
                principal.user_id,
                tenant_id,
                header_tenant_id,
                request.url.path,
            )

        # 将 principal/tenant 写入请求上下文：
        # - request.scope["principal"] 供 main.py 的内联租户校验中间件使用
        # - request.state 供下游中间件(RequestContextMiddleware/request_tracer)与路由使用
        request.scope["principal"] = principal
        request.scope["tenant_id"] = tenant_id
        request.state.principal = principal
        request.state.tenant_id = tenant_id

        response = await call_next(request)

        # 响应头回写派生自 principal 的租户ID（而非客户端提供的值）
        response.headers["x-tenant-id"] = tenant_id

        return response


class TenantIsolationValidator:
    """租户隔离校验器 - 验证数据访问权限"""

    @staticmethod
    def validate_tenant_access(
        principal: Principal,
        resource_tenant_id: str,
        resource_type: str = "resource",
    ) -> bool:
        """验证principal是否可以访问指定租户的资源

        Args:
            principal: 当前principal
            resource_tenant_id: 资源所属的租户ID
            resource_type: 资源类型（用于日志）

        Returns:
            True if access is allowed, False otherwise
        """
        # 管理员可以访问所有租户
        if principal.role == "admin":
            return True

        # 检查principal的租户ID是否与资源租户ID匹配
        if principal.tenant_id != resource_tenant_id:
            logger.warning(
                f"Tenant isolation violation: user={principal.user_id}, "
                f"principal_tenant={principal.tenant_id}, "
                f"resource_tenant={resource_tenant_id}, "
                f"resource_type={resource_type}"
            )
            return False

        return True

    @staticmethod
    def filter_by_tenant(
        records: list[dict[str, Any]],
        principal: Principal,
        tenant_field: str = "tenant_id",
    ) -> list[dict[str, Any]]:
        """按租户过滤记录列表

        Args:
            records: 记录列表
            principal: 当前principal
            tenant_field: 租户字段名

        Returns:
            过滤后的记录列表
        """
        # 管理员可以看到所有租户的记录
        if principal.role == "admin":
            return records

        # 其他用户只能看到自己租户的记录
        return [
            record
            for record in records
            if record.get(tenant_field) == principal.tenant_id
        ]

    @staticmethod
    def build_tenant_filter(
        principal: Principal,
        tenant_field: str = "tenant_id",
    ) -> dict[str, Any]:
        """构建数据库查询的租户过滤条件

        Args:
            principal: 当前principal
            tenant_field: 租户字段名

        Returns:
            过滤条件字典
        """
        # 管理员不需要租户过滤
        if principal.role == "admin":
            return {}

        # 其他用户只能查询自己租户的数据
        return {tenant_field: principal.tenant_id}


def require_tenant_isolation(
    tenant_field: str = "tenant_id",
) -> Callable:
    """装饰器 - 要求租户隔离校验

    使用示例:
        @router.get("/items/{item_id}")
        @require_tenant_isolation()
        async def get_item(item_id: str, principal: Principal):
            ...
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 获取principal和resource_tenant_id
            principal = kwargs.get("principal")
            resource_tenant_id = kwargs.get("tenant_id") or kwargs.get("resource_tenant_id")

            if principal and resource_tenant_id:
                if not TenantIsolationValidator.validate_tenant_access(
                    principal,
                    resource_tenant_id,
                    resource_type=func.__name__,
                ):
                    from backend.app.api.errors import api_error
                    from backend.app.core.contracts import ErrorCode

                    raise api_error(
                        403,
                        ErrorCode.AUTHORIZATION_FAILED,
                        "Access denied: tenant isolation violation",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
