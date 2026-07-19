from __future__ import annotations

from backend.app.core.open_source_api import OpenSourceCandidateRecord
from backend.app.core.open_source_wiring import build_default_open_source_store
from backend.app.core.open_source_store import OpenSourceDiscoveryStore


class StubProvider:
    def __init__(self, name: str, items: list[OpenSourceCandidateRecord]) -> None:
        self.name = name
        self._items = items

    def search(self, query: str, limit: int = 10):
        return self._items[:limit]


def test_default_open_source_store_has_many_providers() -> None:
    store = build_default_open_source_store()

    assert isinstance(store, OpenSourceDiscoveryStore)
    assert len(store._providers) >= 5


def test_store_build_report_keeps_unique_candidates() -> None:
    a = OpenSourceCandidateRecord(name="alpha", source="x", url="https://example.com/shared", score=0.9)
    b = OpenSourceCandidateRecord(name="beta", source="y", url="https://example.com/shared", score=0.4)
    c = OpenSourceCandidateRecord(name="gamma", source="z", url="https://example.com/other", score=0.8)
    store = OpenSourceDiscoveryStore(providers=[StubProvider("b", [c]), StubProvider("a", [a, b])])

    report = store.build_report("alpha", limit=10)

    assert len(report.candidates) == 2
    assert report.candidates[0].score >= report.candidates[1].score
