"""安全头中间件 — OWASP 推荐安全头 + 渗透测试准备 (P2-07)。

确保所有 HTTP 响应包含推荐的安全头：
- Content-Security-Policy (CSP)
- X-Content-Type-Options
- X-Frame-Options
- Strict-Transport-Security (HSTS)
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy

SECURITY: Implements OWASP recommended security headers.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# 生产环境安全头配置
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    ),
    "Cache-Control": "no-store, max-age=0",
}

# CSP: 收紧策略
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# HSTS
HSTS_HEADER = "Strict-Transport-Security"
HSTS_VALUE = "max-age=31536000; includeSubDomains; preload"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP 安全头中间件 — 为所有响应注入安全头。

    配置:
    - enforce_csp: 是否强制 CSP（开发环境可关闭以允许 HMR）
    - enforce_hsts: 是否强制 HSTS（仅 HTTPS 环境启用）
    - strip_server: 是否移除 Server 头（防信息泄露）
    """

    def __init__(
        self,
        app: Any,
        *,
        enforce_csp: bool = True,
        enforce_hsts: bool = True,
        strip_server: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(app)
        self.enforce_csp = enforce_csp
        self.enforce_hsts = enforce_hsts
        self.strip_server = strip_server
        self.extra_headers = extra_headers or {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # 注入标准安全头
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        # CSP
        if self.enforce_csp:
            response.headers["Content-Security-Policy"] = CSP_POLICY

        # HSTS
        if self.enforce_hsts:
            response.headers[HSTS_HEADER] = HSTS_VALUE

        # 额外自定义头
        for header, value in self.extra_headers.items():
            response.headers[header] = value

        # 移除 Server 头防信息泄露
        if self.strip_server:
            response.headers.pop("Server", None)

        return response


class CORSSecurityMiddleware(BaseHTTPMiddleware):
    """安全 CORS 中间件 — 白名单 origin 精确匹配。"""

    def __init__(self, app: Any, allowed_origins: list[str] | None = None):
        super().__init__(app)
        self.allowed_origins = set(allowed_origins or [])

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        origin = request.headers.get("origin")

        # 预检请求
        if request.method == "OPTIONS":
            if origin and origin in self.allowed_origins:
                return Response(
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
                        "Access-Control-Max-Age": "3600",
                        "Access-Control-Allow-Credentials": "true",
                    },
                )
            return Response(status_code=403)

        response = await call_next(request)

        # 实际响应追加 CORS 头
        if origin and origin in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Expose-Headers"] = "Content-Type, X-Total-Count"

        return response


def validate_security_headers(headers: dict[str, str]) -> dict[str, Any]:
    """验证响应头是否满足安全基线（渗透测试用）。

    Returns:
        验证结果: {passed: bool, missing: [...], present: {...}}
    """
    required = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": None,  # 存在即可
        "Referrer-Policy": None,
    }
    recommended = {
        "Strict-Transport-Security": None,
        "Permissions-Policy": None,
        "X-XSS-Protection": None,
    }

    missing_required = []
    missing_recommended = []
    present = {}

    for header, expected_value in required.items():
        value = headers.get(header.lower()) or headers.get(header)
        if value is None:
            missing_required.append(header)
        else:
            present[header] = value
            if expected_value and value != expected_value:
                missing_required.append(f"{header} (expected: {expected_value}, got: {value})")

    for header, _ in recommended.items():
        value = headers.get(header.lower()) or headers.get(header)
        if value is None:
            missing_recommended.append(header)
        else:
            present[header] = value

    return {
        "passed": len(missing_required) == 0,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "present": present,
        "score": round(len(present) / (len(required) + len(recommended)) * 100, 1),
    }
