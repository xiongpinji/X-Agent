from __future__ import annotations

from backend.app.core.open_source_base import OpenSourceCandidateRecord


class PackageRegistryOpenSourceProvider:
    def __init__(self, name: str = "package-registry") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []


class RubyGemsOpenSourceProvider:
    def __init__(self, name: str = "rubygems") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []
