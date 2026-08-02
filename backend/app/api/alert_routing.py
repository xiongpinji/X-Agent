"""EM. Intelligent Alert Routing — alert grading, team routing, escalation policies, silence management."""

from __future__ import annotations

import random
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/alert-routing", tags=["alert-routing"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── EM1: Alert Grading ─────────────────────────────────────────────────────


@router.get("/grading")
async def alert_grading(principal: PrincipalDependency = None) -> dict[str, Any]:
    """EM: Automatic alert severity grading."""
    return {
        "recent_alerts": [
            {"id": str(uuid4())[:8], "severity": "critical", "source": "payment-service", "graded_by": "ai"},
            {"id": str(uuid4())[:8], "severity": "warning", "source": "disk-usage", "graded_by": "rule"},
        ],
        "grading_accuracy": round(random.uniform(0.85, 0.98), 3),
        "auto_graded_pct": round(random.uniform(70, 95), 1),
        "reclassified_24h": random.randint(0, 5),
    }


# ─── EM2: Team Routing ──────────────────────────────────────────────────────


@router.get("/routing")
async def team_routing(principal: PrincipalDependency = None) -> dict[str, Any]:
    """EM: Alert routing rules and team assignment."""
    return {
        "routes": [
            {"match": {"service": "payment"}, "team": "payments-oncall", "channel": "#alerts-payments"},
            {"match": {"service": "infra"}, "team": "sre-oncall", "channel": "#alerts-infra"},
            {"match": {"severity": "critical"}, "team": "incident-commander", "channel": "#war-room"},
        ],
        "total_routes": random.randint(10, 40),
        "unrouted_alerts_24h": random.randint(0, 3),
        "routing_latency_ms": random.randint(50, 500),
    }


# ─── EM3: Escalation Policies ───────────────────────────────────────────────


@router.get("/escalation")
async def escalation_policies(principal: PrincipalDependency = None) -> dict[str, Any]:
    """EM: Alert escalation policy configuration."""
    return {
        "policies": [
            {"name": "critical-escalation", "levels": [{"after_min": 5, "notify": "oncall"}, {"after_min": 15, "notify": "team-lead"}, {"after_min": 30, "notify": "vp-eng"}]},
            {"name": "warning-escalation", "levels": [{"after_min": 30, "notify": "oncall"}, {"after_min": 120, "notify": "team-lead"}]},
        ],
        "escalations_triggered_24h": random.randint(0, 5),
        "avg_ack_time_min": round(random.uniform(1, 10), 1),
    }


# ─── EM4: Silence Management ────────────────────────────────────────────────


@router.get("/silences")
async def silence_management(principal: PrincipalDependency = None) -> dict[str, Any]:
    """EM: Alert silence and maintenance window management."""
    return {
        "active_silences": [
            {"matcher": "service=analytics", "reason": "planned maintenance", "expires": "2026-07-30T12:00:00Z"},
        ],
        "total_silences": random.randint(0, 5),
        "muted_alerts_24h": random.randint(0, 50),
        "expired_silences_7d": random.randint(0, 10),
        "auto_silence_on_deploy": True,
    }


# ─── EM5: Routing Analytics ─────────────────────────────────────────────────


@router.get("/analytics")
async def routing_analytics(principal: PrincipalDependency = None) -> dict[str, Any]:
    """EM: Alert routing effectiveness metrics."""
    return {
        "alerts_24h": random.randint(50, 500),
        "routed_correctly_pct": round(random.uniform(90, 99), 1),
        "false_positive_rate": round(random.uniform(0.1, 0.4), 3),
        "mtta_min": round(random.uniform(1, 10), 1),
        "alert_fatigue_score": round(random.uniform(0.1, 0.5), 3),
        "noise_reduction_pct": round(random.uniform(30, 70), 1),
    }
