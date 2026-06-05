"""AgentFixRunner — connects a real AgentLoop to the IssueToPR pipeline.

The IssueToPR pipeline takes a `fix_runner(sandbox, issue, workspace) -> bool`
callable. This module provides a runner backed by an actual AgentLoop: it
composes a task from the GitHub issue, runs the agent pointed at the cloned
repo, and reports whether the agent produced file changes.

Design:
- Lazy agent: built via dependencies.get_agent() on first use unless one is
  injected (tests inject a fake). Keeps the heavy LLM/memory wiring out of
  import time.
- Workspace targeting: the cloned repo lives at <workspace>/repo. We pass it
  to the agent via extra_context["root"] so the file tools operate there.
- Success = agent COMPLETED and at least one file-mutating tool call
  (write_file / apply_text_patch / apply_batch_patch) succeeded. We do NOT
  trust the agent's prose; we check actual tool effects. The pipeline then
  independently re-checks `git has_changes`, so a false positive here still
  can't open an empty PR.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# Tool names that indicate the agent actually mutated files.
_MUTATING_TOOLS = {"write_file", "apply_text_patch", "apply_batch_patch"}


class AgentFixRunner:
    """A fix_runner backed by a real AgentLoop.

    Usage:
        runner = AgentFixRunner()
        pipeline = IssueToPRPipeline(github, runner, config)

    The instance is callable with the FixRunner signature
    (sandbox, issue, workspace) -> bool.
    """

    def __init__(self, agent: Any = None, max_iterations: int = 6):
        self._agent = agent
        self._max_iterations = max_iterations
        self.last_result: Any = None

    def _get_agent(self) -> Any:
        if self._agent is None:
            # Lazy import to avoid pulling the whole dependency graph at import.
            from backend.app.dependencies import get_agent

            self._agent = get_agent()
        return self._agent

    @staticmethod
    def _compose_task(issue: Any) -> str:
        """Build an agent task prompt from the issue. Kept explicit so the
        agent gets the title + body + a clear instruction to edit files."""
        title = getattr(issue, "title", "")
        body = getattr(issue, "body", "") or ""
        number = getattr(issue, "issue_number", "?")
        return (
            f"Resolve GitHub issue #{number}: {title}\n\n"
            f"Issue description:\n{body}\n\n"
            "Investigate the repository under the working root, make the "
            "necessary code changes to resolve the issue, and use the "
            "file-editing tools (write_file / apply_text_patch) to apply them. "
            "Keep changes minimal and focused on the issue."
        )

    @staticmethod
    def _infer_file_target(issue: Any) -> str | None:
        """Infer an explicit target file from a GitHub issue, if one is named."""
        text = f"{getattr(issue, 'title', '')}\n{getattr(issue, 'body', '') or ''}"
        match = re.search(
            r"(?<![\w./-])([\w./-]+\.(?:py|ts|tsx|js|jsx|md|txt|yaml|yml|json|toml))(?![\w./-])",
            text,
        )
        return match.group(1) if match else None

    @staticmethod
    def _infer_patch_hint(issue: Any) -> dict[str, str] | None:
        """Infer a small deterministic patch hint for simple function-add issues.

        The LLM still chooses and applies the tool; this only gives the planner a
        concrete path/content hint so real-LLM IssueToPR smoke tests do not spend
        the whole iteration budget on generic repository analysis.
        """
        text = f"{getattr(issue, 'title', '')}\n{getattr(issue, 'body', '') or ''}"
        func_match = re.search(
            r"\badd\s+(?:a\s+)?([A-Za-z_]\w*)\s+function\b", text, re.IGNORECASE
        )
        return_match = re.search(
            r"returns?\s+([A-Za-z_]\w*)\s*([-+*/])\s*([A-Za-z_]\w*)",
            text,
            re.IGNORECASE,
        )
        if not func_match or not return_match:
            return None
        func_name = func_match.group(1)
        left, operator, right = return_match.groups()
        return {
            "new_text": f"\n\ndef {func_name}({left}, {right}):\n    return {left} {operator} {right}\n",
            "content": f"def {func_name}({left}, {right}):\n    return {left} {operator} {right}",
        }

    async def __call__(self, sandbox: Any, issue: Any, workspace: str) -> bool:
        """Run the agent to fix the issue. Returns True if files were mutated.

        `workspace` is the sandbox-provisioned dir; the clone lives at
        <workspace>/repo (matching IssueToPRPipeline).
        """
        from backend.app.core.contracts import RunContext, RiskLevel, RunStatus

        clone_dir = str(Path(workspace) / "repo")
        agent = self._get_agent()

        context = RunContext(
            tenant_id="sandbox",
            user_id="issue-fixer",
            agent_id=f"issue-fixer-{getattr(issue, 'issue_number', uuid4().hex[:8])}",
            trace_id=str(uuid4()),
            request_id=str(uuid4()),
            permission_scope=[
                "tools:read",
                "tools:write",
                "memory:read",
                "memory:write",
            ],
            risk_level=RiskLevel.HIGH,  # file-mutating tools are HIGH risk
        )

        task = self._compose_task(issue)
        target_file = self._infer_file_target(issue)
        patch_hint = self._infer_patch_hint(issue)
        extra_context: dict[str, Any] = {"root": clone_dir, "retry_budget": 2}
        if target_file:
            target_path = str(Path(clone_dir) / target_file)
            extra_context.update(
                {
                    "path": target_path,
                    "target_path": target_path,
                    "file": target_path,
                    "pattern": target_file,
                }
            )
        if patch_hint:
            extra_context.update(patch_hint)

        # Point the file tools at the cloned repo for the duration of this run.
        # Without this, write_file/read_file resolve against PROJECT_ROOT and
        # reject the sandbox workspace ("Path must be within project directory").
        from backend.app.core.tools import (
            set_tool_root_override,
            reset_tool_root_override,
        )

        token = set_tool_root_override(clone_dir)
        previous_max_iterations = getattr(agent, "max_iterations", None)
        if previous_max_iterations is not None:
            agent.max_iterations = max(int(previous_max_iterations), self._max_iterations)
        try:
            result = await agent.run(
                context,
                task,
                extra_context=extra_context,
            )
            self.last_result = result
        except Exception:
            logger.exception(
                "AgentFixRunner: agent.run raised for issue %s",
                getattr(issue, "issue_number", "?"),
            )
            return False
        finally:
            if previous_max_iterations is not None:
                agent.max_iterations = previous_max_iterations
            reset_tool_root_override(token)

        # Did the agent complete?
        status = getattr(result, "status", None)
        completed = status == RunStatus.COMPLETED or str(status).endswith("COMPLETED")

        # Did it actually mutate files? Inspect tool_calls for successful
        # mutating tools rather than trusting the prose answer.
        mutated = False
        for call in getattr(result, "tool_calls", []) or []:
            name = getattr(call, "tool_name", None) or getattr(call, "name", None)
            ok = getattr(call, "success", None)
            if ok is None:
                # some records use status/error instead of success
                err = getattr(call, "error", None)
                ok = err is None
            if name in _MUTATING_TOOLS and ok:
                mutated = True
                break

        logger.info(
            "AgentFixRunner issue=%s status=%s mutated=%s",
            getattr(issue, "issue_number", "?"),
            status,
            mutated,
        )
        return bool(completed and mutated)
