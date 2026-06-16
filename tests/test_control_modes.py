from __future__ import annotations

from backend.app.core.control_modes import (
    ControlModeStore,
    GoalCreateRequest,
    GoalLoopPolicy,
    GoalLoopService,
    GoalStatus,
    GoalStopReason,
    PlanModeDraftRequest,
    PlanModeService,
    PlanModeStatus,
)


def test_plan_mode_draft_requires_approval_and_contains_loop_contract() -> None:
    record = PlanModeService().draft(
        PlanModeDraftRequest(task="implement plan mode", context={"inspected_files": ["app.py"]}),
        tenant_id="tenant-a",
        user_id="user-a",
    )

    assert record.status == PlanModeStatus.WAITING_APPROVAL
    assert record.approval_required is True
    assert record.execution_plan["steps"]
    assert record.coding_loop["phases"] == ["explore", "plan", "edit", "verify", "deliver"]
    assert record.snapshot["next_action"] == "approve_plan"


def test_control_mode_store_persists_plan_and_goal(tmp_path) -> None:
    path = tmp_path / "control.json"
    store = ControlModeStore(path)
    plan = PlanModeService().draft(
        PlanModeDraftRequest(task="persist plan", require_approval=False),
        tenant_id="tenant-a",
        user_id="user-a",
    )
    goal, goal_plan = GoalLoopService().create(
        GoalCreateRequest(
            objective="persist goal",
            policy=GoalLoopPolicy(require_plan_approval=False),
        ),
        tenant_id="tenant-a",
        user_id="user-a",
    )

    store.save_plan(plan)
    store.save_plan(goal_plan)
    store.save_goal(goal)

    reloaded = ControlModeStore(path)
    assert reloaded.get_plan(plan.plan_id).status == PlanModeStatus.APPROVED
    assert reloaded.get_goal(goal.goal_id).objective == "persist goal"


def test_goal_create_waits_for_plan_approval_by_default() -> None:
    goal, plan = GoalLoopService().create(
        GoalCreateRequest(objective="ship loop engineering"),
        tenant_id="tenant-a",
        user_id="user-a",
    )

    assert plan.status == PlanModeStatus.WAITING_APPROVAL
    assert goal.status == GoalStatus.WAITING_APPROVAL
    assert goal.stop_reason == GoalStopReason.PLAN_APPROVAL_REQUIRED
    assert goal.plan_id == plan.plan_id


def test_goal_advance_plan_only_blocks_until_approved() -> None:
    service = GoalLoopService()
    goal, plan = service.create(
        GoalCreateRequest(objective="ship loop engineering"),
        tenant_id="tenant-a",
        user_id="user-a",
    )

    advanced = service.advance_without_execution(goal, plan)

    assert advanced.status == GoalStatus.WAITING_APPROVAL
    assert advanced.stop_reason == GoalStopReason.PLAN_APPROVAL_REQUIRED
    assert not advanced.iterations


def test_goal_advance_plan_only_adds_next_iteration_after_approval() -> None:
    service = GoalLoopService()
    goal, plan = service.create(
        GoalCreateRequest(objective="ship loop engineering"),
        tenant_id="tenant-a",
        user_id="user-a",
    )
    plan.status = PlanModeStatus.APPROVED

    advanced = service.advance_without_execution(goal, plan, user_feedback="continue")

    assert advanced.status == GoalStatus.ACTIVE
    assert advanced.stop_reason == GoalStopReason.NONE
    assert len(advanced.iterations) == 1
    assert advanced.iterations[0].status == "planned"
    assert "iteration 1" in advanced.iterations[0].task


def test_goal_advance_stops_when_iteration_budget_is_exhausted() -> None:
    service = GoalLoopService()
    goal, plan = service.create(
        GoalCreateRequest(
            objective="ship loop engineering",
            policy=GoalLoopPolicy(require_plan_approval=False, max_iterations=1),
        ),
        tenant_id="tenant-a",
        user_id="user-a",
    )

    first = service.advance_without_execution(goal, plan)
    second = service.advance_without_execution(first, plan)

    assert len(second.iterations) == 1
    assert second.status == GoalStatus.BLOCKED
    assert second.stop_reason == GoalStopReason.MAX_ITERATIONS_REACHED


def test_goal_advance_stops_when_token_budget_is_exhausted() -> None:
    service = GoalLoopService()
    goal, plan = service.create(
        GoalCreateRequest(
            objective="ship loop engineering",
            policy=GoalLoopPolicy(
                require_plan_approval=False,
                max_iterations=5,
                token_budget=1,
            ),
        ),
        tenant_id="tenant-a",
        user_id="user-a",
    )

    stopped = service.advance_without_execution(goal, plan)

    assert stopped.status == GoalStatus.BLOCKED
    assert stopped.stop_reason == GoalStopReason.BUDGET_EXHAUSTED
