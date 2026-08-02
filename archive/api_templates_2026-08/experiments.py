"""AB. A/B Experiment Platform — traffic splitting, statistical significance, metric comparison."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Experiment store ────────────────────────────────────────────────────────

_experiments: dict[str, dict[str, Any]] = {}


# ─── Statistical helpers ─────────────────────────────────────────────────────


def _z_test_proportions(n1: int, c1: int, n2: int, c2: int) -> dict[str, Any]:
    """Two-proportion z-test for conversion rates."""
    if n1 == 0 or n2 == 0:
        return {"z_score": 0, "p_value": 1.0, "significant": False}

    p1 = c1 / n1
    p2 = c2 / n2
    p_pool = (c1 + c2) / (n1 + n2)

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)) if p_pool * (1 - p_pool) > 0 else 1e-10
    z = (p1 - p2) / se if se > 0 else 0

    # Approximate p-value (two-tailed) using normal CDF approximation
    p_value = 2 * (1 - _norm_cdf(abs(z)))

    return {
        "z_score": round(z, 4),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
        "confidence_level": "95%",
        "variant_a_rate": round(p1, 4),
        "variant_b_rate": round(p2, 4),
        "relative_improvement": round((p1 - p2) / max(p2, 1e-10) * 100, 2),
    }


def _norm_cdf(x: float) -> float:
    """Approximate standard normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ─── AB1: Create Experiment ──────────────────────────────────────────────────


@router.post("")
async def create_experiment(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AB: Create a new A/B experiment."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    exp_id = str(uuid4())
    experiment = {
        "id": exp_id,
        "name": body.get("name", "Untitled Experiment"),
        "description": body.get("description", ""),
        "status": "draft",
        "hypothesis": body.get("hypothesis", ""),
        "variants": body.get("variants", [
            {"id": "control", "name": "Control", "traffic_pct": 50, "config": {}},
            {"id": "treatment", "name": "Treatment", "traffic_pct": 50, "config": {}},
        ]),
        "target_metric": body.get("target_metric", "conversion_rate"),
        "min_sample_size": body.get("min_sample_size", 100),
        "created_by": principal.user_id,
        "created_at": datetime.now(UTC).isoformat(),
        "started_at": None,
        "ended_at": None,
        "results": None,
    }
    _experiments[exp_id] = experiment
    return {"created": True, "experiment": experiment}


# ─── AB2: Start / Stop Experiment ────────────────────────────────────────────


@router.post("/{experiment_id}/start")
async def start_experiment(experiment_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """AB: Start an experiment (begin traffic splitting)."""
    enforce_scope(principal, "agent:run")

    exp = _experiments.get(experiment_id)
    if not exp:
        return {"error": "Experiment not found"}
    if exp["status"] == "running":
        return {"error": "Experiment already running"}

    exp["status"] = "running"
    exp["started_at"] = datetime.now(UTC).isoformat()
    # Initialize counters
    for v in exp["variants"]:
        v["impressions"] = 0
        v["conversions"] = 0

    return {"started": True, "experiment_id": experiment_id, "status": "running"}


@router.post("/{experiment_id}/stop")
async def stop_experiment(experiment_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """AB: Stop an experiment and compute final results."""
    enforce_scope(principal, "agent:run")

    exp = _experiments.get(experiment_id)
    if not exp:
        return {"error": "Experiment not found"}

    exp["status"] = "completed"
    exp["ended_at"] = datetime.now(UTC).isoformat()

    # Compute results
    variants = exp["variants"]
    if len(variants) >= 2:
        a, b = variants[0], variants[1]
        stats = _z_test_proportions(
            a.get("impressions", 0), a.get("conversions", 0),
            b.get("impressions", 0), b.get("conversions", 0),
        )
        winner = a["id"] if stats["variant_a_rate"] >= stats["variant_b_rate"] else b["id"]
        exp["results"] = {**stats, "winner": winner if stats["significant"] else "inconclusive"}

    return {"stopped": True, "experiment_id": experiment_id, "results": exp.get("results")}


# ─── AB3: Assign Variant (Traffic Split) ─────────────────────────────────────


@router.post("/{experiment_id}/assign")
async def assign_variant(
    experiment_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AB: Assign a user/request to a variant (deterministic bucketing)."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    exp = _experiments.get(experiment_id)
    if not exp:
        return {"error": "Experiment not found"}
    if exp["status"] != "running":
        return {"error": f"Experiment not running (status: {exp['status']})"}

    user_id = body.get("user_id", principal.user_id)

    # Deterministic assignment via hash
    import hashlib
    hash_val = int(hashlib.md5(f"{experiment_id}:{user_id}".encode()).hexdigest(), 16) % 100

    cumulative = 0
    assigned_variant = exp["variants"][-1]["id"]
    for v in exp["variants"]:
        cumulative += v.get("traffic_pct", 50)
        if hash_val < cumulative:
            assigned_variant = v["id"]
            v["impressions"] = v.get("impressions", 0) + 1
            break

    return {
        "experiment_id": experiment_id,
        "user_id": user_id,
        "assigned_variant": assigned_variant,
        "bucket": hash_val,
    }


# ─── AB4: Record Conversion ──────────────────────────────────────────────────


@router.post("/{experiment_id}/convert")
async def record_conversion(
    experiment_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AB: Record a conversion event for a variant."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    exp = _experiments.get(experiment_id)
    if not exp:
        return {"error": "Experiment not found"}

    variant_id = body.get("variant_id", "treatment")
    for v in exp["variants"]:
        if v["id"] == variant_id:
            v["conversions"] = v.get("conversions", 0) + 1
            return {"recorded": True, "variant": variant_id, "total_conversions": v["conversions"]}

    return {"error": f"Variant '{variant_id}' not found"}


# ─── AB5: Experiment Results & Dashboard ─────────────────────────────────────


@router.get("")
async def list_experiments(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AB: List all experiments with status summary."""
    enforce_scope(principal, "agent:run")

    experiments = list(_experiments.values())
    return {
        "experiments": experiments,
        "total": len(experiments),
        "by_status": {
            "draft": sum(1 for e in experiments if e["status"] == "draft"),
            "running": sum(1 for e in experiments if e["status"] == "running"),
            "completed": sum(1 for e in experiments if e["status"] == "completed"),
        },
    }


@router.get("/{experiment_id}/results")
async def get_experiment_results(experiment_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """AB: Get detailed results with statistical analysis."""
    enforce_scope(principal, "agent:run")

    exp = _experiments.get(experiment_id)
    if not exp:
        return {"error": "Experiment not found"}

    variants = exp["variants"]
    variant_stats = []
    for v in variants:
        imp = v.get("impressions", 0)
        conv = v.get("conversions", 0)
        variant_stats.append({
            "id": v["id"],
            "name": v.get("name", v["id"]),
            "impressions": imp,
            "conversions": conv,
            "conversion_rate": round(conv / max(imp, 1) * 100, 2),
            "traffic_pct": v.get("traffic_pct", 50),
        })

    # Statistical test between first two variants
    stats = None
    if len(variants) >= 2:
        a, b = variants[0], variants[1]
        stats = _z_test_proportions(
            a.get("impressions", 0), a.get("conversions", 0),
            b.get("impressions", 0), b.get("conversions", 0),
        )

    total_impressions = sum(v.get("impressions", 0) for v in variants)
    reached_significance = stats["significant"] if stats else False

    return {
        "experiment": {
            "id": exp["id"],
            "name": exp["name"],
            "status": exp["status"],
            "hypothesis": exp.get("hypothesis", ""),
            "target_metric": exp.get("target_metric", ""),
        },
        "variants": variant_stats,
        "statistics": stats,
        "total_impressions": total_impressions,
        "min_sample_reached": total_impressions >= exp.get("min_sample_size", 100),
        "reached_significance": reached_significance,
        "recommendation": "ship_winner" if reached_significance and stats and stats["significant"] else "continue_testing" if not reached_significance else "inconclusive_restart",
    }
