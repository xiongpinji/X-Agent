"""Agent management commands.

Provides commands for running agents, listing available agents, and managing
agent execution with permission scopes and context.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import typer

from cli.client import APIError, AuthError, ConnectionError, XAgentCLIError, create_client
from cli.console import print_error, print_json, print_success, print_table
from cli.evidence import (
    build_completion_contract,
    build_evidence,
    print_completion_verdict,
    print_evidence,
    save_completion_contract,
)
from cli.state import get_current_config

agent_app = typer.Typer(
    name="agent",
    help="Agent management commands",
    no_args_is_help=True,
)


@agent_app.command()
def run(
    task: str = typer.Argument(..., help="Task description for the agent to execute"),
    scope: Optional[list[str]] = typer.Option(
        None,
        "--scope",
        help="Permission scopes (can be used multiple times)",
    ),
    context: Optional[str] = typer.Option(
        None,
        "--context",
        help="Extra context as JSON string",
    ),
    stream: bool = typer.Option(
        False,
        "--stream/--no-stream",
        help="Stream results as they arrive",
    ),
    headless: bool = typer.Option(
        False,
        "--headless",
        help="CI/CD headless mode: JSON-only output, no interactive elements, exit code reflects success",
        envvar="XAGENT_HEADLESS",
    ),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        help="Override client mode for this command: 'http' or 'local'",
    ),
    contract: Optional[str] = typer.Option(
        None,
        "--contract",
        help="Write the completion contract (证据化完成判定) as JSON to the given path",
    ),
    parallel: Optional[int] = typer.Option(
        None,
        "--parallel",
        min=1,
        max=20,
        help="Fan out ';'-separated subtasks to N parallel sub-agents via the core executor (local mode only)",
    ),
) -> None:
    """Run an agent with the given task.

    Example:
        xagent agent run "Analyze the market trends"
        xagent agent run "Search for Python tutorials" --scope tools:read --scope memory:read
        xagent agent run "Process data" --context '{"format": "json"}'
        xagent agent run "Fix the bug" --headless  # CI/CD mode
        xagent agent run "task1; task2; task3" --parallel 3 --mode local  # parallel fan-out
    """
    try:
        config = get_current_config()
        if mode is not None:
            from cli.state import apply_mode_override

            try:
                config = apply_mode_override(mode)
            except ValueError as e:
                if headless:
                    print(json.dumps({"error": str(e)}))
                else:
                    print_error(str(e), config)
                raise typer.Exit(code=2)
        client = create_client(config)

        permission_scope = scope or ["tools:read", "memory:read", "memory:write"]

        extra_context: dict[str, Any] = {}
        if context:
            try:
                extra_context = json.loads(context)
            except json.JSONDecodeError as e:
                if headless:
                    print(json.dumps({"error": f"Invalid JSON in --context: {e}"}))
                else:
                    print_error(f"Invalid JSON in --context: {e}", config)
                raise typer.Exit(code=1)

        if parallel is not None:
            # ─── D1: parallel fan-out via core ParallelAgentExecutor ────────
            if getattr(config, "mode", "http") != "local":
                msg = "--parallel 目前仅支持 --mode local（直接调用核心 ParallelAgentExecutor）"
                if headless:
                    print(json.dumps({"error": msg}))
                else:
                    print_error(msg, config)
                raise typer.Exit(code=2)

            subtasks = _split_subtasks(task)
            if not subtasks:
                msg = "No subtasks found; separate subtasks with ';'"
                if headless:
                    print(json.dumps({"error": msg}))
                else:
                    print_error(msg, config)
                raise typer.Exit(code=1)

            batch = asyncio.run(
                _run_parallel_batch(
                    subtasks=subtasks,
                    max_parallel=parallel,
                    permission_scope=permission_scope,
                    extra_context=extra_context,
                )
            )
            _render_parallel_batch(batch, subtasks, headless, config)
            all_ok = batch.failed_tasks == 0 and batch.timeout_tasks == 0
            raise typer.Exit(code=0 if all_ok else 1)

        result = asyncio.run(
            client.run_agent(
                task=task,
                permission_scope=permission_scope,
                extra_context=extra_context,
                stream=stream,
            )
        )

        evidence = build_evidence(result)
        contract_obj = build_completion_contract(result, task=task)
        contract_path = None
        if contract:
            contract_path = save_completion_contract(contract_obj, contract)

        # ─── Headless / CI-CD mode: machine-readable JSON only ───────────────
        if headless or config.output_format == "json":
            output = {
                "trace_id": result.get("trace_id", ""),
                "status": result.get("status", ""),
                "answer": result.get("answer", ""),
                "iterations": result.get("iterations", 0),
                "tool_calls": evidence["tool_calls"],
                "evidence": evidence,
                "completion_contract": contract_obj,
                "execution_summary": result.get("execution_summary", {}),
            }
            if contract_path is not None:
                output["contract_path"] = str(contract_path)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            # Exit code: 0 if completed, 1 otherwise
            raise typer.Exit(code=0 if result.get("status") == "completed" else 1)

        # ─── Rich interactive mode ───────────────────────────────────────────
        display_result = {
            "trace_id": result.get("trace_id", "N/A"),
            "status": result.get("status", "N/A"),
            "task": result.get("task", task)[:50],
            "tool_calls": len(result.get("tool_calls", [])),
        }

        print_json(display_result, config)

        # Display the actual answer prominently
        answer = result.get("answer", "")
        if answer:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
            console = Console()
            console.print()
            console.print(Panel(
                Text(answer[:2000], style="green"),
                title="\u2713 Answer",
                border_style="green",
                padding=(0, 1),
            ))

        print_success("Agent execution completed", config)

        # ─── 完成证据 (codex-exec-style completion evidence) ─────────────────
        print_evidence(evidence, config)

        # ─── 证据化完成判定 (Track D2 completion contract verdict) ───────────
        print_completion_verdict(contract_obj, config)
        if contract_path is not None:
            print_success(f"Completion contract written to {contract_path}", config)

    except typer.Exit:
        raise
    except (ConnectionError, AuthError, APIError) as e:
        if headless:
            print(json.dumps({"error": str(e)}))
        else:
            print_error(f"Agent execution failed: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        if headless:
            print(json.dumps({"error": str(e)}))
        else:
            print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        if headless:
            print(json.dumps({"error": str(e)}))
        else:
            print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)


# ─── D1: parallel fan-out helpers (--parallel) ──────────────────────────────


def _split_subtasks(task: str) -> list[str]:
    """Split a ';'-separated task string into subtask goals."""
    return [s.strip() for s in task.split(";") if s.strip()]


async def _run_parallel_batch(
    subtasks: list[str],
    max_parallel: int,
    permission_scope: list[str],
    extra_context: dict[str, Any],
) -> Any:
    """Fan out subtasks through the core ParallelAgentExecutor (local mode).

    Returns the executor's SpawnResult. Each subtask gets an independent
    RunContext (hence an independent trace_id) on the shared AgentLoop,
    mirroring the API-side wiring in ``api/parallel_agents.py``.
    """
    from backend.app.core.contracts import RunContext
    from backend.app.core.parallel_agent_executor import (
        AgentTask,
        IsolationMode,
        ParallelAgentExecutor,
    )
    from backend.app.dependencies import get_agent

    agent_loop = get_agent()

    class _CliParallelAgent:
        """Adapt the shared AgentLoop to the executor's agent protocol."""

        def __init__(self, agent_id: str, isolation: IsolationMode) -> None:
            self.agent_id = agent_id
            self.isolation = isolation

        async def execute(self, task: AgentTask) -> dict[str, Any]:
            context = RunContext(
                agent_id=self.agent_id,
                permission_scope=list(permission_scope),
            )
            extra = {
                "parallel_agent_id": self.agent_id,
                "isolation": self.isolation.value,
                **(task.metadata or {}),
                **extra_context,
            }
            response = await agent_loop.run(context, task.goal, extra)
            body = response.model_dump(mode="json")
            body["trace_id"] = getattr(response, "trace_id", None) or context.trace_id
            if str(body.get("status", "")).lower() == "failed":
                raise RuntimeError(body.get("error") or "agent run failed")
            return body

    executor = ParallelAgentExecutor(max_workers=max_parallel)
    tasks = [
        AgentTask(
            goal=goal,
            max_retries=0,  # CLI fan-out: surface failures immediately, no retry storm
            metadata={"subtask_index": i},
        )
        for i, goal in enumerate(subtasks)
    ]
    return await executor.spawn_agents(
        tasks=tasks,
        isolation=IsolationMode.ISOLATED,
        max_parallel=max_parallel,
        agent_factory=lambda agent_id, isolation: _CliParallelAgent(agent_id, isolation),
    )


def _render_parallel_batch(batch: Any, subtasks: list[str], headless: bool, config: Any) -> None:
    """Render per-subtask status table + evidence sections (复用 build_evidence)."""
    rows: list[dict[str, Any]] = []
    evidences: list[dict[str, Any]] = []
    bodies: list[dict[str, Any]] = []

    for i, r in enumerate(batch.results):
        body = r.result if isinstance(r.result, dict) else {}
        body = dict(body)
        body.setdefault("status", str(r.status))
        if r.error and not body.get("error"):
            body["error"] = r.error
        bodies.append(body)
        evidence = build_evidence(body)
        evidences.append(evidence)
        rows.append(
            {
                "#": i + 1,
                "Subtask": (subtasks[i] if i < len(subtasks) else r.task_id)[:40],
                "Status": str(r.status),
                "Duration(s)": f"{r.duration_seconds:.2f}",
                "Trace": str(evidence.get("trace_id") or "N/A")[:36],
            }
        )

    sum_duration = sum(r.duration_seconds for r in batch.results)

    # ─── Headless / JSON mode ─────────────────────────────────────────────
    if headless or config.output_format == "json":
        print(
            json.dumps(
                {
                    "batch_id": batch.batch_id,
                    "mode": "parallel",
                    "max_parallel": batch.metadata.get("max_parallel"),
                    "total_tasks": batch.total_tasks,
                    "completed_tasks": batch.completed_tasks,
                    "failed_tasks": batch.failed_tasks,
                    "timeout_tasks": batch.timeout_tasks,
                    "wall_seconds": batch.total_duration_seconds,
                    "sum_subtask_seconds": sum_duration,
                    "subtasks": [
                        {
                            "subtask": subtasks[i] if i < len(subtasks) else r.task_id,
                            "status": str(r.status),
                            "trace_id": bodies[i].get("trace_id", ""),
                            "duration_seconds": r.duration_seconds,
                            "error": r.error,
                            "evidence": evidences[i],
                        }
                        for i, r in enumerate(batch.results)
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    # ─── Rich interactive mode ────────────────────────────────────────────
    print_table(rows, title="Parallel Subtasks", config=config)
    speedup = sum_duration / batch.total_duration_seconds if batch.total_duration_seconds > 0 else 0.0
    print_success(
        f"Parallel batch {batch.batch_id[:8]}: "
        f"{batch.completed_tasks}/{batch.total_tasks} completed, "
        f"wall={batch.total_duration_seconds:.2f}s vs serial={sum_duration:.2f}s "
        f"(speedup {speedup:.2f}x)",
        config,
    )

    from rich.console import Console

    console = Console()
    for i, evidence in enumerate(evidences):
        label = subtasks[i] if i < len(subtasks) else f"subtask {i + 1}"
        console.print(f"\n[bold]── Subtask {i + 1}: {label[:60]}[/bold]")
        print_evidence(evidence, config)


@agent_app.command("list")
def list_agents() -> None:
    """List all available agents.

    Example:
        xagent agent list
    """
    try:
        config = get_current_config()
        client = create_client(config)

        result = asyncio.run(client.list_agents())

        agents = result.get("data", []) if isinstance(result, dict) else result

        if not agents:
            print_error("No agents found", config)
            return

        table_data = [
            {
                "ID": agent.get("id", "N/A"),
                "Name": agent.get("name", "N/A"),
                "Status": agent.get("status", "N/A"),
                "Capabilities": ", ".join(agent.get("capabilities", [])),
            }
            for agent in agents
        ]

        print_table(table_data, title="Available Agents", config=config)

    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to list agents: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)
