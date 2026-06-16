from backend.app.core.agent_run_closure import build_agent_run_closure_report
from backend.app.core.contracts import (
    RiskLevel,
    RunStatus,
    ToolCallRecord,
    ToolPolicyVerdict,
    TraceEvent,
)


def _policy(approval_id: str | None = None) -> ToolPolicyVerdict:
    return ToolPolicyVerdict(
        allowed=True,
        reason="test",
        approval_id=approval_id,
    )


def _tool(
    name: str,
    *,
    success: bool = True,
    output=None,  # noqa: ANN001
    error: str | None = None,
    arguments_preview: dict | None = None,
    approval_id: str | None = None,
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=name,
        success=success,
        output=output,
        error=error,
        policy=_policy(approval_id=approval_id),
        risk_level=RiskLevel.LOW,
        arguments_preview=arguments_preview or {},
    )


def test_agent_run_closure_reports_ready_for_handoff_when_execution_and_validation_pass() -> None:
    report = build_agent_run_closure_report(
        task="Fix app and validate",
        status=RunStatus.COMPLETED,
        iterations=2,
        memory_hits=3,
        events=[TraceEvent(trace_id="trace-1", event="context.pack")],
        tool_calls=[
            _tool(
                "engineering_stage_patch_approval",
                output={
                    "changed_files": ["app.py", "tests/test_app.py"],
                    "approval_id": "approval-1",
                    "summary": "patched",
                },
            ),
            _tool(
                "engineering_run_validation",
                output={
                    "command": "pytest tests/test_app.py -q",
                    "exit_code": 0,
                    "timed_out": False,
                    "stdout": "1 passed",
                },
            ),
        ],
        answer="Done",
    )

    assert report["kind"] == "agent_run_closure_report"
    assert report["status"] == "ready_for_handoff"
    assert report["ready_for_handoff"] is True
    assert report["blocking_reasons"] == []
    assert report["phase_states"]["test"] == "passed"
    assert report["evidence"]["changes"][0]["changed_files"] == ["app.py", "tests/test_app.py"]
    assert report["next_actions"] == ["prepare_commit_or_handoff_report"]


def test_agent_run_closure_blocks_completed_answer_without_validation() -> None:
    report = build_agent_run_closure_report(
        task="Claim completion without tests",
        status=RunStatus.COMPLETED,
        iterations=1,
        memory_hits=0,
        events=[TraceEvent(trace_id="trace-1", event="context.pack")],
        tool_calls=[_tool("engineering_stage_patch_approval", output={"changed_files": ["app.py"]})],
        answer="Done",
    )

    assert report["status"] == "needs_followup"
    assert report["ready_for_handoff"] is False
    assert "validation_missing" in report["blocking_reasons"]
    assert "run_targeted_validation" in report["next_actions"]


def test_agent_run_closure_surfaces_failed_validation_and_repair_suggestion() -> None:
    report = build_agent_run_closure_report(
        task="Run validation",
        status=RunStatus.FAILED,
        iterations=3,
        memory_hits=1,
        events=[],
        tool_calls=[
            _tool(
                "engineering_run_validation",
                success=False,
                output={
                    "command": "pytest -q",
                    "exit_code": 1,
                    "timed_out": False,
                    "stderr": "failed",
                    "failure_attribution": {
                        "category": "test_failed",
                        "next_action": "fix_validation_failure_and_rerun",
                    },
                },
                error="pytest failed",
            )
        ],
        error="agent stopped after validation failure",
    )

    assert report["status"] == "needs_followup"
    assert report["phase_states"]["test"] == "failed"
    assert "validation_failed" in report["blocking_reasons"]
    assert "tool_failure" in report["blocking_reasons"]
    assert report["failure_suggestions"][0]["category"] == "test_failed"
    assert report["failure_suggestions"][0]["command"] == "pytest -q"
    assert report["next_actions"][0] == "fix_validation_failure_and_rerun"


def test_agent_run_closure_dedupes_event_failure_strategy_suggestions() -> None:
    report = build_agent_run_closure_report(
        task="Tool failed",
        status=RunStatus.FAILED,
        iterations=1,
        memory_hits=0,
        events=[
            TraceEvent(
                trace_id="trace-1",
                event="tool.failure_strategy",
                data={
                    "tool_name": "shell",
                    "category": "timeout",
                    "next_action": "retry_with_longer_timeout",
                    "retry_budget": 1,
                },
            ),
            TraceEvent(
                trace_id="trace-1",
                event="tool.failure_strategy",
                data={
                    "tool_name": "shell",
                    "category": "timeout",
                    "next_action": "retry_with_longer_timeout",
                    "retry_budget": 1,
                },
            ),
        ],
        tool_calls=[],
        error=None,
    )

    assert report["failure_suggestions"] == [
        {
            "source": "shell",
            "category": "timeout",
            "next_action": "retry_with_longer_timeout",
            "retry_budget": 1,
            "tool_router": None,
        }
    ]
    assert "retry_with_longer_timeout" in report["next_actions"]
