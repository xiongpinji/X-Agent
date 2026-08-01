"""CLI chat command - interactive agent conversation with streaming TUI.

Provides Codex-like streaming terminal experience with:
- Real-time token-by-token output
- Rich markdown rendering
- Tool call visualization
- Multi-turn session persistence
"""
from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console

from cli.console import print_error, print_info

chat_app = typer.Typer(no_args_is_help=True)


@chat_app.callback(invoke_without_command=True)
def chat(
    ctx: typer.Context,
    message: Optional[str] = typer.Argument(None, help="Message to send to the agent"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID for multi-turn context"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Enable streaming output"),
) -> None:
    """Interactive chat with X-Agent (streaming TUI).

    Examples:
        xagent chat "帮我重构这个函数"
        xagent chat --session my-session "分析这段代码的性能"
        xagent chat  (enters interactive mode with streaming)
    """
    if ctx.invoked_subcommand is not None:
        return

    from cli.state import get_current_config
    config = get_current_config()

    if message:
        _send_message_streaming(message, config, session_id=session_id)
    else:
        _interactive_mode(config, session_id=session_id)


def _send_message_streaming(message: str, config, session_id: str | None = None) -> None:
    """Send a single message with streaming TUI output."""
    from cli.streaming import ChatSession, stream_chat_interactive

    console = Console()
    session = None
    if session_id:
        session = ChatSession.load(session_id) or ChatSession(session_id=session_id)

    try:
        response = asyncio.run(stream_chat_interactive(
            message=message,
            base_url=config.api_base_url,
            api_key=config.api_key,
            session=session,
            console=console,
        ))
        if session and response:
            from cli.streaming import ConversationTurn
            session.add_turn(ConversationTurn(role="user", content=message))
            session.add_turn(ConversationTurn(role="assistant", content=response))
            session.save()
    except Exception as e:
        print_error(f"Chat failed: {e}")
        raise typer.Exit(code=1)


def _interactive_mode(config, session_id: str | None = None) -> None:
    """Enter interactive chat mode with full streaming TUI."""
    from cli.streaming import run_interactive_chat

    try:
        run_interactive_chat(
            base_url=config.api_base_url,
            api_key=config.api_key,
            session_id=session_id,
        )
    except Exception as e:
        print_error(f"Interactive chat error: {e}")
        raise typer.Exit(code=1)


@chat_app.command()
def sessions() -> None:
    """List saved chat sessions."""
    from cli.streaming import ChatSession

    console = Console()
    session_list = ChatSession.list_sessions()
    if not session_list:
        console.print("[dim]No saved sessions.[/dim]")
        return

    from rich.table import Table
    import time
    table = Table(title="Chat Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Turns", justify="right")
    table.add_column("Created")
    for s in session_list[:20]:
        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["created"]))
        table.add_row(s["id"], str(s["turns"]), created)
    console.print(table)
