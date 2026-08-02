"""CLI command modules.

Exports all command app instances for mounting in main.py.
"""

from cli.commands.agent_cmd import agent_app
from cli.commands.approvals_cmd import approvals_app
from cli.commands.chat_cmd import chat_app
from cli.commands.gateway_cmd import gateway_app
from cli.commands.github_cmd import github_app
from cli.commands.hooks_cmd import hooks_app
from cli.commands.init_cmd import init_app
from cli.commands.memory_cmd import memory_app
from cli.commands.review_cmd import review_app
from cli.commands.skill_cmd import skill_app
from cli.commands.tools_cmd import tools_app
from cli.commands.workflow_cmd import workflow_app

__all__ = [
    "agent_app",
    "approvals_app",
    "chat_app",
    "gateway_app",
    "github_app",
    "hooks_app",
    "init_app",
    "memory_app",
    "review_app",
    "skill_app",
    "tools_app",
    "workflow_app",
]
