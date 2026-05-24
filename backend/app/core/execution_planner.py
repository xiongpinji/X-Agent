from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.core.test_mapper import TestMappingResult


@dataclass
class ExecutionPlan:
    steps: list[str] = field(default_factory=list)
    verification_steps: list[str] = field(default_factory=list)
    suggested_test_commands: list[str] = field(default_factory=list)
    rollback_steps: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionPlanner:
    """Build a simple execution plan that includes verification commands."""

    def build(self, task: str, test_mapping: TestMappingResult | None = None) -> ExecutionPlan:
        steps = ["understand request", "inspect relevant files", "apply change", "verify result"]
        verification_steps = ["run targeted checks"]
        suggested_test_commands = []
        rollback_steps = ["revert the last patch if verification fails"]
        risk_notes = ["confirm the change scope before editing"]
        next_actions = ["identify entrypoints", "locate related tests", "prepare the smallest patch"]
        if test_mapping is not None:
            steps.insert(2, "review impacted tests")
            verification_steps = [f"review {len(test_mapping.test_files)} mapped tests", "run selected tests", "inspect failure output"]
            suggested_test_commands = self._commands_from_mapping(test_mapping)
            if test_mapping.dependency_hints:
                risk_notes.append(f"{len(test_mapping.dependency_hints)} dependency hints identified")
            if test_mapping.impact_hints:
                risk_notes.append(f"{len(test_mapping.impact_hints)} impact hints identified")
            if test_mapping.related_files:
                next_actions.insert(0, f"prioritize {test_mapping.related_files[0].get('path', 'related files')}")
            rollback_steps.append("restore the previous implementation if the fix regresses tests")
        return ExecutionPlan(
            steps=steps,
            verification_steps=verification_steps,
            suggested_test_commands=suggested_test_commands,
            rollback_steps=rollback_steps,
            risk_notes=risk_notes,
            next_actions=next_actions,
            metadata={
                "task": task,
                "test_mapping": test_mapping.query if test_mapping else None,
                "recommended_commands": test_mapping.recommended_commands if test_mapping else [],
                "related_file_count": len(test_mapping.related_files) if test_mapping else 0,
                "dependency_hint_count": len(test_mapping.dependency_hints) if test_mapping else 0,
            },
        )

    @staticmethod
    def _commands_from_mapping(test_mapping: TestMappingResult) -> list[str]:
        commands = list(test_mapping.recommended_commands)
        for item in test_mapping.test_files[:5]:
            path = str(item.get("path", "")).strip()
            if not path:
                continue
            if path.endswith(".py"):
                commands.append(f"pytest {path}")
            elif path.endswith((".ts", ".tsx", ".js", ".jsx")):
                commands.append(f"npm test -- {path}")
            else:
                commands.append(path)
        return list(dict.fromkeys(commands))


execution_planner = ExecutionPlanner()
