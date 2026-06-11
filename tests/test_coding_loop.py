from backend.app.core.coding_loop import (
    CODING_LOOP_PHASES,
    CodingLoopEvidence,
    CodingLoopPlan,
    build_coding_loop_plan,
)


def test_coding_loop_plan_uses_canonical_stage_order() -> None:
    plan = build_coding_loop_plan(
        "add a tested coding loop contract",
        repo_status=_complete_repo_status(),
        available_tools=("engineering_search", "apply_patch", "pytest"),
    )

    assert isinstance(plan, CodingLoopPlan)
    assert plan.phases == ("explore", "plan", "edit", "verify", "deliver")
    assert plan.phases == CODING_LOOP_PHASES
    assert [item.phase for item in plan.evidence] == [
        "explore",
        "explore",
        "plan",
        "plan",
        "edit",
        "verify",
        "deliver",
    ]
    assert plan.is_acceptable() is True
    assert plan.acceptance_failures() == ()


def test_coding_loop_plan_names_required_evidence_for_real_agent_closure() -> None:
    plan = build_coding_loop_plan(
        "replace token-only parity with closure evidence",
        repo_status=_complete_repo_status(),
        available_tools=("codegraph_context", "apply_patch", "uv run pytest"),
    )

    evidence_by_key = plan.evidence_by_key()

    assert all(isinstance(item, CodingLoopEvidence) for item in plan.evidence)
    assert set(evidence_by_key) == {
        "repo_status_snapshot",
        "target_context",
        "ordered_phase_plan",
        "acceptance_criteria",
        "edit_artifact",
        "verification_result",
        "delivery_summary",
    }
    assert evidence_by_key["verification_result"].present is True
    assert evidence_by_key["verification_result"].acceptance == (
        "At least one validation command completed with exit_code=0 and no timeout."
    )
    assert "verification_result_must_pass_after_edit" in plan.acceptance_conditions
    assert "required_evidence_is_present_for_each_phase" in plan.acceptance_conditions


def test_coding_loop_plan_fails_acceptance_when_required_evidence_is_missing() -> None:
    plan = build_coding_loop_plan(
        "ship the change",
        repo_status={
            "git_status": " M source/backend/app/core/coding_loop.py",
            "inspected_files": ["source/backend/app/core/coding_loop.py"],
            "changed_files": ["source/backend/app/core/coding_loop.py"],
            "validation_results": [
                {"command": "pytest source/tests/test_coding_loop.py", "exit_code": 1}
            ],
        },
        available_tools=("engineering_search", "apply_patch", "pytest"),
    )

    assert plan.is_acceptable() is False
    assert plan.missing_required_evidence() == ("verification_result", "delivery_summary")
    assert plan.acceptance_failures() == (
        "evidence_missing:verification_result",
        "evidence_missing:delivery_summary",
    )


def test_coding_loop_plan_reports_tool_gaps_as_acceptance_failures() -> None:
    plan = build_coding_loop_plan(
        "edit without capabilities should not be acceptable",
        repo_status=_complete_repo_status(),
        available_tools=("pytest",),
    )

    assert plan.tool_gaps == ("explore", "edit")
    assert "tool_missing:explore" in plan.acceptance_failures()
    assert "tool_missing:edit" in plan.acceptance_failures()
    assert plan.is_acceptable() is False


def _complete_repo_status() -> dict:
    return {
        "git_status": " M source/backend/app/core/coding_loop.py",
        "branch": "codex/coding-loop",
        "inspected_files": [
            "source/backend/app/core/agent_run_closure.py",
            "source/tests/test_codex_parity_readiness.py",
        ],
        "changed_files": [
            "source/backend/app/core/coding_loop.py",
            "source/tests/test_coding_loop.py",
        ],
        "validation_results": [
            {
                "command": "uv run --isolated --python 3.11 pytest source/tests/test_coding_loop.py",
                "exit_code": 0,
                "timed_out": False,
            }
        ],
        "delivery_summary": "Changed files and pytest result are ready for handoff.",
    }
