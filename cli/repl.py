"""Interactive REPL mode for X-Agent CLI.

Provides an interactive read-eval-print loop with command history,
auto-completion, and support for agent/workflow operations.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory

from cli.client import XAgentCLIError, create_client
from cli.config import CLIConfig
from cli.console import (
    get_console,
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
    print_warning,
)

logger = logging.getLogger("xagent.cli.repl")


class XAgentREPL:
    """Interactive REPL for X-Agent CLI operations.

    Provides command history, auto-completion, and support for:
    - Running agents with tasks
    - Listing agents, tools, workflows
    - Checking workflow status
    - Interactive command parsing and execution
    """

    # Built-in commands
    BUILTIN_COMMANDS = {
        "help": "Show available commands",
        "run": "Run an agent task: run <task>",
        "agents": "List all agents",
        "agent": "Agent commands: agent list",
        "tools": "List all available tools",
        "workflows": "List all workflows",
        "status": "Get workflow status: status <workflow_id>",
        "clear": "Clear screen",
        "exit": "Exit REPL",
        "quit": "Exit REPL",
    }

    def __init__(self, config: CLIConfig) -> None:
        """Initialize REPL instance.

        Args:
            config: CLI configuration
        """
        self.config = config
        self.console = get_console(config)
        self._setup_history()
        self._client = create_client(config)

    def _setup_history(self) -> None:
        """Set up command history file."""
        history_dir = Path.home() / ".xagent"
        history_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = history_dir / "repl_history"

    def _get_completer(self) -> WordCompleter:
        """Get word completer for built-in commands.

        Returns:
            WordCompleter instance with command suggestions
        """
        commands = list(self.BUILTIN_COMMANDS.keys())
        return WordCompleter(commands, ignore_case=True)

    def _print_welcome(self) -> None:
        """Print welcome message."""
        self.console.print(
            "[bold cyan]X-Agent Interactive REPL[/bold cyan]",
            style="bold",
        )
        self.console.print(
            f"Mode: [yellow]{self.config.mode}[/yellow] | "
            f"API: [yellow]{self.config.api_base_url}[/yellow]"
        )
        self.console.print(
            "Type [bold]help[/bold] for available commands or "
            "[bold]exit[/bold] to quit.\n"
        )

    def _print_help(self) -> None:
        """Print help message with available commands."""
        help_data = [
            {"Command": cmd, "Description": desc}
            for cmd, desc in self.BUILTIN_COMMANDS.items()
        ]
        print_table(help_data, title="Available Commands", config=self.config)

    def _parse_command(self, line: str) -> tuple[str, list[str]]:
        """Parse input line into command and arguments.

        Args:
            line: Input line from user

        Returns:
            Tuple of (command, args_list)
        """
        line = line.strip()
        if not line:
            return "", []

        try:
            parts = shlex.split(line)
        except ValueError:
            # Fallback to simple split if shlex fails
            parts = line.split()

        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        return command, args

    async def _handle_run(self, args: list[str]) -> None:
        """Handle 'run' command to execute an agent task.

        Args:
            args: Command arguments (task description)
        """
        if not args:
            print_error("Usage: run <task>", self.config)
            return

        task = " ".join(args)
        try:
            print_info(f"Running task: {task}", self.config)
            result = await self._client.run_agent(task)
            print_success("Task completed", self.config)
            print_json(result, self.config)
        except XAgentCLIError as e:
            print_error(f"Failed to run task: {e}", self.config)
        except Exception as e:
            print_error(f"Unexpected error: {e}", self.config)
            logger.exception("Error in run command")

    async def _handle_agents(self, args: list[str]) -> None:
        """Handle 'agents' command to list available agents.

        Args:
            args: Command arguments (unused)
        """
        try:
            result = await self._client.list_agents()
            agents = result.get("data", []) if isinstance(result, dict) else result
            if isinstance(agents, list) and agents:
                print_table(agents, title="Available Agents", config=self.config)
            else:
                print_info("No agents available", self.config)
        except XAgentCLIError as e:
            print_error(f"Failed to list agents: {e}", self.config)
        except Exception as e:
            print_error(f"Unexpected error: {e}", self.config)
            logger.exception("Error in agents command")

    async def _handle_tools(self, args: list[str]) -> None:
        """Handle 'tools' command to list available tools.

        Args:
            args: Command arguments (unused)
        """
        try:
            tools = await self._client.list_tools()
            if tools:
                print_table(tools, title="Available Tools", config=self.config)
            else:
                print_info("No tools available", self.config)
        except XAgentCLIError as e:
            print_error(f"Failed to list tools: {e}", self.config)
        except Exception as e:
            print_error(f"Unexpected error: {e}", self.config)
            logger.exception("Error in tools command")

    async def _handle_workflows(self, args: list[str]) -> None:
        """Handle 'workflows' command to list workflows.

        Args:
            args: Command arguments (unused)
        """
        try:
            workflows = await self._client.list_workflows()
            if workflows:
                print_table(workflows, title="Available Workflows", config=self.config)
            else:
                print_info("No workflows available", self.config)
        except XAgentCLIError as e:
            print_error(f"Failed to list workflows: {e}", self.config)
        except Exception as e:
            print_error(f"Unexpected error: {e}", self.config)
            logger.exception("Error in workflows command")

    async def _handle_status(self, args: list[str]) -> None:
        """Handle 'status' command to check workflow status.

        Args:
            args: Command arguments (workflow_id)
        """
        if not args:
            print_error("Usage: status <workflow_id>", self.config)
            return

        workflow_id = args[0]
        try:
            status = await self._client.get_workflow_status(workflow_id)
            print_json(status, self.config)
        except XAgentCLIError as e:
            print_error(f"Failed to get workflow status: {e}", self.config)
        except Exception as e:
            print_error(f"Unexpected error: {e}", self.config)
            logger.exception("Error in status command")

    async def _handle_agent_subcommand(self, args: list[str]) -> None:
        """Handle 'agent' subcommands.

        Args:
            args: Subcommand arguments
        """
        if not args or args[0].lower() == "list":
            await self._handle_agents([])
        else:
            print_error(
                "Unknown agent subcommand. Use 'agent list' to list agents.",
                self.config,
            )

    async def _execute_command(self, command: str, args: list[str]) -> bool:
        """Execute a parsed command.

        Args:
            command: Command name
            args: Command arguments

        Returns:
            True if should continue REPL, False if should exit
        """
        if not command:
            return True

        if command == "help":
            self._print_help()
        elif command == "run":
            await self._handle_run(args)
        elif command == "agents":
            await self._handle_agents(args)
        elif command == "agent":
            await self._handle_agent_subcommand(args)
        elif command == "tools":
            await self._handle_tools(args)
        elif command == "workflows":
            await self._handle_workflows(args)
        elif command == "status":
            await self._handle_status(args)
        elif command == "clear":
            self.console.clear()
        elif command in ("exit", "quit"):
            return False
        else:
            print_warning(
                f"Unknown command: {command}. Type 'help' for available commands.",
                self.config,
            )

        return True

    async def run(self) -> None:
        """Run the interactive REPL loop.

        Handles user input, command parsing, and execution until exit.
        """
        self._print_welcome()

        session = PromptSession(
            history=FileHistory(str(self.history_file)),
            completer=self._get_completer(),
        )

        try:
            while True:
                try:
                    line = await session.prompt_async("xagent> ")
                    command, args = self._parse_command(line)
                    should_continue = await self._execute_command(command, args)
                    if not should_continue:
                        print_info("Goodbye!", self.config)
                        break
                except KeyboardInterrupt:
                    print_warning("\nInterrupted by user", self.config)
                    continue
                except EOFError:
                    print_info("Goodbye!", self.config)
                    break
        except Exception as e:
            print_error(f"REPL error: {e}", self.config)
            logger.exception("Unexpected REPL error")


def start_repl(config: CLIConfig) -> None:
    """Start the interactive REPL.

    Entry point for REPL mode. Creates and runs XAgentREPL instance.

    Args:
        config: CLI configuration
    """
    repl = XAgentREPL(config)
    asyncio.run(repl.run())
