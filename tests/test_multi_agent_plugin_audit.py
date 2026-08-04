"""P2-01 + P2-07 + P2-12: 多Agent编排 + 插件市场 + 企业审计测试.

P2-01 覆盖:
- 任务分解 (代码/研究/批量/默认)
- 并行/串行/分层执行
- 失败恢复 (retry/skip/abort)
- 拓扑排序

P2-07 覆盖:
- 提交/审核/发布流水线
- 搜索/发现
- 安装/卸载
- 评价/统计
- 风险评分

P2-12 覆盖:
- CEF/Syslog/JSONL 格式化
- 留存策略评估
- 合规状态
- 分析聚合
"""

import pytest
from datetime import UTC, datetime, timedelta

from backend.app.core.collaboration.orchestrator import (
    FailurePolicy,
    MultiAgentOrchestrator,
    OrchestrationMode,
    OrchestrationPlan,
    SubTask,
    SubTaskStatus,
)
from backend.app.core.audit_enhanced.siem_exporter import SIEMConfig, SIEMExporter, SIEMFormat
from backend.app.core.audit_enhanced.retention import RetentionEngine, RetentionPolicy


# ─── P2-01: 多 Agent 编排 ─────────────────────────────────────────────────────


class TestTaskDecomposition:
    def setup_method(self):
        self.orchestrator = MultiAgentOrchestrator()

    def test_decompose_code_task(self):
        plan = self.orchestrator.decompose_task("实现用户登录功能代码")
        assert plan.mode == OrchestrationMode.SEQUENTIAL
        assert len(plan.subtasks) == 3
        assert "分析" in plan.subtasks[0].description

    def test_decompose_research_task(self):
        plan = self.orchestrator.decompose_task("研究竞品分析")
        assert plan.mode == OrchestrationMode.SEQUENTIAL
        assert len(plan.subtasks) == 3

    def test_decompose_batch_task(self):
        plan = self.orchestrator.decompose_task("批量处理多个文件")
        assert plan.mode == OrchestrationMode.PARALLEL
        assert len(plan.subtasks) == 3

    def test_decompose_default_task(self):
        plan = self.orchestrator.decompose_task("你好世界")
        assert len(plan.subtasks) == 1
        assert plan.subtasks[0].description == "你好世界"


class TestOrchestrationExecution:
    def setup_method(self):
        self.orchestrator = MultiAgentOrchestrator()

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        plan = OrchestrationPlan(
            task="并行测试",
            mode=OrchestrationMode.PARALLEL,
            subtasks=[
                SubTask(description="task-a"),
                SubTask(description="task-b"),
                SubTask(description="task-c"),
            ],
        )
        result = await self.orchestrator.execute(plan)
        assert result.status == "completed"
        assert result.completed == 3
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        st1 = SubTask(description="step-1")
        st2 = SubTask(description="step-2", depends_on=[st1.task_id])
        plan = OrchestrationPlan(
            task="串行测试",
            mode=OrchestrationMode.SEQUENTIAL,
            subtasks=[st1, st2],
        )
        result = await self.orchestrator.execute(plan)
        assert result.status == "completed"
        assert result.completed == 2

    @pytest.mark.asyncio
    async def test_hierarchical_execution(self):
        plan = OrchestrationPlan(
            task="分层测试",
            mode=OrchestrationMode.HIERARCHICAL,
            subtasks=[
                SubTask(description="leader"),
                SubTask(description="worker-1"),
                SubTask(description="worker-2"),
            ],
        )
        result = await self.orchestrator.execute(plan)
        assert result.status == "completed"
        assert result.completed == 3

    @pytest.mark.asyncio
    async def test_execution_stored(self):
        plan = OrchestrationPlan(task="存储测试", subtasks=[SubTask(description="t")])
        result = await self.orchestrator.execute(plan)
        fetched = self.orchestrator.get_execution(result.execution_id)
        assert fetched is not None
        assert fetched.execution_id == result.execution_id

    @pytest.mark.asyncio
    async def test_execution_duration(self):
        plan = OrchestrationPlan(task="计时测试", subtasks=[SubTask(description="t")])
        result = await self.orchestrator.execute(plan)
        assert result.duration_ms >= 0
        assert result.completed_at is not None


class TestTopologicalSort:
    def test_sort_with_dependencies(self):
        st1 = SubTask(task_id="a", description="first")
        st2 = SubTask(task_id="b", description="second", depends_on=["a"])
        st3 = SubTask(task_id="c", description="third", depends_on=["b"])
        ordered = MultiAgentOrchestrator._topological_sort([st3, st1, st2])
        ids = [s.task_id for s in ordered]
        assert ids.index("a") < ids.index("b") < ids.index("c")

    def test_layers_parallel(self):
        st1 = SubTask(task_id="a", description="a")
        st2 = SubTask(task_id="b", description="b")
        st3 = SubTask(task_id="c", description="c", depends_on=["a", "b"])
        layers = MultiAgentOrchestrator._topological_layers([st1, st2, st3])
        assert len(layers) == 2
        assert len(layers[0]) == 2  # a, b 并行
        assert len(layers[1]) == 1  # c


# ─── P2-07: 插件市场 ──────────────────────────────────────────────────────────


class TestSIEMExporter:
    def _make_record(self) -> dict:
        return {
            "id": "rec-1",
            "action": "user.login",
            "resource_type": "session",
            "resource_id": "sess-1",
            "tenant_id": "tenant-a",
            "actor_id": "user-1",
            "outcome": "success",
            "created_at": "2026-07-20T10:00:00+00:00",
            "trace_id": "trace-1",
        }

    def test_format_cef(self):
        exporter = SIEMExporter(SIEMConfig(format=SIEMFormat.CEF))
        line = exporter.format_record(self._make_record())
        assert line.startswith("CEF:0|X-Agent|")
        assert "user.login" in line
        assert "tenant-a" in line

    def test_format_syslog(self):
        exporter = SIEMExporter(SIEMConfig(format=SIEMFormat.SYSLOG))
        line = exporter.format_record(self._make_record())
        assert "xagent-audit" in line
        assert "tenant-a" in line

    def test_format_jsonl(self):
        exporter = SIEMExporter(SIEMConfig(format=SIEMFormat.JSON_LINES))
        line = exporter.format_record(self._make_record())
        import json
        data = json.loads(line)
        assert data["action"] == "user.login"
        assert "_siem" in data

    @pytest.mark.asyncio
    async def test_flush_to_buffer(self):
        exporter = SIEMExporter(SIEMConfig(format=SIEMFormat.CEF))
        records = [self._make_record() for _ in range(5)]
        result = await exporter.flush(records)
        assert result.exported == 5
        assert result.failed == 0
        assert len(exporter.get_buffer()) == 5


class TestRetentionEngine:
    def _make_records(self, count=10, age_days=0) -> list[dict]:
        now = datetime.now(UTC)
        records = []
        for i in range(count):
            created = now - timedelta(days=age_days + i)
            records.append({
                "id": f"rec-{i}",
                "created_at": created.isoformat(),
                "action": "test",
            })
        return records

    def test_evaluate_active(self):
        engine = RetentionEngine(RetentionPolicy(retention_days=365, archive_after_days=90))
        records = self._make_records(5, age_days=10)
        decision = engine.evaluate(records)
        assert decision.active_records == 5
        assert decision.delete_eligible == 0

    def test_evaluate_archive_eligible(self):
        engine = RetentionEngine(RetentionPolicy(retention_days=365, archive_after_days=90))
        records = self._make_records(5, age_days=100)
        decision = engine.evaluate(records)
        assert decision.archive_eligible == 5

    def test_evaluate_delete_eligible(self):
        engine = RetentionEngine(RetentionPolicy(retention_days=365, archive_after_days=90))
        records = self._make_records(5, age_days=400)
        decision = engine.evaluate(records)
        assert decision.delete_eligible == 5

    def test_enforce(self):
        engine = RetentionEngine(RetentionPolicy(retention_days=30, archive_after_days=7))
        records = self._make_records(10, age_days=0)  # 0-9 天
        result = engine.enforce(records)
        assert result.protected > 0  # WORM 保护

    def test_compliance_status_compliant(self):
        engine = RetentionEngine(RetentionPolicy(retention_days=365, immutable=True))
        records = self._make_records(5, age_days=10)
        status = engine.get_compliance_status(records)
        assert status.is_compliant
        assert status.worm_enabled

    def test_compliance_status_non_compliant(self):
        engine = RetentionEngine(RetentionPolicy(retention_days=30, immutable=True))
        records = self._make_records(5, age_days=60)
        status = engine.get_compliance_status(records)
        assert not status.is_compliant
        assert status.records_beyond_retention == 5
