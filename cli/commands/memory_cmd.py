"""CLI memory commands - search and manage agent memory."""
from __future__ import annotations

import asyncio

import typer

from cli.console import print_error, print_info

memory_app = typer.Typer(no_args_is_help=True)


@memory_app.command("search")
def memory_search(
    query: str = typer.Argument(..., help="Search query"),
    layers: str | None = typer.Option(None, "--layers", "-l", help="Layer range, e.g. '1-10' or '4-7'"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Search agent memory.

    Examples:
        xagent memory search "认证逻辑"
        xagent memory search "database schema" --layers 4-7
        xagent memory search "API设计" --limit 5
    """
    from cli.client import create_client
    from cli.state import get_current_config

    try:
        config = get_current_config()
        client = create_client(config)

        async def _run():
            response = await client.request(
                "POST",
                "/api/v1/memory/search",
                json={
                    "query": query,
                    "layers": _parse_layers(layers),
                    "limit": limit,
                },
            )
            _print_results(response)

        asyncio.run(_run())
    except Exception as e:
        print_error(f"Memory search failed: {e}")
        raise typer.Exit(code=1)


@memory_app.command("store")
def memory_store(
    content: str = typer.Argument(..., help="Content to store"),
    layer: int = typer.Option(5, "--layer", "-l", help="Memory layer (1-10)"),
    tags: str | None = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
) -> None:
    """Store content in agent memory.

    Examples:
        xagent memory store "项目使用 PostgreSQL 14" --layer 6
        xagent memory store "团队约定: 所有API需要认证" --tags "convention,api"
    """
    from cli.client import create_client
    from cli.state import get_current_config

    try:
        config = get_current_config()
        client = create_client(config)

        async def _run():
            response = await client.request(
                "POST",
                "/api/v1/memory/store",
                json={
                    "content": content,
                    "layer": layer,
                    "tags": tags.split(",") if tags else [],
                },
            )
            print_info(f"Stored (id: {response.get('id', 'ok')})")

        asyncio.run(_run())
    except Exception as e:
        print_error(f"Memory store failed: {e}")
        raise typer.Exit(code=1)


@memory_app.command("list")
def memory_list(
    layer: int | None = typer.Option(None, "--layer", "-l", help="Filter by layer"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
) -> None:
    """List recent memories.

    Examples:
        xagent memory list
        xagent memory list --layer 8 --limit 5
    """
    from cli.client import create_client
    from cli.state import get_current_config

    try:
        config = get_current_config()
        client = create_client(config)

        async def _run():
            params = {"limit": limit}
            if layer is not None:
                params["layer"] = layer
            response = await client.request("GET", "/api/v1/memory/list", params=params)
            _print_results(response)

        asyncio.run(_run())
    except Exception as e:
        print_error(f"Memory list failed: {e}")
        raise typer.Exit(code=1)


def _parse_layers(layers_str: str | None) -> list[int] | None:
    """Parse layer range string like '4-7' or '1,3,5'."""
    if not layers_str:
        return None
    if "-" in layers_str:
        parts = layers_str.split("-")
        start, end = int(parts[0]), int(parts[1])
        return list(range(start, end + 1))
    return [int(x.strip()) for x in layers_str.split(",")]


def _print_results(response: dict | list) -> None:
    """Print memory search results."""
    results = response.get("results", response) if isinstance(response, dict) else response
    if not results:
        print_info("No results found.")
        return

    if isinstance(results, list):
        for i, item in enumerate(results, 1):
            if isinstance(item, dict):
                layer = item.get("layer", "?")
                content = item.get("content", item.get("text", ""))[:100]
                score = item.get("score", "")
                score_str = f" (score: {score:.3f})" if isinstance(score, float) else ""
                typer.echo(f"  {i}. [L{layer}]{score_str} {content}")
            else:
                typer.echo(f"  {i}. {item}")
    else:
        typer.echo(str(results))
