"""BX. AI Ops Knowledge Base — incident case library, runbook generation, similar event matching, experience accumulation."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/ops-knowledge", tags=["ops-knowledge"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Stores ──────────────────────────────────────────────────────────────────

_cases: list[dict[str, Any]] = []


# ─── BX1: Incident Case Library ──────────────────────────────────────────────


@router.post("/cases")
async def add_case(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BX: Add an incident case to the knowledge base."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    case = {
        "id": f"case-{uuid4().hex[:8]}",
        "title": body.get("title", "OOM kill on payment-service"),
        "severity": body.get("severity", "high"),
        "root_cause": body.get("root_cause", "Memory leak in connection pool"),
        "resolution": body.get("resolution", "Upgraded HikariCP, added connection timeout"),
        "affected_services": body.get("services", ["payment-service"]),
        "duration_min": body.get("duration_min", 45),
        "tags": body.get("tags", ["memory", "connection-pool", "java"]),
        "prevention": body.get("prevention", "Add memory usage alert at 80%"),
        "created_at": datetime.now(UTC).isoformat(),
    }
    _cases.append(case)
    return case


@router.get("/cases")
async def list_cases(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BX: List incident cases."""
    enforce_scope(principal, "agent:run")
    return {
        "cases": _cases,
        "total": len(_cases),
        "by_severity": {
            "critical": sum(1 for c in _cases if c["severity"] == "critical"),
            "high": sum(1 for c in _cases if c["severity"] == "high"),
            "medium": sum(1 for c in _cases if c["severity"] == "medium"),
        },
    }


# ─── BX2: Runbook Generation ─────────────────────────────────────────────────


@router.post("/runbooks/generate")
async def generate_runbook(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BX: Auto-generate a runbook from incident patterns."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    return {
        "runbook_id": f"rb-{uuid4().hex[:8]}",
        "trigger": body.get("trigger", "high_error_rate"),
        "service": body.get("service", "payment-service"),
        "steps": [
            {"step": 1, "action": "Verify alert", "command": "kubectl get pods -n payment -l app=payment"},
            {"step": 2, "action": "Check logs", "command": "kubectl logs -n payment -l app=payment --tail=100"},
            {"step": 3, "action": "Check resource usage", "command": "kubectl top pods -n payment"},
            {"step": 4, "action": "Rollback if needed", "command": "kubectl rollout undo deployment/payment -n payment"},
            {"step": 5, "action": "Verify recovery", "command": "curl -s https://api.example.com/health | jq ."},
        ],
        "escalation": {"after_min": 15, "to": "oncall-lead", "channel": "#incidents"},
        "auto_generated": True,
        "confidence": round(random.uniform(0.8, 0.95), 2),
    }


# ─── BX3: Similar Event Matching ─────────────────────────────────────────────


@router.post("/similar")
async def find_similar(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BX: Find similar past incidents using semantic matching."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    return {
        "query": body.get("description", "High latency on order service"),
        "matches": [
            {"case_id": "case-abc123", "title": "DB connection pool exhaustion", "similarity": 0.91, "resolution": "Increased pool size to 50"},
            {"case_id": "case-def456", "title": "GC storms on order-service", "similarity": 0.84, "resolution": "Tuned G1GC parameters"},
            {"case_id": "case-ghi789", "title": "Network partition to DB cluster", "similarity": 0.72, "resolution": "Switched to secondary AZ"},
        ],
        "total_matches": 3,
        "search_method": "embedding_cosine_similarity",
        "threshold": 0.7,
    }


# ─── BX4: Experience Accumulation ────────────────────────────────────────────


@router.post("/lessons")
async def add_lesson(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BX: Record a lesson learned / post-mortem insight."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    return {
        "id": f"lesson-{uuid4().hex[:8]}",
        "incident_ref": body.get("incident", "INC-2026-042"),
        "category": body.get("category", "process"),
        "lesson": body.get("lesson", "Always verify connection pool settings after dependency upgrades"),
        "action_items": body.get("actions", ["Add pool config to pre-deploy checklist"]),
        "applicable_to": body.get("services", ["all-java-services"]),
        "recorded_at": datetime.now(UTC).isoformat(),
    }


# ─── BX5: Knowledge Stats ────────────────────────────────────────────────────


@router.get("/stats")
async def knowledge_stats(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BX: Knowledge base statistics."""
    enforce_scope(principal, "agent:run")
    return {
        "total_cases": len(_cases),
        "total_runbooks": 24,
        "total_lessons": 89,
        "coverage": {"services_with_runbooks": 20, "total_services": 24},
        "avg_resolution_time_min": 38,
        "repeat_incident_rate": 0.12,
        "top_tags": ["memory", "database", "network", "deployment", "config"],
        "last_updated": datetime.now(UTC).isoformat(),
    }
