from __future__ import annotations


def build_timeline_bucket(timeline: list[dict[str, object]]) -> dict[str, object]:
    return {"title": "Timeline", "count": len(timeline), "items": timeline}
