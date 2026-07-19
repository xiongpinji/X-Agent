from __future__ import annotations

from backend.app.core.open_source_api import OpenSourceCandidateRecord
from backend.app.core.open_source_forge_providers import BitbucketOpenSourceProvider, CodebergOpenSourceProvider, GiteaOpenSourceProvider, GitLabOpenSourceProvider
from backend.app.core.open_source_registry import CratesIoOpenSourceProvider, MavenCentralOpenSourceProvider, NpmRegistryOpenSourceProvider, PackageRegistryOpenSourceProvider, RubyGemsOpenSourceProvider
from backend.app.core.open_source_store import OpenSourceDiscoveryStore


class StubProvider:
    def __init__(self, name: str, items: list[OpenSourceCandidateRecord]) -> None:
        self.name = name
        self._items = items

    def search(self, query: str, limit: int = 10):
        return self._items[:limit]


def test_registry_provider_names_exist() -> None:
    providers = [PackageRegistryOpenSourceProvider(), NpmRegistryOpenSourceProvider(), MavenCentralOpenSourceProvider(), CratesIoOpenSourceProvider(), RubyGemsOpenSourceProvider()]
    assert all(provider.name for provider in providers)


def test_forge_provider_names_exist() -> None:
    providers = [BitbucketOpenSourceProvider(), GitLabOpenSourceProvider(), GiteaOpenSourceProvider(), CodebergOpenSourceProvider()]
    assert all(provider.name for provider in providers)


def test_store_dedupes_by_url_and_sorts_by_score() -> None:
    a = OpenSourceCandidateRecord(name="alpha", source="x", url="https://example.com/shared", score=0.9)
    b = OpenSourceCandidateRecord(name="beta", source="y", url="https://example.com/shared", score=0.4)
    c = OpenSourceCandidateRecord(name="gamma", source="z", url="https://example.com/other", score=0.8)
    store = OpenSourceDiscoveryStore(providers=[StubProvider("b", [c]), StubProvider("a", [a, b])])

    report = store.build_report("alpha", limit=10)

    assert [item.url for item in report.candidates] == ["https://example.com/shared", "https://example.com/other"]
    assert report.candidates[0].score >= report.candidates[1].score
