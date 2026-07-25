import logging
import time
from collections import deque
from secrets import token_urlsafe
from threading import Lock
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError as PydanticValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.app.api.errors import (
    XAgentAPIError,
    pydantic_validation_error_handler,
    validation_error_handler,
    xagent_api_error_handler,
)
from backend.app.core.hooks import (
    DEFAULT_CONFIG_RELPATH,
    HooksConfig,
    get_hook_manager,
    register_hooks_from_config,
)
from backend.app.core.lifecycle import get_lifecycle_manager
from backend.app.core.mcp.manager import initialize_mcp_manager
from backend.app.core.security import Principal
from backend.app.core.tenant_isolation import TenantIsolationMiddleware
from backend.app.core.tool_registry import ToolCatalog
from backend.app.dependencies import (
    get_audit_store,
    get_browser_store,
    get_current_principal,
    get_memory,
    get_run_store,
    get_trace_store,
    get_workflow_repository,
)
from backend.app.settings import get_settings


def require_api_key_header(request: Request) -> None:
    if not settings.require_api_key:
        return
    if request.url.path in {"/", "/health", "/ready", "/metrics", "/api/v1/channels/telegram/webhook"}:
        return
    if request.headers.get("x-api-key"):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")


class _RateLimiter:
    """Simple in-memory rate limiter using sliding window per client IP.

    Supports optional Redis backend for distributed deployments.
    Returns retry_after seconds when rate limit is exceeded.
    """

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = {}
        self._lock = Lock()

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Check if request is allowed.

        Returns:
            Tuple of (allowed: bool, retry_after: int seconds).
        """
        now = time.time()
        with self._lock:
            window = self._windows.get(key)
            if window is None:
                window = deque()
                self._windows[key] = window
            while window and window[0] < now - window_seconds:
                window.popleft()
            if len(window) >= limit:
                # Calculate when the oldest request in window expires
                retry_after = int(window[0] + window_seconds - now) + 1
                return False, max(retry_after, 1)
            window.append(now)
            return True, 0

    def cleanup(self, max_age_seconds: int = 3600) -> None:
        now = time.time()
        with self._lock:
            stale = [k for k, w in self._windows.items() if w and w[-1] < now - max_age_seconds]
            for k in stale:
                del self._windows[k]


_rate_limiter = _RateLimiter()


def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _request_has_valid_api_key(request: Request) -> bool:
    """Whether the request carries a valid X-API-Key (bootstrap or stored key).

    Used by the CSRF middleware to exempt header-authenticated, CSRF-immune
    requests. Reuses the exact auth-layer checks so this exemption can never be
    looser than authentication: a forged X-API-Key value still fails here.
    """
    raw_key = request.headers.get("x-api-key")
    if not raw_key:
        return False
    try:
        from backend.app.dependencies import (
            _matches_bootstrap_key,
            get_api_key_store,
        )

        app_settings = get_settings()
        if _matches_bootstrap_key(
            raw_key,
            app_settings.bootstrap_api_key,
            app_settings.bootstrap_api_key_sha256,
        ):
            return True
        return get_api_key_store().authenticate(raw_key) is not None
    except Exception:
        return False


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware using token validation.

    SECURITY: Prevents Cross-Site Request Forgery attacks by validating
    CSRF tokens on state-changing requests (POST, PUT, PATCH, DELETE).
    """

    # Safe methods that don't require CSRF tokens
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    # Endpoints that don't require CSRF protection
    EXEMPT_PATHS = {
        "/",
        "/health",
        "/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/logout",
        # The CSRF-token issuing endpoint must itself be exempt — a client has no
        # token yet when it calls here, so requiring one creates a bootstrap
        # deadlock (the endpoint that hands out tokens could never be reached).
        "/api/v1/csrf-token",
        # Signature-authenticated server-to-server webhook. Feishu's servers
        # cannot carry a cookie-based CSRF token; the endpoint authenticates via
        # signed callback headers (official X-Lark-* or legacy x-feishu-*) which an
        # attacker page cannot forge. Same CSRF-immunity rationale as the
        # header-based API-key exemption below. Without this the webhook is
        # unreachable in production (CSRF 403s before the signature check runs).
        "/api/v1/integrations/feishu/events",
        # First-run chat bootstrap. Authentication is still enforced inside the
        # workflow router; unauthenticated access is only granted in non-production
        # dev mode by a route-specific principal, not by global anonymous scope.
        "/api/v1/workflows/create/chat",
        # Read-only issue-to-PR planning endpoint. Execute mode intentionally
        # remains CSRF-protected.
        "/api/v1/issue-to-pr/dry-run",
        # Signature-token authenticated Telegram webhook. Telegram cannot send
        # browser CSRF tokens, and forged browser pages cannot set Telegram's
        # secret-token header across origins.
        "/api/v1/channels/telegram/webhook",
    }

    # SECURITY/ARCHITECTURE: token store is class-level (shared across instances).
    # Two instances exist — the module-level ``_csrf_middleware`` used by the
    # /api/v1/csrf-token endpoint to GENERATE tokens, and the instance Starlette
    # creates when this class is added to the ASGI stack (which VALIDATES tokens).
    # If the store were per-instance, generated tokens would be invisible to the
    # validating instance and every token would be rejected. A class-level dict
    # keyed by session_id makes generation and validation share the same state
    # within the process.
    _tokens: dict[str, set[str]] = {}  # session_id -> set of valid tokens
    _lock = Lock()

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Skip CSRF check for safe methods
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        # Skip CSRF check for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip CSRF check for non-API endpoints
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # SECURITY: Header-based API-key auth is inherently immune to CSRF.
        # CSRF attacks rely on the browser auto-attaching ambient credentials
        # (cookies) to a forged cross-site request. A custom request header like
        # X-API-Key cannot be set cross-origin by an attacker page (it would be a
        # non-simple request gated by a CORS preflight, which this app does not
        # grant to untrusted origins; CORS here also uses allow_credentials=False).
        # So a request carrying a valid bootstrap/API key is not a forgeable
        # cross-site request and must not be blocked by the cookie-based CSRF
        # check — otherwise all programmatic clients (CLI, server-to-server) are
        # locked out. This mirrors Django REST Framework, which exempts
        # non-SessionAuthentication (token/key) requests from CSRF enforcement.
        if _request_has_valid_api_key(request):
            return await call_next(request)

        # SECURITY: Bearer-token auth is likewise CSRF-immune. A bearer token is
        # presented in the Authorization header, which a browser will not attach
        # automatically to a cross-site request and which an attacker page cannot
        # set cross-origin (non-simple header → blocked by CORS preflight; this
        # app does not grant CORS to untrusted origins, allow_credentials=False).
        # So a request carrying a Bearer token is not a forgeable cross-site
        # request and must not be blocked by the cookie-based CSRF check —
        # otherwise programmatic token clients (CLI, SDK, server-to-server)
        # cannot call state-changing endpoints such as /api/v1/auth/refresh.
        # This mirrors the API-key exemption above and DRF's exemption of
        # non-SessionAuthentication requests. Token validity is still enforced
        # by the route's own auth layer (enforce_scope / principal.authenticated),
        # so an invalid/expired token is rejected there with 401 — CSRF exemption
        # only skips the *cookie* anti-forgery check, not authentication.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            return await call_next(request)

        # Validate CSRF token
        csrf_token = request.headers.get("X-CSRF-Token")
        session_id = request.cookies.get("session_id")

        if not csrf_token or not session_id:
            logger.warning(f"CSRF token missing for {request.method} {request.url.path}")
            return JSONResponse(
                {"detail": "CSRF token required"},
                status_code=403
            )

        # Check if token is valid for this session
        with self._lock:
            valid_tokens = self._tokens.get(session_id, set())
            if csrf_token not in valid_tokens:
                logger.warning(f"Invalid CSRF token for session {session_id}")
                return JSONResponse(
                    {"detail": "Invalid CSRF token"},
                    status_code=403
                )

        response = await call_next(request)
        return response

    def generate_csrf_token(self, session_id: str) -> str:
        """Generate a new CSRF token for a session.

        Args:
            session_id: Session identifier

        Returns:
            CSRF token
        """
        token = token_urlsafe(32)
        with self._lock:
            if session_id not in self._tokens:
                self._tokens[session_id] = set()
            self._tokens[session_id].add(token)
            # Keep only last 10 tokens per session
            if len(self._tokens[session_id]) > 10:
                self._tokens[session_id].pop()
        return token


_csrf_middleware = CSRFProtectionMiddleware(None)


settings = get_settings()
logger = logging.getLogger("xagent.http")

# 创建全局工具注册表实例
tool_registry = ToolCatalog()

frontend_dir = settings.static_dir
# React 构建产物目录(frontend/dist)。存在时优先伺服构建产物,不存在时回退源码目录。
frontend_dist_dir = frontend_dir / "dist"

# ─── OpenAPI 文档元数据 ─────────────────────────────────────────────────────────

OPENAPI_DESCRIPTION = """\
X-Agent is a commercial-grade autonomous AI agent platform.

## Core Capabilities

- **Agent Lifecycle** — create, configure, execute and monitor autonomous agents
- **Goal Mode** — autonomous objective tracking with checkpoint-based progress
- **Dual-Layer Memory** — short-term working memory + long-term vector store (Qdrant)
- **Workflow Orchestration** — DAG-based workflow engine with scheduling & replay
- **Self-Evolution (GEPA)** — Gather → Evaluate → Plan → Act improvement cycle
- **AI Code Review** — automated diff/PR/file review with risk scoring
- **Enterprise SSO** — OIDC / SAML / LDAP / WebAuthn authentication
- **MCP Integration** — Model Context Protocol tool discovery & management
- **Multi-Agent Collaboration** — parallel agent execution and coordination
- **Plugin Ecosystem** — extensible plugin runtime with marketplace

## Security

- API-key / Bearer-token / CSRF protection
- Tenant isolation & RBAC
- Rate limiting & request size enforcement
- Audit logging with syslog/webhook export
- KMS envelope encryption with auto key rotation

## Links

- [GitHub Repository](https://github.com/x-agent/x-agent)
- [Documentation](https://docs.x-agent.dev)
"""

tags_metadata = [
    {"name": "agents", "description": "Agent lifecycle management — create, configure, execute and monitor autonomous agents"},
    {"name": "goals", "description": "Goal Mode — autonomous objective tracking with checkpoint-based progress"},
    {"name": "code-review", "description": "AI-powered code review — diff, PR and file analysis with risk scoring"},
    {"name": "evolution", "description": "Self-evolution engine (GEPA cycle: Gather → Evaluate → Plan → Act)"},
    {"name": "workflows", "description": "Workflow orchestration — DAG-based execution, scheduling and replay"},
    {"name": "memory", "description": "Dual-layer memory system — short-term working memory + long-term vector store"},
    {"name": "sso", "description": "Enterprise SSO — OIDC / SAML / LDAP / WebAuthn authentication"},
    {"name": "mcp", "description": "Model Context Protocol — tool discovery, registration and management"},
    {"name": "auth", "description": "Authentication & authorization — login, register, token refresh, RBAC"},
    {"name": "multi-agent", "description": "Multi-agent collaboration — parallel execution and coordination"},
    {"name": "plugins", "description": "Plugin ecosystem — runtime loading, marketplace and lifecycle"},
    {"name": "tools", "description": "Tool registry — discover, register and execute agent tools"},
    {"name": "sessions", "description": "Session management — conversation sessions and context"},
    {"name": "audit", "description": "Audit logging — compliance trail with export channels"},
    {"name": "security", "description": "Security operations — API keys, CSRF, tenant isolation"},
    {"name": "health", "description": "Health & readiness probes for orchestration platforms"},
]

# P1-06: 生产模式禁用 API 文档端点(/docs, /redoc, /openapi.json), 防止匿名访问接口定义
_is_production = settings.app_mode == "production"
app = FastAPI(
    title="X-Agent API",
    description=OPENAPI_DESCRIPTION,
    version="0.3.0-alpha",
    contact={"name": "X-Agent Team", "url": "https://github.com/x-agent/x-agent"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=tags_metadata,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)
if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dir, html=False), name="assets")
if frontend_dist_dir.is_dir():
    # dist/index.html 以根绝对路径引用 /js/...、/css/... 构建产物
    for _dist_subdir in ("js", "css"):
        _dist_subdir_path = frontend_dist_dir / _dist_subdir
        if _dist_subdir_path.is_dir():
            app.mount(
                f"/{_dist_subdir}",
                StaticFiles(directory=_dist_subdir_path, html=False),
                name=f"dist-{_dist_subdir}",
            )

# Parse CORS origins from settings - CRITICAL: Never use wildcard in production
allow_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

# Security enforcement: Prevent wildcard CORS in production
if "*" in allow_origins:
    if settings.app_mode == "production":
        logger.error("CRITICAL SECURITY: CORS wildcard detected in production mode. Rejecting configuration.")
        raise ValueError("CORS wildcard (*) is not allowed in production mode. Set XAGENT_CORS_ORIGINS to specific domains.")
    else:
        logger.warning("CORS wildcard detected in development mode. This is NOT recommended for production.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id", "X-API-Key", "X-CSRF-Token"],
)

# SECURITY: Add CSRF protection middleware
app.add_middleware(CSRFProtectionMiddleware)

# MONITORING: Wire the existing HTTP metrics middleware (backend.app.monitoring.middleware)
# so request latency/status are recorded into the Prometheus registry.
try:
    from backend.app.monitoring.middleware import MetricsMiddleware
    app.add_middleware(MetricsMiddleware)
except ImportError:
    logger.warning("monitoring middleware not available")

# PERFORMANCE: Wire the performance monitoring middleware (P1-18)
# Tracks per-endpoint latency, throughput, and error rates.
try:
    from backend.app.core.performance_middleware import PerformanceMonitoringMiddleware
    app.add_middleware(PerformanceMonitoringMiddleware)
except ImportError:
    logger.debug("performance monitoring middleware not available")

# SECURITY: Mount the real tenant isolation middleware (core/tenant_isolation.py)
# so request.state.tenant_id is actually populated for downstream handlers.
app.add_middleware(TenantIsolationMiddleware)

# MONITORING: Prometheus scrape endpoint. Uses the same default registry that
# core.metrics.metrics_collector records into. Degrade gracefully if the
# optional dependency is absent.
try:
    from prometheus_client import make_asgi_app

    app.mount("/metrics", make_asgi_app())

    @app.get("/metrics", include_in_schema=False)
    async def _metrics_exact_path():
        # Starlette Mount only matches "/metrics/..." — serve the exact path
        # Prometheus operators expect without a redirect (some scrapers do not
        # follow redirects with auth headers intact).
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from starlette.responses import Response

        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    logger.info("Prometheus metrics endpoint mounted at /metrics")
except ImportError:
    logger.warning("prometheus_client not installed; /metrics endpoint not available")


@app.middleware("http")
async def quota_enforcement_middleware(request: Request, call_next):
    """Tenant quota enforcement middleware.

    When XAGENT_QUOTA_ENABLED=true, checks and increments the daily API call
    counter for the authenticated tenant. Returns 429 with quota info when
    the daily limit is exceeded.

    Only active for /api/ paths. Skips health/auth endpoints.
    """
    if not settings.quota_enabled:
        return await call_next(request)

    path = request.url.path
    # Only enforce on API paths; skip health/auth/public endpoints
    if not path.startswith("/api/"):
        return await call_next(request)
    if path in {"/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/health"}:
        return await call_next(request)

    # Resolve tenant from request state (set by TenantIsolationMiddleware)
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        # No authenticated tenant — skip quota check (auth will handle 401)
        return await call_next(request)

    from backend.app.core.tenant_quota import get_tenant_quota_manager

    manager = get_tenant_quota_manager()
    allowed, reason = manager.check_quota(tenant_id, "api_calls")
    if not allowed:
        limits = manager.get_limits(tenant_id)
        usage = manager.get_usage(tenant_id)
        return JSONResponse(
            {
                "detail": "Daily API call quota exceeded",
                "quota": {
                    "resource": "api_calls",
                    "used": usage.api_calls_today,
                    "limit": limits.max_api_calls_per_day,
                    "reason": reason,
                },
            },
            status_code=429,
            headers={"Retry-After": "3600", "X-Quota-Resource": "api_calls"},
        )

    # Increment the daily API call counter
    manager.increment_usage(tenant_id, "api_calls")
    return await call_next(request)


@app.middleware("http")
async def lifecycle_tracking_middleware(request: Request, call_next):
    """Track active requests for graceful shutdown draining.

    Increments the lifecycle manager's active-request counter on entry
    and decrements on exit. During shutdown, new requests to non-health
    endpoints receive 503 Service Unavailable.
    """
    lifecycle = get_lifecycle_manager()

    # Reject new work during shutdown (except health probes for LB detection)
    if lifecycle.is_shutting_down and request.url.path not in {"/health", "/ready", "/metrics"}:
        return JSONResponse(
            {"detail": "Service is shutting down"},
            status_code=503,
        )

    lifecycle.track_request_start()
    try:
        response = await call_next(request)
        return response
    finally:
        lifecycle.track_request_end()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Production rate limiting middleware.

    Configurable via:
    - XAGENT_RATE_LIMIT_ENABLED: true/false (default: true in production, false in dev)
    - XAGENT_RATE_LIMIT_RPM: general API requests per minute (default: 100)
    - XAGENT_RATE_LIMIT_AUTH_RPM: auth routes per minute (default: 20)
    - XAGENT_RATE_LIMIT_LOGIN_RPM: login attempts per minute (default: 10)
    - XAGENT_RATE_LIMIT_REGISTER_RPM: register attempts per minute (default: 5)

    Returns 429 with Retry-After header when exceeded.
    """
    if not settings.rate_limit_active:
        return await call_next(request)

    path = request.url.path
    client_ip = _get_client_ip(request)

    def _rate_limited_response(retry_after: int) -> JSONResponse:
        resp = JSONResponse(
            {"detail": "Rate limit exceeded. Try again later."},
            status_code=429,
        )
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    if path == "/api/v1/auth/login":
        allowed, retry_after = _rate_limiter.is_allowed(
            f"login:{client_ip}", limit=settings.rate_limit_login_rpm, window_seconds=60
        )
        if not allowed:
            return _rate_limited_response(retry_after)
    elif path == "/api/v1/auth/register":
        allowed, retry_after = _rate_limiter.is_allowed(
            f"register:{client_ip}", limit=settings.rate_limit_register_rpm, window_seconds=60
        )
        if not allowed:
            return _rate_limited_response(retry_after)
    elif path.startswith("/api/v1/auth/"):
        allowed, retry_after = _rate_limiter.is_allowed(
            f"auth:{client_ip}", limit=settings.rate_limit_auth_rpm, window_seconds=60
        )
        if not allowed:
            return _rate_limited_response(retry_after)
    elif path.startswith("/api/"):
        allowed, retry_after = _rate_limiter.is_allowed(
            f"api:{client_ip}", limit=settings.rate_limit_rpm, window_seconds=60
        )
        if not allowed:
            return _rate_limited_response(retry_after)
    return await call_next(request)


@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next):
    """Reject requests with body exceeding max_request_body_size.

    Checks Content-Length header to reject oversized payloads early
    before reading the body into memory. Default limit: 10MB.
    Configurable via XAGENT_MAX_REQUEST_BODY_SIZE.
    """
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_request_body_size:
                return JSONResponse(
                    {
                        "detail": (
                            f"Request body too large. "
                            f"Maximum allowed size is {settings.max_request_body_size // (1024 * 1024)}MB."
                        )
                    },
                    status_code=413,
                )
        except (ValueError, TypeError):
            pass  # Malformed Content-Length — let downstream handle it
    return await call_next(request)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()

    # Bind request context to structlog for distributed trace propagation
    try:
        from backend.app.core.logging_config import bind_request_context, clear_request_context
        bind_request_context(request_id=request_id, path=request.url.path, method=request.method)
    except Exception:
        clear_request_context = None

    try:
        if settings.require_api_key and request.url.path not in {"/", "/health", "/ready", "/metrics", "/api/v1/channels/telegram/webhook"}:
            if not request.headers.get("x-api-key"):
                response = JSONResponse({"detail": "Missing API key"}, status_code=401)
                response.headers["x-request-id"] = request_id
                return response
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        response.headers["x-request-id"] = request_id
        logger.info(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response
    finally:
        if clear_request_context is not None:
            clear_request_context()


@app.middleware("http")
async def tenant_isolation_middleware(request: Request, call_next):
    """Enforce tenant isolation at middleware level.

    CRITICAL SECURITY: Validate that tenant_id in request body/params matches
    the authenticated principal's tenant_id (unless principal is admin).
    This prevents tenant isolation bypass attacks.
    """
    # Skip middleware for public endpoints
    if request.url.path in {"/", "/health", "/ready", "/api/v1/auth/login", "/api/v1/auth/register"}:
        return await call_next(request)

    # Skip middleware for non-API endpoints
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    try:
        # Resolve the principal directly: this previously read
        # request.scope["principal"], which nothing ever populated, making the
        # check dead code. Resolve via the standard dependency (best-effort;
        # real auth still happens in route handlers) and publish it on
        # scope/state so downstream handlers can reuse it.
        principal = get_current_principal(request)
        request.scope["principal"] = principal
        request.state.principal = principal
        if principal and principal.role != "admin":
            # Check for tenant_id in query parameters
            tenant_id_param = request.query_params.get("tenant_id")
            if tenant_id_param and tenant_id_param != principal.tenant_id:
                return JSONResponse(
                    {"detail": f"Tenant isolation violation: cannot access tenant '{tenant_id_param}'"},
                    status_code=403
                )
    except Exception:
        # If we can't validate, let the route handler deal with it
        pass

    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses.

    Implements:
    - Content-Security-Policy (CSP) to prevent XSS
    - X-Frame-Options to prevent clickjacking
    - X-Content-Type-Options to prevent MIME sniffing
    - Strict-Transport-Security (HSTS) for HTTPS enforcement
    - X-XSS-Protection for legacy browser support
    """
    response = await call_next(request)

    # Content-Security-Policy: Prevent XSS attacks
    # P1-06: 生产模式移除 unsafe-inline/unsafe-eval, 杜绝内联脚本注入向量
    if settings.app_mode == "production":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

    # X-Frame-Options: Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # X-Content-Type-Options: Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Strict-Transport-Security: Enforce HTTPS (only in production)
    if settings.app_mode == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    # X-XSS-Protection: Legacy browser support
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Referrer-Policy: Control referrer information
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Permissions-Policy: Control browser features
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )

    return response


_routers_registered = False


def _register_all_routers() -> None:
    """Lazily import and register all API routers.

    Called during startup event to defer heavy module imports until the
    application is actually starting, reducing initial import time from ~9s
    to under 2s.

    Idempotent: safe to call multiple times (e.g. repeated TestClient startups).
    """
    global _routers_registered
    if _routers_registered:
        return
    _routers_registered = True
    from backend.app.api.agents import router as agents_router
    from backend.app.api.approvals import router as approvals_router
    from backend.app.api.audit import router as audit_router
    from backend.app.api.audit_enterprise import router as audit_enterprise_router
    from backend.app.api.audit_rotation_api import router as audit_rotation_router
    from backend.app.api.auth import router as auth_router
    from backend.app.api.backup_qdrant import router as backup_qdrant_router
    from backend.app.api.backup_scheduler import router as backup_scheduler_router
    from backend.app.api.browser import router as browser_router
    from backend.app.api.browser_advanced import router as browser_advanced_router
    from backend.app.api.channels import router as channels_router
    from backend.app.api.chat_history import router as chat_history_router
    from backend.app.api.checkpoints import router as checkpoints_router
    from backend.app.api.code_review import router as code_review_router
    from backend.app.api.collaboration import router as collaboration_router
    from backend.app.api.compliance import router as compliance_router
    from backend.app.api.desktop import router as desktop_router
    from backend.app.api.dispatch import router as dispatch_router
    from backend.app.api.dr_status import router as dr_status_router
    from backend.app.api.enterprise_sso import router as enterprise_sso_router
    from backend.app.api.evolution import router as evolution_router
    from backend.app.api.execution import router as execution_router
    from backend.app.api.execution_control import router as execution_control_router
    from backend.app.api.feedback import router as feedback_router
    from backend.app.api.feishu import router as feishu_router
    from backend.app.api.file_preview import router as file_preview_router
    from backend.app.api.gdpr import router as gdpr_router
    from backend.app.api.goals import router as goals_router
    from backend.app.api.health import router as health_router
    from backend.app.api.integrations import router as integrations_router
    from backend.app.api.issue_to_pr import router as issue_to_pr_router
    from backend.app.api.marketplace_control import router as marketplace_control_router
    from backend.app.api.mcp import router as mcp_router
    from backend.app.api.memory import router as memory_router
    from backend.app.api.memory_control import router as memory_control_router
    from backend.app.api.memory_enhanced import router as memory_enhanced_router
    from backend.app.api.messages import router as messages_router
    from backend.app.api.metrics import router as metrics_router
    from backend.app.api.migration import router as migration_router
    from backend.app.api.mobile import router as mobile_router
    from backend.app.api.multi_agent import router as multi_agent_router
    from backend.app.api.navigation_control import router as navigation_control_router
    from backend.app.api.notifications import router as notifications_router
    from backend.app.api.ops import router as ops_router
    from backend.app.api.org import router as org_router
    from backend.app.api.organization_control import router as organization_control_router
    from backend.app.api.overview import router as overview_router
    from backend.app.api.parallel_agents import router as parallel_agents_router
    from backend.app.api.planning import router as planning_router
    from backend.app.api.plugin_ecosystem import router as plugin_ecosystem_router
    from backend.app.api.questions import router as questions_router
    from backend.app.api.replay import router as replay_router
    from backend.app.api.runs import router as runs_router
    from backend.app.api.sandbox_tasks import router as sandbox_tasks_router
    from backend.app.api.scim import router as scim_router
    from backend.app.api.security import router as security_router
    from backend.app.api.sessions import router as sessions_router
    from backend.app.api.skill_curator import router as skill_curator_router
    from backend.app.api.skill_sediment import router as skill_sediment_router
    from backend.app.api.skills_api import router as skills_api_router
    from backend.app.api.sso import auth_router as sso_auth_router
    from backend.app.api.sso import oidc_router
    from backend.app.api.streaming import router as streaming_router
    from backend.app.api.sync import router as sync_router
    from backend.app.api.tasks_ui import router as tasks_router
    from backend.app.api.tenant_quota import router as tenant_quota_router
    from backend.app.api.tenants import router as tenants_router
    from backend.app.api.tools import router as tools_router
    from backend.app.api.tools_batch import router as tools_batch_router
    from backend.app.api.tools_control import router as tools_control_router
    from backend.app.api.traces import router as traces_router
    from backend.app.api.users import router as users_router
    from backend.app.api.verification import router as verification_router
    from backend.app.api.work_mode import router as work_mode_router
    from backend.app.api.workbench import router as workbench_router
    from backend.app.api.workflows import router as workflows_router
    from backend.app.api.workspace import router as workspace_router
    from backend.plugins.router import router as plugin_runtime_router

    app.include_router(auth_router)
    app.include_router(agents_router)
    app.include_router(approvals_router)
    app.include_router(audit_router)
    app.include_router(browser_router)
    app.include_router(channels_router)
    app.include_router(chat_history_router)
    app.include_router(collaboration_router)
    app.include_router(desktop_router)
    app.include_router(dispatch_router)
    app.include_router(feishu_router)
    app.include_router(integrations_router)
    app.include_router(issue_to_pr_router)
    app.include_router(memory_router)
    app.include_router(mcp_router)
    app.include_router(org_router)
    app.include_router(evolution_router)
    app.include_router(migration_router)
    app.include_router(planning_router)
    app.include_router(workbench_router)
    app.include_router(messages_router)
    app.include_router(metrics_router)
    app.include_router(overview_router)
    app.include_router(execution_router)
    app.include_router(verification_router)
    app.include_router(replay_router)
    app.include_router(ops_router)
    app.include_router(plugin_runtime_router)
    app.include_router(runs_router)
    app.include_router(security_router)
    app.include_router(sessions_router)
    app.include_router(checkpoints_router)
    app.include_router(gdpr_router)
    app.include_router(mobile_router)
    app.include_router(code_review_router)
    app.include_router(skill_sediment_router)
    app.include_router(multi_agent_router)
    app.include_router(plugin_ecosystem_router)
    app.include_router(audit_enterprise_router)
    app.include_router(audit_rotation_router)
    app.include_router(compliance_router)
    app.include_router(skill_curator_router)
    app.include_router(skills_api_router)
    app.include_router(oidc_router)
    app.include_router(sso_auth_router)
    app.include_router(enterprise_sso_router)
    app.include_router(scim_router)
    app.include_router(tenant_quota_router)
    app.include_router(tenants_router)
    app.include_router(traces_router)
    app.include_router(tools_router)
    app.include_router(users_router)
    app.include_router(workflows_router)
    app.include_router(execution_control_router)
    app.include_router(tools_control_router)
    app.include_router(memory_control_router)
    app.include_router(organization_control_router)
    app.include_router(marketplace_control_router)
    app.include_router(navigation_control_router)
    app.include_router(notifications_router)
    app.include_router(health_router)
    app.include_router(streaming_router)
    app.include_router(tasks_router)
    app.include_router(questions_router)
    app.include_router(file_preview_router)
    app.include_router(parallel_agents_router)
    app.include_router(work_mode_router)
    app.include_router(goals_router)
    app.include_router(browser_advanced_router)
    app.include_router(workspace_router)
    app.include_router(tools_batch_router)
    app.include_router(memory_enhanced_router)
    app.include_router(feedback_router)
    app.include_router(sync_router)
    app.include_router(sandbox_tasks_router)
    app.include_router(backup_qdrant_router)
    app.include_router(backup_scheduler_router)
    app.include_router(dr_status_router)

    # SPA fallback must be registered AFTER all API routers (catch-all route)
    @app.get("/{spa_path:path}", include_in_schema=False)
    async def spa_fallback(spa_path: str) -> FileResponse:
        dist_index = frontend_dist_dir / "index.html"
        if dist_index.exists() and spa_path.split("/", 1)[0] in _SPA_ROUTE_PREFIXES:
            return FileResponse(dist_index)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    logger.info("All routers registered")

app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(PydanticValidationError, pydantic_validation_error_handler)


@app.on_event("startup")
async def startup_event():
    """应用启动事件处理器

    初始化MCP管理器和其他必要的服务。
    """
    logger.info("Starting X-Agent application...")

    # Phase 0: Initialize lifecycle manager (graceful shutdown orchestration)
    lifecycle = get_lifecycle_manager()
    await lifecycle.on_startup(app)

    # Phase 1: Register all API routers (deferred imports)
    _register_all_routers()

    # Initialize Redis connection pool
    try:
        from backend.app.core.redis_client import init_redis
        redis_client = await init_redis()
        app.state.redis = redis_client
        if redis_client.is_available:
            logger.info("Redis connection pool initialized")
        else:
            logger.info("Redis not available, using in-memory fallback")
    except Exception as e:
        logger.warning(f"Redis initialization failed: {e}. Using in-memory fallback.")

    # Security check: warn if production API auth is disabled
    from backend.app.settings import get_settings as _get_settings
    _settings = _get_settings()
    if _settings.app_mode == "production" and not _settings.require_api_key:
        logger.warning(
            "SECURITY WARNING: XAGENT_REQUIRE_API_KEY=false in production mode. "
            "Cloud and API deployments should set XAGENT_REQUIRE_API_KEY=true to prevent unauthenticated access. "
            "Desktop-local deployments may leave this off intentionally."
        )


    try:
        # P1-01: 初始化MCP管理器（官方 SDK 工具发现与管理）
        # 仅当 XAGENT_MCP_ENABLED=true 时启用（opt-in）
        if _settings.mcp_enabled:
            mcp_manager = await initialize_mcp_manager(
                tool_registry=tool_registry,
                config_path=_settings.mcp_config_path,
            )

            if mcp_manager:
                logger.info("MCP manager initialized successfully")
                # 获取初始化统计信息
                stats = mcp_manager.get_stats()
                logger.info(f"MCP initialization stats: {stats}")
            else:
                logger.warning(
                    "MCP manager initialization skipped - no configuration found "
                    "or all servers failed. Application will continue without MCP support."
                )
        else:
            logger.info("MCP disabled (XAGENT_MCP_ENABLED=false), skipping initialization")
    except Exception as e:
        logger.error(f"Failed to initialize MCP manager: {e}", exc_info=True)
        # 根据配置决定是否继续启动
        # 当前策略：记录错误但继续启动，允许应用在没有MCP的情况下运行
        logger.warning("Application startup continuing without MCP support")

    # 加载并注册 Hooks（控制平面拦截层）
    # Hooks 从 .xagent/hooks.json 读取声明式配置，注册进进程级全局
    # HookManager；ToolRegistry 在咽喉点 execute() 处复用同一个全局管理器，
    # 因此这里的注册顺序与工具注册表构造顺序无关。无配置 = 空管理器 = 无操作。
    try:
        hooks_config = HooksConfig(DEFAULT_CONFIG_RELPATH)
        if hooks_config.hooks:
            is_valid, errors = hooks_config.validate()
            if not is_valid:
                logger.warning("Hooks configuration has errors: %s", errors)
            count = register_hooks_from_config(get_hook_manager(), hooks_config)
            logger.info("Registered %d hook(s) from %s", count, DEFAULT_CONFIG_RELPATH)
        else:
            logger.info(
                "No hooks configured (%s absent or empty); "
                "agent runs without control-plane hooks.",
                DEFAULT_CONFIG_RELPATH,
            )
    except Exception as e:
        # Fail-open: a broken hooks config must never block startup.
        logger.error(f"Failed to load hooks configuration: {e}", exc_info=True)
        logger.warning("Application startup continuing without hooks")

    # Start the sandbox worker (persistent drain loop on the app event loop).
    try:
        from backend.app.api.sandbox_tasks import start_sandbox_worker
        await start_sandbox_worker()
    except Exception as e:
        logger.error(f"Failed to start sandbox worker: {e}", exc_info=True)
        logger.warning("Application startup continuing without sandbox worker")

    # P1-11: 技能系统接入主循环 —— 将 skills/ 目录下的技能桥接为 AgentLoop 可消费工具
    try:
        from backend.app.core.skill_agent_adapter import register_skills_into_tool_registry
        from backend.app.core.tools import ToolRegistry as RuntimeToolRegistry

        # 获取或创建运行时工具注册表（AgentLoop 咽喉点）
        runtime_registry = getattr(app.state, "runtime_tool_registry", None)
        if runtime_registry is None:
            runtime_registry = RuntimeToolRegistry()
            app.state.runtime_tool_registry = runtime_registry
        registered_skills = await register_skills_into_tool_registry(runtime_registry)
        if registered_skills:
            logger.info(f"P1-11: Registered {len(registered_skills)} skill(s) into agent loop: {registered_skills}")
        else:
            logger.info("P1-11: No skills found in skills/ directory; agent loop runs without skill tools")
    except Exception as e:
        logger.error(f"Failed to register skills into agent loop: {e}", exc_info=True)
        logger.warning("Application startup continuing without skill tools")

    # P1-12: 插件系统接入主循环 —— 加载 plugins/ 目录下的 MCP 插件并桥接为 AgentLoop 可消费工具
    try:
        from backend.app.core.plugin_agent_adapter import register_plugins_into_tool_registry
        from backend.plugins.runtime import get_plugin_runtime

        plugin_runtime = get_plugin_runtime()
        plugin_runtime.load_all()
        # 获取 AgentLoop 的 ToolRegistry（与 get_agent() 单例共享）
        try:
            from backend.app.dependencies import get_agent
            agent_instance = get_agent()
            plugin_tool_registry = agent_instance.tools
        except Exception:
            plugin_tool_registry = getattr(app.state, "runtime_tool_registry", None)

        if plugin_tool_registry is not None:
            registered_plugins = register_plugins_into_tool_registry(
                plugin_tool_registry, runtime=plugin_runtime,
            )
            if registered_plugins:
                logger.info(
                    "P1-12: Registered %d plugin tool(s) into agent loop: %s",
                    len(registered_plugins), registered_plugins,
                )
            else:
                logger.info(
                    "P1-12: Plugins loaded but no tools registered "
                    "(config requirements not met or no loadable plugins)",
                )
        else:
            logger.info("P1-12: No ToolRegistry available for plugin tool registration")
    except Exception as e:
        logger.error(f"Failed to register plugin tools into agent loop: {e}", exc_info=True)
        logger.warning("Application startup continuing without plugin tools")


    # P1-04: 审计外送器接线 — syslog/webhook 双通道, 配置驱动, 无配置=零开销
    try:
        import os

        from backend.app.core.audit_shipper import AuditShipper, SyslogExporter, WebhookExporter
        from backend.app.dependencies import set_audit_shipper

        exporters = []
        syslog_host = os.environ.get("XAGENT_AUDIT_SYSLOG_HOST")
        webhook_url = os.environ.get("XAGENT_AUDIT_WEBHOOK_URL")
        if syslog_host:
            syslog_port = int(os.environ.get("XAGENT_AUDIT_SYSLOG_PORT", "514"))
            exporters.append(SyslogExporter(syslog_host, port=syslog_port))
        if webhook_url:
            exporters.append(WebhookExporter(webhook_url))
        if exporters:
            shipper = AuditShipper(exporters)
            await shipper.start()
            set_audit_shipper(shipper)
            app.state.audit_shipper = shipper
            logger.info("P1-04: Audit shipper active (%d channel(s))", len(exporters))
        else:
            logger.info("P1-04: No audit export channels configured (XAGENT_AUDIT_SYSLOG_HOST / XAGENT_AUDIT_WEBHOOK_URL)")
    except Exception as e:
        logger.error(f"Failed to initialize audit shipper: {e}", exc_info=True)
        logger.warning("Application startup continuing without audit export")

    # P2-02: KMS 初始化 — 信封加密 + 自动密钥轮换检查
    try:
        from backend.app.core.kms import get_kms_manager

        kms = get_kms_manager()
        if kms.health_check():
            # 启动时执行一次自动轮换检查 (超过 auto_rotate_days 则轮换)
            rotated = kms.rotate_if_needed()
            if rotated:
                logger.info("P2-02: KMS key auto-rotated to v%d", rotated.version)
            app.state.kms_manager = kms
            logger.info("P2-02: KMS initialized (backend=%s)", kms.backend.value)
        else:
            logger.warning("P2-02: KMS health check failed; encryption features degraded")
    except Exception as e:
        logger.error(f"Failed to initialize KMS: {e}", exc_info=True)
        logger.warning("Application startup continuing without KMS")

    # P2-06: OpenTelemetry 初始化 — OTLP trace/metric 导出
    try:
        from backend.app.core.otel_exporter import get_otel_exporter

        otel = get_otel_exporter()
        if otel.is_active:
            app.state.otel_exporter = otel
            logger.info("P2-06: OTel exporter active")
        else:
            logger.info("P2-06: OTel disabled or SDK not installed (XAGENT_OTEL_ENABLED=false)")
    except Exception as e:
        logger.error(f"Failed to initialize OTel exporter: {e}", exc_info=True)
        logger.warning("Application startup continuing without OTel")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件处理器

    委托给 LifecycleManager 执行生产级优雅关闭:
    1. 标记 draining (health → 503, LB 停止路由)
    2. 等待在飞请求完成 (可配置超时)
    3. 反依赖顺序关闭所有服务连接
    """
    lifecycle = get_lifecycle_manager()
    await lifecycle.on_shutdown(
        timeout=settings.shutdown_timeout,
        drain_seconds=settings.shutdown_drain_seconds,
    )


@app.get("/chat")
async def chat_page() -> FileResponse:
    """伺服 chat 页: 优先 dist 构建产物, 回退源码目录。"""
    dist_chat = frontend_dist_dir / "chat.html"
    if dist_chat.exists():
        return FileResponse(dist_chat)
    return FileResponse(frontend_dir / "chat.html")


@app.get("/console")
async def console_page() -> FileResponse:
    """伺服 console 页: 优先 dist 构建产物, 回退源码目录。"""
    dist_console = frontend_dist_dir / "console.html"
    if dist_console.exists():
        return FileResponse(dist_console)
    return FileResponse(frontend_dir / "console.html")


@app.get("/manifest.json", include_in_schema=False)
async def pwa_manifest() -> FileResponse:
    """伺服 PWA manifest: 优先 dist 构建产物, 回退 public 目录。"""
    dist_manifest = frontend_dist_dir / "manifest.json"
    if dist_manifest.exists():
        return FileResponse(dist_manifest, media_type="application/manifest+json")
    return FileResponse(frontend_dir / "public" / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    """伺服 Service Worker: 优先 dist 构建产物, 回退 public 目录。"""
    dist_sw = frontend_dist_dir / "sw.js"
    if dist_sw.exists():
        return FileResponse(dist_sw, media_type="application/javascript")
    return FileResponse(frontend_dir / "public" / "sw.js", media_type="application/javascript")


@app.get("/")
async def root() -> FileResponse:
    dist_index = frontend_dist_dir / "index.html"
    if dist_index.exists():
        # React 构建产物存在时, / 直接返回 React 入口
        return FileResponse(dist_index)
    startup = frontend_dir / "startup.html"
    if startup.exists():
        return FileResponse(startup)
    return FileResponse(frontend_dir / "index.html")


@app.get("/health")
async def health() -> JSONResponse:
    """Liveness probe. Public (in every middleware skip-list); no auth/CSRF.

    Reports only that the process is up and serving — does not touch
    downstream components (that is what /ready is for). The `service`
    key lets multi-service deployments disambiguate which app answered.

    During graceful shutdown, returns 503 with {"status": "draining"}
    so load balancers detect the instance is leaving the pool.
    """
    lifecycle = get_lifecycle_manager()
    if lifecycle.is_shutting_down:
        return JSONResponse(
            {"status": "draining", "service": "x-agent"},
            status_code=503,
        )
    return JSONResponse({"status": "ok", "service": "x-agent"})


@app.get("/api-key/status")
async def api_key_status() -> dict[str, bool]:
    """Report whether API-key enforcement is currently active.

    Read-only introspection endpoint. Lets a client (or ops dashboard)
    discover whether protected routes require the `x-api-key` header
    without having to probe a guarded route and interpret a 401. Returns
    the live `settings.require_api_key` flag so the answer always tracks
    the running configuration.
    """
    return {"require_api_key": settings.require_api_key}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness probe. Verifies each core component dependency resolves.

    Public (in every middleware skip-list). Returns 200 with per-component
    "ok" when all required components are reachable, 503 with the failing
    component(s) marked "error" otherwise.

    `components` covers the local stores (memory/trace/runs/workflows/audit)
    plus the optional service integrations (qdrant/browser/observability).
    Optional integrations never fail the probe: they report "ok" when a real
    backend is wired and "degraded" when running on the in-memory fallback,
    so a dev box with no Qdrant/Langfuse still reports ready. `integrations`
    is a parallel name→bool map of whether each optional backend is real.
    """
    from backend.app.services.memory.qdrant_client import vector_client
    from backend.app.services.observability.langfuse_client import langfuse_client

    component_getters = {
        "memory": get_memory,
        "trace": get_trace_store,
        "runs": get_run_store,
        "workflows": get_workflow_repository,
        "audit": get_audit_store,
    }
    components: dict[str, str] = {}
    all_ok = True
    for name, getter in component_getters.items():
        try:
            getter()
            components[name] = "ok"
        except Exception as exc:
            logger.warning("readiness check failed for %s: %s", name, exc)
            components[name] = "error"
            all_ok = False

    # 可选服务集成：探针只读其连通性，不因缺失而 not_ready（dev 环境无 Qdrant/
    # Langfuse 也应 ready）。real backend → "ok"，内存回退 → "degraded"。
    integrations: dict[str, bool] = {}
    for name, probe in (
        ("qdrant", lambda: vector_client.has_real_client),
        ("browser", lambda: get_browser_store().has_real_client if hasattr(get_browser_store(), "has_real_client") else True),
        ("langfuse", lambda: langfuse_client.has_real_client),
    ):
        try:
            integrations[name] = bool(probe())
        except Exception as exc:
            logger.warning("readiness integration probe failed for %s: %s", name, exc)
            integrations[name] = False
    components["qdrant"] = "ok" if integrations["qdrant"] else "degraded"
    components["browser"] = "ok" if integrations["browser"] else "degraded"
    components["observability"] = "ok" if integrations["langfuse"] else "degraded"

    body = {
        "status": "ready" if all_ok else "not_ready",
        "components": components,
        "integrations": integrations,
    }
    return JSONResponse(body, status_code=200 if all_ok else 503)


@app.get("/api/v1/entry")
async def entry(principal: Principal = Depends(get_current_principal)) -> dict[str, object]:
    tools = ["agent", "memory", "workflow", "browser", "desktop", "plugins", "open_source"]
    sections = [
        {"key": "overview", "label": "overview"},
        {"key": "execution", "label": "execution"},
        {"key": "tools", "label": "tools"},
        {"key": "memory", "label": "memory"},
        {"key": "organization", "label": "organization"},
        {"key": "marketplace", "label": "marketplace"},
        {"key": "navigation", "label": "navigation"},
        {"key": "audit", "label": "audit"},
    ]
    return {
        "principal": principal.model_dump(mode="json"),
        "tools": tools,
        "sections": sections,
    }


@app.post("/api/v1/csrf-token")
async def get_csrf_token(request: Request) -> JSONResponse:
    """Generate CSRF token for client.

    SECURITY: Returns a CSRF token that must be included in X-CSRF-Token header
    for all state-changing requests (POST, PUT, PATCH, DELETE).

    Returns:
        dict: CSRF token
    """
    session_id = request.cookies.get("session_id") or str(uuid4())
    token = _csrf_middleware.generate_csrf_token(session_id)
    # Bind the token to a session by returning the session_id as a cookie. Without
    # this, a first-time client (no session_id yet) receives a token tied to a
    # server-generated session it never learns, so the token can't be validated
    # on the follow-up request. Setting the cookie closes that loop.
    response = JSONResponse({"csrf_token": token})
    response.set_cookie(
        "session_id", session_id, httponly=True, samesite="lax",
        secure=(settings.app_mode == "production"),
    )
    return response


# SPA 前端路由 fallback。仅在 dist 构建产物存在时, 将 React Router 已知前缀
# (frontend/src/App.tsx 中定义的所有路由前缀) 回退到 dist/index.html;
# 其余未知路径(含 /api/...)仍返回标准 404。必须注册在所有路由之后。
_SPA_ROUTE_PREFIXES = frozenset({"memory", "tasks", "tools", "chat", "agents", "settings", "workflows", "goals", "review", "evolution", "login"})
