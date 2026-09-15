"""事件分发 —— 把 ``triggers`` 真正用起来。

背景
====
``notification_config_store`` 里的 ``triggers`` 此前只作为**被校验的枚举**存下来:
用户能在 Notifications tab 里勾选「新反馈时通知我」, 但没有任何代码读它。本模块
补上那一步 —— 反馈创建 / 解决时, 找出该租户「启用了该 trigger 的渠道」并投递。

诚实语义（本模块的核心约束）
============================
``ConsoleNotificationProvider.is_configured()`` 返回 True、``send()`` 返回
``success=True``, 但它只写一行日志, 什么都不发。所以

    「投出去没有」**不能**问 ``is_configured()``, 只能按 provider 类型判别。

这与 ``api/notification_configs.py::test_notification_config`` 是同一口径、同一措辞
—— 同一个问题在两处给出不同答案, 是这个仓库已经被咬过一次的坑。

失败隔离
========
单条渠道失败不影响其它渠道, 也不向调用方抛。通知发不出去, **绝不能**把
「反馈已创建」这个事实一起弄失败。

为什么是「一次评估」而不是「分别订阅」
======================================
``sentiment_negative`` 依赖分析器算出的 ``sentiment``, 而分析在
``create_feedback`` 里发生在建表**之后**。所以创建类的 4 个 trigger 统一在分析
完成后评估一次, 而不是拆成「建完发一次、分析完再发一次」。

已知锋利边角（按决策实现, 此处显式记账）
========================================
``high_priority_feedback`` ⟺ ``severity == "high"``, ``critical_feedback``
⟺ ``severity == "critical"``, 两者**互斥**。因此只订阅
``high_priority_feedback`` 的渠道**收不到 critical 反馈**。这是刻意的口径选择
(severity 是用户显式选的枚举, 可预测), 但订阅者要自己记得两个都勾。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from backend.app.core.notification_config_store import (
    NotificationConfigRecord,
    NotificationConfigStore,
    get_notification_config_store,
)
from backend.app.core.notification_dispatch_store import (
    DeliveryRecord,
    NotificationDispatchStore,
    get_notification_dispatch_store,
)
from backend.app.core.notifications import (
    ConsoleNotificationProvider,
    NoopNotificationProvider,
    NotificationMessage,
    WebhookNotificationProvider,
    get_notification_provider,
)

logger = logging.getLogger("xagent.notification_dispatch")

# 自称「已配置」「发送成功」但实际什么都不发的 provider。
# 判别「有没有真投递」必须按**类型**看这里, 而不是问 is_configured()。
_FALSE_GREEN_PROVIDERS = (ConsoleNotificationProvider, NoopNotificationProvider)

_MAX_DESCRIPTION_CHARS = 500


# ---------------------------------------------------------------------------
# 事件载荷
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeedbackEvent:
    """分发所需的最小反馈快照。

    刻意不用 ORM 模型: 分发是纯函数式的一段逻辑, 接受一个不可变值对象既好测,
    也不会让它悄悄依赖 ``FeedbackModel`` 的字段增删。
    """

    feedback_id: str
    title: str
    description: str = ""
    feedback_type: str = ""
    severity: str = ""
    status: str = ""
    sentiment: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 脱敏
# ---------------------------------------------------------------------------

def mask_target(target: str) -> str:
    """把投递目标压成可安全落盘/打日志的形态。

    ``target`` 可能是收件邮箱或 Slack Incoming Webhook URL —— **后者本身就是凭据**。
    """
    if not target:
        return "***"
    if target.startswith(("http://", "https://")):
        m = re.match(r"^(https?://[^/]+)", target)
        return f"{m.group(1)}/***" if m else "***"
    if "@" in target:
        local, _, domain = target.partition("@")
        return f"{local[:1]}***@{domain}"
    return "***"


def _scrub(text: str, secret: str) -> str:
    """从详情文本里抹掉机密。

    存在理由: ``WebhookNotificationProvider`` 失败时把 ``str(exception)`` 塞进
    ``DeliveryResult.error``, 而 httpx 的异常**会把完整 URL 带在消息里**。若原样
    落库, 一张「投递失败」的记录就顺手把 Slack webhook 凭据写进了明文文件。
    """
    if not text:
        return text
    if secret and secret in text:
        text = text.replace(secret, mask_target(secret))
    # 兜底: 即便 secret 是别的形态, 也不让 slack webhook URL 整条落地。
    return re.sub(r"https://hooks\.slack\.com/\S+", "https://hooks.slack.com/***", text)


# ---------------------------------------------------------------------------
# trigger 判定
# ---------------------------------------------------------------------------

def triggers_for_created_feedback(event: FeedbackEvent) -> list[str]:
    """创建反馈时要评估哪些 trigger（按决策: high 与 critical 互斥）。"""
    matched = ["new_feedback"]
    if event.severity == "high":
        matched.append("high_priority_feedback")
    elif event.severity == "critical":
        matched.append("critical_feedback")
    if event.sentiment == "negative":
        matched.append("sentiment_negative")
    return matched


def _event_metadata_lines(event: FeedbackEvent) -> str:
    lines = [
        f"类型: {event.feedback_type or '-'}",
        f"严重度: {event.severity or '-'}",
        f"状态: {event.status or '-'}",
        f"情感: {event.sentiment or '-'}",
        f"分类: {event.category or '-'}",
    ]
    if event.tags:
        lines.append(f"标签: {', '.join(event.tags)}")
    return "\n".join(lines)


def build_feedback_subject_body(trigger: str, event: FeedbackEvent) -> tuple[str, str]:
    """构造一条反馈通知的 (subject, body)。"""
    prefixes = {
        "new_feedback": "[新反馈]",
        "high_priority_feedback": "[高优先级]",
        "critical_feedback": "[严重]",
        "sentiment_negative": "[负面情感]",
        "feedback_resolved": "[已解决]",
    }
    prefix = prefixes.get(trigger, "[反馈]")
    subject = f"{prefix} {event.title}"

    description = event.description or ""
    if len(description) > _MAX_DESCRIPTION_CHARS:
        description = description[:_MAX_DESCRIPTION_CHARS] + "…"

    body = (
        f"反馈 ID: {event.feedback_id}\n"
        f"标题: {event.title}\n\n"
        f"{_event_metadata_lines(event)}\n\n"
        f"{description}"
    )
    return subject, body.strip()


def build_daily_summary_digest(
    *,
    total: int,
    by_status: dict[str, int],
    by_severity: dict[str, int],
    critical_open: int,
    window_label: str = "过去 24 小时",
) -> tuple[str, str]:
    """把统计数字渲染成每日摘要的 (subject, body)。

    纯格式化, 不查库 —— 数字由调用方取好, 便于单测与复用。

    ⚠️ 调用方**必须**保证数字与 ``window_label`` 同口径。2026-09-15 之前这里
    写死「过去 24 小时的反馈概览」而数字是全量计数 —— 手动触发时危害有限,
    一旦每天定时发出就是「每天发全量快照却声称是日报」。现由调用方传入标签,
    见 ``core/daily_summary.py``（新增量按窗口、``critical_open`` 走存量）。
    """
    subject = f"[每日摘要] 反馈总计 {total} 条，未解决严重 {critical_open} 条"

    def _render(mapping: dict[str, int], order: tuple[str, ...]) -> str:
        items = [(k, mapping.get(k, 0)) for k in order]
        # 枚举之外的键也不丢: 后端加新状态时摘要不会默默少一行。
        items += [(k, v) for k, v in sorted(mapping.items()) if k not in order]
        return ", ".join(f"{k}={v}" for k, v in items) or "-"

    # 两类口径**排版上分开**：读者不该拿同一个「过去 N 小时」去理解存量指标。
    body = (
        f"{window_label}的反馈概览（新增量口径）\n\n"
        f"总计: {total}\n\n"
        "按状态: "
        f"{_render(by_status, ('new', 'acknowledged', 'in_progress', 'resolved', 'closed'))}\n"
        f"按严重度: {_render(by_severity, ('low', 'medium', 'high', 'critical'))}\n\n"
        f"未解决且严重度为 critical（当前存量，不限窗口）: {critical_open}"
    )
    return subject, body


# ---------------------------------------------------------------------------
# 分发
# ---------------------------------------------------------------------------

def _select_configs(
    config_store: NotificationConfigStore, tenant_id: str, trigger: str
) -> list[NotificationConfigRecord]:
    """启用且订阅了该 trigger 的渠道。"""
    return [
        c
        for c in config_store.list_for_tenant(tenant_id)
        if c.enabled and trigger in c.triggers
    ]


async def _deliver(
    config: NotificationConfigRecord, subject: str, body: str
) -> tuple[bool, str, str]:
    """投递到单个渠道, 返回 ``(delivered, provider_name, detail)``。

    永不抛 —— 调用方按「一条渠道失败不影响其它渠道」的约定处理。
    """
    provider_name = ""
    try:
        if config.type == "email":
            provider = get_notification_provider()
            provider_name = type(provider).__name__
            if isinstance(provider, _FALSE_GREEN_PROVIDERS):
                # 与 test 端点逐字同口径。这里**不能**返回 True: 它什么都没发。
                return (
                    False,
                    provider_name,
                    f"未配置真实邮件通道（当前 provider={provider_name}，"
                    "XAGENT_SMTP_HOST 为空），本次未实际投递。",
                )
            result = await provider.send(
                NotificationMessage(
                    to=config.target, subject=subject, body=body, channel="email"
                )
            )
        else:
            # Slack Incoming Webhook 只认 {"text": ...}。
            provider = WebhookNotificationProvider(
                url=config.target, payload_format="slack"
            )
            provider_name = type(provider).__name__
            result = await provider.send(
                NotificationMessage(
                    to=config.target, subject=subject, body=body, channel="slack"
                )
            )
    except Exception as exc:  # 单条渠道的任何异常都不许外溢
        provider_name = provider_name or "unknown"
        detail = _scrub(str(exc) or exc.__class__.__name__, config.target)
        return False, provider_name, f"投递异常（{provider_name}）：{detail}"

    if result.success:
        return True, result.provider or provider_name, f"已通过 {result.provider} 投递。"

    detail = _scrub(result.error or "未知错误", config.target)
    return False, result.provider or provider_name, f"投递失败（{result.provider}）：{detail}"


async def dispatch_notification(
    *,
    tenant_id: str,
    trigger: str,
    subject: str,
    body: str,
    feedback_id: str | None = None,
    config_store: NotificationConfigStore | None = None,
    log_store: NotificationDispatchStore | None = None,
) -> list[DeliveryRecord]:
    """把一条事件投递到该租户所有启用了该 trigger 的渠道。

    返回每个渠道一条 ``DeliveryRecord``（含未投递的那些）。**不抛异常。**
    """
    configs = _select_configs(
        config_store or get_notification_config_store(), tenant_id, trigger
    )
    if not configs:
        return []

    store = log_store or get_notification_dispatch_store()
    records: list[DeliveryRecord] = []
    for config in configs:
        delivered, provider_name, detail = await _deliver(config, subject, body)
        record = DeliveryRecord(
            tenant_id=tenant_id,
            trigger=trigger,
            config_id=config.id,
            channel=config.type,
            provider=provider_name,
            target_hint=mask_target(config.target),
            delivered=delivered,
            detail=detail,
            subject=subject,
            feedback_id=feedback_id,
        )
        store.append(record)
        records.append(record)

        if delivered:
            logger.info(
                "已投递通知 trigger=%s channel=%s config=%s", trigger, config.type, config.id
            )
        else:
            # WARNING 而非 INFO: 「没投出去」是运维需要看见的事。
            logger.warning(
                "通知未实际投递 trigger=%s channel=%s config=%s: %s",
                trigger,
                config.type,
                config.id,
                detail,
            )
    return records


async def dispatch_feedback_event(
    *,
    tenant_id: str,
    trigger: str,
    event: FeedbackEvent,
    config_store: NotificationConfigStore | None = None,
    log_store: NotificationDispatchStore | None = None,
) -> list[DeliveryRecord]:
    """按 ``trigger`` 构造消息并分发一条反馈事件。"""
    subject, body = build_feedback_subject_body(trigger, event)
    return await dispatch_notification(
        tenant_id=tenant_id,
        trigger=trigger,
        subject=subject,
        body=body,
        feedback_id=event.feedback_id,
        config_store=config_store,
        log_store=log_store,
    )


async def dispatch_created_feedback(
    *,
    tenant_id: str,
    event: FeedbackEvent,
    config_store: NotificationConfigStore | None = None,
    log_store: NotificationDispatchStore | None = None,
) -> list[DeliveryRecord]:
    """创建反馈时评估并分发全部命中的 trigger（一次评估, 见模块 docstring）。"""
    out: list[DeliveryRecord] = []
    for trigger in triggers_for_created_feedback(event):
        out.extend(
            await dispatch_feedback_event(
                tenant_id=tenant_id,
                trigger=trigger,
                event=event,
                config_store=config_store,
                log_store=log_store,
            )
        )
    return out
