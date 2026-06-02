"""Unit tests for CLI commands.

Tests Typer command groups (agent, tools, workflow, init) and main app commands
(health, config_show, repl) using CliRunner.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from cli.client import APIError, AuthError, ConnectionError, XAgentCLIError
from cli.config import CLIConfig
from cli.main import app, set_current_config


@pytest.fixture
def runner():
    """Provide CliRunner instance."""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Provide mock CLIConfig."""
    return CLIConfig(
        api_base_url="http://localhost:8000",
        mode="http",
        output_format="plain",
    )


@pytest.fixture(autouse=True)
def setup_config(mock_config):
    """Set up config before each test."""
    set_current_config(mock_config)
    yield


class TestMainApp:
    """Test main app and global options."""

    def test_app_help(self, runner):
        """Test --help shows usage."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "X-Agent CLI" in result.stdout

    def test_app_version(self, runner):
        """Test --version shows version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "xagent version" in result.stdout

    def test_app_no_args_shows_help(self, runner):
        """Test app with no args shows help."""
        result = runner.invoke(app, [])
        # no_args_is_help=True causes Typer to exit with code 2
        assert result.exit_code in (0, 2)
        assert "X-Agent CLI" in result.stdout or "Usage" in result.stdout


class TestHealthCommand:
    """Test health check command."""

    def test_health_check_healthy(self, runner, mock_config):
        """Test health command with healthy backend."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = {"status": "healthy"}

        with patch(
            "cli.client.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["health"])
            assert result.exit_code == 0
            assert "healthy" in result.stdout.lower()

    def test_health_check_unhealthy(self, runner, mock_config):
        """Test health command with unhealthy backend."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = {
            "status": "unhealthy",
            "error": "Connection refused",
        }

        with patch(
            "cli.client.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["health"])
            assert result.exit_code == 1

    def test_health_check_connection_error(self, runner, mock_config):
        """Test health command handles ConnectionError."""
        mock_client = AsyncMock()
        mock_client.health_check.side_effect = ConnectionError("Failed to connect")

        with patch(
            "cli.client.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["health"])
            assert result.exit_code == 1


class TestConfigShowCommand:
    """Test config_show command."""

    def test_config_show_displays_config(self, runner, mock_config):
        """Test config_show displays current configuration."""
        result = runner.invoke(app, ["config-show"])
        assert result.exit_code == 0
        assert "API URL" in result.stdout
        assert "localhost:8000" in result.stdout
        assert "Mode" in result.stdout

    def test_config_show_masks_api_key(self, runner):
        """Test config_show masks API key."""
        result = runner.invoke(
            app,
            ["--api-key", "secret-key-12345", "config-show"],
        )
        assert result.exit_code == 0
        assert "secret-key" not in result.stdout
        assert "****" in result.stdout or "*" in result.stdout


class TestAgentCommands:
    """Test agent subcommand group."""

    def test_agent_help(self, runner):
        """Test agent --help shows subcommands."""
        result = runner.invoke(app, ["agent", "--help"])
        assert result.exit_code == 0
        assert "run" in result.stdout.lower()
        assert "list" in result.stdout.lower()

    def test_agent_run_success(self, runner, mock_config):
        """Test agent run command succeeds."""
        mock_client = AsyncMock()
        mock_client.run_agent.return_value = {
            "trace_id": "trace123",
            "status": "completed",
            "task": "test task",
            "tool_calls": [{"id": "1"}, {"id": "2"}],
        }

        with patch(
            "cli.commands.agent_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["agent", "run", "test task"])
            assert result.exit_code == 0
            mock_client.run_agent.assert_called_once()

    def test_agent_run_with_scope(self, runner, mock_config):
        """Test agent run with permission scope."""
        mock_client = AsyncMock()
        mock_client.run_agent.return_value = {"status": "completed"}

        with patch(
            "cli.commands.agent_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["agent", "run", "task", "--scope", "read", "--scope", "write"],
            )
            assert result.exit_code == 0
            call_args = mock_client.run_agent.call_args
            assert "read" in call_args[1]["permission_scope"]
            assert "write" in call_args[1]["permission_scope"]

    def test_agent_run_with_context(self, runner, mock_config):
        """Test agent run with extra context."""
        mock_client = AsyncMock()
        mock_client.run_agent.return_value = {"status": "completed"}

        with patch(
            "cli.commands.agent_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["agent", "run", "task", "--context", '{"key": "value"}'],
            )
            assert result.exit_code == 0
            call_args = mock_client.run_agent.call_args
            assert call_args[1]["extra_context"]["key"] == "value"

    def test_agent_run_invalid_json_context(self, runner, mock_config):
        """Test agent run rejects invalid JSON context."""
        result = runner.invoke(
            app,
            ["agent", "run", "task", "--context", "invalid json"],
        )
        assert result.exit_code == 1

    def test_agent_run_connection_error(self, runner, mock_config):
        """Test agent run handles ConnectionError."""
        mock_client = AsyncMock()
        mock_client.run_agent.side_effect = ConnectionError("Failed to connect")

        with patch(
            "cli.commands.agent_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["agent", "run", "task"])
            assert result.exit_code == 1

    def test_agent_run_auth_error(self, runner, mock_config):
        """Test agent run handles AuthError."""
        mock_client = AsyncMock()
        mock_client.run_agent.side_effect = AuthError("Invalid API key")

        with patch(
            "cli.commands.agent_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["agent", "run", "task"])
            assert result.exit_code == 1

    def test_agent_list_success(self, runner, mock_config):
        """Test agent list command succeeds."""
        mock_client = AsyncMock()
        mock_client.list_agents.return_value = {
            "data": [
                {
                    "id": "agent1",
                    "name": "Agent 1",
                    "status": "active",
                    "capabilities": ["read", "write"],
                }
            ]
        }

        with patch(
            "cli.commands.agent_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["agent", "list"])
            assert result.exit_code == 0
            assert "agent1" in result.stdout or "Agent 1" in result.stdout

    def test_agent_list_empty(self, runner, mock_config):
        """Test agent list with no agents."""
        mock_client = AsyncMock()
        mock_client.list_agents.return_value = {"data": []}

        with patch(
            "cli.commands.agent_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["agent", "list"])
            assert result.exit_code == 0


class TestToolsCommands:
    """Test tools subcommand group."""

    def test_tools_help(self, runner):
        """Test tools --help shows subcommands."""
        result = runner.invoke(app, ["tools", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout.lower()

    def test_tools_list_success(self, runner, mock_config):
        """Test tools list command succeeds."""
        mock_client = AsyncMock()
        mock_client.list_tools.return_value = [
            {
                "name": "tool1",
                "description": "Tool 1 description",
                "category": "utility",
                "status": "active",
            }
        ]

        with patch(
            "cli.commands.tools_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["tools", "list"])
            assert result.exit_code == 0
            assert "tool1" in result.stdout or "Tool 1" in result.stdout

    def test_tools_list_empty(self, runner, mock_config):
        """Test tools list with no tools."""
        mock_client = AsyncMock()
        mock_client.list_tools.return_value = []

        with patch(
            "cli.commands.tools_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["tools", "list"])
            assert result.exit_code == 0

    def test_tools_list_api_error(self, runner, mock_config):
        """Test tools list handles APIError."""
        mock_client = AsyncMock()
        mock_client.list_tools.side_effect = APIError("API error")

        with patch(
            "cli.commands.tools_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["tools", "list"])
            assert result.exit_code == 1


class TestWorkflowCommands:
    """Test workflow subcommand group."""

    def test_workflow_help(self, runner):
        """Test workflow --help shows subcommands."""
        result = runner.invoke(app, ["workflow", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout.lower()
        assert "create" in result.stdout.lower()
        assert "run" in result.stdout.lower()

    def test_workflow_list_success(self, runner, mock_config):
        """Test workflow list command succeeds."""
        mock_client = AsyncMock()
        mock_client.list_workflows.return_value = [
            {
                "id": "wf1",
                "name": "Workflow 1",
                "nodes": [{"id": "n1"}],
                "edges": [{"id": "e1"}],
                "status": "draft",
            }
        ]

        with patch(
            "cli.commands.workflow_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["workflow", "list"])
            assert result.exit_code == 0

    def test_workflow_create_from_spec_string(self, runner, mock_config):
        """Test workflow create with JSON spec string."""
        mock_client = AsyncMock()
        mock_client.create_workflow.return_value = {
            "id": "wf123",
            "name": "test-wf",
            "status": "created",
        }

        with patch(
            "cli.commands.workflow_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["workflow", "create", "--spec", '{"name": "test-wf", "nodes": []}'],
            )
            assert result.exit_code == 0
            mock_client.create_workflow.assert_called_once()

    def test_workflow_create_invalid_json(self, runner, mock_config):
        """Test workflow create rejects invalid JSON."""
        result = runner.invoke(
            app,
            ["workflow", "create", "--spec", "invalid json"],
        )
        assert result.exit_code == 1

    def test_workflow_create_no_spec_or_file(self, runner, mock_config):
        """Test workflow create requires spec or file."""
        result = runner.invoke(app, ["workflow", "create"])
        assert result.exit_code == 1

    def test_workflow_run_success(self, runner, mock_config):
        """Test workflow run command succeeds."""
        mock_client = AsyncMock()
        mock_client.run_workflow.return_value = {
            "run_id": "run123",
            "workflow_id": "wf123",
            "status": "running",
        }

        with patch(
            "cli.commands.workflow_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["workflow", "run", "wf123"])
            assert result.exit_code == 0
            mock_client.run_workflow.assert_called_once()

    def test_workflow_run_with_inputs(self, runner, mock_config):
        """Test workflow run with inputs."""
        mock_client = AsyncMock()
        mock_client.run_workflow.return_value = {"run_id": "run123"}

        with patch(
            "cli.commands.workflow_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["workflow", "run", "wf123", "--inputs", '{"param": "value"}'],
            )
            assert result.exit_code == 0
            call_args = mock_client.run_workflow.call_args
            assert call_args[1]["inputs"]["param"] == "value"

    def test_workflow_status_success(self, runner, mock_config):
        """Test workflow status command succeeds."""
        mock_client = AsyncMock()
        mock_client.get_workflow_status.return_value = {
            "workflow_id": "wf123",
            "status": "completed",
            "run_count": 5,
        }

        with patch(
            "cli.commands.workflow_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["workflow", "status", "wf123"])
            assert result.exit_code == 0


class TestInitCommands:
    """Test init subcommand group."""

    def test_init_help(self, runner):
        """Test init --help shows subcommands."""
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "setup" in result.stdout.lower()
        assert "project" in result.stdout.lower()

    def test_init_setup_non_interactive(self, runner, mock_config):
        """Test init setup with non-interactive mode."""
        with patch("cli.commands.init_cmd.save_config"):
            result = runner.invoke(
                app,
                [
                    "init",
                    "setup",
                    "--no-interactive",
                    "--api-url",
                    "http://api.example.com",
                ],
            )
            assert result.exit_code == 0

    def test_init_project_creates_structure(self, runner, mock_config):
        """Test init project creates directory structure."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                ["init", "project", "--path", tmpdir, "--name", "test-project"],
            )
            assert result.exit_code == 0

            project_path = Path(tmpdir)
            assert (project_path / ".xagent").exists()
            assert (project_path / "workflows").exists()
            assert (project_path / "tools").exists()
            assert (project_path / "data").exists()


class TestErrorHandling:
    """Test error handling across commands."""

    def test_command_with_xagent_cli_error(self, runner, mock_config):
        """Test command handles XAgentCLIError."""
        mock_client = AsyncMock()
        mock_client.run_agent.side_effect = XAgentCLIError("CLI error")

        with patch(
            "cli.commands.agent_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["agent", "run", "task"])
            assert result.exit_code == 1

    def test_command_with_unexpected_error(self, runner, mock_config):
        """Test command handles unexpected errors."""
        mock_client = AsyncMock()
        mock_client.run_agent.side_effect = RuntimeError("Unexpected error")

        with patch(
            "cli.commands.agent_cmd.create_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["agent", "run", "task"])
            assert result.exit_code == 1
