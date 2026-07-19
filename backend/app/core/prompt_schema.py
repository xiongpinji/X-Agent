"""Prompt schema and models for X-Agent prompt engineering platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PromptInput:
    """Input specification for a prompt."""
    name: str
    type: str  # "string", "list", "dict", "object"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class PromptOutput:
    """Output specification for a prompt."""
    name: str
    type: str  # "string", "list", "dict", "object"
    description: str


@dataclass
class PromptExample:
    """Example usage of a prompt."""
    input: dict[str, Any]
    output: str
    description: str = ""


@dataclass
class PromptMetadata:
    """Metadata for a prompt."""
    id: str
    name: str
    version: str  # semantic versioning: major.minor.patch
    purpose: str
    scope: str  # "system", "role", "tool", "recovery", "audit", "memory", "marketplace", "navigation"
    description: str = ""
    owner: str = "x-agent"
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deprecated: bool = False
    deprecation_reason: str = ""


@dataclass
class PromptConstraint:
    """Constraint for prompt execution."""
    name: str
    description: str
    severity: str  # "error", "warning", "info"


@dataclass
class PromptSchema:
    """Complete schema for a prompt."""
    metadata: PromptMetadata
    content: str  # The actual prompt text
    inputs: list[PromptInput] = field(default_factory=list)
    outputs: list[PromptOutput] = field(default_factory=list)
    constraints: list[PromptConstraint] = field(default_factory=list)
    examples: list[PromptExample] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # Other prompt IDs this depends on
    variables: dict[str, str] = field(default_factory=dict)  # Template variables

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": {
                "id": self.metadata.id,
                "name": self.metadata.name,
                "version": self.metadata.version,
                "purpose": self.metadata.purpose,
                "scope": self.metadata.scope,
                "description": self.metadata.description,
                "owner": self.metadata.owner,
                "tags": self.metadata.tags,
                "created_at": self.metadata.created_at.isoformat(),
                "updated_at": self.metadata.updated_at.isoformat(),
                "deprecated": self.metadata.deprecated,
                "deprecation_reason": self.metadata.deprecation_reason,
            },
            "content": self.content,
            "inputs": [
                {
                    "name": inp.name,
                    "type": inp.type,
                    "description": inp.description,
                    "required": inp.required,
                    "default": inp.default,
                }
                for inp in self.inputs
            ],
            "outputs": [
                {
                    "name": out.name,
                    "type": out.type,
                    "description": out.description,
                }
                for out in self.outputs
            ],
            "constraints": [
                {
                    "name": c.name,
                    "description": c.description,
                    "severity": c.severity,
                }
                for c in self.constraints
            ],
            "examples": [
                {
                    "input": ex.input,
                    "output": ex.output,
                    "description": ex.description,
                }
                for ex in self.examples
            ],
            "dependencies": self.dependencies,
            "variables": self.variables,
        }
