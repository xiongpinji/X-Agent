#!/usr/bin/env python3
"""Run the owner-gated Feishu outbound pilot smoke.

The default mode is non-mutating. A real Feishu message is sent only when the
owner explicitly passes --execute, --owner-approved, and a receive ID while the
Feishu app credentials are configured in the environment.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core.feishu_bridge import FeishuBridge

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-feishu-outbound-live.json"
DEFAULT_TEXT = "X-Agent Feishu outbound owner-gated smoke"


@dataclass(frozen=True)
class OutboundCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class FeishuOutboundSmokeReport:
    status: str
    generated_at: str
    channel: str
    evidence_type: str
    owner_gated: bool
    execute_requested: bool
    owner_approved: bool
    receive_id_present: bool
    receive_id_type: str
    text_length: int
    app_id_configured: bool
    app_secret_configured: bool
    encrypt_key_configured: bool
    mutation_performed: bool
    outbound_message_sent: bool
    attempted_outbound_message_send: bool
    full_codex_parity_claimed: bool
    feishu_result_summary: dict[str, Any]
    checks: list[OutboundCheck]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _passed(name: str, details: dict[str, Any] | None = None) -> OutboundCheck:
    return OutboundCheck(name=name, status="passed", details=details or {})


def _action_required(name: str, error: str, details: dict[str, Any] | None = None) -> OutboundCheck:
    return OutboundCheck(name=name, status="action_required", details=details or {}, error=error)


def _failed(name: str, error: str, details: dict[str, Any] | None = None) -> OutboundCheck:
    return OutboundCheck(name=name, status="failed", details=details or {}, error=error)


def _result_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep outbound evidence useful without storing message text or tokens."""

    summary: dict[str, Any] = {}
    for key in ("code", "msg", "message", "request_id"):
        if key in payload:
            summary[key] = payload.get(key)
    data = payload.get("data")
    if isinstance(data, dict):
        summary["data_keys"] = sorted(str(key) for key in data.keys())
        message_id = data.get("message_id")
        if message_id:
            summary["message_id_present"] = True
    return summary


def _overall_status(checks: list[OutboundCheck], *, execute_requested: bool, sent: bool) -> str:
    if any(check.status == "failed" for check in checks):
        return "failed"
    if sent:
        return "passed"
    if any(check.status == "action_required" for check in checks):
        return "owner_action_required"
    if not execute_requested:
        return "ready_to_execute"
    return "owner_action_required"


def _next_commands(*, status: str, output_path: Path) -> list[str]:
    if status == "passed":
        return [f"Review {output_path} before adding outbound send as a required pilot gate."]
    if status == "ready_to_execute":
        return [
            "Run again with --execute --owner-approved --receive-id <disposable-feishu-chat-id> to send one real message.",
            f"Review {output_path}; this dry-run did not perform an outbound mutation.",
        ]
    if status == "owner_action_required":
        return [
            "Set XAGENT_FEISHU_APP_ID and XAGENT_FEISHU_APP_SECRET in the owner environment.",
            "Pass --receive-id, --execute, and --owner-approved only when the owner permits one real Feishu send.",
        ]
    return ["Inspect the failed check in the outbound smoke report before retrying."]


async def build_feishu_outbound_smoke_report(
    *,
    receive_id: str | None,
    receive_id_type: str = "chat_id",
    text: str = DEFAULT_TEXT,
    execute: bool = False,
    owner_approved: bool = False,
    output_path: Path = DEFAULT_OUTPUT,
    bridge: Any | None = None,
) -> FeishuOutboundSmokeReport:
    bridge = bridge or FeishuBridge()
    configured = bool(bridge.configure_from_env())
    receive_id_present = bool(receive_id and receive_id.strip())
    app_id_configured = bool(getattr(bridge, "app_id", None))
    app_secret_configured = bool(getattr(bridge, "app_secret", None))
    encrypt_key_configured = bool(getattr(bridge, "encrypt_key", None))

    checks: list[OutboundCheck] = []
    checks.append(
        _passed("owner_gate_mode", {"execute_requested": execute, "owner_approved": owner_approved})
        if not execute or owner_approved
        else _action_required(
            "owner_gate_mode",
            "real outbound send requires --owner-approved in addition to --execute",
            {"execute_requested": execute, "owner_approved": owner_approved},
        )
    )
    checks.append(
        _passed(
            "feishu_app_configured",
            {
                "app_id_configured": app_id_configured,
                "app_secret_configured": app_secret_configured,
                "encrypt_key_configured": encrypt_key_configured,
            },
        )
        if configured and app_id_configured and app_secret_configured
        else _action_required(
            "feishu_app_configured",
            "Feishu app credentials are not configured in the owner environment",
            {
                "app_id_configured": app_id_configured,
                "app_secret_configured": app_secret_configured,
                "encrypt_key_configured": encrypt_key_configured,
            },
        )
    )
    checks.append(
        _passed("receive_id", {"receive_id_present": True, "receive_id_type": receive_id_type})
        if receive_id_present
        else _action_required(
            "receive_id",
            "receive ID is required before a real outbound Feishu message can be sent",
            {"receive_id_present": False, "receive_id_type": receive_id_type},
        )
    )

    attempted = False
    sent = False
    mutation_performed = False
    result_summary: dict[str, Any] = {}
    if execute and owner_approved and configured and receive_id_present:
        attempted = True
        mutation_performed = True
        try:
            result = await bridge.send_text_message(
                receive_id=receive_id.strip(),
                text=text,
                receive_id_type=receive_id_type,
            )
        except Exception as exc:  # noqa: BLE001 - evidence must record provider failure
            checks.append(_failed("outbound_send", f"Feishu outbound send failed: {exc}"))
        else:
            sent = True
            result_summary = _result_summary(result if isinstance(result, dict) else {"message": str(result)})
            checks.append(_passed("outbound_send", {"provider_result_summary": result_summary}))
    else:
        checks.append(
            _passed(
                "no_outbound_mutation",
                {
                    "execute_requested": execute,
                    "owner_approved": owner_approved,
                    "configured": configured,
                    "receive_id_present": receive_id_present,
                },
            )
        )

    status = _overall_status(checks, execute_requested=execute, sent=sent)
    return FeishuOutboundSmokeReport(
        status=status,
        generated_at=_utc_now(),
        channel="feishu",
        evidence_type="commercial_pilot_feishu_outbound_live",
        owner_gated=True,
        execute_requested=execute,
        owner_approved=owner_approved,
        receive_id_present=receive_id_present,
        receive_id_type=receive_id_type,
        text_length=len(text),
        app_id_configured=app_id_configured,
        app_secret_configured=app_secret_configured,
        encrypt_key_configured=encrypt_key_configured,
        mutation_performed=mutation_performed,
        outbound_message_sent=sent,
        attempted_outbound_message_send=attempted,
        full_codex_parity_claimed=False,
        feishu_result_summary=result_summary,
        checks=checks,
        next_commands=_next_commands(status=status, output_path=output_path),
        known_limits=[
            "This report is separate from inbound Feishu live evidence.",
            "Default mode performs no outbound Feishu mutation.",
            "A passed outbound report proves one owner-approved test send only, not broad channel SLA.",
            "Full Codex parity is not claimed by this report.",
        ],
    )


def write_report(report: FeishuOutboundSmokeReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receive-id")
    parser.add_argument("--receive-id-type", default="chat_id")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner-approved", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    report = await build_feishu_outbound_smoke_report(
        receive_id=args.receive_id,
        receive_id_type=args.receive_id_type,
        text=args.text,
        execute=args.execute,
        owner_approved=args.owner_approved,
        output_path=args.output,
    )
    write_report(report, args.output)
    print(f"Commercial pilot Feishu outbound smoke status: {report.status}")
    print(f"Report written to {args.output}")
    print(f"Execute requested: {report.execute_requested}")
    print(f"Owner approved: {report.owner_approved}")
    print(f"Mutation performed: {report.mutation_performed}")
    print(f"Outbound message sent: {report.outbound_message_sent}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status in {"passed", "ready_to_execute"} else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
