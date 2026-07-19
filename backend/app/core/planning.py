from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.core.contracts import TaskFrame


@dataclass
class PlanStep:
    kind: str
    instruction: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskPlan:
    task_id: str
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    verification_steps: list[str] = field(default_factory=list)
    rollback_steps: list[str] = field(default_factory=list)
    status: str = "draft"
    revision: int = 0


class PlanningEngine:
    """Build a compact execution plan from task intent and execution context."""

    def build(self, task: TaskFrame, metadata: dict[str, Any] | None = None) -> TaskPlan:
        metadata = metadata or {}
        task_text = f"{task.goal} {task.description} {metadata.get('task', '')}".lower()
        steps: list[PlanStep] = [PlanStep(kind="observe", instruction="Inspect task context")]

        if any(token in task_text for token in ["fix", "patch", "edit", "write", "implement", "refactor", "update"]):
            steps.append(PlanStep(kind="tool", instruction="Read relevant file(s)", tool_name="read_file", arguments={"path": str(metadata.get("path") or metadata.get("target_path") or ""), "limit": int(metadata.get("read_limit", 8000))}))
        if any(token in task_text for token in ["search", "find", "locate", "discover", "analyze", "inspect"]):
            steps.append(PlanStep(kind="tool", instruction="Inspect repository or evidence", tool_name="search_text", arguments={"root": str(metadata.get("root") or "."), "query": task.goal, "pattern": str(metadata.get("pattern") or "**/*"), "limit": int(metadata.get("limit", 20))}))
        if any(token in task_text for token in ["test", "verify", "validate", "check", "confirm"]):
            steps.append(PlanStep(kind="tool", instruction="Run validation", tool_name="run_tests", arguments={"root": str(metadata.get("root") or "."), "target": str(metadata.get("path") or metadata.get("target_path") or "")}))

        if any(token in task_text for token in ["browser", "desktop", "ui", "page", "click", "fill"]):
            steps.append(PlanStep(kind="tool", instruction="Use automation tool", tool_name="browser", arguments={"goal": task.goal}))

        if any(token in task_text for token in ["memory", "remember", "recall", "history"]):
            steps.append(PlanStep(kind="tool", instruction="Recall relevant memory", tool_name="memory_search", arguments={"query": task.goal}))

        steps.append(PlanStep(kind="reflect", instruction="Review progress and adjust"))
        steps.append(PlanStep(kind="final", instruction="Finalize answer"))

        verification_steps = ["re-read changed files", "run targeted tests", "confirm expected output"]
        rollback_steps = ["restore backup", "revert last patch", "summarize failure"]
        risks = []
        if task.requires_approval:
            risks.append("approval boundary")
        if task.risk_level.value in {"high", "critical"}:
            risks.append("high risk change")

        return TaskPlan(
            task_id=task.task_id,
            goal=task.goal,
            steps=steps,
            risks=risks,
            verification_steps=verification_steps,
            rollback_steps=rollback_steps,
        )
