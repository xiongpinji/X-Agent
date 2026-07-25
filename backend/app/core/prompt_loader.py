"""Prompt loader with file loading, variable substitution, and version management."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.app.core.prompt_schema import (
    PromptConstraint,
    PromptExample,
    PromptInput,
    PromptMetadata,
    PromptOutput,
    PromptSchema,
)


class PromptVersionManager:
    """Manages prompt versioning with semantic versioning support."""

    @staticmethod
    def parse_version(version: str) -> tuple[int, int, int]:
        """Parse semantic version string to tuple."""
        parts = version.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version}. Expected major.minor.patch")
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError as e:
            raise ValueError(f"Version parts must be integers: {version}") from e

    @staticmethod
    def increment_version(version: str, level: str = "patch") -> str:
        """Increment version by level: major, minor, or patch."""
        major, minor, patch = PromptVersionManager.parse_version(version)
        if level == "major":
            return f"{major + 1}.0.0"
        elif level == "minor":
            return f"{major}.{minor + 1}.0"
        elif level == "patch":
            return f"{major}.{minor}.{patch + 1}"
        else:
            raise ValueError(f"Invalid increment level: {level}")

    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """Compare two versions. Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2."""
        major1, minor1, patch1 = PromptVersionManager.parse_version(v1)
        major2, minor2, patch2 = PromptVersionManager.parse_version(v2)

        if (major1, minor1, patch1) < (major2, minor2, patch2):
            return -1
        elif (major1, minor1, patch1) > (major2, minor2, patch2):
            return 1
        return 0


class PromptLoader:
    """Loads prompts from files with variable substitution and validation."""

    def __init__(self, base_path: str | Path | None = None):
        """Initialize loader with optional base path."""
        self.base_path = Path(base_path) if base_path else Path(__file__).parent.parent.parent / "prompts"
        self._cache: dict[str, PromptSchema] = {}
        self._version_history: dict[str, list[str]] = {}

    def load_from_file(self, file_path: str | Path) -> PromptSchema:
        """Load prompt from a markdown or JSON file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        if file_path.suffix == ".md":
            return self._load_from_markdown(file_path)
        elif file_path.suffix == ".json":
            return self._load_from_json(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

    def _load_from_markdown(self, file_path: Path) -> PromptSchema:
        """Load prompt from markdown file with YAML frontmatter."""
        content = file_path.read_text(encoding="utf-8")

        # Parse frontmatter
        if not content.startswith("---"):
            raise ValueError(f"Markdown prompt must start with YAML frontmatter: {file_path}")

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid markdown format in {file_path}")

        import yaml
        try:
            metadata_dict = yaml.safe_load(parts[1])
        except Exception as e:
            raise ValueError(f"Invalid YAML frontmatter in {file_path}: {e}") from e

        prompt_content = parts[2].strip()

        # Build metadata
        metadata = PromptMetadata(
            id=metadata_dict.get("id", file_path.stem),
            name=metadata_dict.get("name", file_path.stem),
            version=metadata_dict.get("version", "1.0.0"),
            purpose=metadata_dict.get("purpose", ""),
            scope=metadata_dict.get("scope", "system"),
            description=metadata_dict.get("description", ""),
            owner=metadata_dict.get("owner", "x-agent"),
            tags=metadata_dict.get("tags", []),
            deprecated=metadata_dict.get("deprecated", False),
            deprecation_reason=metadata_dict.get("deprecation_reason", ""),
        )

        # Parse inputs, outputs, constraints, examples from content
        inputs = self._parse_section(prompt_content, "inputs", PromptInput)
        outputs = self._parse_section(prompt_content, "outputs", PromptOutput)
        constraints = self._parse_section(prompt_content, "constraints", PromptConstraint)
        examples = self._parse_examples(prompt_content)

        schema = PromptSchema(
            metadata=metadata,
            content=prompt_content,
            inputs=inputs,
            outputs=outputs,
            constraints=constraints,
            examples=examples,
            dependencies=metadata_dict.get("dependencies", []),
            variables=metadata_dict.get("variables", {}),
        )

        self._cache[metadata.id] = schema
        return schema

    def _load_from_json(self, file_path: Path) -> PromptSchema:
        """Load prompt from JSON file."""
        data = json.loads(file_path.read_text(encoding="utf-8"))

        metadata_dict = data.get("metadata", {})
        metadata = PromptMetadata(
            id=metadata_dict.get("id", file_path.stem),
            name=metadata_dict.get("name", file_path.stem),
            version=metadata_dict.get("version", "1.0.0"),
            purpose=metadata_dict.get("purpose", ""),
            scope=metadata_dict.get("scope", "system"),
            description=metadata_dict.get("description", ""),
            owner=metadata_dict.get("owner", "x-agent"),
            tags=metadata_dict.get("tags", []),
            deprecated=metadata_dict.get("deprecated", False),
            deprecation_reason=metadata_dict.get("deprecation_reason", ""),
        )

        inputs = [
            PromptInput(
                name=inp["name"],
                type=inp.get("type", "string"),
                description=inp.get("description", ""),
                required=inp.get("required", True),
                default=inp.get("default"),
            )
            for inp in data.get("inputs", [])
        ]

        outputs = [
            PromptOutput(
                name=out["name"],
                type=out.get("type", "string"),
                description=out.get("description", ""),
            )
            for out in data.get("outputs", [])
        ]

        constraints = [
            PromptConstraint(
                name=c["name"],
                description=c.get("description", ""),
                severity=c.get("severity", "warning"),
            )
            for c in data.get("constraints", [])
        ]

        examples = [
            PromptExample(
                input=ex.get("input", {}),
                output=ex.get("output", ""),
                description=ex.get("description", ""),
            )
            for ex in data.get("examples", [])
        ]

        schema = PromptSchema(
            metadata=metadata,
            content=data.get("content", ""),
            inputs=inputs,
            outputs=outputs,
            constraints=constraints,
            examples=examples,
            dependencies=data.get("dependencies", []),
            variables=data.get("variables", {}),
        )

        self._cache[metadata.id] = schema
        return schema

    def substitute_variables(self, prompt: PromptSchema, variables: dict[str, Any]) -> str:
        """Substitute variables in prompt content."""
        content = prompt.content

        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, str(value))

        return content

    def get_prompt(self, prompt_id: str) -> PromptSchema | None:
        """Get cached prompt by ID."""
        return self._cache.get(prompt_id)

    def register_version(self, prompt_id: str, version: str) -> None:
        """Register a new version for a prompt."""
        if prompt_id not in self._version_history:
            self._version_history[prompt_id] = []

        if version not in self._version_history[prompt_id]:
            self._version_history[prompt_id].append(version)
            self._version_history[prompt_id].sort(
                key=lambda v: PromptVersionManager.parse_version(v)
            )

    def get_version_history(self, prompt_id: str) -> list[str]:
        """Get version history for a prompt."""
        return self._version_history.get(prompt_id, [])

    @staticmethod
    def _parse_section(content: str, section_name: str, item_class) -> list:
        """Parse a section from markdown content."""
        pattern = rf"## {section_name.capitalize()}\n(.*?)(?=##|\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if not match:
            return []

        section_content = match.group(1)
        items = []

        for line in section_content.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                # Parse list item
                item_text = line[2:].strip()
                if item_class == PromptInput:
                    parts = item_text.split(":", 1)
                    if len(parts) == 2:
                        items.append(PromptInput(
                            name=parts[0].strip(),
                            type="string",
                            description=parts[1].strip(),
                        ))
                elif item_class == PromptOutput:
                    parts = item_text.split(":", 1)
                    if len(parts) == 2:
                        items.append(PromptOutput(
                            name=parts[0].strip(),
                            type="string",
                            description=parts[1].strip(),
                        ))
                elif item_class == PromptConstraint:
                    parts = item_text.split(":", 1)
                    if len(parts) == 2:
                        items.append(PromptConstraint(
                            name=parts[0].strip(),
                            description=parts[1].strip(),
                            severity="warning",
                        ))

        return items

    @staticmethod
    def _parse_examples(content: str) -> list[PromptExample]:
        """Parse examples from markdown content."""
        pattern = r"## Examples\n(.*?)(?=##|\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if not match:
            return []

        examples = []
        section_content = match.group(1)

        # Simple example parsing - can be enhanced
        example_blocks = re.findall(r"### Example.*?\n(.*?)(?=###|\Z)", section_content, re.DOTALL)
        for block in example_blocks:
            examples.append(PromptExample(
                input={},
                output=block.strip(),
                description="",
            ))

        return examples


# Global loader instance
prompt_loader = PromptLoader()
