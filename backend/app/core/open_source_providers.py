from __future__ import annotations

from datetime import UTC, datetime

from backend.app.core.open_source_api import OpenSourceCandidateRecord


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


class GitHubOpenSourceProvider:
    def __init__(self, name: str = "github", token: str | None = None) -> None:
        self.name = name
        self.token = token

    def search(self, query: str, limit: int = 10) -> list[OpenSourceCandidateRecord]:
        try:
            import requests
        except ImportError:
            return []
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        params = {"q": query, "sort": "stars", "order": "desc", "per_page": max(1, min(limit, 50))}
        try:
            response = requests.get("https://api.github.com/search/repositories", headers=headers, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []
        items = payload.get("items", []) if isinstance(payload, dict) else []
        records: list[OpenSourceCandidateRecord] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            lic = item.get("license") or {}
            owner = item.get("owner") or {}
            topics = item.get("topics") or []
            if not isinstance(topics, list):
                topics = []
            stars = int(item.get("stargazers_count") or 0)
            forks = int(item.get("forks_count") or 0)
            watchers = int(item.get("watchers_count") or 0)
            archived = bool(item.get("archived") or False)
            score = min(1.0, (stars / 100000.0) + (forks / 250000.0) + (watchers / 250000.0) + (0.05 if not archived else -0.1))
            records.append(OpenSourceCandidateRecord(name=str(item.get("name") or ""), source=self.name, url=str(item.get("html_url") or ""), license=str(lic.get("spdx_id") or lic.get("name") or ""), summary=str(item.get("description") or ""), score=max(0.0, min(1.0, score)), reasons=["github search result", f"stars:{stars}", f"forks:{forks}"], tags=[str(item.get("language") or ""), "github", *[str(t) for t in topics[:5] if str(t).strip()]], metadata={"stars": stars, "forks": forks, "watchers": watchers, "language": item.get("language"), "archived": archived, "default_branch": item.get("default_branch"), "homepage": item.get("homepage"), "topics": topics, "owner_login": owner.get("login"), "owner_type": owner.get("type"), "provider": self.name, "provider_kind": "github", "raw_score": score}))
        return records
