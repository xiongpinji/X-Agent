"""
Task planning engine - handles task decomposition and plan generation.

Extracted from AgentLoop to reduce coupling and improve testability.
Responsibilities:
  - Decompose tasks into subtasks
  - Analyze task characteristics
  - Generate execution plans
  - Prioritize tools based on context
"""

from typing import Any
import json

from backend.app.core.contracts import RunContext
from backend.app.core.llm import LLMRouter
from backend.app.core.agent.protocols import PlanStep, TaskProfile


class TaskPlanner:
    """Plans task execution and decomposes complex tasks."""

    def __init__(
        self,
        llm_router: LLMRouter,
        tool_registry: Any,  # ToolRegistry
    ):
        self.llm = llm_router
        self.tools = tool_registry

    async def plan(
        self,
        context: RunContext,
        task: str,
        goal: str,
        extra_context: dict[str, Any],
    ) -> list[PlanStep]:
        """
        Generate execution plan from task description.

        Args:
            context: Execution context
            task: Task description
            goal: Derived goal
            extra_context: Additional context

        Returns:
            List of plan steps
        """
        tool_manifest = self.tools.manifest()
        related_tools = self.tools.related_tools(f"{task} {goal}")

        task_profile = self.analyze_task(task, extra_context)
        tool_profile = self._build_tool_profile(task_profile, related_tools)

        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._build_user_prompt(
                task, goal, task_profile, tool_profile, related_tools, extra_context
            )},
        ]

        response = await self.llm.chat(messages, self.tools.definitions_for_llm())
        plan_text = response.content or ""

        if response.tool_calls:
            steps = self._parse_tool_calls(response.tool_calls)
        else:
            steps = self._parse_plan_text(plan_text, tool_manifest)

        if not steps:
            steps = self._fallback_plan(task_profile, tool_profile, related_tools, extra_context)

        steps = self._deduplicate_steps(steps)
        steps = self._limit_steps(steps, max_steps=4)

        return steps

    def decompose(
        self,
        task: str,
        extra_context: dict[str, Any],
    ) -> list[str]:
        """
        Break task into logical subtasks.

        Args:
            task: Task description
            extra_context: Additional context

        Returns:
            List of subtask descriptions
        """
        text = f"{task}\n{json.dumps(extra_context, ensure_ascii=False, default=str)}".lower()

        cues = [
            ("understand request", ["analyze", "understand", "inspect", "review", "explain", "summarize"]),
            ("locate relevant files", ["find", "search", "locate", "where", "discover"]),
            ("draft implementation plan", ["plan", "design", "approach", "strategy"]),
            ("apply modification", ["modify", "edit", "patch", "fix", "update", "refactor", "implement", "change", "write"]),
            ("verify results", ["verify", "check", "validate", "test", "confirm"]),
            ("summarize completion", ["summary", "report", "wrap up", "finalize"]),
        ]

        subtasks: list[str] = []
        for label, keywords in cues:
            if any(keyword in text for keyword in keywords):
                subtasks.append(label)

        if not subtasks:
            subtasks = ["understand request", "complete task", "verify output"]

        return list(dict.fromkeys(subtasks[:5]))

    def analyze_task(
        self,
        task: str,
        extra_context: dict[str, Any],
    ) -> TaskProfile:
        """
        Analyze task characteristics.

        Args:
            task: Task description
            extra_context: Additional context

        Returns:
            TaskProfile with analysis results
        """
        text = f"{task} {json.dumps(extra_context, ensure_ascii=False, default=str)}".lower()

        # Infer mode
        mode = self._infer_mode(task, extra_context)

        # Infer intent
        intent = self._infer_intent(text)

        # Extract constraints
        constraints = self._extract_constraints(extra_context)

        # Build focus areas
        focus = self._build_focus(mode, extra_context)

        # Calculate complexity
        complexity = min(1.0, 0.25 + 0.12 * len(self.decompose(task, extra_context)))

        # Calculate urgency
        urgency = 0.7 if any(token in text for token in ["urgent", "asap", "now", "immediately", "blocking"]) else 0.4

        return TaskProfile(
            mode=mode,
            intent=intent,
            complexity=round(complexity, 2),
            urgency=round(urgency, 2),
            constraints=constraints,
            focus=focus,
        )

    def _infer_mode(self, task: str, extra_context: dict[str, Any]) -> str:
        """Infer task mode from description."""
        text = f"{task} {json.dumps(extra_context, ensure_ascii=False, default=str)}".lower()

        if any(token in text for token in ["write", "modify", "edit", "patch", "fix", "implement", "refactor", "update", "create"]):
            return "edit"
        if any(token in text for token in ["search", "inspect", "analyze", "impact", "dependency", "entrypoint", "trace"]):
            return "analyze"
        if any(token in text for token in ["summarize", "summary", "explain", "overview", "report"]):
            return "summarize"
        if any(token in text for token in ["file", "code", "repo", "tree", "directory", "folder"]):
            return "search"
        return "general"

    def _infer_intent(self, text: str) -> str:
        """Infer task intent from text."""
        if any(token in text for token in ["fix", "patch", "edit", "write", "implement", "refactor", "update"]):
            return "code_change"
        if any(token in text for token in ["analyze", "inspect", "review", "understand", "explain"]):
            return "analysis"
        if any(token in text for token in ["summarize", "report", "overview", "wrap up"]):
            return "summary"
        if any(token in text for token in ["search", "locate", "find", "discover"]):
            return "discovery"
        if any(token in text for token in ["browser", "desktop", "ui", "page", "click", "fill", "screenshot"]):
            return "automation"
        return "general"

    def _extract_constraints(self, extra_context: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract task constraints from context."""
        constraints = []
        for key in ["root", "path", "target_path", "file", "pattern", "limit", "read_limit", "replace_all"]:
            value = extra_context.get(key)
            if value not in (None, "", [], {}):
                constraints.append({key: value})
        return constraints

    def _build_focus(self, mode: str, extra_context: dict[str, Any]) -> list[str]:
        """Build focus areas for task."""
        focus = []
        if mode in {"edit", "analyze", "summarize", "search"}:
            focus.append(mode)
        return list(dict.fromkeys(focus))[:5]

    def _build_tool_profile(self, task_profile: TaskProfile, related_tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Build tool selection profile."""
        tool_names = [str(tool.get("name", "")) for tool in related_tools[:8]]
        preferred = tool_names[0] if tool_names else None

        confidence = 0.35
        if task_profile.intent != "general":
            confidence += 0.2
        if task_profile.mode in {"edit", "analyze", "search", "summarize"}:
            confidence += 0.2
        if preferred:
            confidence += 0.15
        if len(tool_names) > 3:
            confidence += 0.1

        confidence = min(confidence, 1.0)

        return {
            "preferred_tool": preferred,
            "alternatives": [name for name in tool_names if name != preferred][:4],
            "task_mode": task_profile.mode,
            "intent": task_profile.intent,
            "confidence": round(confidence, 2),
        }

    def _parse_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[PlanStep]:
        """Parse tool calls from LLM response."""
        steps = []
        for call in tool_calls:
            steps.append(PlanStep(
                kind="tool",
                instruction=f"Use {call.get('name', 'tool')}",
                tool_name=str(call.get("name", "")),
                arguments=call.get("arguments", {}) if isinstance(call.get("arguments", {}), dict) else {},
            ))
        steps.append(PlanStep(kind="final", instruction="Finalize answer"))
        return steps

    def _parse_plan_text(self, plan_text: str, tool_manifest: list[dict[str, Any]]) -> list[PlanStep]:
        """Parse plan from text response."""
        text = plan_text.strip()
        if not text:
            return []

        # Try JSON parsing
        if text.startswith("{") or text.startswith("["):
            try:
                payload = json.loads(text)
                if isinstance(payload, list):
                    return [self._step_from_dict(item) for item in payload if isinstance(item, dict)]
                if isinstance(payload, dict):
                    steps = payload.get("steps")
                    if isinstance(steps, list):
                        return [self._step_from_dict(item) for item in steps if isinstance(item, dict)]
            except Exception:
                pass

        # Parse line by line
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        steps = []
        for line in lines:
            lowered = line.lower()
            if lowered.startswith("observe"):
                steps.append(PlanStep(kind="observe", instruction=line))
            elif lowered.startswith("tool:"):
                name = line.split(":", 1)[1].strip().split()[0]
                steps.append(PlanStep(kind="tool", instruction=line, tool_name=name, arguments={}))
            elif lowered.startswith("reflect"):
                steps.append(PlanStep(kind="reflect", instruction=line))
            elif lowered.startswith("final"):
                steps.append(PlanStep(kind="final", instruction=line))

        return steps

    def _fallback_plan(
        self,
        task_profile: TaskProfile,
        tool_profile: dict[str, Any],
        related_tools: list[dict[str, Any]],
        extra_context: dict[str, Any],
    ) -> list[PlanStep]:
        """Generate fallback plan when LLM fails."""
        steps = []

        # Start with observation
        steps.append(PlanStep(
            kind="observe",
            instruction=f"Observe context for {task_profile.intent}",
        ))

        # Add tool step if confident
        if tool_profile.get("preferred_tool"):
            steps.append(PlanStep(
                kind="tool",
                instruction=f"Use {tool_profile['preferred_tool']}",
                tool_name=tool_profile["preferred_tool"],
                arguments={},
            ))

        # Add reflection if needed
        if task_profile.complexity > 0.7:
            steps.append(PlanStep(
                kind="reflect",
                instruction="Reflect on progress",
            ))

        # Finalize
        steps.append(PlanStep(kind="final", instruction="Finalize answer"))

        return steps

    def _deduplicate_steps(self, steps: list[PlanStep]) -> list[PlanStep]:
        """Remove duplicate steps."""
        seen = set()
        deduped = []
        for step in steps:
            signature = (step.kind, step.tool_name, step.instruction.strip().lower())
            if signature not in seen:
                seen.add(signature)
                deduped.append(step)
        return deduped

    def _limit_steps(self, steps: list[PlanStep], max_steps: int = 4) -> list[PlanStep]:
        """Limit plan to maximum steps."""
        if len(steps) > max_steps:
            steps = steps[:max_steps]
            if steps and steps[-1].kind != "final":
                steps[-1] = PlanStep(kind="final", instruction="Finalize answer")
        return steps

    def _step_from_dict(self, data: dict[str, Any]) -> PlanStep:
        """Convert dict to PlanStep."""
        return PlanStep(
            kind=str(data.get("kind") or data.get("type") or "final"),
            instruction=str(data.get("instruction") or data.get("content") or ""),
            tool_name=str(data["tool_name"]) if data.get("tool_name") else None,
            arguments=dict(data.get("arguments") or {}),
        )

    def _system_prompt(self) -> str:
        """Get system prompt for planning."""
        return (
            "You are X-Agent, a coding and operations agent. "
            "First classify the task mode, then produce a compact execution plan with observe/tool/reflect/final steps. "
            "Preserve the main objective, avoid redundant steps, and adapt when failures occur. "
            "Prefer tools when needed, and finish with a concise final step."
        )

    def _build_user_prompt(
        self,
        task: str,
        goal: str,
        task_profile: TaskProfile,
        tool_profile: dict[str, Any],
        related_tools: list[dict[str, Any]],
        extra_context: dict[str, Any],
    ) -> str:
        """Build user prompt for planning."""
        return "\n".join([
            f"Task: {task}",
            f"Goal: {goal}",
            f"Mode: {task_profile.mode}",
            f"Intent: {task_profile.intent}",
            f"Complexity: {task_profile.complexity}",
            f"Urgency: {task_profile.urgency}",
            f"Preferred tool: {tool_profile.get('preferred_tool')}",
            f"Available tools: {json.dumps([t.get('name') for t in related_tools[:5]], ensure_ascii=False)}",
            "Output a short plan using steps with kind observe/tool/reflect/final.",
        ])
