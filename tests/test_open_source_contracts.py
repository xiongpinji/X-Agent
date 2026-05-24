from __future__ import annotations

from backend.app.core.open_source_api import OpenSourceCandidateRecord, OpenSourceDiscoveryStore, build_default_open_source_store


def test_open_source_api_exports_are_available() -> None:
    assert OpenSourceCandidateRecord is not None
    assert OpenSourceDiscoveryStore is not None
    assert build_default_open_source_store is not None
