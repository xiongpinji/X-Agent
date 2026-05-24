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
            # Remove entries outside the window
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
    # Do not trust X-Forwarded-For without verified proxy chain to prevent IP spoofing
    return request.client.host if request.client else "unknown"


settings = get_settings()
logger = logging.getLogger("xagent.http")

frontend_dir = settings.static_dir
app = FastAPI(title=settings.app_name, version="0.1.0")
if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dir, html=False), name="assets")
allow_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
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
    # Strict limits for auth endpoints
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
        {
            "id": "workbench",
            "label": "Workbench",
            "href": "/api/v1/workbench",
            "description": "统一任务入口与工具总览",
        },
        {
            "id": "overview",
            "label": "Overview",
            "href": "/api/v1/overview/draft",
            "description": "生成任务概览、计划、验证与恢复上下文",
        },
        {
            "id": "agents",
            "label": "Agents",
            "href": "/api/v1/agents",
            "description": "智能体执行与运行管理",
        },
        {
            "id": "workflows",
            "label": "Workflows",
            "href": "/api/v1/workflows/runs",
            "description": "工作流、时间线、补偿与回放",
        },
        {
            "id": "memory",
            "label": "Memory",
            "href": "/api/v1/memory/search",
            "description": "记忆检索、写入与管理",
        },
        {
            "id": "traces",
            "label": "Traces",
            "href": "/api/v1/traces",
            "description": "追踪、审计与复盘",
        },
    ]
    return {
        "status": "active",
        "service": settings.app_name,
        "mode": settings.app_mode if principal.authenticated and principal.role == "admin" else "production",
        "entrypoint": "/",
        "landing": "/api/v1/workbench",
        "tools": tools,
        "sections": sections,
        "primary_actions": [
            {"id": "create-task", "label": "Create Task", "href": "/api/v1/workbench/tasks"},
            {"id": "health", "label": "Health", "href": "/health"},
            {"id": "ready", "label": "Ready", "href": "/ready"},
        ],
        "notes": [
            "All major capabilities should be reachable from this entry map.",
            "The workbench is the primary operational entry for first-version delivery.",
        ],
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/api-key/status")
async def api_key_status(principal: Principal = Depends(get_current_principal)) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return {"require_api_key": settings.require_api_key, "service": settings.app_name}


@app.get("/ready")
async def ready():
    components: dict[str, str] = {}
    checks = {
        "memory": _check_memory,
        "qdrant": _check_qdrant,
        "trace": _check_trace,
        "runs": _check_runs,
        "workflows": _check_workflows,
        "audit": _check_audit,
        "browser": _check_browser,
        "observability": _check_observability,
    }
    for name, check in checks.items():
        try:
            await check()
            components[name] = "ok"
        except Exception as exc:  # noqa: BLE001 - readiness should report component failures
            components[name] = "failed"
            logger.warning("ready_check_failed", extra={"component": name, "error": str(exc)})
    status = "ready" if all(value == "ok" for value in components.values()) else "degraded"
    return JSONResponse(
        {
            "status": status,
            "service": settings.app_name,
            "components": components,
            "integrations": {
                "qdrant": "real" if vector_client.has_real_client else "fallback",
                "langfuse": "real" if langfuse_client.has_real_client else "fallback",
                "browser": "real" if browser_client.has_real_client else "fallback",
            },
        },
        status_code=200 if status == "ready" else 503,
    )


async def _check_memory() -> None:
    count = get_memory().count()
    if hasattr(count, "__await__"):
        await count
    memory_indexer.index(tenant_id="ready-check", text="ready.memory.check", source="ready")
    results = memory_retriever.search(tenant_id="ready-check", query="ready memory", top_k=1)
    if results is None:
        raise RuntimeError("memory readiness failed")


async def _check_qdrant() -> None:
    names = vector_client.get_collection_names()
    if names is None:
        raise RuntimeError("qdrant readiness failed")
    vector_client.ensure_collection("memory")
    if "memory" not in vector_client.get_collection_names():
        raise RuntimeError("qdrant memory collection missing")


async def _check_trace() -> None:
    get_trace_store().event_count()


async def _check_runs() -> None:
    get_run_store().count()


async def _check_workflows() -> None:
    get_workflow_repository().definition_count()


async def _check_audit() -> None:
    get_audit_store().count()


async def _check_browser() -> None:
    session = browser_automation.create_session(trace_id="ready-check", run_id="ready-check")
    try:
        if browser_automation.get_session(session.session_id) is None:
            raise RuntimeError("browser readiness failed")
    finally:
        browser_automation.close(session.session_id)


async def _check_observability() -> None:
    event = langfuse_client.log("ready.check", service=settings.app_name)
    if event.type != "ready.check":
        raise RuntimeError("observability readiness failed")
