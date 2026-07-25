"""Tests for Work Mode — 跨应用长任务编排。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.work_mode.orchestrator import (
    Artifact,
    Milestone,
    WorkOrchestrator,
    WorkSession,
    WorkSessionStatus,
)
from backend.app.core.work_mode.connectors import (
    AppConnector,
    FileConnector,
    MemoryConnector,
)
from backend.app.core.work_mode.goal_decomposer import GoalDecomposer, MilestoneSpec


# ─── WorkSession Model Tests ──────────────────────────────────────────────────


class TestWorkSession:
    def test_defaults(self):
        session = WorkSession(goal="test goal")
        assert session.status == WorkSessionStatus.ACTIVE
        assert session.max_duration_hours == 8.0
        assert session.current_milestone_index == 0
        assert session.session_id  # non-empty uuid

    def test_to_dict(self):
        session = WorkSession(goal="build app")
        session.milestones = [
            Milestone(index=0, title="Setup", status="completed"),
            Milestone(index=1, title="Implement", status="pending"),
        ]
        d = session.to_dict()
        assert d["goal"] == "build app"
        assert d["status"] == "active"
        assert len(d["milestones"]) == 2
        assert d["milestones"][0]["title"] == "Setup"


class TestMilestone:
    def test_defaults(self):
        m = Milestone(index=0, title="Phase 1")
        assert m.status == "pending"
        assert m.output == ""

    def test_artifact_creation(self):
        a = Artifact(name="report.md", content="# Report", artifact_type="report")
        assert a.artifact_id  # non-empty
        assert a.artifact_type == "report"


# ─── GoalDecomposer Tests ─────────────────────────────────────────────────────


class TestGoalDecomposer:
    async def test_heuristic_decompose(self):
        """Without LLM, decomposer uses heuristic splitting."""
        decomposer = GoalDecomposer(llm_router=None)
        specs = await decomposer.decompose("Build a web application with auth", max_milestones=4)
        assert len(specs) >= 1
        assert all(isinstance(s, MilestoneSpec) for s in specs)
        assert all(s.title for s in specs)

    async def test_decompose_respects_max(self):
        decomposer = GoalDecomposer(llm_router=None)
        specs = await decomposer.decompose("Complex multi-step task", max_milestones=2)
        assert len(specs) <= 2

    async def test_decompose_with_llm(self):
        """With LLM router, decomposer uses LLM for decomposition."""
        import json
        router = AsyncMock()
        resp = MagicMock()
        resp.content = json.dumps([
            {"title": "Step 1", "description": "Do first thing", "deliverable": "output1"},
            {"title": "Step 2", "description": "Do second thing", "deliverable": "output2"},
        ])
        router.chat = AsyncMock(return_value=resp)

        decomposer = GoalDecomposer(llm_router=router)
        specs = await decomposer.decompose("Two step task", max_milestones=5)
        assert len(specs) == 2
        assert specs[0].title == "Step 1"


# ─── Connector Tests ──────────────────────────────────────────────────────────


class TestConnectors:
    async def test_memory_connector_read_write(self):
        conn = MemoryConnector()
        ok = await conn.write("hello world", target="greeting")
        assert ok is True
        result = await conn.read("greeting")
        assert "hello world" in result

    async def test_memory_connector_notify(self):
        conn = MemoryConnector()
        ok = await conn.notify("test notification")
        # notify calls write with target="notification"
        assert ok is True

    def test_file_connector_name(self):
        conn = FileConnector()
        assert conn.name == "file"


# ─── WorkOrchestrator Tests ───────────────────────────────────────────────────


class TestWorkOrchestrator:
    async def test_start_session(self):
        """Start session decomposes goal and creates milestones."""
        orch = WorkOrchestrator(agent_factory=None, llm_router=None)
        session = await orch.start_session("Build a REST API", max_hours=2.0, max_milestones=3)

        assert session.status == WorkSessionStatus.ACTIVE
        assert session.goal == "Build a REST API"
        assert len(session.milestones) >= 1
        assert session.max_duration_hours == 2.0

    async def test_get_session(self):
        orch = WorkOrchestrator(agent_factory=None, llm_router=None)
        session = await orch.start_session("Test goal")
        retrieved = orch.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    async def test_get_nonexistent_session(self):
        orch = WorkOrchestrator(agent_factory=None, llm_router=None)
        assert orch.get_session("nonexistent-id") is None

    async def test_list_sessions(self):
        orch = WorkOrchestrator(agent_factory=None, llm_router=None)
        await orch.start_session("Goal A")
        await orch.start_session("Goal B")
        sessions = orch.list_sessions()
        assert len(sessions) >= 2

    async def test_pause_session(self):
        orch = WorkOrchestrator(agent_factory=None, llm_router=None)
        session = await orch.start_session("Pausable task")
        paused = await orch.pause_session(session.session_id)
        assert paused is not None
        assert paused.status == WorkSessionStatus.PAUSED

    async def test_resume_session(self):
        orch = WorkOrchestrator(agent_factory=None, llm_router=None)
        session = await orch.start_session("Resumable task")
        await orch.pause_session(session.session_id)
        resumed = await orch.resume_session(session.session_id)
        assert resumed.status == WorkSessionStatus.ACTIVE

    async def test_tick_executes_milestone(self):
        """Tick should execute the current milestone."""
        outputs = iter(["milestone-1-output", "milestone-2-output"])

        async def agent_factory(task: str, context: dict) -> str:
            return next(outputs, "done")

        orch = WorkOrchestrator(agent_factory=agent_factory, llm_router=None)
        session = await orch.start_session("Two step task", max_milestones=2)

        # Tick first milestone
        updated = await orch.tick(session.session_id)
        assert updated.milestones[0].status in ("completed", "running")

    async def test_tick_nonexistent_raises(self):
        orch = WorkOrchestrator(agent_factory=None, llm_router=None)
        with pytest.raises(ValueError):
            await orch.tick("nonexistent-id")
