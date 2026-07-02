from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


PASS_STATUSES = {"pass", "passed", "success", "successful", "accepted", "ok", "complete", "completed"}
FAIL_STATUSES = {"fail", "failed", "failure", "error", "blocked", "rejected"}
MISSING_STATUSES = {"", "missing", "unknown", "not_run", "not-run", "pending"}


@dataclass(frozen=True)
class AgentEvalCriterion:
    criterion_id: str
    label: str
    required: bool = True
    min_score: float = 0.75
    evidence_required: bool = True
    regression_tolerance: float = 0.15


@dataclass(frozen=True)
class AgentEvalRow:
    criterion_id: str
    label: str
    required: bool
    status: str
    score: float
    min_score: float
    evidence_count: int
    evidence_required: bool
    baseline_score: float | None
    regression_delta: float
    decision: str
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "label": self.label,
            "required": self.required,
            "status": self.status,
            "score": self.score,
            "min_score": self.min_score,
            "evidence_count": self.evidence_count,
            "evidence_required": self.evidence_required,
            "baseline_score": self.baseline_score,
            "regression_delta": self.regression_delta,
            "decision": self.decision,
            "reasons": list(self.reasons),
        }


def build_agent_eval_matrix(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    criteria = _criteria(data)
    results_by_id = _results_by_id(data)
    baseline_by_id = _baseline_by_id(data)
    evidence_by_id = _evidence_by_id(data)

    rows = [
        evaluate_agent_task_result(
            criterion,
            results_by_id.get(criterion.criterion_id),
            baseline_by_id.get(criterion.criterion_id),
            evidence_by_id.get(criterion.criterion_id, []),
        )
        for criterion in criteria
    ]
    issues = _issues(rows)
    status = _status(rows, issues)
    accepted_count = sum(1 for row in rows if row.decision == "accepted")
    blocked_count = sum(1 for row in rows if row.decision == "blocked")
    review_count = sum(1 for row in rows if row.decision == "needs_review")
    score = round(sum(row.score for row in rows) / len(rows), 2) if rows else 0.0

    return {
        "kind": "agent_eval_matrix",
        "version": 1,
        "ok": status == "accepted",
        "status": status,
        "task_id": str(data.get("task_id") or data.get("id") or ""),
        "goal": str(data.get("goal") or data.get("objective") or ""),
        "summary": {
            "criteria_count": len(rows),
            "accepted_count": accepted_count,
            "needs_review_count": review_count,
            "blocked_count": blocked_count,
            "missing_count": sum(1 for row in rows if row.status == "missing"),
            "regression_count": sum(1 for row in rows if row.regression_delta < 0),
            "score": score,
        },
        "rows": [row.as_dict() for row in rows],
        "issues": issues,
        "next_actions": _next_actions(rows, issues),
    }


def evaluate_agent_task_result(
    criterion: AgentEvalCriterion | Mapping[str, Any] | Any,
    result: Mapping[str, Any] | Any | None = None,
    baseline: Mapping[str, Any] | Any | None = None,
    evidence: Sequence[Any] | None = None,
) -> AgentEvalRow:
    normalized_criterion = _criterion(criterion)
    result_payload = _as_mapping(result)
    baseline_payload = _as_mapping(baseline)
    status = _normalize_status(result_payload.get("status"))
    score = _score(result_payload, status)
    baseline_score = _baseline_score(baseline_payload)
    regression_delta = round(score - baseline_score, 2) if baseline_score is not None else 0.0
    evidence_count = _evidence_count(result_payload, evidence or [])
    decision, reasons = _decision(
        normalized_criterion,
        status=status,
        score=score,
        evidence_count=evidence_count,
        regression_delta=regression_delta,
    )
    return AgentEvalRow(
        criterion_id=normalized_criterion.criterion_id,
        label=normalized_criterion.label,
        required=normalized_criterion.required,
        status=status,
        score=score,
        min_score=normalized_criterion.min_score,
        evidence_count=evidence_count,
        evidence_required=normalized_criterion.evidence_required,
        baseline_score=baseline_score,
        regression_delta=regression_delta,
        decision=decision,
        reasons=tuple(reasons),
    )


def _criteria(data: Mapping[str, Any]) -> list[AgentEvalCriterion]:
    raw = _as_sequence(data.get("criteria") or data.get("acceptance_criteria"))
    if not raw:
        raw = _as_sequence(data.get("results") or data.get("task_results"))
    return [_criterion(item) for item in raw]


def _criterion(value: AgentEvalCriterion | Mapping[str, Any] | Any) -> AgentEvalCriterion:
    if isinstance(value, AgentEvalCriterion):
        return value
    payload = _as_mapping(value)
    criterion_id = str(payload.get("criterion_id") or payload.get("id") or payload.get("name") or "")
    label = str(payload.get("label") or payload.get("title") or payload.get("name") or criterion_id)
    required = _bool(payload.get("required"), default=True)
    return AgentEvalCriterion(
        criterion_id=criterion_id,
        label=label,
        required=required,
        min_score=_normalize_score(_float(payload.get("min_score") or payload.get("threshold") or 0.75)),
        evidence_required=_bool(payload.get("evidence_required"), default=required),
        regression_tolerance=_normalize_score(_float(payload.get("regression_tolerance") or 0.15)),
    )


def _results_by_id(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_results = data.get("results") or data.get("task_results") or {}
    if isinstance(raw_results, Mapping):
        return {str(key): _as_mapping(value) for key, value in raw_results.items()}
    return {
        str(item.get("criterion_id") or item.get("id") or item.get("name") or ""): item
        for item in (_as_mapping(value) for value in _as_sequence(raw_results))
    }


def _baseline_by_id(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    baseline = data.get("baseline") or data.get("previous") or {}
    if isinstance(baseline, Mapping) and not any(key in baseline for key in ("criterion_id", "id", "score", "status")):
        return {str(key): _as_mapping(value) for key, value in baseline.items()}
    return {
        str(item.get("criterion_id") or item.get("id") or item.get("name") or ""): item
        for item in (_as_mapping(value) for value in _as_sequence(baseline))
    }


def _evidence_by_id(data: Mapping[str, Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    evidence = data.get("evidence") or data.get("artifacts") or []
    if isinstance(evidence, Mapping):
        for key, value in evidence.items():
            grouped[str(key)] = _as_sequence(value) or [value]
        return grouped
    for item in _as_sequence(evidence):
        payload = _as_mapping(item)
        criterion_id = str(payload.get("criterion_id") or payload.get("id") or payload.get("name") or "")
        if criterion_id:
            grouped.setdefault(criterion_id, []).append(item)
    return grouped


def _decision(
    criterion: AgentEvalCriterion,
    *,
    status: str,
    score: float,
    evidence_count: int,
    regression_delta: float,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if status == "missing":
        reasons.append("result missing")
    elif status == "failed":
        reasons.append("result failed")
    if score < criterion.min_score:
        reasons.append("score below threshold")
    if criterion.evidence_required and evidence_count == 0:
        reasons.append("evidence missing")
    if regression_delta < -criterion.regression_tolerance:
        reasons.append("regression beyond tolerance")

    if not reasons:
        return "accepted", ["criterion accepted"]
    if criterion.required and any(reason in reasons for reason in ("result missing", "result failed", "score below threshold")):
        return "blocked", reasons
    if criterion.required and "evidence missing" in reasons:
        return "blocked", reasons
    return "needs_review", reasons


def _issues(rows: Sequence[AgentEvalRow]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in rows:
        if row.decision == "accepted":
            continue
        if row.status == "missing":
            code = "agent_eval_required_criterion_missing" if row.required else "agent_eval_optional_criterion_missing"
        elif row.status == "failed":
            code = "agent_eval_required_criterion_failed" if row.required else "agent_eval_optional_criterion_failed"
        elif row.regression_delta < 0:
            code = "agent_eval_regression_detected"
        elif row.evidence_required and row.evidence_count == 0:
            code = "agent_eval_evidence_missing"
        else:
            code = "agent_eval_threshold_not_met"
        issues.append(
            {
                "code": code,
                "severity": "high" if row.decision == "blocked" else "medium",
                "criterion_id": row.criterion_id,
                "reasons": list(row.reasons),
            }
        )
    return issues


def _status(rows: Sequence[AgentEvalRow], issues: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "empty"
    if any(row.decision == "blocked" for row in rows):
        return "blocked"
    if issues:
        return "needs_review"
    return "accepted"


def _next_actions(rows: Sequence[AgentEvalRow], issues: Sequence[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return ["provide_acceptance_criteria_and_task_results"]
    codes = {str(issue.get("code") or "") for issue in issues}
    if any(code.endswith("_missing") for code in codes):
        return ["collect_missing_results_or_evidence", "rerun_agent_eval_matrix"]
    if "agent_eval_required_criterion_failed" in codes:
        return ["fix_required_task_failures", "rerun_agent_eval_matrix"]
    if "agent_eval_regression_detected" in codes:
        return ["review_regression_delta", "compare_against_baseline"]
    if issues:
        return ["review_eval_issues", "decide_release_readiness"]
    return ["prepare_release_or_review_handoff"]


def _normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in PASS_STATUSES:
        return "passed"
    if status in FAIL_STATUSES:
        return "failed"
    if status in MISSING_STATUSES:
        return "missing"
    return "needs_review"


def _score(result: Mapping[str, Any], status: str) -> float:
    if "score" in result:
        return _normalize_score(_float(result.get("score")))
    if status == "passed":
        return 1.0
    if status == "failed":
        return 0.0
    return 0.0


def _baseline_score(baseline: Mapping[str, Any]) -> float | None:
    if not baseline:
        return None
    if "score" in baseline:
        return _normalize_score(_float(baseline.get("score")))
    return None


def _evidence_count(result: Mapping[str, Any], evidence: Sequence[Any]) -> int:
    count = len([item for item in evidence if item])
    count += len(_as_sequence(result.get("evidence")))
    count += len(_as_sequence(result.get("artifacts")))
    return count


def _normalize_score(score: float) -> float:
    if score > 1.0:
        return round(max(0.0, min(1.0, score / 100.0)), 2)
    return round(max(0.0, min(1.0, score)), 2)


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "required"}


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
