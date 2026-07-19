"""P1-07: 崩溃恢复模拟测试 —— worker 被 kill 后，重启进程可恢复未完成任务。

模拟方式：用 KeyboardInterrupt (BaseException) 在第二个节点执行期间杀死
execute() —— 普通的 except Exception 捕获不到它，任务直接死亡，存储中留下
一条 RUNNING 且带有节点级进度（resume_cursor）的 run，与真实 kill 完全同构。
随后用一套全新的 repository/runtime 对象（等价于进程重启）执行恢复。
"""
from datetime import UTC, datetime

import pytest

from backend.app.core.workflow_store import (
    SQLWorkflowRepository,
    SQLWorkflowScheduleStore,
    create_workflow_engine,
)
from backend.app.core.workflows import (
    WorkflowCreateRequest,
    WorkflowEdge,
    WorkflowExecutionError,
    WorkflowExecutor,
    WorkflowNode,
    WorkflowNodeResult,
    WorkflowNodeType,
    WorkflowRepository,
    WorkflowRunRecord,
    WorkflowRunStatus,
    WorkflowRuntimeManager,
    WorkflowScheduleStore,
    WorkflowScheduler,
)
from backend.app.workflow_worker import WorkflowSchedulerService


def _three_node_workflow() -> WorkflowCreateRequest:
    return WorkflowCreateRequest(
        name="recovery-wf",
        nodes=[
            WorkflowNode(id="a", type=WorkflowNodeType.INPUT, config={"key": "seed"}),
            WorkflowNode(id="b", type=WorkflowNodeType.TRANSFORM, config={"template": "{a}-b"}),
            WorkflowNode(id="c", type=WorkflowNodeType.OUTPUT, config={"from": "b"}),
        ],
        edges=[WorkflowEdge(source="a", target="b"), WorkflowEdge(source="b", target="c")],
    )


def _file_stack(tmp_path):
    repository = WorkflowRepository(
        definition_path=tmp_path / "workflows.json",
        run_path=tmp_path / "runs.jsonl",
    )
    executor = WorkflowExecutor(agent=object(), repository=repository)
    runtime = WorkflowRuntimeManager(executor=executor, repository=repository)
    return repository, executor, runtime


def _sql_stack(tmp_path):
    engine = create_workflow_engine(f"sqlite:///{tmp_path / 'workflow.db'}")
    repository = SQLWorkflowRepository(engine)
    executor = WorkflowExecutor(agent=object(), repository=repository)
    runtime = WorkflowRuntimeManager(executor=executor, repository=repository)
    return repository, executor, runtime


async def _crash_mid_run(repository, executor, monkeypatch) -> str:
    """执行到节点 b 时杀死任务，返回 run_id。"""
    definition = repository.upsert_definition(_three_node_workflow())
    original_execute_node = WorkflowExecutor._execute_node
    calls = {"b": 0}

    async def kill_on_b(self, run_context, node, definition, state, inputs, approved_approvals):
        if node.id == "b" and calls["b"] == 0:
            calls["b"] += 1
            raise KeyboardInterrupt("simulated worker kill")
        return await original_execute_node(
            self, run_context, node, definition, state, inputs, approved_approvals
        )

    monkeypatch.setattr(WorkflowExecutor, "_execute_node", kill_on_b)
    with pytest.raises(KeyboardInterrupt):
        await executor.execute(
            definition.id, {"seed": "s"}, run_id=None, worker_id="dead-worker"
        )
    monkeypatch.undo()

    runs = repository.list_runs(workflow_id=definition.id, limit=1)
    assert runs, "run 记录必须已外置持久化"
    return runs[0].run_id


class TestProgressPersistence:
    """节点级进度持久化是崩溃恢复的前提。"""

    @pytest.mark.parametrize("stack", [_file_stack, _sql_stack])
    async def test_progress_persisted_before_kill(self, tmp_path, monkeypatch, stack) -> None:
        repository, executor, _ = stack(tmp_path)
        run_id = await _crash_mid_run(repository, executor, monkeypatch)

        orphan = repository.get_run(run_id)
        assert orphan is not None
        assert orphan.status == WorkflowRunStatus.RUNNING, "被 kill 的 run 应保持 RUNNING"
        assert orphan.resume_cursor == 1, "节点 a 完成后游标必须已持久化"
        assert [r.node_id for r in orphan.node_results] == ["a"]
        assert orphan.worker_id == "dead-worker"
        assert orphan.heartbeat_at is not None


class TestCrashRecovery:
    @pytest.mark.parametrize("stack", [_file_stack, _sql_stack])
    async def test_restart_resumes_interrupted_run(self, tmp_path, monkeypatch, stack) -> None:
        repository, executor, _ = stack(tmp_path)
        run_id = await _crash_mid_run(repository, executor, monkeypatch)
        workflow_id = repository.get_run(run_id).workflow_id

        # —— 模拟进程重启：全新 executor/runtime（无任何内存任务状态）——
        fresh_executor = WorkflowExecutor(agent=object(), repository=repository)
        fresh_runtime = WorkflowRuntimeManager(executor=fresh_executor, repository=repository)

        interrupted = fresh_runtime.list_interrupted_runs()
        assert [r.run_id for r in interrupted] == [run_id]

        recovered = await fresh_runtime.recover_interrupted_runs(resume=True)
        assert [r.run_id for r in recovered] == [run_id]

        # 恢复任务在本 runtime 中登记，等待其完成
        task = fresh_runtime._tasks.get(run_id)
        assert task is not None, "恢复的 run 必须由新 runtime 接管"
        final = await task

        assert final.status == WorkflowRunStatus.COMPLETED
        assert final.run_id == run_id
        assert [r.node_id for r in final.node_results] == ["a", "b", "c"], (
            "节点 a 不得重复执行（结果来自检查点），b/c 续跑"
        )
        # 状态重建：c 的输出依赖 b，b 依赖 a —— 链式渲染成功即证明状态恢复正确
        assert final.outputs["c"] == "s-b"
        stored = repository.get_run(run_id)
        assert stored.status == WorkflowRunStatus.COMPLETED
        assert stored.resume_cursor == 3

    @pytest.mark.parametrize("stack", [_file_stack, _sql_stack])
    async def test_recovery_marks_failed_when_definition_missing(
        self, tmp_path, monkeypatch, stack
    ) -> None:
        repository, executor, _ = stack(tmp_path)
        run_id = await _crash_mid_run(repository, executor, monkeypatch)
        workflow_id = repository.get_run(run_id).workflow_id
        repository.delete_definition(workflow_id)

        fresh_executor = WorkflowExecutor(agent=object(), repository=repository)
        fresh_runtime = WorkflowRuntimeManager(executor=fresh_executor, repository=repository)
        recovered = await fresh_runtime.recover_interrupted_runs(resume=True)

        assert len(recovered) == 1
        assert recovered[0].status == WorkflowRunStatus.FAILED
        assert "interrupted" in (recovered[0].error or "")

    async def test_recovery_mark_failed_strategy(self, tmp_path, monkeypatch) -> None:
        repository, executor, _ = _file_stack(tmp_path)
        run_id = await _crash_mid_run(repository, executor, monkeypatch)

        fresh_executor = WorkflowExecutor(agent=object(), repository=repository)
        fresh_runtime = WorkflowRuntimeManager(executor=fresh_executor, repository=repository)
        recovered = await fresh_runtime.recover_interrupted_runs(resume=False)

        assert recovered[0].status == WorkflowRunStatus.FAILED
        assert "interrupted" in (recovered[0].error or "")

    async def test_resume_rejects_terminal_run(self, tmp_path) -> None:
        repository, executor, _ = _file_stack(tmp_path)
        definition = repository.upsert_definition(_three_node_workflow())
        record = await executor.execute(definition.id, {"seed": "x"})
        assert record.status == WorkflowRunStatus.COMPLETED
        with pytest.raises(WorkflowExecutionError, match="not resumable"):
            await executor.resume(record.run_id)

    async def test_resume_missing_run_raises(self, tmp_path) -> None:
        repository, executor, _ = _file_stack(tmp_path)
        with pytest.raises(WorkflowExecutionError, match="not found"):
            await executor.resume("no-such-run")

    async def test_running_runs_owned_by_this_runtime_are_not_interrupted(self, tmp_path) -> None:
        repository, executor, runtime = _file_stack(tmp_path)
        definition = repository.upsert_definition(_three_node_workflow())
        started = await runtime.start(definition.id, {"seed": "x"})
        assert runtime.list_interrupted_runs() == [], "本进程持有的 RUNNING run 不算孤儿"
        task = runtime._tasks[started.run_id]
        final = await task
        assert final.status == WorkflowRunStatus.COMPLETED


class TestSchedulerServiceRecovery:
    async def test_service_recovers_and_fires_due_schedules(self, tmp_path, monkeypatch) -> None:
        repository, executor, _ = _file_stack(tmp_path)
        run_id = await _crash_mid_run(repository, executor, monkeypatch)

        schedule_store = WorkflowScheduleStore(storage_path=tmp_path / "schedules.json")
        fresh_executor = WorkflowExecutor(agent=object(), repository=repository)
        fresh_runtime = WorkflowRuntimeManager(executor=fresh_executor, repository=repository)
        scheduler = WorkflowScheduler(
            repository=repository, runtime=fresh_runtime, schedule_store=schedule_store
        )

        service = WorkflowSchedulerService(
            scheduler=scheduler,
            interval_seconds=0.05,
            worker_id="restart-worker",
        )
        await service.start()
        try:
            assert service.running
            task = fresh_runtime._tasks.get(run_id)
            assert task is not None, "服务启动必须触发崩溃恢复"
            final = await task
            assert final.status == WorkflowRunStatus.COMPLETED
        finally:
            await service.stop()
        assert not service.running

    async def test_service_start_is_idempotent(self, tmp_path) -> None:
        repository, executor, runtime = _file_stack(tmp_path)
        schedule_store = WorkflowScheduleStore(storage_path=tmp_path / "schedules.json")
        scheduler = WorkflowScheduler(
            repository=repository, runtime=runtime, schedule_store=schedule_store
        )
        service = WorkflowSchedulerService(scheduler=scheduler, interval_seconds=0.05)
        await service.start()
        first_task = service._task
        await service.start()
        assert service._task is first_task
        await service.stop()


class TestSQLStoreRecoveryIntegration:
    """端到端：SQL 存储 + cron 调度 + 服务恢复共用同一引擎。"""

    async def test_sql_backed_scheduler_service(self, tmp_path) -> None:
        engine = create_workflow_engine(f"sqlite:///{tmp_path / 'workflow.db'}")
        repository = SQLWorkflowRepository(engine)
        schedule_store = SQLWorkflowScheduleStore(engine)
        executor = WorkflowExecutor(agent=object(), repository=repository)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repository)
        scheduler = WorkflowScheduler(
            repository=repository, runtime=runtime, schedule_store=schedule_store
        )
        definition = repository.upsert_definition(_three_node_workflow())
        schedule = scheduler.schedule(
            definition.id,
            __import__("backend.app.core.workflows", fromlist=["WorkflowScheduleRequest"]).WorkflowScheduleRequest(
                inputs={"seed": "sql"}, run_at=datetime.now(UTC)
            ),
            tenant_id="default",
            user_id="tester",
            permission_scope=[],
        )

        service = WorkflowSchedulerService(scheduler=scheduler, interval_seconds=0.05)
        await service.start()
        try:
            for _ in range(100):
                if schedule_store.get(schedule.schedule_id).status.value == "triggered":
                    break
                import asyncio

                await asyncio.sleep(0.05)
        finally:
            await service.stop()
        updated = schedule_store.get(schedule.schedule_id)
        assert updated.status.value == "triggered"
        assert updated.run_id is not None
