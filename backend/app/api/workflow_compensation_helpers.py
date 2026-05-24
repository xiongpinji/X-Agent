from __future__ import annotations


def build_compensation_view(compensation_events: list[dict[str, object]]) -> list[dict[str, object]]:
    return compensation_events


def build_compensation_bucket(compensation_chain: list[dict[str, object]]) -> dict[str, object]:
    return {"title": "Compensations", "count": len(compensation_chain), "items": compensation_chain}
