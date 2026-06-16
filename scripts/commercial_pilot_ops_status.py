#!/usr/bin/env python3
"""Generate the Feishu commercial pilot operations status.

This read-only report is the single operator-facing rollup for Pilot V1. It
combines the final handoff gate, channel readiness matrix, inbound Feishu live
evidence, optional outbound owner gate evidence, and frozen RC baseline without
requiring an outbound Feishu mutation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-ops-status.json"
DEFAULT_HANDOFF_REPORT = REPORT_DIR / "commercial-pilot-handoff-status.json"
DEFAULT_CHANNEL_READINESS_REPORT = REPORT_DIR / "commercial-pilot-channel-readiness.json"
DEFAULT_FEISHU_LIVE_REPORT = REPORT_DIR / "commercial-pilot-feishu-live.json"
DEFAULT_OUTBOUND_REPORT = REPORT_DIR / "commercial-pilot-feishu-outbound-live.json"
DEFAULT_RC_DELIVERY_REPORT = REPORT_DIR / "rc-delivery-status.json"


@dataclass(frozen=True)
class OpsCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class PilotOpsStatusReport:
    status: str
    generated_at: str
    pilot_channel: str
    pilot_tag_name: str | None
    pilot_commit_sha: str | None
    rc_tag_name: str | None
    rc_commit_sha: str | None
    handoff_status: str | None
    channel_readiness_status: str | None
    inbound_live_status: str | None
    outbound_owner_gate_status: str
    rc_baseline_status: str | None
    full_codex_parity_claimed: bool
    reports: dict[str, str]
    checks: list[OpsCheck]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
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


def _status_for_required_report(source_status: str | None) -> str:
    if source_status == "failed":
        return "failed"
    return "action_required"


def _handoff_check(payload: dict[str, Any] | None, error: str | None) -> OpsCheck:
    if error or payload is None:
        return OpsCheck(name="handoff_status", status="action_required", error=error or "handoff report missing")
    details = {
        "source_status": payload.get("status"),
        "pilot_tag_name": payload.get("pilot_tag_name"),
        "pilot_commit_sha": payload.get("expected_pilot_commit_sha"),
        "rc_tag_name": payload.get("rc_tag_name"),
        "rc_commit_sha": payload.get("expected_rc_commit_sha"),
        "full_codex_parity_claimed": payload.get("full_codex_parity_claimed"),
    }
    if payload.get("full_codex_parity_claimed") is True:
        return OpsCheck(
            name="handoff_status",
            status="failed",
            details=details,
            error="handoff report claims full Codex parity",
        )
    if payload.get("status") != "pilot_handoff_ready":
        return OpsCheck(
            name="handoff_status",
            status=_status_for_required_report(str(payload.get("status"))),
            details=details,
            error="commercial pilot handoff is not ready",
        )
    return OpsCheck(name="handoff_status", status="passed", details=details)


def _rc_baseline_check(
    payload: dict[str, Any] | None,
    error: str | None,
    *,
    handoff: dict[str, Any] | None,
) -> OpsCheck:
    if error or payload is None:
        return OpsCheck(name="rc_baseline", status="action_required", error=error or "RC delivery report missing")
    expected_tag = handoff.get("rc_tag_name") if handoff else None
    expected_sha = handoff.get("expected_rc_commit_sha") if handoff else None
    details = {
        "source_status": payload.get("status"),
        "tag_name": payload.get("tag_name"),
        "expected_commit_sha": payload.get("expected_commit_sha"),
        "handoff_rc_tag_name": expected_tag,
        "handoff_rc_commit_sha": expected_sha,
    }
    mismatches: list[str] = []
    if payload.get("status") != "commercial_rc_ready":
        mismatches.append("status")
    if expected_tag and payload.get("tag_name") != expected_tag:
        mismatches.append("tag_name")
    if expected_sha and payload.get("expected_commit_sha") != expected_sha:
        mismatches.append("expected_commit_sha")
    if mismatches:
        return OpsCheck(
            name="rc_baseline",
            status="failed",
            details=details | {"mismatches": mismatches},
            error="RC baseline is not accepted for the pilot operations status",
        )
    return OpsCheck(name="rc_baseline", status="passed", details=details)


def _selected_channel(payload: dict[str, Any] | None, pilot_channel: str) -> dict[str, Any] | None:
    if not payload:
        return None
    channels = payload.get("channels")
    if not isinstance(channels, list):
        return None
    for channel in channels:
        if isinstance(channel, dict) and channel.get("channel") == pilot_channel:
            return channel
    return None


def _channel_readiness_check(
    payload: dict[str, Any] | None,
    error: str | None,
    *,
    pilot_channel: str,
) -> OpsCheck:
    if error or payload is None:
        return OpsCheck(
            name="channel_readiness",
            status="action_required",
            error=error or "channel readiness report missing",
        )
    selected = _selected_channel(payload, pilot_channel)
    details = {
        "source_status": payload.get("status"),
        "pilot_channel": payload.get("pilot_channel"),
        "selected_channel_status": selected.get("status") if selected else None,
        "full_codex_parity_claimed": payload.get("full_codex_parity_claimed"),
    }
    if payload.get("full_codex_parity_claimed") is True:
        return OpsCheck(
            name="channel_readiness",
            status="failed",
            details=details,
            error="channel readiness report claims full Codex parity",
        )
    if payload.get("pilot_channel") != pilot_channel or selected is None:
        return OpsCheck(
            name="channel_readiness",
            status="action_required",
            details=details,
            error="selected pilot channel is missing from the readiness matrix",
        )
    if payload.get("status") not in {"ready", "ready_with_owner_gates"} or selected.get("status") != "ready":
        return OpsCheck(
            name="channel_readiness",
            status="action_required",
            details=details,
            error="selected pilot channel is not ready",
        )
    return OpsCheck(name="channel_readiness", status="passed", details=details)


def _feishu_live_evidence_check(payload: dict[str, Any] | None, error: str | None) -> OpsCheck:
    if error or payload is None:
        return OpsCheck(
            name="feishu_inbound_live",
            status="action_required",
            error=error or "Feishu inbound live evidence missing",
        )
    expected = {
        "status": "passed",
        "channel": "feishu",
        "evidence_type": "commercial_pilot_feishu_live",
        "event_type": "im.message.receive_v1",
        "mutation_performed": False,
        "outbound_message_sent": False,
    }
    mismatches = [key for key, value in expected.items() if payload.get(key) != value]
    if not payload.get("event_id"):
        mismatches.append("event_id")
    if payload.get("signature_mode") not in {"lark_sha256", "legacy_hmac_sha256"}:
        mismatches.append("signature_mode")
    if payload.get("encrypted_callback") is not True:
        mismatches.append("encrypted_callback")
    details = {
        "source_status": payload.get("status"),
        "event_id": payload.get("event_id"),
        "event_type": payload.get("event_type"),
        "signature_mode": payload.get("signature_mode"),
        "encrypted_callback": payload.get("encrypted_callback"),
        "mutation_performed": payload.get("mutation_performed"),
        "outbound_message_sent": payload.get("outbound_message_sent"),
    }
    if mismatches:
        return OpsCheck(
            name="feishu_inbound_live",
            status="failed",
            details=details | {"mismatches": mismatches},
            error="Feishu inbound live evidence is not accepted",
        )
    return OpsCheck(name="feishu_inbound_live", status="passed", details=details)


def _outbound_owner_gate_check(payload: dict[str, Any] | None, error: str | None) -> OpsCheck:
    if error or payload is None:
        return OpsCheck(
            name="feishu_outbound_owner_gate",
            status="preview",
            details={"optional": True, "source_status": None},
            error=error or "optional outbound owner gate has not been run",
        )
    details = {
        "optional": True,
        "source_status": payload.get("status"),
        "evidence_type": payload.get("evidence_type"),
        "execute_requested": payload.get("execute_requested"),
        "owner_approved": payload.get("owner_approved"),
        "mutation_performed": payload.get("mutation_performed"),
        "outbound_message_sent": payload.get("outbound_message_sent"),
        "attempted_outbound_message_send": payload.get("attempted_outbound_message_send"),
        "full_codex_parity_claimed": payload.get("full_codex_parity_claimed"),
    }
    if payload.get("full_codex_parity_claimed") is True:
        return OpsCheck(
            name="feishu_outbound_owner_gate",
            status="failed",
            details=details,
            error="optional outbound report claims full Codex parity",
        )
    mutation = payload.get("mutation_performed") is True
    owner_approved = payload.get("owner_approved") is True
    execute_requested = payload.get("execute_requested") is True
    sent = payload.get("outbound_message_sent") is True
    if mutation and not (owner_approved and execute_requested):
        return OpsCheck(
            name="feishu_outbound_owner_gate",
            status="failed",
            details=details,
            error="outbound mutation was recorded without explicit execute and owner approval",
        )
    if sent and not (
        payload.get("status") == "passed"
        and payload.get("channel") == "feishu"
        and payload.get("evidence_type") == "commercial_pilot_feishu_outbound_live"
        and mutation
        and owner_approved
        and execute_requested
    ):
        return OpsCheck(
            name="feishu_outbound_owner_gate",
            status="failed",
            details=details,
            error="outbound send evidence is not accepted",
        )
    if (
        payload.get("status") == "passed"
        and payload.get("channel") == "feishu"
        and payload.get("evidence_type") == "commercial_pilot_feishu_outbound_live"
        and mutation
        and sent
        and owner_approved
        and execute_requested
    ):
        return OpsCheck(name="feishu_outbound_owner_gate", status="passed", details=details)
    if not mutation and not sent:
        return OpsCheck(
            name="feishu_outbound_owner_gate",
            status="preview",
            details=details,
            error="optional outbound owner gate is not required for Pilot V1 readiness",
        )
    return OpsCheck(
        name="feishu_outbound_owner_gate",
        status="preview",
        details=details,
        error="optional outbound owner gate is incomplete and not used as a Pilot V1 blocker",
    )


def _parity_claim_check(reports: dict[str, dict[str, Any] | None]) -> OpsCheck:
    claimers = [
        name
        for name, payload in reports.items()
        if isinstance(payload, dict) and payload.get("full_codex_parity_claimed") is True
    ]
    if claimers:
        return OpsCheck(
            name="no_full_codex_parity_claim",
            status="failed",
            details={"claiming_reports": claimers},
            error="one or more pilot operations reports claim full Codex parity",
        )
    return OpsCheck(
        name="no_full_codex_parity_claim",
        status="passed",
        details={"full_codex_parity_claimed": False},
    )


def _overall_status(checks: list[OpsCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "pilot_ops_blocked"
    required_pending = [
        check.name
        for check in checks
        if check.status == "action_required" and check.name != "feishu_outbound_owner_gate"
    ]
    if required_pending:
        return "pilot_ops_action_required"
    return "pilot_ops_ready"


def _next_commands(status: str) -> list[str]:
    if status == "pilot_ops_ready":
        return [
            "Use .xagent_runtime\\reports\\commercial-pilot-ops-status.json as the operator and UI status source.",
            "Run python scripts\\commercial_pilot_ops_status.py after refreshing handoff, channel, or Feishu evidence.",
        ]
    if status == "pilot_ops_action_required":
        return [
            "Inspect the non-passing required check in commercial-pilot-ops-status.json.",
            "Rerun commercial_pilot_handoff_status.py and commercial_pilot_channel_readiness.py after fixing evidence.",
        ]
    return [
        "Do not promote the pilot operations status until failed checks are resolved.",
        "Keep RC and pilot tags unchanged while regenerating runtime evidence reports.",
    ]


def build_pilot_ops_status_report(
    *,
    handoff_report_path: Path = DEFAULT_HANDOFF_REPORT,
    channel_readiness_report_path: Path = DEFAULT_CHANNEL_READINESS_REPORT,
    feishu_live_report_path: Path = DEFAULT_FEISHU_LIVE_REPORT,
    outbound_report_path: Path = DEFAULT_OUTBOUND_REPORT,
    rc_delivery_report_path: Path = DEFAULT_RC_DELIVERY_REPORT,
    pilot_channel: str = "feishu",
) -> PilotOpsStatusReport:
    handoff, handoff_error = _read_json(handoff_report_path)
    channel, channel_error = _read_json(channel_readiness_report_path)
    inbound, inbound_error = _read_json(feishu_live_report_path)
    outbound, outbound_error = _read_json(outbound_report_path)
    rc_delivery, rc_error = _read_json(rc_delivery_report_path)

    checks = [
        _handoff_check(handoff, handoff_error),
        _rc_baseline_check(rc_delivery, rc_error, handoff=handoff),
        _channel_readiness_check(channel, channel_error, pilot_channel=pilot_channel),
        _feishu_live_evidence_check(inbound, inbound_error),
        _outbound_owner_gate_check(outbound, outbound_error),
        _parity_claim_check(
            {
                "handoff": handoff,
                "channel_readiness": channel,
                "feishu_inbound_live": inbound,
                "feishu_outbound_owner_gate": outbound,
                "rc_delivery": rc_delivery,
            }
        ),
    ]
    status = _overall_status(checks)
    outbound_check = next(check for check in checks if check.name == "feishu_outbound_owner_gate")
    return PilotOpsStatusReport(
        status=status,
        generated_at=_utc_now(),
        pilot_channel=pilot_channel,
        pilot_tag_name=handoff.get("pilot_tag_name") if handoff else None,
        pilot_commit_sha=handoff.get("expected_pilot_commit_sha") if handoff else None,
        rc_tag_name=handoff.get("rc_tag_name") if handoff else None,
        rc_commit_sha=handoff.get("expected_rc_commit_sha") if handoff else None,
        handoff_status=handoff.get("status") if handoff else None,
        channel_readiness_status=channel.get("status") if channel else None,
        inbound_live_status=inbound.get("status") if inbound else None,
        outbound_owner_gate_status=outbound_check.status,
        rc_baseline_status=rc_delivery.get("status") if rc_delivery else None,
        full_codex_parity_claimed=False,
        reports={
            "handoff_status": str(handoff_report_path),
            "channel_readiness": str(channel_readiness_report_path),
            "feishu_inbound_live": str(feishu_live_report_path),
            "feishu_outbound_owner_gate": str(outbound_report_path),
            "rc_delivery": str(rc_delivery_report_path),
        },
        checks=checks,
        next_commands=_next_commands(status),
        known_limits=[
            "This report is an operations rollup over existing runtime evidence.",
            "Feishu Pilot V1 requires inbound live evidence; outbound send remains optional and owner-gated.",
            "Telegram is not required for the first domestic pilot.",
            "Full Codex parity is not claimed by this report.",
            "Generated reports under .xagent_runtime are not staged by default.",
        ],
    )


def write_report(report: PilotOpsStatusReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff-report", type=Path, default=DEFAULT_HANDOFF_REPORT)
    parser.add_argument("--channel-readiness-report", type=Path, default=DEFAULT_CHANNEL_READINESS_REPORT)
    parser.add_argument("--feishu-live-report", type=Path, default=DEFAULT_FEISHU_LIVE_REPORT)
    parser.add_argument("--outbound-report", type=Path, default=DEFAULT_OUTBOUND_REPORT)
    parser.add_argument("--rc-delivery-report", type=Path, default=DEFAULT_RC_DELIVERY_REPORT)
    parser.add_argument("--pilot-channel", default="feishu")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_pilot_ops_status_report(
        handoff_report_path=args.handoff_report,
        channel_readiness_report_path=args.channel_readiness_report,
        feishu_live_report_path=args.feishu_live_report,
        outbound_report_path=args.outbound_report,
        rc_delivery_report_path=args.rc_delivery_report,
        pilot_channel=args.pilot_channel,
    )
    write_report(report, args.output)
    print(f"Commercial pilot ops status: {report.status}")
    print(f"Pilot channel: {report.pilot_channel}")
    print(f"Pilot tag: {report.pilot_tag_name or '<missing>'}")
    print(f"RC tag: {report.rc_tag_name or '<missing>'}")
    print(f"Report written to {args.output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "pilot_ops_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
