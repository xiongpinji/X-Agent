from __future__ import annotations

from backend.app.core.open_source_api import OpenSourceCandidateRecord, build_default_open_source_store


def test_open_source_end_to_end_search_and_report() -> None:
    store = build_default_open_source_store()
    report = store.build_report("playwright", limit=5)

    assert report.query == "playwright"
    assert report.snapshot["provider_count"] >= 5
    assert report.candidates


def test_open_source_end_to_end_dedupes_by_url() -> None:
    store = build_default_open_source_store()
    report = store.build_report("openai", limit=10)

    urls = [item.url for item in report.candidates if item.url]
    assert len(urls) == len(set(urls))
