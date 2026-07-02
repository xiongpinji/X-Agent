from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


DEFAULT_MIN_SCORE = 0.6


@dataclass(frozen=True)
class OpenSourceCandidateAudit:
    index: int
    name: str
    source: str
    url: str
    status: str
    score: float
    normalized_score: float
    license: str
    risk_flags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "source": self.source,
            "url": self.url,
            "status": self.status,
            "score": self.score,
            "normalized_score": self.normalized_score,
            "license": self.license,
            "risk_flags": list(self.risk_flags),
        }


def audit_open_source_report(report: Any, *, min_score: float = DEFAULT_MIN_SCORE) -> dict[str, Any]:
    payload = _as_mapping(report)
    candidates = [_as_mapping(item) for item in _as_sequence(payload.get("candidates"))]
    candidate_audits = [
        audit_open_source_candidate(candidate, index=index, min_score=min_score)
        for index, candidate in enumerate(candidates)
    ]
    duplicate_urls = _duplicate_urls(candidate_audits)
    issues = _build_issues(candidate_audits, duplicate_urls)
    provider_count = _provider_count(payload)
    shortlist_count = len(_as_sequence(payload.get("shortlist")))
    blocked_count = len(_as_sequence(payload.get("blocked")))

    if not candidates:
        issues.append(
            {
                "code": "open_source_report_empty",
                "severity": "high",
                "message": "Open-source discovery report has no candidates.",
            }
        )
    if provider_count == 0:
        issues.append(
            {
                "code": "open_source_report_no_providers",
                "severity": "medium",
                "message": "Open-source discovery report does not identify any providers.",
            }
        )

    high_or_critical = [issue for issue in issues if issue["severity"] in {"high", "critical"}]
    return {
        "kind": "open_source_report_audit",
        "version": 1,
        "ok": not high_or_critical,
        "status": "review_required" if high_or_critical else "passed",
        "query": str(payload.get("query") or ""),
        "summary": {
            "candidate_count": len(candidate_audits),
            "shortlist_count": shortlist_count,
            "blocked_count": blocked_count,
            "provider_count": provider_count,
            "issue_count": len(issues),
            "max_score": max((item.normalized_score for item in candidate_audits), default=0.0),
            "duplicate_url_count": len(duplicate_urls),
        },
        "candidates": [item.as_dict() for item in candidate_audits],
        "duplicate_urls": duplicate_urls,
        "issues": issues,
    }


def audit_open_source_candidate(
    candidate: Mapping[str, Any],
    *,
    index: int = 0,
    min_score: float = DEFAULT_MIN_SCORE,
) -> OpenSourceCandidateAudit:
    metadata = _as_mapping(candidate.get("metadata"))
    score = _float(candidate.get("score"))
    normalized_score = _normalize_score(score)
    license_value = str(candidate.get("license") or "").strip()
    flags: list[str] = []
    if not license_value:
        flags.append("missing_license")
    if normalized_score < min_score:
        flags.append("low_score")
    if bool(metadata.get("archived")):
        flags.append("archived")
    if str(candidate.get("status") or "").lower() == "blocked":
        flags.append("blocked")
    return OpenSourceCandidateAudit(
        index=index,
        name=str(candidate.get("name") or ""),
        source=str(candidate.get("source") or ""),
        url=str(candidate.get("url") or ""),
        status=str(candidate.get("status") or ""),
        score=score,
        normalized_score=normalized_score,
        license=license_value,
        risk_flags=tuple(flags),
    )


def _build_issues(
    candidates: Sequence[OpenSourceCandidateAudit],
    duplicate_urls: Sequence[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in candidates:
        for flag in item.risk_flags:
            severity = "high" if flag in {"archived", "blocked"} else "medium"
            issues.append(
                {
                    "code": f"open_source_candidate_{flag}",
                    "severity": severity,
                    "candidate": item.name,
                    "url": item.url,
                    "message": f"Candidate has risk flag: {flag}.",
                }
            )
    for url in duplicate_urls:
        issues.append(
            {
                "code": "open_source_duplicate_candidate_url",
                "severity": "medium",
                "url": url,
                "message": "Multiple candidates share the same URL.",
            }
        )
    return issues


def _duplicate_urls(candidates: Sequence[OpenSourceCandidateAudit]) -> list[str]:
    counts: dict[str, int] = {}
    for item in candidates:
        key = item.url.strip().lower()
        if key:
            counts[key] = counts.get(key, 0) + 1
    return sorted(url for url, count in counts.items() if count > 1)


def _provider_count(payload: Mapping[str, Any]) -> int:
    providers = _as_sequence(payload.get("providers"))
    if providers:
        return len(providers)
    for key in ("snapshot", "summary"):
        nested = _as_mapping(payload.get(key))
        count = nested.get("provider_count")
        if count is not None:
            return max(0, int(_float(count)))
    provider_names = {
        str(_as_mapping(item).get("source") or "")
        for item in _as_sequence(payload.get("candidates"))
        if str(_as_mapping(item).get("source") or "")
    }
    return len(provider_names)


def _normalize_score(score: float) -> float:
    if score > 1.0:
        return max(0.0, min(1.0, score / 100.0))
    return max(0.0, min(1.0, score))


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []
