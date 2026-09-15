"""每日摘要 —— 「算摘要 → 投递」这条链路的**唯一**实现。

为什么单独成模块
================
这条链路有两个调用方：

- ``api/notification_configs.py::run_daily_summary`` —— 手动触发，调用方要回执
- ``core/scheduler`` 里注册的每日定时任务 —— 无人看回执，只落投递记录

两边各写一份「数一遍 + 拼摘要 + 投递」必然分叉（手动端点先改、定时任务落后，
或反过来），而分叉的表现是「同一件事两个答案」—— 本仓已被咬过一次。

为什么不放 api：定时任务的注册与执行体属于 core，**core 不该反向 import api**。

窗口口径（本模块存在的主要理由）
================================
``daily_summary`` 的正文写着「过去 24 小时」，但 2026-09-15 之前数字来自
``count_feedback`` 的**全量**计数、没有时间窗。手动触发时危害有限；一旦每天定时
发出，就变成「每天发一份全量快照，却声称是日报」。

现在的口径分成两类，**刻意不同**，正文里分别写明：

- **新增量**（总量 / 按状态 / 按严重度）—— 按窗口过滤，回答「过去 24 小时新增了什么」
- **``critical_open``** —— **当前存量、不按窗口过滤**，回答「现在还剩多少未解决的
  严重问题」。一条上周建的 critical 若仍未解决，今天依然是待办。

把这两个问题按同一把尺子理解，日报就会漏掉真正该催的事。

与 ``triggers`` 的关系
======================
只有「有启用且订阅了 ``daily_summary`` 渠道」的租户才跑 —— 否则用户没订阅也被投递，
或者为没人接的租户空跑一遍聚合。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from backend.app.core.notification_config_store import (
    NotificationConfigStore,
    get_notification_config_store,
)
from backend.app.core.notification_dispatch import (
    build_daily_summary_digest,
    dispatch_notification,
)
from backend.app.core.notification_dispatch_store import (
    DeliveryRecord,
    NotificationDispatchStore,
)

logger = logging.getLogger("xagent.daily_summary")

DAILY_SUMMARY_TRIGGER = "daily_summary"

#: 摘要窗口。正文里的「过去 N 小时」由它算出，不写死文案。
DEFAULT_WINDOW = timedelta(hours=24)

#: 默认触发时刻。``CronScheduler._calculate_next_cron_time`` 按 **UTC** 解释，
#: 所以这是 UTC 09:00（= 中国标准时间 17:00）。要本地时刻须换时区。
DEFAULT_CRON = "0 9 * * *"

WINDOW_LABEL_PREFIX = "过去"

#: ``count_feedback`` 一次只吃一个过滤条件，「critical 且未收尾」只能列举后数。
_CRITICAL_SCAN_LIMIT = 1000

_OPEN_STATES = ("new", "acknowledged", "in_progress")
_STATUS_ORDER = ("new", "acknowledged", "in_progress", "resolved", "closed")
_SEVERITY_ORDER = ("low", "medium", "high", "critical")


@dataclass(frozen=True)
class DailySummaryRun:
    """一次「给某个租户算并投递摘要」的完整结果。"""

    tenant_id: str
    subject: str
    body: str
    records: list[DeliveryRecord] = field(default_factory=list)

    @property
    def active_channels(self) -> int:
        """匹配到的渠道数（可能大于 0 而一条都没真投出去 —— 见 notification_dispatch）。"""
        return len(self.records)

    @property
    def delivered_count(self) -> int:
        """**真**投出去的条数。未配置真实通道时会是 0，且这是刻意的。"""
        return sum(1 for r in self.records if r.delivered)


# ---------------------------------------------------------------------------
# 依赖获取
# ---------------------------------------------------------------------------

def _default_feedback_store():
    """惰性取反馈存储。

    ``get_feedback_store`` 定义在 ``api/feedback.py``。模块级 import 它会让 core
    反向依赖 api（加载顺序耦合、且 api 层还会 import core）。这里刻意**函数内 import**，
    与 ``main.py`` 里既有的惰性接线风格一致；调用方也可以直接注入 store 绕过它
    （测试全部走注入，不依赖这个默认值）。
    """
    from backend.app.api.feedback import get_feedback_store

    return get_feedback_store()


# ---------------------------------------------------------------------------
# 窗口
# ---------------------------------------------------------------------------

def window_start(
    *, now: datetime | None = None, window: timedelta = DEFAULT_WINDOW
) -> datetime:
    """窗口起点（tz-aware UTC）。"""
    return (now or datetime.now(UTC)) - window


def window_label(window: timedelta = DEFAULT_WINDOW) -> str:
    """把窗口渲染成人话，供摘要正文使用（不写死「24 小时」）。"""
    hours = window.total_seconds() / 3600
    if hours.is_integer():
        return f"{WINDOW_LABEL_PREFIX} {int(hours)} 小时"
    return f"{WINDOW_LABEL_PREFIX} {window}"


# ---------------------------------------------------------------------------
# 租户发现
# ---------------------------------------------------------------------------

def subscribed_tenants(
    trigger: str = DAILY_SUMMARY_TRIGGER,
    *,
    config_store: NotificationConfigStore | None = None,
) -> list[str]:
    """有「启用且订阅了该 trigger 的渠道」的租户 id（已排序）。

    定时任务没有 ``principal``，租户只能这样发现。未订阅的租户**不跑** ——
    既不为没人接的租户空跑聚合，也不把「用户没要的东西」发出去。
    """
    store = config_store or get_notification_config_store()
    return [
        tenant_id
        for tenant_id in store.list_tenants()
        if any(
            c.enabled and trigger in c.triggers
            for c in store.list_for_tenant(tenant_id)
        )
    ]


# ---------------------------------------------------------------------------
# 摘要计算
# ---------------------------------------------------------------------------

async def build_tenant_digest(
    tenant_id: str,
    *,
    now: datetime | None = None,
    window: timedelta = DEFAULT_WINDOW,
    feedback_store=None,
) -> tuple[str, str]:
    """算出租户的 ``(subject, body)``。纯聚合，不投递。"""
    store = feedback_store or _default_feedback_store()
    since = window_start(now=now, window=window)

    by_status = {
        s: await store.count_feedback(tenant_id=tenant_id, status=s, created_after=since)
        for s in _STATUS_ORDER
    }
    by_severity = {
        s: await store.count_feedback(tenant_id=tenant_id, severity=s, created_after=since)
        for s in _SEVERITY_ORDER
    }
    total = await store.count_feedback(tenant_id=tenant_id, created_after=since)

    # 存量口径：**不带** created_after（见模块 docstring）。
    critical_items = await store.list_feedback(
        tenant_id=tenant_id, severity="critical", limit=_CRITICAL_SCAN_LIMIT
    )
    critical_open = sum(1 for f in critical_items if f.status in _OPEN_STATES)
    if len(critical_items) >= _CRITICAL_SCAN_LIMIT:
        # 触顶时**不静默**：日志留痕，数字仍按实际的报（可能偏低）。
        logger.warning(
            "daily_summary: critical 反馈已达列举上限 %d，critical_open 可能偏低 (tenant=%s)",
            _CRITICAL_SCAN_LIMIT,
            tenant_id,
        )

    return build_daily_summary_digest(
        total=total,
        by_status=by_status,
        by_severity=by_severity,
        critical_open=critical_open,
        window_label=window_label(window),
    )


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------

async def run_for_tenant(
    tenant_id: str,
    *,
    now: datetime | None = None,
    window: timedelta = DEFAULT_WINDOW,
    feedback_store=None,
    config_store: NotificationConfigStore | None = None,
    log_store: NotificationDispatchStore | None = None,
) -> DailySummaryRun:
    """给单个租户算一次摘要并按 ``daily_summary`` 订阅投递。"""
    subject, body = await build_tenant_digest(
        tenant_id, now=now, window=window, feedback_store=feedback_store
    )
    records = await dispatch_notification(
        tenant_id=tenant_id,
        trigger=DAILY_SUMMARY_TRIGGER,
        subject=subject,
        body=body,
        config_store=config_store,
        log_store=log_store,
    )
    return DailySummaryRun(
        tenant_id=tenant_id, subject=subject, body=body, records=records
    )


async def run_for_all_subscribed_tenants(
    *,
    now: datetime | None = None,
    window: timedelta = DEFAULT_WINDOW,
    feedback_store=None,
    config_store: NotificationConfigStore | None = None,
    log_store: NotificationDispatchStore | None = None,
) -> list[DailySummaryRun]:
    """对每个订阅了 ``daily_summary`` 的租户各跑一次。

    **单租户失败不影响其它租户** —— 一个租户的存储异常不该让全站当天的日报都发不出去。
    失败只记 ERROR（含堆栈）并继续，返回值里**不含**失败租户（它不是一次成功的 run）。
    """
    runs: list[DailySummaryRun] = []
    for tenant_id in subscribed_tenants(config_store=config_store):
        try:
            runs.append(
                await run_for_tenant(
                    tenant_id,
                    now=now,
                    window=window,
                    feedback_store=feedback_store,
                    config_store=config_store,
                    log_store=log_store,
                )
            )
        except Exception as exc:  # noqa: BLE001 - 逐租户隔离，见 docstring
            logger.error(
                "daily_summary: tenant %s failed, continuing with the rest: %s",
                tenant_id,
                exc,
                exc_info=True,
            )
    return runs


# ---------------------------------------------------------------------------
# 注册（与启动期解耦，便于直接单测）
# ---------------------------------------------------------------------------

def register_daily_summary_job(
    scheduler,
    *,
    cron_expression: str = DEFAULT_CRON,
    name: str = DAILY_SUMMARY_TRIGGER,
    window: timedelta = DEFAULT_WINDOW,
    feedback_store=None,
    config_store: NotificationConfigStore | None = None,
    log_store: NotificationDispatchStore | None = None,
) -> str:
    """把每日摘要注册进 scheduler，返回 ``task_id``。

    刻意做成**只依赖传入的 scheduler** 的纯函数：测试可以直接给一个全新的
    ``CronScheduler()``，断言「注册了一个 cron 任务、执行体跑出预期结果」——
    不必启动 app、不必跑 lifespan（测试里 ``TestClient(app)`` 不进上下文，
    启动期接线根本不执行，这一点只能靠可注入的注册函数覆盖）。

    幂等由调用方的接线守卫负责（``main.py`` 的 ``_scheduler_wiring_done``），
    与同一块里另外三项接线一致；这里**不**再做一次「同名去重」——那会多出一份
    需要自己维护的对齐逻辑。

    三个 store 覆盖参数**原样透传**给执行体：测试可以取出
    ``scheduler.scheduled_tasks[task_id].coroutine`` 直接 await，断言它真的跑了
    聚合与投递。不透传的话，「注册了一个什么都不干的 job」在测试里根本看不出来。
    """

    async def _job() -> dict[str, int]:
        runs = await run_for_all_subscribed_tenants(
            window=window,
            feedback_store=feedback_store,
            config_store=config_store,
            log_store=log_store,
        )
        return {
            "tenants": len(runs),
            "active_channels": sum(r.active_channels for r in runs),
            "delivered": sum(r.delivered_count for r in runs),
        }

    return scheduler.schedule_cron(
        name=name,
        coroutine=_job,
        cron_expression=cron_expression,
        metadata={"source": "daily_summary", "window": window_label(window)},
    )


__all__ = [
    "DAILY_SUMMARY_TRIGGER",
    "DEFAULT_CRON",
    "DEFAULT_WINDOW",
    "DailySummaryRun",
    "build_tenant_digest",
    "register_daily_summary_job",
    "run_for_all_subscribed_tenants",
    "run_for_tenant",
    "subscribed_tenants",
    "window_label",
    "window_start",
]
