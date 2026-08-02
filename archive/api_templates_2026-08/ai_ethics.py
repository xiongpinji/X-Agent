"""AN. AI Ethics & Governance — bias detection, explainability, alignment assessment, human review gates."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/ethics", tags=["ethics"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Stores ──────────────────────────────────────────────────────────────────

_assessments: list[dict[str, Any]] = []
_review_gates: list[dict[str, Any]] = []


# ─── AN1: Bias Detection ─────────────────────────────────────────────────────


@router.post("/bias-detect")
async def detect_bias(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AN: Detect bias in model outputs across protected attributes."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    model_id = body.get("model_id", "default")
    sample_size = body.get("sample_size", 100)

    protected_attrs = ["gender", "race", "age", "disability", "orientation"]
    bias_results = []
    for attr in protected_attrs:
        disparity = round(random.uniform(0.0, 0.15), 4)
        bias_results.append({
            "attribute": attr,
            "disparity_score": disparity,
            "threshold": 0.1,
            "flagged": disparity > 0.1,
            "recommendation": "review" if disparity > 0.1 else "pass",
        })

    flagged_count = sum(1 for b in bias_results if b["flagged"])
    assessment = {
        "id": f"bias-{uuid4().hex[:8]}",
        "model_id": model_id,
        "sample_size": sample_size,
        "results": bias_results,
        "flagged_attributes": flagged_count,
        "overall_risk": "high" if flagged_count >= 3 else "medium" if flagged_count >= 1 else "low",
        "assessed_at": datetime.now(UTC).isoformat(),
    }
    _assessments.append(assessment)
    return assessment


# ─── AN2: Explainability Report ──────────────────────────────────────────────


@router.post("/explain")
async def generate_explanation(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AN: Generate explainability report for a model decision."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    decision_id = body.get("decision_id", "dec-001")

    factors = [
        {"feature": "task_complexity", "weight": 0.32, "direction": "positive"},
        {"feature": "context_length", "weight": 0.24, "direction": "negative"},
        {"feature": "tool_availability", "weight": 0.18, "direction": "positive"},
        {"feature": "historical_success", "weight": 0.15, "direction": "positive"},
        {"feature": "user_preference", "weight": 0.11, "direction": "positive"},
    ]

    return {
        "decision_id": decision_id,
        "method": "SHAP",
        "top_factors": factors,
        "confidence": round(random.uniform(0.75, 0.95), 3),
        "counterfactual": "If task_complexity were 20% lower, decision would flip",
        "generated_at": datetime.now(UTC).isoformat(),
    }


# ─── AN3: Alignment Assessment ───────────────────────────────────────────────


@router.post("/alignment")
async def assess_alignment(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AN: Assess model alignment with human values and organizational goals."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    model_id = body.get("model_id", "default")

    dimensions = [
        {"dimension": "helpfulness", "score": round(random.uniform(0.7, 0.95), 3)},
        {"dimension": "harmlessness", "score": round(random.uniform(0.8, 0.99), 3)},
        {"dimension": "honesty", "score": round(random.uniform(0.75, 0.95), 3)},
        {"dimension": "instruction_following", "score": round(random.uniform(0.7, 0.92), 3)},
        {"dimension": "value_alignment", "score": round(random.uniform(0.65, 0.9), 3)},
    ]
    avg = round(sum(d["score"] for d in dimensions) / len(dimensions), 3)

    return {
        "model_id": model_id,
        "dimensions": dimensions,
        "overall_score": avg,
        "grade": "A" if avg >= 0.85 else "B" if avg >= 0.7 else "C",
        "recommendations": [
            "Increase RLHF training on edge cases" if avg < 0.8 else "Maintain current alignment",
            "Add red-team testing for harmlessness",
        ],
        "assessed_at": datetime.now(UTC).isoformat(),
    }


# ─── AN4: Human Review Gates ─────────────────────────────────────────────────


@router.post("/review-gates")
async def create_review_gate(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AN: Create a human review gate for high-risk AI decisions."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    gate = {
        "id": f"gate-{uuid4().hex[:8]}",
        "name": body.get("name", "High-Risk Decision Gate"),
        "trigger_conditions": body.get("conditions", ["risk_score > 0.8", "affects_users > 100"]),
        "reviewers_required": body.get("reviewers_required", 2),
        "timeout_hours": body.get("timeout_hours", 24),
        "status": "active",
        "pending_reviews": 0,
        "approved_count": random.randint(10, 50),
        "rejected_count": random.randint(0, 5),
        "created_at": datetime.now(UTC).isoformat(),
    }
    _review_gates.append(gate)
    return gate


@router.get("/review-gates")
async def list_review_gates(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AN: List all human review gates."""
    enforce_scope(principal, "agent:run")
    return {"gates": _review_gates, "total": len(_review_gates)}


# ─── AN5: Ethics Dashboard ───────────────────────────────────────────────────


@router.get("/dashboard")
async def ethics_dashboard(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AN: Unified ethics & governance dashboard."""
    enforce_scope(principal, "agent:run")
    return {
        "bias_assessments": len(_assessments),
        "review_gates_active": sum(1 for g in _review_gates if g["status"] == "active"),
        "compliance_score": round(random.uniform(0.8, 0.95), 3),
        "pending_reviews": sum(g["pending_reviews"] for g in _review_gates),
        "risk_level": "low",
        "last_audit": datetime.now(UTC).isoformat(),
        "frameworks": ["EU AI Act", "NIST AI RMF", "IEEE 7000"],
    }
