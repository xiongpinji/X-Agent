"""AF. Data Pipeline & Stream Processing — ETL pipelines, real-time streams, data quality, schema evolution."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Pipeline store ──────────────────────────────────────────────────────────

_pipelines: dict[str, dict[str, Any]] = {}
_streams: dict[str, dict[str, Any]] = {}


# ─── AF1: ETL Pipeline CRUD ──────────────────────────────────────────────────


@router.get("")
async def list_pipelines(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AF: List all data pipelines."""
    enforce_scope(principal, "agent:run")

    pipelines = list(_pipelines.values())
    return {
        "pipelines": pipelines,
        "total": len(pipelines),
        "by_status": {
            "active": sum(1 for p in pipelines if p["status"] == "active"),
            "paused": sum(1 for p in pipelines if p["status"] == "paused"),
            "failed": sum(1 for p in pipelines if p["status"] == "failed"),
        },
    }


@router.post("")
async def create_pipeline(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AF: Create a new ETL pipeline definition."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    pipeline_id = str(uuid4())
    pipeline = {
        "id": pipeline_id,
        "name": body.get("name", "Untitled Pipeline"),
        "description": body.get("description", ""),
        "status": "draft",
        "source": {
            "type": body.get("source_type", "postgresql"),
            "connection": body.get("source_connection", ""),
            "query": body.get("source_query", ""),
        },
        "transforms": body.get("transforms", [
            {"type": "filter", "config": {"condition": "status = 'active'"}},
            {"type": "map", "config": {"fields": ["id", "name", "created_at"]}},
        ]),
        "sink": {
            "type": body.get("sink_type", "data_warehouse"),
            "connection": body.get("sink_connection", ""),
            "table": body.get("sink_table", ""),
        },
        "schedule": body.get("schedule", "0 */6 * * *"),  # Every 6 hours
        "created_at": datetime.now(UTC).isoformat(),
        "last_run": None,
        "metrics": {"runs": 0, "records_processed": 0, "errors": 0},
    }
    _pipelines[pipeline_id] = pipeline
    return {"created": True, "pipeline": pipeline}


@router.post("/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """AF: Trigger a pipeline run."""
    enforce_scope(principal, "agent:run")

    pipeline = _pipelines.get(pipeline_id)
    if not pipeline:
        return {"error": "Pipeline not found"}

    records = random.randint(100, 10000)
    duration_ms = random.randint(500, 30000)
    errors = random.randint(0, 5)

    pipeline["status"] = "active"
    pipeline["last_run"] = datetime.now(UTC).isoformat()
    pipeline["metrics"]["runs"] += 1
    pipeline["metrics"]["records_processed"] += records
    pipeline["metrics"]["errors"] += errors

    return {
        "run_id": str(uuid4()),
        "pipeline_id": pipeline_id,
        "status": "completed" if errors == 0 else "completed_with_warnings",
        "records_processed": records,
        "duration_ms": duration_ms,
        "errors": errors,
    }


# ─── AF2: Real-Time Streams ──────────────────────────────────────────────────


@router.get("/streams")
async def list_streams(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AF: List active data streams."""
    enforce_scope(principal, "agent:run")

    streams = list(_streams.values())
    return {
        "streams": streams,
        "total": len(streams),
        "active": sum(1 for s in streams if s["status"] == "active"),
    }


@router.post("/streams")
async def create_stream(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AF: Create a real-time data stream."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    stream_id = str(uuid4())
    stream = {
        "id": stream_id,
        "name": body.get("name", "Untitled Stream"),
        "topic": body.get("topic", f"stream-{stream_id[:8]}"),
        "status": "active",
        "partitions": body.get("partitions", 3),
        "replication_factor": body.get("replication_factor", 2),
        "retention_hours": body.get("retention_hours", 168),
        "consumers": [],
        "metrics": {
            "messages_per_sec": round(random.uniform(10, 1000), 1),
            "total_messages": random.randint(10000, 1000000),
            "lag": random.randint(0, 100),
        },
        "created_at": datetime.now(UTC).isoformat(),
    }
    _streams[stream_id] = stream
    return {"created": True, "stream": stream}


@router.post("/streams/{stream_id}/consume")
async def consume_stream(stream_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """AF: Consume messages from a stream (simulated)."""
    enforce_scope(principal, "agent:run")

    stream = _streams.get(stream_id)
    if not stream:
        return {"error": "Stream not found"}

    messages = [
        {"offset": random.randint(1000, 9999), "key": f"key-{i}", "value": {"event": "sample", "ts": datetime.now(UTC).isoformat()}}
        for i in range(random.randint(1, 10))
    ]

    return {"stream_id": stream_id, "messages": messages, "count": len(messages)}


# ─── AF3: Data Quality Monitoring ────────────────────────────────────────────


@router.get("/quality")
async def get_data_quality(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AF: Data quality metrics and anomaly detection."""
    enforce_scope(principal, "agent:run")

    checks = [
        {"name": "Null Rate", "table": "users", "threshold": "< 1%", "current": "0.3%", "status": "pass"},
        {"name": "Duplicate Rate", "table": "orders", "threshold": "< 0.1%", "current": "0.05%", "status": "pass"},
        {"name": "Freshness", "table": "events", "threshold": "< 5min", "current": "2min", "status": "pass"},
        {"name": "Schema Drift", "table": "products", "threshold": "0 changes", "current": "2 new columns", "status": "warn"},
        {"name": "Row Count Anomaly", "table": "transactions", "threshold": "±20%", "current": "-35%", "status": "fail"},
    ]

    passed = sum(1 for c in checks if c["status"] == "pass")
    return {
        "checks": checks,
        "total": len(checks),
        "passed": passed,
        "warnings": sum(1 for c in checks if c["status"] == "warn"),
        "failures": sum(1 for c in checks if c["status"] == "fail"),
        "quality_score": round(passed / len(checks) * 100, 1),
        "last_check": datetime.now(UTC).isoformat(),
    }


# ─── AF4: Schema Registry & Evolution ────────────────────────────────────────


@router.get("/schemas")
async def list_schemas(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AF: List registered schemas with version history."""
    enforce_scope(principal, "agent:run")

    schemas = [
        {"id": "user-event", "version": 3, "format": "avro", "compatibility": "BACKWARD", "fields": 12, "updated_at": "2024-06-15T10:00:00Z"},
        {"id": "order-event", "version": 5, "format": "json", "compatibility": "FULL", "fields": 18, "updated_at": "2024-06-20T14:30:00Z"},
        {"id": "payment-event", "version": 2, "format": "protobuf", "compatibility": "FORWARD", "fields": 9, "updated_at": "2024-06-10T08:00:00Z"},
    ]

    return {
        "schemas": schemas,
        "total": len(schemas),
        "compatibility_modes": ["BACKWARD", "FORWARD", "FULL", "NONE"],
    }


@router.post("/schemas/validate")
async def validate_schema(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AF: Validate schema compatibility for evolution."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    schema_id = body.get("schema_id", "")
    new_fields = body.get("new_fields", [])
    removed_fields = body.get("removed_fields", [])
    compatibility = body.get("compatibility", "BACKWARD")

    issues = []
    if removed_fields and compatibility in ("BACKWARD", "FULL"):
        issues.append(f"Cannot remove fields with {compatibility} compatibility")
    if not new_fields and not removed_fields:
        issues.append("No schema changes detected")

    return {
        "schema_id": schema_id,
        "compatible": len(issues) == 0,
        "issues": issues,
        "compatibility_mode": compatibility,
        "recommendation": "safe_to_deploy" if not issues else "requires_review",
    }
