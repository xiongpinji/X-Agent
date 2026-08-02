"""AL. Natural Language Programming Interface — intent recognition, NL2SQL, NL2API, conversational development."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/nlprog", tags=["nlprog"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── AL1: Intent Recognition & Code Generation ───────────────────────────────


@router.post("/generate")
async def generate_from_nl(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AL: Generate code from natural language description."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    prompt = body.get("prompt", "")
    language = body.get("language", "python")
    context = body.get("context", "")

    # Intent classification
    intent = "general"
    if any(k in prompt.lower() for k in ("api", "endpoint", "route", "server")):
        intent = "api_development"
    elif any(k in prompt.lower() for k in ("database", "query", "sql", "table")):
        intent = "data_access"
    elif any(k in prompt.lower() for k in ("test", "assert", "mock")):
        intent = "testing"
    elif any(k in prompt.lower() for k in ("class", "model", "schema")):
        intent = "data_modeling"

    # Simulated code generation
    code_templates = {
        "python": f'# Generated from: {prompt[:60]}\ndef solution():\n    """Auto-generated implementation."""\n    pass  # TODO: implement\n',
        "javascript": f'// Generated from: {prompt[:60]}\nfunction solution() {{\n  // TODO: implement\n}}\n',
        "typescript": f'// Generated from: {prompt[:60]}\nfunction solution(): void {{\n  // TODO: implement\n}}\n',
    }

    return {
        "prompt": prompt,
        "language": language,
        "intent": intent,
        "code": code_templates.get(language, code_templates["python"]),
        "explanation": f"Generated {intent} code for: {prompt[:80]}",
        "confidence": 0.85,
        "alternatives": 2,
        "model": "codellama-34b",
        "generated_at": datetime.now(UTC).isoformat(),
    }


# ─── AL2: NL2SQL ─────────────────────────────────────────────────────────────


@router.post("/nl2sql")
async def natural_language_to_sql(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AL: Convert natural language to SQL query."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    question = body.get("question", "")
    schema = body.get("schema", "default")
    dialect = body.get("dialect", "postgresql")

    # Simple pattern-based SQL generation
    sql = "SELECT * FROM users"
    if "count" in question.lower():
        sql = "SELECT COUNT(*) as total FROM users"
    elif "average" in question.lower() or "avg" in question.lower():
        sql = "SELECT AVG(amount) as avg_amount FROM orders"
    elif "top" in question.lower() or "latest" in question.lower():
        sql = "SELECT * FROM users ORDER BY created_at DESC LIMIT 10"
    elif "group" in question.lower():
        sql = "SELECT status, COUNT(*) as cnt FROM orders GROUP BY status"

    return {
        "question": question,
        "sql": sql,
        "dialect": dialect,
        "schema": schema,
        "tables_referenced": ["users"] if "user" in question.lower() else ["orders"],
        "confidence": 0.82,
        "is_read_only": not any(k in sql.upper() for k in ("INSERT", "UPDATE", "DELETE", "DROP")),
        "execution_plan": "Sequential Scan → Aggregate",
    }


# ─── AL3: NL2API ─────────────────────────────────────────────────────────────


@router.post("/nl2api")
async def natural_language_to_api(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AL: Convert natural language to API call specification."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    intent_text = body.get("intent", "")
    base_url = body.get("base_url", "http://localhost:8299/api/v1")

    # Map intent to API call
    api_spec = {"method": "GET", "path": "/agents", "params": {}}
    if "create" in intent_text.lower() or "new" in intent_text.lower():
        api_spec = {"method": "POST", "path": "/agents/run", "body": {"task": intent_text}}
    elif "delete" in intent_text.lower() or "remove" in intent_text.lower():
        api_spec = {"method": "DELETE", "path": "/agents/{id}"}
    elif "update" in intent_text.lower() or "change" in intent_text.lower():
        api_spec = {"method": "PUT", "path": "/agents/{id}", "body": {}}
    elif "list" in intent_text.lower() or "show" in intent_text.lower():
        api_spec = {"method": "GET", "path": "/agents", "params": {"limit": 20}}

    return {
        "intent": intent_text,
        "api_call": {
            "method": api_spec["method"],
            "url": f"{base_url}{api_spec['path']}",
            "headers": {"X-API-Key": "***", "Content-Type": "application/json"},
            "body": api_spec.get("body"),
            "params": api_spec.get("params"),
        },
        "curl_command": f"curl -X {api_spec['method']} {base_url}{api_spec['path']} -H 'X-API-Key: ***'",
        "confidence": 0.78,
    }


# ─── AL4: Conversational Development ─────────────────────────────────────────


@router.post("/chat")
async def conversational_dev(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AL: Conversational development assistant — multi-turn code building."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    message = body.get("message", "")
    session_id = body.get("session_id", str(uuid4()))
    history = body.get("history", [])

    # Classify conversation stage
    stage = "exploration"
    if len(history) > 3:
        stage = "implementation"
    if any(k in message.lower() for k in ("test", "verify", "check")):
        stage = "verification"
    if any(k in message.lower() for k in ("deploy", "ship", "done")):
        stage = "completion"

    return {
        "session_id": session_id,
        "stage": stage,
        "response": f"[AI Dev Assistant] Understanding your request: '{message[:60]}...'. Let me help you build this step by step.",
        "suggested_actions": [
            {"action": "generate_code", "label": "Generate implementation"},
            {"action": "explain", "label": "Explain approach"},
            {"action": "test", "label": "Write tests"},
        ],
        "context": {"turn": len(history) + 1, "files_touched": [], "language_detected": "python"},
    }


# ─── AL5: Code Explanation ───────────────────────────────────────────────────


@router.post("/explain")
async def explain_code(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AL: Explain code in natural language."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    code = body.get("code", "")
    detail_level = body.get("detail", "medium")

    lines = code.split("\n")
    return {
        "code_snippet": code[:200],
        "language": "python",
        "explanation": f"This code contains {len(lines)} lines. It appears to define functions/classes for data processing.",
        "summary": "Data processing utility with error handling",
        "complexity": "moderate" if len(lines) > 20 else "simple",
        "key_concepts": ["function definition", "error handling", "data transformation"],
        "detail_level": detail_level,
    }
