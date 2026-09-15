"""通知渠道配置 API (backend/app/api/notification_configs.py) 单测。

为什么不进 lifespan 也能测
==========================
``tests/conftest.py`` 在导入期已幂等调用 ``_register_all_routers()``(并加守卫防止
startup 二次注册), 所以这里直接 ``TestClient(app)`` 即可, 路由已就位。

隔离
====
- 存储走 ``XAGENT_NOTIFICATION_CONFIG_STORE_PATH`` → ``tmp_path``, 不碰仓库 ``data/``。
- 鉴权走 bootstrap key(真实 ``get_current_principal`` → admin, 全 scope)。
- 「谁有什么 scope」的用例用 ``dependency_overrides`` 构造 Principal —— 那测的是
  ``ROLE_SCOPES`` 这张表本身(本段改的就是它), 不是重复测密钥存储。
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from backend.app.core.notification_config_store import (
    NotificationConfigRecord,
    get_notification_config_store,
    reset_notification_config_store,
)
from backend.app.core.notifications import (
    ConsoleNotificationProvider,
    NotificationMessage,
    set_notification_provider,
)
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.dependencies import get_current_principal
from backend.app.main import app
from backend.app.settings import get_settings

BASE = "/api/v1/notification-configs"

# 前端 services/feedback.ts::NotificationConfig 的字段集合。后端刻意不含 tenant_id
# (与 FeedbackResponse 同口径), snake_case 由 service 层 adapter 转 camelCase。
FRONTEND_CONTRACT_KEYS = {
    "id",
    "type",
    "enabled",
    "target",
    "triggers",
    "created_at",
    "updated_at",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "XAGENT_NOTIFICATION_CONFIG_STORE_PATH", str(tmp_path / "notification_configs.json")
    )
    reset_notification_config_store()
    yield TestClient(app)  # 不进上下文 → 不跑 lifespan
    reset_notification_config_store()
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_headers():
    return {"x-api-key": get_settings().bootstrap_api_key or "xagent-dev-key-2024"}


def _create(client, headers, **overrides):
    payload = {"type": "email", "target": "ops@example.com", "triggers": ["new_feedback"]}
    payload.update(overrides)
    r = client.post(f"{BASE}/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _use_role(role: str) -> None:
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        tenant_id="default",
        user_id=f"{role}-user",
        role=role,
        scopes=list(ROLE_SCOPES.get(role, [])),
        authenticated=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrud:
    def test_list_starts_empty(self, client, admin_headers):
        r = client.get(f"{BASE}/", headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_create_returns_frontend_contract_shape(self, client, admin_headers):
        body = _create(client, admin_headers)
        assert set(body.keys()) == FRONTEND_CONTRACT_KEYS
        assert "tenant_id" not in body  # 刻意不暴露租户标识
        assert body["type"] == "email"
        assert body["enabled"] is True
        assert body["triggers"] == ["new_feedback"]

    def test_create_then_list_then_get(self, client, admin_headers):
        created = _create(client, admin_headers, target="a@example.com")
        listed = client.get(f"{BASE}/", headers=admin_headers).json()
        assert [c["id"] for c in listed] == [created["id"]]

        got = client.get(f"{BASE}/{created['id']}", headers=admin_headers)
        assert got.status_code == 200
        assert got.json()["target"] == "a@example.com"

    def test_patch_is_partial(self, client, admin_headers):
        created = _create(client, admin_headers, triggers=["new_feedback", "critical_feedback"])
        r = client.patch(
            f"{BASE}/{created['id']}",
            json={"target": "changed@example.com", "enabled": False},
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["target"] == "changed@example.com"
        assert body["enabled"] is False
        # 未给出的字段不动
        assert body["triggers"] == ["new_feedback", "critical_feedback"]
        assert body["id"] == created["id"]

    def test_patch_empty_body_is_noop(self, client, admin_headers):
        created = _create(client, admin_headers)
        r = client.patch(f"{BASE}/{created['id']}", json={}, headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["target"] == created["target"]

    def test_delete_then_404(self, client, admin_headers):
        created = _create(client, admin_headers)
        assert client.delete(f"{BASE}/{created['id']}", headers=admin_headers).status_code == 204
        # 反向证据: 删除真的生效, 不是静默成功
        assert client.get(f"{BASE}/{created['id']}", headers=admin_headers).status_code == 404
        assert client.delete(f"{BASE}/{created['id']}", headers=admin_headers).status_code == 404

    def test_unknown_id_is_404(self, client, admin_headers):
        assert client.get(f"{BASE}/no-such-id", headers=admin_headers).status_code == 404
        assert client.patch(
            f"{BASE}/no-such-id", json={"enabled": False}, headers=admin_headers
        ).status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 校验
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidation:
    def test_unknown_trigger_is_422(self, client, admin_headers):
        r = client.post(
            f"{BASE}/",
            json={"type": "email", "target": "x@example.com", "triggers": ["carrier_pigeon"]},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_unknown_type_is_422(self, client, admin_headers):
        r = client.post(
            f"{BASE}/",
            json={"type": "sms", "target": "x@example.com", "triggers": []},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_blank_target_is_422(self, client, admin_headers):
        r = client.post(
            f"{BASE}/",
            json={"type": "email", "target": "", "triggers": []},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_empty_triggers_accepted(self, client, admin_headers):
        """后端不做过度约束: 空 triggers 不是脏数据(前端自己要求 >=1)。"""
        assert _create(client, admin_headers, triggers=[])["triggers"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# 租户收敛
# ═══════════════════════════════════════════════════════════════════════════════

class TestTenancy:
    def test_cross_tenant_read_and_delete_are_404(self, client, admin_headers):
        """跨租户一律 404(不是 403), 避免泄露资源存在性。"""
        foreign = NotificationConfigRecord(
            type="email", target="foreign@example.com", tenant_id="globex"
        )
        get_notification_config_store().add(foreign)

        assert client.get(f"{BASE}/{foreign.id}", headers=admin_headers).status_code == 404
        assert client.delete(f"{BASE}/{foreign.id}", headers=admin_headers).status_code == 404
        # 且没被真的删掉
        assert get_notification_config_store().get(foreign.id) is not None

    def test_list_only_returns_own_tenant(self, client, admin_headers):
        get_notification_config_store().add(
            NotificationConfigRecord(type="email", target="foreign@example.com", tenant_id="globex")
        )
        _create(client, admin_headers, target="mine@example.com")
        listed = client.get(f"{BASE}/", headers=admin_headers).json()
        assert [c["target"] for c in listed] == ["mine@example.com"]


# ═══════════════════════════════════════════════════════════════════════════════
# scope（方案 A：admin + developer 都可读写）
# ═══════════════════════════════════════════════════════════════════════════════

class TestScopes:
    """方案 A：admin + developer 都可读写。

    ⚠️ 为什么这里要带 Authorization 头
    ----------------------------------
    ``main.py::CSRFProtectionMiddleware`` 对状态变更方法(POST/PUT/PATCH/DELETE)
    默认要 cookie + ``X-CSRF-Token``, 但对 **带 API key 或 Bearer 头**的请求豁免
    (那两种凭据浏览器不会跨站自动带上, 天然免疫 CSRF)。前端 ``feedback.ts`` 正是用
    ``Authorization: Bearer <auth_token>`` 调用的 —— 所以浏览器通路是通的, 前端无需
    为 CSRF 做任何改动。本类用例带上同样的头, 走的就是浏览器那条路。

    这些用例的 principal 由 ``dependency_overrides`` 提供, 故 token 值本身不参与校验;
    这里测的是 ``ROLE_SCOPES`` 这张表(本段改动的对象), 不是重复测密钥存储。
    """

    BROWSER = {"Authorization": "Bearer test-token-csrf-exempt"}

    def test_admin_reads_and_writes(self, client, admin_headers):
        assert client.get(f"{BASE}/", headers=admin_headers).status_code == 200
        _create(client, admin_headers)

    def test_developer_reads_and_writes(self, client):
        """方案 A 的核心: /feedback 页与侧栏对 developer 可见, 只给 admin 就是坏 tab。"""
        _use_role("developer")
        assert client.get(f"{BASE}/", headers=self.BROWSER).status_code == 200
        r = client.post(
            f"{BASE}/",
            json={"type": "email", "target": "dev@example.com", "triggers": []},
            headers=self.BROWSER,
        )
        assert r.status_code == 201, r.text

    @pytest.mark.parametrize("role", ["user", "viewer"])
    def test_ordinary_roles_denied(self, client, role):
        """负向对照: 若 scope 检查是空转, 这条不会红。"""
        _use_role(role)
        r = client.get(f"{BASE}/", headers=self.BROWSER)
        assert r.status_code == 403
        # 403 必须来自 scope 判定, 不是来自 CSRF 之类的别的中间件
        assert "notifications:read" in r.text

    def test_unauthenticated_is_401(self, client):
        # GET 是安全方法, CSRF 中间件不参与 → 401 确实来自 enforce_scope
        assert client.get(f"{BASE}/").status_code == 401

    def test_state_change_without_any_credential_is_blocked(self, client):
        """裸 POST(无 key / 无 Bearer / 无 CSRF)先被 CSRF 中间件挡下 —— 401 之前就 403。

        记录这个顺序不是吹毛求疵: 它说明「未鉴权写请求」在到达业务代码前就被拒了。
        """
        r = client.post(
            f"{BASE}/", json={"type": "email", "target": "x@example.com", "triggers": []}
        )
        assert r.status_code == 403
        assert "CSRF" in r.text

    def test_role_table_grants(self):
        """直接锁 ROLE_SCOPES —— 这是本段改动的对象。"""
        for role in ("admin", "developer"):
            scopes = ROLE_SCOPES[role]
            assert "notifications:read" in scopes
            assert "notifications:write" in scopes
        assert "notifications:read" not in ROLE_SCOPES["user"]
        assert "notifications:write" not in ROLE_SCOPES["user"]


# ═══════════════════════════════════════════════════════════════════════════════
# test 端点的诚实性
# ═══════════════════════════════════════════════════════════════════════════════

class TestTestEndpointHonesty:
    def test_console_provider_trap_is_real(self):
        """前提实证: console provider 自称已配置、返回 success=True, 但什么都没发。

        如果这条不成立, 下面那条「必须 false」的断言就没有意义。
        """
        import asyncio

        provider = ConsoleNotificationProvider()
        assert provider.is_configured() is True
        result = asyncio.run(
            provider.send(NotificationMessage(to="x@example.com", subject="s", body="b"))
        )
        assert result.success is True
        assert result.provider == "console"

    def test_email_test_is_false_when_no_smtp(self, client, admin_headers):
        """无 SMTP 环境下必须返回 success=false —— 宁可红着脸报「没配」, 不给假绿。"""
        created = _create(client, admin_headers)
        set_notification_provider(ConsoleNotificationProvider())

        r = client.post(f"{BASE}/{created['id']}/test", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False, f"假绿！{body}"
        assert "未实际投递" in body["message"]

    def test_test_endpoint_404_for_unknown_id(self, client, admin_headers):
        assert client.post(f"{BASE}/no-such-id/test", headers=admin_headers).status_code == 404

    def test_slack_test_posts_text_payload(self, client, admin_headers, slack_sink):
        """Slack Incoming Webhook 只认 {"text": ...} —— 发通用结构会被拒为 invalid_payload。"""
        received, url = slack_sink
        created = _create(client, admin_headers, type="slack", target=url)

        r = client.post(f"{BASE}/{created['id']}/test", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["success"] is True, r.text

        assert len(received) == 1, f"接收器应收到 1 次 POST, 实得 {len(received)}"
        assert list(received[0].keys()) == ["text"]
        assert "X-Agent" in received[0]["text"]


@pytest.fixture()
def slack_sink():
    """本地 HTTP 接收器 —— 让 slack 分支打到真实 socket, 校验真实载荷。"""
    received: list[dict] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
            received.append(json.loads(raw))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args):  # 静音
            pass

    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield received, f"http://127.0.0.1:{srv.server_address[1]}/services/T000/B000/XXXX"
    finally:
        srv.shutdown()
        srv.server_close()
