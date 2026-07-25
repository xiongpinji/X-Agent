"""CLI chat command - interactive agent conversation."""
from __future__ import annotations

import asyncio
from typing import Optional

import typer

from cli.console import print_error, print_info

chat_app = typer.Typer(no_args_is_help=True)


@chat_app.callback(invoke_without_command=True)
def chat(
    ctx: typer.Context,
    message: Optional[str] = typer.Argument(None, help="Message to send to the agent"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Enable streaming output"),
) -> None:
    """Interactive chat with X-Agent.

    Examples:
        xagent chat "帮我重构这个函数"
        xagent chat --session my-session "分析这段代码的性能"
        xagent chat  (enters interactive mode)
    """
    if ctx.invoked_subcommand is not None:
        return

    if message:
        _send_message(message, session_id=session_id, stream=stream)
    else:
        _interactive_mode(session_id=session_id)


def _send_message(message: str, session_id: str | None = None, stream: bool = True) -> None:
    """Send a single message to the agent."""
    from cli.client import create_client
    from cli.state import get_current_config

    try:
        config = get_current_config()
        client = create_client(config)

        async def _run():
            response = await client.chat(
                message=message,
                session_id=session_id,
                stream=stream,
            )
            if stream and hasattr(response, "get_stream"):
                async for chunk in response.get_stream():
                    typer.echo(chunk, nl=False)
                typer.echo()
            else:
                content = response.get("content", "") if isinstance(response, dict) else str(response)
                typer.echo(content)

        asyncio.run(_run())
    except Exception as e:
        print_error(f"Chat failed: {e}")
        raise typer.Exit(code=1)


def _interactive_mode(session_id: str | None = None) -> None:
    """Enter interactive chat mode."""
    print_info("X-Agent Interactive Chat (type 'exit' or Ctrl+C to quit)")
    print_info("-" * 50)

    while True:
        try:
            user_input = typer.prompt("\n> ", default="", show_default=False)
            if not user_input.strip():
                continue
            if user_input.strip().lower() in ("exit", "quit", "q"):
                print_info("Goodbye!")
                break
            _send_message(user_input, session_id=session_id, stream=True)
        except (KeyboardInterrupt, EOFError):
            print_info("\nGoodbye!")
            break
