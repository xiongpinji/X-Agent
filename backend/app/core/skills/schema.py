"""Pydantic schemas for skill definitions and execution."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class SkillStep(BaseModel):
    """A single step in a skill workflow.

    Represents a task to execute, which may involve calling a tool,
    running an LLM, or performing conditional logic.

    Attributes:
        id: Unique identifier for this step within the skill
        tool: Name of the tool to invoke from tool_registry
        args: Static arguments to pass to the tool
        prompt: For LLM tools, the prompt to send to the model
        foreach: Expression to iterate over (e.g., "{{steps.read_files.output}}")
        condition: Boolean expression to skip step if false
        output_var: Variable name to store step result (e.g., "my_result")
    """

    id: str = Field(..., description="Unique step identifier")
    tool: str = Field(..., description="Tool name from tool_registry")
    args: dict[str, Any] = Field(default_factory=dict, description="Static tool arguments")
    prompt: Optional[str] = Field(None, description="LLM prompt for this step")
    foreach: Optional[str] = Field(None, description="Iterate over expression")
    condition: Optional[str] = Field(None, description="Skip if condition is false")
    output_var: Optional[str] = Field(None, description="Store result in this variable")


class SkillTrigger(BaseModel):
    """How a skill can be invoked.

    Supports event-driven (webhook), command-line, and scheduled triggers.

    Attributes:
        event: Webhook event name (e.g., "push", "pull_request")
        command: CLI command to trigger skill (e.g., "review-code")
        schedule: Cron expression for scheduled execution
    """

    event: Optional[str] = Field(None, description="Webhook event name")
    command: Optional[str] = Field(None, description="CLI command")
    schedule: Optional[str] = Field(None, description="Cron expression (minute hour day month dow)")


class SkillInput(BaseModel):
    """Input parameter for a skill.

    Describes what inputs the skill accepts and how to validate them.

    Attributes:
        name: Parameter name
        type: Data type (string, file_list, integer, boolean, object)
        description: Human-readable description
        default: Default value if not provided
        required: Whether this input is mandatory
    """

    name: str = Field(..., description="Parameter name")
    type: str = Field(default="string", description="Parameter type")
    description: str = Field(default="", description="Parameter description")
    default: Any = Field(None, description="Default value")
    required: bool = Field(default=True, description="Is parameter required")


class SkillOutput(BaseModel):
    """Output produced by a skill.

    Defines the structured outputs returned after skill execution.

    Attributes:
        name: Output name
        value: Template expression to extract/compute output value
    """

    name: str = Field(..., description="Output name")
    value: str = Field(..., description="Template expression for output value")


class SkillDefinition(BaseModel):
    """Complete skill definition.

    Describes a reusable skill template with inputs, steps, and outputs.
    Skills are declarative, YAML-based workflow templates.

    Attributes:
        name: Skill name (unique identifier)
        version: Semantic version
        description: Human-readable description
        author: Author/organization
        triggers: How skill can be invoked
        inputs: Input parameters
        steps: Workflow steps
        outputs: Skill outputs
    """

    name: str = Field(..., description="Skill name")
    version: str = Field(default="1.0", description="Semantic version")
    description: str = Field(..., description="Skill description")
    author: str = Field(default="x-agent", description="Author/organization")
    triggers: list[SkillTrigger] = Field(default_factory=list, description="Trigger configurations")
    inputs: list[SkillInput] = Field(default_factory=list, description="Input parameters")
    steps: list[SkillStep] = Field(..., description="Workflow steps")
    outputs: list[SkillOutput] = Field(default_factory=list, description="Output definitions")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "code_review",
                "version": "1.0",
                "description": "Review code for issues",
                "author": "x-agent",
                "triggers": [{"command": "review-code"}],
                "inputs": [
                    {
                        "name": "file_path",
                        "type": "string",
                        "description": "Path to file to review",
                        "required": True,
                    }
                ],
                "steps": [
                    {
                        "id": "read_file",
                        "tool": "file_reader",
                        "args": {"path": "{{inputs.file_path}}"},
                        "output_var": "content",
                    }
                ],
                "outputs": [{"name": "review", "value": "{{steps.analyze.output}}"}],
            }
        }


class StepResult(BaseModel):
    """Result from executing a single step.

    Attributes:
        step_id: ID of the step that executed
        success: Whether execution succeeded
        output: Result data from the step
        error: Error message if execution failed
        duration_ms: Execution time in milliseconds
    """

    step_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float


class SkillResult(BaseModel):
    """Result from executing an entire skill.

    Attributes:
        skill_name: Name of executed skill
        success: Whether all steps succeeded
        outputs: Extracted outputs from skill execution
        errors: List of errors encountered
        step_results: Detailed results from each step
        total_duration_ms: Total execution time
    """

    skill_name: str
    success: bool
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    step_results: list[StepResult] = Field(default_factory=list)
    total_duration_ms: float
