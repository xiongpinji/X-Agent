from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.channel_integration_readiness import (
    assess_channel_integration,
    build_channel_integration_readiness,
)


def test_channel_readiness_marks_complete_bidirectional_channel_ready() -> None:
    matrix = build_channel_integration_readiness(
        {
            "workspace": "tenant-a",
            "channels": [
                {
                    "channel": "github",
                    "name": "github-issues",
                    "direction": "bidirectional",
                    "auth": {"configured": True, "mode": "app"},
                    "signature_verified": True,
                    "callback_evidence": [{"event_id": "evt-1", "status": "passed"}],
                    "delivery_evidence": [{"delivery_id": "del-1", "status": "delivered"}],
                    "correlation_id": "corr-1",
                    "retry_policy": {"enabled": True, "max_attempts": 3},
                    "mutation_requested": True,
                    "owner_approved": True,
                }
            ],
        }
    )

    assert matrix["kind"] == "channel_integration_readiness"
    assert matrix["ok"] is True
    assert matrix["status"] == "ready"
    assert matrix["summary"]["ready_count"] == 1
    assert matrix["next_actions"] == ["prepare_channel_integration_review"]


def test_outbound_mutation_without_owner_approval_blocks() -> None:
    matrix = build_channel_integration_readiness(
        {
            "channels": [
                {
                    "channel": "slack",
                    "direction": "outbound",
                    "auth_mode": "bot_token",
                    "delivery_receipt": "ok",
                    "delivery_id": "d1",
                    "retry_policy": "exponential",
                    "send_message": True,
                }
            ]
        }
    )

    assert matrix["status"] == "blocked"
    assert matrix["channels"][0]["decision"] == "blocked"
    assert matrix["issues"][0]["code"] == "channel_integration_owner_approval_missing"
    assert matrix["next_actions"] == ["obtain_owner_approval_before_outbound_send", "refresh_channel_readiness"]


def test_inbound_without_signature_or_callback_evidence_needs_review() -> None:
    matrix = build_channel_integration_readiness(
        {
            "channels": [
                {
                    "provider": "linear",
                    "mode": "inbound",
                    "token_ref": "linear-token",
                    "request_id": "req-1",
                    "retry_policy": {"enabled": True},
                }
            ]
        }
    )

    assert matrix["status"] == "needs_review"
    assert "signature verification missing" in matrix["channels"][0]["reasons"]
    assert "callback evidence missing" in matrix["channels"][0]["reasons"]
    assert matrix["issues"][0]["code"] == "channel_integration_signature_missing"


def test_unsupported_channel_is_blocked() -> None:
    item = assess_channel_integration(
        {
            "channel": "unknown-chat",
            "auth": "token",
            "signature_verified": True,
            "callback_received": True,
            "event_id": "evt",
            "retry_policy": "retry",
        }
    )

    assert item.decision == "blocked"
    assert "unsupported channel" in item.reasons


def test_missing_correlation_or_retry_policy_needs_review() -> None:
    matrix = build_channel_integration_readiness(
        {
            "channels": [
                {
                    "channel": "feishu",
                    "direction": "inbound",
                    "auth": "app_secret",
                    "signature_verified": True,
                    "callback_evidence": [{"status": "passed"}],
                }
            ]
        }
    )

    assert matrix["status"] == "needs_review"
    assert "correlation id missing" in matrix["channels"][0]["reasons"]
    assert "retry policy missing" in matrix["channels"][0]["reasons"]
    assert matrix["issues"][0]["code"] == "channel_integration_correlation_missing"


def test_accepts_mapping_and_dataclass_like_channel_payloads() -> None:
    @dataclass
    class Channel:
        channel: str
        direction: str
        auth: str
        signature_verified: bool
        event_id: str
        callback_evidence: list[dict[str, str]]
        retry_policy: str

    matrix = build_channel_integration_readiness(
        {
            "integrations": {
                "teams": Channel(
                    "teams",
                    "inbound",
                    "bearer",
                    True,
                    "evt-1",
                    [{"status": "passed"}],
                    "retry",
                )
            }
        }
    )

    assert matrix["status"] == "ready"
    assert matrix["channels"][0]["channel"] == "teams"
    assert matrix["channels"][0]["callback_evidence_count"] == 2


def test_empty_matrix_requests_channel_payloads() -> None:
    matrix = build_channel_integration_readiness({})

    assert matrix["status"] == "empty"
    assert matrix["ok"] is False
    assert matrix["next_actions"] == ["provide_channel_payloads"]
