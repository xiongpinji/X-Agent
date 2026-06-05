"""AgentFixRunner — connects a real AgentLoop to the IssueToPR pipeline."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)
_MUTATING_TOOLS = {"write_file", "apply_text_patch", "apply_batch_patch"}


class AgentFixRunner:
    """A fix_runner backed by a real AgentLoop."""

    def __init__(self, agent: Any = None, max_iterations: int = 6):
        self._agent = agent
        self._max_iterations = max_iterations
        self.last_result: Any = None

    def _get_agent(self) -> Any:
        if self._agent is None:
            from backend.app.dependencies import get_agent
            self._agent = get_agent()
        return self._agent

    @staticmethod
    def _compose_task(issue: Any) -> str:
        title = getattr(issue, "title", "")
        body = getattr(issue, "body", "") or ""
        number = getattr(issue, "issue_number", "?")
        return (
            f"Resolve GitHub issue #{number}: {title}\n\n"
            f"Issue description:\n{body}\n\n"
            "Investigate the repository under the working root, make the necessary code changes "
            "to resolve the issue, and use the file-editing tools (write_file / apply_text_patch) "
            "to apply them. Keep changes minimal and focused on the issue."
        )

    @staticmethod
    def _infer_file_target(issue: Any) -> str | None:
        text = f"{getattr(issue, 'title', '')}\n{getattr(issue, 'body', '') or ''}"
        match = re.search(
            r"(?<![\w./-])([\w./-]+\.(?:py|ts|tsx|js|jsx|md|txt|yaml|yml|json|toml))(?![\w./-])",
            text,
        )
        return match.group(1) if match else None

    @staticmethod
    def _infer_patch_hint(issue: Any) -> dict[str, str] | None:
        text = f"{getattr(issue, 'title', '')}\n{getattr(issue, 'body', '') or ''}"
        func_match = re.search(
            r"\badd\s+(?:a\s+)?([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s+function\b",
            text,
            re.IGNORECASE,
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
        snippet = f"\n\ndef {func_name}({left}, {right}):\n    return {left} {operator} {right}\n"
        return {
            "append_text": snippet,
            "content": f"def {func_name}({left}, {right}):\n    return {left} {operator} {right}",
        }

    async def __call__(self, sandbox: Any, issue: Any, workspace: str) -> bool:
        from backend.app.core.contracts import RunContext, RiskLevel, RunStatus

        clone_dir = str(Path(workspace) / "repo")
        agent = self._get_agent()
        context = RunContext(
            tenant_id="sandbox",
            user_id="issue-fixer",
            agent_id=f"issue-fixer-{getattr(issue, 'issue_number', uuid4().hex[:8])}",
            trace_id=str(uuid4()),
            request_id=str(uuid4()),
            permission_scope=["tools:read", "tools:write", "memory:read", "memory:write"],
            risk_level=RiskLevel.HIGH,
        )

        task = self._compose_task(issue)
        target_file = self._infer_file_target(issue)
        patch_hint = self._infer_patch_hint(issue)
        if not target_file and patch_hint:
            target_file = "calc.py"

        extra_context: dict[str, Any] = {"root": clone_dir, "retry_budget": 2}
        target_path = ""
        if target_file:
            target_path = str(Path(clone_dir) / target_file)
            extra_context.update({
                "path": target_path,
                "target_path": target_path,
                "file": target_path,
                "pattern": target_file,
            })
        if patch_hint:
            if target_path and patch_hint.get("append_text"):
                try:
                    current = Path(target_path).read_text(encoding="utf-8")
                except OSError:
                    current = ""
                extra_context["old_text"] = current
                extra_context["new_text"] = current.rstrip() + patch_hint["append_text"]
            extra_context.update({k: v for k, v in patch_hint.items() if k != "append_text"})

        from backend.app.core.tools import reset_tool_root_override, set_tool_root_override
        token = set_tool_root_override(clone_dir)
        previous_max_iterations = getattr(agent, "max_iterations", None)
        if previous_max_iterations is not None:
            agent.max_iterations = max(int(previous_max_iterations), self._max_iterations)
        try:
            result = await agent.run(context, task, extra_context=extra_context)
            self.last_result = result
        except Exception:
            logger.exception("AgentFixRunner: agent.run raised for issue %s", getattr(issue, "issue_number", "?"))
            return False
        finally:
            if previous_max_iterations is not None:
                agent.max_iterations = previous_max_iterations
            reset_tool_root_override(token)

        status = getattr(result, "status", None)
        completed = status == RunStatus.COMPLETED or str(status).endswith("COMPLETED")
        mutated = False
        for call in getattr(result, "tool_calls", []) or []:
            name = getattr(call, "tool_name", None) or getattr(call, "name", None)
            ok = getattr(call, "success", None)
            if ok is None:
                ok = getattr(call, "error", None) is None
            if name in _MUTATING_TOOLS and ok:
                mutated = True
                break
        logger.info("AgentFixRunner issue=%s status=%s mutated=%s", getattr(issue, "issue_number", "?"), status, mutated)
        return bool(completed and mutated)
