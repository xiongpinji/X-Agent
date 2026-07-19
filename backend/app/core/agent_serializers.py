from __future__ import annotations

from typing import Any

from backend.app.api.recovery_helpers import RecoveryContext
from backend.app.core.contracts import ExecutionFrame, RecoveryFrame, TraceSummary


def serialize_recovery(recovery: RecoveryFrame | RecoveryContext | dict[str, Any] | None) -> dict[str, Any]:
    if recovery is None:
        return {}
    if hasattr(recovery, "to_payload"):
        return recovery.to_payload()  # type: ignore[union-attr]
    if hasattr(recovery, "model_dump"):
        return recovery.model_dump(mode="json")  # type: ignore[union-attr]
    return dict(recovery)


def serialize_snapshot(snapshot: dict[str, Any] | ExecutionFrame | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    if isinstance(snapshot, dict):
        return snapshot
    if hasattr(snapshot, "model_dump"):
        return snapshot.model_dump(mode="json")  # type: ignore[union-attr]
    return {"value": snapshot}


def serialize_summary(summary: dict[str, Any] | TraceSummary | None) -> dict[str, Any]:
    if summary is None:
        return {}
    if isinstance(summary, dict):
        return summary
    if hasattr(summary, "model_dump"):
        return summary.model_dump(mode="json")  # type: ignore[union-attr]
    return {"value": summary}


def serialize_run_view(
    *,
    trace_id: str,
    status: str,
    recovery: RecoveryFrame | RecoveryContext | dict[str, Any] | None = None,
    snapshot: dict[str, Any] | ExecutionFrame | None = None,
    summary: dict[str, Any] | TraceSummary | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "status": status,
        "recovery": serialize_recovery(recovery),
        "snapshot": serialize_snapshot(snapshot),
        "summary": serialize_summary(summary),
        "metadata": metadata or {},
    }


def build_recovery_payload(
    recovery: RecoveryFrame | RecoveryContext | dict[str, Any] | None,
) -> dict[str, Any]:
    return serialize_recovery(recovery)


def build_snapshot_payload(
    snapshot: dict[str, Any] | ExecutionFrame | None,
) -> dict[str, Any]:
    return serialize_snapshot(snapshot)


def build_summary_payload(
    summary: dict[str, Any] | TraceSummary | None,
) -> dict[str, Any]:
    return serialize_summary(summary)
