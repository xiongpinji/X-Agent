import logging
import time
from collections import deque
from threading import Lock
from uuid import uuid4
from secrets import token_urlsafe

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError as PydanticValidationError
from starlette.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.api.agents import router as agents_router
from backend.app.api.approvals import router as approvals_router
from backend.app.api.audit import router as audit_router
from backend.app.api.browser import router as browser_router
from backend.app.api.channels import router as channels_router
from backend.app.api.collaboration import router as collaboration_router
from backend.app.api.commercial_pilot import router as commercial_pilot_router
from backend.app.api.control_modes import router as control_modes_router
from backend.app.api.control_plane import router as control_plane_router
from backend.app.api.desktop import router as desktop_router
from backend.app.api.dispatch import router as dispatch_router
from backend.app.api.errors import (
    XAgentAPIError,
    pydantic_validation_error_handler,
    validation_error_handler,
    xagent_api_error_handler,
)
from backend.app.api.auth import router as auth_router
from backend.app.api.feishu import router as feishu_router
from backend.app.api.integrations import router as integrations_router
from backend.app.api.issue_to_pr import router as issue_to_pr_router
from backend.app.api.memory import router as memory_router
from backend.app.api.messages import router as messages_router
from backend.app.api.org import router as org_router
from backend.app.api.evolution import router as evolution_router
from backend.app.api.migration import router as migration_router
from backend.app.api.workbench import router as workbench_router
from backend.app.api.metrics import router as metrics_router
from backend.app.api.overview import router as overview_router
from backend.app.api.planning import router as planning_router
from backend.app.api.execution import router as execution_router
from backend.app.api.verification import router as verification_router
from backend.app.api.replay import router as replay_router
from backend.app.api.ops import router as ops_router
from backend.app.api.runs import router as runs_router
from backend.app.api.security import router as security_router
from backend.app.api.skill_curator import router as skill_curator_router
from backend.app.api.tenants import router as tenants_router
from backend.app.api.tools import router as tools_router
from backend.app.api.traces import router as traces_router
from backend.app.api.users import router as users_router
from backend.app.api.workflows import router as workflows_router
from backend.app.api.execution_control import router as execution_control_router
from backend.app.api.tools_control import router as tools_control_router
from backend.app.api.memory_control import router as memory_control_router
from backend.app.api.organization_control import router as organization_control_router
from backend.app.api.marketplace_control import router as marketplace_control_router
from backend.app.api.navigation_control import router as navigation_control_router
from backend.app.api.health import router as health_router
from backend.app.api.streaming import router as streaming_router
from backend.app.api.tasks_ui import router as tasks_router
from backend.app.api.questions import router as questions_router
from backend.app.api.file_preview import router as file_preview_router
from backend.app.api.parallel_agents import router as parallel_agents_router
from backend.app.api.browser_advanced import router as browser_advanced_router
from backend.app.api.workspace import router as workspace_router
from backend.app.api.tools_batch import router as tools_batch_router
from backend.app.api.memory_enhanced import router as memory_enhanced_router
from backend.app.api.feedback import router as feedback_router
from backend.app.api.sync import router as sync_router
from backend.app.api.sandbox_tasks import router as sandbox_tasks_router
from backend.app.api.sandbox_tasks import start_sandbox_worker, stop_sandbox_worker
from backend.app.services.browser.automation import browser_automation
from backend.app.services.browser.playwright_client import browser_client
from backend.app.services.memory.indexer import memory_indexer
from backend.app.services.memory.retriever import memory_retriever
from backend.app.services.memory.qdrant_client import vector_client
from backend.app.services.observability.langfuse_client import langfuse_client
from backend.app.dependencies import (
    enforce_scope,
    get_audit_store,
    get_browser_store,
    get_current_principal,
    get_memory,
    get_run_store,
    get_trace_store,
    get_workflow_repository,
)
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.core.mcp.manager import (
    initialize_mcp_manager,
    shutdown_mcp_manager,
)
from backend.app.core.feishu_bridge import feishu_bridge
from backend.app.core.hooks import (
    DEFAULT_CONFIG_RELPATH,
    HooksConfig,
    get_hook_manager,
    register_hooks_from_config,
)
from backend.app.core.tool_registry import ToolCatalog
from backend.app.settings import get_settings


API_KEY_EXEMPT_PATHS = {
    "/",
    "/health",
    "/ready",
    "/api/v1/channels/telegram/webhook",
    "/api/v1/integrations/feishu/events",
}


def require_api_key_header(request: Request) -> None:
    if not settings.require_api_key:
        return
    if request.url.path in API_KEY_EXEMPT_PATHS:
        return
    if _request_has_valid_api_key(request):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")


class _RateLimiter:
    """Simple in-memory rate limiter using sliding window per client IP."""

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = {}
        self._lock = Lock()

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            window = self._windows.get(key)
            if window is None:
                window = deque()
                self._windows[key] = window
            while window and window[0] < now - window_seconds:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(now)
            return True

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
            request.scope["principal"] = Principal(
                tenant_id="default",
                user_id="bootstrap-admin",
                role="admin",
                scopes=list(ROLE_SCOPES["admin"]),
                api_key_id="bootstrap",
                authenticated=True,
            )
            return True
        principal = get_api_key_store().authenticate(raw_key)
        if principal is None:
            return False
        request.scope["principal"] = principal
        return True
    except Exception:  # noqa: BLE001 - never let CSRF exemption check crash the request
        return False


def _api_key_failure_detail(request: Request) -> str:
    return "Invalid API key" if request.headers.get("x-api-key") else "Missing API key"


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
app = FastAPI(title=settings.app_name, version="0.1.0")
if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dir, html=False), name="assets")

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


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    client_ip = _get_client_ip(request)
    if path == "/api/v1/auth/login":
        if not _rate_limiter.is_allowed(f"login:{client_ip}", limit=10, window_seconds=60):
            return JSONResponse({"detail": "Rate limit exceeded. Try again later."}, status_code=429)
    elif path == "/api/v1/auth/register":
        if not _rate_limiter.is_allowed(f"register:{client_ip}", limit=5, window_seconds=60):
            return JSONResponse({"detail": "Rate limit exceeded. Try again later."}, status_code=429)
    elif path.startswith("/api/"):
        if not _rate_limiter.is_allowed(f"api:{client_ip}", limit=100, window_seconds=60):
            return JSONResponse({"detail": "Rate limit exceeded. Try again later."}, status_code=429)
    return await call_next(request)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    started = time.perf_counter()
    if settings.require_api_key and request.url.path not in API_KEY_EXEMPT_PATHS:
        if not _request_has_valid_api_key(request):
            response = JSONResponse({"detail": _api_key_failure_detail(request)}, status_code=401)
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
        principal = request.scope.get("principal")
        if principal is None and (
            request.headers.get("x-api-key")
            or request.headers.get("authorization", "").lower().startswith("bearer ")
        ):
            try:
                principal = get_current_principal(request)
            except Exception:
                principal = None
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


app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(browser_router)
app.include_router(channels_router)
app.include_router(collaboration_router)
app.include_router(commercial_pilot_router)
app.include_router(control_modes_router)
app.include_router(control_plane_router)
app.include_router(desktop_router)
app.include_router(dispatch_router)
app.include_router(feishu_router)
app.include_router(integrations_router)
app.include_router(issue_to_pr_router)
app.include_router(memory_router)
app.include_router(org_router)
app.include_router(evolution_router)
app.include_router(migration_router)
app.include_router(planning_router)
app.include_router(workbench_router)
app.include_router(messages_router)
app.include_router(metrics_router, dependencies=[Depends(get_current_principal)])
app.include_router(overview_router)
app.include_router(execution_router)
app.include_router(verification_router)
app.include_router(replay_router)
app.include_router(ops_router)
app.include_router(runs_router)
app.include_router(security_router)
app.include_router(skill_curator_router)
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
app.include_router(health_router)
app.include_router(streaming_router)
app.include_router(tasks_router)
app.include_router(questions_router)
app.include_router(file_preview_router)
app.include_router(parallel_agents_router)
app.include_router(browser_advanced_router)
app.include_router(workspace_router)
app.include_router(tools_batch_router)
app.include_router(memory_enhanced_router)
app.include_router(feedback_router)
app.include_router(sync_router)
app.include_router(sandbox_tasks_router)
app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(PydanticValidationError, pydantic_validation_error_handler)


@app.on_event("startup")
async def startup_event():
    """应用启动事件处理器

    初始化MCP管理器和其他必要的服务。
    """
    logger.info("Starting X-Agent application...")

    # Security check: production API auth must be enforced unless running as a
    # local desktop (lite) deployment (SECURITY P0-06).
    # 云端/API 部署若误配 require_api_key=false,整个 API 无认证保护——拒绝启动。
    # 桌面 lite 单机模式可显式关闭(本机用户即操作者,无网络暴露面)。
    from backend.app.settings import get_settings as _get_settings
    _settings = _get_settings()
    if _settings.app_mode == "production" and not _settings.require_api_key:
        if _settings.mode == "lite":
            # 桌面本地部署:保留 WARNING,不阻断启动
            logger.warning(
                "XAGENT_REQUIRE_API_KEY=false in production desktop (lite) mode. "
                "Acceptable for single-user local use; do NOT expose this to a network."
            )
        else:
            # 云端/standard/production 部署:强制要求认证,拒绝启动
            raise RuntimeError(
                "XAGENT_REQUIRE_API_KEY=false is forbidden in production mode (mode="
                + str(_settings.mode)
                + "). Set XAGENT_REQUIRE_API_KEY=true, or use XAGENT_MODE=lite for "
                "single-user desktop deployments. Ref: SECURITY_DECISIONS.md D-1"
            )

    if _settings.feishu_app_id and _settings.feishu_app_secret:
        feishu_bridge.configure(
            app_id=_settings.feishu_app_id,
            app_secret=_settings.feishu_app_secret,
            base_url=_settings.feishu_base_url,
            encrypt_key=_settings.feishu_encrypt_key,
        )
        logger.info("Feishu bridge configured from environment")
    elif feishu_bridge.configure_from_env():
        logger.info("Feishu bridge configured from legacy environment aliases")
    else:
        logger.info("Feishu bridge not configured from environment")

    try:
        # 初始化MCP管理器
        # MCP管理器负责发现、连接和管理MCP服务器
        mcp_manager = await initialize_mcp_manager(
            tool_registry=tool_registry,
            config_path="config/mcp_servers.yaml"
        )

        if mcp_manager:
            logger.info("MCP manager initialized successfully")
            # 获取初始化统计信息
            stats = mcp_manager.get_stats()
            logger.info(f"MCP initialization stats: {stats}")
        else:
            logger.warning(
                "MCP manager initialization skipped - no configuration found or all servers failed. "
                "Application will continue without MCP support."
            )
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
        await start_sandbox_worker()
    except Exception as e:
        logger.error(f"Failed to start sandbox worker: {e}", exc_info=True)
        logger.warning("Application startup continuing without sandbox worker")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件处理器

    清理MCP资源和其他必要的清理工作。
    """
    logger.info("Shutting down X-Agent application...")

    try:
        # 关闭MCP管理器
        # 这会停止健康检查任务并关闭所有MCP服务器连接
        await shutdown_mcp_manager()
        logger.info("MCP manager shutdown complete")
    except Exception as e:
        logger.error(f"Error during MCP manager shutdown: {e}", exc_info=True)

    try:
        await stop_sandbox_worker()
        logger.info("Sandbox worker shutdown complete")
    except Exception as e:
        logger.error(f"Error during sandbox worker shutdown: {e}", exc_info=True)

    logger.info("X-Agent application shutdown complete")


@app.get("/chat")
async def chat_page() -> FileResponse:
    return FileResponse(frontend_dir / "chat.html")


@app.get("/")
async def root() -> FileResponse:
    startup = frontend_dir / "startup.html"
    if startup.exists():
        return FileResponse(startup)
    return FileResponse(frontend_dir / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Public (in every middleware skip-list); no auth/CSRF.

    Reports only that the process is up and serving — does not touch
    downstream components (that is what /ready is for). The `service`
    key lets multi-service deployments disambiguate which app answered.
    """
    return {"status": "ok", "service": "x-agent"}


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
        except Exception as exc:  # noqa: BLE001 - report, don't crash the probe
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
        except Exception as exc:  # noqa: BLE001 - optional integration, never fail probe
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
