"""Prompt integration for agent execution pipeline."""

from __future__ import annotations

from typing import Any

from backend.app.core.prompt_registry import prompt_registry
from backend.app.core.prompt_schema import PromptSchema


class PromptContext:
    """Context for prompt execution with variable substitution."""

    def __init__(self, prompt: PromptSchema, variables: dict[str, Any] = None):
        """Initialize prompt context."""
        self.prompt = prompt
        self.variables = variables or {}
        self.rendered_content = None

    def render(self) -> str:
        """Render prompt with variables substituted."""
        if self.rendered_content is None:
            from backend.app.core.prompt_loader import prompt_loader
            self.rendered_content = prompt_loader.substitute_variables(
                self.prompt, self.variables
            )
        return self.rendered_content

    def get_metadata(self) -> dict[str, Any]:
        """Get prompt metadata."""
        return {
            "id": self.prompt.metadata.id,
            "name": self.prompt.metadata.name,
            "version": self.prompt.metadata.version,
            "scope": self.prompt.metadata.scope,
            "purpose": self.prompt.metadata.purpose,
        }


class PromptManager:
    """Manages prompt loading and execution in the agent pipeline."""

    def __init__(self):
        """Initialize prompt manager."""
        self.registry = prompt_registry
        self._loaded = False

    def initialize(self, base_path: str = None) -> int:
        """Initialize and load all prompts."""
        if self._loaded:
            return 0

        loaded = self.registry.load_from_directory(base_path)
        self._loaded = True
        return loaded

    def get_system_prompt(self, variables: dict[str, Any] = None) -> PromptContext:
        """Get the system prompt for agent initialization."""
        prompt = self.registry.get_prompt("agent_system")
        if not prompt:
            raise ValueError("System prompt 'agent_system' not found")
        return PromptContext(prompt, variables or {})

    def get_role_prompt(self, role: str, variables: dict[str, Any] = None) -> PromptContext:
        """Get a role-specific prompt."""
        prompt_id = f"{role}_role"
        prompt = self.registry.get_prompt(prompt_id)
        if not prompt:
            # Try alternative naming
            prompt = self.registry.get_prompt(role)
        if not prompt:
            raise ValueError(f"Role prompt '{role}' not found")
        return PromptContext(prompt, variables or {})

    def get_tool_prompt(self, tool_name: str, variables: dict[str, Any] = None) -> PromptContext:
        """Get a tool-specific prompt."""
        prompt_id = f"{tool_name}_tool"
        prompt = self.registry.get_prompt(prompt_id)
        if not prompt:
            # Try alternative naming
            prompt = self.registry.get_prompt(tool_name)
        if not prompt:
            raise ValueError(f"Tool prompt '{tool_name}' not found")
        return PromptContext(prompt, variables or {})

    def get_recovery_prompt(self, recovery_type: str, variables: dict[str, Any] = None) -> PromptContext:
        """Get a recovery-specific prompt."""
        prompt_id = f"{recovery_type}_recovery"
        prompt = self.registry.get_prompt(prompt_id)
        if not prompt:
            # Try alternative naming
            prompt = self.registry.get_prompt(recovery_type)
        if not prompt:
            raise ValueError(f"Recovery prompt '{recovery_type}' not found")
        return PromptContext(prompt, variables or {})

    def get_prompts_by_scope(self, scope: str) -> list[PromptContext]:
        """Get all prompts in a scope."""
        prompts = self.registry.get_prompts_by_scope(scope)
        return [PromptContext(p) for p in prompts]

    def build_messages(self, system_prompt: PromptContext, user_message: str,
                      role_prompt: PromptContext = None) -> list[dict[str, str]]:
        """Build message list for LLM call."""
        messages = []

        # Add system prompt
        messages.append({
            "role": "system",
            "content": system_prompt.render(),
        })

        # Add role prompt if provided
        if role_prompt:
            messages.append({
                "role": "system",
                "content": f"Role: {role_prompt.render()}",
            })

        # Add user message
        messages.append({
            "role": "user",
            "content": user_message,
        })

        return messages

    def validate_all_prompts(self) -> tuple[int, int]:
        """Validate all registered prompts."""
        prompts = self.registry.list_all_prompts()
        valid_count = 0
        invalid_count = 0

        for prompt in prompts:
            is_valid, errors = self.registry.validate_prompt(prompt)
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                print(f"Invalid prompt {prompt.metadata.id}: {errors}")

        return valid_count, invalid_count


# Global prompt manager instance
prompt_manager = PromptManager()
