#!/usr/bin/env python3
"""Generate a customer-readable Feishu Pilot V1 delivery receipt.

The receipt consumes existing evidence reports only. It does not refresh the
final gate, move tags, call external services, or send Feishu messages.
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
DEFAULT_OPS_STATUS_REPORT = REPORT_DIR / "commercial-pilot-ops-status.json"
DEFAULT_DELIVERY_MANIFEST_REPORT = REPORT_DIR / "commercial-pilot-delivery-manifest.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-delivery-receipt.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-pilot-delivery-receipt.md"


@dataclass(frozen=True)
class ReceiptCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class SourceReportSummary:
    name: str
    path: str
    status: str | None
    sha256: str | None
    size_bytes: int | None
    error: str | None = None


@dataclass(frozen=True)
class DeliveryReceiptReport:
    status: str
    generated_at: str
    evidence_type: str
    pilot_channel: str | None
    pilot_tag_name: str | None
    pilot_commit_sha: str | None
    rc_tag_name: str | None
    rc_commit_sha: str | None
    final_gate_status: str | None
    ops_status: str | None
    delivery_manifest_status: str | None
    outbound_owner_gate_status: str | None
    artifact_count: int | None
    full_codex_parity_claimed: bool
    mutation_performed: bool
    outbound_message_sent: bool
    source_reports: list[SourceReportSummary]
    checks: list[ReceiptCheck]
    customer_summary: list[str]
    sign_off_items: list[str]
    known_limits: list[str]
    next_commands: list[str]

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


def _source_summary(name: str, path: Path, payload: dict[str, Any] | None, read_error: str | None) -> SourceReportSummary:
    sha256, size_bytes, digest_error = _sha256_file(path)
    return SourceReportSummary(
        name=name,
        path=str(path),
        status=payload.get("status") if payload else None,
        sha256=sha256,
        size_bytes=size_bytes,
        error=read_error or digest_error,
    )


def _status_check(name: str, actual: str | None, expected: str, *, label: str) -> ReceiptCheck:
    passed = actual == expected
    return ReceiptCheck(
        name=name,
        status="passed" if passed else "failed",
        details={"actual": actual, "expected": expected},
        error=None if passed else f"{label} is not {expected}",
    )


def _boolean_false_check(name: str, value: Any, *, label: str) -> ReceiptCheck:
    passed = value is False
    return ReceiptCheck(
        name=name,
        status="passed" if passed else "failed",
        details={"value": value, "expected": False},
        error=None if passed else f"{label} must be false",
    )


def _source_reports_check(sources: list[SourceReportSummary]) -> ReceiptCheck:
    failed = [source.name for source in sources if source.error or not source.sha256]
    if failed:
        return ReceiptCheck(
            name="source_reports_available",
            status="failed",
            details={"failed_sources": failed},
            error="one or more source reports are missing or unreadable",
        )
    return ReceiptCheck(name="source_reports_available", status="passed", details={"count": len(sources)})


def _all_checks_status(checks: list[ReceiptCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "delivery_receipt_blocked"
    return "delivery_receipt_ready"


def _artifact_count(manifest: dict[str, Any] | None) -> int | None:
    artifacts = manifest.get("artifacts") if manifest else None
    return len(artifacts) if isinstance(artifacts, list) else None


def _customer_summary(*, ops: dict[str, Any] | None, final_gate: dict[str, Any] | None, manifest: dict[str, Any] | None) -> list[str]:
    return [
        f"Pilot channel: {ops.get('pilot_channel') if ops else '<missing>'}",
        f"Pilot tag: {ops.get('pilot_tag_name') if ops else '<missing>'}",
        f"Pilot commit: {ops.get('pilot_commit_sha') if ops else '<missing>'}",
        f"RC baseline: {ops.get('rc_tag_name') if ops else '<missing>'} / {ops.get('rc_commit_sha') if ops else '<missing>'}",
        f"Final gate: {final_gate.get('status') if final_gate else '<missing>'}",
        f"Delivery manifest: {manifest.get('status') if manifest else '<missing>'}",
        f"Outbound owner gate: {ops.get('outbound_owner_gate_status') if ops else '<missing>'}",
    ]


def _sign_off_items() -> list[str]:
    return [
        "Final gate is final_gate_ready.",
        "Operator status is pilot_ops_ready.",
        "Delivery manifest is delivery_manifest_ready.",
        "Feishu inbound live evidence is passed.",
        "No final gate mutation was performed.",
        "No outbound Feishu message is required for Pilot V1 readiness.",
        "full_codex_parity_claimed is false.",
    ]


def _next_commands(status: str) -> list[str]:
    if status == "delivery_receipt_ready":
        return [
            "Archive commercial-pilot-delivery-receipt.json and commercial-pilot-delivery-receipt.md with the customer handoff.",
            "Regenerate the receipt after rerunning commercial_pilot_final_gate.py.",
        ]
    return [
        "Inspect commercial-pilot-delivery-receipt.json and fix the first failed check.",
        "Rerun python scripts\\commercial_pilot_final_gate.py before regenerating the receipt.",
    ]


def build_delivery_receipt_report(
    *,
    final_gate_report_path: Path = DEFAULT_FINAL_GATE_REPORT,
    ops_status_report_path: Path = DEFAULT_OPS_STATUS_REPORT,
    delivery_manifest_report_path: Path = DEFAULT_DELIVERY_MANIFEST_REPORT,
) -> DeliveryReceiptReport:
    final_gate, final_gate_error = _read_json(final_gate_report_path)
    ops, ops_error = _read_json(ops_status_report_path)
    manifest, manifest_error = _read_json(delivery_manifest_report_path)
    sources = [
        _source_summary("final_gate", final_gate_report_path, final_gate, final_gate_error),
        _source_summary("operator_status", ops_status_report_path, ops, ops_error),
        _source_summary("delivery_manifest", delivery_manifest_report_path, manifest, manifest_error),
    ]

    checks = [
        _source_reports_check(sources),
        _status_check("final_gate_ready", final_gate.get("status") if final_gate else None, "final_gate_ready", label="final gate"),
        _status_check("operator_status_ready", ops.get("status") if ops else None, "pilot_ops_ready", label="operator status"),
        _status_check(
            "delivery_manifest_ready",
            manifest.get("status") if manifest else None,
            "delivery_manifest_ready",
            label="delivery manifest",
        ),
        _boolean_false_check(
            "no_full_codex_parity_claim",
            any(
                payload.get("full_codex_parity_claimed") is True
                for payload in [final_gate, ops, manifest]
                if isinstance(payload, dict)
            ),
            label="full Codex parity claim",
        ),
        _boolean_false_check(
            "no_final_gate_mutation",
            final_gate.get("mutation_performed") if final_gate else None,
            label="final gate mutation_performed",
        ),
        _boolean_false_check(
            "no_final_gate_outbound_send",
            final_gate.get("outbound_message_sent") if final_gate else None,
            label="final gate outbound_message_sent",
        ),
    ]
    status = _all_checks_status(checks)
    return DeliveryReceiptReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_pilot_delivery_receipt",
        pilot_channel=ops.get("pilot_channel") if ops else None,
        pilot_tag_name=ops.get("pilot_tag_name") if ops else None,
        pilot_commit_sha=ops.get("pilot_commit_sha") if ops else None,
        rc_tag_name=ops.get("rc_tag_name") if ops else None,
        rc_commit_sha=ops.get("rc_commit_sha") if ops else None,
        final_gate_status=final_gate.get("status") if final_gate else None,
        ops_status=ops.get("status") if ops else None,
        delivery_manifest_status=manifest.get("status") if manifest else None,
        outbound_owner_gate_status=ops.get("outbound_owner_gate_status") if ops else None,
        artifact_count=_artifact_count(manifest),
        full_codex_parity_claimed=False,
        mutation_performed=False,
        outbound_message_sent=False,
        source_reports=sources,
        checks=checks,
        customer_summary=_customer_summary(ops=ops, final_gate=final_gate, manifest=manifest),
        sign_off_items=_sign_off_items(),
        known_limits=[
            "This receipt summarizes existing evidence reports and does not run live Feishu checks.",
            "Outbound Feishu send remains optional and owner-gated for Pilot V1.",
            "This is not a GA release note and does not claim full Codex parity.",
            "Generated reports under .xagent_runtime are not staged by default.",
        ],
        next_commands=_next_commands(status),
    )


def render_markdown_receipt(report: DeliveryReceiptReport) -> str:
    checks = "\n".join(f"- {check.name}: `{check.status}`" for check in report.checks)
    sources = "\n".join(
        f"- {source.name}: `{source.status}` / `{source.sha256 or '<missing-sha256>'}`"
        for source in report.source_reports
    )
    summary = "\n".join(f"- {item}" for item in report.customer_summary)
    sign_off = "\n".join(f"- [ ] {item}" for item in report.sign_off_items)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    return (
        "# X-Agent Feishu Pilot V1 Delivery Receipt\n\n"
        f"- Status: `{report.status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Pilot channel: `{report.pilot_channel}`\n"
        f"- Pilot tag: `{report.pilot_tag_name}`\n"
        f"- Pilot commit: `{report.pilot_commit_sha}`\n"
        f"- RC baseline: `{report.rc_tag_name}` / `{report.rc_commit_sha}`\n"
        f"- Final gate: `{report.final_gate_status}`\n"
        f"- Delivery manifest: `{report.delivery_manifest_status}`\n"
        f"- Outbound owner gate: `{report.outbound_owner_gate_status}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n\n"
        "## Customer Summary\n\n"
        f"{summary}\n\n"
        "## Source Reports\n\n"
        f"{sources}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Sign-Off Items\n\n"
        f"{sign_off}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: DeliveryReceiptReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_receipt(report: DeliveryReceiptReport, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_receipt(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-gate-report", type=Path, default=DEFAULT_FINAL_GATE_REPORT)
    parser.add_argument("--ops-status-report", type=Path, default=DEFAULT_OPS_STATUS_REPORT)
    parser.add_argument("--delivery-manifest-report", type=Path, default=DEFAULT_DELIVERY_MANIFEST_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_delivery_receipt_report(
        final_gate_report_path=args.final_gate_report,
        ops_status_report_path=args.ops_status_report,
        delivery_manifest_report_path=args.delivery_manifest_report,
    )
    write_report(report, args.output)
    write_markdown_receipt(report, args.markdown_output)
    print(f"Commercial pilot delivery receipt status: {report.status}")
    print(f"Pilot channel: {report.pilot_channel or '<missing>'}")
    print(f"Pilot tag: {report.pilot_tag_name or '<missing>'}")
    print(f"Final gate status: {report.final_gate_status or '<missing>'}")
    print(f"Delivery manifest status: {report.delivery_manifest_status or '<missing>'}")
    print(f"JSON receipt written to {args.output}")
    print(f"Markdown receipt written to {args.markdown_output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Mutation performed: {report.mutation_performed}")
    print(f"Outbound message sent: {report.outbound_message_sent}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "delivery_receipt_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
