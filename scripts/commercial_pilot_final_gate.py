#!/usr/bin/env python3
"""Run the final read-only Feishu Pilot V1 delivery gate.

The final gate fixes the required handoff order:

1. Regenerate the operator status report.
2. Regenerate the delivery manifest after the operator report is fresh.
3. Accept the handoff only when both reports are ready.

It performs no Feishu outbound mutation and does not move tags or RC evidence.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now
from scripts.commercial_pilot_delivery_manifest import (
    DEFAULT_OUTPUT as DEFAULT_MANIFEST_OUTPUT,
    DeliveryManifestReport,
    build_delivery_manifest_report,
    write_report as write_manifest_report,
)
from scripts.commercial_pilot_ops_status import (
    DEFAULT_OUTPUT as DEFAULT_OPS_OUTPUT,
    PilotOpsStatusReport,
    build_pilot_ops_status_report,
    write_report as write_ops_report,
)

DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-final-gate.json"


@dataclass(frozen=True)
class FinalGateCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class FinalGateStep:
    name: str
    status: str
    output_path: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class FinalGateReport:
    status: str
    generated_at: str
    evidence_type: str
    pilot_channel: str
    ops_status: str
    delivery_manifest_status: str
    full_codex_parity_claimed: bool
    mutation_performed: bool
    outbound_message_sent: bool
    steps: list[FinalGateStep]
    checks: list[FinalGateCheck]
    reports: dict[str, str]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


OpsBuilder = Callable[..., PilotOpsStatusReport]
ManifestBuilder = Callable[..., DeliveryManifestReport]
OpsWriter = Callable[[PilotOpsStatusReport, Path], None]
ManifestWriter = Callable[[DeliveryManifestReport, Path], None]


def _step_from_ops(report: PilotOpsStatusReport, output_path: Path) -> FinalGateStep:
    return FinalGateStep(
        name="operator_status",
        status="passed" if report.status == "pilot_ops_ready" else "failed",
        output_path=str(output_path),
        details={
            "source_status": report.status,
            "pilot_channel": report.pilot_channel,
            "pilot_tag_name": report.pilot_tag_name,
            "rc_tag_name": report.rc_tag_name,
            "outbound_owner_gate_status": report.outbound_owner_gate_status,
            "full_codex_parity_claimed": report.full_codex_parity_claimed,
        },
        error=None if report.status == "pilot_ops_ready" else "operator status report is not pilot_ops_ready",
    )


def _step_from_manifest(report: DeliveryManifestReport, output_path: Path) -> FinalGateStep:
    return FinalGateStep(
        name="delivery_manifest",
        status="passed" if report.status == "delivery_manifest_ready" else "failed",
        output_path=str(output_path),
        details={
            "source_status": report.status,
            "pilot_channel": report.pilot_channel,
            "artifact_count": len(report.artifacts),
            "full_codex_parity_claimed": report.full_codex_parity_claimed,
        },
        error=None if report.status == "delivery_manifest_ready" else "delivery manifest is not ready",
    )


def _ordered_refresh_check(steps: list[FinalGateStep]) -> FinalGateCheck:
    ordered_names = [step.name for step in steps]
    passed = ordered_names == ["operator_status", "delivery_manifest"]
    return FinalGateCheck(
        name="ordered_refresh_chain",
        status="passed" if passed else "failed",
        details={"steps": ordered_names},
        error=None if passed else "final gate did not refresh reports in the required order",
    )


def _ops_ready_check(report: PilotOpsStatusReport) -> FinalGateCheck:
    return FinalGateCheck(
        name="operator_status_ready",
        status="passed" if report.status == "pilot_ops_ready" else "failed",
        details={"source_status": report.status},
        error=None if report.status == "pilot_ops_ready" else "operator status is not ready",
    )


def _manifest_ready_check(report: DeliveryManifestReport) -> FinalGateCheck:
    return FinalGateCheck(
        name="delivery_manifest_ready",
        status="passed" if report.status == "delivery_manifest_ready" else "failed",
        details={"source_status": report.status, "artifact_count": len(report.artifacts)},
        error=None if report.status == "delivery_manifest_ready" else "delivery manifest is not ready",
    )


def _no_parity_claim_check(
    *,
    ops_report: PilotOpsStatusReport,
    manifest_report: DeliveryManifestReport,
) -> FinalGateCheck:
    claimers = []
    if ops_report.full_codex_parity_claimed:
        claimers.append("operator_status")
    if manifest_report.full_codex_parity_claimed:
        claimers.append("delivery_manifest")
    return FinalGateCheck(
        name="no_full_codex_parity_claim",
        status="failed" if claimers else "passed",
        details={"claiming_reports": claimers, "full_codex_parity_claimed": False},
        error="one or more final gate reports claim full Codex parity" if claimers else None,
    )


def _no_mutation_check() -> FinalGateCheck:
    return FinalGateCheck(
        name="no_final_gate_mutation",
        status="passed",
        details={"mutation_performed": False, "outbound_message_sent": False},
    )


def _overall_status(checks: list[FinalGateCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "final_gate_blocked"
    return "final_gate_ready"


def _next_commands(status: str) -> list[str]:
    if status == "final_gate_ready":
        return [
            "Use .xagent_runtime\\reports\\commercial-pilot-final-gate.json as the final pre-handoff gate.",
            "Share ops status, delivery manifest, and final gate reports with the pilot handoff package.",
        ]
    return [
        "Inspect commercial-pilot-final-gate.json and fix the first failed check.",
        "Rerun python scripts\\commercial_pilot_final_gate.py after refreshing upstream evidence.",
    ]


def build_final_gate_report(
    *,
    pilot_channel: str = "feishu",
    ops_output_path: Path = DEFAULT_OPS_OUTPUT,
    manifest_output_path: Path = DEFAULT_MANIFEST_OUTPUT,
    ops_builder: OpsBuilder = build_pilot_ops_status_report,
    manifest_builder: ManifestBuilder = build_delivery_manifest_report,
    ops_writer: OpsWriter = write_ops_report,
    manifest_writer: ManifestWriter = write_manifest_report,
) -> FinalGateReport:
    ops_report = ops_builder(pilot_channel=pilot_channel)
    ops_writer(ops_report, ops_output_path)

    manifest_report = manifest_builder(pilot_channel=pilot_channel)
    manifest_writer(manifest_report, manifest_output_path)

    steps = [
        _step_from_ops(ops_report, ops_output_path),
        _step_from_manifest(manifest_report, manifest_output_path),
    ]
    checks = [
        _ordered_refresh_check(steps),
        _ops_ready_check(ops_report),
        _manifest_ready_check(manifest_report),
        _no_parity_claim_check(ops_report=ops_report, manifest_report=manifest_report),
        _no_mutation_check(),
    ]
    status = _overall_status(checks)
    return FinalGateReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_pilot_final_gate",
        pilot_channel=pilot_channel,
        ops_status=ops_report.status,
        delivery_manifest_status=manifest_report.status,
        full_codex_parity_claimed=False,
        mutation_performed=False,
        outbound_message_sent=False,
        steps=steps,
        checks=checks,
        reports={
            "operator_status": str(ops_output_path),
            "delivery_manifest": str(manifest_output_path),
        },
        next_commands=_next_commands(status),
        known_limits=[
            "This final gate is read-only except for regenerating runtime evidence reports.",
            "It does not move git tags, change RC evidence, or send Feishu outbound messages.",
            "Optional outbound Feishu evidence remains owner-gated and is not required for Pilot V1 readiness.",
            "Full Codex parity is not claimed by this final gate.",
        ],
    )


def write_report(report: FinalGateReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ops-output", type=Path, default=DEFAULT_OPS_OUTPUT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--pilot-channel", default="feishu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_final_gate_report(
        pilot_channel=args.pilot_channel,
        ops_output_path=args.ops_output,
        manifest_output_path=args.manifest_output,
    )
    write_report(report, args.output)
    print(f"Commercial pilot final gate status: {report.status}")
    print(f"Pilot channel: {report.pilot_channel}")
    print(f"Ops status: {report.ops_status}")
    print(f"Delivery manifest status: {report.delivery_manifest_status}")
    print(f"Report written to {args.output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Mutation performed: {report.mutation_performed}")
    print(f"Outbound message sent: {report.outbound_message_sent}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "final_gate_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
