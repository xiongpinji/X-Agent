"""Streaming TUI Engine for X-Agent CLI.

Provides real-time streaming output with rich markdown rendering,
comparable to OpenAI Codex's terminal streaming experience.

Features:
- SSE (Server-Sent Events) streaming client
- Real-time token-by-token rendering with Rich Markdown
- Spinner/status indicators during agent thinking
- Tool call visualization with collapsible panels
- Multi-turn conversation with session persistence
- Interruptible streaming (Ctrl+C graceful handling)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

logger = logging.getLogger("xagent.cli.streaming")

# Session persistence directory
SESSION_DIR = Path.home() / ".xagent" / "sessions"


@dataclass
class StreamEvent:
    """A single SSE stream event."""

    event_type: str  # "token", "tool_call", "tool_result", "thinking", "error", "done"
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


class SSEStreamClient:
    """Server-Sent Events streaming client for X-Agent API.

    Handles SSE protocol parsing and yields structured StreamEvents.
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

    async def stream_chat(
        self,
        message: str,
        session_id: str | None = None,
        context: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream chat response from the agent API.

        Args:
            message: User message
            session_id: Optional session ID for multi-turn
            context: Optional conversation context

        Yields:
            StreamEvent instances as they arrive
        """
        client = await self._get_client()
        payload: dict[str, Any] = {
            "task": message,
            "stream": True,
            "permission_scope": [],
            "extra_context": {},
        }
        if session_id:
            payload["session_id"] = session_id
        if context:
            payload["extra_context"]["conversation_history"] = context

        try:
            async with client.stream("POST", "/api/v1/agents/run", json=payload) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    yield StreamEvent(
                        event_type="error",
                        data={"message": f"HTTP {response.status_code}: {body.decode()[:200]}"},
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
                            if event.event_type == "done":
                                return

                # Handle remaining buffer
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

    def _parse_sse_event(self, raw: str) -> StreamEvent | None:
        """Parse raw SSE text into a StreamEvent."""
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

        # Normalize event types
        if event_type in ("message", "content", "delta"):
            event_type = "token"
        elif event_type == "tool_use":
            event_type = "tool_call"
        elif event_type == "observation":
            event_type = "tool_result"

        return StreamEvent(event_type=event_type, data=data)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class StreamingTUI:
    """Rich TUI renderer for streaming agent output.

    Provides real-time rendering of:
    - Token-by-token text with markdown formatting
    - Tool call panels with status indicators
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

    def render_thinking(self, content: str = "") -> None:
        """Show thinking indicator."""
        if not self._is_thinking:
            self._is_thinking = True
            self.console.print(
                Text("⟨thinking⟩ ", style="dim italic") + Text(content[:80] + "..." if len(content) > 80 else content, style="dim"),
            )

    def render_token(self, text: str) -> None:
        """Render a streaming token (incremental text)."""
        if self._is_thinking:
            self._is_thinking = False
            self.console.print()  # newline after thinking
        self._current_text += text
        # Print token directly for real-time feel
        self.console.print(text, end="", highlight=False, markup=False)

    def render_tool_call(self, data: dict[str, Any]) -> None:
        """Render a tool call panel."""
        if self._current_text:
            self.console.print()  # flush current line
            self._current_text = ""

        tool_name = data.get("name", data.get("tool", "unknown"))
        tool_input = data.get("input", data.get("arguments", {}))
        call_id = data.get("id", "")

        self._tool_calls.append(data)

        # Compact tool call display
        input_preview = json.dumps(tool_input, ensure_ascii=False)
        if len(input_preview) > 120:
            input_preview = input_preview[:117] + "..."

        panel = Panel(
            Text(input_preview, style="dim"),
            title=f"🔧 {tool_name}",
            subtitle=call_id[:8] if call_id else None,
            border_style="blue",
            padding=(0, 1),
        )
        self.console.print(panel)

    def render_tool_result(self, data: dict[str, Any]) -> None:
        """Render tool execution result."""
        result = data.get("output", data.get("result", data.get("content", "")))
        if isinstance(result, dict):
            result = json.dumps(result, ensure_ascii=False, indent=2)
        result_str = str(result)
        if len(result_str) > 500:
            result_str = result_str[:497] + "..."

        self.console.print(
            Panel(
                Text(result_str, style="green"),
                title="✓ Result",
                border_style="green",
                padding=(0, 1),
            )
        )

    def render_error(self, message: str) -> None:
        """Render an error message."""
        if self._current_text:
            self.console.print()
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
        if self._current_text:
            self.console.print()  # final newline
            self._current_text = ""

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


async def stream_chat_interactive(
    message: str,
    base_url: str,
    api_key: str | None = None,
    session: ChatSession | None = None,
    console: Console | None = None,
) -> str:
    """High-level function: stream a chat message with full TUI rendering.

    Args:
        message: User message to send
        base_url: API base URL
        api_key: Optional API key
        session: Optional chat session for context
        console: Optional Rich console

    Returns:
        Full assistant response text
    """
    tui = StreamingTUI(console)
    client = SSEStreamClient(base_url, api_key)

    context = session.context_messages if session else None
    session_id = session.session_id if session else None

    tui.render_start()

    try:
        async for event in client.stream_chat(message, session_id=session_id, context=context):
            if event.event_type == "token":
                text = event.data.get("text", event.data.get("content", ""))
                if text:
                    tui.render_token(text)
            elif event.event_type == "thinking":
                tui.render_thinking(event.data.get("content", ""))
            elif event.event_type == "tool_call":
                tui.render_tool_call(event.data)
            elif event.event_type == "tool_result":
                tui.render_tool_result(event.data)
            elif event.event_type == "error":
                tui.render_error(event.data.get("message", "Unknown error"))
            elif event.event_type == "done":
                tui.render_done(event.data)
                break
    finally:
        await client.close()

    return tui.get_full_response()


def run_interactive_chat(
    base_url: str,
    api_key: str | None = None,
    session_id: str | None = None,
) -> None:
    """Run the full interactive chat loop with TUI.

    This is the main entry point for `xagent chat` interactive mode.
    Provides Codex-like streaming terminal experience.

    Args:
        base_url: API base URL
        api_key: Optional API key
        session_id: Optional session ID to resume
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

    # Welcome banner
    console.print(Panel(
        "[bold cyan]X-Agent[/bold cyan] Interactive Chat\n"
        f"[dim]Session: {session.session_id} | Server: {base_url}[/dim]\n"
        "[dim]Type your message, 'exit' to quit, 'history' for context[/dim]",
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
            if user_input.lower() == "history":
                _show_history(console, session)
                continue
            if user_input.lower() == "sessions":
                _show_sessions(console)
                continue

            # Record user turn
            session.add_turn(ConversationTurn(role="user", content=user_input))

            # Stream response
            console.print("[bold blue]Agent>[/bold blue] ", end="")
            response = asyncio.run(stream_chat_interactive(
                message=user_input,
                base_url=base_url,
                api_key=api_key,
                session=session,
                console=console,
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
