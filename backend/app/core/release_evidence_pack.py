from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


READY_STATUSES = {"ready", "accepted", "adopt_ready", "passed", "complete", "completed", "ok"}
REVIEW_STATUSES = {"needs_review", "preview", "owner_action_required", "ready_with_owner_gates"}
BLOCKED_STATUSES = {"blocked", "failed", "failure", "error", "do_not_adopt"}
EMPTY_STATUSES = {"", "empty", "missing", "unknown"}


@dataclass(frozen=True)
class EvidencePackItem:
    kind: str
    name: str
    status: str
    ok: bool
    issue_count: int
    high_issue_count: int
    next_actions: tuple[str, ...] = field(default_factory=tuple)
    summary: Mapping[str, Any] = field(default_factory=dict)
    decision: str = "ready"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "status": self.status,
            "ok": self.ok,
            "issue_count": self.issue_count,
            "high_issue_count": self.high_issue_count,
            "next_actions": list(self.next_actions),
            "summary": dict(self.summary),
            "decision": self.decision,
            "reasons": list(self.reasons),
        }


def build_release_evidence_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    items = [_evidence_item(item) for item in _matrix_payloads(data)]
    issues = _issues(items)
    status = _status(items)
    required_kinds = tuple(str(item) for item in _as_sequence(data.get("required_kinds")))
    missing_kinds = _missing_required_kinds(items, required_kinds)
    if missing_kinds and status != "blocked":
        status = "needs_review"
    if missing_kinds:
        issues.append(
            {
                "code": "release_evidence_required_matrix_missing",
                "severity": "medium",
                "missing_kinds": list(missing_kinds),
            }
        )

    return {
        "kind": "release_evidence_pack",
        "version": 1,
        "ok": status == "ready",
        "status": status,
        "release_id": str(data.get("release_id") or data.get("integration_id") or data.get("task_id") or ""),
        "summary": {
            "matrix_count": len(items),
            "ready_count": sum(1 for item in items if item.decision == "ready"),
            "needs_review_count": sum(1 for item in items if item.decision == "needs_review"),
            "blocked_count": sum(1 for item in items if item.decision == "blocked"),
            "empty_count": sum(1 for item in items if item.decision == "empty"),
            "issue_count": sum(item.issue_count for item in items) + len(missing_kinds),
            "high_issue_count": sum(item.high_issue_count for item in items),
            "missing_required_kind_count": len(missing_kinds),
        },
        "items": [item.as_dict() for item in items],
        "issues": issues,
        "missing_required_kinds": list(missing_kinds),
        "next_actions": _next_actions(items, issues, missing_kinds),
    }


def assess_evidence_matrix(matrix: Mapping[str, Any] | Any) -> EvidencePackItem:
    return _evidence_item(matrix)


def _evidence_item(matrix: Mapping[str, Any] | Any) -> EvidencePackItem:
    payload = _as_mapping(matrix)
    kind = str(payload.get("kind") or payload.get("type") or "unknown")
    name = str(payload.get("name") or payload.get("title") or kind)
    raw_status = _normalize_token(payload.get("status"))
    issues = [_as_mapping(item) for item in _as_sequence(payload.get("issues"))]
    high_issue_count = sum(1 for issue in issues if str(issue.get("severity") or "").lower() == "high")
    ok = _bool(payload.get("ok"), default=raw_status in READY_STATUSES)
    decision, reasons = _decision(raw_status, ok=ok, issue_count=len(issues), high_issue_count=high_issue_count)
    return EvidencePackItem(
        kind=kind,
        name=name,
        status=raw_status or "unknown",
        ok=ok,
        issue_count=len(issues),
        high_issue_count=high_issue_count,
        next_actions=tuple(str(item) for item in _as_sequence(payload.get("next_actions"))),
        summary=_as_mapping(payload.get("summary")),
        decision=decision,
        reasons=tuple(reasons),
    )


def _decision(status: str, *, ok: bool, issue_count: int, high_issue_count: int) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if status in BLOCKED_STATUSES:
        reasons.append("matrix blocked")
    if high_issue_count > 0:
        reasons.append("high severity issues present")
    if status in EMPTY_STATUSES:
        reasons.append("matrix empty or missing")
    if status in REVIEW_STATUSES or (issue_count > 0 and not ok):
        reasons.append("matrix needs review")
    if not ok and status in READY_STATUSES:
        reasons.append("matrix ok flag is false")

    if "matrix blocked" in reasons or "high severity issues present" in reasons:
        return "blocked", reasons
    if "matrix empty or missing" in reasons:
        return "empty", reasons
    if reasons:
        return "needs_review", reasons
    return "ready", ["matrix ready"]


def _issues(items: Sequence[EvidencePackItem]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in items:
        if item.decision == "ready":
            continue
        issues.append(
            {
                "code": _issue_code(item),
                "severity": "high" if item.decision == "blocked" else "medium",
                "kind": item.kind,
                "name": item.name,
                "status": item.status,
                "reasons": list(item.reasons),
            }
        )
    return issues


def _issue_code(item: EvidencePackItem) -> str:
    if "matrix blocked" in item.reasons:
        return "release_evidence_matrix_blocked"
    if "high severity issues present" in item.reasons:
        return "release_evidence_high_severity_issues"
    if "matrix empty or missing" in item.reasons:
        return "release_evidence_matrix_empty"
    if "matrix needs review" in item.reasons:
        return "release_evidence_matrix_needs_review"
    if "matrix ok flag is false" in item.reasons:
        return "release_evidence_ok_flag_false"
    return "release_evidence_item_needs_review"


def _status(items: Sequence[EvidencePackItem]) -> str:
    if not items:
        return "empty"
    if any(item.decision == "blocked" for item in items):
        return "blocked"
    if any(item.decision in {"needs_review", "empty"} for item in items):
        return "needs_review"
    return "ready"


def _next_actions(
    items: Sequence[EvidencePackItem],
    issues: Sequence[Mapping[str, Any]],
    missing_kinds: Sequence[str],
) -> list[str]:
    if not items:
        return ["provide_evidence_matrices"]
    if missing_kinds:
        return ["collect_missing_required_matrices", "rebuild_release_evidence_pack"]
    if any(item.decision == "blocked" for item in items):
        return ["resolve_blocking_evidence_matrices", "rebuild_release_evidence_pack"]
    if issues:
        actions: list[str] = []
        for item in items:
            if item.decision != "ready":
                actions.extend(item.next_actions)
        return list(dict.fromkeys(actions)) or ["review_release_evidence_issues", "decide_integration_readiness"]
    return ["prepare_mainline_integration_review"]


def _missing_required_kinds(items: Sequence[EvidencePackItem], required_kinds: Sequence[str]) -> tuple[str, ...]:
    present = {item.kind for item in items}
    return tuple(kind for kind in required_kinds if kind not in present)


def _matrix_payloads(data: Mapping[str, Any]) -> list[Any]:
    raw = data.get("matrices") or data.get("evidence") or data.get("items") or []
    if isinstance(raw, Mapping):
        return list(raw.values())
    return _as_sequence(raw)


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "ready", "accepted"}


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
