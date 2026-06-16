from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

CODING_LOOP_PHASES: tuple[str, ...] = ("explore", "plan", "edit", "verify", "deliver")


@dataclass(frozen=True)
class CodingLoopEvidence:
    key: str
    phase: str
    description: str
    acceptance: str
    required: bool = True
    present: bool = False
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class CodingLoopPlan:
    task: str
    phases: tuple[str, ...]
    evidence: tuple[CodingLoopEvidence, ...]
    acceptance_conditions: tuple[str, ...]
    available_tools: tuple[str, ...]
    tool_gaps: tuple[str, ...]

    def evidence_by_key(self) -> dict[str, CodingLoopEvidence]:
        return {item.key: item for item in self.evidence}

    def missing_required_evidence(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.evidence if item.required and not item.present)

    def acceptance_failures(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.task.strip():
            failures.append("task_missing")
        failures.extend(f"tool_missing:{role}" for role in self.tool_gaps)
        failures.extend(f"evidence_missing:{key}" for key in self.missing_required_evidence())
        return tuple(failures)

    def is_acceptable(self) -> bool:
        return not self.acceptance_failures()


def build_coding_loop_plan(
    task: str,
    repo_status: Mapping[str, Any] | None,
    available_tools: Sequence[str] | None,
) -> CodingLoopPlan:
    """Build the minimum evidence contract for a real coding-agent loop."""
    status = dict(repo_status or {})
    tools = _normalize_tools(available_tools)
    tool_gaps = _tool_gaps(tools)
    validation = _validation_state(status)

    evidence = (
        CodingLoopEvidence(
            key="repo_status_snapshot",
            phase="explore",
            description="Repository status was captured before claiming scope or completion.",
            acceptance="Includes git status, branch, cleanliness, or changed-file state.",
            present=_has_any(status, ("git_status", "branch", "clean", "changed_files", "status")),
            details=_string_details(status, ("branch", "git_status", "status")),
        ),
        CodingLoopEvidence(
            key="target_context",
            phase="explore",
            description="Relevant files, symbols, searches, or context notes were inspected.",
            acceptance="Names at least one inspected file, symbol, search, or context summary.",
            present=_has_any(
                status,
                ("inspected_files", "explored_symbols", "search_queries", "context_summary"),
            ),
            details=_sequence_details(
                status,
                ("inspected_files", "explored_symbols", "search_queries"),
            ),
        ),
        CodingLoopEvidence(
            key="ordered_phase_plan",
            phase="plan",
            description="The work is represented as explore, plan, edit, verify, and deliver.",
            acceptance="Phase order matches the canonical coding loop.",
            present=True,
            details=CODING_LOOP_PHASES,
        ),
        CodingLoopEvidence(
            key="acceptance_criteria",
            phase="plan",
            description="Completion requires concrete evidence instead of token-only parity.",
            acceptance="Every required evidence item is present and verification passes.",
            present=True,
            details=("all_required_evidence_present", "verification_result_passed"),
        ),
        CodingLoopEvidence(
            key="edit_artifact",
            phase="edit",
            description="A patch, diff, or changed-file list exists for the task.",
            acceptance="Names a patch id, diff summary, or changed files produced by the loop.",
            present=_has_any(status, ("patch_id", "diff_summary", "changed_files")),
            details=_sequence_details(status, ("changed_files",)) + _string_details(
                status,
                ("patch_id", "diff_summary"),
            ),
        ),
        CodingLoopEvidence(
            key="verification_result",
            phase="verify",
            description="Relevant validation was run after the edit.",
            acceptance="At least one validation command completed with exit_code=0 and no timeout.",
            present=validation["passed"],
            details=validation["details"],
        ),
        CodingLoopEvidence(
            key="delivery_summary",
            phase="deliver",
            description="The handoff states changed files, validation, and any remaining risk.",
            acceptance="Includes a final answer, delivery summary, or handoff summary.",
            present=_has_any(status, ("delivery_summary", "handoff_summary", "final_answer")),
            details=_string_details(status, ("delivery_summary", "handoff_summary", "final_answer")),
        ),
    )

    return CodingLoopPlan(
        task=task,
        phases=CODING_LOOP_PHASES,
        evidence=evidence,
        acceptance_conditions=(
            "phase_order_is_explore_plan_edit_verify_deliver",
            "required_evidence_is_present_for_each_phase",
            "verification_result_must_pass_after_edit",
            "delivery_summary_must_name_outcome_and_residual_risk",
        ),
        available_tools=tools,
        tool_gaps=tool_gaps,
    )


def _normalize_tools(available_tools: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(sorted({str(tool).strip().lower() for tool in available_tools or () if str(tool).strip()}))


def _tool_gaps(tools: tuple[str, ...]) -> tuple[str, ...]:
    role_keywords = {
        "explore": ("read", "search", "rg", "grep", "find", "codegraph", "context"),
        "edit": ("apply_patch", "patch", "edit", "write"),
        "verify": ("pytest", "test", "validation", "shell", "run"),
    }
    gaps = [
        role
        for role, keywords in role_keywords.items()
        if not any(keyword in tool for tool in tools for keyword in keywords)
    ]
    return tuple(gaps)


def _has_any(status: Mapping[str, Any], keys: Sequence[str]) -> bool:
    return any(_present(status.get(key)) for key in keys)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return bool(value)
    return True


def _sequence_details(status: Mapping[str, Any], keys: Sequence[str]) -> tuple[str, ...]:
    details: list[str] = []
    for key in keys:
        value = status.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
            details.extend(str(item) for item in value if str(item).strip())
    return tuple(details)


def _string_details(status: Mapping[str, Any], keys: Sequence[str]) -> tuple[str, ...]:
    details: list[str] = []
    for key in keys:
        value = status.get(key)
        if isinstance(value, str) and value.strip():
            details.append(value.strip())
    return tuple(details)


def _validation_state(status: Mapping[str, Any]) -> dict[str, Any]:
    results = status.get("validation_results")
    commands = _sequence_details(status, ("validation_commands",))
    if not isinstance(results, Sequence) or isinstance(results, (bytes, bytearray, str)):
        return {"passed": False, "details": commands}

    details = list(commands)
    passed = False
    for result in results:
        if not isinstance(result, Mapping):
            continue
        command = str(result.get("command") or "").strip()
        exit_code = result.get("exit_code")
        timed_out = result.get("timed_out") is True
        if command:
            details.append(f"{command}: exit_code={exit_code}")
        if exit_code == 0 and not timed_out:
            passed = True
    return {"passed": passed, "details": tuple(details)}


__all__ = [
    "CODING_LOOP_PHASES",
    "CodingLoopEvidence",
    "CodingLoopPlan",
    "build_coding_loop_plan",
]
