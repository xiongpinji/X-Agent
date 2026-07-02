from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable

SubagentStatus = Literal["succeeded", "failed", "timed_out"]
RuntimeStatus = Literal["ready_for_merge", "blocked"]


@dataclass(frozen=True)
class AgentAssignment:
    assignment_id: str
    agent_id: str
    objective: str
    inputs: Mapping[str, Any] = field(default_factory=dict)
    expected_changed_files: tuple[str, ...] = ()
    validation_required: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> AgentAssignment:
        return cls(
            assignment_id=str(payload["assignment_id"]),
            agent_id=str(payload["agent_id"]),
            objective=str(payload.get("objective", "")),
            inputs=dict(payload.get("inputs") or {}),
            expected_changed_files=tuple(str(item) for item in payload.get("expected_changed_files", ())),
            validation_required=bool(payload.get("validation_required", True)),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True)
class SubagentRunOutput:
    result: Mapping[str, Any] = field(default_factory=dict)
    artifacts: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    validation_evidence: tuple[str, ...] = ()
    validation: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> SubagentRunOutput:
        return cls(
            result=dict(payload.get("result") or {}),
            artifacts=tuple(str(item) for item in payload.get("artifacts", ())),
            changed_files=tuple(str(item) for item in payload.get("changed_files", ())),
            validation_evidence=tuple(str(item) for item in payload.get("validation_evidence", ())),
            validation=dict(payload.get("validation") or {}),
        )


@dataclass(frozen=True)
class SubagentResult:
    assignment_id: str
    agent_id: str
    trace_id: str
    started_at: str
    completed_at: str
    duration_ms: int
    status: SubagentStatus
    result: Mapping[str, Any] = field(default_factory=dict)
    artifacts: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    validation_evidence: tuple[str, ...] = ()
    validation: Mapping[str, Any] = field(default_factory=dict)
    conflicts: tuple[str, ...] = ()
    merge_order: int | None = None
    failure_category: str | None = None
    error: str | None = None

    @property
    def has_validation_evidence(self) -> bool:
        return bool(self.validation_evidence)

    def with_conflicts(self, conflicts: Sequence[str]) -> SubagentResult:
        return SubagentResult(
            assignment_id=self.assignment_id,
            agent_id=self.agent_id,
            trace_id=self.trace_id,
            started_at=self.started_at,
            completed_at=self.completed_at,
            duration_ms=self.duration_ms,
            status=self.status,
            result=self.result,
            artifacts=self.artifacts,
            changed_files=self.changed_files,
            validation_evidence=self.validation_evidence,
            validation=self.validation,
            conflicts=tuple(conflicts),
            merge_order=self.merge_order,
            failure_category=self.failure_category,
            error=self.error,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "agent_id": self.agent_id,
            "trace_id": self.trace_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "result": dict(self.result),
            "artifacts": list(self.artifacts),
            "changed_files": list(self.changed_files),
            "validation_evidence": list(self.validation_evidence),
            "validation": dict(self.validation),
            "conflicts": list(self.conflicts),
            "merge_order": self.merge_order,
            "failure_category": self.failure_category,
            "error": self.error,
        }


@dataclass(frozen=True)
class MergeSequenceStep:
    assignment_id: str
    agent_id: str
    merge_order: int | None
    status: SubagentStatus
    changed_files: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    validation_evidence_count: int = 0
    blocking: bool = False
    blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "agent_id": self.agent_id,
            "merge_order": self.merge_order,
            "status": self.status,
            "changed_files": list(self.changed_files),
            "artifacts": list(self.artifacts),
            "validation_evidence_count": self.validation_evidence_count,
            "blocking": self.blocking,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class RuntimeSummary:
    kind: str
    status: RuntimeStatus
    ready_to_merge: bool
    started_at: str
    completed_at: str
    duration_ms: int
    max_parallel: int
    timeout_seconds: float | None
    results: tuple[SubagentResult, ...]
    merge_sequence: tuple[MergeSequenceStep, ...]
    parent_acceptance_report: Mapping[str, Any]
    conflicts: Mapping[str, tuple[str, ...]]
    merge_order_conflicts: Mapping[int, tuple[str, ...]]
    failure_count: int
    timed_out_count: int
    missing_validation_evidence_count: int
    required_followups: tuple[str, ...]
    blocking_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "ready_to_merge": self.ready_to_merge,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "max_parallel": self.max_parallel,
            "timeout_seconds": self.timeout_seconds,
            "results": [item.to_dict() for item in self.results],
            "merge_sequence": [item.to_dict() for item in self.merge_sequence],
            "parent_acceptance_report": dict(self.parent_acceptance_report),
            "conflicts": {path: list(agent_ids) for path, agent_ids in self.conflicts.items()},
            "merge_order_conflicts": {str(order): list(ids) for order, ids in self.merge_order_conflicts.items()},
            "failure_count": self.failure_count,
            "timed_out_count": self.timed_out_count,
            "missing_validation_evidence_count": self.missing_validation_evidence_count,
            "required_followups": list(self.required_followups),
            "blocking_reasons": list(self.blocking_reasons),
        }


@runtime_checkable
class SubagentRunner(Protocol):
    def __call__(self, assignment: AgentAssignment, *, trace_id: str) -> Awaitable[SubagentRunOutput | Mapping[str, Any]]:
        ...


Runner = SubagentRunner | Callable[[AgentAssignment], Awaitable[SubagentRunOutput | Mapping[str, Any]]]


async def run_agent_orchestration_runtime(
    assignments: Sequence[AgentAssignment | Mapping[str, Any]],
    runner: Runner,
    *,
    max_parallel: int = 4,
    timeout_seconds: float | None = None,
) -> RuntimeSummary:
    if max_parallel < 1:
        raise ValueError("max_parallel must be >= 1")

    normalized_assignments = tuple(_coerce_assignment(item) for item in assignments)
    started_at = _now_iso()
    started_monotonic = time.perf_counter()
    semaphore = asyncio.Semaphore(max_parallel)
    tasks = [
        _run_one_assignment(
            assignment,
            runner,
            semaphore=semaphore,
            timeout_seconds=timeout_seconds,
        )
        for assignment in normalized_assignments
    ]
    raw_results = await asyncio.gather(*tasks)
    results, conflicts = _attach_conflicts(raw_results)
    completed_at = _now_iso()
    duration_ms = _duration_ms(started_monotonic)
    return _build_runtime_summary(
        results,
        conflicts=conflicts,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        max_parallel=max_parallel,
        timeout_seconds=timeout_seconds,
    )


async def run_agent_orchestration_runtime_smoke() -> RuntimeSummary:
    async def runner(assignment: AgentAssignment, *, trace_id: str) -> SubagentRunOutput:
        await asyncio.sleep(0)
        return SubagentRunOutput(
            result={"trace_id": trace_id, "objective": assignment.objective},
            artifacts=(f"artifact://{assignment.assignment_id}",),
            changed_files=assignment.expected_changed_files,
            validation_evidence=(f"validated:{assignment.assignment_id}",),
            validation={"passed": True},
        )

    return await run_agent_orchestration_runtime(
        (
            AgentAssignment(
                assignment_id="runtime-smoke-a",
                agent_id="agent-a",
                objective="prove runtime smoke path",
                expected_changed_files=("backend/app/core/agent_orchestration_runtime.py",),
            ),
            AgentAssignment(
                assignment_id="runtime-smoke-b",
                agent_id="agent-b",
                objective="prove parallel smoke path",
                expected_changed_files=("tests/test_agent_orchestration_runtime.py",),
            ),
        ),
        runner,
        max_parallel=2,
        timeout_seconds=2,
    )


def run_agent_orchestration_runtime_smoke_sync() -> dict[str, Any]:
    return asyncio.run(run_agent_orchestration_runtime_smoke()).to_dict()


async def _run_one_assignment(
    assignment: AgentAssignment,
    runner: Runner,
    *,
    semaphore: asyncio.Semaphore,
    timeout_seconds: float | None,
) -> SubagentResult:
    trace_id = f"subagent-{uuid.uuid4().hex}"

    async with semaphore:
        started_at = _now_iso()
        started_monotonic = time.perf_counter()
        try:
            output = await _call_runner(runner, assignment, trace_id=trace_id, timeout_seconds=timeout_seconds)
            completed_at = _now_iso()
            return SubagentResult(
                assignment_id=assignment.assignment_id,
                agent_id=assignment.agent_id,
                trace_id=trace_id,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=_duration_ms(started_monotonic),
                status="succeeded",
                result=output.result,
                artifacts=output.artifacts,
                changed_files=output.changed_files,
                validation_evidence=output.validation_evidence,
                validation=output.validation,
                merge_order=_merge_order_from_assignment(assignment),
            )
        except TimeoutError as exc:
            completed_at = _now_iso()
            return _failure_result(
                assignment,
                trace_id=trace_id,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=_duration_ms(started_monotonic),
                status="timed_out",
                failure_category="timeout",
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - runner errors must be isolated per subagent
            completed_at = _now_iso()
            return _failure_result(
                assignment,
                trace_id=trace_id,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=_duration_ms(started_monotonic),
                status="failed",
                failure_category=_classify_failure(exc),
                error=f"{type(exc).__name__}: {exc}",
            )


async def _call_runner(
    runner: Runner,
    assignment: AgentAssignment,
    *,
    trace_id: str,
    timeout_seconds: float | None,
) -> SubagentRunOutput:
    async def invoke() -> SubagentRunOutput:
        try:
            value = runner(assignment, trace_id=trace_id)  # type: ignore[misc]
        except TypeError:
            value = runner(assignment)  # type: ignore[call-arg]
        if inspect.isawaitable(value):
            value = await value
        return _coerce_runner_output(value)

    if timeout_seconds is None:
        return await invoke()
    try:
        return await asyncio.wait_for(invoke(), timeout=timeout_seconds)
    except TimeoutError as exc:
        raise TimeoutError(f"subagent runner exceeded {timeout_seconds} second(s)") from exc


def _build_runtime_summary(
    results: Sequence[SubagentResult],
    *,
    conflicts: Mapping[str, tuple[str, ...]],
    started_at: str,
    completed_at: str,
    duration_ms: int,
    max_parallel: int,
    timeout_seconds: float | None,
) -> RuntimeSummary:
    failure_count = sum(1 for item in results if item.status == "failed")
    timed_out_count = sum(1 for item in results if item.status == "timed_out")
    missing_validation_evidence_count = sum(
        1 for item in results if item.status == "succeeded" and not item.has_validation_evidence
    )
    merge_sequence, merge_order_conflicts = _build_merge_sequence(results)
    blocking_reasons: list[str] = []
    if conflicts:
        blocking_reasons.append("resolve_conflicts")
    if merge_order_conflicts:
        blocking_reasons.append("resolve_merge_order_conflicts")
    if failure_count:
        blocking_reasons.append("retry_failed_subagents")
    if timed_out_count:
        blocking_reasons.append("retry_timed_out_subagents")
    if missing_validation_evidence_count:
        blocking_reasons.append("collect_validation_evidence")

    required_followups = _required_followups(
        results,
        conflicts=conflicts,
        merge_order_conflicts=merge_order_conflicts,
        missing_validation_evidence_count=missing_validation_evidence_count,
    )
    ready_to_merge = not blocking_reasons
    parent_acceptance_report = _build_parent_acceptance_report(
        ready_to_merge=ready_to_merge,
        merge_sequence=merge_sequence,
        conflicts=conflicts,
        merge_order_conflicts=merge_order_conflicts,
        blocking_reasons=blocking_reasons,
        required_followups=required_followups,
    )
    return RuntimeSummary(
        kind="agent_orchestration_runtime_summary",
        status="ready_for_merge" if ready_to_merge else "blocked",
        ready_to_merge=ready_to_merge,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        max_parallel=max_parallel,
        timeout_seconds=timeout_seconds,
        results=tuple(results),
        merge_sequence=merge_sequence,
        parent_acceptance_report=parent_acceptance_report,
        conflicts=dict(conflicts),
        merge_order_conflicts=dict(merge_order_conflicts),
        failure_count=failure_count,
        timed_out_count=timed_out_count,
        missing_validation_evidence_count=missing_validation_evidence_count,
        required_followups=tuple(required_followups),
        blocking_reasons=tuple(blocking_reasons),
    )


def _attach_conflicts(results: Sequence[SubagentResult]) -> tuple[tuple[SubagentResult, ...], dict[str, tuple[str, ...]]]:
    file_agents: dict[str, list[str]] = defaultdict(list)
    for result in results:
        if result.status != "succeeded":
            continue
        for changed_file in result.changed_files:
            file_agents[changed_file].append(result.agent_id)

    conflicts = {
        changed_file: tuple(agent_ids)
        for changed_file, agent_ids in file_agents.items()
        if len(set(agent_ids)) > 1
    }
    if not conflicts:
        return tuple(results), {}

    results_with_conflicts = []
    for result in results:
        result_conflicts = [path for path in result.changed_files if path in conflicts]
        results_with_conflicts.append(result.with_conflicts(result_conflicts))
    return tuple(results_with_conflicts), conflicts


def _build_merge_sequence(
    results: Sequence[SubagentResult],
) -> tuple[tuple[MergeSequenceStep, ...], dict[int, tuple[str, ...]]]:
    ordered_results = sorted(
        results,
        key=lambda item: (
            item.merge_order is None,
            item.merge_order if item.merge_order is not None else 0,
            item.assignment_id,
        ),
    )
    order_assignments: dict[int, list[str]] = defaultdict(list)
    for result in results:
        if result.merge_order is not None:
            order_assignments[result.merge_order].append(result.assignment_id)
    merge_order_conflicts = {
        order: tuple(assignment_ids)
        for order, assignment_ids in order_assignments.items()
        if len(set(assignment_ids)) > 1
    }

    steps: list[MergeSequenceStep] = []
    for result in ordered_results:
        blockers: list[str] = []
        if result.status == "failed":
            blockers.append("subagent_failed")
        elif result.status == "timed_out":
            blockers.append("subagent_timed_out")
        if result.conflicts:
            blockers.append("changed_file_conflict")
        if result.status == "succeeded" and not result.has_validation_evidence:
            blockers.append("missing_validation_evidence")
        if result.merge_order is not None and result.merge_order in merge_order_conflicts:
            blockers.append("merge_order_conflict")
        steps.append(
            MergeSequenceStep(
                assignment_id=result.assignment_id,
                agent_id=result.agent_id,
                merge_order=result.merge_order,
                status=result.status,
                changed_files=result.changed_files,
                artifacts=result.artifacts,
                validation_evidence_count=len(result.validation_evidence),
                blocking=bool(blockers),
                blockers=tuple(blockers),
            )
        )
    return tuple(steps), merge_order_conflicts


def _build_parent_acceptance_report(
    *,
    ready_to_merge: bool,
    merge_sequence: Sequence[MergeSequenceStep],
    conflicts: Mapping[str, tuple[str, ...]],
    merge_order_conflicts: Mapping[int, tuple[str, ...]],
    blocking_reasons: Sequence[str],
    required_followups: Sequence[str],
) -> dict[str, Any]:
    blocked_steps = [item for item in merge_sequence if item.blocking]
    return {
        "kind": "agent_orchestration_parent_acceptance_report",
        "status": "accepted" if ready_to_merge else "blocked",
        "ready_to_merge": ready_to_merge,
        "merge_sequence_status": "passed" if not blocked_steps and not merge_order_conflicts else "blocked",
        "merge_sequence_assignment_ids": [item.assignment_id for item in merge_sequence],
        "merge_sequence_count": len(merge_sequence),
        "blocked_sequence_count": len(blocked_steps),
        "conflict_status": "clear" if not conflicts else "blocked",
        "merge_order_conflict_status": "clear" if not merge_order_conflicts else "blocked",
        "blocking_reasons": list(blocking_reasons),
        "required_followups": list(required_followups),
    }


def _required_followups(
    results: Sequence[SubagentResult],
    *,
    conflicts: Mapping[str, tuple[str, ...]],
    merge_order_conflicts: Mapping[int, tuple[str, ...]],
    missing_validation_evidence_count: int,
) -> list[str]:
    followups: list[str] = []
    followups.extend(f"resolve_conflict:{path}" for path in sorted(conflicts))
    followups.extend(f"resolve_merge_order_conflict:{order}" for order in sorted(merge_order_conflicts))
    followups.extend(
        f"retry_assignment:{item.assignment_id}:{item.failure_category}"
        for item in results
        if item.status in {"failed", "timed_out"}
    )
    if missing_validation_evidence_count:
        followups.extend(
            f"collect_validation_evidence:{item.assignment_id}"
            for item in results
            if item.status == "succeeded" and not item.has_validation_evidence
        )
    return followups[:20]


def _failure_result(
    assignment: AgentAssignment,
    *,
    trace_id: str,
    started_at: str,
    completed_at: str,
    duration_ms: int,
    status: SubagentStatus,
    failure_category: str,
    error: str,
) -> SubagentResult:
    return SubagentResult(
        assignment_id=assignment.assignment_id,
        agent_id=assignment.agent_id,
        trace_id=trace_id,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        status=status,
        failure_category=failure_category,
        merge_order=_merge_order_from_assignment(assignment),
        error=error,
    )


def _classify_failure(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return "validation_error"
    if isinstance(exc, PermissionError):
        return "permission_error"
    if isinstance(exc, FileNotFoundError):
        return "missing_resource"
    return "runner_error"


def _coerce_assignment(item: AgentAssignment | Mapping[str, Any]) -> AgentAssignment:
    if isinstance(item, AgentAssignment):
        return item
    return AgentAssignment.from_mapping(item)


def _coerce_runner_output(item: SubagentRunOutput | Mapping[str, Any]) -> SubagentRunOutput:
    if isinstance(item, SubagentRunOutput):
        return item
    return SubagentRunOutput.from_mapping(item)


def _merge_order_from_assignment(assignment: AgentAssignment) -> int | None:
    value = assignment.metadata.get("merge_order")
    if value is None:
        return None
    try:
        order = int(value)
    except (TypeError, ValueError):
        return None
    return order if order >= 0 else None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _duration_ms(started_monotonic: float) -> int:
    return max(0, round((time.perf_counter() - started_monotonic) * 1000))
