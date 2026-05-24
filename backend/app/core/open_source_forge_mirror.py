from __future__ import annotations

from backend.app.core.open_source_base import OpenSourceCandidateRecord


class SourceForgeOpenSourceProvider:
    def __init__(self, name: str = "sourceforge") -> None:
        self.name = name

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        return []
