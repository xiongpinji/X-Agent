from __future__ import annotations


def build_timeline_sections(timeline: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{"title": "Run", "events": timeline}]


def build_run_timeline(run) -> list[dict[str, object]]:
    timeline = [{"kind": "run.started", "timestamp": run.started_at.isoformat(), "workflow_id": run.workflow_id}]
    for result in run.node_results:
        timeline.append({"kind": "node.started", "timestamp": result.started_at.isoformat(), "node_id": result.node_id, "node_type": result.node_type.value, "status": result.status.value})
        event_kind = "node.completed" if result.status == result.status.COMPLETED else "node.compensated" if result.compensated else "node.failed"
        timeline.append({"kind": event_kind, "timestamp": result.completed_at.isoformat(), "node_id": result.node_id, "node_type": result.node_type.value, "status": result.status.value, "attempts": result.attempts, "agent_trace_id": result.agent_trace_id, "compensated": result.compensated, "error": result.error, "compensation_error": result.compensation_error, "compensation_output": result.compensation_output})
    timeline.append({"kind": "run.completed", "timestamp": run.completed_at.isoformat(), "workflow_id": run.workflow_id, "status": run.status.value})
    return timeline
