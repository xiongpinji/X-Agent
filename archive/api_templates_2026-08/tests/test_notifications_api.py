"""
通知系统新增端点测试: POST /subscribe(JSON 文件存储)、WS /ws(连接/心跳/ping-pong)、
POST /broadcast/test(真实广播投递)。
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api import notifications as notif_mod
from backend.app.core.notification_subscriptions import (
    get_subscription_store,
    reset_subscription_store,
)
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

AUTH_HEADERS = {"x-api-key": "bootstrap"}

SUBSCRIBE_BODY = {
    "subscription": {
        "endpoint": "https://push.example.com/sub/abc123",
        "keys": {"p256dh": "BPp256dhKeyExample", "auth": "authSecretExample"},
    },
    "user_agent": "pytest-agent",
}


@pytest.fixture
def subscription_store(tmp_path, monkeypatch):
    """隔离的 JSON 订阅存储(临时文件)。"""
    monkeypatch.setenv(
        "XAGENT_NOTIFICATION_SUBSCRIPTION_STORE_PATH",
        str(tmp_path / "notification_subscriptions.json"),
    )
    reset_subscription_store()
    yield get_subscription_store()
    reset_subscription_store()


@pytest.fixture
def client(subscription_store):
    # 不进入 lifespan: 路由已由 tests/conftest.py 幂等注册,
    # 通知端点不依赖 startup 初始化的 DB。
    c = TestClient(app)
    yield c
    app.dependency_overrides.pop(get_current_principal, None)


def _use(principal: Principal) -> None:
    app.dependency_overrides[get_current_principal] = lambda: principal


class TestSubscribe:
    def test_subscribe_success(self, client, subscription_store):
        _use(Principal(
            user_id="notif-user-1",
            tenant_id="notif-tenant-1",
            role="user",
            scopes=["notifications:subscribe"],
            authenticated=True,
        ))
        resp = client.post(
            "/api/v1/notifications/subscribe",
            json=SUBSCRIBE_BODY,
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "subscribed"
        assert data["user_id"] == "notif-user-1"
        assert data["tenant_id"] == "notif-tenant-1"
        assert subscription_store.count() == 1
        assert subscription_store._storage_path.exists()

    def test_subscribe_dedupes_same_endpoint(self, client, subscription_store):
        _use(Principal(
            user_id="notif-user-1",
            tenant_id="notif-tenant-1",
            role="user",
            scopes=["notifications:subscribe"],
            authenticated=True,
        ))
        for _ in range(2):
            resp = client.post(
                "/api/v1/notifications/subscribe",
                json=SUBSCRIBE_BODY,
                headers=AUTH_HEADERS,
            )
            assert resp.status_code == 201
        assert subscription_store.count() == 1

    def test_subscribe_requires_scope_when_authenticated(self, client):
        _use(Principal(
            user_id="notif-user-2",
            tenant_id="notif-tenant-1",
            role="user",
            scopes=[],
            authenticated=True,
        ))
        resp = client.post(
            "/api/v1/notifications/subscribe",
            json=SUBSCRIBE_BODY,
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 403

    def test_subscribe_anonymous_dev_fallback(self, client, subscription_store):
        # 匿名主体(开发模式回落): 订阅按 anonymous 记录。
        # 注: 真实无凭证 POST 会被 CSRF 中间件拦截(403), 这里通过依赖覆盖
        # 注入匿名 principal 验证端点内部的分支逻辑。
        _use(Principal(authenticated=False))
        resp = client.post(
            "/api/v1/notifications/subscribe",
            json=SUBSCRIBE_BODY,
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["user_id"] == "anonymous"


class TestNotificationWebSocket:
    def test_ws_connect_and_ping_pong(self, client):
        with client.websocket_connect("/api/v1/notifications/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connected"

            ws.send_text(json.dumps({"type": "ping"}))
            reply = ws.receive_json()
            assert reply["type"] == "pong"

    def test_ws_heartbeat(self, client, monkeypatch):
        monkeypatch.setattr(notif_mod, "HEARTBEAT_INTERVAL_SECONDS", 0.1)
        with client.websocket_connect("/api/v1/notifications/ws") as ws:
            first = ws.receive_json()
            assert first["type"] == "connected"

            # 在若干帧内应收到服务端心跳
            seen_heartbeat = False
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "heartbeat":
                    seen_heartbeat = True
                    break
            assert seen_heartbeat


class TestBroadcastTestEndpoint:
    def test_broadcast_requires_manage_scope(self, client):
        _use(Principal(
            user_id="notif-user-3",
            tenant_id="notif-tenant-1",
            role="user",
            scopes=["notifications:subscribe"],
            authenticated=True,
        ))
        resp = client.post(
            "/api/v1/notifications/broadcast/test",
            json={"title": "t", "body": "b"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 403

    def test_broadcast_really_delivers_to_ws(self, client):
        # bootstrap admin 具备 notifications:manage
        with client.websocket_connect("/api/v1/notifications/ws") as ws:
            assert ws.receive_json()["type"] == "connected"

            resp = client.post(
                "/api/v1/notifications/broadcast/test",
                json={"title": "Release", "body": "RC check passed"},
                headers=AUTH_HEADERS,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "broadcast"
            assert resp.json()["connections"] >= 1

            # 真实投递: WS 客户端收到该广播
            delivered = None
            for _ in range(5):
                msg = ws.receive_json()
                if msg.get("type") == "test_broadcast":
                    delivered = msg
                    break
            assert delivered is not None
            assert delivered["title"] == "Release"
            assert delivered["body"] == "RC check passed"
