from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


PERMISSIVE_LICENSES = {"mit", "apache-2.0", "bsd", "bsd-2-clause", "bsd-3-clause", "isc", "mpl-2.0"}
RESTRICTIVE_LICENSES = {"gpl-2.0", "gpl-3.0", "agpl-3.0", "lgpl-2.1", "lgpl-3.0"}
HIGH_RISK_FLAGS = {"archived", "blocked", "security_issue", "malware", "unmaintained"}
MEDIUM_RISK_FLAGS = {"missing_license", "low_score", "unknown_license", "heavy_runtime_dependency"}
FIT_KEYWORDS = {
    "browser": {"browser", "web", "playwright", "automation", "ui", "computer-use"},
    "agent": {"agent", "subagent", "orchestration", "workflow", "swe", "coding"},
    "review": {"review", "pull request", "pr", "diff", "git", "issue"},
    "evaluation": {"eval", "benchmark", "test", "acceptance", "regression"},
    "mcp": {"mcp", "tool", "server", "connector", "integration"},
}


@dataclass(frozen=True)
class OpenSourceAdoptionCandidate:
    name: str
    url: str
    license: str
    fit_score: float
    health_score: float
    risk_score: float
    adoption_score: float
    recommendation: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    risk_flags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "license": self.license,
            "fit_score": self.fit_score,
            "health_score": self.health_score,
            "risk_score": self.risk_score,
            "adoption_score": self.adoption_score,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "risk_flags": list(self.risk_flags),
        }


def build_open_source_adoption_matrix(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    target = str(data.get("target") or data.get("task") or data.get("query") or "")
    candidates = [_as_mapping(item) for item in _candidate_payloads(data)]
    assessments = [assess_open_source_candidate(item, target=target) for item in candidates]
    ready = [item for item in assessments if item.recommendation == "adopt_ready"]
    review = [item for item in assessments if item.recommendation == "needs_review"]
    blocked = [item for item in assessments if item.recommendation == "do_not_adopt"]

    return {
        "kind": "open_source_adoption_matrix",
        "version": 1,
        "ok": bool(ready) and not blocked,
        "status": "adopt_ready" if ready and not blocked else ("needs_review" if assessments else "empty"),
        "target": target,
        "summary": {
            "candidate_count": len(assessments),
            "adopt_ready_count": len(ready),
            "needs_review_count": len(review),
            "do_not_adopt_count": len(blocked),
            "top_candidate": assessments[0].name if assessments else "",
            "top_score": assessments[0].adoption_score if assessments else 0.0,
        },
        "candidates": [item.as_dict() for item in assessments],
        "issues": _issues(assessments),
        "next_actions": _next_actions(assessments),
    }


def assess_open_source_candidate(candidate: Mapping[str, Any], *, target: str = "") -> OpenSourceAdoptionCandidate:
    metadata = _as_mapping(candidate.get("metadata"))
    name = str(candidate.get("name") or "")
    url = str(candidate.get("url") or "")
    license_value = str(candidate.get("license") or "").strip()
    normalized_license = license_value.lower()
    raw_score = _normalize_score(_float(candidate.get("score")))
    risk_flags = _risk_flags(candidate, metadata=metadata, normalized_license=normalized_license, raw_score=raw_score)
    fit_score, fit_reasons = _fit_score(candidate, target=target)
    health_score, health_reasons = _health_score(candidate, raw_score=raw_score, metadata=metadata)
    risk_score = _risk_score(risk_flags)
    adoption_score = round(max(0.0, min(1.0, (fit_score * 0.45) + (health_score * 0.4) - (risk_score * 0.35))), 2)
    recommendation = _recommendation(adoption_score, risk_flags)
    reasons = tuple([*fit_reasons, *health_reasons, *_license_reasons(normalized_license, license_value)])
    return OpenSourceAdoptionCandidate(
        name=name,
        url=url,
        license=license_value,
        fit_score=round(fit_score, 2),
        health_score=round(health_score, 2),
        risk_score=round(risk_score, 2),
        adoption_score=adoption_score,
        recommendation=recommendation,
        reasons=reasons,
        risk_flags=tuple(risk_flags),
    )


def _candidate_payloads(data: Mapping[str, Any]) -> list[Any]:
    if _as_sequence(data.get("candidates")):
        return _as_sequence(data.get("candidates"))
    report = _as_mapping(data.get("report") or data.get("open_source_report"))
    return _as_sequence(report.get("candidates"))


def _fit_score(candidate: Mapping[str, Any], *, target: str) -> tuple[float, list[str]]:
    text = " ".join(
        [
            str(candidate.get("name") or ""),
            str(candidate.get("summary") or candidate.get("description") or ""),
            " ".join(str(item) for item in _as_sequence(candidate.get("tags"))),
            " ".join(str(item) for item in _as_sequence(candidate.get("reasons"))),
        ]
    ).lower()
    target_text = target.lower()
    matched: list[str] = []
    for domain, keywords in FIT_KEYWORDS.items():
        if any(keyword in target_text for keyword in keywords) and any(keyword in text for keyword in keywords):
            matched.append(domain)
    if not target_text:
        return 0.5, ["no target provided; using neutral fit"]
    score = min(1.0, 0.35 + 0.22 * len(matched))
    reasons = [f"matched target domain: {domain}" for domain in matched] or ["no strong target-domain match"]
    return score, reasons


def _health_score(
    candidate: Mapping[str, Any],
    *,
    raw_score: float,
    metadata: Mapping[str, Any],
) -> tuple[float, list[str]]:
    stars = _float(metadata.get("stars"))
    forks = _float(metadata.get("forks"))
    recent_activity = str(metadata.get("recent_activity") or metadata.get("maintenance") or "").lower()
    score = raw_score
    reasons = [f"discovery score={round(raw_score, 2)}"]
    if stars >= 1000:
        score += 0.12
        reasons.append("popular repository")
    if forks >= 100:
        score += 0.06
        reasons.append("healthy fork signal")
    if recent_activity in {"active", "recent", "maintained"}:
        score += 0.12
        reasons.append("recent maintenance signal")
    if metadata.get("archived") is True:
        score -= 0.4
        reasons.append("archived repository")
    return max(0.0, min(1.0, score)), reasons


def _risk_flags(
    candidate: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    normalized_license: str,
    raw_score: float,
) -> list[str]:
    flags = [str(item) for item in _as_sequence(candidate.get("risk_flags")) if str(item)]
    if not normalized_license:
        flags.append("missing_license")
    elif normalized_license not in PERMISSIVE_LICENSES and normalized_license not in RESTRICTIVE_LICENSES:
        flags.append("unknown_license")
    if normalized_license in RESTRICTIVE_LICENSES:
        flags.append("restrictive_license")
    if raw_score < 0.35:
        flags.append("low_score")
    if metadata.get("archived") is True:
        flags.append("archived")
    if str(candidate.get("status") or "").lower() == "blocked":
        flags.append("blocked")
    if metadata.get("heavy_runtime_dependency") is True:
        flags.append("heavy_runtime_dependency")
    return tuple(dict.fromkeys(flags))  # type: ignore[return-value]


def _risk_score(risk_flags: Sequence[str]) -> float:
    score = 0.0
    for flag in risk_flags:
        if flag in HIGH_RISK_FLAGS or flag == "restrictive_license":
            score += 0.45
        elif flag in MEDIUM_RISK_FLAGS:
            score += 0.2
        else:
            score += 0.1
    return min(1.0, score)


def _recommendation(adoption_score: float, risk_flags: Sequence[str]) -> str:
    if set(risk_flags).intersection(HIGH_RISK_FLAGS) or "restrictive_license" in risk_flags:
        return "do_not_adopt"
    if adoption_score >= 0.62 and not risk_flags:
        return "adopt_ready"
    return "needs_review"


def _license_reasons(normalized_license: str, original: str) -> list[str]:
    if not normalized_license:
        return ["missing license"]
    if normalized_license in PERMISSIVE_LICENSES:
        return [f"permissive license: {original}"]
    if normalized_license in RESTRICTIVE_LICENSES:
        return [f"restrictive license: {original}"]
    return [f"unknown license: {original}"]


def _issues(assessments: Sequence[OpenSourceAdoptionCandidate]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in assessments:
        if item.recommendation == "do_not_adopt":
            issues.append(
                {
                    "code": "open_source_candidate_do_not_adopt",
                    "severity": "high",
                    "candidate": item.name,
                    "risk_flags": list(item.risk_flags),
                }
            )
        elif item.recommendation == "needs_review":
            issues.append(
                {
                    "code": "open_source_candidate_needs_review",
                    "severity": "medium",
                    "candidate": item.name,
                    "risk_flags": list(item.risk_flags),
                }
            )
    return issues


def _next_actions(assessments: Sequence[OpenSourceAdoptionCandidate]) -> list[str]:
    if not assessments:
        return ["provide_open_source_candidates"]
    if any(item.recommendation == "do_not_adopt" for item in assessments):
        return ["reject_blocked_candidates", "review_alternatives"]
    if any(item.recommendation == "needs_review" for item in assessments):
        return ["review_license_and_integration_risk"]
    return ["prepare_integration_design_review"]


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
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []
