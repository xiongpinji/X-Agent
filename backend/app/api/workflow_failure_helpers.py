from __future__ import annotations


def build_failure_view(failure_events: list[dict[str, object]]) -> list[dict[str, object]]:
    return failure_events


def build_failure_bucket(failure_chain: list[dict[str, object]]) -> dict[str, object]:
    return {"title": "Failures", "count": len(failure_chain), "items": failure_chain}
