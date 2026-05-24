from __future__ import annotations


def build_node_bucket(node_results: list[dict[str, object]]) -> dict[str, object]:
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for item in node_results:
        status = str(item.get("status") or "unknown")
        node_type = str(item.get("node_type") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_type[node_type] = by_type.get(node_type, 0) + 1
    summary = {
        "total": len(node_results),
        "by_status": by_status,
        "by_type": by_type,
        "failure_nodes": [item["node_id"] for item in node_results if item.get("error")],
        "ui": {"cards": [{"label": status, "value": count} for status, count in by_status.items()]},
    }
    return {"title": "Nodes", "count": len(node_results), "items": node_results, "summary": summary}
