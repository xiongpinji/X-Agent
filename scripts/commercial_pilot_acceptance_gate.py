#!/usr/bin/env python3
"""Build the read-only Feishu Pilot V1 operations acceptance gate.

This gate consumes existing evidence reports only. It does not refresh reports,
call external services, move tags, or send Feishu outbound messages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_FINAL_GATE_REPORT = REPORT_DIR / "commercial-pilot-final-gate.json"
DEFAULT_DELIVERY_RECEIPT_REPORT = REPORT_DIR / "commercial-pilot-delivery-receipt.json"
DEFAULT_HANDOFF_REPORT = REPORT_DIR / "commercial-pilot-handoff-status.json"
DEFAULT_OPS_STATUS_REPORT = REPORT_DIR / "commercial-pilot-ops-status.json"
DEFAULT_DELIVERY_MANIFEST_REPORT = REPORT_DIR / "commercial-pilot-delivery-manifest.json"
DEFAULT_FEISHU_LIVE_REPORT = REPORT_DIR / "commercial-pilot-feishu-live.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-acceptance-gate.json"


@dataclass(frozen=True)
class AcceptanceSourceReport:
    name: str
    path: str
    status: str | None
    sha256: str | None
    size_bytes: int | None
    error: str | None = None


@dataclass(frozen=True)
class AcceptanceCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class AcceptanceGateReport:
    status: str
    generated_at: str
    evidence_type: str
    pilot_channel: str | None
    pilot_tag_name: str | None
    pilot_commit_sha: str | None
    rc_tag_name: str | None
    rc_commit_sha: str | None
    final_gate_status: str | None
    delivery_receipt_status: str | None
    handoff_status: str | None
    ops_status: str | None
    delivery_manifest_status: str | None
    inbound_live_status: str | None
    outbound_owner_gate_status: str | None
    full_codex_parity_claimed: bool
    mutation_performed: bool
    outbound_message_sent: bool
    source_reports: list[AcceptanceSourceReport]
    checks: list[AcceptanceCheck]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_reports"] = [asdict(source) for source in self.source_reports]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"report not found: {path}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read report {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {path}"
    return payload, None


def _sha256_file(path: Path) -> tuple[str | None, int | None, str | None]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None, f"report not found: {path}"
    except OSError as exc:
        return None, None, f"could not read report {path}: {exc}"
    return hashlib.sha256(data).hexdigest(), len(data), None


def _source_summary(
    name: str,
    path: Path,
    payload: dict[str, Any] | None,
    read_error: str | None,
) -> AcceptanceSourceReport:
    sha256, size_bytes, digest_error = _sha256_file(path)
    return AcceptanceSourceReport(
        name=name,
        path=str(path),
        status=payload.get("status") if payload else None,
        sha256=sha256,
        size_bytes=size_bytes,
        error=read_error or digest_error,
    )


def _source_reports_check(sources: list[AcceptanceSourceReport]) -> AcceptanceCheck:
    failed = [source.name for source in sources if source.error or not source.sha256]
    if failed:
        return AcceptanceCheck(
            name="source_reports_available",
            status="action_required",
            details={"failed_sources": failed},
            error="one or more acceptance source reports are missing or unreadable",
        )
    return AcceptanceCheck(name="source_reports_available", status="passed", details={"count": len(sources)})


def _status_check(
    name: str,
    payload: dict[str, Any] | None,
    expected: str,
    *,
    label: str,
) -> AcceptanceCheck:
    actual = payload.get("status") if payload else None
    passed = actual == expected
    return AcceptanceCheck(
        name=name,
        status="passed" if passed else "action_required",
        details={"actual": actual, "expected": expected},
        error=None if passed else f"{label} is not {expected}",
    )


def _identity_consistency_check(
    *,
    ops: dict[str, Any] | None,
    receipt: dict[str, Any] | None,
    handoff: dict[str, Any] | None,
    final_gate: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> AcceptanceCheck:
    missing_inputs = [
        name
        for name, payload in {
            "operator_status": ops,
            "delivery_receipt": receipt,
            "handoff_status": handoff,
            "final_gate": final_gate,
            "delivery_manifest": manifest,
        }.items()
        if payload is None
    ]
    if missing_inputs:
        return AcceptanceCheck(
            name="identity_consistency",
            status="action_required",
            details={"missing_inputs": missing_inputs},
            error="identity consistency cannot be checked until required source reports are available",
        )

    expected = {
        "pilot_channel": ops.get("pilot_channel") if ops else None,
        "pilot_tag_name": ops.get("pilot_tag_name") if ops else None,
        "pilot_commit_sha": ops.get("pilot_commit_sha") if ops else None,
        "rc_tag_name": ops.get("rc_tag_name") if ops else None,
        "rc_commit_sha": ops.get("rc_commit_sha") if ops else None,
    }
    observed = {
        "receipt_pilot_channel": receipt.get("pilot_channel") if receipt else None,
        "receipt_pilot_tag_name": receipt.get("pilot_tag_name") if receipt else None,
        "receipt_pilot_commit_sha": receipt.get("pilot_commit_sha") if receipt else None,
        "receipt_rc_tag_name": receipt.get("rc_tag_name") if receipt else None,
        "receipt_rc_commit_sha": receipt.get("rc_commit_sha") if receipt else None,
        "handoff_pilot_tag_name": handoff.get("pilot_tag_name") if handoff else None,
        "handoff_pilot_commit_sha": handoff.get("expected_pilot_commit_sha") if handoff else None,
        "handoff_rc_tag_name": handoff.get("rc_tag_name") if handoff else None,
        "handoff_rc_commit_sha": handoff.get("expected_rc_commit_sha") if handoff else None,
        "final_gate_pilot_channel": final_gate.get("pilot_channel") if final_gate else None,
        "manifest_pilot_channel": manifest.get("pilot_channel") if manifest else None,
    }
    mismatches: list[str] = []
    if expected["pilot_channel"] and observed["receipt_pilot_channel"] != expected["pilot_channel"]:
        mismatches.append("receipt_pilot_channel")
    if expected["pilot_channel"] and observed["final_gate_pilot_channel"] != expected["pilot_channel"]:
        mismatches.append("final_gate_pilot_channel")
    if expected["pilot_channel"] and observed["manifest_pilot_channel"] != expected["pilot_channel"]:
        mismatches.append("manifest_pilot_channel")
    for key in ("pilot_tag_name", "pilot_commit_sha", "rc_tag_name", "rc_commit_sha"):
        expected_value = expected[key]
        receipt_value = observed[f"receipt_{key}"]
        if expected_value and receipt_value != expected_value:
            mismatches.append(f"receipt_{key}")
    if expected["pilot_tag_name"] and observed["handoff_pilot_tag_name"] != expected["pilot_tag_name"]:
        mismatches.append("handoff_pilot_tag_name")
    if expected["pilot_commit_sha"] and observed["handoff_pilot_commit_sha"] != expected["pilot_commit_sha"]:
        mismatches.append("handoff_pilot_commit_sha")
    if expected["rc_tag_name"] and observed["handoff_rc_tag_name"] != expected["rc_tag_name"]:
        mismatches.append("handoff_rc_tag_name")
    if expected["rc_commit_sha"] and observed["handoff_rc_commit_sha"] != expected["rc_commit_sha"]:
        mismatches.append("handoff_rc_commit_sha")

    details = {"expected": expected, "observed": observed, "mismatches": mismatches}
    if mismatches:
        return AcceptanceCheck(
            name="identity_consistency",
            status="failed",
            details=details,
            error="pilot and RC identity fields are inconsistent across acceptance reports",
        )
    return AcceptanceCheck(name="identity_consistency", status="passed", details=details)


def _feishu_inbound_audit_check(payload: dict[str, Any] | None) -> AcceptanceCheck:
    if payload is None:
        return AcceptanceCheck(
            name="feishu_inbound_event_audit",
            status="action_required",
            details={"missing_inputs": ["feishu_inbound_live"]},
            error="Feishu inbound event audit cannot be checked until live evidence is available",
        )

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
        return AcceptanceCheck(
            name="feishu_inbound_event_audit",
            status="failed" if unsafe else "action_required",
            details=details,
            error="Feishu inbound event audit evidence is not accepted",
        )
    return AcceptanceCheck(name="feishu_inbound_event_audit", status="passed", details=details)


def _parity_claim_check(reports: dict[str, dict[str, Any] | None]) -> AcceptanceCheck:
    claimers = [
        name
        for name, payload in reports.items()
        if isinstance(payload, dict) and payload.get("full_codex_parity_claimed") is True
    ]
    if claimers:
        return AcceptanceCheck(
            name="no_full_codex_parity_claim",
            status="failed",
            details={"claiming_reports": claimers},
            error="one or more acceptance reports claim full Codex parity",
        )
    return AcceptanceCheck(
        name="no_full_codex_parity_claim",
        status="passed",
        details={"full_codex_parity_claimed": False},
    )


def _no_mutation_check(
    *,
    final_gate: dict[str, Any] | None,
    receipt: dict[str, Any] | None,
    live: dict[str, Any] | None,
) -> AcceptanceCheck:
    missing_inputs = [
        name
        for name, payload in {
            "final_gate": final_gate,
            "delivery_receipt": receipt,
            "feishu_inbound_live": live,
        }.items()
        if payload is None
    ]
    if missing_inputs:
        return AcceptanceCheck(
            name="no_acceptance_gate_mutation",
            status="action_required",
            details={"missing_inputs": missing_inputs},
            error="mutation checks cannot be completed until required source reports are available",
        )

    observed = {
        "final_gate_mutation_performed": final_gate.get("mutation_performed") if final_gate else None,
        "final_gate_outbound_message_sent": final_gate.get("outbound_message_sent") if final_gate else None,
        "receipt_mutation_performed": receipt.get("mutation_performed") if receipt else None,
        "receipt_outbound_message_sent": receipt.get("outbound_message_sent") if receipt else None,
        "live_mutation_performed": live.get("mutation_performed") if live else None,
        "live_outbound_message_sent": live.get("outbound_message_sent") if live else None,
    }
    offenders = [key for key, value in observed.items() if value is not False]
    if offenders:
        return AcceptanceCheck(
            name="no_acceptance_gate_mutation",
            status="failed",
            details={"observed": observed, "offenders": offenders},
            error="acceptance source evidence must not record final gate or inbound outbound mutation",
        )
    return AcceptanceCheck(name="no_acceptance_gate_mutation", status="passed", details={"observed": observed})


def _outbound_owner_gate_check(ops: dict[str, Any] | None) -> AcceptanceCheck:
    status = ops.get("outbound_owner_gate_status") if ops else None
    passed = status in {"preview", "passed"}
    return AcceptanceCheck(
        name="outbound_owner_gate_optional",
        status="passed" if passed else "action_required",
        details={"outbound_owner_gate_status": status, "required_for_pilot_v1": False},
        error=None if passed else "outbound owner gate status is not accepted for Pilot V1",
    )


def _overall_status(checks: list[AcceptanceCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "pilot_acceptance_blocked"
    if any(check.status == "action_required" for check in checks):
        return "pilot_acceptance_action_required"
    return "pilot_acceptance_ready"


def _next_commands(status: str) -> list[str]:
    if status == "pilot_acceptance_ready":
        return [
            "Archive commercial-pilot-acceptance-gate.json with the Feishu Pilot V1 handoff evidence.",
            "Rerun scripts\\commercial_pilot_acceptance_gate.py after refreshing final gate or receipt evidence.",
        ]
    if status == "pilot_acceptance_action_required":
        return [
            "Inspect commercial-pilot-acceptance-gate.json and fix the first action_required check.",
            "Rerun powershell -ExecutionPolicy Bypass -File scripts\\run_feishu_pilot_final_handoff.ps1 before acceptance.",
        ]
    return [
        "Do not use this pilot evidence for customer acceptance until failed checks are resolved.",
        "Inspect full_codex_parity_claimed, mutation_performed, and outbound_message_sent fields first.",
    ]


def build_acceptance_gate_report(
    *,
    final_gate_report_path: Path = DEFAULT_FINAL_GATE_REPORT,
    delivery_receipt_report_path: Path = DEFAULT_DELIVERY_RECEIPT_REPORT,
    handoff_report_path: Path = DEFAULT_HANDOFF_REPORT,
    ops_status_report_path: Path = DEFAULT_OPS_STATUS_REPORT,
    delivery_manifest_report_path: Path = DEFAULT_DELIVERY_MANIFEST_REPORT,
    feishu_live_report_path: Path = DEFAULT_FEISHU_LIVE_REPORT,
) -> AcceptanceGateReport:
    final_gate, final_gate_error = _read_json(final_gate_report_path)
    receipt, receipt_error = _read_json(delivery_receipt_report_path)
    handoff, handoff_error = _read_json(handoff_report_path)
    ops, ops_error = _read_json(ops_status_report_path)
    manifest, manifest_error = _read_json(delivery_manifest_report_path)
    live, live_error = _read_json(feishu_live_report_path)
    sources = [
        _source_summary("final_gate", final_gate_report_path, final_gate, final_gate_error),
        _source_summary("delivery_receipt", delivery_receipt_report_path, receipt, receipt_error),
        _source_summary("handoff_status", handoff_report_path, handoff, handoff_error),
        _source_summary("operator_status", ops_status_report_path, ops, ops_error),
        _source_summary("delivery_manifest", delivery_manifest_report_path, manifest, manifest_error),
        _source_summary("feishu_inbound_live", feishu_live_report_path, live, live_error),
    ]
    reports = {
        "final_gate": final_gate,
        "delivery_receipt": receipt,
        "handoff_status": handoff,
        "operator_status": ops,
        "delivery_manifest": manifest,
        "feishu_inbound_live": live,
    }
    checks = [
        _source_reports_check(sources),
        _status_check("final_gate_ready", final_gate, "final_gate_ready", label="final gate"),
        _status_check("delivery_receipt_ready", receipt, "delivery_receipt_ready", label="delivery receipt"),
        _status_check("handoff_ready", handoff, "pilot_handoff_ready", label="handoff status"),
        _status_check("operator_status_ready", ops, "pilot_ops_ready", label="operator status"),
        _status_check("delivery_manifest_ready", manifest, "delivery_manifest_ready", label="delivery manifest"),
        _identity_consistency_check(ops=ops, receipt=receipt, handoff=handoff, final_gate=final_gate, manifest=manifest),
        _feishu_inbound_audit_check(live),
        _outbound_owner_gate_check(ops),
        _parity_claim_check(reports),
        _no_mutation_check(final_gate=final_gate, receipt=receipt, live=live),
    ]
    status = _overall_status(checks)
    return AcceptanceGateReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_pilot_acceptance_gate",
        pilot_channel=ops.get("pilot_channel") if ops else None,
        pilot_tag_name=ops.get("pilot_tag_name") if ops else None,
        pilot_commit_sha=ops.get("pilot_commit_sha") if ops else None,
        rc_tag_name=ops.get("rc_tag_name") if ops else None,
        rc_commit_sha=ops.get("rc_commit_sha") if ops else None,
        final_gate_status=final_gate.get("status") if final_gate else None,
        delivery_receipt_status=receipt.get("status") if receipt else None,
        handoff_status=handoff.get("status") if handoff else None,
        ops_status=ops.get("status") if ops else None,
        delivery_manifest_status=manifest.get("status") if manifest else None,
        inbound_live_status=live.get("status") if live else None,
        outbound_owner_gate_status=ops.get("outbound_owner_gate_status") if ops else None,
        full_codex_parity_claimed=False,
        mutation_performed=False,
        outbound_message_sent=False,
        source_reports=sources,
        checks=checks,
        next_commands=_next_commands(status),
        known_limits=[
            "This acceptance gate is read-only and consumes existing evidence reports only.",
            "It does not refresh reports, move tags, call GitHub, or send Feishu outbound messages.",
            "Outbound Feishu send remains optional and owner-gated for Pilot V1.",
            "Full Codex parity is not claimed by this acceptance gate.",
        ],
    )


def write_report(report: AcceptanceGateReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-gate-report", type=Path, default=DEFAULT_FINAL_GATE_REPORT)
    parser.add_argument("--delivery-receipt-report", type=Path, default=DEFAULT_DELIVERY_RECEIPT_REPORT)
    parser.add_argument("--handoff-report", type=Path, default=DEFAULT_HANDOFF_REPORT)
    parser.add_argument("--ops-status-report", type=Path, default=DEFAULT_OPS_STATUS_REPORT)
    parser.add_argument("--delivery-manifest-report", type=Path, default=DEFAULT_DELIVERY_MANIFEST_REPORT)
    parser.add_argument("--feishu-live-report", type=Path, default=DEFAULT_FEISHU_LIVE_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_acceptance_gate_report(
        final_gate_report_path=args.final_gate_report,
        delivery_receipt_report_path=args.delivery_receipt_report,
        handoff_report_path=args.handoff_report,
        ops_status_report_path=args.ops_status_report,
        delivery_manifest_report_path=args.delivery_manifest_report,
        feishu_live_report_path=args.feishu_live_report,
    )
    write_report(report, args.output)
    print(f"Commercial pilot acceptance gate status: {report.status}")
    print(f"Pilot channel: {report.pilot_channel or '<missing>'}")
    print(f"Pilot tag: {report.pilot_tag_name or '<missing>'}")
    print(f"Pilot commit: {report.pilot_commit_sha or '<missing>'}")
    print(f"Report written to {args.output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Mutation performed: {report.mutation_performed}")
    print(f"Outbound message sent: {report.outbound_message_sent}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "pilot_acceptance_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
