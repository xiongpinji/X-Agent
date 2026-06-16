from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.channels import get_channel_router
from backend.app.core.channels import ChannelConfig, ChannelRegistry, TelegramAdapter
from backend.app.core.channels.base import ChannelMessage
from backend.app.core.channels.router import ChannelRouter
from backend.app.main import app


def _client_with_router() -> tuple[TestClient, list[tuple[str, str]]]:
    sent: list[tuple[str, str]] = []

    async def dispatch_message(message: ChannelMessage) -> dict[str, object]:
        return {
            "run_id": "run-api-telegram",
            "status": "accepted",
            "reply_text": f"handled {message.text}",
            "dispatch": {"source": "test", "task": message.text},
        }

    async def reply_sender(message: ChannelMessage, text: str) -> dict[str, object]:
        sent.append((message.conversation_id, text))
        return {"ok": True}

    def override_router() -> ChannelRouter:
        registry = ChannelRegistry()
        registry.register(TelegramAdapter(ChannelConfig(token="token", signing_secret="secret")))
        return ChannelRouter(
            registry,
            dispatch_callable=dispatch_message,
            reply_sender=reply_sender,
        )

    app.dependency_overrides[get_channel_router] = override_router
    return TestClient(app), sent


def teardown_function() -> None:
    app.dependency_overrides.pop(get_channel_router, None)


def test_telegram_webhook_dispatches_and_replies_with_mocked_sender() -> None:
    client, sent = _client_with_router()

    response = client.post(
        "/api/v1/channels/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        json={
            "message": {
                "message_id": 9,
                "text": "ship status",
                "chat": {"id": 111},
                "from": {"id": 222},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["channel"] == "telegram"
    assert payload["conversation_id"] == "111"
    assert payload["message_id"] == "9"
    assert payload["run_id"] == "run-api-telegram"
    assert payload["status"] == "accepted"
    assert payload["reply_sent"] is True
    assert payload["reply_text"] == "handled ship status"
    assert sent == [("111", "handled ship status")]


def test_telegram_webhook_rejects_invalid_signature() -> None:
    client, _ = _client_with_router()

    response = client.post(
        "/api/v1/channels/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"message": {"message_id": 1, "text": "hello", "chat": {"id": 1}}},
    )

    assert response.status_code == 401


def test_telegram_webhook_rejects_when_secret_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("XAGENT_TELEGRAM_SIGNING_SECRET", raising=False)
    client = TestClient(app)

    response = client.post(
        "/api/v1/channels/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        json={"message": {"message_id": 1, "text": "hello", "chat": {"id": 1}}},
    )

    assert response.status_code == 401


def test_telegram_webhook_ignores_non_message_payload() -> None:
    client, sent = _client_with_router()

    response = client.post(
        "/api/v1/channels/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        json={"poll": {"id": "p1"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ignored"
    assert payload["reply_sent"] is False
    assert sent == []
