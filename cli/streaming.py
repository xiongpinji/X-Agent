"""Streaming TUI Engine for X-Agent CLI.

Provides real-time streaming output with rich markdown rendering,
comparable to OpenAI Codex's terminal streaming experience.

Features:
- SSE (Server-Sent Events) streaming client against the true streaming
  backend endpoints (POST /api/v1/agent/run/stream + GET /api/v1/agent/stream/{run_id})
- Real-time rendering of fine-grained agent events: iterations, tool
  calls/results, plans, approvals, and the final answer
- Spinner/status indicators during agent thinking
- Tool call visualization with collapsible panels
- Multi-turn conversation with session persistence
- Chat input enhancements: @path file references and slash commands
- Inline y/n approval prompts when a tool call needs a decision
- Interruptible streaming (Ctrl+C graceful handling)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

logger = logging.getLogger("xagent.cli.streaming")

# Session persistence directory
SESSION_DIR = Path.home() / ".xagent" / "sessions"

# True-streaming backend endpoints
RUN_STREAM_ENDPOINT = "/api/v1/agent/run/stream"


def _stream_endpoint(run_id: str) -> str:
    return f"/api/v1/agent/stream/{run_id}"


# ============================================================================
# Chat input parsing (pure functions, unit-testable without a TUI)
# ============================================================================

# @path reference: "@" preceded by start-of-text/whitespace/punctuation (not a
# word char, so emails like user@example.com are not matched), followed by a
# filesystem-ish token.
FILE_REF_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_\-][A-Za-z0-9_\-.\\/]*)")

MAX_FILE_REFS = 5
MAX_FILE_BYTES = 100 * 1024  # 100KB per file


@dataclass
class FileRef:
    """A single @path reference resolved from chat input."""

    raw: str  # path text as typed (without the leading @)
    resolved: str | None = None  # absolute path if resolved
    content: str | None = None  # file content (possibly truncated)
    error: str | None = None  # human-readable problem, if any
    truncated: bool = False


@dataclass
class ParsedChatInput:
    """Result of parsing raw chat input for @path references."""

    message: str  # original message (unchanged; refs stay visible to the agent)
    files: list[FileRef] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)


def _clean_ref_token(token: str) -> str:
    """Strip trailing punctuation that is unlikely to be part of a path."""
    return token.rstrip(".,;:!?)\"]}'").rstrip("。" "，" "；" "：" "！" "）" "」" "』")


def parse_file_references(text: str, cwd: str | Path = ".") -> ParsedChatInput:
    """Extract ``@path`` file references from chat input.

    Files are read relative to ``cwd``. At most MAX_FILE_REFS files are
    attached; each is capped at MAX_FILE_BYTES. Missing/unreadable files
    produce a notice but never interrupt the chat.

    Returns the original message plus resolved file contents and notices.
    """
    parsed = ParsedChatInput(message=text)
    base = Path(cwd)

    seen: set[str] = set()
    count = 0
    for match in FILE_REF_RE.finditer(text or ""):
        raw = _clean_ref_token(match.group(1))
        if not raw or raw in seen:
            continue
        seen.add(raw)

        if count >= MAX_FILE_REFS:
            parsed.notices.append(f"@{raw}: skipped (max {MAX_FILE_REFS} files per message)")
            continue
        count += 1

        ref = FileRef(raw=raw)
        path = Path(raw)
        if not path.is_absolute():
            path = base / path
        try:
            if not path.exists():
                ref.error = "file not found"
                parsed.notices.append(f"@{raw}: file not found (skipped)")
            elif path.is_dir():
                ref.error = "is a directory"
                parsed.notices.append(f"@{raw}: is a directory (skipped)")
            else:
                data = path.read_bytes()
                if b"\x00" in data[:1024]:
                    ref.error = "binary file"
                    parsed.notices.append(f"@{raw}: binary file (skipped)")
                else:
                    ref.truncated = len(data) > MAX_FILE_BYTES
                    ref.content = data[:MAX_FILE_BYTES].decode("utf-8", errors="replace")
                    if ref.truncated:
                        parsed.notices.append(f"@{raw}: truncated to {MAX_FILE_BYTES // 1024}KB")
                    ref.resolved = str(path)
        except OSError as exc:
            ref.error = str(exc)
            parsed.notices.append(f"@{raw}: unreadable ({exc})")
        parsed.files.append(ref)

    return parsed


def build_extra_context(parsed: ParsedChatInput | None, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the API extra_context payload from parsed chat input."""
    extra = dict(base or {})
    if parsed is None:
        return extra
    attached = [
        {
            "path": f.resolved or f.raw,
            "size": len(f.content or ""),
            "truncated": f.truncated,
            "content": f.content or "",
        }
        for f in parsed.files
        if f.content is not None
    ]
    if attached:
        extra["attached_files"] = attached
        extra["file_count"] = len(attached)
    return extra


# ============================================================================
# Slash commands (pure parsing; execution lives in the interactive loop)
# ============================================================================

SLASH_COMMANDS: dict[str, str] = {
    "/help": "Show this help",
    "/clear": "Clear current conversation history",
    "/sessions": "List saved chat sessions",
    "/resume": "/resume <trace_id> — resume a run from its last checkpoint",
    "/approvals": "List pending approval requests",
    "/approve": "/approve <id> — approve (and execute) a pending request",
    "/reject": "/reject <id> — reject a pending request",
    "/model": "Show the active backend model configuration",
}


@dataclass
class SlashCommand:
    """A parsed slash command."""

    name: str
    args: list[str]
    line: str


def parse_slash_command(line: str) -> SlashCommand | None:
    """Parse a chat input line into a SlashCommand, or None if not a command."""
    text = (line or "").strip()
    if not text.startswith("/"):
        return None
    parts = text.split()
    name = parts[0].lower()
    if name not in SLASH_COMMANDS:
        return None
    return SlashCommand(name=name, args=parts[1:], line=text)


@dataclass
class StreamEvent:
    """A single SSE stream event."""

    event_type: str  # "token", "status", "iteration", "tool_call", "tool_result", "plan", "approval_required", "thinking", "error", "done"
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatSession:
    """Persistent chat session with conversation history."""

    session_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_turn(self, turn: ConversationTurn) -> None:
        """Add a conversation turn."""
        self.turns.append(turn)

    @property
    def context_messages(self) -> list[dict[str, str]]:
        """Get messages formatted for API context."""
        return [{"role": t.role, "content": t.content} for t in self.turns[-20:]]

    def save(self) -> None:
        """Persist session to disk."""
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSION_DIR / f"{self.session_id}.json"
        data = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "turns": [
                {
                    "role": t.role,
                    "content": t.content,
                    "timestamp": t.timestamp,
                    "tool_calls": t.tool_calls,
                    "metadata": t.metadata,
                }
                for t in self.turns
            ],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, session_id: str) -> ChatSession | None:
        """Load session from disk."""
        path = SESSION_DIR / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            session = cls(
                session_id=data["session_id"],
                created_at=data.get("created_at", time.time()),
                metadata=data.get("metadata", {}),
            )
            for t in data.get("turns", []):
                session.add_turn(ConversationTurn(
                    role=t["role"],
                    content=t["content"],
                    timestamp=t.get("timestamp", 0),
                    tool_calls=t.get("tool_calls", []),
                    metadata=t.get("metadata", {}),
                ))
            return session
        except Exception as e:
            logger.warning(f"Failed to load session {session_id}: {e}")
            return None

    @classmethod
    def list_sessions(cls) -> list[dict[str, Any]]:
        """List all saved sessions."""
        if not SESSION_DIR.exists():
            return []
        sessions = []
        for p in sorted(SESSION_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                sessions.append({
                    "id": data.get("session_id", p.stem),
                    "turns": len(data.get("turns", [])),
                    "created": data.get("created_at", 0),
                })
            except Exception:
                continue
        return sessions


class CliAPIError(Exception):
    """Raised for non-2xx responses from chat helper API calls."""


class SSEStreamClient:
    """Server-Sent Events streaming client for X-Agent API.

    Uses the true streaming backend:
    1. ``POST /api/v1/agent/run/stream`` starts a background run and
       returns ``{run_id, stream_url, trace_id}``.
    2. ``GET  /api/v1/agent/stream/{run_id}`` subscribes to the SSE
       channel and yields fine-grained events (iteration / tool_call /
       tool_result / plan / approval_required / completion ...) until the
       run reaches a terminal state.
    """

    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Accept": "text/event-stream"}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
            )
        return self._client

    # ------------------------------------------------------------------
    # Generic JSON helpers (used by slash commands and approval prompts)
    # ------------------------------------------------------------------

    async def api_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a JSON endpoint, raising CliAPIError on non-2xx."""
        client = await self._get_client()
        response = await client.get(path, params=params, headers={"Accept": "application/json"})
        return self._json_or_raise(response)

    async def api_post(self, path: str, json_body: Any = None, params: dict[str, Any] | None = None) -> Any:
        """POST a JSON endpoint, raising CliAPIError on non-2xx."""
        client = await self._get_client()
        response = await client.post(path, json=json_body, params=params, headers={"Accept": "application/json"})
        return self._json_or_raise(response)

    @staticmethod
    def _json_or_raise(response: httpx.Response) -> Any:
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text[:200])
            except Exception:
                detail = response.text[:200]
            raise CliAPIError(f"HTTP {response.status_code}: {detail}")
        try:
            return response.json()
        except Exception as exc:
            raise CliAPIError(f"Invalid JSON response: {exc}") from exc

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def start_run(
        self,
        message: str,
        extra_context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Start a streaming agent run; returns run_id/stream_url/trace_id."""
        client = await self._get_client()
        payload: dict[str, Any] = {
            "task": message,
            "extra_context": extra_context or {},
        }
        if session_id:
            payload["session_id"] = session_id
        response = await client.post(
            RUN_STREAM_ENDPOINT,
            json=payload,
            headers={"Accept": "application/json"},
        )
        data = self._json_or_raise(response)
        if not isinstance(data, dict) or not data.get("run_id"):
            raise CliAPIError(f"Unexpected run/stream response: {str(data)[:200]}")
        return data

    async def stream_run(self, run_id: str) -> AsyncIterator[StreamEvent]:
        """Subscribe to a run's SSE channel until the stream terminates."""
        client = await self._get_client()
        try:
            async with client.stream("GET", _stream_endpoint(run_id)) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode(errors="replace")
                    yield StreamEvent(
                        event_type="error",
                        data={"message": f"HTTP {response.status_code}: {body[:200]}"},
                    )
                    return

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        event_str, buffer = buffer.split("\n\n", 1)
                        event = self._parse_sse_event(event_str)
                        if event:
                            yield event
                            if event.event_type in ("done", "error"):
                                return

                if buffer.strip():
                    event = self._parse_sse_event(buffer)
                    if event:
                        yield event
        except httpx.ConnectError as e:
            yield StreamEvent(event_type="error", data={"message": f"Connection failed: {e}"})
        except httpx.TimeoutException:
            yield StreamEvent(event_type="error", data={"message": "Stream timeout"})
        except Exception as e:
            yield StreamEvent(event_type="error", data={"message": f"Stream error: {e}"})

    async def stream_chat(
        self,
        message: str,
        session_id: str | None = None,
        context: list[dict[str, str]] | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream chat response from the agent API (compat entry point).

        Starts a streaming run, then subscribes to its event channel.
        """
        extra = dict(extra_context or {})
        if context:
            extra["conversation_history"] = context
        try:
            start = await self.start_run(message, extra_context=extra, session_id=session_id)
        except CliAPIError as e:
            yield StreamEvent(event_type="error", data={"message": str(e)})
            return
        # aclosing: if the consumer breaks early, deterministically close the
        # inner generator (and its httpx stream context) instead of relying
        # on GC finalization, which races with client.close().
        async with contextlib.aclosing(self.stream_run(str(start["run_id"]))) as events:
            async for event in events:
                yield event

    def _parse_sse_event(self, raw: str) -> StreamEvent | None:
        """Parse raw SSE text into a StreamEvent, normalizing event types."""
        event_type = "token"
        data_lines: list[str] = []

        for line in raw.strip().split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line.startswith("data: "):
                data_lines.append(line[6:])

        if not data_lines:
            # Plain text chunk (non-SSE streaming)
            text = raw.strip()
            if text:
                return StreamEvent(event_type="token", data={"text": text})
            return None

        data_str = "\n".join(data_lines)
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            data = {"text": data_str}

        if not isinstance(data, dict):
            data = {"text": str(data)}

        # Backend StreamEvent envelope: {event_type, timestamp, run_id, data, sequence}
        inner = data.get("data")
        payload: dict[str, Any] = dict(inner) if isinstance(inner, dict) else data
        for key in ("run_id", "sequence", "timestamp"):
            if key in data and key not in payload:
                payload[key] = data[key]

        # Normalize event types
        role = str(payload.get("role", "") or "")
        if event_type in ("message", "content", "delta"):
            event_type = "token" if role not in ("system",) else "status"
            if "content" in payload and "text" not in payload:
                payload["text"] = payload["content"]
        elif event_type == "completion":
            event_type = "done"
        elif event_type in ("progress", "heartbeat"):
            event_type = "status" if event_type == "progress" else "heartbeat"
        elif event_type == "tool_use":
            event_type = "tool_call"
        elif event_type == "observation":
            event_type = "tool_result"

        if event_type == "heartbeat":
            return None

        return StreamEvent(event_type=event_type, data=payload)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class StreamingTUI:
    """Rich TUI renderer for streaming agent output.

    Provides real-time rendering of:
    - Token-by-token text with markdown formatting
    - Agent iterations and plans
    - Tool call lines with arguments/result summaries
    - Approval prompts
    - Thinking/reasoning indicators
    - Error displays
    """

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self._current_text = ""
        self._tool_calls: list[dict[str, Any]] = []
        self._is_thinking = False

    def render_start(self) -> None:
        """Render the start of an assistant response."""
        self._current_text = ""
        self._tool_calls = []
        self._is_thinking = False

    def _flush_line(self) -> None:
        if self._current_text:
            self.console.print()
            self._current_text = ""

    def render_thinking(self, content: str = "") -> None:
        """Show thinking indicator."""
        if not self._is_thinking:
            self._is_thinking = True
            self.console.print(
                Text("⟨thinking⟩ ", style="dim italic") + Text(content[:80] + "..." if len(content) > 80 else content, style="dim"),
            )

    def render_status(self, text: str) -> None:
        """Render a transient status/system line."""
        if not text:
            return
        if self._current_text:
            self.console.print()
            self._current_text = ""
        self.console.print(Text(f"· {text}", style="dim"))

    def render_iteration(self, data: dict[str, Any]) -> None:
        """Render an agent loop iteration marker."""
        if self._is_thinking:
            self._is_thinking = False
        iteration = data.get("iteration", "?")
        step_kind = str(data.get("step_kind") or "")
        instruction = str(data.get("instruction") or "")
        marker = {
            "tool": "⚙",
            "observe": "👁",
            "reflect": "🧠",
            "final": "🏁",
        }.get(step_kind, "→")
        line = f"{marker} step {iteration}"
        if step_kind:
            line += f" [{step_kind}]"
        if instruction:
            preview = instruction if len(instruction) <= 100 else instruction[:97] + "..."
            line += f" {preview}"
        self.console.print(Text(line, style="dim cyan"))

    def render_plan(self, data: dict[str, Any]) -> None:
        """Render plan creation."""
        goal = str(data.get("goal") or "")
        step_count = data.get("step_count", "?")
        line = f"▣ plan ready · {step_count} steps"
        if goal:
            preview = goal if len(goal) <= 80 else goal[:77] + "..."
            line += f" · {preview}"
        self.console.print(Text(line, style="bold blue"))

    def render_token(self, text: str) -> None:
        """Render a streaming token (incremental text)."""
        if self._is_thinking:
            self._is_thinking = False
            self.console.print()  # newline after thinking
        self._current_text += text
        # Print token directly for real-time feel
        self.console.print(text, end="", highlight=False, markup=False)

    def render_final_answer(self, text: str) -> None:
        """Render the final answer (markdown) once the run completes."""
        self._flush_line()
        if text.strip():
            self._current_text = text
            self.console.print(Markdown(text))

    def render_tool_call(self, data: dict[str, Any]) -> None:
        """Render a tool call (live completion marker or invocation panel)."""
        self._flush_line()

        tool_name = str(
            data.get("tool_name")
            or data.get("name")
            or data.get("tool")
            or "unknown"
        )
        phase = data.get("phase") or "started"
        self._tool_calls.append(data)

        if phase == "completed":
            success = bool(data.get("success", True))
            latency = data.get("latency_ms")
            mark = Text("✓", style="green") if success else Text("✗", style="red")
            suffix = f" ({latency:.0f}ms)" if isinstance(latency, (int, float)) else ""
            self.console.print(Text("  ") + mark + Text(f" {tool_name}{suffix}", style="dim"))
            return

        tool_input = data.get("input", data.get("arguments", {}))
        input_preview = json.dumps(tool_input, ensure_ascii=False) if tool_input else ""
        if len(input_preview) > 120:
            input_preview = input_preview[:117] + "..."

        panel = Panel(
            Text(input_preview, style="dim"),
            title=f"🔧 {tool_name}",
            subtitle=str(data.get("id", ""))[:8] or None,
            border_style="blue",
            padding=(0, 1),
        )
        self.console.print(panel)

    def render_tool_result(self, data: dict[str, Any]) -> None:
        """Render tool execution result summary."""
        tool_name = str(data.get("tool_name") or "")
        args = data.get("arguments", "")
        result = data.get("output", data.get("result", data.get("content", "")))
        if isinstance(result, (dict, list)):
            result = json.dumps(result, ensure_ascii=False)
        result_str = str(result or "")
        if len(result_str) > 300:
            result_str = result_str[:297] + "..."

        style = "green" if data.get("success", True) else "red"
        parts = [Text("  ↳ ", style="dim")]
        if tool_name:
            parts.append(Text(f"{tool_name}: ", style=style))
        if args:
            args_str = str(args)
            if len(args_str) > 120:
                args_str = args_str[:117] + "..."
            parts.append(Text(f"{args_str} → ", style="dim"))
        parts.append(Text(result_str or "(empty)", style=style))
        if data.get("error"):
            parts.append(Text(f" [error: {data['error']}]", style="red"))
        self.console.print(Text.assemble(*parts))

    def render_approval_required(self, data: dict[str, Any]) -> None:
        """Render an approval request panel (without the prompt itself)."""
        self._flush_line()
        approval_id = data.get("approval_id") or "(no id)"
        tool_name = data.get("tool_name") or data.get("resource_id") or "?"
        risk = data.get("risk_level", "?")
        reason = str(data.get("reason") or "")
        body = Text()
        body.append(f"Tool: {tool_name}\n", style="bold")
        body.append(f"Risk: {risk}  Approval ID: {approval_id}\n", style="dim")
        if reason:
            body.append(f"Reason: {reason[:300]}", style="dim")
        args = data.get("arguments")
        if args:
            args_str = json.dumps(args, ensure_ascii=False) if not isinstance(args, str) else args
            if len(args_str) > 200:
                args_str = args_str[:197] + "..."
            body.append(f"\nArguments: {args_str}", style="dim")
        self.console.print(Panel(body, title="⚠ Approval required", border_style="yellow", padding=(0, 1)))

    def render_error(self, message: str) -> None:
        """Render an error message."""
        self._flush_line()
        self.console.print(
            Panel(
                Text(message, style="red"),
                title="✗ Error",
                border_style="red",
                padding=(0, 1),
            )
        )

    def render_done(self, data: dict[str, Any] | None = None) -> None:
        """Render completion indicator."""
        self._flush_line()

        # Summary line
        elapsed = data.get("elapsed_ms", 0) if data else 0
        tokens = data.get("tokens_used", 0) if data else 0
        parts = []
        if elapsed:
            parts.append(f"{elapsed/1000:.1f}s")
        if tokens:
            parts.append(f"{tokens} tokens")
        if self._tool_calls:
            parts.append(f"{len(self._tool_calls)} tools")
        if parts:
            self.console.print(Text(f"  [{', '.join(parts)}]", style="dim"))

    def get_full_response(self) -> str:
        """Get the accumulated full response text."""
        return self._current_text


# ============================================================================
# Approval handling
# ============================================================================

def confirm_approval(console: Console, data: dict[str, Any]) -> bool:
    """Ask the user to approve a pending request (y/N prompt).

    Separated from the async flow so tests can patch this single function.
    """
    try:
        answer = console.input("[bold yellow]Approve this action? [y/N][/bold yellow] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


async def handle_approval_event(
    client: SSEStreamClient,
    console: Console,
    data: dict[str, Any],
    *,
    execute_after_approve: bool = True,
    confirmer: Callable[[Console, dict[str, Any]], bool] | None = None,
) -> None:
    """Inline approval flow: prompt y/n, then call the approvals API."""
    approval_id = data.get("approval_id")
    if not approval_id:
        console.print("[yellow]Approval required but no approval id was provided; use /approvals to inspect.[/yellow]")
        return

    approved = (confirmer or confirm_approval)(console, data)
    try:
        if approved:
            record = await client.api_post(
                f"/api/v1/approvals/{approval_id}/approve",
                json_body={"decided_by": "cli-user", "reason": "approved via chat"},
            )
            status = record.get("status", "approved") if isinstance(record, dict) else "approved"
            console.print(f"[green]✓ approval {approval_id} {status}[/green]")
            if execute_after_approve:
                try:
                    tool_result = await client.api_post(f"/api/v1/approvals/{approval_id}/execute")
                    ok = bool(tool_result.get("success")) if isinstance(tool_result, dict) else False
                    mark = "[green]✓[/green]" if ok else "[red]✗[/red]"
                    console.print(f"{mark} executed approval {approval_id}")
                except CliAPIError as exc:
                    console.print(f"[yellow]approved but execution failed: {exc}[/yellow]")
        else:
            record = await client.api_post(
                f"/api/v1/approvals/{approval_id}/reject",
                json_body={"decided_by": "cli-user", "reason": "rejected via chat"},
            )
            status = record.get("status", "rejected") if isinstance(record, dict) else "rejected"
            console.print(f"[red]✗ approval {approval_id} {status}[/red]")
    except CliAPIError as exc:
        console.print(f"[red]approval decision failed: {exc}[/red]")


async def stream_chat_interactive(
    message: str,
    base_url: str,
    api_key: str | None = None,
    session: ChatSession | None = None,
    console: Console | None = None,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """High-level function: stream a chat message with full TUI rendering.

    Args:
        message: User message to send
        base_url: API base URL
        api_key: Optional API key
        session: Optional chat session for context
        console: Optional Rich console
        extra_context: Optional extra context (e.g. @file attachments)

    Returns:
        Full assistant response text
    """
    tui = StreamingTUI(console)
    client = SSEStreamClient(base_url, api_key)

    context = session.context_messages if session else None
    session_id = session.session_id if session else None

    tui.render_start()
    final_answer = ""

    try:
        # aclosing: deterministic generator teardown before the finally
        # block closes the shared httpx client.
        async with contextlib.aclosing(client.stream_chat(
            message,
            session_id=session_id,
            context=context,
            extra_context=extra_context,
        )) as event_stream:
            async for event in event_stream:
                if event.event_type == "token":
                    text = event.data.get("text", event.data.get("content", ""))
                    if text:
                        tui.render_token(text)
                elif event.event_type == "status":
                    tui.render_status(str(event.data.get("current_step") or event.data.get("content") or ""))
                elif event.event_type == "thinking":
                    tui.render_thinking(event.data.get("content", ""))
                elif event.event_type == "iteration":
                    tui.render_iteration(event.data)
                elif event.event_type == "plan":
                    tui.render_plan(event.data)
                elif event.event_type == "tool_call":
                    tui.render_tool_call(event.data)
                elif event.event_type == "tool_result":
                    tui.render_tool_result(event.data)
                elif event.event_type == "approval_required":
                    tui.render_approval_required(event.data)
                    # Inline y/N prompt; blocks the stream briefly (approval
                    # events arrive after the run itself has finished).
                    await handle_approval_event(client, tui.console, event.data)
                elif event.event_type == "error":
                    tui.render_error(event.data.get("message", "Unknown error"))
                elif event.event_type == "done":
                    final_answer = str(event.data.get("result") or "")
                    if final_answer:
                        tui.render_final_answer(final_answer)
                    tui.render_done(event.data)
                    break
    finally:
        await client.close()

    return final_answer or tui.get_full_response()


# ============================================================================
# Slash command execution (requires the API client)
# ============================================================================

def _print_help(console: Console) -> None:
    table = Table(title="Chat Commands", show_lines=False)
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description")
    for name, desc in SLASH_COMMANDS.items():
        table.add_row(name, desc)
    table.add_row("@<path>", "Attach a file (relative to cwd, max 5 files, 100KB each)")
    table.add_row("exit / quit", "Leave the chat")
    table.add_row("history", "Show conversation history")
    console.print(table)


async def execute_slash_command(
    cmd: SlashCommand,
    console: Console,
    client: SSEStreamClient,
    session: ChatSession,
) -> bool:
    """Execute a slash command. Returns True when the input was a command.

    Pure dispatch around the (async) API calls; parse_slash_command is the
    testable pure parser.
    """
    if cmd.name == "/help":
        _print_help(console)
    elif cmd.name == "/clear":
        session.turns.clear()
        session.metadata["cleared_at"] = time.time()
        console.print("[dim]Conversation history cleared.[/dim]")
    elif cmd.name == "/sessions":
        _show_sessions(console)
    elif cmd.name == "/resume":
        if not cmd.args:
            console.print("[yellow]Usage: /resume <trace_id>[/yellow]")
        else:
            trace_id = cmd.args[0]
            try:
                result = await client.api_post(f"/api/v1/checkpoints/{trace_id}/resume", json_body={})
                console.print(
                    f"[green]Resumed {trace_id}[/green] → new trace "
                    f"{result.get('new_trace_id', '?')} from iteration "
                    f"{result.get('resumed_from_iteration', '?')} ({result.get('status', '?')})"
                )
            except CliAPIError as exc:
                console.print(f"[red]Resume failed: {exc}[/red]")
    elif cmd.name == "/approvals":
        try:
            approvals = await client.api_get("/api/v1/approvals", params={"status": "pending", "limit": 20})
        except CliAPIError as exc:
            console.print(f"[red]Failed to list approvals: {exc}[/red]")
            return True
        if not approvals:
            console.print("[dim]No pending approvals.[/dim]")
        else:
            table = Table(title="Pending Approvals")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Tool", style="bold")
            table.add_column("Risk")
            table.add_column("Reason", max_width=40)
            for rec in approvals:
                table.add_row(
                    str(rec.get("id", ""))[:13] + "…",
                    str(rec.get("resource_id", "?")),
                    str(rec.get("risk_level", "?")),
                    str(rec.get("reason", ""))[:60],
                )
            console.print(table)
    elif cmd.name in ("/approve", "/reject"):
        if not cmd.args:
            console.print(f"[yellow]Usage: {cmd.name} <approval_id>[/yellow]")
        else:
            approval_id = cmd.args[0]
            action = "approve" if cmd.name == "/approve" else "reject"
            try:
                record = await client.api_post(
                    f"/api/v1/approvals/{approval_id}/{action}",
                    json_body={"decided_by": "cli-user", "reason": f"{action}d via chat"},
                )
                status = record.get("status", action) if isinstance(record, dict) else action
                console.print(f"[green]✓ {action} {approval_id}: {status}[/green]")
                if action == "approve":
                    try:
                        tool_result = await client.api_post(f"/api/v1/approvals/{approval_id}/execute")
                        ok = bool(tool_result.get("success")) if isinstance(tool_result, dict) else False
                        console.print(f"{'[green]✓[/green]' if ok else '[red]✗[/red]'} executed {approval_id}")
                    except CliAPIError as exc:
                        console.print(f"[yellow]approved but execution failed: {exc}[/yellow]")
            except CliAPIError as exc:
                console.print(f"[red]{action} failed: {exc}[/red]")
    elif cmd.name == "/model":
        try:
            config = await client.api_get("/api/v1/agent/model-config")
        except CliAPIError as exc:
            console.print(f"[red]Failed to load model config: {exc}[/red]")
            return True
        console.print(Panel(
            f"[bold]backend[/bold]: {config.get('llm_backend', '?')}\n"
            f"[bold]fallback order[/bold]: {', '.join(config.get('fallback_order') or []) or '-'}\n"
            f"[bold]openai model[/bold]: {config.get('openai_model') or '-'}\n"
            f"[bold]deepseek model[/bold]: {config.get('deepseek_model') or '-'}\n"
            f"[bold]router backends[/bold]: "
            f"{', '.join(b.get('name', '?') for b in config.get('router_backends') or []) or '-'}",
            title="Model Configuration",
            border_style="cyan",
        ))
    return True


def run_interactive_chat(
    base_url: str,
    api_key: str | None = None,
    session_id: str | None = None,
    cwd: str | Path = ".",
) -> None:
    """Run the full interactive chat loop with TUI.

    This is the main entry point for `xagent chat` interactive mode.
    Provides Codex-like streaming terminal experience with @file
    references, slash commands and inline approvals.
    """
    console = Console()

    # Load or create session
    session: ChatSession | None = None
    if session_id:
        session = ChatSession.load(session_id)
        if session:
            console.print(f"[dim]Resumed session: {session_id} ({len(session.turns)} turns)[/dim]")
        else:
            session = ChatSession(session_id=session_id)
    else:
        import uuid
        session = ChatSession(session_id=f"chat-{uuid.uuid4().hex[:8]}")

    client = SSEStreamClient(base_url, api_key)

    # Welcome banner
    console.print(Panel(
        "[bold cyan]X-Agent[/bold cyan] Interactive Chat\n"
        f"[dim]Session: {session.session_id} | Server: {base_url}[/dim]\n"
        "[dim]Type your message; /help for commands; @path to attach files; 'exit' to quit[/dim]",
        border_style="cyan",
        title="🤖",
    ))

    while True:
        try:
            console.print()
            user_input = console.input("[bold green]You>[/bold green] ").strip()

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            # Slash commands
            slash = parse_slash_command(user_input)
            if slash is not None:
                asyncio.run(execute_slash_command(slash, console, client, session))
                session.save()
                continue

            if user_input.lower() == "history":
                _show_history(console, session)
                continue
            if user_input.lower() == "sessions":
                _show_sessions(console)
                continue

            # @path file references
            parsed = parse_file_references(user_input, cwd=cwd)
            for notice in parsed.notices:
                console.print(Text(f"· {notice}", style="yellow"))
            extra_context = build_extra_context(parsed)

            # Record user turn
            session.add_turn(ConversationTurn(role="user", content=user_input))

            # Stream response
            console.print("[bold blue]Agent>[/bold blue]")
            response = asyncio.run(stream_chat_interactive(
                message=user_input,
                base_url=base_url,
                api_key=api_key,
                session=session,
                console=console,
                extra_context=extra_context or None,
            ))

            # Record assistant turn
            if response:
                session.add_turn(ConversationTurn(role="assistant", content=response))

            # Auto-save session
            session.save()

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Type 'exit' to quit.[/dim]")
            continue
        except EOFError:
            console.print("[dim]Goodbye![/dim]")
            break

    # Final save
    session.save()
    asyncio.run(client.close())


def _show_history(console: Console, session: ChatSession) -> None:
    """Display conversation history."""
    if not session.turns:
        console.print("[dim]No history yet.[/dim]")
        return
    table = Table(title="Conversation History")
    table.add_column("#", style="dim", width=3)
    table.add_column("Role", style="bold")
    table.add_column("Content", max_width=60)
    for i, turn in enumerate(session.turns[-10:], 1):
        content_preview = turn.content[:57] + "..." if len(turn.content) > 60 else turn.content
        role_style = "green" if turn.role == "user" else "blue"
        table.add_row(str(i), f"[{role_style}]{turn.role}[/{role_style}]", content_preview)
    console.print(table)


def _show_sessions(console: Console) -> None:
    """Display available sessions."""
    sessions = ChatSession.list_sessions()
    if not sessions:
        console.print("[dim]No saved sessions.[/dim]")
        return
    table = Table(title="Saved Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Turns", justify="right")
    table.add_column("Created")
    for s in sessions[:10]:
        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["created"]))
        table.add_row(s["id"], str(s["turns"]), created)
    console.print(table)
