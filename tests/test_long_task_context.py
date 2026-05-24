from __future__ import annotations

from backend.app.core.agent import AgentTrajectory


def test_long_task_context_retains_subtasks_and_observations() -> None:
    trajectory = AgentTrajectory(task="t", goal="g")
    trajectory.subtasks = ["understand request", "locate relevant files", "verify results"]
    trajectory.subtask_status = {"understand request": "done", "locate relevant files": "pending"}
    trajectory.observations.extend(["obs1", "obs2", "obs3"])
    trajectory.reflections.extend(["ref1", "ref2"])

    assert trajectory.subtasks[0] == "understand request"
    assert len(trajectory.observations) == 3
    assert len(trajectory.reflections) == 2
    assert trajectory.subtask_status["understand request"] == "done"
