from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.channels import get_channel_router, router as channels_router
from backend.app.api.sandbox_tasks import router as sandbox_router
from backend.app.core.channels import ChannelConfig, ChannelRegistry, TelegramAdapter
from backend.app.core.channels.router import ChannelRouter


def test_telegram_webhook_fails_closed_when_secret_missing() -> None:
    app = FastAPI()
    app.include_router(channels_router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    client = TestClient(app)

    response = client.post(
        "/api/v1/channels/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "anything"},
        json={"message": {"message_id": 1, "text": "hi", "chat": {"id": 1}}},
    )

    assert response.status_code == 401


def test_telegram_webhook_fails_closed_with_empty_adapter_secret() -> None:
    app = FastAPI()
    app.include_router(channels_router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)

    def override_router() -> ChannelRouter:
        registry = ChannelRegistry()
        registry.register(TelegramAdapter(ChannelConfig(token="token", signing_secret="")))
        return ChannelRouter(registry)

    app.dependency_overrides[get_channel_router] = override_router
    client = TestClient(app)

    response = client.post(
        "/api/v1/channels/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "anything"},
        json={"message": {"message_id": 1, "text": "hi", "chat": {"id": 1}}},
    )

    assert response.status_code == 401


def test_github_webhook_fails_closed_when_secret_missing(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_GITHUB_WEBHOOK_SECRET", raising=False)
    app = FastAPI()
    app.include_router(sandbox_router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    client = TestClient(app)

    response = client.post(
        "/api/v1/sandbox/webhook/github",
        json={"action": "assigned", "issue": {"number": 1}},
    )

    assert response.status_code == 403
