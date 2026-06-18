from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def build_integration_adoption_readme(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    components = _components(data)
    component_map = {str(component.get("kind") or f"component_{index}"): component for index, component in enumerate(components)}
    validation = _validation(data)
    candidate_files = _candidate_files(data, components)
    boundaries = [str(item) for item in _as_sequence(data.get("boundaries"))] or [
        "Detached secondary-candidate payload only.",
        "Mainline owner controls adoption writes.",
    ]
    issues = _issues(component_map, validation, candidate_files)
    status = _status(issues)
    sections = _sections(data, component_map, validation, candidate_files, boundaries, issues)
    next_actions = _next_actions(status, issues)

    return {
        "kind": "integration_adoption_readme",
        "readme_id": str(data.get("readme_id") or ""),
        "ok": status == "ready",
        "status": status,
        "title": str(data.get("title") or "Integration Adoption Notes"),
        "summary": {
            "section_count": len(sections),
            "component_count": len(component_map),
            "candidate_file_count": len(candidate_files),
            "issue_count": len(issues),
        },
        "components": list(component_map.values()),
        "candidate_files": candidate_files,
        "validation": validation,
        "sections": sections,
        "issues": issues,
        "next_actions": next_actions,
        "markdown_preview": render_adoption_readme_markdown(sections, title=str(data.get("title") or "Integration Adoption Notes")),
    }


def render_adoption_readme_markdown(
    sections: Sequence[Mapping[str, Any] | Any],
    *,
    title: str = "Integration Adoption Notes",
) -> str:
    lines = [f"# {title}", ""]
    for section in sections:
        payload = _as_mapping(section)
        heading = str(payload.get("title") or payload.get("section_id") or "Section")
        lines.append(f"## {heading}")
        for bullet in _as_sequence(payload.get("bullets")):
            lines.append(f"- {bullet}")
        lines.append("")
    return "\n".join(lines)


def _components(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("components")
    if raw:
        return [_as_mapping(item) for item in _as_sequence(raw)]
    keys = ("final_review_brief", "closure_checklist", "traceability_index")
    return [_as_mapping(data[key]) for key in keys if data.get(key)]


def _validation(data: Mapping[str, Any]) -> dict[str, list[str]]:
    raw = _as_mapping(data.get("validation"))
    commands = _as_sequence(raw.get("commands")) or _as_sequence(data.get("validation_commands"))
    results = _as_sequence(raw.get("results")) or _as_sequence(data.get("validation_results"))
    return {
        "commands": [str(command) for command in commands],
        "results": [str(result) for result in results],
    }


def _candidate_files(data: Mapping[str, Any], components: Sequence[Mapping[str, Any]]) -> list[str]:
    files = [str(path) for path in _as_sequence(data.get("candidate_files"))]
    for component in components:
        files.extend(str(path) for path in _as_sequence(component.get("files")))
        for entry in _as_sequence(component.get("entries")):
            files.extend(str(path) for path in _as_sequence(_as_mapping(entry).get("files")))
    return _unique(files)


def _issues(
    components: Mapping[str, Mapping[str, Any]],
    validation: Mapping[str, Sequence[str]],
    candidate_files: Sequence[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key, component in components.items():
        if component.get("ok") is False or str(component.get("status") or "") == "blocked":
            issues.append(
                {
                    "code": "adoption_readme_component_blocked",
                    "severity": "high",
                    "component": _component_key(key),
                }
            )
    if not validation.get("commands") and not validation.get("results"):
        issues.append({"code": "adoption_readme_validation_missing", "severity": "medium"})
    if not candidate_files:
        issues.append({"code": "adoption_readme_files_missing", "severity": "medium"})
    return issues


def _status(issues: Sequence[Mapping[str, Any]]) -> str:
    if any(str(issue.get("severity")) == "high" for issue in issues):
        return "blocked"
    if issues:
        return "needs_review"
    return "ready"


def _sections(
    data: Mapping[str, Any],
    components: Mapping[str, Mapping[str, Any]],
    validation: Mapping[str, Sequence[str]],
    candidate_files: Sequence[str],
    boundaries: Sequence[str],
    issues: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    title = str(data.get("title") or "Integration Adoption Notes")
    component_bullets = [
        f"{kind}: {component.get('status', 'unknown')}"
        for kind, component in components.items()
    ] or ["No adoption components provided."]
    validation_bullets = list(validation.get("commands") or validation.get("results") or ["Validation evidence missing."])
    file_bullets = list(candidate_files or ["Candidate files missing."])
    issue_bullets = [str(issue.get("code")) for issue in issues] or ["No adoption readme issues."]
    return [
        {"section_id": "overview", "title": "Overview", "bullets": [title]},
        {"section_id": "components", "title": "Components", "bullets": component_bullets},
        {"section_id": "validation", "title": "Validation", "bullets": validation_bullets},
        {"section_id": "boundaries", "title": "Boundaries", "bullets": list(boundaries)},
        {"section_id": "candidate_files", "title": "Candidate Files", "bullets": file_bullets + issue_bullets},
    ]


def _next_actions(status: str, issues: Sequence[Mapping[str, Any]]) -> list[str]:
    if status == "blocked":
        return ["resolve_adoption_readme_blockers", "rebuild_integration_adoption_readme"]
    actions: list[str] = []
    codes = [str(issue.get("code")) for issue in issues]
    if "adoption_readme_validation_missing" in codes:
        actions.append("attach_adoption_validation_commands")
    if "adoption_readme_files_missing" in codes:
        actions.append("attach_adoption_candidate_files")
    if actions:
        actions.append("rebuild_integration_adoption_readme")
        return actions
    return ["review_adoption_readme_payload_with_mainline"]


def _component_key(kind: str) -> str:
    return kind.removeprefix("integration_")


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []


def _unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
