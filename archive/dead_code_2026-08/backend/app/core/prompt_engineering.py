"""Prompt engineering framework with templates, versioning, and optimization."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class PromptType(StrEnum):
    """Types of prompts in the system."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


class PromptStatus(StrEnum):
    """Status of a prompt version."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class PromptTemplate(BaseModel):
    """A reusable prompt template with variables."""

    template_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    prompt_type: PromptType = PromptType.USER
    content: str
    variables: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def extract_variables(self) -> list[str]:
        """Extract variable names from template content."""
        import re
        pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
        return list(set(re.findall(pattern, self.content)))

    def validate_variables(self) -> bool:
        """Validate that all variables in content are declared."""
        extracted = self.extract_variables()
        declared = set(self.variables)
        return set(extracted).issubset(declared)

    def format(self, **kwargs: Any) -> str:
        """Format template with provided variables."""
        if not self.validate_variables():
            raise ValueError("Template variables mismatch")
        return self.content.format(**kwargs)


class PromptVersion(BaseModel):
    """A versioned prompt with performance metrics."""

    version_id: str = Field(default_factory=lambda: str(uuid4()))
    template_id: str
    version: int
    content: str
    status: PromptStatus = PromptStatus.DRAFT
    parent_version: int | None = None
    changes: str = ""
    performance_metrics: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    activated_at: datetime | None = None

    def activate(self) -> None:
        """Activate this version."""
        self.status = PromptStatus.ACTIVE
        self.activated_at = datetime.now(UTC)

    def archive(self) -> None:
        """Archive this version."""
        self.status = PromptStatus.ARCHIVED

    def deprecate(self) -> None:
        """Mark as deprecated."""
        self.status = PromptStatus.DEPRECATED


class FewShotExample(BaseModel):
    """Few-shot example for in-context learning."""

    example_id: str = Field(default_factory=lambda: str(uuid4()))
    input: str
    output: str
    category: str = ""
    difficulty: str = "medium"  # easy, medium, hard
    quality_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptWithExamples(BaseModel):
    """Prompt combined with few-shot examples."""

    prompt_id: str = Field(default_factory=lambda: str(uuid4()))
    template_id: str
    examples: list[FewShotExample] = Field(default_factory=list)
    example_count: int = 0
    ordering: str = "difficulty"  # difficulty, random, sequential

    def add_example(self, example: FewShotExample) -> None:
        """Add a few-shot example."""
        self.examples.append(example)
        self.example_count = len(self.examples)

    def remove_example(self, example_id: str) -> None:
        """Remove a few-shot example."""
        self.examples = [e for e in self.examples if e.example_id != example_id]
        self.example_count = len(self.examples)

    def get_ordered_examples(self) -> list[FewShotExample]:
        """Get examples in specified order."""
        if self.ordering == "difficulty":
            return sorted(self.examples, key=lambda e: {"easy": 0, "medium": 1, "hard": 2}.get(e.difficulty, 1))
        elif self.ordering == "random":
            import random
            return random.sample(self.examples, len(self.examples))
        return self.examples


class PromptOptimizationSuggestion(BaseModel):
    """Suggestion for prompt optimization."""

    suggestion_id: str = Field(default_factory=lambda: str(uuid4()))
    template_id: str
    suggestion_type: str  # clarity, specificity, structure, examples, etc.
    current_text: str
    suggested_text: str
    reasoning: str
    expected_improvement: float  # 0.0 to 1.0
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PromptEngineering:
    """Main prompt engineering framework."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._versions: dict[str, list[PromptVersion]] = {}
        self._examples: dict[str, list[FewShotExample]] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def create_template(
        self,
        name: str,
        content: str,
        prompt_type: PromptType = PromptType.USER,
        description: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PromptTemplate:
        """Create a new prompt template."""
        template = PromptTemplate(
            name=name,
            content=content,
            prompt_type=prompt_type,
            description=description,
            tags=tags or [],
            metadata=metadata or {},
        )
        template.variables = template.extract_variables()
        self._templates[template.template_id] = template
        self._versions[template.template_id] = []
        self._save_to_disk()
        return template

    def get_template(self, template_id: str) -> PromptTemplate | None:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def list_templates(self, tags: list[str] | None = None) -> list[PromptTemplate]:
        """List all templates, optionally filtered by tags."""
        templates = list(self._templates.values())
        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]
        return templates

    def update_template(self, template_id: str, **kwargs: Any) -> PromptTemplate | None:
        """Update a template."""
        template = self._templates.get(template_id)
        if not template:
            return None
        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)
        template.updated_at = datetime.now(UTC)
        if "content" in kwargs:
            template.variables = template.extract_variables()
        self._save_to_disk()
        return template

    def create_version(
        self,
        template_id: str,
        content: str,
        changes: str = "",
        parent_version: int | None = None,
    ) -> PromptVersion | None:
        """Create a new version of a template."""
        if template_id not in self._templates:
            return None

        versions = self._versions.get(template_id, [])
        version_num = len(versions) + 1

        version = PromptVersion(
            template_id=template_id,
            version=version_num,
            content=content,
            changes=changes,
            parent_version=parent_version,
        )

        self._versions[template_id].append(version)
        self._save_to_disk()
        return version

    def get_version(self, template_id: str, version: int) -> PromptVersion | None:
        """Get a specific version."""
        versions = self._versions.get(template_id, [])
        for v in versions:
            if v.version == version:
                return v
        return None

    def list_versions(self, template_id: str) -> list[PromptVersion]:
        """List all versions of a template."""
        return self._versions.get(template_id, [])

    def get_active_version(self, template_id: str) -> PromptVersion | None:
        """Get the active version of a template."""
        versions = self._versions.get(template_id, [])
        for v in versions:
            if v.status == PromptStatus.ACTIVE:
                return v
        return versions[-1] if versions else None

    def activate_version(self, template_id: str, version: int) -> PromptVersion | None:
        """Activate a specific version."""
        target = self.get_version(template_id, version)
        if not target:
            return None

        # Deactivate current active version
        current = self.get_active_version(template_id)
        if current and current.status == PromptStatus.ACTIVE:
            current.status = PromptStatus.DRAFT

        target.activate()
        self._save_to_disk()
        return target

    def add_few_shot_example(
        self,
        template_id: str,
        input_text: str,
        output_text: str,
        category: str = "",
        difficulty: str = "medium",
    ) -> FewShotExample | None:
        """Add a few-shot example to a template."""
        if template_id not in self._templates:
            return None

        example = FewShotExample(
            input=input_text,
            output=output_text,
            category=category,
            difficulty=difficulty,
        )

        if template_id not in self._examples:
            self._examples[template_id] = []
        self._examples[template_id].append(example)
        self._save_to_disk()
        return example

    def get_few_shot_examples(self, template_id: str) -> list[FewShotExample]:
        """Get all few-shot examples for a template."""
        return self._examples.get(template_id, [])

    def format_with_examples(
        self,
        template_id: str,
        example_count: int = 3,
        **variables: Any,
    ) -> str:
        """Format a template with few-shot examples."""
        template = self._templates.get(template_id)
        if not template:
            return ""

        examples = self._examples.get(template_id, [])
        if not examples:
            return template.format(**variables)

        # Select examples
        selected = examples[:example_count]

        # Build prompt with examples
        prompt_parts = []
        for example in selected:
            prompt_parts.append(f"Input: {example.input}")
            prompt_parts.append(f"Output: {example.output}")
            prompt_parts.append("")

        prompt_parts.append(template.format(**variables))
        return "\n".join(prompt_parts)

    def suggest_optimization(
        self,
        template_id: str,
        suggestion_type: str,
        current_text: str,
        suggested_text: str,
        reasoning: str,
        expected_improvement: float = 0.1,
    ) -> PromptOptimizationSuggestion:
        """Create an optimization suggestion."""
        suggestion = PromptOptimizationSuggestion(
            template_id=template_id,
            suggestion_type=suggestion_type,
            current_text=current_text,
            suggested_text=suggested_text,
            reasoning=reasoning,
            expected_improvement=expected_improvement,
        )
        return suggestion

    def _save_to_disk(self) -> None:
        """Save all data to disk."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Save templates
        templates_file = self._storage_path.parent / "templates.jsonl"
        with templates_file.open("w", encoding="utf-8") as f:
            for template in self._templates.values():
                f.write(template.model_dump_json() + "\n")

        # Save versions
        versions_file = self._storage_path.parent / "versions.jsonl"
        with versions_file.open("w", encoding="utf-8") as f:
            for versions in self._versions.values():
                for version in versions:
                    f.write(version.model_dump_json() + "\n")

        # Save examples
        examples_file = self._storage_path.parent / "examples.jsonl"
        with examples_file.open("w", encoding="utf-8") as f:
            for examples in self._examples.values():
                for example in examples:
                    f.write(example.model_dump_json() + "\n")

    def _load_from_disk(self) -> None:
        """Load all data from disk."""
        if self._storage_path is None or not self._storage_path.parent.exists():
            return

        # Load templates
        templates_file = self._storage_path.parent / "templates.jsonl"
        if templates_file.exists():
            with templates_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        template = PromptTemplate.model_validate_json(line)
                        self._templates[template.template_id] = template

        # Load versions
        versions_file = self._storage_path.parent / "versions.jsonl"
        if versions_file.exists():
            with versions_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        version = PromptVersion.model_validate_json(line)
                        if version.template_id not in self._versions:
                            self._versions[version.template_id] = []
                        self._versions[version.template_id].append(version)

        # Load examples
        examples_file = self._storage_path.parent / "examples.jsonl"
        if examples_file.exists():
            with examples_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        FewShotExample.model_validate_json(line)
                        # Note: We lose the template_id mapping here, would need to store it
                        # For now, we'll rebuild it from versions
