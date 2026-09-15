"""事件分发核心单测（notification_dispatch + notification_dispatch_store）。

本文件锁死四件事——它们都是「看起来对、实际错」的高危面：

1. **假绿 provider**。``ConsoleNotificationProvider.is_configured()`` 恒 True、
   ``send()`` 恒 ``success=True``，但它只写一行日志。所以「投出去没有」只能按
   provider **类型**判别。若哪天有人改回 ``is_configured()`` 当门槛，本文件必须转红。
2. **失败隔离**。一条渠道抛异常不能让其它渠道不投、更不能让调用方收到异常
   （那会把「反馈已创建」一起弄失败）。
3. **脱敏**。``WebhookNotificationProvider`` 失败时 ``str(exception)`` 里带着完整
   的 Slack webhook URL —— 那是凭据。原样落库等于把凭据写进明文 JSON。
4. **trigger 匹配**。``high_priority_feedback`` 与 ``critical_feedback`` 互斥
   （按决策），且 disabled 渠道与订阅了别的 trigger 的渠道都不能被选中。
"""
from __future__ import annotations

import json

import pytest

import backend.app.core.notification_dispatch as dispatch_mod
import backend.app.core.notifications as notif_mod
from backend.app.core.notification_config_store import (
    NotificationConfigRecord,
    NotificationConfigStore,
)
from backend.app.core.notification_dispatch import (
    FeedbackEvent,
    build_daily_summary_digest,
    build_feedback_subject_body,
    dispatch_created_feedback,
    dispatch_feedback_event,
    dispatch_notification,
    mask_target,
    triggers_for_created_feedback,
)
from backend.app.core.notification_dispatch_store import (
    MAX_RECORDS,
    DeliveryRecord,
    NotificationDispatchStore,
)
from backend.app.core.notifications import (
    ConsoleNotificationProvider,
    DeliveryResult,
    NotificationMessage,
    NoopNotificationProvider,
)

SLACK_URL = "https://hooks.slack.com/services/T000/B000/SUPERSECRETTOKEN"
EMAIL = "ops@example.com"


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------

@pytest.fixture()
def config_store(tmp_path) -> NotificationConfigStore:
    return NotificationConfigStore(storage_path=tmp_path / "configs.json")


@pytest.fixture()
def log_store(tmp_path) -> NotificationDispatchStore:
    return NotificationDispatchStore(storage_path=tmp_path / "deliveries.json")


@pytest.fixture()
def console_provider(monkeypatch):
    """把全局 provider 换成「假绿」的 Console 实现。"""
    monkeypatch.setattr(notif_mod, "_active_provider", ConsoleNotificationProvider())


def _add(config_store, **overrides) -> NotificationConfigRecord:
    payload = {"type": "email", "target": EMAIL, "triggers": ["new_feedback"]}
    payload.update(overrides)
    return config_store.add(NotificationConfigRecord(**payload))


def _event(**overrides) -> FeedbackEvent:
    payload = {
        "feedback_id": "fb-1",
        "title": "Login broken",
        "description": "Clicking login does nothing.",
        "feedback_type": "bug",
        "severity": "low",
        "status": "new",
        "sentiment": "neutral",
    }
    payload.update(overrides)
    return FeedbackEvent(**payload)


# --- 替身 provider -----------------------------------------------------------
# 都实现 NotificationProvider 的两个方法（send / is_configured），签名与真实现一致。

class _FlakyWebhookProvider:
    """构造成功、发送时抛异常 —— 用来验证失败隔离与脱敏。"""

    def __init__(self, url, payload_format="generic", **kw):
        self._url = url

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        raise RuntimeError(f"connect to {self._url} failed: timeout")

    def is_configured(self) -> bool:
        return True


class _OkEmailProvider:
    """真的会返回 success 的邮件 provider。"""

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        return DeliveryResult(success=True, provider="smtp", message_id="m-1")

    def is_configured(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# trigger 判定
# ---------------------------------------------------------------------------

class TestTriggerSelection:
    def test_every_created_feedback_hits_new_feedback(self):
        assert "new_feedback" in triggers_for_created_feedback(_event())

    @pytest.mark.parametrize(
        ("severity", "expected"),
        [
            ("low", []),
            ("medium", []),
            ("high", ["high_priority_feedback"]),
            ("critical", ["critical_feedback"]),
        ],
    )
    def test_severity_maps_to_at_most_one_severity_trigger(self, severity, expected):
        matched = triggers_for_created_feedback(_event(severity=severity))
        assert [t for t in matched if t != "new_feedback"] == expected

    def test_critical_does_not_also_hit_high_priority(self):
        """按决策二者互斥。

        后果是只订阅 ``high_priority_feedback`` 的渠道收不到 critical 反馈 —— 这是
        刻意的口径选择，此处把它**固定下来**，避免以后有人"顺手"改成包含关系却
        没意识到订阅者语义变了。
        """
        matched = triggers_for_created_feedback(_event(severity="critical"))
        assert "high_priority_feedback" not in matched

    def test_negative_sentiment_adds_its_trigger(self):
        matched = triggers_for_created_feedback(_event(sentiment="negative"))
        assert "sentiment_negative" in matched

    def test_non_negative_sentiment_does_not(self):
        for sentiment in ("positive", "neutral", None):
            assert "sentiment_negative" not in triggers_for_created_feedback(
                _event(sentiment=sentiment)
            )


# ---------------------------------------------------------------------------
# 脱敏
# ---------------------------------------------------------------------------

class TestMaskTarget:
    def test_email_keeps_domain_only(self):
        assert mask_target(EMAIL) == "o***@example.com"

    def test_webhook_keeps_origin_only(self):
        masked = mask_target(SLACK_URL)
        assert masked == "https://hooks.slack.com/***"
        assert "SUPERSECRETTOKEN" not in masked

    def test_empty_and_opaque_are_fully_masked(self):
        assert mask_target("") == "***"
        assert mask_target("some-raw-token") == "***"


# ---------------------------------------------------------------------------
# 分发：渠道选择
# ---------------------------------------------------------------------------

class TestChannelSelection:
    async def test_no_configs_means_no_records_and_nothing_persisted(
        self, config_store, log_store
    ):
        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert records == []
        assert log_store.count() == 0

    async def test_disabled_channel_is_not_selected(self, config_store, log_store):
        _add(config_store, enabled=False)
        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert records == []
        assert log_store.count() == 0

    async def test_channel_subscribed_to_another_trigger_is_not_selected(
        self, config_store, log_store
    ):
        _add(config_store, triggers=["critical_feedback"])
        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert records == []

    async def test_other_tenants_channels_are_not_selected(self, config_store, log_store):
        _add(config_store, tenant_id="other-tenant")
        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert records == []

    async def test_multiple_matching_channels_each_get_a_record(
        self, config_store, log_store, console_provider
    ):
        _add(config_store, target="a@example.com")
        _add(config_store, target="b@example.com")
        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert len(records) == 2
        assert log_store.count() == 2


# ---------------------------------------------------------------------------
# 分发：诚实语义
# ---------------------------------------------------------------------------

class TestHonestDelivery:
    async def test_console_provider_is_reported_as_not_delivered(
        self, config_store, log_store, console_provider
    ):
        """核心用例：provider 自称成功，记录必须说「没真投递」。"""
        _add(config_store)
        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert len(records) == 1
        record = records[0]
        assert record.delivered is False
        assert record.provider == "ConsoleNotificationProvider"
        assert "未配置真实邮件通道" in record.detail
        assert "未实际投递" in record.detail

    async def test_noop_provider_is_also_reported_as_not_delivered(
        self, config_store, log_store, monkeypatch
    ):
        """Noop 同样自称 configured —— 判别必须覆盖它，不只是 Console。"""
        monkeypatch.setattr(notif_mod, "_active_provider", NoopNotificationProvider())
        _add(config_store)
        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert records[0].delivered is False
        assert records[0].provider == "NoopNotificationProvider"

    async def test_a_real_provider_reporting_success_is_delivered(
        self, config_store, log_store, monkeypatch
    ):
        """反向用例：换成会真投的 provider 后必须报 True。

        少了它，一条「无条件 delivered=False」的实现也能让上面两条全绿。
        """

        class _RealProvider:
            async def send(self, message: NotificationMessage) -> DeliveryResult:
                return DeliveryResult(success=True, provider="smtp", message_id="m-1")

            def is_configured(self) -> bool:
                return True

        monkeypatch.setattr(notif_mod, "_active_provider", _RealProvider())
        _add(config_store)
        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert records[0].delivered is True
        assert records[0].provider == "smtp"

    async def test_provider_reporting_failure_is_not_delivered(
        self, config_store, log_store, monkeypatch
    ):
        class _BrokenProvider:
            async def send(self, message: NotificationMessage) -> DeliveryResult:
                return DeliveryResult(success=False, provider="smtp", error="550 mailbox down")

            def is_configured(self) -> bool:
                return True

        monkeypatch.setattr(notif_mod, "_active_provider", _BrokenProvider())
        _add(config_store)
        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert records[0].delivered is False
        assert "550 mailbox down" in records[0].detail


# ---------------------------------------------------------------------------
# 分发：slack 渠道
# ---------------------------------------------------------------------------

class TestSlackChannel:
    async def test_slack_goes_through_the_webhook_provider(
        self, config_store, log_store, monkeypatch
    ):
        """slack 渠道必须切到 slack 载荷格式（通用结构会被 Slack 拒为 invalid_payload）。"""
        captured: dict = {}

        class _CapturingWebhook:
            def __init__(self, url, payload_format="generic", **kw):
                captured["url"] = url
                captured["payload_format"] = payload_format
                self._url = url

            async def send(self, message: NotificationMessage) -> DeliveryResult:
                captured["message"] = message
                return DeliveryResult(success=True, provider="webhook", message_id="wh-200")

        monkeypatch.setattr(dispatch_mod, "WebhookNotificationProvider", _CapturingWebhook)
        _add(config_store, type="slack", target=SLACK_URL, triggers=["new_feedback"])

        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert captured["payload_format"] == "slack"
        assert captured["url"] == SLACK_URL
        assert records[0].delivered is True
        assert records[0].channel == "slack"

    async def test_webhook_error_never_leaks_the_raw_url(
        self, config_store, log_store, monkeypatch, tmp_path, console_provider
    ):
        """最要紧的一条：凭据不许落盘。

        httpx 的异常会把完整 URL 带在消息里，``_deliver`` 若原样透传，
        「投递失败」这条记录就顺手把 Slack 凭据写进了明文 JSON。
        """
        class _FailingWebhook:
            def __init__(self, url, payload_format="generic", **kw):
                self._url = url

            async def send(self, message: NotificationMessage) -> DeliveryResult:
                raise RuntimeError(f"connect to {self._url} failed: timeout")

        monkeypatch.setattr(dispatch_mod, "WebhookNotificationProvider", _FailingWebhook)
        _add(config_store, type="slack", target=SLACK_URL, triggers=["new_feedback"])
        _add(config_store, type="email", target=EMAIL, triggers=["new_feedback"])

        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )

        by_channel = {r.channel: r for r in records}
        assert by_channel["slack"].delivered is False
        assert "SUPERSECRETTOKEN" not in by_channel["slack"].detail
        assert by_channel["slack"].target_hint == "https://hooks.slack.com/***"
        assert by_channel["email"].target_hint == "o***@example.com"

        # 断言持久化文件本身，而不是只看返回值 —— 落盘才是真正的泄露面。
        persisted = (tmp_path / "deliveries.json").read_text(encoding="utf-8")
        assert "SUPERSECRETTOKEN" not in persisted
        assert SLACK_URL not in persisted
        assert EMAIL not in persisted

    async def test_non_slack_webhook_secret_is_also_scrubbed(
        self, config_store, log_store, monkeypatch, tmp_path, console_provider
    ):
        """兜底正则只认 ``hooks.slack.com``。

        换个 webhook 主机（Mattermost / Rocket.Chat 等 Slack 兼容端点也走这条
        ``type="slack"`` 分支）时，唯一挡住凭据的就是 ``_scrub`` 里的**精确替换**。
        只留兜底正则的话，明文 token 会照原样落盘。

        这条用例存在的理由：只测 ``hooks.slack.com`` 时，兜底正则自己就能把
        token 抹掉，于是「精确替换」那段代码是死是活**测不出来**。
        """
        generic_url = "https://hooks.example.com/services/GENERICTOKEN"

        class _FailingGenericWebhook:
            def __init__(self, url, payload_format="generic", **kw):
                self._url = url

            async def send(self, message: NotificationMessage) -> DeliveryResult:
                raise RuntimeError(f"connect to {self._url} failed: timeout")

        monkeypatch.setattr(
            dispatch_mod, "WebhookNotificationProvider", _FailingGenericWebhook
        )
        _add(config_store, type="slack", target=generic_url, triggers=["new_feedback"])

        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )

        assert records[0].delivered is False
        assert "GENERICTOKEN" not in records[0].detail
        assert records[0].target_hint == "https://hooks.example.com/***"

        persisted = (tmp_path / "deliveries.json").read_text(encoding="utf-8")
        assert "GENERICTOKEN" not in persisted


# ---------------------------------------------------------------------------
# 分发：失败隔离
# ---------------------------------------------------------------------------

class TestFailureIsolation:
    async def test_one_broken_channel_does_not_stop_the_others(
        self, config_store, log_store, monkeypatch
    ):
        """第一条渠道抛异常，第二条仍必须投递；调用方不该看到异常。"""
        monkeypatch.setattr(
            dispatch_mod, "WebhookNotificationProvider", _FlakyWebhookProvider
        )
        monkeypatch.setattr(notif_mod, "_active_provider", _OkEmailProvider())

        _add(config_store, type="slack", target=SLACK_URL, triggers=["new_feedback"])
        _add(config_store, type="email", target=EMAIL, triggers=["new_feedback"])
        assert config_store.count() == 2

        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert len(records) == 2
        by_channel = {r.channel: r for r in records}
        assert by_channel["slack"].delivered is False
        assert by_channel["email"].delivered is True

    async def test_provider_construction_failure_is_contained(
        self, config_store, log_store, monkeypatch
    ):
        """连 provider 构造都抛（比如 URL 非法）时也不许外溢。"""

        class _ExplodingWebhook:
            def __init__(self, *a, **kw):
                raise ValueError("invalid url")

        monkeypatch.setattr(dispatch_mod, "WebhookNotificationProvider", _ExplodingWebhook)
        _add(config_store, type="slack", target=SLACK_URL, triggers=["new_feedback"])

        records = await dispatch_notification(
            tenant_id="default",
            trigger="new_feedback",
            subject="s",
            body="b",
            config_store=config_store,
            log_store=log_store,
        )
        assert len(records) == 1
        assert records[0].delivered is False


# ---------------------------------------------------------------------------
# 组合入口
# ---------------------------------------------------------------------------

class TestDispatchEntryPoints:
    async def test_dispatch_created_feedback_covers_every_matched_trigger(
        self, config_store, log_store, console_provider
    ):
        _add(config_store, triggers=["new_feedback"])
        _add(config_store, triggers=["critical_feedback"])
        _add(config_store, triggers=["sentiment_negative"])
        _add(config_store, triggers=["high_priority_feedback"])

        records = await dispatch_created_feedback(
            tenant_id="default",
            event=_event(severity="critical", sentiment="negative"),
            config_store=config_store,
            log_store=log_store,
        )
        assert {r.trigger for r in records} == {
            "new_feedback",
            "critical_feedback",
            "sentiment_negative",
        }

    async def test_dispatch_feedback_event_records_feedback_id_and_subject(
        self, config_store, log_store, console_provider
    ):
        _add(config_store, triggers=["feedback_resolved"])
        records = await dispatch_feedback_event(
            tenant_id="default",
            trigger="feedback_resolved",
            event=_event(),
            config_store=config_store,
            log_store=log_store,
        )
        assert records[0].feedback_id == "fb-1"
        assert "Login broken" in records[0].subject


# ---------------------------------------------------------------------------
# 消息构造
# ---------------------------------------------------------------------------

class TestMessageBuilding:
    def test_subject_carries_the_trigger_prefix(self):
        subject, _ = build_feedback_subject_body("critical_feedback", _event())
        assert subject.startswith("[严重]")

    def test_long_description_is_truncated(self):
        _, body = build_feedback_subject_body(
            "new_feedback", _event(description="x" * 2000)
        )
        assert "…" in body
        assert len(body) < 2000

    def test_digest_reports_unknown_enum_keys_instead_of_dropping_them(self):
        """后端加新状态时，摘要不能默默少一行。"""
        _, body = build_daily_summary_digest(
            total=3,
            by_status={"new": 3},
            by_severity={"high": 1, "brand_new_level": 2},
            critical_open=0,
        )
        assert "brand_new_level=2" in body

    def test_digest_mentions_critical_open(self):
        subject, _ = build_daily_summary_digest(
            total=5, by_status={}, by_severity={}, critical_open=2
        )
        assert "2" in subject


# ---------------------------------------------------------------------------
# 投递记录存储
# ---------------------------------------------------------------------------

class TestDispatchStore:
    def test_records_are_returned_newest_first(self, tmp_path):
        store = NotificationDispatchStore(storage_path=tmp_path / "d.json")
        for i in range(3):
            store.append(DeliveryRecord(trigger=f"t{i}", subject=f"s{i}"))
        assert [r.trigger for r in store.list_for_tenant("default")] == ["t2", "t1", "t0"]

    def test_tenant_isolation(self, tmp_path):
        store = NotificationDispatchStore(storage_path=tmp_path / "d.json")
        store.append(DeliveryRecord(tenant_id="a", trigger="t"))
        store.append(DeliveryRecord(tenant_id="b", trigger="t"))
        assert len(store.list_for_tenant("a")) == 1

    def test_filtering_happens_before_the_limit(self, tmp_path):
        """先过滤再切片。

        反过来会先丢掉窗口外的匹配项，把「最近 50 条」变成「最近 50 条里恰好匹配的」。
        """
        store = NotificationDispatchStore(storage_path=tmp_path / "d.json")
        store.append(DeliveryRecord(trigger="wanted"))
        for _ in range(5):
            store.append(DeliveryRecord(trigger="noise"))
        assert len(store.list_for_tenant("default", limit=1, trigger="wanted")) == 1

    def test_oldest_records_are_trimmed_at_the_cap(self, tmp_path):
        store = NotificationDispatchStore(storage_path=tmp_path / "d.json")
        for i in range(MAX_RECORDS + 5):
            store.append(DeliveryRecord(trigger=f"t{i}"))
        assert store.count() == MAX_RECORDS
        newest = store.list_for_tenant("default", limit=1)
        assert newest[0].trigger == f"t{MAX_RECORDS + 4}"

    def test_records_survive_a_reload(self, tmp_path):
        path = tmp_path / "d.json"
        NotificationDispatchStore(storage_path=path).append(
            DeliveryRecord(trigger="t", delivered=True, target_hint="o***@example.com")
        )
        assert NotificationDispatchStore(storage_path=path).count() == 1

    def test_corrupt_file_does_not_break_startup(self, tmp_path):
        path = tmp_path / "d.json"
        path.write_text("{not json", encoding="utf-8")
        assert NotificationDispatchStore(storage_path=path).count() == 0

    def test_invalid_records_are_skipped_not_fatal(self, tmp_path):
        path = tmp_path / "d.json"
        path.write_text(
            json.dumps({"deliveries": [{"trigger": "ok"}, {"no_trigger": True}]}),
            encoding="utf-8",
        )
        assert NotificationDispatchStore(storage_path=path).count() == 1
