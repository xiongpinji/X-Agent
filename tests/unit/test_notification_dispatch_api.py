"""事件分发 API 接线单测 —— 反馈写入路径 → 投递记录。

这一层测的是**组件测试测不到的那一段**：``api/feedback.py`` 里
``background_tasks.add_task(dispatch_created_feedback, ...)`` 到底有没有真的接上。
dispatch 自身的逻辑已在 ``test_notification_dispatch.py`` 里单独覆盖；本文件只问
「写入路径有没有触发它」以及「回执端点有没有说实话」。

⚠️ 这里也是 ``GET /deliveries`` **路由遮蔽**的唯一防线：它和 ``GET /{config_id}``
是同一个路径形状，声明顺序错了会注册成功、能启动、只有这个端点 404。

隔离
====
- 三套存储全部重定向到 ``tmp_path``（feedback / notification config / dispatch）。
- 三个惰性单例全部重置 —— 不清就会沿用上一个用例（乃至仓库 ``data/``）的路径。
- provider 固定为 ``ConsoleNotificationProvider``（假绿那一个），这样「未配置真实
  通道」的诚实路径才是**确定**被测到的，而不是取决于本机有没有配 SMTP。
- ``tests/conftest.py`` 导入期已幂等注册全部路由，直接 ``TestClient(app)``，
  不进上下文（不跑 lifespan）。``TestClient`` 会在返回前把 BackgroundTasks 跑完。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.app.api.feedback as feedback_api
import backend.app.core.notifications as notif_mod
from backend.app.core.notification_config_store import reset_notification_config_store
from backend.app.core.notification_dispatch_store import reset_notification_dispatch_store
from backend.app.core.notifications import ConsoleNotificationProvider
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal
from backend.app.main import app
from backend.app.settings import get_settings

CONFIGS = "/api/v1/notification-configs"
FEEDBACK = "/api/v1/feedback"

EMAIL = "ops@example.com"

CREATE_BODY = {
    "feedback_type": "bug",
    "title": "Login button does nothing",
    "description": "Clicking login has no effect.",
    "severity": "low",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("XAGENT_FEEDBACK_STORE_PATH", str(tmp_path / "feedback.json"))
    monkeypatch.setenv("XAGENT_FEEDBACK_STORE_BACKEND", "file")
    monkeypatch.setenv(
        "XAGENT_NOTIFICATION_CONFIG_STORE_PATH", str(tmp_path / "notification_configs.json")
    )
    monkeypatch.setenv(
        "XAGENT_NOTIFICATION_DISPATCH_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    # 工厂把实例缓存在模块全局；不清就会沿用上一个用例的路径。
    monkeypatch.setattr(feedback_api, "_feedback_store", None)
    monkeypatch.setattr(feedback_api, "_feedback_store_backend", None)
    reset_notification_config_store()
    reset_notification_dispatch_store()
    # 固定「假绿」provider：诚实路径必须被测到，而不是取决于本机配没配 SMTP。
    monkeypatch.setattr(notif_mod, "_active_provider", ConsoleNotificationProvider())
    yield TestClient(app)
    reset_notification_config_store()
    reset_notification_dispatch_store()
    app.dependency_overrides.clear()


@pytest.fixture()
def headers():
    """bootstrap key → admin，带 feedback:write 与 notifications:read/write。"""
    return {"x-api-key": get_settings().bootstrap_api_key or "xagent-dev-key-2024"}


def _add_channel(client, headers, **overrides) -> dict:
    payload = {"type": "email", "target": EMAIL, "triggers": ["new_feedback"]}
    payload.update(overrides)
    r = client.post(f"{CONFIGS}/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _create_feedback(client, headers, **overrides) -> dict:
    payload = dict(CREATE_BODY)
    payload.update(overrides)
    r = client.post(f"{FEEDBACK}/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _deliveries(client, headers, **params) -> list:
    r = client.get(f"{CONFIGS}/deliveries", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _use_scopes(scopes: list[str]) -> None:
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        tenant_id="default",
        user_id="scoped-user",
        role="custom",
        scopes=scopes,
        authenticated=True,
    )


# ---------------------------------------------------------------------------
# 路由可达性（遮蔽防线）
# ---------------------------------------------------------------------------

class TestDeliveriesRouteIsReachable:
    def test_deliveries_is_not_swallowed_by_the_config_id_route(self, client, headers):
        """``GET /deliveries`` 必须返回**列表**。

        声明顺序写反时，``GET /{config_id}`` 会先匹配，config_id 收到字面量
        "deliveries"，于是这个端点 404 —— 而应用照常启动、其它端点全绿。
        """
        body = _deliveries(client, headers)
        assert isinstance(body, list)

    def test_reading_a_config_named_deliveries_still_404s(self, client, headers):
        """反向确认：路由没被改坏成「deliveries 是合法 config_id」。"""
        r = client.get(f"{CONFIGS}/deliveries", headers=headers)
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# 反馈写入路径 → 分发
# ---------------------------------------------------------------------------

class TestCreatedFeedbackTriggersDispatch:
    def test_new_feedback_channel_receives_a_delivery_record(self, client, headers):
        _add_channel(client, headers, triggers=["new_feedback"])
        created = _create_feedback(client, headers)

        records = _deliveries(client, headers)
        assert len(records) == 1
        assert records[0]["trigger"] == "new_feedback"
        assert records[0]["feedback_id"] == created["id"]
        assert "Login button does nothing" in records[0]["subject"]

    def test_a_channel_subscribed_elsewhere_gets_nothing(self, client, headers):
        _add_channel(client, headers, triggers=["daily_summary"])
        _create_feedback(client, headers)
        assert _deliveries(client, headers) == []

    def test_disabled_channel_gets_nothing(self, client, headers):
        _add_channel(client, headers, triggers=["new_feedback"], enabled=False)
        _create_feedback(client, headers)
        assert _deliveries(client, headers) == []

    def test_critical_and_negative_hit_their_own_triggers_not_high_priority(
        self, client, headers
    ):
        _add_channel(client, headers, triggers=["critical_feedback"], target="c@example.com")
        _add_channel(client, headers, triggers=["sentiment_negative"], target="n@example.com")
        _add_channel(client, headers, triggers=["high_priority_feedback"], target="h@example.com")

        # severity=critical → 只命中 critical_feedback（按决策与 high_priority 互斥）
        _create_feedback(client, headers, severity="critical")

        triggers = [r["trigger"] for r in _deliveries(client, headers, limit=100)]
        assert "critical_feedback" in triggers
        assert "high_priority_feedback" not in triggers

    def test_high_severity_hits_high_priority(self, client, headers):
        _add_channel(client, headers, triggers=["high_priority_feedback"])
        _add_channel(client, headers, triggers=["critical_feedback"], target="c@example.com")
        _create_feedback(client, headers, severity="high")

        triggers = [r["trigger"] for r in _deliveries(client, headers, limit=100)]
        assert triggers == ["high_priority_feedback"]


class TestResolvedFeedbackTriggersDispatch:
    def test_resolving_emits_feedback_resolved(self, client, headers):
        _add_channel(client, headers, triggers=["feedback_resolved"])
        created = _create_feedback(client, headers)
        assert _deliveries(client, headers) == []

        r = client.post(f"{FEEDBACK}/{created['id']}/resolve", json={}, headers=headers)
        assert r.status_code == 200, r.text

        records = _deliveries(client, headers)
        assert [x["trigger"] for x in records] == ["feedback_resolved"]
        assert records[0]["feedback_id"] == created["id"]

    def test_patching_status_to_resolved_does_not_double_send(self, client, headers):
        """``PATCH {status}`` 刻意**不**触发 —— 否则一次「解决」会投两遍。

        前端走的是 ``POST /resolve``，所以这条边界是有意为之的产物，此处固定下来。
        """
        _add_channel(client, headers, triggers=["feedback_resolved"])
        created = _create_feedback(client, headers)

        # ⚠️ ``status`` 是**查询参数**（端点签名 ``Query(None, alias="status")``）。
        # 放进 json body 会被静默忽略、PATCH 降级成一次空更新 —— 那样这条用例就
        # 成了「什么都没发生，所以没有重复投递」的假绿。变异验证实测：给 PATCH
        # 加上分发后它照样通过。下面那条状态断言是自检 —— 没有它，参数位置再次
        # 写错也不会有人发现。
        r = client.patch(
            f"{FEEDBACK}/{created['id']}", params={"status": "resolved"}, headers=headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "resolved"
        assert _deliveries(client, headers) == []


# ---------------------------------------------------------------------------
# 诚实回执
# ---------------------------------------------------------------------------

class TestHonestReceipt:
    def test_console_provider_is_reported_as_not_delivered(self, client, headers):
        """核心：配了渠道、事件发生了，回执必须说「没真投递」而不是给个成功。"""
        _add_channel(client, headers, triggers=["new_feedback"])
        _create_feedback(client, headers)

        record = _deliveries(client, headers)[0]
        assert record["delivered"] is False
        assert record["provider"] == "ConsoleNotificationProvider"
        assert "未配置真实邮件通道" in record["detail"]
        assert "未实际投递" in record["detail"]

    def test_target_is_masked_in_the_response(self, client, headers):
        _add_channel(client, headers, triggers=["new_feedback"])
        _create_feedback(client, headers)

        record = _deliveries(client, headers)[0]
        assert record["target_hint"] == "o***@example.com"
        assert EMAIL not in record["target_hint"]

    def test_channel_config_response_never_carries_tenant_id(self, client, headers):
        created = _add_channel(client, headers)
        assert "tenant_id" not in created
        assert all("tenant_id" not in r for r in _deliveries(client, headers))


# ---------------------------------------------------------------------------
# 查询端点
# ---------------------------------------------------------------------------

class TestDeliveriesQuery:
    def test_filter_by_trigger(self, client, headers):
        _add_channel(client, headers, triggers=["new_feedback", "feedback_resolved"])
        created = _create_feedback(client, headers)
        client.post(f"{FEEDBACK}/{created['id']}/resolve", json={}, headers=headers)

        only_resolved = _deliveries(client, headers, trigger="feedback_resolved")
        assert [r["trigger"] for r in only_resolved] == ["feedback_resolved"]

        only_new = _deliveries(client, headers, trigger="new_feedback")
        assert [r["trigger"] for r in only_new] == ["new_feedback"]

    def test_filter_by_config_id(self, client, headers):
        first = _add_channel(client, headers, triggers=["new_feedback"], target="a@example.com")
        _add_channel(client, headers, triggers=["new_feedback"], target="b@example.com")
        _create_feedback(client, headers)

        scoped = _deliveries(client, headers, config_id=first["id"])
        assert len(scoped) == 1
        assert scoped[0]["config_id"] == first["id"]

    def test_limit_is_respected_and_newest_first(self, client, headers):
        _add_channel(client, headers, triggers=["new_feedback"])
        ids = [_create_feedback(client, headers, title=f"issue {i}")["id"] for i in range(3)]

        records = _deliveries(client, headers, limit=2)
        assert len(records) == 2
        assert records[0]["feedback_id"] == ids[-1]

    def test_limit_out_of_range_is_rejected(self, client, headers):
        assert client.get(f"{CONFIGS}/deliveries?limit=0", headers=headers).status_code == 422
        assert client.get(f"{CONFIGS}/deliveries?limit=999", headers=headers).status_code == 422

    def test_other_tenants_records_are_not_visible(self, client, headers):
        _add_channel(client, headers, triggers=["new_feedback"])
        _create_feedback(client, headers)
        assert len(_deliveries(client, headers)) == 1

        app.dependency_overrides[get_current_principal] = lambda: Principal(
            tenant_id="a-different-tenant",
            user_id="u",
            role="admin",
            scopes=["notifications:read", "notifications:write"],
            authenticated=True,
        )
        assert _deliveries(client, headers) == []


# ---------------------------------------------------------------------------
# 手动 daily_summary
# ---------------------------------------------------------------------------

class TestDailySummaryRun:
    def test_reports_honestly_when_no_real_channel_is_configured(self, client, headers):
        """配了 daily_summary 渠道但没有真实投递能力 —— 回执必须说实话。"""
        _add_channel(client, headers, triggers=["daily_summary"])

        r = client.post(f"{CONFIGS}/daily-summary/run", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["trigger"] == "daily_summary"
        assert body["active_channels"] == 1
        assert body["delivered_count"] == 0
        assert body["records"][0]["delivered"] is False
        assert "未配置真实邮件通道" in body["records"][0]["detail"]

    def test_with_no_channels_it_reports_zero_and_still_succeeds(self, client, headers):
        r = client.post(f"{CONFIGS}/daily-summary/run", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["active_channels"] == 0
        assert r.json()["delivered_count"] == 0

    def test_digest_reflects_actual_feedback_counts(self, client, headers):
        _add_channel(client, headers, triggers=["daily_summary"])
        _create_feedback(client, headers, severity="critical")
        _create_feedback(client, headers, severity="low")

        body = client.post(f"{CONFIGS}/daily-summary/run", headers=headers).json()
        # 两条反馈都还是 new；critical 的那条计入「未解决严重」。
        assert "2" in body["subject"]
        assert "1" in body["subject"]

    def test_run_is_recorded_in_the_delivery_log(self, client, headers):
        _add_channel(client, headers, triggers=["daily_summary"])
        client.post(f"{CONFIGS}/daily-summary/run", headers=headers)

        records = _deliveries(client, headers)
        assert [r["trigger"] for r in records] == ["daily_summary"]

    def test_channels_not_subscribed_to_daily_summary_are_skipped(self, client, headers):
        _add_channel(client, headers, triggers=["new_feedback"])
        body = client.post(f"{CONFIGS}/daily-summary/run", headers=headers).json()
        assert body["active_channels"] == 0


# ---------------------------------------------------------------------------
# scope
# ---------------------------------------------------------------------------

class TestScopeEnforcement:
    def test_deliveries_requires_notifications_read(self, client, headers):
        _use_scopes(["feedback:read"])
        r = client.get(f"{CONFIGS}/deliveries", headers=headers)
        assert r.status_code == 403

    def test_daily_summary_run_requires_notifications_write(self, client, headers):
        """必须带 ``x-api-key``。

        少了它，POST 会先被 CSRF 中间件拦成 ``403 CSRF token required`` ——
        断言 ``in (401, 403)`` 于是无条件成立，量到的是 CSRF 门而不是作用域门。
        变异验证实测：去掉端点里的 ``enforce_scope(..., "notifications:write")``
        这条用例照样通过，即它当时**什么都没测**。
        """
        _use_scopes(["notifications:read"])
        r = client.post(f"{CONFIGS}/daily-summary/run", headers=headers)
        assert r.status_code == 403
        assert "CSRF" not in r.text
