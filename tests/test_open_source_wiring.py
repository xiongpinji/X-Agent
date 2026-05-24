from __future__ import annotations

from backend.app.core.open_source_wiring import build_default_open_source_store


def test_open_source_wiring_builds_store_with_providers() -> None:
    store = build_default_open_source_store()

    assert store is not None
    assert len(store._providers) >= 5
