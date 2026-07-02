from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


READY_STATUSES = {"ready", "passed", "accepted", "complete", "completed", "ok"}
REVIEW_STATUSES = {"needs_review", "review_next", "preview", "owner_action_required"}
BLOCKED_STATUSES = {"blocked", "failed", "failure", "error", "block"}
EMPTY_STATUSES = {"", "empty", "missing", "unknown"}

READY_RECOMMENDATIONS = {"integrate_now", "review_top", "ready", "accept", "accepted"}
REVIEW_RECOMMENDATIONS = {"review_next", "defer", "needs_review", "preview"}
BLOCKED_RECOMMENDATIONS = {"block", "blocked", "reject", "rejected"}


@dataclass(frozen=True)
class CandidateDependency:
    candidate_id: str
    name: str = ""
    owner: str = ""
    status: str = "unknown"
    recommendation: str = ""
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    blocks: tuple[str, ...] = field(default_factory=tuple)
    blocked_by: tuple[str, ...] = field(default_factory=tuple)
    issue_count: int = 0
    state: str = "needs_review"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "owner": self.owner,
            "status": self.status,
            "recommendation": self.recommendation,
            "depends_on": list(self.depends_on),
            "blocks": list(self.blocks),
            "blocked_by": list(self.blocked_by),
            "issue_count": self.issue_count,
            "state": self.state,
            "reasons": list(self.reasons),
        }


def build_candidate_dependency_map(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    candidates = [_candidate(item, index) for index, item in enumerate(_candidate_payloads(data), start=1)]
    by_id = {item.candidate_id: item for item in candidates if item.candidate_id}
    effective_blocked_by = _effective_blocked_by(candidates)
    missing_dependencies = _missing_dependencies(candidates, by_id, effective_blocked_by)
    cycles = _cycles(candidates, by_id, effective_blocked_by)
    blocked_chains = _blocked_chains(candidates, by_id, effective_blocked_by, missing_dependencies, cycles)
    orphan_candidates = [item.candidate_id for item in candidates if not item.owner]
    issues = _issues(candidates, missing_dependencies, cycles, blocked_chains, orphan_candidates)
    status = _status(candidates, issues)

    return {
        "kind": "candidate_dependency_map",
        "version": 1,
        "ok": status == "ready",
        "status": status,
        "map_id": str(data.get("map_id") or data.get("review_id") or data.get("id") or ""),
        "summary": {
            "candidate_count": len(candidates),
            "ready_count": sum(1 for item in candidates if item.state == "ready"),
            "needs_review_count": sum(1 for item in candidates if item.state == "needs_review"),
            "blocked_count": sum(1 for item in candidates if item.state == "blocked"),
            "missing_dependency_count": len(missing_dependencies),
            "cycle_count": len(cycles),
            "blocked_chain_count": len(blocked_chains),
            "orphan_candidate_count": len(orphan_candidates),
        },
        "candidates": [item.as_dict() for item in candidates],
        "ready_roots": _ready_roots(candidates, effective_blocked_by, missing_dependencies, cycles),
        "ready_with_satisfied_dependencies": _ready_with_satisfied_dependencies(
            candidates,
            by_id,
            effective_blocked_by,
            missing_dependencies,
            cycles,
        ),
        "integration_order": _integration_order(candidates, by_id, effective_blocked_by, cycles),
        "blocked_chains": blocked_chains,
        "cycles": cycles,
        "missing_dependencies": missing_dependencies,
        "orphan_candidates": orphan_candidates,
        "issues": issues,
        "next_actions": _next_actions(candidates, issues),
    }


def analyze_candidate_dependency(candidate: Mapping[str, Any] | Any) -> CandidateDependency:
    return _candidate(candidate, 1)


def _candidate(candidate: Mapping[str, Any] | Any, index: int) -> CandidateDependency:
    payload = _as_mapping(candidate)
    candidate_id = str(payload.get("candidate_id") or payload.get("id") or "").strip()
    name = str(payload.get("name") or payload.get("title") or "").strip()
    if not candidate_id and name:
        candidate_id = name
    if not candidate_id:
        candidate_id = f"unknown-{index}"

    status = _normalize_token(payload.get("status"))
    recommendation = _normalize_token(payload.get("recommendation") or payload.get("decision"))
    issue_count = _count(payload.get("issues"))
    owner = str(payload.get("owner") or payload.get("team") or "").strip()
    reasons = _candidate_reasons(status=status, recommendation=recommendation, owner=owner, issue_count=issue_count)

    return CandidateDependency(
        candidate_id=candidate_id,
        name=name,
        owner=owner,
        status=status or "unknown",
        recommendation=recommendation,
        depends_on=tuple(
            _dedupe(
                _refs(payload.get("depends_on"))
                + _refs(payload.get("dependencies"))
                + _refs(payload.get("requires"))
                + _refs(payload.get("prerequisites"))
            )
        ),
        blocks=tuple(_dedupe(_refs(payload.get("blocks")) + _refs(payload.get("blocks_candidates")))),
        blocked_by=tuple(_dedupe(_refs(payload.get("blocked_by")) + _refs(payload.get("blockers")))),
        issue_count=issue_count,
        state=_candidate_state(reasons),
        reasons=tuple(reasons),
    )


def _candidate_reasons(*, status: str, recommendation: str, owner: str, issue_count: int) -> list[str]:
    reasons: list[str] = []
    if not owner:
        reasons.append("owner missing")
    if status in BLOCKED_STATUSES or recommendation in BLOCKED_RECOMMENDATIONS:
        reasons.append("candidate blocked")
    if status in REVIEW_STATUSES or recommendation in REVIEW_RECOMMENDATIONS:
        reasons.append("candidate needs review")
    if status in EMPTY_STATUSES and recommendation not in READY_RECOMMENDATIONS:
        reasons.append("status missing or unknown")
    if issue_count > 0:
        reasons.append("candidate has unresolved issues")
    if not reasons:
        if status in READY_STATUSES or recommendation in READY_RECOMMENDATIONS:
            reasons.append("candidate ready")
        else:
            reasons.append("candidate needs review")
    return reasons


def _candidate_state(reasons: Sequence[str]) -> str:
    if "candidate blocked" in reasons:
        return "blocked"
    review_reasons = {
        "owner missing",
        "candidate needs review",
        "status missing or unknown",
        "candidate has unresolved issues",
    }
    if any(reason in review_reasons for reason in reasons):
        return "needs_review"
    return "ready"


def _effective_blocked_by(candidates: Sequence[CandidateDependency]) -> dict[str, list[str]]:
    blocked_by: dict[str, list[str]] = {item.candidate_id: list(item.blocked_by) for item in candidates}
    for item in candidates:
        for target in item.blocks:
            blocked_by.setdefault(target, [])
            if item.candidate_id not in blocked_by[target]:
                blocked_by[target].append(item.candidate_id)
    return {candidate_id: _dedupe(values) for candidate_id, values in blocked_by.items()}


def _prerequisites(candidate: CandidateDependency, effective_blocked_by: Mapping[str, Sequence[str]]) -> list[str]:
    return _dedupe(list(candidate.depends_on) + list(effective_blocked_by.get(candidate.candidate_id, [])))


def _missing_dependencies(
    candidates: Sequence[CandidateDependency],
    by_id: Mapping[str, CandidateDependency],
    effective_blocked_by: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for item in candidates:
        for dependency in _prerequisites(item, effective_blocked_by):
            if dependency not in by_id:
                missing.append(
                    {
                        "candidate_id": item.candidate_id,
                        "dependency_id": dependency,
                        "code": "candidate_dependency_missing",
                    }
                )
        for target in item.blocks:
            if target not in by_id:
                missing.append(
                    {
                        "candidate_id": item.candidate_id,
                        "dependency_id": target,
                        "code": "candidate_block_target_missing",
                    }
                )
    return missing


def _cycles(
    candidates: Sequence[CandidateDependency],
    by_id: Mapping[str, CandidateDependency],
    effective_blocked_by: Mapping[str, Sequence[str]],
) -> list[list[str]]:
    graph = {
        item.candidate_id: [dependency for dependency in _prerequisites(item, effective_blocked_by) if dependency in by_id]
        for item in candidates
    }
    color: dict[str, str] = {}
    stack: list[str] = []
    found: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        color[node] = "visiting"
        stack.append(node)
        for dependency in graph.get(node, []):
            state = color.get(dependency)
            if state is None:
                visit(dependency)
            elif state == "visiting" and dependency in stack:
                start = stack.index(dependency)
                cycle = stack[start:] + [dependency]
                key = _cycle_key(cycle)
                if key not in seen:
                    seen.add(key)
                    found.append(cycle)
        stack.pop()
        color[node] = "done"

    for item in candidates:
        if color.get(item.candidate_id) is None:
            visit(item.candidate_id)
    return found


def _blocked_chains(
    candidates: Sequence[CandidateDependency],
    by_id: Mapping[str, CandidateDependency],
    effective_blocked_by: Mapping[str, Sequence[str]],
    missing_dependencies: Sequence[Mapping[str, Any]],
    cycles: Sequence[Sequence[str]],
) -> list[dict[str, Any]]:
    missing_by_candidate: dict[str, list[str]] = defaultdict(list)
    for item in missing_dependencies:
        if item.get("code") == "candidate_dependency_missing":
            missing_by_candidate[str(item.get("candidate_id") or "")].append(str(item.get("dependency_id") or ""))
    cycle_members = {candidate_id for cycle in cycles for candidate_id in cycle}

    chains: list[dict[str, Any]] = []
    for item in candidates:
        chain, reason = _first_blocked_chain(
            item,
            by_id,
            effective_blocked_by,
            missing_by_candidate,
            cycle_members,
            visited=set(),
        )
        if chain:
            chains.append({"candidate_id": item.candidate_id, "chain": chain, "reason": reason})
    return chains


def _first_blocked_chain(
    item: CandidateDependency,
    by_id: Mapping[str, CandidateDependency],
    effective_blocked_by: Mapping[str, Sequence[str]],
    missing_by_candidate: Mapping[str, Sequence[str]],
    cycle_members: set[str],
    visited: set[str],
) -> tuple[list[str], str]:
    if item.candidate_id in cycle_members:
        return [item.candidate_id], "dependency_cycle"
    if item.candidate_id in missing_by_candidate:
        return [item.candidate_id, missing_by_candidate[item.candidate_id][0]], "missing_dependency"
    if item.state == "blocked":
        return [item.candidate_id], "candidate_blocked"
    if item.candidate_id in visited:
        return [], ""

    visited.add(item.candidate_id)
    for dependency_id in _prerequisites(item, effective_blocked_by):
        dependency = by_id.get(dependency_id)
        if dependency is None:
            return [item.candidate_id, dependency_id], "missing_dependency"
        if dependency.state != "ready":
            return [item.candidate_id, dependency_id], f"dependency_{dependency.state}"
        subchain, reason = _first_blocked_chain(
            dependency,
            by_id,
            effective_blocked_by,
            missing_by_candidate,
            cycle_members,
            visited=set(visited),
        )
        if subchain:
            return [item.candidate_id] + subchain, reason
    return [], ""


def _ready_roots(
    candidates: Sequence[CandidateDependency],
    effective_blocked_by: Mapping[str, Sequence[str]],
    missing_dependencies: Sequence[Mapping[str, Any]],
    cycles: Sequence[Sequence[str]],
) -> list[str]:
    blocked = _blocked_candidate_ids(missing_dependencies, cycles)
    return [
        item.candidate_id
        for item in candidates
        if item.state == "ready"
        and item.candidate_id not in blocked
        and not _prerequisites(item, effective_blocked_by)
    ]


def _ready_with_satisfied_dependencies(
    candidates: Sequence[CandidateDependency],
    by_id: Mapping[str, CandidateDependency],
    effective_blocked_by: Mapping[str, Sequence[str]],
    missing_dependencies: Sequence[Mapping[str, Any]],
    cycles: Sequence[Sequence[str]],
) -> list[str]:
    blocked = _blocked_candidate_ids(missing_dependencies, cycles)
    ready: list[str] = []
    for item in candidates:
        if item.state != "ready" or item.candidate_id in blocked:
            continue
        prerequisites = _prerequisites(item, effective_blocked_by)
        if prerequisites and all(by_id.get(dependency) and by_id[dependency].state == "ready" for dependency in prerequisites):
            ready.append(item.candidate_id)
    return ready


def _integration_order(
    candidates: Sequence[CandidateDependency],
    by_id: Mapping[str, CandidateDependency],
    effective_blocked_by: Mapping[str, Sequence[str]],
    cycles: Sequence[Sequence[str]],
) -> list[str]:
    if cycles:
        return []

    ids = [item.candidate_id for item in candidates]
    dependencies_by_candidate = {
        item.candidate_id: [dependency for dependency in _prerequisites(item, effective_blocked_by) if dependency in by_id]
        for item in candidates
    }
    dependents: dict[str, list[str]] = defaultdict(list)
    indegree = {candidate_id: 0 for candidate_id in ids}
    for candidate_id, dependencies in dependencies_by_candidate.items():
        indegree[candidate_id] = len(dependencies)
        for dependency in dependencies:
            dependents[dependency].append(candidate_id)

    queue = deque(candidate_id for candidate_id in ids if indegree[candidate_id] == 0)
    order: list[str] = []
    while queue:
        candidate_id = queue.popleft()
        order.append(candidate_id)
        for dependent in dependents.get(candidate_id, []):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
    return order if len(order) == len(ids) else []


def _issues(
    candidates: Sequence[CandidateDependency],
    missing_dependencies: Sequence[Mapping[str, Any]],
    cycles: Sequence[Sequence[str]],
    blocked_chains: Sequence[Mapping[str, Any]],
    orphan_candidates: Sequence[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in missing_dependencies:
        issues.append({"code": item["code"], "severity": "high", **dict(item)})
    for cycle in cycles:
        issues.append({"code": "candidate_dependency_cycle", "severity": "high", "cycle": list(cycle)})
    for chain in blocked_chains:
        if chain.get("reason") in {"missing_dependency", "dependency_cycle"}:
            continue
        issues.append({"code": "candidate_dependency_blocked_chain", "severity": "high", **dict(chain)})
    for item in candidates:
        if item.state == "needs_review":
            issues.append(
                {
                    "code": "candidate_dependency_candidate_needs_review",
                    "severity": "medium",
                    "candidate_id": item.candidate_id,
                    "reasons": list(item.reasons),
                }
            )
    for candidate_id in orphan_candidates:
        issues.append(
            {
                "code": "candidate_dependency_owner_missing",
                "severity": "medium",
                "candidate_id": candidate_id,
            }
        )
    return issues


def _status(candidates: Sequence[CandidateDependency], issues: Sequence[Mapping[str, Any]]) -> str:
    if not candidates:
        return "empty"
    if any(item.get("severity") == "high" for item in issues):
        return "blocked"
    if issues:
        return "needs_review"
    return "ready"


def _next_actions(candidates: Sequence[CandidateDependency], issues: Sequence[Mapping[str, Any]]) -> list[str]:
    if not candidates:
        return ["provide_dependency_candidates"]

    codes = {str(item.get("code") or "") for item in issues}
    actions: list[str] = []
    if "candidate_dependency_cycle" in codes:
        actions.append("resolve_dependency_cycles")
    if "candidate_dependency_missing" in codes or "candidate_block_target_missing" in codes:
        actions.append("add_missing_dependencies_or_remove_references")
    if "candidate_dependency_blocked_chain" in codes:
        actions.append("resolve_blocked_candidate_dependencies")
    if "candidate_dependency_owner_missing" in codes:
        actions.append("assign_candidate_dependency_owners")
    if "candidate_dependency_candidate_needs_review" in codes:
        actions.append("review_candidate_dependency_readiness")
    if actions:
        actions.append("rebuild_candidate_dependency_map")
        return _dedupe(actions)
    return ["prepare_ordered_integration_plan"]


def _blocked_candidate_ids(
    missing_dependencies: Sequence[Mapping[str, Any]],
    cycles: Sequence[Sequence[str]],
) -> set[str]:
    blocked = {str(item.get("candidate_id") or "") for item in missing_dependencies}
    blocked.update(candidate_id for cycle in cycles for candidate_id in cycle)
    return blocked


def _candidate_payloads(data: Mapping[str, Any]) -> list[Any]:
    raw = data.get("candidates") or data.get("dependency_map") or data.get("nodes") or data.get("items") or []
    if isinstance(raw, Mapping):
        payloads: list[Any] = []
        for key, value in raw.items():
            if isinstance(value, Mapping):
                item = dict(value)
                item.setdefault("candidate_id", key)
                payloads.append(item)
            else:
                payloads.append(value)
        return payloads
    return _as_sequence(raw)


def _refs(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [str(value).strip()] if str(value).strip() else []
    if isinstance(value, Mapping):
        return [str(key).strip() for key in value if str(key).strip()]
    if isinstance(value, Sequence):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Mapping):
        if "code" in value or "status" in value:
            return 1
        return len(value)
    if isinstance(value, (str, bytes)):
        return 1 if value else 0
    if isinstance(value, Sequence):
        return len([item for item in value if item])
    return 1


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


def _cycle_key(cycle: Sequence[str]) -> tuple[str, ...]:
    body = list(cycle[:-1]) if len(cycle) > 1 and cycle[0] == cycle[-1] else list(cycle)
    if not body:
        return tuple(cycle)
    rotations = [tuple(body[index:] + body[:index]) for index in range(len(body))]
    return min(rotations)
