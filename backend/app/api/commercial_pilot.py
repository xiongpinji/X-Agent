"""Read-only commercial pilot report APIs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"

router = APIRouter(prefix="/api/v1/commercial-pilot/feishu", tags=["commercial-pilot"])


@dataclass(frozen=True)
class ReportSpec:
    name: str
    filename: str
    required: bool = True
    expected_statuses: frozenset[str] = frozenset()
    expected_evidence_type: str | None = None


REPORT_SPECS = (
    ReportSpec(
        "acceptance_gate",
        "commercial-pilot-acceptance-gate.json",
        expected_statuses=frozenset({"pilot_acceptance_ready"}),
        expected_evidence_type="commercial_pilot_acceptance_gate",
    ),
    ReportSpec(
        "handoff_index",
        "commercial-pilot-handoff-index.json",
        expected_statuses=frozenset({"handoff_index_ready"}),
        expected_evidence_type="commercial_pilot_handoff_index",
    ),
    ReportSpec(
        "final_gate",
        "commercial-pilot-final-gate.json",
        expected_statuses=frozenset({"final_gate_ready"}),
        expected_evidence_type="commercial_pilot_final_gate",
    ),
    ReportSpec(
        "delivery_receipt",
        "commercial-pilot-delivery-receipt.json",
        expected_statuses=frozenset({"delivery_receipt_ready"}),
        expected_evidence_type="commercial_pilot_delivery_receipt",
    ),
    ReportSpec(
        "handoff_status",
        "commercial-pilot-handoff-status.json",
        expected_statuses=frozenset({"pilot_handoff_ready"}),
    ),
    ReportSpec(
        "operator_status",
        "commercial-pilot-ops-status.json",
        expected_statuses=frozenset({"pilot_ops_ready"}),
    ),
    ReportSpec(
        "delivery_manifest",
        "commercial-pilot-delivery-manifest.json",
        expected_statuses=frozenset({"delivery_manifest_ready"}),
        expected_evidence_type="commercial_pilot_delivery_manifest",
    ),
    ReportSpec(
        "feishu_inbound_live",
        "commercial-pilot-feishu-live.json",
        expected_statuses=frozenset({"passed"}),
        expected_evidence_type="commercial_pilot_feishu_live",
    ),
    ReportSpec(
        "channel_readiness",
        "commercial-pilot-channel-readiness.json",
        expected_statuses=frozenset({"ready", "ready_with_owner_gates"}),
    ),
    ReportSpec(
        "rc_delivery_status",
        "rc-delivery-status.json",
        expected_statuses=frozenset({"commercial_rc_ready"}),
    ),
)

WATCHED_MUTATION_REPORTS = {
    "acceptance_gate",
    "handoff_index",
    "final_gate",
    "delivery_receipt",
    "feishu_inbound_live",
}


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"report not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read report {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {_display_path(path)}"
    return payload, None


def _sha256_file(path: Path) -> tuple[str | None, int | None, str | None]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None, f"report not found: {_display_path(path)}"
    except OSError as exc:
        return None, None, f"could not read report {_display_path(path)}: {exc}"
    return hashlib.sha256(data).hexdigest(), len(data), None


def _report_summary(spec: ReportSpec, report_dir: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    path = report_dir / spec.filename
    payload, read_error = _read_json(path)
    sha256, size_bytes, digest_error = _sha256_file(path)
    report_status = payload.get("status") if payload else None
    evidence_type = payload.get("evidence_type") if payload else None
    errors = [error for error in [read_error, digest_error] if error]
    summary_status = "missing" if errors and spec.required else "optional_missing" if errors else "present"

    if payload:
        if payload.get("full_codex_parity_claimed") is True:
            summary_status = "failed"
            errors.append("report claims full Codex parity")
        elif spec.expected_statuses and report_status not in spec.expected_statuses:
            summary_status = "action_required" if spec.required else "preview"
            errors.append(f"report status {report_status!r} is not accepted")
        elif spec.expected_evidence_type and evidence_type != spec.expected_evidence_type:
            summary_status = "failed" if spec.required else "preview"
            errors.append("report evidence_type is not accepted")
        else:
            summary_status = "passed" if spec.required else "present"

    return (
        {
            "name": spec.name,
            "path": _display_path(path),
            "required": spec.required,
            "status": summary_status,
            "report_status": report_status,
            "evidence_type": evidence_type,
            "sha256": sha256,
            "size_bytes": size_bytes,
            "error": "; ".join(errors) if errors else None,
        },
        payload,
    )


def _check_required_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    missing_or_invalid = [
        report["name"]
        for report in reports
        if report["required"] and report["status"] not in {"passed", "present"}
    ]
    if missing_or_invalid:
        hard_failed = [
            report["name"]
            for report in reports
            if report["required"] and report["status"] == "failed"
        ]
        return {
            "name": "required_reports",
            "status": "failed" if hard_failed else "action_required",
            "details": {"missing_or_invalid": missing_or_invalid},
            "error": "one or more required pilot reports are missing or invalid",
        }
    return {"name": "required_reports", "status": "passed", "details": {"count": len(reports)}, "error": None}


def _check_ready(payload: dict[str, Any] | None, *, name: str, expected: str) -> dict[str, Any]:
    actual = payload.get("status") if payload else None
    passed = actual == expected
    return {
        "name": name,
        "status": "passed" if passed else "action_required",
        "details": {"actual": actual, "expected": expected},
        "error": None if passed else f"{name} is not {expected}",
    }


def _check_no_parity_claim(payloads: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    claimers = [
        name
        for name, payload in payloads.items()
        if isinstance(payload, dict) and payload.get("full_codex_parity_claimed") is True
    ]
    if claimers:
        return {
            "name": "no_full_codex_parity_claim",
            "status": "failed",
            "details": {"claiming_reports": claimers},
            "error": "one or more pilot reports claim full Codex parity",
        }
    return {
        "name": "no_full_codex_parity_claim",
        "status": "passed",
        "details": {"full_codex_parity_claimed": False},
        "error": None,
    }


def _check_no_mutation(payloads: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    observed: dict[str, Any] = {}
    offenders: list[str] = []
    for name in sorted(WATCHED_MUTATION_REPORTS):
        payload = payloads.get(name)
        if not isinstance(payload, dict):
            continue
        mutation = payload.get("mutation_performed")
        outbound = payload.get("outbound_message_sent")
        observed[f"{name}.mutation_performed"] = mutation
        observed[f"{name}.outbound_message_sent"] = outbound
        if mutation is not False:
            offenders.append(f"{name}.mutation_performed")
        if outbound is not False:
            offenders.append(f"{name}.outbound_message_sent")
    if offenders:
        return {
            "name": "no_pilot_report_mutation",
            "status": "failed",
            "details": {"observed": observed, "offenders": offenders},
            "error": "pilot reports must not record final gate or inbound outbound mutation",
        }
    return {"name": "no_pilot_report_mutation", "status": "passed", "details": {"observed": observed}, "error": None}


def _inbound_event_audit(payload: dict[str, Any] | None) -> dict[str, Any]:
    expected = {
        "status": "passed",
        "channel": "feishu",
        "evidence_type": "commercial_pilot_feishu_live",
        "event_type": "im.message.receive_v1",
        "tenant_key_present": True,
        "message_id_present": True,
        "chat_id_present": True,
        "content_present": True,
        "encrypted_callback": True,
        "mutation_performed": False,
        "outbound_message_sent": False,
    }
    mismatches = [key for key, value in expected.items() if payload is None or payload.get(key) != value]
    if payload is None or not payload.get("event_id"):
        mismatches.append("event_id")
    if payload is None or payload.get("signature_mode") not in {"lark_sha256", "legacy_hmac_sha256"}:
        mismatches.append("signature_mode")
    details = {
        "event_id": payload.get("event_id") if payload else None,
        "event_type": payload.get("event_type") if payload else None,
        "signature_mode": payload.get("signature_mode") if payload else None,
        "encrypted_callback": payload.get("encrypted_callback") if payload else None,
        "tenant_key_present": payload.get("tenant_key_present") if payload else None,
        "message_id_present": payload.get("message_id_present") if payload else None,
        "chat_id_present": payload.get("chat_id_present") if payload else None,
        "content_present": payload.get("content_present") if payload else None,
        "mutation_performed": payload.get("mutation_performed") if payload else None,
        "outbound_message_sent": payload.get("outbound_message_sent") if payload else None,
        "mismatches": mismatches,
    }
    if mismatches:
        unsafe = {"mutation_performed", "outbound_message_sent", "channel", "evidence_type"} & set(mismatches)
        return {
            "name": "feishu_inbound_event_audit",
            "status": "failed" if unsafe else "action_required",
            "details": details,
            "error": "Feishu inbound event audit evidence is not accepted",
        }
    return {"name": "feishu_inbound_event_audit", "status": "passed", "details": details, "error": None}


def _overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "pilot_operational_blocked"
    if any(check["status"] == "action_required" for check in checks):
        return "pilot_operational_action_required"
    return "pilot_operational_ready"


def build_feishu_pilot_status(report_dir: Path | None = None) -> dict[str, Any]:
    active_report_dir = report_dir or REPORT_DIR
    reports: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any] | None] = {}
    for spec in REPORT_SPECS:
        summary, payload = _report_summary(spec, active_report_dir)
        reports.append(summary)
        payloads[spec.name] = payload

    acceptance = payloads.get("acceptance_gate")
    handoff_index = payloads.get("handoff_index")
    ops = payloads.get("operator_status")
    live = payloads.get("feishu_inbound_live")
    checks = [
        _check_required_reports(reports),
        _check_ready(acceptance, name="acceptance_gate_ready", expected="pilot_acceptance_ready"),
        _check_ready(handoff_index, name="handoff_index_ready", expected="handoff_index_ready"),
        _inbound_event_audit(live),
        _check_no_parity_claim(payloads),
        _check_no_mutation(payloads),
    ]
    status = _overall_status(checks)
    return {
        "status": status,
        "pilot_channel": (acceptance or ops or {}).get("pilot_channel"),
        "pilot_tag_name": (acceptance or ops or {}).get("pilot_tag_name"),
        "pilot_commit_sha": (acceptance or ops or {}).get("pilot_commit_sha"),
        "rc_tag_name": (acceptance or ops or {}).get("rc_tag_name"),
        "rc_commit_sha": (acceptance or ops or {}).get("rc_commit_sha"),
        "acceptance_gate_status": acceptance.get("status") if acceptance else None,
        "handoff_index_status": handoff_index.get("status") if handoff_index else None,
        "outbound_owner_gate_status": ops.get("outbound_owner_gate_status") if ops else None,
        "full_codex_parity_claimed": False,
        "mutation_performed": False,
        "outbound_message_sent": False,
        "reports": reports,
        "checks": checks,
        "known_limits": [
            "This API is read-only and only reflects existing runtime reports.",
            "It does not refresh reports, move tags, call GitHub, or send Feishu outbound messages.",
            "Outbound Feishu send remains optional and owner-gated for Pilot V1.",
            "Full Codex parity is not claimed by this API response.",
        ],
    }


@router.get("/status")
async def get_feishu_pilot_status() -> dict[str, Any]:
    """Return the stable read-only Feishu Pilot V1 operations status."""
    return build_feishu_pilot_status()


@router.get("/reports")
async def list_feishu_pilot_reports() -> dict[str, Any]:
    """List Feishu Pilot V1 evidence reports with digest metadata."""
    status = build_feishu_pilot_status()
    return {
        "status": status["status"],
        "pilot_channel": status["pilot_channel"],
        "reports": status["reports"],
        "known_limits": status["known_limits"],
    }


@router.get("/reports/{report_name}")
async def get_feishu_pilot_report(report_name: str) -> dict[str, Any]:
    """Return a single Feishu Pilot V1 evidence report with digest metadata."""
    spec = next((candidate for candidate in REPORT_SPECS if candidate.name == report_name), None)
    if spec is None:
        raise HTTPException(status_code=404, detail="commercial pilot report is not registered")
    summary, payload = _report_summary(spec, REPORT_DIR)
    if payload is None:
        raise HTTPException(status_code=404, detail=summary["error"] or "commercial pilot report is missing")
    return {"status": "report_available", "report": summary, "payload": payload}
