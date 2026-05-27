import logging
import time
from collections import deque
from threading import Lock
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from backend.app.api.agents import router as agents_router
from backend.app.api.approvals import router as approvals_router
from backend.app.api.audit import router as audit_router
from backend.app.api.browser import router as browser_router
from backend.app.api.collaboration import router as collaboration_router
from backend.app.api.desktop import router as desktop_router
from backend.app.api.dispatch import router as dispatch_router
from backend.app.api.errors import (
    XAgentAPIError,
    validation_error_handler,
    xagent_api_error_handler,
)
from backend.app.api.auth import router as auth_router
from backend.app.api.feishu import router as feishu_router
from backend.app.api.integrations import router as integrations_router
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
from backend.app.services.browser.automation import browser_automation
from backend.app.services.browser.playwright_client import browser_client
from backend.app.services.memory.indexer import memory_indexer
from backend.app.services.memory.retriever import memory_retriever
from backend.app.services.memory.qdrant_client import vector_client
from backend.app.services.observability.langfuse_client import langfuse_client
from backend.app.dependencies import (
    enforce_scope,
    get_audit_store,
    get_current_principal,
    get_memory,
    get_run_store,
    get_trace_store,
    get_workflow_repository,
)
from backend.app.core.security import Principal
from backend.app.settings import get_settings


def require_api_key_header(request: Request) -> None:
    if not settings.require_api_key:
        return
    if request.url.path in {"/", "/health", "/ready"}:
        return
    if request.headers.get("x-api-key"):
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


settings = get_settings()
logger = logging.getLogger("xagent.http")

frontend_dir = settings.static_dir
app = FastAPI(title=settings.app_name, version="0.1.0")
if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dir, html=False), name="assets")
# Parse CORS origins from settings - never use wildcard in production
allow_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if "*" in allow_origins and settings.app_mode == "production":
    logger.warning("CORS wildcard detected in production mode. Using restricted origins instead.")
    allow_origins = ["http://localhost:3000", "http://localhost:8000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id", "X-API-Key"],
)


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
    if settings.require_api_key and request.url.path not in {"/", "/health", "/ready"}:
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


app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(browser_router)
app.include_router(collaboration_router)
app.include_router(desktop_router)
app.include_router(dispatch_router)
app.include_router(feishu_router)
app.include_router(integrations_router)
app.include_router(memory_router)
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
app.include_router(runs_router)
app.include_router(security_router)
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
app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)


@app.get("/")
async def root() -> FileResponse:
    startup = frontend_dir / "startup.html"
    if startup.exists():
        return FileResponse(startup)
    return FileResponse(frontend_dir / "index.html")


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
