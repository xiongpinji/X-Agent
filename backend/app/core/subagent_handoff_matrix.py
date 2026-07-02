from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


SUCCESS_STATUSES = {"success", "succeeded", "passed", "complete", "completed", "accepted", "ok"}
BLOCKED_STATUSES = {"blocked", "failed", "failure", "error", "timed_out", "timeout", "cancelled", "canceled"}


@dataclass(frozen=True)
class SubagentHandoffItem:
    handoff_id: str
    agent_id: str
    status: str
    summary_present: bool
    artifact_count: int
    validation_count: int
    changed_files: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)
    followups: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    parent_acceptance_refs: tuple[str, ...] = field(default_factory=tuple)
    decision: str = "ready"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "summary_present": self.summary_present,
            "artifact_count": self.artifact_count,
            "validation_count": self.validation_count,
            "changed_files": list(self.changed_files),
            "blockers": list(self.blockers),
            "followups": list(self.followups),
            "owner": self.owner,
            "parent_acceptance_refs": list(self.parent_acceptance_refs),
            "decision": self.decision,
            "reasons": list(self.reasons),
        }


def build_subagent_handoff_matrix(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    items = [_evaluate_handoff(item) for item in _handoff_payloads(data)]
    conflicts = _file_conflicts(items)
    rows = [_with_conflict_decision(item, conflicts) for item in items]
    issues = _issues(rows, conflicts)
    status = _status(rows, conflicts)

    return {
        "kind": "subagent_handoff_matrix",
        "version": 1,
        "ok": status == "ready",
        "status": status,
        "parent_task_id": str(data.get("parent_task_id") or data.get("task_id") or data.get("id") or ""),
        "goal": str(data.get("goal") or data.get("objective") or ""),
        "summary": {
            "handoff_count": len(rows),
            "ready_count": sum(1 for row in rows if row.decision == "ready"),
            "needs_review_count": sum(1 for row in rows if row.decision == "needs_review"),
            "blocked_count": sum(1 for row in rows if row.decision == "blocked"),
            "conflict_count": len(conflicts),
            "artifact_count": sum(row.artifact_count for row in rows),
            "validation_count": sum(row.validation_count for row in rows),
            "blocker_count": sum(len(row.blockers) for row in rows),
        },
        "rows": [row.as_dict() for row in rows],
        "conflicts": {path: list(agent_ids) for path, agent_ids in conflicts.items()},
        "issues": issues,
        "next_actions": _next_actions(rows, conflicts, issues),
    }


def evaluate_subagent_handoff(handoff: Mapping[str, Any] | Any) -> SubagentHandoffItem:
    return _evaluate_handoff(handoff)


def _evaluate_handoff(handoff: Mapping[str, Any] | Any) -> SubagentHandoffItem:
    payload = _as_mapping(handoff)
    handoff_id = str(payload.get("handoff_id") or payload.get("assignment_id") or payload.get("id") or "")
    agent_id = str(payload.get("agent_id") or payload.get("subagent_id") or payload.get("owner_agent") or "")
    status = _normalize_status(payload.get("status"))
    summary_present = bool(str(payload.get("summary") or payload.get("result_summary") or "").strip())
    artifact_count = _count(payload.get("artifacts") or payload.get("outputs"))
    validation_count = _count(payload.get("validation_evidence") or payload.get("validation") or payload.get("tests"))
    changed_files = tuple(_strings(payload.get("changed_files") or payload.get("files")))
    blockers = tuple(_strings(payload.get("blockers") or payload.get("blocking_reasons")))
    followups = tuple(_strings(payload.get("followups") or payload.get("required_followups") or payload.get("next_steps")))
    owner = str(payload.get("owner") or payload.get("review_owner") or "")
    parent_refs = tuple(_strings(payload.get("parent_acceptance_refs") or payload.get("acceptance_refs")))
    decision, reasons = _decision(
        status=status,
        summary_present=summary_present,
        artifact_count=artifact_count,
        validation_count=validation_count,
        blockers=blockers,
        owner=owner,
        parent_refs=parent_refs,
    )
    return SubagentHandoffItem(
        handoff_id=handoff_id,
        agent_id=agent_id,
        status=status,
        summary_present=summary_present,
        artifact_count=artifact_count,
        validation_count=validation_count,
        changed_files=changed_files,
        blockers=blockers,
        followups=followups,
        owner=owner,
        parent_acceptance_refs=parent_refs,
        decision=decision,
        reasons=tuple(reasons),
    )


def _decision(
    *,
    status: str,
    summary_present: bool,
    artifact_count: int,
    validation_count: int,
    blockers: Sequence[str],
    owner: str,
    parent_refs: Sequence[str],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if status == "blocked":
        reasons.append("handoff status blocked")
    elif status == "unknown":
        reasons.append("handoff status missing")
    if blockers:
        reasons.append("blockers present")
    if not summary_present:
        reasons.append("summary missing")
    if artifact_count == 0:
        reasons.append("artifacts missing")
    if validation_count == 0:
        reasons.append("validation evidence missing")
    if not owner:
        reasons.append("owner missing")
    if not parent_refs:
        reasons.append("parent acceptance refs missing")

    if "handoff status blocked" in reasons or "blockers present" in reasons:
        return "blocked", reasons
    if reasons:
        return "needs_review", reasons
    return "ready", ["handoff ready"]


def _with_conflict_decision(
    item: SubagentHandoffItem,
    conflicts: Mapping[str, Sequence[str]],
) -> SubagentHandoffItem:
    if not item.changed_files:
        return item
    conflicting_paths = [path for path in item.changed_files if path in conflicts]
    if not conflicting_paths:
        return item
    reasons = tuple(dict.fromkeys([*item.reasons, "changed-file conflict"]))
    decision = "blocked" if item.decision == "blocked" else "needs_review"
    return SubagentHandoffItem(
        handoff_id=item.handoff_id,
        agent_id=item.agent_id,
        status=item.status,
        summary_present=item.summary_present,
        artifact_count=item.artifact_count,
        validation_count=item.validation_count,
        changed_files=item.changed_files,
        blockers=item.blockers,
        followups=item.followups,
        owner=item.owner,
        parent_acceptance_refs=item.parent_acceptance_refs,
        decision=decision,
        reasons=reasons,
    )


def _file_conflicts(items: Sequence[SubagentHandoffItem]) -> dict[str, tuple[str, ...]]:
    owners_by_path: dict[str, list[str]] = {}
    for item in items:
        identity = item.agent_id or item.handoff_id or "unknown"
        for path in item.changed_files:
            owners_by_path.setdefault(path, []).append(identity)
    return {
        path: tuple(dict.fromkeys(owners))
        for path, owners in owners_by_path.items()
        if len(set(owners)) > 1
    }


def _issues(
    rows: Sequence[SubagentHandoffItem],
    conflicts: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for path, agent_ids in conflicts.items():
        issues.append(
            {
                "code": "subagent_handoff_changed_file_conflict",
                "severity": "medium",
                "path": path,
                "agent_ids": list(agent_ids),
            }
        )
    for row in rows:
        if row.decision == "ready":
            continue
        code = _issue_code(row)
        issues.append(
            {
                "code": code,
                "severity": "high" if row.decision == "blocked" else "medium",
                "handoff_id": row.handoff_id,
                "agent_id": row.agent_id,
                "reasons": list(row.reasons),
            }
        )
    return issues


def _issue_code(row: SubagentHandoffItem) -> str:
    if "handoff status blocked" in row.reasons:
        return "subagent_handoff_status_blocked"
    if "blockers present" in row.reasons:
        return "subagent_handoff_blockers_present"
    if "changed-file conflict" in row.reasons:
        return "subagent_handoff_changed_file_conflict"
    if "validation evidence missing" in row.reasons:
        return "subagent_handoff_validation_missing"
    if "artifacts missing" in row.reasons:
        return "subagent_handoff_artifacts_missing"
    if "summary missing" in row.reasons:
        return "subagent_handoff_summary_missing"
    if "owner missing" in row.reasons:
        return "subagent_handoff_owner_missing"
    if "parent acceptance refs missing" in row.reasons:
        return "subagent_handoff_parent_acceptance_refs_missing"
    return "subagent_handoff_needs_review"


def _status(rows: Sequence[SubagentHandoffItem], conflicts: Mapping[str, Sequence[str]]) -> str:
    if not rows:
        return "empty"
    if any(row.decision == "blocked" for row in rows):
        return "blocked"
    if conflicts or any(row.decision == "needs_review" for row in rows):
        return "needs_review"
    return "ready"


def _next_actions(
    rows: Sequence[SubagentHandoffItem],
    conflicts: Mapping[str, Sequence[str]],
    issues: Sequence[Mapping[str, Any]],
) -> list[str]:
    if not rows:
        return ["provide_subagent_handoffs"]
    codes = {str(issue.get("code") or "") for issue in issues}
    if any(row.decision == "blocked" for row in rows):
        return ["resolve_blocked_handoffs", "request_subagent_updates"]
    if conflicts:
        return ["resolve_changed_file_conflicts", "refresh_parent_handoff"]
    if any(code.endswith("_missing") for code in codes):
        return ["collect_missing_handoff_evidence", "refresh_parent_handoff"]
    if issues:
        return ["review_subagent_handoff_issues", "decide_parent_merge_readiness"]
    return ["prepare_parent_merge_review"]


def _handoff_payloads(data: Mapping[str, Any]) -> list[Any]:
    raw = data.get("handoffs") or data.get("subagents") or data.get("results") or []
    if isinstance(raw, Mapping):
        return list(raw.values())
    return _as_sequence(raw)


def _normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in SUCCESS_STATUSES:
        return "succeeded"
    if status in BLOCKED_STATUSES:
        return "blocked"
    if status:
        return "needs_review"
    return "unknown"


def _count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Mapping):
        if "passed" in value or "ok" in value or "status" in value:
            return 1
        return len(value)
    if isinstance(value, (str, bytes)):
        return 1 if value else 0
    if isinstance(value, Sequence):
        return len([item for item in value if item])
    return 1


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [str(value)] if value else []
    if isinstance(value, Mapping):
        return [str(key) for key in value.keys()]
    if isinstance(value, Sequence):
        return [str(item) for item in value if str(item)]
    return [str(value)]


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
