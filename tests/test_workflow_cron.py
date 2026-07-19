"""P1-07: cron 调度解析与周期调度行为单测。"""
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.core.workflows import (
    WorkflowExecutionError,
    WorkflowRepository,
    WorkflowRuntimeManager,
    WorkflowExecutor,
    WorkflowScheduleRequest,
    WorkflowScheduleStatus,
    WorkflowScheduleStore,
    WorkflowScheduler,
    WorkflowCreateRequest,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeType,
    _MinimalCron,
    next_cron_run,
)

NOW = datetime(2026, 7, 20, 10, 30, 0, tzinfo=UTC)  # 周一


class TestNextCronRun:
    def test_every_n_minutes(self) -> None:
        assert next_cron_run("*/15 * * * *", now=NOW) == datetime(2026, 7, 20, 10, 45, tzinfo=UTC)

    def test_daily_at_hour(self) -> None:
        assert next_cron_run("0 9 * * *", now=NOW) == datetime(2026, 7, 21, 9, 0, tzinfo=UTC)

    def test_weekly_sunday(self) -> None:
        fire_at = next_cron_run("0 0 * * 0", now=NOW)
        assert fire_at.weekday() == 6  # Sunday
        assert fire_at > NOW

    def test_monthly_first_day(self) -> None:
        assert next_cron_run("0 0 1 * *", now=NOW) == datetime(2026, 8, 1, 0, 0, tzinfo=UTC)

    def test_naive_now_is_treated_as_utc(self) -> None:
        fire_at = next_cron_run("*/5 * * * *", now=datetime(2026, 7, 20, 10, 30))
        assert fire_at.tzinfo is not None

    @pytest.mark.parametrize("expression", ["", "   ", "bad expr", "61 * * * *", "* * * *", "0 0 32 1 0"])
    def test_invalid_expression_raises(self, expression: str) -> None:
        with pytest.raises(WorkflowExecutionError):
            next_cron_run(expression, now=NOW)


class TestMinimalCronFallback:
    """内置降级解析器（croniter 缺失时使用）。"""

    def test_step_values(self) -> None:
        cron = _MinimalCron("*/20 * * * *")
        assert cron.next_after(NOW) == datetime(2026, 7, 20, 10, 40, tzinfo=UTC)

    def test_range_and_list(self) -> None:
        cron = _MinimalCron("0 9-17/2 * * *")
        assert cron.next_after(NOW) == datetime(2026, 7, 20, 11, 0, tzinfo=UTC)
        cron_list = _MinimalCron("0,30 9 * * *")
        assert cron_list.next_after(NOW) == datetime(2026, 7, 21, 9, 0, tzinfo=UTC)

    def test_weekday_matching(self) -> None:
        cron = _MinimalCron("0 9 * * 1")  # 周一 09:00
        assert cron.next_after(NOW) == datetime(2026, 7, 27, 9, 0, tzinfo=UTC)

    def test_sunday_zero_and_seven_equivalent(self) -> None:
        by_zero = _MinimalCron("0 0 * * 0").next_after(NOW)
        by_seven = _MinimalCron("0 0 * * 7").next_after(NOW)
        assert by_zero == by_seven
        assert by_zero.weekday() == 6

    def test_dom_dow_or_semantics(self) -> None:
        # 每月 1 号或周一都触发（Vixie cron OR 语义）
        cron = _MinimalCron("0 0 1 * 1")
        fire_at = cron.next_after(NOW)
        assert fire_at.day == 1 or fire_at.weekday() == 0
        assert fire_at == datetime(2026, 7, 27, 0, 0, tzinfo=UTC)  # 下一个周一

    def test_matches_croniter_for_common_expressions(self) -> None:
        pytest.importorskip("croniter")
        for expression in ["*/5 * * * *", "0 9 * * *", "30 14 * * 3", "0 0 1 * *", "15 8 1,15 * *"]:
            assert _MinimalCron(expression).next_after(NOW) == next_cron_run(expression, now=NOW), expression

    @pytest.mark.parametrize("expression", ["", "* * * *", "61 * * * *", "0 25 * * *", "0 0 0 * *", "*/0 * * * *", "x * * * *"])
    def test_invalid_expressions_raise(self, expression: str) -> None:
        with pytest.raises(WorkflowExecutionError):
            _MinimalCron(expression)


def _simple_workflow_request() -> WorkflowCreateRequest:
    return WorkflowCreateRequest(
        name="cron-target",
        nodes=[
            WorkflowNode(id="a", type=WorkflowNodeType.INPUT),
            WorkflowNode(id="b", type=WorkflowNodeType.OUTPUT, config={"from": "a"}),
        ],
        edges=[WorkflowEdge(source="a", target="b")],
    )


def _build_scheduler(tmp_path):
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "runs.jsonl",
    )
    schedule_store = WorkflowScheduleStore(storage_path=tmp_path / "schedules.json")
    executor = WorkflowExecutor(agent=object(), repository=repository)
    runtime = WorkflowRuntimeManager(executor=executor, repository=repository)
    scheduler = WorkflowScheduler(repository=repository, runtime=runtime, schedule_store=schedule_store)
    return repository, schedule_store, scheduler


class TestCronScheduling:
    def test_schedule_with_cron_computes_next_fire(self, tmp_path) -> None:
        repository, schedule_store, scheduler = _build_scheduler(tmp_path)
        workflow = repository.upsert_definition(_simple_workflow_request())

        record = scheduler.schedule(
            workflow.id,
            WorkflowScheduleRequest(cron="0 12 * * *"),
            tenant_id="default",
            user_id="tester",
            permission_scope=[],
        )

        assert record.cron == "0 12 * * *"
        assert record.run_at > datetime.now(UTC)
        assert record.status == WorkflowScheduleStatus.PENDING
        reloaded = schedule_store.get(record.schedule_id)
        assert reloaded is not None and reloaded.cron == "0 12 * * *"

    def test_schedule_with_invalid_cron_raises(self, tmp_path) -> None:
        repository, _, scheduler = _build_scheduler(tmp_path)
        workflow = repository.upsert_definition(_simple_workflow_request())
        with pytest.raises(WorkflowExecutionError):
            scheduler.schedule(
                workflow.id,
                WorkflowScheduleRequest(cron="not-a-cron"),
                tenant_id="default",
                user_id="tester",
                permission_scope=[],
            )

    @pytest.mark.asyncio
    async def test_run_due_rearms_cron_schedule(self, tmp_path) -> None:
        repository, schedule_store, scheduler = _build_scheduler(tmp_path)
        workflow = repository.upsert_definition(_simple_workflow_request())
        # 每分钟触发：创建后立即到期
        record = scheduler.schedule(
            workflow.id,
            WorkflowScheduleRequest(cron="* * * * *"),
            tenant_id="default",
            user_id="tester",
            permission_scope=[],
        )
        assert record.run_at <= datetime.now(UTC) + timedelta(minutes=1)
        # 强制到期
        schedule_store.reschedule(record.schedule_id, run_at=datetime.now(UTC) - timedelta(seconds=1))

        triggered = await scheduler.run_due(worker_id="test-worker")

        assert len(triggered) == 1
        updated = schedule_store.get(record.schedule_id)
        assert updated is not None
        assert updated.status == WorkflowScheduleStatus.PENDING, "cron 调度触发后应重排为 PENDING"
        assert updated.run_at > datetime.now(UTC) - timedelta(seconds=5), "应已重排到未来的下一次触发时间"
        assert updated.run_id is not None, "应记录本次触发的 run_id"
        assert updated.locked_by is None and updated.locked_until is None

    @pytest.mark.asyncio
    async def test_run_due_one_shot_schedule_still_terminal(self, tmp_path) -> None:
        repository, schedule_store, scheduler = _build_scheduler(tmp_path)
        workflow = repository.upsert_definition(_simple_workflow_request())
        record = scheduler.schedule(
            workflow.id,
            WorkflowScheduleRequest(run_at=datetime.now(UTC) - timedelta(seconds=1)),
            tenant_id="default",
            user_id="tester",
            permission_scope=[],
        )

        triggered = await scheduler.run_due(worker_id="test-worker")

        assert len(triggered) == 1
        updated = schedule_store.get(record.schedule_id)
        assert updated is not None and updated.status == WorkflowScheduleStatus.TRIGGERED
