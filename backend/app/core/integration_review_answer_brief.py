from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewAnswerBriefItem:
    candidate_id: str
    question: str
    answer: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    missing_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    status: str = "needs_review"
    confidence: str = "low"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "question": self.question,
            "answer": self.answer,
            "evidence_refs": list(self.evidence_refs),
            "missing_refs": list(self.missing_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "status": self.status,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
        }


def summarize_review_answer_brief_item(
    item: Mapping[str, Any] | Any,
    *,
    question_hints: Mapping[str, str] | None = None,
    blocked_refs: set[str] | None = None,
) -> ReviewAnswerBriefItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or payload.get("id") or "")
    evidence_refs = tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs") or payload.get("matched_refs")))
    missing_refs = tuple(str(ref) for ref in _as_sequence(payload.get("missing_refs")))
    status = str(payload.get("status") or "needs_review")
    question = str(
        payload.get("question")
        or (question_hints or {}).get(candidate_id)
        or f"Is {candidate_id or 'this candidate'} ready for mainline review?"
    )
    answer = str(
        payload.get("answer")
        or (
            "Ready for mainline review with attached evidence."
            if status in {"ready", "passed"} and not missing_refs
            else "Review after missing evidence is resolved."
        )
    )
    reasons: list[str] = []
    if missing_refs:
        reasons.append("answer evidence incomplete")
    if status == "blocked" or evidence_refs and set(evidence_refs) & (blocked_refs or set()):
        status = "blocked"
        reasons.append("answer source blocked")
    confidence = "high" if status in {"ready", "passed"} and evidence_refs and not missing_refs else "low"
    return ReviewAnswerBriefItem(
        candidate_id=candidate_id,
        question=question,
        answer=answer,
        evidence_refs=evidence_refs,
        missing_refs=missing_refs,
        owner=str(payload.get("owner") or ""),
        reviewer=str(payload.get("reviewer") or ""),
        status=status,
        confidence=confidence,
        reasons=tuple(reasons or ["answer ready"] if confidence == "high" else reasons),
    )


def build_integration_review_answer_brief(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw_items = _answer_items(data)
    if not raw_items:
        return {
            "kind": "integration_review_answer_brief",
            "brief_id": str(data.get("brief_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"answer_count": 0, "high_confidence_count": 0},
            "answers": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_answer_brief_inputs"],
        }
    blocked_refs = _blocked_refs(data)
    hints = _as_mapping(data.get("question_hints"))
    answers = [summarize_review_answer_brief_item(item, question_hints=hints, blocked_refs=blocked_refs) for item in raw_items]
    blocked = [item.candidate_id for item in answers if item.status == "blocked"]
    review = [item.candidate_id for item in answers if item.status not in {"ready", "passed", "blocked"} or item.missing_refs]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_review_answer_blockers", "rebuild_integration_review_answer_brief"]
    elif review:
        status = "needs_review"
        next_actions = ["attach_review_answer_evidence", "rebuild_integration_review_answer_brief"]
    else:
        status = "ready"
        next_actions = ["share_review_answer_brief_with_mainline"]
    return {
        "kind": "integration_review_answer_brief",
        "brief_id": str(data.get("brief_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "answer_count": len(answers),
            "high_confidence_count": sum(1 for item in answers if item.confidence == "high"),
        },
        "answers": [item.as_dict() for item in answers],
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _answer_items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("answers"):
        return _as_sequence(data.get("answers"))
    digest = _as_mapping(data.get("query_result_digest"))
    return _as_sequence(digest.get("digests"))


def _blocked_refs(data: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    index = _as_mapping(data.get("review_evidence_index"))
    for record in _as_sequence(index.get("records")):
        payload = _as_mapping(record)
        if payload.get("status") == "blocked":
            ref = str(payload.get("ref") or "")
            if ref:
                refs.add(ref)
    return refs


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
