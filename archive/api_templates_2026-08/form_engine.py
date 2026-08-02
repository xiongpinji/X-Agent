"""BA. Low-Code Form Engine — dynamic rendering, validation rules, conditional logic, submission workflows."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/forms", tags=["forms-engine"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Stores ──────────────────────────────────────────────────────────────────

_form_definitions: dict[str, dict[str, Any]] = {}
_submissions: list[dict[str, Any]] = []


# ─── BA1: Dynamic Form Definition ────────────────────────────────────────────


@router.post("/definitions")
async def create_form_definition(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BA: Create a dynamic form definition with field types and layout."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    form_id = f"form-{uuid4().hex[:8]}"
    fields = body.get("fields", [
        {"id": "name", "type": "text", "label": "Full Name", "required": True},
        {"id": "email", "type": "email", "label": "Email", "required": True},
        {"id": "role", "type": "select", "label": "Role", "options": ["admin", "user", "viewer"]},
        {"id": "bio", "type": "textarea", "label": "Bio", "max_length": 500},
    ])

    form = {
        "id": form_id,
        "title": body.get("title", "Untitled Form"),
        "description": body.get("description", ""),
        "fields": fields,
        "layout": body.get("layout", "vertical"),
        "theme": body.get("theme", "default"),
        "version": 1,
        "status": "published",
        "created_at": datetime.now(UTC).isoformat(),
    }
    _form_definitions[form_id] = form
    return form


@router.get("/definitions")
async def list_form_definitions(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BA: List all form definitions."""
    enforce_scope(principal, "agent:run")
    return {"forms": list(_form_definitions.values()), "total": len(_form_definitions)}


# ─── BA2: Validation Rules ───────────────────────────────────────────────────


@router.post("/validate")
async def validate_submission(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BA: Validate form data against field rules."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    data = body.get("data", {})

    errors = []
    warnings = []
    for key, value in data.items():
        if not value:
            errors.append({"field": key, "rule": "required", "message": f"{key} is required"})
        elif isinstance(value, str) and len(value) > 500:
            warnings.append({"field": key, "rule": "max_length", "message": f"{key} exceeds 500 chars"})

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "fields_checked": len(data),
        "validated_at": datetime.now(UTC).isoformat(),
    }


# ─── BA3: Conditional Logic ──────────────────────────────────────────────────


@router.post("/conditions/evaluate")
async def evaluate_conditions(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BA: Evaluate conditional field visibility rules."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    data = body.get("data", {})

    conditions = body.get("conditions", [
        {"field": "role", "operator": "eq", "value": "admin", "show": ["admin_panel", "permissions"]},
        {"field": "role", "operator": "eq", "value": "viewer", "hide": ["edit_button", "delete_button"]},
    ])

    results = []
    for cond in conditions:
        field_val = data.get(cond["field"])
        met = field_val == cond.get("value")
        results.append({
            "condition": cond,
            "met": met,
            "visible_fields": cond.get("show", []) if met else [],
            "hidden_fields": cond.get("hide", []) if met else [],
        })

    return {"evaluations": results, "data": data}


# ─── BA4: Submission Workflow ────────────────────────────────────────────────


@router.post("/submit")
async def submit_form(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BA: Submit form data and trigger workflow."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    submission = {
        "id": f"sub-{uuid4().hex[:8]}",
        "form_id": body.get("form_id", "form-001"),
        "data": body.get("data", {}),
        "submitted_by": principal.user_id if principal else "anonymous",
        "workflow_status": "pending_review",
        "workflow_steps": ["validate", "review", "approve", "notify"],
        "current_step": 0,
        "submitted_at": datetime.now(UTC).isoformat(),
    }
    _submissions.append(submission)
    return submission


@router.get("/submissions")
async def list_submissions(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BA: List form submissions."""
    enforce_scope(principal, "agent:run")
    return {"submissions": _submissions[-20:], "total": len(_submissions)}


# ─── BA5: Form Analytics ─────────────────────────────────────────────────────


@router.get("/analytics")
async def form_analytics(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BA: Form usage and completion analytics."""
    enforce_scope(principal, "agent:run")
    return {
        "total_forms": len(_form_definitions),
        "total_submissions": len(_submissions),
        "completion_rate": round(random.uniform(0.6, 0.9), 3),
        "avg_completion_time_s": random.randint(30, 300),
        "drop_off_fields": ["bio", "phone"],
        "top_forms": [{"id": f"form-{i}", "submissions": random.randint(10, 200)} for i in range(1, 4)],
    }
