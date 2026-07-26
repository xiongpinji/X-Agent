from __future__ import annotations

import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from backend.app.api.channels import get_channel_router
from backend.app.core.channels import ChannelConfig, ChannelRegistry, SlackAdapter
from backend.app.core.channels.base import ChannelMessage
from backend.app.core.channels.router import ChannelRouter
from backend.app.main import CSRFProtectionMiddleware, app

_SECRET = "slack-signing-secret"
_EVENTS_PATH = "/api/v1/channels/slack/events"

# The Slack webhook is HMAC-signature authenticated server-to-server traffic;
# like the Telegram webhook it belongs in main.py's CSRF/API-key exemption
# sets (orchestrator-owned file). Mirror that exemption here so tests exercise
# the post-exemption behavior.
def setup_function() -> None:
    CSRFProtectionMiddleware.EXEMPT_PATHS.add(_EVENTS_PATH)


def _sign(body: bytes, secret: str = _SECRET, timestamp: str | None = None) -> dict[str, str]:
    ts = timestamp or str(int(time.time()))
    basestring = b"v0:" + ts.encode() + b":" + body
    signature = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return {
        "X-Slack-Signature": signature,
        "X-Slack-Request-Timestamp": ts,
        "Content-Type": "application/json",
    }


def _post(client: TestClient, payload: dict, secret: str = _SECRET) -> object:
    body = json.dumps(payload).encode()
    return client.post("/api/v1/channels/slack/events", content=body, headers=_sign(body, secret))


def _client_with_router() -> tuple[TestClient, list[tuple[str, str]]]:
    sent: list[tuple[str, str]] = []

    async def dispatch_message(message: ChannelMessage) -> dict[str, object]:
        return {
            "run_id": "run-api-slack",
            "status": "accepted",
            "reply_text": f"handled {message.text}",
            "dispatch": {"source": "test", "task": message.text},
        }

    async def reply_sender(message: ChannelMessage, text: str) -> dict[str, object]:
        sent.append((message.conversation_id, text))
        return {"ok": True}

    def override_router() -> ChannelRouter:
        registry = ChannelRegistry()
        registry.register(SlackAdapter(ChannelConfig(token="xoxb-test", signing_secret=_SECRET)))
        return ChannelRouter(
            registry,
            dispatch_callable=dispatch_message,
            reply_sender=reply_sender,
        )

    app.dependency_overrides[get_channel_router] = override_router
    return TestClient(app), sent


def teardown_function() -> None:
    app.dependency_overrides.pop(get_channel_router, None)
    CSRFProtectionMiddleware.EXEMPT_PATHS.discard(_EVENTS_PATH)


def test_slack_url_verification_echoes_challenge_with_valid_signature() -> None:
    client, sent = _client_with_router()

    response = _post(client, {"type": "url_verification", "challenge": "ch-123"})

    assert response.status_code == 200
    assert response.json() == {"challenge": "ch-123"}
    assert sent == []


def test_slack_message_event_dispatches_and_replies() -> None:
    client, sent = _client_with_router()

    response = _post(
        client,
        {
            "type": "event_callback",
            "team_id": "T1",
            "event_id": "Ev1",
            "event": {
                "type": "message",
                "user": "U123",
                "channel": "C456",
                "text": "ship status",
                "ts": "1700000000.000100",
                "client_msg_id": "msg-1",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["channel"] == "slack"
    assert payload["conversation_id"] == "C456"
    assert payload["message_id"] == "msg-1"
    assert payload["run_id"] == "run-api-slack"
    assert payload["status"] == "accepted"
    assert payload["reply_sent"] is True
    assert payload["reply_text"] == "handled ship status"
    assert payload["sender_id"] == "U123"
    assert sent == [("C456", "handled ship status")]


def test_slack_webhook_rejects_invalid_signature() -> None:
    client, _ = _client_with_router()

    response = _post(
        client,
        {"type": "url_verification", "challenge": "ch-123"},
        secret="wrong-secret",
    )

    assert response.status_code == 401


def test_slack_webhook_rejects_stale_timestamp() -> None:
    client, _ = _client_with_router()
    body = json.dumps({"type": "url_verification", "challenge": "ch"}).encode()
    stale = str(int(time.time()) - 3600)

    response = client.post(
        "/api/v1/channels/slack/events",
        content=body,
        headers=_sign(body, timestamp=stale),
    )

    assert response.status_code == 401


def test_slack_webhook_unconfigured_fails_loudly(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("XAGENT_SLACK_SIGNING_SECRET", raising=False)
    client = TestClient(app)
    body = json.dumps({"type": "url_verification", "challenge": "ch"}).encode()

    response = client.post(
        "/api/v1/channels/slack/events",
        content=body,
        headers=_sign(body),
    )

    assert response.status_code == 503
    assert "XAGENT_SLACK_BOT_TOKEN" in response.text


def test_slack_webhook_ignores_bot_and_subtype_messages() -> None:
    client, sent = _client_with_router()

    for event in (
        {"type": "message", "bot_id": "B1", "channel": "C1", "text": "bot echo"},
        {"type": "message", "subtype": "message_changed", "channel": "C1", "text": "edit"},
        {"type": "reaction_added", "user": "U1"},
    ):
        response = _post(client, {"type": "event_callback", "event": event})
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    assert sent == []
