"""Tests for CompletionPhase."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.core.agent_phases import CompletionPhase, PhaseContext
from backend.app.core.contracts import AgentRunResponse, RunStatus


class TestCompletionPhase:
    """Test suite for CompletionPhase."""

    @pytest.mark.asyncio
    async def test_completion_phase_execute(
        self, phase_context: PhaseContext
    ) -> None:
        """Test CompletionPhase.execute()."""
        phase = CompletionPhase()

        # Set up phase context
        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = ["obs1", "obs2"]
        phase_context.iteration = 3

        # Mock the necessary methods
        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()
        phase_context.loop.run_store.save = MagicMock()

        result = await phase.execute(phase_context)

        # Verify result
        assert result is not None
        assert isinstance(result, AgentRunResponse)
        assert result.status == RunStatus.COMPLETED
        assert result.answer == "Test answer"

    @pytest.mark.asyncio
    async def test_completion_phase_audit_recording(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that CompletionPhase records audit."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = []
        phase_context.iteration = 1

        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()

        await phase.execute(phase_context)

        # Verify audit was recorded
        phase_context.loop._record_audit.assert_called()

    @pytest.mark.asyncio
    async def test_completion_phase_memory_storage(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that CompletionPhase stores in memory."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = ["obs1"]
        phase_context.iteration = 1

        memory_id = str(uuid4())
        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=memory_id)
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()

        result = await phase.execute(phase_context)

        # Verify memory was stored
        phase_context.loop.memory.store.assert_called()
        assert result.snapshot["memory_id"] == memory_id

    @pytest.mark.asyncio
    async def test_completion_phase_execution_summary_building(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that CompletionPhase builds execution summary."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = ["obs1", "obs2"]
        phase_context.iteration = 2

        summary = {
            "iterations": 2,
            "observations": 2,
            "tools_used": 0,
            "status": "completed",
        }

        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(return_value=summary)
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()

        result = await phase.execute(phase_context)

        # Verify execution summary was built
        phase_context.loop._build_execution_summary.assert_called()
        assert result.execution_summary == summary

    @pytest.mark.asyncio
    async def test_completion_phase_trace_emission(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that CompletionPhase emits completion trace."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = []
        phase_context.iteration = 1

        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()

        await phase.execute(phase_context)

        # Verify trace was emitted
        phase_context.loop._emit_trace.assert_called()

    @pytest.mark.asyncio
    async def test_completion_phase_run_store_save(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that CompletionPhase saves to run store."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = []
        phase_context.iteration = 1

        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()
        phase_context.loop.run_store.save = MagicMock()

        await phase.execute(phase_context)

        # Verify run was saved
        phase_context.loop.run_store.save.assert_called()

    @pytest.mark.asyncio
    async def test_completion_phase_response_structure(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that CompletionPhase returns proper response structure."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = ["obs1"]
        phase_context.iteration = 1

        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()

        result = await phase.execute(phase_context)

        # Verify response structure
        assert result.trace_id is not None
        assert result.agent_id is not None
        assert result.status == RunStatus.COMPLETED
        assert result.answer == "Test answer"
        assert result.iterations >= 1
        assert result.memory_hits >= 1
        assert isinstance(result.tool_calls, list)
        assert isinstance(result.execution_summary, dict)
        assert isinstance(result.snapshot, dict)

    @pytest.mark.asyncio
    async def test_completion_phase_snapshot_building(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that CompletionPhase builds snapshot."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = ["obs1", "obs2"]
        phase_context.iteration = 2

        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()
        phase_context.loop.memory.count = MagicMock(return_value=10)

        result = await phase.execute(phase_context)

        # Verify snapshot was built
        assert result.snapshot is not None
        assert "memory_id" in result.snapshot
        assert "goal" in result.snapshot
        assert "stage" in result.snapshot
        assert "observation_count" in result.snapshot

    @pytest.mark.asyncio
    async def test_completion_phase_with_session_id(
        self, phase_context: PhaseContext
    ) -> None:
        """Test CompletionPhase with session ID."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = []
        phase_context.iteration = 1
        phase_context.context.session_id = str(uuid4())

        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()

        result = await phase.execute(phase_context)

        # Verify session ID is in execution summary
        assert result.execution_summary.get("session_id") is not None

    @pytest.mark.asyncio
    async def test_completion_phase_with_multiple_tool_calls(
        self, phase_context: PhaseContext, tool_call_record
    ) -> None:
        """Test CompletionPhase with multiple tool calls."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = [tool_call_record, tool_call_record]
        phase_context.observations = ["obs1"]
        phase_context.iteration = 2

        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()

        result = await phase.execute(phase_context)

        # Verify tool calls are in response
        assert len(result.tool_calls) == 2

    @pytest.mark.asyncio
    async def test_completion_phase_trajectory_finalization(
        self, phase_context: PhaseContext
    ) -> None:
        """Test that CompletionPhase finalizes trajectory."""
        phase = CompletionPhase()

        phase_context.answer = "Test answer"
        phase_context.tool_calls = []
        phase_context.observations = []
        phase_context.iteration = 1

        phase_context.loop._record_audit = MagicMock()
        phase_context.loop.memory.store = AsyncMock(return_value=str(uuid4()))
        phase_context.loop._build_execution_summary = MagicMock(
            return_value={"summary": "test"}
        )
        phase_context.loop._emit_trace = MagicMock()
        phase_context.loop.runtime_adapter.build_run_view = MagicMock(
            return_value=MagicMock(model_dump=MagicMock(return_value={"view": "test"}))
        )
        phase_context.loop.run_store = MagicMock()

        await phase.execute(phase_context)

        # Verify trajectory stage was updated
        assert phase_context.trajectory.stage == "finalizing"
