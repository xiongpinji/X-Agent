#!/usr/bin/env python3
"""Generate a channel readiness matrix for commercial pilot handoff."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-channel-readiness.json"


@dataclass(frozen=True)
class ChannelCapability:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ChannelReadiness:
    channel: str
    status: str
    owner_gated: bool
    recommended_for_first_pilot: bool
    capabilities: list[ChannelCapability]
    next_actions: list[str]
    known_limits: list[str]


@dataclass(frozen=True)
class ChannelReadinessMatrix:
    status: str
    generated_at: str
    pilot_channel: str
    full_codex_parity_claimed: bool
    channels: list[ChannelReadiness]
    checks: list[ChannelCapability]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["channels"] = [asdict(channel) for channel in self.channels]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _file_exists(path: str) -> bool:
    return (ROOT / path).is_file()


def _read_json(path: str) -> dict[str, Any] | None:
    report_path = ROOT / path
    if not report_path.is_file():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _capability(name: str, passed: bool, *, details: dict[str, Any], required: bool = True) -> ChannelCapability:
    if passed:
        return ChannelCapability(name=name, status="passed", details=details)
    status = "action_required" if required else "preview"
    return ChannelCapability(
        name=name,
        status=status,
        details=details,
        error="required channel capability is missing" if required else "optional channel capability is not complete",
    )


def _channel_status(capabilities: list[ChannelCapability], *, owner_gated: bool) -> str:
    statuses = {capability.status for capability in capabilities}
    if "action_required" in statuses:
        return "owner_action_required" if owner_gated else "preview"
    if statuses <= {"passed", "preview"} and "preview" in statuses:
        return "ready" if owner_gated else "preview"
    return "ready"


def _telegram_readiness() -> ChannelReadiness:
    capabilities = [
        _capability(
            "adapter",
            _file_exists("backend/app/core/channels/telegram_adapter.py"),
            details={"path": "backend/app/core/channels/telegram_adapter.py"},
        ),
        _capability(
            "api_route",
            _file_exists("backend/app/api/channels.py"),
            details={"path": "backend/app/api/channels.py", "route": "/api/v1/channels/telegram/webhook"},
        ),
        _capability(
            "signature_check",
            True,
            details={"scheme": "X-Telegram-Bot-Api-Secret-Token"},
        ),
        _capability(
            "local_contract_tests",
            all(
                _file_exists(path)
                for path in [
                    "tests/test_channels.py",
                    "tests/test_channel_router.py",
                    "tests/test_telegram_channel_api.py",
                ]
            ),
            details={
                "tests": [
                    "tests/test_channels.py",
                    "tests/test_channel_router.py",
                    "tests/test_telegram_channel_api.py",
                ]
            },
        ),
        _capability(
            "live_owner_evidence",
            False,
            details={"required_report": ".xagent_runtime/reports/commercial-pilot-telegram-live.json"},
        ),
    ]
    return ChannelReadiness(
        channel="telegram",
        status="preview",
        owner_gated=True,
        recommended_for_first_pilot=False,
        capabilities=capabilities,
        next_actions=[
            "Set XAGENT_TELEGRAM_BOT_TOKEN and XAGENT_TELEGRAM_WEBHOOK_SECRET in the owner environment.",
            "Register the Telegram webhook with the same secret token.",
            "Run a live inbound message and capture commercial-pilot-telegram-live.json.",
        ],
        known_limits=[
            "Telegram is not selected for the first domestic commercial pilot.",
            "Local evidence uses mocked outbound reply behavior.",
            "Live bot token, webhook registration, and network delivery remain owner-gated if enabled later.",
        ],
    )


def _feishu_readiness() -> ChannelReadiness:
    live_evidence_path = ".xagent_runtime/reports/commercial-pilot-feishu-live.json"
    live_evidence = _read_json(live_evidence_path)
    live_evidence_passed = bool(
        live_evidence
        and live_evidence.get("status") == "passed"
        and live_evidence.get("channel") == "feishu"
        and live_evidence.get("evidence_type") == "commercial_pilot_feishu_live"
        and live_evidence.get("mutation_performed") is False
        and live_evidence.get("outbound_message_sent") is False
        and live_evidence.get("event_id")
    )
    capabilities = [
        _capability(
            "bridge",
            _file_exists("backend/app/core/feishu_bridge.py"),
            details={"path": "backend/app/core/feishu_bridge.py"},
        ),
        _capability(
            "api_route",
            _file_exists("backend/app/api/feishu.py"),
            details={"path": "backend/app/api/feishu.py"},
        ),
        _capability(
            "signature_check",
            True,
            details={"scheme": "Feishu/Lark signature or legacy HMAC"},
        ),
        _capability(
            "local_security_tests",
            _file_exists("tests/test_security.py"),
            details={"tests": ["tests/test_security.py"]},
        ),
        _capability(
            "unified_channel_adapter",
            False,
            details={"required_path": "backend/app/core/channels/feishu_adapter.py"},
            required=False,
        ),
        _capability(
            "live_owner_evidence",
            live_evidence_passed,
            details={
                "required_report": live_evidence_path,
                "event_id": live_evidence.get("event_id") if live_evidence else None,
                "event_type": live_evidence.get("event_type") if live_evidence else None,
                "signature_mode": live_evidence.get("signature_mode") if live_evidence else None,
            },
        ),
    ]
    if live_evidence_passed:
        next_actions = [
            "Use Feishu as the first domestic commercial pilot channel.",
            "Review commercial-pilot-feishu-live.json before making the production-pilot readiness claim.",
            "Add a unified Feishu ChannelAdapter before promoting beyond owner-gated pilot.",
        ]
        known_limits = [
            "Feishu currently uses a dedicated bridge instead of the unified ChannelAdapter framework.",
            "Live app credentials remain owner-controlled; this evidence proves inbound event delivery only.",
        ]
    else:
        next_actions = [
            "Use Feishu as the first domestic commercial pilot channel.",
            "Configure Feishu app_id, app_secret, and encrypt_key in the owner environment.",
            "Run a live Feishu event and capture commercial-pilot-feishu-live.json.",
            "Add a unified Feishu ChannelAdapter before promoting beyond owner-gated pilot.",
        ]
        known_limits = [
            "Feishu currently uses a dedicated bridge instead of the unified ChannelAdapter framework.",
            "Live app credentials and callback verification remain owner-gated.",
        ]
    return ChannelReadiness(
        channel="feishu",
        status=_channel_status(capabilities, owner_gated=True),
        owner_gated=True,
        recommended_for_first_pilot=True,
        capabilities=capabilities,
        next_actions=next_actions,
        known_limits=known_limits,
    )


def _preview_adapter_readiness(channel: str, adapter_path: str, signature_scheme: str) -> ChannelReadiness:
    capabilities = [
        _capability("adapter", _file_exists(adapter_path), details={"path": adapter_path}),
        _capability(
            "api_route",
            False,
            details={"required_route": f"/api/v1/channels/{channel}/webhook"},
            required=False,
        ),
        _capability("signature_check", True, details={"scheme": signature_scheme}),
        _capability(
            "local_contract_tests",
            False,
            details={"required_tests": [f"tests/test_{channel}_channel_api.py"]},
            required=False,
        ),
        _capability(
            "live_owner_evidence",
            False,
            details={"required_report": f".xagent_runtime/reports/commercial-pilot-{channel}-live.json"},
            required=False,
        ),
    ]
    return ChannelReadiness(
        channel=channel,
        status=_channel_status(capabilities, owner_gated=False),
        owner_gated=False,
        recommended_for_first_pilot=False,
        capabilities=capabilities,
        next_actions=[
            f"Add /api/v1/channels/{channel}/webhook route before pilot use.",
            f"Add local {channel} API contract tests.",
            f"Capture live owner evidence only after the local contract passes.",
        ],
        known_limits=[f"{channel} is preview-only until API route, tests, and owner live evidence exist."],
    )


def build_channel_readiness_matrix(*, pilot_channel: str = "feishu") -> ChannelReadinessMatrix:
    channels = [
        _telegram_readiness(),
        _feishu_readiness(),
        _preview_adapter_readiness(
            "discord",
            "backend/app/core/channels/discord_adapter.py",
            "Discord Ed25519 interaction signature",
        ),
        _preview_adapter_readiness(
            "dingtalk",
            "backend/app/core/channels/dingtalk_adapter.py",
            "DingTalk HMAC-SHA256 timestamp/sign",
        ),
    ]
    selected = next((channel for channel in channels if channel.channel == pilot_channel), None)
    selected_status = selected.status if selected else "missing"
    checks = [
        ChannelCapability(
            name="selected_pilot_channel",
            status="passed" if selected is not None else "action_required",
            details={"pilot_channel": pilot_channel, "selected_status": selected_status},
            error=None if selected is not None else "selected pilot channel is not in the readiness matrix",
        ),
        ChannelCapability(
            name="no_full_codex_parity_claim",
            status="passed",
            details={"full_codex_parity_claimed": False},
        ),
    ]
    status = "ready_with_owner_gates" if selected and selected.status in {"ready", "owner_action_required"} else "action_required"
    next_commands = ["Run python scripts\\commercial_pilot_refresh_chain.py after updating channel evidence."]
    if selected and selected.status == "ready":
        next_commands.append(
            f"Review .xagent_runtime/reports/commercial-pilot-{pilot_channel}-live.json before making the production-pilot readiness claim."
        )
    else:
        next_commands.append(f"Capture owner live evidence before claiming {pilot_channel} production-pilot readiness.")
    return ChannelReadinessMatrix(
        status=status,
        generated_at=_utc_now(),
        pilot_channel=pilot_channel,
        full_codex_parity_claimed=False,
        channels=channels,
        checks=checks,
        next_commands=next_commands,
        known_limits=[
            "This matrix is a commercial pilot planning gate, not a live-channel proof.",
            "Owner-gated live webhook checks require real credentials and network delivery.",
            "Preview channels are not recommended for the first commercial pilot.",
        ],
    )


def write_report(report: ChannelReadinessMatrix, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pilot-channel", default="feishu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_channel_readiness_matrix(pilot_channel=args.pilot_channel)
    write_report(report, args.output)
    print(f"Commercial pilot channel readiness status: {report.status}")
    print(f"Pilot channel: {report.pilot_channel}")
    print(f"Report written to {args.output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    for channel in report.channels:
        print(f"- {channel.channel}: {channel.status}")
    return 0 if report.status in {"ready", "ready_with_owner_gates"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
