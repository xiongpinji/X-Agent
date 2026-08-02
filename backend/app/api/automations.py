"""Automations API — Codex-style scheduled background agent runs.

Provides CRUD for automation rules that trigger agent runs on a schedule
(cron expression) or event basis. Each automation stores its run history
and supports enable/disable toggling.

Endpoints:
    POST   /api/v1/automations          — Create automation
    GET    /api/v1/automations          — List automations
    GET    /api/v1/automations/{id}     — Get automation detail
    PATCH  /api/v1/automations/{id}     — Update (enable/disable/edit)
    DELETE /api/v1/automations/{id}     — Delete automation
    POST   /api/v1/automations/{id}/run — Trigger immediate run
    GET    /api/v1/automations/{id}/history — Run history
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/automations", tags=["automations"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── Models ───────────────────────────────────────────────────────────────────


class AutomationCreate(BaseModel):
    """Request body for creating an automation."""

    name: str = Field(..., min_length=1, max_length=200, description="Human-readable name")
    task: str = Field(..., min_length=1, description="Agent task to execute")
    schedule: str = Field(default="0 0 * * *", description="Cron expression (UTC)")
    enabled: bool = True
    max_retries: int = Field(default=1, ge=0, le=5)
    timeout_seconds: int = Field(default=600, ge=60, le=3600)
    extra_context: dict[str, Any] = Field(default_factory=dict)


class AutomationRecord(BaseModel):
    """Stored automation rule."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    task: str
    schedule: str
    enabled: bool = True
    max_retries: int = 1
    timeout_seconds: int = 600
    extra_context: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    run_count: int = 0


class RunHistoryEntry(BaseModel):
    """One execution record."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    automation_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "running"  # running | completed | failed | timeout
    answer: str = ""
    error: str = ""
    trace_id: str | None = None


# ─── In-memory store ──────────────────────────────────────────────────────────

_automations: dict[str, AutomationRecord] = {}
_history: dict[str, list[RunHistoryEntry]] = {}  # automation_id -> entries


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_automation(body: AutomationCreate, principal: PrincipalDependency) -> dict[str, Any]:
    """Create a new automation rule."""
    enforce_scope(principal, "agent:run")
    record = AutomationRecord(
        name=body.name,
        task=body.task,
        schedule=body.schedule,
        enabled=body.enabled,
        max_retries=body.max_retries,
        timeout_seconds=body.timeout_seconds,
        extra_context=body.extra_context,
        tenant_id=principal.tenant_id,
        created_by=principal.user_id,
    )
    _automations[record.id] = record
    _history[record.id] = []
    return record.model_dump(mode="json")


@router.get("")
async def list_automations(principal: PrincipalDependency) -> dict[str, Any]:
    """List all automations for the current tenant."""
    enforce_scope(principal, "agent:read")
    items = [
        a.model_dump(mode="json")
        for a in _automations.values()
        if a.tenant_id == principal.tenant_id
    ]
    return {"data": items, "total": len(items)}


@router.get("/{automation_id}")
async def get_automation(automation_id: str, principal: PrincipalDependency) -> dict[str, Any]:
    """Get automation detail."""
    enforce_scope(principal, "agent:read")
    record = _automations.get(automation_id)
    if not record or record.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Automation not found")
    return record.model_dump(mode="json")


@router.patch("/{automation_id}")
async def update_automation(automation_id: str, body: dict[str, Any], principal: PrincipalDependency) -> dict[str, Any]:
    """Update automation (enable/disable, edit schedule/task)."""
    enforce_scope(principal, "agent:run")
    record = _automations.get(automation_id)
    if not record or record.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Automation not found")

    for field in ("name", "task", "schedule", "enabled", "max_retries", "timeout_seconds", "extra_context"):
        if field in body:
            setattr(record, field, body[field])
    record.updated_at = datetime.now(UTC)
    return record.model_dump(mode="json")


@router.delete("/{automation_id}", status_code=204)
async def delete_automation(automation_id: str, principal: PrincipalDependency) -> None:
    """Delete an automation."""
    enforce_scope(principal, "agent:run")
    record = _automations.get(automation_id)
    if not record or record.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Automation not found")
    del _automations[automation_id]
    _history.pop(automation_id, None)


@router.post("/{automation_id}/run")
async def trigger_automation_run(automation_id: str, principal: PrincipalDependency) -> dict[str, Any]:
    """Trigger an immediate run of the automation (manual or CI/CD trigger)."""
    enforce_scope(principal, "agent:run")
    record = _automations.get(automation_id)
    if not record or record.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Automation not found")

    entry = RunHistoryEntry(automation_id=automation_id)
    _history.setdefault(automation_id, []).append(entry)

    # Execute agent in background
    async def _execute():
        try:
            from backend.app.core.agent.loop import AgentLoop
            from backend.app.core.contracts import RunContext
            from backend.app.dependencies import get_agent

            agent = get_agent()
            context = RunContext(
                tenant_id=record.tenant_id,
                user_id=record.created_by,
                permission_scope=["tools:*", "memory:*"],
            )
            result = await asyncio.wait_for(
                agent.run(context, record.task, record.extra_context),
                timeout=record.timeout_seconds,
            )
            entry.status = "completed"
            entry.answer = (result.answer or "")[:2000]
            entry.trace_id = result.trace_id
            record.last_run_status = "completed"
        except asyncio.TimeoutError:
            entry.status = "timeout"
            entry.error = f"Timed out after {record.timeout_seconds}s"
            record.last_run_status = "timeout"
        except Exception as exc:
            entry.status = "failed"
            entry.error = str(exc)[:500]
            record.last_run_status = "failed"
        finally:
            entry.completed_at = datetime.now(UTC)
            record.last_run_at = entry.started_at
            record.run_count += 1

    asyncio.create_task(_execute())

    return {"run_id": entry.id, "status": "running", "automation_id": automation_id}


@router.get("/{automation_id}/history")
async def get_automation_history(automation_id: str, principal: PrincipalDependency, limit: int = 20) -> dict[str, Any]:
    """Get run history for an automation."""
    enforce_scope(principal, "agent:read")
    record = _automations.get(automation_id)
    if not record or record.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Automation not found")

    entries = _history.get(automation_id, [])[-limit:]
    return {
        "automation_id": automation_id,
        "entries": [e.model_dump(mode="json") for e in reversed(entries)],
        "total_runs": record.run_count,
    }
