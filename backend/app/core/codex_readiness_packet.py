from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

try:
    from backend.app.core._codex_readiness_packet_core import (
        build_readiness_packet as _build_spec_readiness_packet,
        summarize_readiness_item as _summarize_spec_readiness_item,
    )
    from backend.app.core._codex_readiness_packet_specs import SPECS as _CODEX_PACKET_SPECS
except Exception:  # pragma: no cover - fallback keeps this helper standalone.
    _build_spec_readiness_packet = None
    _summarize_spec_readiness_item = None
    _CODEX_PACKET_SPECS: dict[str, Any] = {}


READY_STATUSES = {
    "ready",
    "passed",
    "success",
    "succeeded",
    "ok",
    "closed",
    "complete",
    "completed",
    "validated",
    "approved",
    "indexed",
    "fresh",
    "merged",
    "sent",
    "acknowledged",
    "accepted",
    "delivered",
    "resolved",
    "available",
    "posted",
    "published",
    "routed",
    "archived",
    "recorded",
    "prepared",
}
OPEN_STATUSES = {"open", "pending", "queued", "running", "needs_review", "needs-review", "in_progress", "in-progress"}
FAILED_STATUSES = {"failed", "failure", "error", "errored", "blocked", "rejected", "regressed", "orphaned", "timeout", "timed_out"}


@dataclass(frozen=True)
class CodexReadinessItem:
    payload: dict[str, Any]
    readiness_state: str
    missing_refs: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.payload[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def as_dict(self) -> dict[str, Any]:
        data = dict(self.payload)
        data["readiness_state"] = self.readiness_state
        data["missing_refs"] = list(self.missing_refs)
        data["warnings"] = list(self.warnings)
        data["blockers"] = list(self.blockers)
        return data


def summarize_codex_readiness_item(
    item: Mapping[str, Any] | Any,
    *,
    prefix: str,
    required_refs: Sequence[str] = (),
    conditional_refs: Mapping[str, Sequence[str]] | None = None,
    failed_code: str | None = None,
    live_code: str | None = None,
    open_warning_code: str | None = None,
    residual_ref: str | None = None,
) -> CodexReadinessItem:
    spec_domain = _spec_domain_from_prefix(prefix)
    if spec_domain and _summarize_spec_readiness_item is not None:
        return _summarize_spec_readiness_item(spec_domain, item)

    payload = _as_mapping(item)
    _normalize_payload_tokens(payload)
    status = _normalize_token(
        payload.get("status")
        or payload.get("state")
        or payload.get("readiness_state")
        or payload.get("gate_status")
        or payload.get("approval_status")
        or payload.get("command_status")
        or payload.get("delivery_status")
        or payload.get("decision_status")
        or payload.get("review_status")
        or payload.get("receipt_status")
        or payload.get("closure_status")
        or payload.get("handoff_status")
        or payload.get("session_status")
        or payload.get("diff_status")
        or "ready"
    )
    missing_refs = _missing_refs(payload, required_refs)
    for trigger, refs in (conditional_refs or {}).items():
        if _triggered(payload, trigger):
            for ref in _missing_refs(payload, refs):
                missing_refs.append(ref)
    warnings: list[str] = []
    blockers: list[str] = []

    queue_state = _normalize_token(payload.get("queue_state") or payload.get("orphan_state"))
    failed_status = (
        status in FAILED_STATUSES
        or queue_state in FAILED_STATUSES
        or _has_failed_status_list(payload)
        or (status == "stale" and failed_code and "archive" in prefix)
    )
    if status in FAILED_STATUSES:
        blockers.append(failed_code or f"{prefix}_status_failed")
    elif failed_status:
        blockers.append(failed_code)
    elif status in OPEN_STATUSES and not (prefix == "codex_background_task_readiness" and status in {"queued", "running"}):
        warnings.append(open_warning_code or f"{prefix}_still_open")

    live_blocker = _live_operation_blocker(payload, live_code)
    if live_blocker:
        blockers.append(live_blocker)
        blockers.append(_live_attempt_blocker(prefix))

    if _truthy_any(
        payload,
        (
            "residual_risk_detected",
            "residual_gap_detected",
            "risk_detected",
            "skipped_items_detected",
            "blocked_followups_detected",
            "decision_needs_review",
            "final_decision_needs_review",
            "owner_signoff_pending",
            "filter_review_required",
            "recipient_review_required",
            "suppression_review_required",
            "timestamp_missing",
        ),
    ):
        if residual_ref and residual_ref not in missing_refs and not _has_value(payload.get(residual_ref)):
            missing_refs.append(residual_ref)
        warnings.append(_warning_from_payload(prefix, payload))

    if status == "stale" and not blockers:
        warnings.append(f"{prefix}_stale")
    if payload.get("enabled") is False:
        blockers.append(f"{prefix}_source_disabled")
    if failed_status:
        for ref in _missing_refs(payload, (conditional_refs or {}).get("needs_failure_evidence", ())):
            missing_refs.append(ref)
    if queue_state in FAILED_STATUSES:
        blockers.append("queue_state_not_recoverable")

    readiness_state = "ready"
    if blockers:
        readiness_state = "blocked"
    elif missing_refs or warnings:
        readiness_state = "needs_review"

    return CodexReadinessItem(
        payload=payload,
        readiness_state=readiness_state,
        missing_refs=tuple(dict.fromkeys(missing_refs)),
        warnings=tuple(dict.fromkeys(warnings)),
        blockers=tuple(dict.fromkeys(blockers)),
    )


def build_codex_readiness_packet(
    payload: Mapping[str, Any],
    *,
    kind: str,
    collection_key: str,
    required_packet_refs: Sequence[str] = (),
    packet_missing_refs: Sequence[str] = (),
    required_item_refs: Sequence[str] = (),
    conditional_refs: Mapping[str, Sequence[str]] | None = None,
    ready_actions: Sequence[str] = (),
    empty_actions: Sequence[str] = (),
    packet_missing_actions: Sequence[str] = (),
    blocked_actions: Sequence[str] = (),
    review_actions: Sequence[str] = (),
    prefix: str | None = None,
    failed_code: str | None = None,
    missing_code: str | None = None,
    packet_missing_code: str | None = None,
    live_code: str | None = None,
    summary_ref_field: str | None = None,
    summary_ref_count_key: str | None = None,
    open_warning_code: str | None = None,
    residual_ref: str | None = None,
) -> dict[str, Any]:
    spec_domain = _spec_domain_from_kind(kind)
    if spec_domain and _build_spec_readiness_packet is not None:
        return _build_spec_readiness_packet(spec_domain, payload)

    data = dict(payload)
    prefix = prefix or kind.removesuffix("_packet")
    items = _items_from_payload(data, collection_key)
    if not data or not items:
        return {
            "kind": kind,
            "version": 1,
            "ok": False,
            "status": "empty",
            "summary": _summary([], collection_key, summary_ref_field, summary_ref_count_key),
            collection_key: [],
            "findings": [],
            "packet_missing_refs": [],
            "next_actions": list(empty_actions) or [f"provide_{prefix}_inventory"],
        }

    packet_missing = _packet_missing_refs(data, required_packet_refs, packet_missing_refs)
    summarized = [
        summarize_codex_readiness_item(
            item,
            prefix=prefix,
            required_refs=required_item_refs,
            conditional_refs=conditional_refs,
            failed_code=failed_code,
            live_code=live_code,
            open_warning_code=open_warning_code,
            residual_ref=residual_ref,
        )
        for item in items
    ]

    status = _packet_status(packet_missing, summarized)
    findings = _findings(
        packet_missing=packet_missing,
        summarized=summarized,
        packet_missing_code=packet_missing_code or f"{prefix}_packet_missing_evidence",
        missing_code=missing_code or f"{prefix}_missing_evidence",
    )

    packet = {
        "kind": kind,
        "version": 1,
        "ok": status == "ready",
        "status": status,
        "summary": _summary(summarized, collection_key, summary_ref_field, summary_ref_count_key),
        collection_key: [item.as_dict() for item in summarized],
        "findings": findings,
        "packet_missing_refs": packet_missing,
        "next_actions": _next_actions(
            status,
            ready_actions=ready_actions,
            empty_actions=empty_actions,
            packet_missing_actions=packet_missing_actions,
            blocked_actions=blocked_actions,
            review_actions=review_actions,
            packet_missing=packet_missing,
            prefix=prefix,
        ),
    }
    packet["review_findings"] = findings
    return packet


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


def _normalize_payload_tokens(payload: dict[str, Any]) -> None:
    for key in (
        "status",
        "state",
        "readiness_state",
        "gate_status",
        "approval_status",
        "command_status",
        "delivery_status",
        "provider",
    ):
        value = payload.get(key)
        if isinstance(value, str):
            payload[key] = _normalize_token(value)


def _as_sequence(value: Any) -> list[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []


def _items_from_payload(data: Mapping[str, Any], collection_key: str) -> list[Any]:
    direct = _as_sequence(data.get(collection_key))
    if direct:
        return direct
    singleton_keys = [
        key
        for key, value in data.items()
        if isinstance(value, Mapping) and not key.endswith("_policy") and not key.endswith("_ref")
    ]
    if singleton_keys:
        return [{**_as_mapping(data[key]), "source_type": key, "component_type": key} for key in singleton_keys]
    if data and not any(isinstance(value, (list, tuple)) for value in data.values()):
        return [data]
    return []


def _packet_missing_refs(
    data: Mapping[str, Any],
    required_packet_refs: Sequence[str],
    display_refs: Sequence[str] = (),
) -> list[str]:
    missing: list[str] = []
    for index, key in enumerate(required_packet_refs):
        if _has_value(data.get(key)):
            continue
        if index < len(display_refs):
            missing.append(str(display_refs[index]))
            continue
        if key.endswith("_policy"):
            missing.append(f"{key}_ref")
        elif key == "queue_ref":
            missing.append("task_queue_ref")
        else:
            missing.append(key)
    return missing


def _missing_refs(payload: Mapping[str, Any], required_refs: Sequence[str]) -> list[str]:
    missing: list[str] = []
    for ref in required_refs:
        if not _has_ref(payload, ref):
            missing.append(ref)
    return missing


def _has_ref(payload: Mapping[str, Any], ref: str) -> bool:
    if _has_value(payload.get(ref)):
        return True
    if ref.endswith("_ref") and _has_value(payload.get(f"{ref}s")):
        return True
    if ref.endswith("_refs") and _has_value(payload.get(ref.removesuffix("s"))):
        return True

    alternatives = {
        "artifact_policy_ref": ("artifact_policy",),
        "evidence_index_policy_ref": ("evidence_index_policy",),
        "provenance_policy_ref": ("provenance_policy",),
        "retention_policy_ref": ("retention_policy",),
        "work_product_governance_ref": ("work_product_governance",),
        "retry_policy_ref": ("retry_policy",),
        "resumability_policy_ref": ("resumability_policy",),
        "task_queue_ref": ("queue_ref",),
        "required_check_policy_ref": ("required_check_policy",),
        "workflow_policy_ref": ("workflow_policy",),
        "review_posting_policy_ref": ("review_posting_policy",),
        "diff_or_pr_refs": ("diff_refs", "pr_refs", "diff_ref", "pr_ref"),
        "resumability_ref": ("resumability_refs", "resumable"),
        "failure_handoff_refs": ("handoff_refs", "handoff_ref"),
        "retry_or_rerun_refs": ("retry_refs", "rerun_refs", "retry_ref", "rerun_ref"),
        "session_or_visual_evidence_ref": (
            "session_ref",
            "visual_evidence_ref",
            "visual_evidence_refs",
            "screenshot_refs",
            "validation_refs",
        ),
    }
    return any(_has_value(payload.get(key)) for key in alternatives.get(ref, ()))


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if value is False:
        return False
    if isinstance(value, (str, bytes)):
        return bool(value)
    if isinstance(value, (Sequence, Mapping)):
        return bool(value)
    return True


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _truthy_any(payload: Mapping[str, Any], keys: Sequence[str]) -> bool:
    return any(bool(payload.get(key)) for key in keys)


def _triggered(payload: Mapping[str, Any], trigger: str) -> bool:
    aliases = {
        "integrity_claimed": ("integrity_claimed", "checksum_claimed"),
        "residual_risk_detected": ("residual_risk_detected", "residual_risk_present"),
        "residual_gap_detected": ("residual_gap_detected", "residual_gap_present"),
        "timestamp_missing": ("timestamp_missing", "decision_timestamp_missing", "receipt_timestamp_missing"),
    }
    return any(bool(payload.get(key)) for key in aliases.get(trigger, (trigger,)))


def _has_failed_status_list(payload: Mapping[str, Any]) -> bool:
    for key, value in payload.items():
        if not (key.endswith("_states") or key.endswith("_statuses")):
            continue
        if any(_normalize_token(item) in FAILED_STATUSES for item in _as_sequence(value)):
            return True
    return False


def _live_operation_blocker(payload: Mapping[str, Any], live_code: str | None) -> str | None:
    for key, value in payload.items():
        if not value:
            continue
        if "mutation_attempted" in key or "live_operation" in key or "live_dispatch" in key or "live_execution" in key:
            return live_code or "codex_live_operation_blocked"
        if key in {"storage_mutation_attempted", "scoring_mutation_attempted", "file_write_attempted", "admin_mutation_attempted"}:
            return live_code or "codex_live_operation_blocked"
    return None


def _live_attempt_blocker(prefix: str) -> str:
    label = prefix
    if label.startswith("codex_") and not label.startswith("codex_secondary_"):
        label = label.removeprefix("codex_")
    label = label.removesuffix("_readiness")
    return f"live_{label}_operation_attempted"


def _warning_from_payload(prefix: str, payload: Mapping[str, Any]) -> str:
    for key in (
        "timestamp_missing",
        "filter_review_required",
        "recipient_review_required",
        "suppression_review_required",
        "decision_needs_review",
        "final_decision_needs_review",
        "owner_signoff_pending",
        "blocked_followups_detected",
        "residual_risk_detected",
        "residual_gap_detected",
        "risk_detected",
        "skipped_items_detected",
    ):
        if payload.get(key):
            return f"{prefix}_{key.removesuffix('_detected')}"
    return f"{prefix}_needs_review"


def _packet_status(packet_missing: Sequence[str], summarized: Sequence[CodexReadinessItem]) -> str:
    if any(item.readiness_state == "blocked" for item in summarized):
        return "blocked"
    if packet_missing or any(item.readiness_state == "needs_review" for item in summarized):
        return "needs_review"
    return "ready"


def _findings(
    *,
    packet_missing: Sequence[str],
    summarized: Sequence[CodexReadinessItem],
    packet_missing_code: str,
    missing_code: str,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if packet_missing:
        findings.append({"code": packet_missing_code, "severity": "medium", "missing_refs": list(packet_missing)})
    for item in summarized:
        for blocker in item.blockers:
            findings.append({"code": blocker, "severity": "high", "missing_refs": list(item.missing_refs)})
        if item.missing_refs and not item.blockers:
            findings.append({"code": missing_code, "severity": "medium", "missing_refs": list(item.missing_refs)})
        for warning in item.warnings:
            findings.append({"code": warning, "severity": "medium", "missing_refs": list(item.missing_refs)})
    return findings


def _summary(
    summarized: Sequence[CodexReadinessItem],
    collection_key: str,
    summary_ref_field: str | None,
    summary_ref_count_key: str | None,
) -> dict[str, Any]:
    singular = _singular(collection_key)
    summary = {
        f"{singular}_count": len(summarized),
        "ready_count": sum(1 for item in summarized if item.readiness_state == "ready"),
        "needs_review_count": sum(1 for item in summarized if item.readiness_state == "needs_review"),
        "blocked_count": sum(1 for item in summarized if item.readiness_state == "blocked"),
        "missing_ref_count": sum(len(item.missing_refs) for item in summarized),
    }
    if summary_ref_field and summary_ref_count_key:
        summary[summary_ref_count_key] = sum(_summary_ref_count(item.payload, summary_ref_field) for item in summarized)
    summary["remote_task_count"] = sum(
        1
        for item in summarized
        if item.payload.get("remote_execution_ref")
        or _normalize_token(item.payload.get("task_type")) in {"cloud", "remote", "background"}
    )
    total_token_budget = sum(_int(item.payload.get("token_budget")) for item in summarized)
    if total_token_budget:
        summary["total_token_budget"] = total_token_budget
    by_component_type: dict[str, int] = {}
    for item in summarized:
        component_type = _normalize_token(item.payload.get("component_type") or item.payload.get("source_type"))
        if component_type:
            if component_type == "mcp_tools":
                component_type = "mcp"
            by_component_type[component_type] = by_component_type.get(component_type, 0) + 1
    if by_component_type:
        summary["by_component_type"] = by_component_type
    return summary


def _singular(collection_key: str) -> str:
    irregular = {"reproducibility": "repro", "visibility_items": "visibility_item"}
    if collection_key in irregular:
        return irregular[collection_key]
    if collection_key.endswith("ies"):
        return f"{collection_key[:-3]}y"
    if collection_key.endswith("s"):
        return collection_key[:-1]
    return collection_key


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _summary_ref_count(payload: Mapping[str, Any], field: str) -> int:
    direct = _as_sequence(payload.get(field))
    if direct:
        return len(direct)
    stem = field.removesuffix("s").removesuffix("_ref")
    tokens = [token for token in stem.split("_") if token]
    total = 0
    for key, value in payload.items():
        if key.endswith("_refs") and (stem in key or all(token in key for token in tokens)):
            total += len(_as_sequence(value))
    return total


def _next_actions(
    status: str,
    *,
    ready_actions: Sequence[str],
    empty_actions: Sequence[str],
    packet_missing_actions: Sequence[str],
    blocked_actions: Sequence[str],
    review_actions: Sequence[str],
    packet_missing: Sequence[str],
    prefix: str,
) -> list[str]:
    if status == "ready":
        return list(ready_actions) or [f"share_{prefix}_with_mainline"]
    if status == "blocked":
        return list(blocked_actions) or [f"resolve_{prefix}_blockers", f"refresh_{prefix}_readiness"]
    if packet_missing and packet_missing_actions:
        return list(packet_missing_actions)
    if review_actions:
        return list(review_actions)
    return [f"attach_{prefix}_evidence", f"refresh_{prefix}_readiness"]


def _spec_domain_from_kind(kind: str) -> str | None:
    raw = kind.removeprefix("codex_")
    candidates = [raw]
    if raw.endswith("_packet"):
        candidates.append(raw.removesuffix("_packet"))
    if raw.endswith("_readiness_packet"):
        candidates.append(raw.removesuffix("_readiness_packet"))
    for candidate in candidates:
        if candidate in _CODEX_PACKET_SPECS:
            return candidate
    return None


def _spec_domain_from_prefix(prefix: str) -> str | None:
    raw = prefix.removeprefix("codex_")
    candidates = [raw]
    if raw.endswith("_readiness"):
        candidates.append(raw.removesuffix("_readiness"))
    for candidate in candidates:
        if candidate in _CODEX_PACKET_SPECS:
            return candidate
    return None
