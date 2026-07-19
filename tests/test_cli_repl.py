"""Unit tests for REPL (Read-Eval-Print Loop) mode.

Tests XAgentREPL command parsing, built-in command execution,
and error handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.config import CLIConfig
from cli.repl import XAgentREPL


@pytest.fixture
def repl_config():
    """Provide CLIConfig for REPL tests."""
    return CLIConfig(
        api_base_url="http://localhost:8000",
        mode="http",
        output_format="plain",
    )


@pytest.fixture
def repl_instance(repl_config):
    """Provide XAgentREPL instance with mocked client."""
    with patch("cli.repl.create_client") as mock_create_client:
        mock_client = AsyncMock()
        mock_create_client.return_value = mock_client
        repl = XAgentREPL(repl_config)
        repl._client = mock_client
        yield repl


class TestXAgentREPLInit:
    """Test XAgentREPL initialization."""

    def test_repl_init(self, repl_config):
        """Test REPL initializes with config."""
        with patch("cli.repl.create_client"):
            repl = XAgentREPL(repl_config)
            assert repl.config == repl_config
            assert repl.history_file is not None

    def test_repl_builtin_commands(self, repl_config):
        """Test REPL has all built-in commands."""
        with patch("cli.repl.create_client"):
            repl = XAgentREPL(repl_config)
            commands = repl.BUILTIN_COMMANDS
            assert "help" in commands
            assert "run" in commands
            assert "agents" in commands
            assert "tools" in commands
            assert "workflows" in commands
            assert "status" in commands
            assert "exit" in commands
            assert "quit" in commands


class TestParseCommand:
    """Test command parsing."""

    def test_parse_command_simple(self, repl_instance):
        """Test parsing simple command."""
        command, args = repl_instance._parse_command("help")
        assert command == "help"
        assert args == []

    def test_parse_command_with_args(self, repl_instance):
        """Test parsing command with arguments."""
        command, args = repl_instance._parse_command("run task description")
        assert command == "run"
        assert args == ["task", "description"]

    def test_parse_command_case_insensitive(self, repl_instance):
        """Test command parsing is case insensitive."""
        command, _ = repl_instance._parse_command("HELP")
        assert command == "help"

    def test_parse_command_empty_string(self, repl_instance):
        """Test parsing empty string."""
        command, args = repl_instance._parse_command("")
        assert command == ""
        assert args == []

    def test_parse_command_whitespace_only(self, repl_instance):
        """Test parsing whitespace-only string."""
        command, args = repl_instance._parse_command("   ")
        assert command == ""
        assert args == []

    def test_parse_command_with_quotes(self, repl_instance):
        """Test parsing command with quoted arguments."""
        command, args = repl_instance._parse_command('run "multi word task"')
        assert command == "run"
        assert "multi word task" in args


class TestHelpCommand:
    """Test help command."""

    @pytest.mark.asyncio
    async def test_execute_help_command(self, repl_instance):
        """Test executing help command."""
        with patch.object(repl_instance, "_print_help") as mock_print_help:
            should_continue = await repl_instance._execute_command("help", [])
            assert should_continue is True
            mock_print_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_print_help(self, repl_instance):
        """Test _print_help outputs commands."""
        with patch("cli.repl.print_table") as mock_print_table:
            repl_instance._print_help()
            mock_print_table.assert_called_once()
            call_args = mock_print_table.call_args
            help_data = call_args[0][0]
            assert len(help_data) > 0


class TestRunCommand:
    """Test run command for agent execution."""

    @pytest.mark.asyncio
    async def test_handle_run_success(self, repl_instance):
        """Test run command executes agent task."""
        repl_instance._client.run_agent.return_value = {
            "trace_id": "123",
            "status": "completed",
        }

        with patch("cli.repl.print_success"):
            with patch("cli.repl.print_json"):
                await repl_instance._handle_run(["test", "task"])
                repl_instance._client.run_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_run_no_args(self, repl_instance):
        """Test run command requires task argument."""
        with patch("cli.repl.print_error") as mock_print_error:
            await repl_instance._handle_run([])
            mock_print_error.assert_called_once()
            assert "Usage" in mock_print_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_run_error(self, repl_instance):
        """Test run command handles errors gracefully."""
        repl_instance._client.run_agent.side_effect = Exception("Error")

        with patch("cli.repl.print_error") as mock_print_error:
            await repl_instance._handle_run(["test"])
            mock_print_error.assert_called()

    @pytest.mark.asyncio
    async def test_execute_run_command(self, repl_instance):
        """Test executing run command."""
        repl_instance._client.run_agent.return_value = {"status": "completed"}

        with patch.object(repl_instance, "_handle_run", new_callable=AsyncMock):
            should_continue = await repl_instance._execute_command("run", ["task"])
            assert should_continue is True


class TestAgentsCommand:
    """Test agents command."""

    @pytest.mark.asyncio
    async def test_handle_agents_success(self, repl_instance):
        """Test agents command lists agents."""
        repl_instance._client.list_agents.return_value = {
            "data": [{"id": "agent1", "name": "Agent 1"}]
        }

        with patch("cli.repl.print_table") as mock_print_table:
            await repl_instance._handle_agents([])
            mock_print_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_agents_empty(self, repl_instance):
        """Test agents command with no agents."""
        repl_instance._client.list_agents.return_value = {"data": []}

        with patch("cli.repl.print_info") as mock_print_info:
            await repl_instance._handle_agents([])
            mock_print_info.assert_called()

    @pytest.mark.asyncio
    async def test_handle_agents_error(self, repl_instance):
        """Test agents command handles errors."""
        repl_instance._client.list_agents.side_effect = Exception("API error")

        with patch("cli.repl.print_error") as mock_print_error:
            await repl_instance._handle_agents([])
            mock_print_error.assert_called()

    @pytest.mark.asyncio
    async def test_execute_agents_command(self, repl_instance):
        """Test executing agents command."""
        repl_instance._client.list_agents.return_value = {"data": []}

        with patch.object(repl_instance, "_handle_agents", new_callable=AsyncMock):
            should_continue = await repl_instance._execute_command("agents", [])
            assert should_continue is True


class TestToolsCommand:
    """Test tools command."""

    @pytest.mark.asyncio
    async def test_handle_tools_success(self, repl_instance):
        """Test tools command lists tools."""
        repl_instance._client.list_tools.return_value = [
            {"name": "tool1", "description": "Tool 1"}
        ]

        with patch("cli.repl.print_table") as mock_print_table:
            await repl_instance._handle_tools([])
            mock_print_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_tools_empty(self, repl_instance):
        """Test tools command with no tools."""
        repl_instance._client.list_tools.return_value = []

        with patch("cli.repl.print_info") as mock_print_info:
            await repl_instance._handle_tools([])
            mock_print_info.assert_called()

    @pytest.mark.asyncio
    async def test_handle_tools_error(self, repl_instance):
        """Test tools command handles errors."""
        repl_instance._client.list_tools.side_effect = Exception("API error")

        with patch("cli.repl.print_error") as mock_print_error:
            await repl_instance._handle_tools([])
            mock_print_error.assert_called()


class TestWorkflowsCommand:
    """Test workflows command."""

    @pytest.mark.asyncio
    async def test_handle_workflows_success(self, repl_instance):
        """Test workflows command lists workflows."""
        repl_instance._client.list_workflows.return_value = [
            {"id": "wf1", "name": "Workflow 1"}
        ]

        with patch("cli.repl.print_table") as mock_print_table:
            await repl_instance._handle_workflows([])
            mock_print_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_workflows_empty(self, repl_instance):
        """Test workflows command with no workflows."""
        repl_instance._client.list_workflows.return_value = []

        with patch("cli.repl.print_info") as mock_print_info:
            await repl_instance._handle_workflows([])
            mock_print_info.assert_called()

    @pytest.mark.asyncio
    async def test_handle_workflows_error(self, repl_instance):
        """Test workflows command handles errors."""
        repl_instance._client.list_workflows.side_effect = Exception("API error")

        with patch("cli.repl.print_error") as mock_print_error:
            await repl_instance._handle_workflows([])
            mock_print_error.assert_called()


class TestStatusCommand:
    """Test status command."""

    @pytest.mark.asyncio
    async def test_handle_status_success(self, repl_instance):
        """Test status command retrieves workflow status."""
        repl_instance._client.get_workflow_status.return_value = {
            "workflow_id": "wf1",
            "status": "completed",
        }

        with patch("cli.repl.print_json") as mock_print_json:
            await repl_instance._handle_status(["wf1"])
            mock_print_json.assert_called_once()
            repl_instance._client.get_workflow_status.assert_called_with("wf1")

    @pytest.mark.asyncio
    async def test_handle_status_no_args(self, repl_instance):
        """Test status command requires workflow_id."""
        with patch("cli.repl.print_error") as mock_print_error:
            await repl_instance._handle_status([])
            mock_print_error.assert_called_once()
            assert "Usage" in mock_print_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_status_error(self, repl_instance):
        """Test status command handles errors."""
        repl_instance._client.get_workflow_status.side_effect = Exception("Error")

        with patch("cli.repl.print_error") as mock_print_error:
            await repl_instance._handle_status(["wf1"])
            mock_print_error.assert_called()


class TestAgentSubcommand:
    """Test agent subcommand."""

    @pytest.mark.asyncio
    async def test_handle_agent_list(self, repl_instance):
        """Test agent list subcommand."""
        repl_instance._client.list_agents.return_value = {"data": []}

        with patch.object(
            repl_instance, "_handle_agents", new_callable=AsyncMock
        ) as mock_handle:
            await repl_instance._handle_agent_subcommand(["list"])
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_agent_no_args_defaults_to_list(self, repl_instance):
        """Test agent subcommand with no args defaults to list."""
        repl_instance._client.list_agents.return_value = {"data": []}

        with patch.object(
            repl_instance, "_handle_agents", new_callable=AsyncMock
        ) as mock_handle:
            await repl_instance._handle_agent_subcommand([])
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_agent_invalid_subcommand(self, repl_instance):
        """Test agent subcommand with invalid subcommand."""
        with patch("cli.repl.print_error") as mock_print_error:
            await repl_instance._handle_agent_subcommand(["invalid"])
            mock_print_error.assert_called()


class TestExitCommand:
    """Test exit and quit commands."""

    @pytest.mark.asyncio
    async def test_execute_exit_command(self, repl_instance):
        """Test exit command returns False."""
        should_continue = await repl_instance._execute_command("exit", [])
        assert should_continue is False

    @pytest.mark.asyncio
    async def test_execute_quit_command(self, repl_instance):
        """Test quit command returns False."""
        should_continue = await repl_instance._execute_command("quit", [])
        assert should_continue is False


class TestClearCommand:
    """Test clear command."""

    @pytest.mark.asyncio
    async def test_execute_clear_command(self, repl_instance):
        """Test clear command clears console."""
        with patch.object(repl_instance.console, "clear") as mock_clear:
            should_continue = await repl_instance._execute_command("clear", [])
            assert should_continue is True
            mock_clear.assert_called_once()


class TestUnknownCommand:
    """Test handling of unknown commands."""

    @pytest.mark.asyncio
    async def test_execute_unknown_command(self, repl_instance):
        """Test unknown command shows warning."""
        with patch("cli.repl.print_warning") as mock_print_warning:
            should_continue = await repl_instance._execute_command("unknown_cmd", [])
            assert should_continue is True
            mock_print_warning.assert_called_once()
            assert "Unknown command" in mock_print_warning.call_args[0][0]


class TestEmptyCommand:
    """Test handling of empty commands."""

    @pytest.mark.asyncio
    async def test_execute_empty_command(self, repl_instance):
        """Test empty command is ignored."""
        should_continue = await repl_instance._execute_command("", [])
        assert should_continue is True


class TestCompleter:
    """Test word completer."""

    def test_get_completer(self, repl_instance):
        """Test _get_completer returns WordCompleter."""
        from prompt_toolkit.completion import WordCompleter

        completer = repl_instance._get_completer()
        assert isinstance(completer, WordCompleter)


class TestWelcomeMessage:
    """Test welcome message."""

    def test_print_welcome(self, repl_instance):
        """Test _print_welcome prints welcome message."""
        with patch.object(repl_instance.console, "print") as mock_print:
            repl_instance._print_welcome()
            assert mock_print.call_count >= 2


class TestIntegration:
    """Integration tests for REPL."""

    def test_repl_setup_history(self, repl_config):
        """Test REPL sets up history file correctly."""
        with patch("cli.repl.create_client"):
            repl = XAgentREPL(repl_config)
            assert repl.history_file is not None
            assert ".xagent" in str(repl.history_file)

    @pytest.mark.asyncio
    async def test_execute_command_sequence(self, repl_instance):
        """Test executing a sequence of commands."""
        repl_instance._client.list_agents.return_value = {"data": []}

        with patch("cli.repl.print_table"):
            # Execute help
            should_continue = await repl_instance._execute_command("help", [])
            assert should_continue is True

            # Execute agents
            with patch.object(
                repl_instance, "_handle_agents", new_callable=AsyncMock
            ):
                should_continue = await repl_instance._execute_command("agents", [])
                assert should_continue is True

            # Execute quit
            should_continue = await repl_instance._execute_command("quit", [])
            assert should_continue is False
