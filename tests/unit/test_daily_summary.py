"""每日摘要定时任务单测 —— cron 时刻 / 租户发现 / 24h 窗口 / 注册接线。

为什么需要这一层
================
``daily_summary`` 从「只能手动触发」变成「每天自动发出」后，多出三类**只在定时
路径上成立**的失败方式，组件测试（``test_notification_dispatch*.py``）覆盖不到：

1. **cron 时刻算错却静默通过** —— ``CronScheduler._calculate_next_cron_time`` 曾是
   桩实现（恒 ``now + 1 天``，完全忽略表达式）。任何非「每 24 小时」的表达式都会
   跑错节奏，而且**不会有任何报错**。本文件是唯一防线。
2. **窗口没生效** —— 正文写「过去 24 小时」而数字是全量计数。手动触发时危害有限；
   一旦每天定时发出，就变成「每天发一份全量快照，却声称是日报」。
3. **注册了个什么都不干的 job** —— 接线成功、能启动、任务列表里也看得到，就是不发。

``TestClient(app)`` 不进上下文 ⇒ **不跑 lifespan** ⇒ ``main.py`` 的接线不在常规
测试覆盖范围内（本仓既有约定）。所以注册被拆成可注入的纯函数
``register_daily_summary_job``：这里给一个全新的 ``CronScheduler()``，再**直接驱动
它注册进去的那个协程**，断言 job 真的跑了聚合与投递。只断言「有个 task 对象存在」
对「job 干不干活」毫无约束力 —— 那种测试在 job 被写成空函数时照样绿。

窗口怎么造「旧数据」
====================
不 mock ``datetime.now``：先正常落一条记录，再改 JSON 里的时间戳。因为窗口过滤
走的正是「落盘 → 读盘」那一趟（``_serialize_dt`` → ``_parse_dt`` → ``_in_window``），
这样测到的才是真实路径，而不是一个理想化的替身。
"""
from __future__ import annotations

import ast
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from croniter import croniter

import backend.app.core.notifications as notif_mod
import backend.app.models.feedback as fb_models
from backend.app.core.daily_summary import (
    DEFAULT_CRON,
    build_tenant_digest,
    register_daily_summary_job,
    run_for_all_subscribed_tenants,
    run_for_tenant,
    subscribed_tenants,
    window_label,
    window_start,
)
from backend.app.core.feedback_store_file import FeedbackStoreFile
from backend.app.core.notification_config_store import (
    NotificationConfigRecord,
    NotificationConfigStore,
)
from backend.app.core.notification_dispatch_store import NotificationDispatchStore
from backend.app.core.notifications import ConsoleNotificationProvider
from backend.app.core.scheduler import CronScheduler

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_PY = REPO_ROOT / "backend" / "app" / "main.py"

TENANT = "tenant-a"
OTHER = "tenant-b"
EMAIL = "ops@example.com"


# ---------------------------------------------------------------------------
# 夹具与工具
# ---------------------------------------------------------------------------

@pytest.fixture()
def console_provider(monkeypatch):
    """固定「假绿」provider。

    它 ``is_configured()`` 恒 True、``send()`` 恒 success，但什么都不发。固定成它，
    「未配置真实通道」的诚实路径才是**确定**被测到的，而不是取决于本机配没配 SMTP；
    同时避免 ``slack`` 渠道在测试里真的发 HTTP 请求。
    """
    monkeypatch.setattr(notif_mod, "_active_provider", ConsoleNotificationProvider())


def _channel(tenant_id: str, triggers, *, enabled: bool = True) -> NotificationConfigRecord:
    return NotificationConfigRecord(
        type="email",
        target=EMAIL,
        enabled=enabled,
        triggers=list(triggers),
        tenant_id=tenant_id,
    )


def _config_store(tmp_path, *records) -> NotificationConfigStore:
    store = NotificationConfigStore(storage_path=tmp_path / "configs.json")
    for record in records:
        store.add(record)
    return store


def _log_store(tmp_path) -> NotificationDispatchStore:
    return NotificationDispatchStore(storage_path=tmp_path / "deliveries.json")


async def _seed_feedback(
    path: Path,
    feedback_id: str,
    *,
    tenant_id: str = TENANT,
    severity: str = "low",
    status: str = "new",
    age_days: float = 0.0,
) -> None:
    """落一条反馈，再把落盘的时间/状态改成本用例需要的值。

    改 JSON 而非 mock ``now``：窗口过滤读的就是落盘后的字符串（``_parse_dt``）。
    """
    await FeedbackStoreFile(path).create_feedback(
        feedback_id=feedback_id,
        user_id="u1",
        tenant_id=tenant_id,
        feedback_type="bug",
        title=f"title-{feedback_id}",
        description="desc",
        severity=severity,
    )
    if age_days or status != "new":
        data = json.loads(path.read_text(encoding="utf-8"))
        record = data["feedback"][feedback_id]
        if age_days:
            when = (datetime.now(UTC) - timedelta(days=age_days)).isoformat()
            record["created_at"] = when
            record["updated_at"] = when
        record["status"] = status
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# 1. cron 下次触发时刻 —— 桩实现的唯一防线
# ---------------------------------------------------------------------------

class TestCronNextTime:
    def test_daily_expression_matches_croniter(self):
        scheduler = CronScheduler()
        task_id = register_daily_summary_job(scheduler)
        next_run = scheduler.scheduled_tasks[task_id].next_run_at
        assert next_run == croniter(DEFAULT_CRON, datetime.now(UTC)).get_next(datetime)

    def test_non_daily_expression_is_not_now_plus_one_day(self):
        """桩实现下这条必红：它无视表达式，恒 ``now + 1 天``。"""
        scheduler = CronScheduler()
        task_id = register_daily_summary_job(scheduler, cron_expression="*/15 * * * *")
        delta = scheduler.scheduled_tasks[task_id].next_run_at - datetime.now(UTC)
        assert timedelta(0) < delta <= timedelta(minutes=15)

    def test_month_boundary_expression_lands_on_the_first(self):
        """``0 9 1 * *`` = 每月 1 日 09:00 UTC。桩实现只会给「明天同一时刻」。"""
        scheduler = CronScheduler()
        task_id = register_daily_summary_job(scheduler, cron_expression="0 9 1 * *")
        next_run = scheduler.scheduled_tasks[task_id].next_run_at
        assert (next_run.day, next_run.hour, next_run.minute) == (1, 9, 0)
        assert next_run > datetime.now(UTC)

    def test_next_run_is_timezone_aware_utc(self):
        """naive 的 next_run_at 拿去和 tz-aware 的 now 比较会抛 TypeError。

        而且必须是 UTC：``croniter`` 配 tz-aware 的 now 返回 UTC，所以
        ``"0 9 * * *"`` 是 **UTC** 09:00，不是本地 9 点。
        """
        scheduler = CronScheduler()
        task_id = register_daily_summary_job(scheduler)
        next_run = scheduler.scheduled_tasks[task_id].next_run_at
        assert next_run.tzinfo is not None
        assert next_run.utcoffset() == timedelta(0)

    @pytest.mark.parametrize("bad", ["not a cron", "99 99 * * *", "0 9 * *"])
    def test_invalid_expression_raises_instead_of_being_accepted(self, bad):
        """从「静默接受、跑错节奏」改成「显式拒绝」。

        ``api/scheduler.py`` 会把 ValueError 转成 400 —— 所以这是**改进**
        （配置写错立刻可见），不是回归。
        """
        with pytest.raises(ValueError):
            register_daily_summary_job(CronScheduler(), cron_expression=bad)

    def test_registered_task_carries_name_and_expression(self):
        scheduler = CronScheduler()
        task_id = register_daily_summary_job(scheduler)
        task = scheduler.scheduled_tasks[task_id]
        assert task.name == "daily_summary"
        assert task.cron_expression == DEFAULT_CRON


# ---------------------------------------------------------------------------
# 2. 租户发现 —— 定时任务没有 principal，租户只能这样找
# ---------------------------------------------------------------------------

class TestTenantDiscovery:
    def test_list_tenants_empty_store(self, tmp_path):
        assert NotificationConfigStore(
            storage_path=tmp_path / "configs.json"
        ).list_tenants() == []

    def test_list_tenants_dedups_and_sorts(self, tmp_path):
        store = _config_store(
            tmp_path,
            _channel("b", ["daily_summary"]),
            _channel("a", ["daily_summary"]),
            _channel("a", ["new_feedback"]),
        )
        assert store.list_tenants() == ["a", "b"]

    def test_subscribed_requires_enabled_and_the_trigger(self, tmp_path):
        store = _config_store(
            tmp_path,
            _channel("subscribed", ["daily_summary"]),
            _channel("disabled", ["daily_summary"], enabled=False),
            _channel("other-trigger", ["new_feedback"]),
            _channel("no-trigger", []),
        )
        assert subscribed_tenants(config_store=store) == ["subscribed"]

    def test_subscribed_honours_the_trigger_argument(self, tmp_path):
        store = _config_store(
            tmp_path,
            _channel("daily", ["daily_summary"]),
            _channel("event", ["new_feedback"]),
        )
        assert subscribed_tenants(config_store=store) == ["daily"]
        assert subscribed_tenants("new_feedback", config_store=store) == ["event"]


# ---------------------------------------------------------------------------
# 3. 窗口本身
# ---------------------------------------------------------------------------

class TestWindowHelpers:
    def test_window_start_subtracts_the_window(self):
        now = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
        assert window_start(now=now, window=timedelta(hours=24)) == datetime(
            2026, 9, 14, 12, 0, tzinfo=UTC
        )

    def test_window_label_is_derived_not_hardcoded(self):
        assert window_label(timedelta(hours=24)) == "过去 24 小时"
        assert window_label(timedelta(hours=1)) == "过去 1 小时"


# ---------------------------------------------------------------------------
# 4. 文件后端的窗口过滤（真实落盘路径）
# ---------------------------------------------------------------------------

class TestFileStoreWindow:
    async def test_list_feedback_excludes_records_before_the_window(self, tmp_path):
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fresh")
        await _seed_feedback(path, "stale", age_days=3)
        store = FeedbackStoreFile(path)

        since = datetime.now(UTC) - timedelta(hours=24)
        ids = {
            f.id
            for f in await store.list_feedback(tenant_id=TENANT, created_after=since)
        }
        assert ids == {"fresh"}

    async def test_list_feedback_without_window_is_unchanged(self, tmp_path):
        """``created_after=None`` ⇒ 全量。既有调用方的语义不许被这次改动动到。"""
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fresh")
        await _seed_feedback(path, "stale", age_days=3)
        store = FeedbackStoreFile(path)

        ids = {f.id for f in await store.list_feedback(tenant_id=TENANT)}
        assert ids == {"fresh", "stale"}

    async def test_count_feedback_excludes_records_before_the_window(self, tmp_path):
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fresh")
        await _seed_feedback(path, "stale", age_days=3)
        store = FeedbackStoreFile(path)

        since = datetime.now(UTC) - timedelta(hours=24)
        assert await store.count_feedback(tenant_id=TENANT, created_after=since) == 1
        assert await store.count_feedback(tenant_id=TENANT) == 2

    async def test_naive_timestamp_is_read_as_utc(self, tmp_path):
        """旧数据里可能有 naive 时间戳；``_parse_dt`` 一律按 UTC 解释。

        若有人改动这个口径，窗口边界会把 naive 记录判成「不在窗内」，日报少报。
        """
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "naive")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["feedback"]["naive"]["created_at"] = (
            datetime.now(UTC).replace(tzinfo=None).isoformat()
        )
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        since = datetime.now(UTC) - timedelta(hours=24)
        store = FeedbackStoreFile(path)
        assert await store.count_feedback(tenant_id=TENANT, created_after=since) == 1
        (item,) = await store.list_feedback(tenant_id=TENANT, created_after=since)
        assert item.created_at.tzinfo is not None


# ---------------------------------------------------------------------------
# 5. Postgres 后端的窗口过滤（差分断言，不连库）
# ---------------------------------------------------------------------------

class _EmptyResult:
    def scalars(self):
        return self

    def all(self):
        return []

    def scalar_one_or_none(self):
        return None


class _CapturingSession:
    """只把语句收下来，不真的执行。"""

    def __init__(self, sink: list):
        self._sink = sink

    async def execute(self, stmt):
        self._sink.append(stmt)
        return _EmptyResult()


def _fake_get_session(sink: list):
    @asynccontextmanager
    async def _cm():
        yield _CapturingSession(sink)

    return _cm


def _where_sql(stmt) -> str:
    return str(
        stmt.whereclause.compile(compile_kwargs={"literal_binds": True})
    )


class TestPostgresWindow:
    """Postgres 路径的窗口过滤：只断言**语句真的带上了谓词**。

    不连库 ⇒ 测不了「数出来几条」，那就测「WHERE 里有没有 created_at」。
    用**差分**而不是单点断言：拿「不带窗口」的语句当对照，否则一个忽略
    ``created_after`` 的实现（谓词压根没加）也能让单点断言通过。
    """

    async def test_list_feedback_adds_created_at_predicate(self, monkeypatch):
        sink: list = []
        monkeypatch.setattr(
            fb_models.SessionManager, "get_session", staticmethod(_fake_get_session(sink))
        )
        store = fb_models.FeedbackStorePostgres()

        await store.list_feedback(tenant_id=TENANT)
        await store.list_feedback(
            tenant_id=TENANT, created_after=datetime(2026, 9, 1, tzinfo=UTC)
        )
        assert len(sink) == 2
        without, with_window = _where_sql(sink[0]), _where_sql(sink[1])
        assert "created_at" not in without
        assert "created_at" in with_window
        assert ">=" in with_window

    async def test_count_feedback_adds_created_at_predicate(self, monkeypatch):
        sink: list = []
        monkeypatch.setattr(
            fb_models.SessionManager, "get_session", staticmethod(_fake_get_session(sink))
        )
        store = fb_models.FeedbackStorePostgres()

        await store.count_feedback(tenant_id=TENANT)
        await store.count_feedback(
            tenant_id=TENANT, created_after=datetime(2026, 9, 1, tzinfo=UTC)
        )
        assert len(sink) == 2
        assert "created_at" not in _where_sql(sink[0])
        assert "created_at" in _where_sql(sink[1])


# ---------------------------------------------------------------------------
# 6. 摘要口径 —— 新增量按窗口、critical_open 走存量
# ---------------------------------------------------------------------------

class TestDigestSemantics:
    async def test_new_volume_is_windowed_while_critical_open_is_stock(self, tmp_path):
        """两类口径刻意不同，正文里必须分别写明。

        窗口外的 critical 若仍未解决，今天**依然**是待办 —— 拿同一把尺子量，
        日报就会漏掉真正该催的事。
        """
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fresh-low")
        await _seed_feedback(path, "fresh-critical", severity="critical")
        await _seed_feedback(path, "old-high", severity="high", age_days=3)
        await _seed_feedback(
            path, "old-critical-open", severity="critical", age_days=5, status="new"
        )
        await _seed_feedback(
            path, "old-critical-closed", severity="critical", age_days=5, status="closed"
        )
        store = FeedbackStoreFile(path)

        subject, body = await build_tenant_digest(TENANT, feedback_store=store)

        # 新增量：窗口内 2 条（fresh-low / fresh-critical），窗口外的 3 条一条都不算。
        assert "总计: 2" in body
        assert "过去 24 小时的反馈概览" in body
        # 存量：窗口外的 critical 仍被计入（fresh-critical + old-critical-open = 2），
        # 已 closed 的不算 —— 所以 2 这个数字同时钉住了「不限窗口」和「只数未解决」。
        assert "未解决且严重度为 critical（当前存量，不限窗口）: 2" in body
        assert "反馈总计 2 条" in subject
        assert "未解决严重 2 条" in subject

    async def test_window_label_comes_from_the_window_argument(self, tmp_path):
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fresh")
        store = FeedbackStoreFile(path)

        _, body = await build_tenant_digest(
            TENANT, window=timedelta(hours=1), feedback_store=store
        )
        assert "过去 1 小时的反馈概览" in body
        assert "过去 24 小时" not in body

    async def test_window_start_is_actually_applied(self, tmp_path):
        """把窗口缩到 0，刚落的记录也应当落在窗口外 —— 证明 since 被真的用上了。"""
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fresh")
        store = FeedbackStoreFile(path)

        now = datetime.now(UTC)
        _, body = await build_tenant_digest(
            TENANT, now=now, window=timedelta(0), feedback_store=store
        )
        assert "总计: 0" in body


# ---------------------------------------------------------------------------
# 7. 单租户执行 / 多租户隔离
# ---------------------------------------------------------------------------

class _TenantSelectiveStore:
    """只对指定租户抛异常 —— 用来验证「一个租户挂掉不拖垮其它租户」。"""

    def __init__(self, failing_tenant: str, inner):
        self._failing = failing_tenant
        self._inner = inner

    async def count_feedback(self, *, tenant_id, **kwargs):
        if tenant_id == self._failing:
            raise RuntimeError("storage exploded")
        return await self._inner.count_feedback(tenant_id=tenant_id, **kwargs)

    async def list_feedback(self, *, tenant_id, **kwargs):
        if tenant_id == self._failing:
            raise RuntimeError("storage exploded")
        return await self._inner.list_feedback(tenant_id=tenant_id, **kwargs)


class TestRunIsolation:
    async def test_run_for_tenant_returns_digest_and_records(self, tmp_path, console_provider):
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fb-1")
        run = await run_for_tenant(
            TENANT,
            feedback_store=FeedbackStoreFile(path),
            config_store=_config_store(tmp_path, _channel(TENANT, ["daily_summary"])),
            log_store=_log_store(tmp_path),
        )
        assert run.tenant_id == TENANT
        assert run.active_channels == 1
        # console provider 恒报 success 但什么都没发 —— 必须如实报 0。
        assert run.delivered_count == 0
        assert len(run.records) == 1

    async def test_tenant_without_subscription_gets_no_records(self, tmp_path, console_provider):
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fb-1")
        log = _log_store(tmp_path)
        run = await run_for_tenant(
            TENANT,
            feedback_store=FeedbackStoreFile(path),
            config_store=_config_store(tmp_path, _channel(TENANT, ["new_feedback"])),
            log_store=log,
        )
        assert run.records == []
        assert run.active_channels == 0
        assert log.count() == 0

    async def test_one_failing_tenant_does_not_stop_the_others(self, tmp_path, console_provider):
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fb-a", tenant_id=TENANT)
        await _seed_feedback(path, "fb-b", tenant_id=OTHER)

        inner = FeedbackStoreFile(path)
        store = _TenantSelectiveStore(TENANT, inner)
        config_store = _config_store(
            tmp_path,
            _channel(TENANT, ["daily_summary"]),
            _channel(OTHER, ["daily_summary"]),
        )

        runs = await run_for_all_subscribed_tenants(
            feedback_store=store,
            config_store=config_store,
            log_store=_log_store(tmp_path),
        )
        # 失败的租户不在返回值里（它不是一次成功的 run），健康的那个照跑。
        assert [r.tenant_id for r in runs] == [OTHER]

    async def test_no_subscribers_means_no_runs_and_nothing_persisted(
        self, tmp_path, console_provider
    ):
        log = _log_store(tmp_path)
        runs = await run_for_all_subscribed_tenants(
            feedback_store=FeedbackStoreFile(tmp_path / "feedback.json"),
            config_store=_config_store(tmp_path),
            log_store=log,
        )
        assert runs == []
        assert log.count() == 0


# ---------------------------------------------------------------------------
# 8. 注册 —— 「job 真的干活」而不是「有个 task 对象」
# ---------------------------------------------------------------------------

class TestRegistration:
    async def test_registered_job_actually_aggregates_and_dispatches(
        self, tmp_path, console_provider
    ):
        """直接把注册进去的协程跑起来。

        若 job 被写成空函数（``return {}``），这条必红 —— 而
        「``task_id in scheduler.scheduled_tasks``」那种断言照样绿。
        """
        path = tmp_path / "feedback.json"
        await _seed_feedback(path, "fb-1", severity="critical")
        log = _log_store(tmp_path)

        scheduler = CronScheduler()
        task_id = register_daily_summary_job(
            scheduler,
            feedback_store=FeedbackStoreFile(path),
            config_store=_config_store(tmp_path, _channel(TENANT, ["daily_summary"])),
            log_store=log,
        )
        result = await scheduler.scheduled_tasks[task_id].coroutine()

        assert result["tenants"] == 1
        assert result["active_channels"] == 1
        assert result["delivered"] == 0  # console provider 什么都没发
        assert log.count() == 1

    async def test_job_reports_zero_when_nobody_subscribes(self, tmp_path, console_provider):
        scheduler = CronScheduler()
        task_id = register_daily_summary_job(
            scheduler,
            feedback_store=FeedbackStoreFile(tmp_path / "feedback.json"),
            config_store=_config_store(tmp_path),
            log_store=_log_store(tmp_path),
        )
        result = await scheduler.scheduled_tasks[task_id].coroutine()
        assert result == {"tenants": 0, "active_channels": 0, "delivered": 0}

    def test_registering_does_not_execute_the_job(self):
        """注册只应构造任务对象；job 要等调度器到点才跑。

        本仓「导入/注册期做 IO」是反复踩过的线：注册期就去聚合 + 投递，会让
        「启动一次」变成「发一轮通知」。
        """
        scheduler = CronScheduler()
        task_id = register_daily_summary_job(scheduler)
        assert len(scheduler.scheduled_tasks) == 1
        assert scheduler.scheduled_tasks[task_id].run_count == 0
        assert scheduler.scheduled_tasks[task_id].last_run_at is None

    def test_job_coroutine_takes_no_arguments(self):
        """``CronScheduler._execute_task`` 用 ``task.coroutine()`` 无参调用。"""
        scheduler = CronScheduler()
        task_id = register_daily_summary_job(scheduler)
        assert scheduler.scheduled_tasks[task_id].coroutine.__code__.co_argcount == 0


# ---------------------------------------------------------------------------
# 9. main.py 接线（源码级）
# ---------------------------------------------------------------------------

def _startup_called_names() -> set[str]:
    """``@app.on_event("startup")`` 处理器体内出现过的被调用名。

    用 AST 而不是子串匹配：注释里提到 ``register_daily_summary_job`` 不算接线，
    被注释掉的调用也正是要抓的那种「假接线」。
    """
    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not (isinstance(func, ast.Attribute) and func.attr == "on_event"):
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                if decorator.args[0].value == "startup":
                    names: set[str] = set()
                    for call in ast.walk(node):
                        if not isinstance(call, ast.Call):
                            continue
                        if isinstance(call.func, ast.Name):
                            names.add(call.func.id)
                        elif isinstance(call.func, ast.Attribute):
                            names.add(call.func.attr)
                    return names
    raise AssertionError('main.py 里找不到 @app.on_event("startup") 处理器')


class TestStartupWiring:
    """``TestClient(app)`` 不跑 lifespan ⇒ 接线只能这样守。

    这组测试能拦住「注册那几行被删了/被注释了」，拦不住「注册了但顺序错了」——
    后者由 ``TestRegistration`` 驱动真实 job 来覆盖。
    """

    def test_startup_registers_the_daily_summary_job(self):
        assert "register_daily_summary_job" in _startup_called_names()

    def test_startup_still_wires_the_other_three_b3_items(self):
        """同一块里的另外三项不该被这次改动挤掉。

        ``task_queue`` 的 handler 注册 + worker 启动、``cron_scheduler`` 与
        workflow worker 的两个常驻循环。
        """
        names = _startup_called_names()
        assert {"register_handler", "start_worker", "create_task"} <= names
        assert "_workflow_worker_forever" in names

    def test_cron_expression_is_overridable_by_env(self):
        assert "XAGENT_DAILY_SUMMARY_CRON" in MAIN_PY.read_text(encoding="utf-8")
