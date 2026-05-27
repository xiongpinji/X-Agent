"""Prompt registry for managing and accessing prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.core.prompt_schema import PromptSchema
from backend.app.core.prompt_loader import prompt_loader, PromptVersionManager


class PromptRegistry:
    """Central registry for all prompts in the system."""

    def __init__(self, base_path: str | Path = None):
        """Initialize registry with optional base path."""
        self.base_path = Path(base_path) if base_path else Path(__file__).parent.parent.parent / "prompts"
        self._prompts: dict[str, PromptSchema] = {}
        self._scopes: dict[str, list[str]] = {}
        self._version_manager = PromptVersionManager()

    def register_prompt(self, prompt: PromptSchema) -> None:
        """Register a prompt in the registry."""
        prompt_id = prompt.metadata.id
        self._prompts[prompt_id] = prompt

        # Index by scope
        scope = prompt.metadata.scope
        if scope not in self._scopes:
            self._scopes[scope] = []
        if prompt_id not in self._scopes[scope]:
            self._scopes[scope].append(prompt_id)

        # Register version
        prompt_loader.register_version(prompt_id, prompt.metadata.version)

    def get_prompt(self, prompt_id: str, version: str = None) -> PromptSchema | None:
        """Get a prompt by ID and optional version."""
        prompt = self._prompts.get(prompt_id)
        if not prompt:
            return None

        if version and prompt.metadata.version != version:
            # Could implement version history lookup here
            return None

        return prompt

    def get_prompts_by_scope(self, scope: str) -> list[PromptSchema]:
        """Get all prompts in a specific scope."""
        prompt_ids = self._scopes.get(scope, [])
        return [self._prompts[pid] for pid in prompt_ids if pid in self._prompts]

    def list_all_prompts(self) -> list[PromptSchema]:
        """List all registered prompts."""
        return list(self._prompts.values())

    def load_from_directory(self, directory: str | Path = None) -> int:
        """Load all prompts from a directory structure."""
        if directory is None:
            directory = self.base_path

        directory = Path(directory)
        if not directory.exists():
            return 0

        loaded_count = 0
        for scope_dir in directory.iterdir():
            if not scope_dir.is_dir():
                continue

            for prompt_file in scope_dir.glob("*.md"):
                try:
                    prompt = prompt_loader.load_from_file(prompt_file)
                    self.register_prompt(prompt)
                    loaded_count += 1
                except Exception as e:
                    print(f"Failed to load prompt from {prompt_file}: {e}")

            for prompt_file in scope_dir.glob("*.json"):
                try:
                    prompt = prompt_loader.load_from_file(prompt_file)
                    self.register_prompt(prompt)
                    loaded_count += 1
                except Exception as e:
                    print(f"Failed to load prompt from {prompt_file}: {e}")

        return loaded_count

    def get_version_history(self, prompt_id: str) -> list[str]:
        """Get version history for a prompt."""
        return prompt_loader.get_version_history(prompt_id)

    def substitute_variables(self, prompt_id: str, variables: dict[str, Any]) -> str | None:
        """Get prompt content with variables substituted."""
        prompt = self.get_prompt(prompt_id)
        if not prompt:
            return None

        return prompt_loader.substitute_variables(prompt, variables)

    def validate_prompt(self, prompt: PromptSchema) -> tuple[bool, list[str]]:
        """Validate a prompt schema."""
        errors = []

        if not prompt.metadata.id:
            errors.append("Prompt ID is required")
        if not prompt.metadata.name:
            errors.append("Prompt name is required")
        if not prompt.metadata.version:
            errors.append("Prompt version is required")
        else:
            try:
                self._version_manager.parse_version(prompt.metadata.version)
            except ValueError as e:
                errors.append(f"Invalid version format: {e}")

        if not prompt.metadata.purpose:
            errors.append("Prompt purpose is required")
        if not prompt.metadata.scope:
            errors.append("Prompt scope is required")

        if prompt.content and len(prompt.content) < 10:
            errors.append("Prompt content is too short")

        return len(errors) == 0, errors

    def export_prompt(self, prompt_id: str, format: str = "json") -> str | None:
        """Export a prompt in specified format."""
        prompt = self.get_prompt(prompt_id)
        if not prompt:
            return None

        if format == "json":
            import json
            return json.dumps(prompt.to_dict(), indent=2, default=str)
        elif format == "markdown":
            return self._export_as_markdown(prompt)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    @staticmethod
    def _export_as_markdown(prompt: PromptSchema) -> str:
        """Export prompt as markdown."""
        lines = [
            "---",
            f"id: {prompt.metadata.id}",
            f"name: {prompt.metadata.name}",
            f"version: {prompt.metadata.version}",
            f"purpose: {prompt.metadata.purpose}",
            f"scope: {prompt.metadata.scope}",
            f"description: {prompt.metadata.description}",
            f"owner: {prompt.metadata.owner}",
            f"tags: {prompt.metadata.tags}",
            f"deprecated: {prompt.metadata.deprecated}",
            "---",
            "",
            prompt.content,
        ]
        return "\n".join(lines)


# Global registry instance
prompt_registry = PromptRegistry()
