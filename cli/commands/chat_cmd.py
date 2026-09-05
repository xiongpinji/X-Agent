"""CLI chat command - interactive agent conversation with streaming TUI.

Provides Codex-like streaming terminal experience with:
- Real-time event-by-event output (iterations, tool calls, plans, approvals)
- @path file references injected into extra_context
- Slash commands (/help /clear /sessions /resume /approvals /approve /reject /model)
- Multi-turn session persistence

Modes:
- http  (default): true SSE streaming against /api/v1/agent/run/stream
- local: in-process agent run via LocalClient (no streaming)
"""
from __future__ import annotations

import asyncio
import os

import typer
from rich.console import Console
from rich.markdown import Markdown

from cli.console import print_error

chat_app = typer.Typer(no_args_is_help=True)


@chat_app.callback(invoke_without_command=True)
def chat(
    ctx: typer.Context,
    message: str | None = typer.Argument(None, help="Message to send to the agent"),
    session_id: str | None = typer.Option(None, "--session", "-s", help="Session ID for multi-turn context"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Enable streaming output (http mode only)"),
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

    if config.mode == "local":
        # LocalClient: in-process agent run, no HTTP streaming involved.
        _send_message_local(message or "", config, session_id=session_id)
        return

    if message:
        _send_message_streaming(message, config, session_id=session_id)
    else:
        _interactive_mode(config, session_id=session_id)


def _send_message_streaming(message: str, config, session_id: str | None = None) -> None:
    """Send a single message with streaming TUI output (http mode)."""
    from cli.streaming import (
        ChatSession,
        ConversationTurn,
        build_extra_context,
        parse_file_references,
        stream_chat_interactive,
    )

    console = Console()
    session = None
    if session_id:
        session = ChatSession.load(session_id) or ChatSession(session_id=session_id)

    parsed = parse_file_references(message, cwd=os.getcwd())
    for notice in parsed.notices:
        console.print(f"[yellow]· {notice}[/yellow]")
    extra_context = build_extra_context(parsed) or None

    try:
        response = asyncio.run(stream_chat_interactive(
            message=message,
            base_url=config.api_base_url,
            api_key=config.api_key,
            session=session,
            console=console,
            extra_context=extra_context,
        ))
        if session and response:
            session.add_turn(ConversationTurn(role="user", content=message))
            session.add_turn(ConversationTurn(role="assistant", content=response))
            session.save()
    except Exception as e:
        print_error(f"Chat failed: {e}")
        raise typer.Exit(code=1)


def _send_message_local(message: str, config, session_id: str | None = None) -> None:
    """Send a single message through the in-process LocalClient."""
    if not message:
        _interactive_mode(config, session_id=session_id)
        return

    from cli.client import create_client

    console = Console()
    client = create_client(config)
    try:
        result = asyncio.run(client.chat(message=message, session_id=session_id))
    except Exception as e:
        print_error(f"Chat failed (local mode): {e}")
        raise typer.Exit(code=1)
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            asyncio.run(close())

    answer = ""
    if isinstance(result, dict):
        answer = str(result.get("answer") or result.get("content") or "")
        if result.get("status") and str(result["status"]) != "completed":
            console.print(f"[yellow]status: {result['status']}[/yellow]")
    console.print("[bold blue]Agent>[/bold blue]")
    if answer:
        console.print(Markdown(answer))
    else:
        console.print("[dim](empty response)[/dim]")


def _interactive_mode(config, session_id: str | None = None) -> None:
    """Enter interactive chat mode with full streaming TUI."""
    if config.mode == "local":
        # Interactive local chat loop: reuse the LocalClient chat path.
        _interactive_local(config, session_id)
        return

    from cli.streaming import run_interactive_chat

    try:
        run_interactive_chat(
            base_url=config.api_base_url,
            api_key=config.api_key,
            session_id=session_id,
            cwd=os.getcwd(),
        )
    except Exception as e:
        print_error(f"Interactive chat error: {e}")
        raise typer.Exit(code=1)


def _interactive_local(config, session_id: str | None = None) -> None:
    """Minimal interactive loop for local mode (in-process agent)."""
    import time

    from cli.client import create_client
    from cli.streaming import ChatSession, ConversationTurn

    console = Console()
    session = (
        ChatSession.load(session_id) if session_id else None
    ) or ChatSession(session_id=session_id or f"chat-local-{int(time.time())}")

    console.print(
        f"[bold cyan]X-Agent[/bold cyan] Local Chat (in-process)\n"
        f"[dim]Session: {session.session_id} | exit to quit[/dim]"
    )
    client = create_client(config)
    try:
        while True:
            try:
                console.print()
                user_input = console.input("[bold green]You>[/bold green] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("[dim]Goodbye![/dim]")
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            session.add_turn(ConversationTurn(role="user", content=user_input))
            console.print("[bold blue]Agent>[/bold blue]")
            try:
                result = asyncio.run(client.chat(
                    message=user_input,
                    session_id=session.session_id,
                ))
                answer = str(result.get("answer") or result.get("content") or "") if isinstance(result, dict) else ""
            except NotImplementedError as e:
                console.print(f"[red]{e}[/red]")
                continue
            except Exception as e:
                console.print(f"[red]Chat failed: {e}[/red]")
                continue
            if answer:
                console.print(Markdown(answer))
                session.add_turn(ConversationTurn(role="assistant", content=answer))
            session.save()
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            asyncio.run(close())
        session.save()


@chat_app.command()
def sessions() -> None:
    """List saved chat sessions."""
    from cli.streaming import ChatSession

    console = Console()
    session_list = ChatSession.list_sessions()
    if not session_list:
        console.print("[dim]No saved sessions.[/dim]")
        return

    import time

    from rich.table import Table
    table = Table(title="Chat Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Turns", justify="right")
    table.add_column("Created")
    for s in session_list[:20]:
        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["created"]))
        table.add_row(s["id"], str(s["turns"]), created)
    console.print(table)
