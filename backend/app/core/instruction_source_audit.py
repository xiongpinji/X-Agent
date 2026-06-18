from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


TASK_KEYWORDS = {
    "development": {"code", "bug", "test", "pytest", "api", "backend", "frontend", "refactor", "git", "pr"},
    "security": {"security", "secret", "token", "auth", "rbac", "permission", "sandbox", "audit"},
    "browser": {"browser", "web", "page", "click", "screenshot", "playwright", "dom", "console"},
    "data": {"data", "analysis", "chart", "visualization", "sql", "pandas", "spreadsheet"},
    "docs": {"doc", "docs", "readme", "report", "handoff", "summary", "markdown"},
    "deployment": {"deploy", "docker", "kubernetes", "helm", "ci", "workflow", "release"},
    "design": {"design", "figma", "ui", "ux", "layout", "component"},
}


@dataclass(frozen=True)
class InstructionAuditIssue:
    code: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


def audit_instruction_sources(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    task = str(data.get("task") or data.get("goal") or data.get("query") or "")
    touched_paths = [str(item) for item in _as_sequence(data.get("paths") or data.get("touched_paths")) if str(item)]
    instruction_sources = [_as_mapping(item) for item in _as_sequence(data.get("instruction_sources"))]
    skills = [_as_mapping(item) for item in _as_sequence(data.get("skills") or data.get("available_skills"))]
    domains = _infer_domains(task=task, paths=touched_paths)
    applicable_sources = _applicable_instruction_sources(instruction_sources, touched_paths)
    suggested_skills = _suggest_skills(skills, domains, task)
    issues = _collect_issues(
        instruction_sources=instruction_sources,
        applicable_sources=applicable_sources,
        suggested_skills=suggested_skills,
        domains=domains,
    )
    blockers = [issue for issue in issues if issue.severity in {"critical", "high"}]

    return {
        "kind": "instruction_source_audit",
        "version": 1,
        "ok": not blockers,
        "status": "blocked" if blockers else ("needs_review" if issues else "ready"),
        "summary": {
            "domain_count": len(domains),
            "instruction_source_count": len(instruction_sources),
            "applicable_source_count": len(applicable_sources),
            "available_skill_count": len(skills),
            "suggested_skill_count": len(suggested_skills),
            "issue_count": len(issues),
        },
        "domains": domains,
        "applicable_instruction_sources": applicable_sources,
        "suggested_skills": suggested_skills,
        "issues": [issue.as_dict() for issue in issues],
        "next_actions": _next_actions(issues, suggested_skills),
    }


def _infer_domains(*, task: str, paths: Sequence[str]) -> list[str]:
    text = f"{task} {' '.join(paths)}".lower()
    domains: list[str] = []
    for domain, keywords in TASK_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            domains.append(domain)
    if any(path.lower().startswith(("docs/", "readme")) for path in paths) and "docs" not in domains:
        domains.append("docs")
    if any(path.lower().startswith((".github/", "deploy/")) for path in paths) and "deployment" not in domains:
        domains.append("deployment")
    if not domains:
        domains.append("general")
    return domains


def _applicable_instruction_sources(
    instruction_sources: Sequence[Mapping[str, Any]],
    paths: Sequence[str],
) -> list[dict[str, Any]]:
    applicable: list[dict[str, Any]] = []
    for source in instruction_sources:
        source_path = str(source.get("path") or source.get("name") or "")
        scopes = [str(item).replace("\\", "/").strip() for item in _as_sequence(source.get("scopes"))]
        applies = not scopes or any(_path_matches_scope(path, scopes) for path in paths)
        if applies:
            applicable.append(
                {
                    "path": source_path,
                    "kind": str(source.get("kind") or _source_kind(source_path)),
                    "priority": int(_float(source.get("priority"), default=0)),
                    "scopes": scopes,
                    "summary": str(source.get("summary") or ""),
                }
            )
    applicable.sort(key=lambda item: (item["priority"], item["path"]), reverse=True)
    return applicable


def _suggest_skills(
    skills: Sequence[Mapping[str, Any]],
    domains: Sequence[str],
    task: str,
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    lowered_task = task.lower()
    domain_set = set(domains)
    for skill in skills:
        name = str(skill.get("name") or skill.get("id") or "")
        description = str(skill.get("description") or skill.get("summary") or "")
        tags = [str(item).lower() for item in _as_sequence(skill.get("tags") or skill.get("domains"))]
        text = f"{name} {description} {' '.join(tags)}".lower()
        matched_domains = sorted(domain for domain in domain_set if domain in tags or domain in text)
        keyword_hits = sorted(
            keyword
            for keywords in TASK_KEYWORDS.values()
            for keyword in keywords
            if keyword in lowered_task and keyword in text
        )
        score = min(1.0, 0.45 * len(matched_domains) + 0.15 * len(keyword_hits))
        if score > 0:
            suggestions.append(
                {
                    "name": name,
                    "score": round(score, 2),
                    "matched_domains": matched_domains,
                    "keyword_hits": keyword_hits[:8],
                    "source": str(skill.get("source") or ""),
                }
            )
    suggestions.sort(key=lambda item: (item["score"], item["name"]), reverse=True)
    return suggestions[:8]


def _collect_issues(
    *,
    instruction_sources: Sequence[Mapping[str, Any]],
    applicable_sources: Sequence[Mapping[str, Any]],
    suggested_skills: Sequence[Mapping[str, Any]],
    domains: Sequence[str],
) -> list[InstructionAuditIssue]:
    issues: list[InstructionAuditIssue] = []
    if not instruction_sources:
        issues.append(
            InstructionAuditIssue(
                "instruction_sources_missing",
                "medium",
                "No repository instruction sources were provided for audit.",
            )
        )
    if instruction_sources and not applicable_sources:
        issues.append(
            InstructionAuditIssue(
                "instruction_sources_not_applicable",
                "medium",
                "Instruction sources exist, but none apply to the provided task paths.",
            )
        )
    conflicts = _conflicting_sources(applicable_sources)
    if conflicts:
        issues.append(
            InstructionAuditIssue(
                "instruction_sources_priority_conflict",
                "medium",
                "Multiple applicable instruction sources share the same priority.",
                {"conflicts": conflicts},
            )
        )
    if "general" not in domains and not suggested_skills:
        issues.append(
            InstructionAuditIssue(
                "instruction_skill_suggestion_missing",
                "medium",
                "No available skill appears to match the inferred task domains.",
                {"domains": list(domains)},
            )
        )
    return issues


def _conflicting_sources(sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_priority: dict[int, list[str]] = {}
    for source in sources:
        priority = int(_float(source.get("priority"), default=0))
        by_priority.setdefault(priority, []).append(str(source.get("path") or ""))
    return [
        {"priority": priority, "sources": sorted(paths)}
        for priority, paths in sorted(by_priority.items(), reverse=True)
        if priority > 0 and len(paths) > 1
    ]


def _next_actions(
    issues: Sequence[InstructionAuditIssue],
    suggested_skills: Sequence[Mapping[str, Any]],
) -> list[str]:
    codes = {issue.code for issue in issues}
    actions: list[str] = []
    if "instruction_sources_missing" in codes:
        actions.append("provide_instruction_sources")
    if "instruction_sources_not_applicable" in codes:
        actions.append("review_instruction_scopes")
    if "instruction_sources_priority_conflict" in codes:
        actions.append("resolve_instruction_priority_conflict")
    if "instruction_skill_suggestion_missing" in codes:
        actions.append("review_skill_catalog")
    if suggested_skills:
        actions.append("review_suggested_skills")
    return actions or ["proceed_with_applicable_instructions"]


def _path_matches_scope(path: str, scopes: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/").strip()
    return any(normalized == scope or normalized.startswith(scope.rstrip("/") + "/") for scope in scopes if scope)


def _source_kind(path: str) -> str:
    lower = path.lower()
    if lower.endswith("agents.md"):
        return "agents_md"
    if ".agents" in lower:
        return "agents_directory"
    if ".codex" in lower:
        return "codex_directory"
    return "instruction"


def _float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
