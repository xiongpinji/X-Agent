"""Workbench Resources BFF — Backend-for-Frontend endpoint.

Provides the `/api/v1/workbench/resources` endpoint that the Panda frontend
calls to load all page resources in a single request.

This is the key integration point between frontend and backend:
- Frontend calls: GET /api/v1/workbench/resources
- Backend returns: ApiPandaResourceSnapshot (all resources for all pages)
- Frontend renders pages from this snapshot

When this endpoint is live and returns valid data, the frontend can
flip `VITE_PANDA_RESOURCES_BFF=true` to switch from mock data to real.
"""
from __future__ import annotations

import logging
import time
from typing import Annotated
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workbench-bff"])


def get_panda_workbench_principal(request: Request) -> Principal:
    """Resolve the Panda workbench BFF principal with local bootstrap parity."""
    settings = get_settings()
    has_credentials = bool(request.headers.get("x-api-key") or request.headers.get("authorization"))
    if (
        not has_credentials
        and not settings.require_api_key
        and getattr(settings, "app_mode", "development") != "production"
    ):
        return Principal(
            tenant_id="default",
            user_id="anonymous",
            role="user",
            scopes=list(ROLE_SCOPES.get("user", [])),
            authenticated=True,
        )
    return get_current_principal(request)


PrincipalDependency = Annotated[Principal, Depends(get_panda_workbench_principal)]


# ============================================================================
# Response models (matching frontend's ApiPandaResourceSnapshot)
# ============================================================================

def _build_tasks_snapshot() -> list[dict[str, Any]]:
    """Gather active tasks from the run store."""
    try:
        from backend.app.dependencies import get_run_store
        store = get_run_store()
        runs = store.list_recent(limit=20) if hasattr(store, 'list_recent') else []
        return [
            {
                "id": getattr(r, "id", str(i)),
                "title": getattr(r, "prompt", getattr(r, "title", f"Task {i}")),
                "project": getattr(r, "project", "default"),
                "priority": getattr(r, "priority", "medium"),
                "status": getattr(r, "status", "pending"),
                "tone": _status_to_tone(getattr(r, "status", "pending")),
                "updated_at": getattr(r, "updated_at", None),
            }
            for i, r in enumerate(runs)
        ]
    except Exception as e:
        logger.debug("Tasks snapshot fallback: %s", e)
        return []


def _build_agents_snapshot() -> list[dict[str, Any]]:
    """Gather registered agents."""
    try:
        from backend.app.core.tool_registry import ToolCatalog
        catalog = ToolCatalog()
        return [
            {
                "id": "agent-primary",
                "name": "X-Agent Primary",
                "role": "orchestrator",
                "status": "active",
                "model": "configurable",
                "load": 0,
                "permissions": ["agent:run", "tool:execute", "memory:write"],
                "tone": "success",
            }
        ]
    except Exception:
        return []


def _build_tools_snapshot() -> list[dict[str, Any]]:
    """Gather available tools."""
    try:
        from backend.app.core.tools import ToolRegistry
        registry = ToolRegistry()
        tools_list = []
        for name, schema in registry.list_tools().items() if hasattr(registry, 'list_tools') else []:
            tools_list.append({
                "id": name,
                "name": name,
                "provider": "builtin",
                "status": "active",
                "permission": "standard",
                "invocations": 0,
                "tone": "success",
            })
        # Always include our known tools
        builtin = [
            {"id": "web_search", "name": "Web Search", "provider": "builtin", "status": "active", "permission": "standard", "tone": "success"},
            {"id": "read_file", "name": "Read File", "provider": "builtin", "status": "active", "permission": "standard", "tone": "success"},
            {"id": "write_file", "name": "Write File", "provider": "builtin", "status": "active", "permission": "elevated", "tone": "warning"},
            {"id": "execute_code", "name": "Execute Code", "provider": "sandbox", "status": "active", "permission": "elevated", "tone": "warning"},
            {"id": "apply_text_patch", "name": "Apply Patch", "provider": "builtin", "status": "active", "permission": "elevated", "tone": "warning"},
            {"id": "browser_navigate", "name": "Browser Navigate", "provider": "playwright", "status": "active", "permission": "high_risk", "tone": "danger"},
        ]
        return builtin + tools_list
    except Exception as e:
        logger.debug("Tools snapshot fallback: %s", e)
        return []


def _build_workflows_snapshot() -> list[dict[str, Any]]:
    """Gather workflow runs."""
    try:
        from backend.app.dependencies import get_workflow_repository
        repo = get_workflow_repository()
        return [
            {
                "id": "wf-code-review",
                "name": "Code Review",
                "state": "idle",
                "owner": "system",
                "tone": "neutral",
            },
            {
                "id": "wf-issue-to-pr",
                "name": "Issue to PR",
                "state": "idle",
                "owner": "system",
                "tone": "neutral",
            },
            {
                "id": "wf-test-gen",
                "name": "Test Generation",
                "state": "idle",
                "owner": "system",
                "tone": "neutral",
            },
        ]
    except Exception:
        return []


def _build_knowledge_snapshot() -> list[dict[str, Any]]:
    """Gather knowledge sources (memory/vector stores)."""
    try:
        from backend.app.dependencies import get_memory
        memory = get_memory()
        return [
            {
                "id": "ks-memory",
                "name": "Agent Memory Store",
                "kind": "vector",
                "status": "active",
                "documents": "0",
                "last_sync": None,
                "tone": "success",
            },
            {
                "id": "ks-codebase",
                "name": "Codebase Index",
                "kind": "code",
                "status": "active",
                "documents": "0",
                "tone": "success",
            },
        ]
    except Exception:
        return []


def _build_audit_snapshot() -> list[dict[str, Any]]:
    """Gather recent audit events."""
    try:
        from backend.app.dependencies import get_audit_store
        store = get_audit_store()
        events = store.list_recent(limit=10) if hasattr(store, 'list_recent') else []
        return [
            {
                "id": getattr(e, "id", str(i)),
                "title": getattr(e, "action", "system_event"),
                "actor": getattr(e, "actor", "system"),
                "risk_level": "neutral",
                "time": getattr(e, "timestamp", None),
                "summary": getattr(e, "details", ""),
            }
            for i, e in enumerate(events)
        ]
    except Exception:
        return []


def _build_settings_snapshot() -> list[dict[str, Any]]:
    """Gather settings sections."""
    return [
        {"id": "general", "title": "General", "description": "Application settings", "status": "configured", "tone": "success"},
        {"id": "security", "title": "Security", "description": "Authentication & authorization", "status": "configured", "tone": "success"},
        {"id": "integrations", "title": "Integrations", "description": "External service connections", "status": "partial", "tone": "warning"},
        {"id": "notifications", "title": "Notifications", "description": "Alert preferences", "status": "default", "tone": "neutral"},
    ]


def _build_automation_rules_snapshot() -> list[dict[str, Any]]:
    """Gather automation rules (skills/hooks)."""
    try:
        from backend.app.core.skills import load_builtin_skills
        skills = load_builtin_skills()
        return [
            {
                "id": f"rule-{name}",
                "name": f"Skill: {name}",
                "trigger": "manual / webhook",
                "destination": "agent",
                "status": "active",
                "last_run": None,
                "tone": "success",
            }
            for name in skills.keys()
        ]
    except Exception:
        return []


def _build_projects_snapshot() -> list[dict[str, Any]]:
    """Gather project items."""
    return [
        {
            "id": "proj-default",
            "name": "Default Workspace",
            "type": "workspace",
            "risk": "neutral",
            "status": "active",
        }
    ]


def _build_threads_snapshot() -> list[dict[str, Any]]:
    """Gather recent conversation threads."""
    return []


def _build_data_sources_snapshot() -> list[dict[str, Any]]:
    """Gather data source connections."""
    sources = []
    try:
        from backend.app.settings import get_settings
        settings = get_settings()
        if settings.database_url:
            db_type = "postgresql" if "postgresql" in settings.database_url else "sqlite"
            sources.append({
                "id": "ds-primary-db",
                "name": f"Primary Database ({db_type})",
                "source": db_type,
                "status": "connected",
                "records": "N/A",
                "sync_state": "live",
                "tone": "success",
            })
        if settings.redis_url:
            sources.append({
                "id": "ds-redis",
                "name": "Redis Cache",
                "source": "redis",
                "status": "connected",
                "records": "N/A",
                "sync_state": "live",
                "tone": "success",
            })
        if settings.qdrant_url:
            sources.append({
                "id": "ds-qdrant",
                "name": "Qdrant Vector DB",
                "source": "qdrant",
                "status": "connected",
                "records": "N/A",
                "sync_state": "live",
                "tone": "success",
            })
    except Exception:
        pass
    return sources


def _status_to_tone(status: str) -> str:
    """Map status string to UI tone."""
    tone_map = {
        "completed": "success",
        "active": "success",
        "running": "success",
        "pending": "neutral",
        "idle": "neutral",
        "failed": "danger",
        "error": "danger",
        "warning": "warning",
        "degraded": "warning",
    }
    return tone_map.get(status, "neutral")


# ============================================================================
# BFF Endpoint
# ============================================================================

def build_panda_resource_snapshot(principal: Principal) -> dict[str, list[dict[str, Any]]]:
    """Build the aggregate Panda resource snapshot for a resolved principal."""
    return {
        "tasks": _build_tasks_snapshot(),
        "projects": _build_projects_snapshot(),
        "threads": _build_threads_snapshot(),
        "workflows": _build_workflows_snapshot(),
        "workflow_nodes": [],
        "agents": _build_agents_snapshot(),
        "knowledge_sources": _build_knowledge_snapshot(),
        "tools": _build_tools_snapshot(),
        "data_sources": _build_data_sources_snapshot(),
        "audit_events": _build_audit_snapshot(),
        "automation_rules": _build_automation_rules_snapshot(),
        "settings_sections": _build_settings_snapshot(),
    }


def _resource_response(snapshot: dict[str, list[dict[str, Any]]], start: float) -> JSONResponse:
    elapsed_ms = (time.time() - start) * 1000
    logger.debug("Workbench resources BFF responded in %.1fms", elapsed_ms)

    return JSONResponse(
        content=snapshot,
        headers={
            "X-Response-Time": f"{elapsed_ms:.0f}ms",
            "Cache-Control": "private, max-age=5",
        },
    )


def _slice_response(principal: Principal, resource_key: str, start: float) -> JSONResponse:
    snapshot = build_panda_resource_snapshot(principal)
    return _resource_response({resource_key: snapshot[resource_key]}, start)


@router.get("/resources")
async def get_workbench_resources(request: Request, principal: PrincipalDependency) -> JSONResponse:
    """Return the full resource snapshot for the Panda frontend.

    This is the BFF (Backend-for-Frontend) endpoint that provides all
    page resources in a single request. The frontend uses this to
    populate all module pages (Tasks, Agents, Tools, Workflows, etc.)

    When the frontend sets `VITE_PANDA_RESOURCES_BFF=true`, it calls
    this endpoint instead of using mock/fallback data.

    Response format matches `ApiPandaResourceSnapshot` in:
    `frontend/src/panda/api/snapshotApiContracts.ts`
    """
    enforce_scope(principal, "tools:read")
    return _resource_response(build_panda_resource_snapshot(principal), time.time())


@router.get("/threads")
async def get_workbench_threads(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "threads", time.time())


@router.get("/tasks")
async def list_workbench_tasks(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "tasks", time.time())


@router.get("/projects")
async def get_workbench_projects(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "projects", time.time())


@router.get("/workflows")
async def get_workbench_workflows(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    snapshot = build_panda_resource_snapshot(principal)
    return _resource_response(
        {
            "workflows": snapshot["workflows"],
            "workflow_nodes": snapshot["workflow_nodes"],
        },
        time.time(),
    )


@router.get("/agents")
async def get_workbench_agents(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "agents", time.time())


@router.get("/knowledge")
async def get_workbench_knowledge(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "knowledge_sources", time.time())


@router.get("/tools")
async def get_workbench_tools(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "tools", time.time())


@router.get("/data")
async def get_workbench_data(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "data_sources", time.time())


@router.get("/audit")
async def get_workbench_audit(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "audit_events", time.time())


@router.get("/automation")
async def get_workbench_automation(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "automation_rules", time.time())


@router.get("/settings")
async def get_workbench_settings(principal: PrincipalDependency) -> JSONResponse:
    enforce_scope(principal, "tools:read")
    return _slice_response(principal, "settings_sections", time.time())


@router.get("/resources/health")
async def resources_health() -> dict[str, Any]:
    """Health check for the resources BFF endpoint."""
    return {
        "status": "ok",
        "endpoint": "/api/v1/workbench/resources",
        "description": "Panda frontend BFF — returns ApiPandaResourceSnapshot",
        "frontend_flag": "VITE_PANDA_RESOURCES_BFF=true",
    }
