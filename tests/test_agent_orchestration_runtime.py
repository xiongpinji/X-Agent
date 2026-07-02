from __future__ import annotations

import asyncio
import time

import pytest

from backend.app.core.agent_orchestration_runtime import (
    AgentAssignment,
    SubagentRunOutput,
    run_agent_orchestration_runtime,
    run_agent_orchestration_runtime_smoke,
)


@pytest.mark.asyncio
async def test_agent_orchestration_runtime_runs_subagents_concurrently() -> None:
    started: list[tuple[str, float]] = []
    released = asyncio.Event()

    async def runner(assignment: AgentAssignment, *, trace_id: str) -> SubagentRunOutput:
        started.append((assignment.assignment_id, time.perf_counter()))
        if len(started) == 2:
            released.set()
        await released.wait()
        await asyncio.sleep(0.02)
        return SubagentRunOutput(
            result={"trace_id": trace_id, "completed": assignment.assignment_id},
            artifacts=(f"artifact://{assignment.assignment_id}",),
            changed_files=(f"{assignment.assignment_id}.py",),
            validation_evidence=(f"pytest::{assignment.assignment_id}",),
            validation={"passed": True},
        )

    summary = await run_agent_orchestration_runtime(
        (
            AgentAssignment("a1", "agent-a", "first assignment"),
            AgentAssignment("a2", "agent-b", "second assignment"),
        ),
        runner,
        max_parallel=2,
        timeout_seconds=1,
    )

    assert summary.status == "ready_for_merge"
    assert summary.ready_to_merge is True
    assert summary.failure_count == 0
    assert len(started) == 2
    assert abs(started[0][1] - started[1][1]) < 0.05
    result_payloads = [item.to_dict() for item in summary.results]
    assert len({item["trace_id"] for item in result_payloads}) == 2
    assert {item["status"] for item in result_payloads} == {"succeeded"}
    assert all(item["validation_evidence"] for item in result_payloads)


@pytest.mark.asyncio
async def test_agent_orchestration_runtime_isolates_single_failure() -> None:
    async def runner(assignment: AgentAssignment, *, trace_id: str) -> SubagentRunOutput:
        if assignment.assignment_id == "bad":
            raise ValueError("acceptance payload is invalid")
        return SubagentRunOutput(
            result={"trace_id": trace_id},
            artifacts=("artifact://good",),
            changed_files=("good.py",),
            validation_evidence=("pytest::good",),
            validation={"passed": True},
        )

    summary = await run_agent_orchestration_runtime(
        (
            AgentAssignment("good", "agent-good", "good assignment"),
            AgentAssignment("bad", "agent-bad", "bad assignment"),
        ),
        runner,
        max_parallel=2,
    )

    results = {item.assignment_id: item for item in summary.results}
    assert summary.status == "blocked"
    assert summary.failure_count == 1
    assert results["good"].status == "succeeded"
    assert results["bad"].status == "failed"
    assert results["bad"].failure_category == "validation_error"
    assert "retry_failed_subagents" in summary.blocking_reasons
    assert "retry_assignment:bad:validation_error" in summary.required_followups


@pytest.mark.asyncio
async def test_agent_orchestration_runtime_blocks_conflicting_changed_files() -> None:
    async def runner(assignment: AgentAssignment, *, trace_id: str) -> SubagentRunOutput:
        return SubagentRunOutput(
            result={"trace_id": trace_id},
            artifacts=(f"artifact://{assignment.assignment_id}",),
            changed_files=("shared.py",),
            validation_evidence=(f"pytest::{assignment.assignment_id}",),
            validation={"passed": True},
        )

    summary = await run_agent_orchestration_runtime(
        (
            AgentAssignment("left", "agent-left", "left edit"),
            AgentAssignment("right", "agent-right", "right edit"),
        ),
        runner,
        max_parallel=2,
    )

    assert summary.status == "blocked"
    assert summary.conflicts == {"shared.py": ("agent-left", "agent-right")}
    assert "resolve_conflicts" in summary.blocking_reasons
    assert "resolve_conflict:shared.py" in summary.required_followups
    assert all(item.conflicts == ("shared.py",) for item in summary.results)


@pytest.mark.asyncio
async def test_agent_orchestration_runtime_blocks_missing_validation_evidence() -> None:
    async def runner(assignment: AgentAssignment, *, trace_id: str) -> dict:
        return {
            "result": {"trace_id": trace_id},
            "artifacts": [f"artifact://{assignment.assignment_id}"],
            "changed_files": [f"{assignment.assignment_id}.py"],
            "validation": {"passed": True},
        }

    summary = await run_agent_orchestration_runtime(
        ({"assignment_id": "a1", "agent_id": "agent-a", "objective": "missing evidence"},),
        runner,
    )

    assert summary.status == "blocked"
    assert summary.missing_validation_evidence_count == 1
    assert "collect_validation_evidence" in summary.blocking_reasons
    assert "collect_validation_evidence:a1" in summary.required_followups


@pytest.mark.asyncio
async def test_agent_orchestration_runtime_builds_parent_merge_sequence() -> None:
    async def runner(assignment: AgentAssignment, *, trace_id: str) -> SubagentRunOutput:
        return SubagentRunOutput(
            result={"trace_id": trace_id, "completed": assignment.assignment_id},
            artifacts=(f"artifact://{assignment.assignment_id}",),
            changed_files=(f"{assignment.assignment_id}.py",),
            validation_evidence=(f"pytest::{assignment.assignment_id}",),
            validation={"passed": True},
        )

    summary = await run_agent_orchestration_runtime(
        (
            AgentAssignment("execute", "agent-execute", "execute", metadata={"merge_order": 20}),
            AgentAssignment("plan", "agent-plan", "plan", metadata={"merge_order": 10}),
        ),
        runner,
        max_parallel=2,
    )

    payload = summary.to_dict()
    assert summary.status == "ready_for_merge"
    assert [item.assignment_id for item in summary.merge_sequence] == ["plan", "execute"]
    assert [item["merge_order"] for item in payload["merge_sequence"]] == [10, 20]
    assert payload["parent_acceptance_report"]["status"] == "accepted"
    assert payload["parent_acceptance_report"]["merge_sequence_assignment_ids"] == ["plan", "execute"]


@pytest.mark.asyncio
async def test_agent_orchestration_runtime_blocks_duplicate_merge_order() -> None:
    async def runner(assignment: AgentAssignment, *, trace_id: str) -> SubagentRunOutput:
        return SubagentRunOutput(
            result={"trace_id": trace_id},
            artifacts=(f"artifact://{assignment.assignment_id}",),
            changed_files=(f"{assignment.assignment_id}.py",),
            validation_evidence=(f"pytest::{assignment.assignment_id}",),
            validation={"passed": True},
        )

    summary = await run_agent_orchestration_runtime(
        (
            AgentAssignment("left", "agent-left", "left", metadata={"merge_order": 10}),
            AgentAssignment("right", "agent-right", "right", metadata={"merge_order": 10}),
        ),
        runner,
        max_parallel=2,
    )

    payload = summary.to_dict()
    assert summary.status == "blocked"
    assert summary.merge_order_conflicts == {10: ("left", "right")}
    assert "resolve_merge_order_conflicts" in summary.blocking_reasons
    assert "resolve_merge_order_conflict:10" in summary.required_followups
    assert all("merge_order_conflict" in item["blockers"] for item in payload["merge_sequence"])


@pytest.mark.asyncio
async def test_agent_orchestration_runtime_marks_timeout_without_failing_batch() -> None:
    async def runner(assignment: AgentAssignment, *, trace_id: str) -> SubagentRunOutput:
        if assignment.assignment_id == "slow":
            await asyncio.sleep(0.05)
        return SubagentRunOutput(validation_evidence=(f"pytest::{assignment.assignment_id}",))

    summary = await run_agent_orchestration_runtime(
        (
            AgentAssignment("fast", "agent-fast", "fast"),
            AgentAssignment("slow", "agent-slow", "slow"),
        ),
        runner,
        max_parallel=2,
        timeout_seconds=0.01,
    )

    results = {item.assignment_id: item for item in summary.results}
    assert summary.status == "blocked"
    assert summary.timed_out_count == 1
    assert results["fast"].status == "succeeded"
    assert results["slow"].status == "timed_out"
    assert results["slow"].failure_category == "timeout"
    assert "retry_timed_out_subagents" in summary.blocking_reasons


@pytest.mark.asyncio
async def test_agent_orchestration_runtime_smoke_returns_merge_ready_summary() -> None:
    summary = await run_agent_orchestration_runtime_smoke()

    payload = summary.to_dict()
    assert payload["kind"] == "agent_orchestration_runtime_summary"
    assert payload["status"] == "ready_for_merge"
    assert payload["ready_to_merge"] is True
    assert len(payload["results"]) == 2
    assert len({item["trace_id"] for item in payload["results"]}) == 2
    assert payload["parent_acceptance_report"]["status"] == "accepted"
