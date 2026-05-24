from __future__ import annotations

from backend.app.core.open_source_base import OpenSourceCandidateRecord


class SourceHutOpenSourceProvider:
    def __init__(self, name: str = "sourcehut") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []


class BitbucketOpenSourceProvider:
    def __init__(self, name: str = "bitbucket") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []


class GitLabOpenSourceProvider:
    def __init__(self, name: str = "gitlab") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []


class CodebergOpenSourceProvider:
    def __init__(self, name: str = "codeberg") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []
