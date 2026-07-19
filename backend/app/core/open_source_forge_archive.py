from __future__ import annotations

from backend.app.core.open_source_base import OpenSourceCandidateRecord


class LaunchpadOpenSourceProvider:
    def __init__(self, name: str = "launchpad") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []


class FossilOpenSourceProvider:
    def __init__(self, name: str = "fossil") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []
