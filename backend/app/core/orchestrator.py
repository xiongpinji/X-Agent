from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.core.contracts import ExecutionFrame, PlanFrame, RecoveryFrame, TaskFrame, ToolDecision


@dataclass
class CapabilityDecision:
    name: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationContext:
    task: TaskFrame
    plan: PlanFrame | None = None
    execution: ExecutionFrame | None = None
    recovery: RecoveryFrame | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityRouter:
    def route(self, context: OrchestrationContext) -> CapabilityDecision:
        metadata = context.metadata
        workflow = metadata.get("workflow", {}) if isinstance(metadata.get("workflow"), dict) else {}
        approval = metadata.get("approval", {}) if isinstance(metadata.get("approval"), dict) else {}
        browser = metadata.get("browser", {}) if isinstance(metadata.get("browser"), dict) else {}
        desktop = metadata.get("desktop", {}) if isinstance(metadata.get("desktop"), dict) else {}
        task_text = f"{context.task.goal} {context.task.description} {metadata.get('task', '')}".lower()

        if approval.get("pending_count", 0) or context.task.requires_approval:
            return CapabilityDecision(name="approval", reason="approval boundary detected", metadata={"approval": approval, "workflow": workflow, "browser": browser, "desktop": desktop})
        if browser.get("active_count", 0) or "browser" in task_text:
            return CapabilityDecision(name="browser", reason="browser context detected", metadata={"browser": browser, "workflow": workflow, "approval": approval, "desktop": desktop})
        if desktop.get("active_count", 0) or "desktop" in task_text:
            return CapabilityDecision(name="desktop", reason="desktop context detected", metadata={"desktop": desktop, "workflow": workflow, "approval": approval, "browser": browser})
        if workflow:
            return CapabilityDecision(name="workflow", reason="workflow context detected", metadata={"workflow": workflow, "approval": approval, "browser": browser, "desktop": desktop})
        if any(token in task_text for token in ["memory", "remember", "recall"]):
            return CapabilityDecision(name="memory", reason="memory intent detected", metadata={"memory": metadata.get("memory", {}), "workflow": workflow, "approval": approval, "browser": browser, "desktop": desktop})
        if any(token in task_text for token in ["trace", "audit", "observe", "report"]):
            return CapabilityDecision(name="observe", reason="observability intent detected", metadata={"trace": metadata.get("trace", {}), "workflow": workflow, "approval": approval, "browser": browser, "desktop": desktop})
        return CapabilityDecision(name="agent", reason="default agent execution", metadata={"task": context.task.model_dump(mode="json")})


class ContextHub:
    def build(self, task: TaskFrame, execution: ExecutionFrame | None = None, *, metadata: dict[str, Any] | None = None) -> OrchestrationContext:
        return OrchestrationContext(
            task=task,
            plan=execution.plan if execution else None,
            execution=execution,
            recovery=execution.recovery_hint if execution else None,
            metadata=metadata or {},
        )


class PlanningEngine:
    def draft(self, context: OrchestrationContext) -> PlanFrame:
        text = f"{context.task.goal} {context.task.description} {context.metadata.get('task', '')}".lower()
        steps: list[str] = ["understand request", "verify result"]
        dependencies: list[str] = []
        verification_steps: list[str] = ["run targeted validation"]
        rollback_steps: list[str] = ["revert the last file change if verification fails"]
        risks: list[str] = []

        if any(token in text for token in ["fix", "patch", "edit", "write", "implement", "refactor", "update", "change"]):
            steps = ["inspect relevant files", "apply precise modification", "verify change"]
            dependencies.append("repository context")
            verification_steps.extend(["run impacted tests", "inspect diff for unintended changes"])
            rollback_steps.append("restore from backup or reverse patch")
            risks.append("code change may affect related tests")
        elif any(token in text for token in ["search", "find", "locate", "discover", "where"]):
            steps = ["scan repository", "rank relevant files", "summarize findings"]
            dependencies.append("repository index")
            verification_steps.append("check relevance against task goal")
        elif any(token in text for token in ["test", "verify", "validate", "check"]):
            steps = ["identify verification target", "run validation", "summarize outcome"]
            dependencies.append("execution environment")
            verification_steps.append("collect failure traces")
        elif any(token in text for token in ["summarize", "report", "explain", "overview"]):
            steps = ["collect evidence", "summarize key points", "deliver concise report"]
            verification_steps.append("ensure summary covers requested scope")

        if context.task.requires_approval:
            risks.append("approval required before risky actions")
            dependencies.append("approval gate")

        if context.execution and isinstance(context.execution.metadata, dict):
            if context.execution.metadata.get("session_id"):
                dependencies.append("resume session state")

        return PlanFrame(
            goal=context.task.goal,
            steps=steps[:5],
            dependencies=list(dict.fromkeys(dependencies))[:5],
            risks=list(dict.fromkeys(risks))[:5],
            verification_steps=verification_steps[:5],
            rollback_steps=rollback_steps[:5],
            status="draft",
            revision=1,
        )


class ToolSelectionEngine:
    def choose(self, context: OrchestrationContext) -> ToolDecision:
        text = f"{context.task.goal} {context.task.description} {context.metadata.get('task', '')}".lower()
        if any(token in text for token in ["fix", "patch", "edit", "write", "implement", "refactor", "update", "change"]):
            return ToolDecision(tool_name="read_file", reason="inspect code before editing", expected_output="file contents")
        if any(token in text for token in ["search", "find", "locate", "discover", "where"]):
            return ToolDecision(tool_name="search_text", reason="locate relevant files", expected_output="matching file paths")
        if any(token in text for token in ["test", "verify", "validate", "check"]):
            return ToolDecision(tool_name="run_tests", reason="validate the current state", expected_output="test results")
        if any(token in text for token in ["summarize", "report", "explain", "overview"]):
            return ToolDecision(tool_name="summarize_text", reason="produce a concise summary", expected_output="summary text")
        if context.plan and context.plan.steps:
            return ToolDecision(tool_name="observe", reason="follow the drafted plan", expected_output="observations")
        return ToolDecision(tool_name="observe", reason="default to observation before action", expected_output="context snapshot")


class RecoveryEngine:
    def decide(self, context: OrchestrationContext) -> RecoveryFrame:
        execution = context.execution
        if execution is None:
            return context.recovery or RecoveryFrame(branch="continue")
        summary = execution.execution_summary if isinstance(execution.execution_summary, dict) else {}
        branch = str(summary.get("branch", execution.recovery_hint.branch if execution.recovery_hint else "continue"))
        reason = summary.get("reason") if isinstance(summary.get("reason"), str) else None
        next_action = summary.get("next_action") if isinstance(summary.get("next_action"), str) else None
        return RecoveryFrame(
            branch=branch,
            reason=reason,
            error_type=str(summary.get("error")) if summary.get("error") else None,
            approval_id=execution.approval_state.get("approval_id") if isinstance(execution.approval_state, dict) else None,
            next_action=next_action,
        )


class Orchestrator:
    def __init__(self, *, router: CapabilityRouter | None = None, context_hub: ContextHub | None = None, recovery_engine: RecoveryEngine | None = None, planning_engine: PlanningEngine | None = None, tool_selection_engine: ToolSelectionEngine | None = None) -> None:
        self.router = router or CapabilityRouter()
        self.context_hub = context_hub or ContextHub()
        self.recovery_engine = recovery_engine or RecoveryEngine()
        self.planning_engine = planning_engine or PlanningEngine()
        self.tool_selection_engine = tool_selection_engine or ToolSelectionEngine()

    def prepare(self, task: TaskFrame, execution: ExecutionFrame | None = None, *, metadata: dict[str, Any] | None = None) -> tuple[OrchestrationContext, CapabilityDecision, RecoveryFrame]:
        context = self.context_hub.build(task, execution, metadata=metadata)
        decision = self.router.route(context)
        recovery = self.recovery_engine.decide(context)
        return context, decision, recovery

    def draft_plan(self, task: TaskFrame, execution: ExecutionFrame | None = None, *, metadata: dict[str, Any] | None = None) -> PlanFrame:
        context = self.context_hub.build(task, execution, metadata=metadata)
        return self.planning_engine.draft(context)

    def select_tool(self, task: TaskFrame, execution: ExecutionFrame | None = None, *, metadata: dict[str, Any] | None = None) -> ToolDecision:
        context = self.context_hub.build(task, execution, metadata=metadata)
        return self.tool_selection_engine.choose(context)
