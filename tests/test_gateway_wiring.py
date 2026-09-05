"""MessagingGateway <-> channels API 接线测试。

验证 backend/app/api/channels.py 中新增的 /api/v1/channels/gateway/* 端点把
core/messaging_gateway.py 的 MessagingGateway 从死代码接活：

- 注册（mock channel，不打真平台）→ status 可见
- send 直达 channel.send_message；broadcast 多平台送达
- incoming 消息触发默认 agent handler（mock agent）并把回复送回 channel
- Telegram webhook 消息在平台注册进 gateway 后也走同一 agent 回路
- start/stop 幂等；可选依赖缺失 fail-closed 返回可诊断错误
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import backend.app.api.channels as channels_api
from backend.app.api.channels import (
    GatewayDependencyMissingError,
    get_channel_router,
    set_gateway_agent_handler,
)
from backend.app.core.channels import ChannelConfig, ChannelRegistry, TelegramAdapter
from backend.app.core.channels.router import ChannelRouter
from backend.app.core.contracts import RunContext
from backend.app.core.messaging_gateway import (
    BaseChannel,
    ChannelConfig as GatewayChannelConfig,
    IncomingMessage,
    OutgoingMessage,
    PlatformType,
    get_messaging_gateway,
)
from backend.app.main import app


class MockChannel(BaseChannel):
    """进程内假 channel：记录发出的消息，可注入入站消息。"""

    def __init__(self, config: GatewayChannelConfig):
        super().__init__(config)
        self.sent: list[OutgoingMessage] = []

    @property
    def platform(self) -> PlatformType:
        return self.config.platform

    async def connect(self) -> bool:
        self._running = True
        return True

    async def disconnect(self) -> None:
        self._running = False

    async def send_message(self, message: OutgoingMessage) -> bool:
        self.sent.append(message)
        return True

    async def is_connected(self) -> bool:
        return self._running

    async def simulate_incoming(self, content: str, channel_id: str = "42") -> None:
        await self._dispatch_message(
            IncomingMessage(
                platform=self.platform, channel_id=channel_id, content=content
            )
        )


class _MockAgentResponse:
    def __init__(self, answer: str) -> None:
        self.answer = answer


class _MockAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def run(self, context: RunContext, task: str, **kwargs) -> _MockAgentResponse:
        self.calls.append((type(context).__name__, task))
        return _MockAgentResponse(f"echo: {task}")


@pytest.fixture(autouse=True)
def _clean_gateway_state():
    """每个测试后清空 gateway 单例状态，避免跨测试泄漏（telegram webhook
    测试共享同一进程，注册残留会让 webhook 触发真实 agent 构建）。"""
    yield
    gateway = get_messaging_gateway()
    for platform in list(gateway._channels.keys()):
        channel = gateway.unregister_channel(platform)
        if channel is not None:
            try:
                asyncio.run(channel.disconnect())
            except Exception:
                pass
    gateway._running = False
    set_gateway_agent_handler(None)
    app.dependency_overrides.pop(get_channel_router, None)


@pytest.fixture
def mock_channel_factory(monkeypatch):
    """把 api 层 channel 工厂换成 MockChannel（绕过可选依赖/真平台）。"""
    created: list[MockChannel] = []

    def factory(platform: PlatformType, config: GatewayChannelConfig) -> MockChannel:
        channel = MockChannel(config)
        created.append(channel)
        return channel

    monkeypatch.setattr(channels_api, "_build_gateway_channel", factory)
    return created


def _client() -> TestClient:
    # 与 tests/test_api.py 同款：x-api-key 走 bootstrap key（tests/conftest.py
    # 设 XAGENT_BOOTSTRAP_API_KEY=bootstrap），同时豁免 CSRF 中间件。
    return TestClient(app, headers={"x-api-key": "bootstrap"})


# ─── 注册 / 状态 / 发送 / 广播 ────────────────────────────────────────────────


def test_register_status_send_broadcast_flow(mock_channel_factory) -> None:
    client = _client()

    response = client.post(
        "/api/v1/channels/gateway/register", json={"platform": "telegram", "token": "t"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "platform": "telegram",
        "registered": True,
        "connected": True,
        "connect_requested": True,
    }

    client.post(
        "/api/v1/channels/gateway/register", json={"platform": "discord", "token": "d"}
    )

    status = client.get("/api/v1/channels/gateway/status").json()
    assert status["running"] is False  # 未显式 start
    assert set(status["channels"]) == {"telegram", "discord"}
    assert status["channels"]["telegram"] == {"enabled": True, "connected": True}
    assert status["agent_handler"] == "default"

    send = client.post(
        "/api/v1/channels/gateway/send",
        json={"platform": "telegram", "channel_id": "42", "content": "hello out"},
    )
    assert send.status_code == 200
    assert send.json()["sent"] is True
    assert [m.content for m in mock_channel_factory[0].sent] == ["hello out"]
    assert mock_channel_factory[0].sent[0].channel_id == "42"

    broadcast = client.post(
        "/api/v1/channels/gateway/broadcast",
        json={
            "content": "announce",
            "platforms": ["telegram", "discord"],
            "channel_ids": {"telegram": "42", "discord": "77"},
        },
    )
    assert broadcast.status_code == 200
    payload = broadcast.json()
    assert payload["results"] == {"telegram": True, "discord": True}
    assert payload["delivered"] == 2
    assert [m.content for m in mock_channel_factory[0].sent] == ["hello out", "announce"]
    assert [m.content for m in mock_channel_factory[1].sent] == ["announce"]
    assert mock_channel_factory[1].sent[0].channel_id == "77"


def test_broadcast_defaults_to_all_registered_platforms(mock_channel_factory) -> None:
    client = _client()
    client.post("/api/v1/channels/gateway/register", json={"platform": "whatsapp"})
    client.post("/api/v1/channels/gateway/register", json={"platform": "telegram"})

    broadcast = client.post(
        "/api/v1/channels/gateway/broadcast",
        json={"content": "to all", "channel_ids": {"whatsapp": "1", "telegram": "2"}},
    )
    assert broadcast.status_code == 200
    assert broadcast.json()["results"] == {"whatsapp": True, "telegram": True}


def test_broadcast_without_channels_is_rejected() -> None:
    client = _client()
    response = client.post("/api/v1/channels/gateway/broadcast", json={"content": "x"})
    assert response.status_code == 400


# ─── Agent 回路：incoming -> 默认 handler -> mock agent -> 回复送回 channel ──


async def test_incoming_message_triggers_default_agent_handler(
    mock_channel_factory, monkeypatch
) -> None:
    import backend.app.dependencies as dependencies

    mock_agent = _MockAgent()
    monkeypatch.setattr(dependencies, "get_agent", lambda: mock_agent)

    client = _client()
    client.post("/api/v1/channels/gateway/register", json={"platform": "telegram"})

    channel = mock_channel_factory[0]
    await channel.simulate_incoming("hello agent", channel_id="42")

    # 默认 handler 调用了 get_agent().run(RunContext(), content)
    assert mock_agent.calls == [("RunContext", "hello agent")]
    # 回复经 gateway.send 送回来源 channel
    assert len(channel.sent) == 1
    assert channel.sent[0].content == "echo: hello agent"
    assert channel.sent[0].channel_id == "42"
    assert channel.sent[0].platform is PlatformType.TELEGRAM

    # 消息同时进入 gateway 队列（既有语义保留）
    gateway = get_messaging_gateway()
    assert gateway.message_queue.qsize() == 1
    queued = gateway.message_queue._queue[0]
    assert queued.content == "hello agent"


async def test_custom_agent_handler_receives_incoming(mock_channel_factory) -> None:
    seen: list[IncomingMessage] = []

    async def handler(message: IncomingMessage) -> str:
        seen.append(message)
        return f"custom reply to {message.username or message.user_id}"

    set_gateway_agent_handler(handler)

    client = _client()
    client.post("/api/v1/channels/gateway/register", json={"platform": "discord"})

    channel = mock_channel_factory[0]
    await channel.simulate_incoming("ping", channel_id="9")

    assert [m.content for m in seen] == ["ping"]
    assert channel.sent[0].content == "custom reply to "
    # 自定义 handler 在 status 中可见
    status = _client().get("/api/v1/channels/gateway/status").json()
    assert status["agent_handler"] == "custom"


async def test_failing_handler_degrades_to_error_text(mock_channel_factory) -> None:
    async def handler(message: IncomingMessage) -> str:
        raise RuntimeError("boom")

    set_gateway_agent_handler(handler)

    client = _client()
    client.post("/api/v1/channels/gateway/register", json={"platform": "telegram"})

    channel = mock_channel_factory[0]
    await channel.simulate_incoming("hello", channel_id="1")

    assert len(channel.sent) == 1
    assert "boom" in channel.sent[0].content


# ─── Telegram webhook -> 同一 agent 回路 ─────────────────────────────────────


def _override_telegram_router() -> None:
    """webhook 侧 router：只验签 + 静默 dispatch（不回 webhook 自身的回复），
    以此断言回复完全来自 gateway agent 回路。"""

    async def silent_dispatch(message):  # type: ignore[no-untyped-def]
        return {"run_id": "run-gw", "status": "accepted", "reply_text": ""}

    registry = ChannelRegistry()
    registry.register(
        TelegramAdapter(ChannelConfig(token="token", signing_secret="secret"))
    )
    app.dependency_overrides[get_channel_router] = lambda: ChannelRouter(
        registry, dispatch_callable=silent_dispatch
    )


def test_telegram_webhook_forwards_to_gateway_agent_loop(mock_channel_factory) -> None:
    _override_telegram_router()
    client = _client()
    webhook_payload = {
        "message": {
            "message_id": 7,
            "text": "ship status",
            "chat": {"id": 111},
            "from": {"id": 222},
        }
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": "secret"}

    # 平台未注册进 gateway：webhook 行为保持原样，不触发 agent 回路
    before = client.post(
        "/api/v1/channels/telegram/webhook", headers=headers, json=webhook_payload
    )
    assert before.status_code == 200
    assert "gateway" not in before.json()

    # 注册进 gateway + 注入自定义 agent handler -> 走同一回路并把回复送回 channel
    seen: list[IncomingMessage] = []

    async def handler(message: IncomingMessage) -> str:
        seen.append(message)
        return f"gateway says: {message.content}"

    set_gateway_agent_handler(handler)
    client.post("/api/v1/channels/gateway/register", json={"platform": "telegram"})

    after = client.post(
        "/api/v1/channels/telegram/webhook", headers=headers, json=webhook_payload
    )
    assert after.status_code == 200
    gateway_section = after.json()["gateway"]
    assert gateway_section["platform"] == "telegram"
    assert gateway_section["reply"] == "gateway says: ship status"
    assert gateway_section["reply_sent"] is True

    assert [m.content for m in seen] == ["ship status"]
    channel = mock_channel_factory[0]
    assert channel.sent[0].content == "gateway says: ship status"
    assert channel.sent[0].channel_id == "111"


# ─── 生命周期与 fail-closed ──────────────────────────────────────────────────


def test_start_stop_idempotent(mock_channel_factory) -> None:
    client = _client()

    stop_before = client.post("/api/v1/channels/gateway/stop").json()
    assert stop_before["stopped"] is False
    assert stop_before["already_stopped"] is True

    client.post(
        "/api/v1/channels/gateway/register",
        json={"platform": "telegram", "connect": False},
    )
    # register connect=False：未连接、未启动
    assert client.get("/api/v1/channels/gateway/status").json()["running"] is False

    started = client.post("/api/v1/channels/gateway/start").json()
    assert started["started"] is True
    assert started["already_running"] is False
    assert started["status"]["running"] is True
    assert started["status"]["channels"]["telegram"]["connected"] is True

    again = client.post("/api/v1/channels/gateway/start").json()
    assert again["started"] is False
    assert again["already_running"] is True

    stopped = client.post("/api/v1/channels/gateway/stop").json()
    assert stopped["stopped"] is True
    assert stopped["already_stopped"] is False
    assert stopped["status"]["running"] is False

    stopped_again = client.post("/api/v1/channels/gateway/stop").json()
    assert stopped_again["stopped"] is False
    assert stopped_again["already_stopped"] is True


def test_start_without_channels_is_rejected() -> None:
    client = _client()
    response = client.post("/api/v1/channels/gateway/start")
    assert response.status_code == 400


def test_register_fail_closed_on_missing_dependency(monkeypatch) -> None:
    def factory(platform: PlatformType, config: GatewayChannelConfig) -> BaseChannel:
        raise GatewayDependencyMissingError(
            "discord.py is not installed. Install with: pip install discord.py"
        )

    monkeypatch.setattr(channels_api, "_build_gateway_channel", factory)
    client = _client()

    response = client.post(
        "/api/v1/channels/gateway/register", json={"platform": "discord", "token": "t"}
    )
    assert response.status_code == 503
    assert "pip install discord.py" in response.json()["message"]

    # fail-closed：没有留下半注册状态
    assert get_messaging_gateway()._channels == {}


def test_register_unsupported_platform_fails_closed() -> None:
    client = _client()
    response = client.post(
        "/api/v1/channels/gateway/register", json={"platform": "feishu"}
    )
    assert response.status_code == 400
    assert "no MessagingGateway channel implementation" in response.json()["message"]
    assert get_messaging_gateway()._channels == {}


def test_register_unknown_platform_name_rejected() -> None:
    client = _client()
    response = client.post(
        "/api/v1/channels/gateway/register", json={"platform": "icq"}
    )
    assert response.status_code == 400


def test_send_without_registered_platform_is_404() -> None:
    client = _client()
    response = client.post(
        "/api/v1/channels/gateway/send",
        json={"platform": "whatsapp", "channel_id": "1", "content": "x"},
    )
    assert response.status_code == 404
