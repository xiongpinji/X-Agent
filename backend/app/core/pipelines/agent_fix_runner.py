"""AgentFixRunner — connects a real AgentLoop to the IssueToPR pipeline."""

from __future__ import annotations

import base64
import json
import logging
import posixpath
import re
import shlex
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)
_MUTATING_TOOLS = {"write_file", "apply_text_patch", "apply_batch_patch"}

# --- P0-15: in-container file-tool execution -------------------------------
# DockerSandbox bind-mounts its workspace at this path inside the container.
_CONTAINER_WORKSPACE_ROOT = "/workspace"
# Keep every base64 chunk well below the ~128KiB single-argument exec limit.
_B64_CHUNK_SIZE = 48 * 1024
# Marker prefix so tool results can be parsed out of container stdout.
_RESULT_MARKER = "__XAGENT_TOOL_RESULT__"

# The following scripts run via `python -c` INSIDE the sandbox container.
# Payloads travel as base64 argv chunks so no shell quoting of user content
# is ever needed. The container image is python:3.11-slim (has `python`).
_PRE_WRITE_SCRIPT = (
    "import json,pathlib,sys\n"
    "p=pathlib.Path(sys.argv[1])\n"
    "previous=''\n"
    "if p.exists():\n"
    "    previous=p.read_text(encoding='utf-8',errors='ignore')\n"
    "    if sys.argv[2]=='1':\n"
    "        p.with_suffix(p.suffix+'.bak').write_text(previous,encoding='utf-8')\n"
    f"print('{_RESULT_MARKER}'+json.dumps({{'previous_size':len(previous)}}))\n"
)
_WRITE_CHUNK_SCRIPT = (
    "import base64,pathlib,sys\n"
    "p=pathlib.Path(sys.argv[1])\n"
    "p.parent.mkdir(parents=True,exist_ok=True)\n"
    "data=base64.b64decode(sys.argv[3].encode('ascii'))\n"
    "mode='wb' if sys.argv[2]=='1' else 'ab'\n"
    "with open(p,mode) as fh:\n"
    "    fh.write(data)\n"
)
_STAT_SCRIPT = (
    "import json,pathlib,sys\n"
    "p=pathlib.Path(sys.argv[1])\n"
    "current=p.read_text(encoding='utf-8',errors='ignore') if p.exists() else ''\n"
    f"print('{_RESULT_MARKER}'+json.dumps({{'current_size':len(current)}}))\n"
)
_PATCH_SCRIPT = (
    "import base64,json,pathlib,sys\n"
    "p=pathlib.Path(sys.argv[1])\n"
    "old=base64.b64decode(sys.argv[2].encode('ascii')).decode('utf-8')\n"
    "new=base64.b64decode(sys.argv[3].encode('ascii')).decode('utf-8')\n"
    "replace_all=sys.argv[4]=='1'\n"
    "backup=sys.argv[5]=='1'\n"
    "result={'path':str(p),'applied':False}\n"
    "if not p.exists() or not p.is_file():\n"
    "    result['error']='file_not_found'\n"
    "else:\n"
    "    original=p.read_text(encoding='utf-8',errors='ignore')\n"
    "    count=original.count(old)\n"
    "    if count==0:\n"
    "        result.update({'error':'pattern_not_found','match_count':0})\n"
    "    elif not replace_all and count>1:\n"
    "        result.update({'error':'ambiguous_match','match_count':count})\n"
    "    else:\n"
    "        updated=original.replace(old,new,-1 if replace_all else 1)\n"
    "        if backup:\n"
    "            p.with_suffix(p.suffix+'.bak').write_text(original,encoding='utf-8')\n"
    "        p.write_text(updated,encoding='utf-8')\n"
    "        verified=p.read_text(encoding='utf-8',errors='ignore')\n"
    "        result.update({'applied':True,'verified':verified==updated,'replace_all':replace_all,'match_count':count,'previous_size':len(original),'current_size':len(updated)})\n"
    f"print('{_RESULT_MARKER}'+json.dumps(result))\n"
)


class _ContainerFileTools:
    """In-container implementations of the mutating file tools (P0-15).

    Each method mirrors the semantics of the host-side tool in
    ``backend.app.core.tools`` but performs the actual file mutation inside
    the Docker sandbox via ``sandbox.run`` — no write touches the host
    filesystem. Paths supplied by the LLM (host absolute, container absolute,
    or clone-relative) are translated into the container namespace and
    strictly confined under /workspace.
    """

    def __init__(self, sandbox: Any, host_workspace: Path, container_clone_root: str):
        self._sandbox = sandbox
        self._host_workspace = Path(host_workspace).resolve()
        self._clone_root = container_clone_root

    def _to_container_path(self, path: str) -> str:
        raw = (path or "").strip().replace("\\", "/")
        if not raw:
            raise ValueError("path is required")
        if raw == _CONTAINER_WORKSPACE_ROOT or raw.startswith(_CONTAINER_WORKSPACE_ROOT + "/"):
            candidate = raw
        else:
            host_path = Path(raw)
            if host_path.is_absolute():
                resolved = host_path.resolve()
                try:
                    rel = resolved.relative_to(self._host_workspace)
                except ValueError:
                    raise PermissionError(f"path outside sandbox workspace: {path}")
                candidate = f"{_CONTAINER_WORKSPACE_ROOT}/{rel.as_posix()}"
            else:
                candidate = f"{self._clone_root}/{raw}"
        normalized = posixpath.normpath(candidate)
        if normalized != _CONTAINER_WORKSPACE_ROOT and not normalized.startswith(_CONTAINER_WORKSPACE_ROOT + "/"):
            raise PermissionError(f"path escapes sandbox workspace: {path}")
        return normalized

    async def _run_script(self, script: str, args: list[str]) -> Any:
        command = " ".join(["python", "-c", shlex.quote(script), *[shlex.quote(arg) for arg in args]])
        return await self._sandbox.run(command)

    @staticmethod
    def _parse_result(stdout: str) -> dict[str, Any]:
        for line in reversed((stdout or "").splitlines()):
            stripped = line.strip()
            if stripped.startswith(_RESULT_MARKER):
                return json.loads(stripped[len(_RESULT_MARKER):])
        raise RuntimeError("container script returned no result payload")

    @staticmethod
    def _run_error(run: Any) -> str:
        return str(getattr(run, "error", None) or getattr(run, "stderr", "") or "unknown container error")

    async def write_file(self, path: str, content: str, backup: bool = True) -> dict[str, Any]:
        cpath = self._to_container_path(path)
        encoded = base64.b64encode((content or "").encode("utf-8")).decode("ascii")
        chunks = [encoded[i:i + _B64_CHUNK_SIZE] for i in range(0, len(encoded), _B64_CHUNK_SIZE)] or [""]
        pre = await self._run_script(_PRE_WRITE_SCRIPT, [cpath, "1" if backup else "0"])
        if not getattr(pre, "success", False):
            raise RuntimeError(f"container pre-write failed for {cpath}: {self._run_error(pre)}")
        previous_size = int(self._parse_result(getattr(pre, "stdout", "")).get("previous_size", 0))
        for index, chunk in enumerate(chunks):
            run = await self._run_script(_WRITE_CHUNK_SCRIPT, [cpath, "1" if index == 0 else "0", chunk])
            if not getattr(run, "success", False):
                raise RuntimeError(f"container write failed for {cpath} (chunk {index}): {self._run_error(run)}")
        post = await self._run_script(_STAT_SCRIPT, [cpath])
        current_size = 0
        if getattr(post, "success", False):
            current_size = int(self._parse_result(getattr(post, "stdout", "")).get("current_size", 0))
        return {"path": cpath, "written": True, "previous_size": previous_size, "current_size": current_size}

    async def apply_text_patch(
        self,
        path: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
        backup: bool = True,
    ) -> dict[str, Any]:
        cpath = self._to_container_path(path)
        args = [
            cpath,
            base64.b64encode((old_text or "").encode("utf-8")).decode("ascii"),
            base64.b64encode((new_text or "").encode("utf-8")).decode("ascii"),
            "1" if replace_all else "0",
            "1" if backup else "0",
        ]
        run = await self._run_script(_PATCH_SCRIPT, args)
        if not getattr(run, "success", False):
            raise RuntimeError(f"container patch failed for {cpath}: {self._run_error(run)}")
        return self._parse_result(getattr(run, "stdout", ""))

    async def apply_batch_patch(self, patches: list[dict[str, Any]], backup: bool = True) -> dict[str, Any]:
        patches = patches or []
        results: list[dict[str, Any]] = []
        success_count = 0
        for patch in patches:
            result = await self.apply_text_patch(
                path=str(patch.get("path", "")),
                old_text=str(patch.get("old_text", "")),
                new_text=str(patch.get("new_text", "")),
                replace_all=bool(patch.get("replace_all", False)),
                backup=backup,
            )
            results.append(result)
            if result.get("applied") and result.get("verified"):
                success_count += 1
        return {
            "applied": success_count == len(patches) and bool(patches),
            "success_count": success_count,
            "total_count": len(patches),
            "results": results,
        }


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

    @staticmethod
    def _resolve_clone_dir(workspace: str) -> str:
        """Normalize the workspace argument into the actual clone dir.

        IssueToPRPipeline passes the clone dir itself (``<workspace>/repo``),
        while tests and programmatic callers pass a workspace that *contains*
        ``repo/``. Accept both shapes; prefer an existing ``repo/`` child.
        """
        base = Path(workspace)
        if (base / "repo").is_dir():
            return str(base / "repo")
        if base.name == "repo" or (base / ".git").exists():
            return str(base)
        return str(base / "repo")

    @staticmethod
    def _container_mount_for(sandbox: Any, clone_dir: str) -> tuple[Path, str] | None:
        """Return (host_workspace, container_clone_root) when the sandbox is a
        Docker-backed DockerSandbox whose workspace — bind-mounted at
        /workspace — contains the clone dir. Otherwise None (degraded mode).
        """
        if sandbox is None or getattr(sandbox, "backend", None) != "docker":
            return None
        workspace = getattr(sandbox, "_workspace", None)
        if workspace is None or not callable(getattr(sandbox, "run", None)):
            return None
        try:
            rel = Path(clone_dir).resolve().relative_to(Path(workspace).resolve())
        except (OSError, ValueError):
            return None
        rel_posix = rel.as_posix()
        root = _CONTAINER_WORKSPACE_ROOT if rel_posix == "." else f"{_CONTAINER_WORKSPACE_ROOT}/{rel_posix}"
        return Path(workspace), root

    @staticmethod
    def _swap_mutating_tool_handlers(agent: Any, handlers: dict[str, Any]) -> list[tuple[str, Any]] | None:
        """Replace the mutating file-tool handlers on the agent's registry.

        Returns a list of (name, original_definition) for restoration, or
        None when the agent exposes no swappable registry — in which case the
        caller MUST fail closed rather than fall back to host file writes.
        """
        tools_map = getattr(getattr(agent, "tools", None), "_tools", None)
        if not isinstance(tools_map, dict):
            return None
        from backend.app.core.tools import ToolDefinition

        swapped: list[tuple[str, Any]] = []
        for name, handler in handlers.items():
            original = tools_map.get(name)
            if original is None:
                continue
            tools_map[name] = ToolDefinition(
                name=original.name,
                description=original.description,
                handler=handler,
                risk_level=original.risk_level,
                required_scope=original.required_scope,
                parameters_schema=original.parameters_schema,
            )
            swapped.append((name, original))
        return swapped

    @staticmethod
    def _restore_tool_handlers(agent: Any, swapped: list[tuple[str, Any]]) -> None:
        tools_map = getattr(getattr(agent, "tools", None), "_tools", None)
        if not isinstance(tools_map, dict):
            return
        for name, original in swapped:
            tools_map[name] = original

    async def __call__(self, sandbox: Any, issue: Any, workspace: str) -> bool:
        from backend.app.core.contracts import RiskLevel, RunContext, RunStatus

        clone_dir = self._resolve_clone_dir(workspace)
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
        # P0-15: no hardcoded demo target. When the issue text names no file,
        # the agent must locate the correct file in the repository itself.

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

        # P0-15: when the pipeline sandbox is a real Docker container, route
        # the mutating file tools INTO the container (its workspace is
        # bind-mounted at /workspace). The host tool-root override is kept
        # ONLY so the read-only tools (read_file / list_files / ...) can
        # inspect the clone dir; the three mutating tools swapped in below
        # never touch the host filesystem.
        from backend.app.core.tools import reset_tool_root_override, set_tool_root_override
        token = set_tool_root_override(clone_dir)
        swapped: list[tuple[str, Any]] = []
        container_mount = self._container_mount_for(sandbox, clone_dir)
        if container_mount is not None:
            host_workspace, container_clone_root = container_mount
            container_tools = _ContainerFileTools(sandbox, host_workspace, container_clone_root)
            swapped_or_none = self._swap_mutating_tool_handlers(agent, {
                "write_file": container_tools.write_file,
                "apply_text_patch": container_tools.apply_text_patch,
                "apply_batch_patch": container_tools.apply_batch_patch,
            })
            if swapped_or_none is None:
                logger.error(
                    "AgentFixRunner: Docker sandbox present but the agent's tool registry is not swappable; "
                    "refusing to fall back to host file writes (issue %s)",
                    getattr(issue, "issue_number", "?"),
                )
                reset_tool_root_override(token)
                return False
            swapped = swapped_or_none
            logger.info(
                "AgentFixRunner: mutating file tools routed into container (root=%s)",
                container_clone_root,
            )
        else:
            # P0-15 残留清零：无 Docker sandbox 时默认 fail-closed，拒绝降级为宿主机写。
            # 开发/测试环境可显式 opt-in（XAGENT_ALLOW_DEGRADED_HOST_WRITE=1），
            # 生产环境不应设置该变量——不可信负载必须走容器隔离。
            import os

            if os.environ.get("XAGENT_ALLOW_DEGRADED_HOST_WRITE", "").lower() not in ("1", "true", "yes"):
                logger.error(
                    "AgentFixRunner: no Docker-backed sandbox (backend=%s); refusing to degrade to host "
                    "file writes (set XAGENT_ALLOW_DEGRADED_HOST_WRITE=1 to opt in for development only) "
                    "(issue %s)",
                    getattr(sandbox, "backend", None),
                    getattr(issue, "issue_number", "?"),
                )
                reset_tool_root_override(token)
                return False
            logger.warning(
                "AgentFixRunner: no Docker-backed sandbox (backend=%s); file tools execute on the HOST "
                "confined to %s — degraded isolation (XAGENT_ALLOW_DEGRADED_HOST_WRITE opt-in), "
                "do not use for untrusted workloads",
                getattr(sandbox, "backend", None),
                clone_dir,
            )
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
            if swapped:
                self._restore_tool_handlers(agent, swapped)
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
