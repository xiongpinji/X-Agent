from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class OpenSourceStatus(str):
    CANDIDATE = "candidate"
    SHORTLISTED = "shortlisted"
    ADOPTED = "adopted"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class OpenSourceCandidateRecord(BaseModel):
    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    source: str = "github"
    url: str = ""
    license: str = ""
    summary: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = OpenSourceStatus.CANDIDATE
    reasons: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OpenSourceDiscoveryReport(BaseModel):
    query: str
    candidates: list[OpenSourceCandidateRecord] = Field(default_factory=list)
    shortlist: list[OpenSourceCandidateRecord] = Field(default_factory=list)
    blocked: list[OpenSourceCandidateRecord] = Field(default_factory=list)
    snapshot: dict[str, object] = Field(default_factory=dict)


class OpenSourceProvider(Protocol):
    name: str

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        ...


class StaticOpenSourceProvider:
    def __init__(self, name: str, records: list[OpenSourceCandidateRecord]) -> None:
        self.name = name
        self._records = records

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        q = query.lower().strip()
        matched = [item for item in self._records if q in item.name.lower() or q in item.summary.lower() or any(q in tag.lower() for tag in item.tags) or any(q in reason.lower() for reason in item.reasons)]
        if not matched:
            matched = list(self._records)
        return [item.model_copy(update={"source": item.source or self.name, "metadata": {**dict(item.metadata), "provider": self.name, "provider_kind": "static"}, "updated_at": datetime.now(UTC)}) for item in matched[:limit]]


class OpenSourceDiscoveryStore:
    def __init__(self, providers: list[OpenSourceProvider] | None = None) -> None:
        self._records: dict[str, OpenSourceCandidateRecord] = {}
        self._lock = RLock()
        self._providers = providers or []

    def register_provider(self, provider: OpenSourceProvider) -> None:
        self._providers.append(provider)

    def add_candidate(self, candidate: OpenSourceCandidateRecord) -> OpenSourceCandidateRecord:
        with self._lock:
            self._records[candidate.candidate_id] = candidate
        return candidate

    def list_candidates(self, limit: int = 100) -> list[OpenSourceCandidateRecord]:
        items = list(self._records.values())
        items.sort(key=lambda item: (item.score, item.updated_at, item.name.lower()), reverse=True)
        return items[:limit]

    def get_candidate(self, candidate_id: str) -> OpenSourceCandidateRecord | None:
        return self._records.get(candidate_id)

    def discover(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        candidates: list[OpenSourceCandidateRecord] = []
        seen: set[str] = set()
        for provider in sorted(self._providers, key=lambda item: getattr(item, "name", item.__class__.__name__).lower()):
            for candidate in provider.search(query, limit=limit):
                key = candidate.url or f"{candidate.source}:{candidate.name}"
                if key in seen:
                    continue
                seen.add(key)
                stored = self.add_candidate(candidate.model_copy(update={"metadata": {**dict(candidate.metadata), "last_discovered_at": datetime.now(UTC).isoformat()}, "updated_at": datetime.now(UTC)}))
                candidates.append(stored)
                if len(candidates) >= limit:
                    break
            if len(candidates) >= limit:
                break
        if not candidates:
            candidates = self.list_candidates(limit=limit)
        candidates.sort(key=lambda item: (item.score, item.updated_at, item.name.lower()), reverse=True)
        return candidates[:limit]

    def refresh_provider(self, provider_name: str) -> int:
        refreshed = 0
        for candidate in list(self._records.values()):
            if candidate.source != provider_name and candidate.metadata.get("provider") != provider_name:
                continue
            updated = candidate.model_copy(update={"metadata": {**dict(candidate.metadata), "refreshed_at": datetime.now(UTC).isoformat()}, "updated_at": datetime.now(UTC)})
            self._records[candidate.candidate_id] = updated
            refreshed += 1
        return refreshed

    def summarize_candidate(self, candidate: OpenSourceCandidateRecord) -> dict[str, object]:
        metadata = dict(candidate.metadata)
        return {"candidate_id": candidate.candidate_id, "name": candidate.name, "source": candidate.source, "url": candidate.url, "license": candidate.license, "score": candidate.score, "status": candidate.status, "summary": candidate.summary, "metadata": metadata, "risk_flags": [flag for flag in ["archived" if metadata.get("archived") else None, "low_score" if candidate.score < 0.6 else None, "missing_license" if not candidate.license else None] if flag is not None]}

    def build_candidate_details(self, candidate_id: str) -> dict[str, object] | None:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            return None
        return {**self.summarize_candidate(candidate), "reasons": candidate.reasons, "tags": candidate.tags, "created_at": candidate.created_at.isoformat(), "updated_at": candidate.updated_at.isoformat()}

    def build_report(self, query: str, limit: int = 10) -> OpenSourceDiscoveryReport:
        discovered = self.discover(query, limit=max(limit * 2, limit))
        candidates = discovered[:limit]
        shortlist = [item for item in candidates if item.status in {OpenSourceStatus.CANDIDATE, OpenSourceStatus.SHORTLISTED, OpenSourceStatus.ADOPTED}]
        blocked = [item for item in candidates if item.status == OpenSourceStatus.BLOCKED]
        return OpenSourceDiscoveryReport(query=query, candidates=candidates, shortlist=shortlist[:limit], blocked=blocked[:limit], snapshot={"candidate_count": len(candidates), "shortlist_count": len(shortlist[:limit]), "blocked_count": len(blocked[:limit]), "query": query, "provider_count": len(self._providers)})
