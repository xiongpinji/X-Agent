from __future__ import annotations

from backend.app.core.open_source_base import OpenSourceCandidateRecord


class ForgejoOpenSourceProvider:
    def __init__(self, name: str = "forgejo") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []


class GiteaOpenSourceProvider:
    def __init__(self, name: str = "gitea") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []


class SavannahOpenSourceProvider:
    def __init__(self, name: str = "savannah") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []
