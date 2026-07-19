from __future__ import annotations

from backend.app.core.open_source_api import OpenSourceCandidateRecord, build_default_open_source_store


def test_open_source_package_only_import_path_smoke() -> None:
    store = build_default_open_source_store()
    report = store.build_report("playwright", limit=3)

    assert OpenSourceCandidateRecord is not None
    assert report.query == "playwright"
