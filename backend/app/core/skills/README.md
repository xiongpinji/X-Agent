# X-Agent Skills Framework

A declarative, composable framework for building reusable agent task templates in X-Agent.

## Overview

The Skills framework provides a YAML-based approach to defining complex, multi-step workflows that can be:
- **Reused** across different agents and contexts
- **Composed** into larger workflows
- **Versioned** and shared
- **Validated** before execution
- **Monitored** with full step-level tracking

## Architecture

### Components

1. **SkillDefinition** - The YAML/Pydantic schema describing a skill
2. **SkillLoader** - Loads and validates skills from YAML files
3. **SkillExecutor** - Executes skills with variable substitution and control flow
4. **Built-in Skills** - Pre-made templates for common tasks

### Core Concepts

#### Skill Structure
```yaml
name: skill_name
version: "1.0"
description: "What this skill does"
author: "x-agent"

triggers:
  - command: cli-command
  - event: webhook_event
  - schedule: "0 9 * * *"

inputs:
  - name: file_path
    type: string
    description: Path to process
    required: true

steps:
  - id: step1
    tool: tool_name
    args:
      param: "{{inputs.file_path}}"
    condition: "{{steps.previous.success}}"
    foreach: "{{steps.list_step.output}}"

outputs:
  - name: result
    value: "{{steps.final_step.output}}"
```

#### Variables and Substitution

Skills support template variable substitution using `{{...}}` syntax:

- **Input values**: `{{inputs.parameter_name}}`
- **Step outputs**: `{{steps.step_id.output}}`
- **Context**: `{{context.key}}`
- **Loop variables**: `{{item}}`, `{{index}}` (in foreach loops)

#### Control Flow

**Conditions**: Skip steps based on expressions
```yaml
condition: "{{steps.check.output}} == true"
```

**Iteration**: Repeat steps over lists
```yaml
foreach: "{{steps.get_files.output}}"
```

## Usage

### Basic Skill Definition

```python
from backend.app.core.skills import (
    SkillDefinition,
    SkillStep,
    SkillInput,
    SkillOutput,
)

skill = SkillDefinition(
    name="process_file",
    version="1.0",
    description="Process a file with multiple steps",
    inputs=[
        SkillInput(
            name="file_path",
            type="string",
            description="Path to file",
            required=True,
        )
    ],
    steps=[
        SkillStep(
            id="read",
            tool="file_reader",
            args={"path": "{{inputs.file_path}}"},
        ),
        SkillStep(
            id="analyze",
            tool="analyzer",
            args={"content": "{{steps.read.output}}"},
        ),
    ],
    outputs=[
        SkillOutput(name="result", value="{{steps.analyze.output}}")
    ],
)
```

### Loading Skills from YAML

```python
from backend.app.core.skills import SkillLoader

loader = SkillLoader()
skills = loader.load_all()  # Loads all .yaml files from default directories

# Load specific skill
skill = loader.load_skill(Path("my_skill.yaml"))

# Validate skill
errors = loader.validate(skill)
if errors:
    print("Validation errors:", errors)
```

### Executing Skills

```python
from backend.app.core.skills import SkillExecutor
from backend.app.core.tool_registry import tool_registry

executor = SkillExecutor(tool_registry)

result = await executor.execute(
    skill=my_skill,
    inputs={"file_path": "/path/to/file.py"},
    context={"user_id": "user123"},
)

print(f"Success: {result.success}")
print(f"Outputs: {result.outputs}")
print(f"Errors: {result.errors}")
```

## Built-in Skills

X-Agent comes with three pre-built skills:

### 1. Code Review (`code_review`)

Review code files for security, performance, and style issues.

**Command**: `review-code`

**Inputs**:
- `file_path` (string, required): Path to file
- `review_type` (string): "security" | "performance" | "style" | "comprehensive"
- `max_issues` (integer): Maximum issues to report

**Outputs**:
- `review_summary`: Brief summary of findings
- `review_detail`: Detailed review in Markdown
- `top_issues`: Most critical issues
- `total_issues_found`: Total count

### 2. Test Generation (`test_gen`)

Generate unit tests for code files.

**Command**: `gen-tests`

**Inputs**:
- `file_path` (string, required): Source file path
- `test_framework` (string): pytest | unittest | jest
- `coverage_target` (integer): Target coverage percentage
- `include_edge_cases` (boolean): Include edge cases

**Outputs**:
- `test_file_content`: Generated test code
- `estimated_coverage`: Coverage percentage
- `test_count`: Number of tests
- `setup_instructions`: How to run tests

### 3. Refactoring (`refactor`)

Suggest and apply code refactoring improvements.

**Command**: `refactor-code`

**Inputs**:
- `file_path` (string, required): File to refactor
- `refactoring_types` (string): "naming,duplication,complexity,performance"
- `auto_apply` (boolean): Apply changes automatically
- `preserve_tests` (boolean): Keep tests passing

**Outputs**:
- `refactoring_report`: Full report with suggestions
- `suggestions`: Specific refactoring suggestions
- `original_metrics`: Code metrics before
- `refactored_code`: Code after refactoring
- `verification_result`: Changes were valid

## Creating Custom Skills

### YAML Template

```yaml
name: my_skill
version: "1.0"
description: "Description of what this skill does"
author: "your-name"

triggers:
  - command: my-command
  - event: my_event
  - schedule: "0 0 * * *"

inputs:
  - name: input_name
    type: string  # or: integer, file_list, boolean, object
    description: "What this input is for"
    default: "default_value"
    required: true

steps:
  - id: unique_step_id
    tool: tool_name_from_registry
    args:
      parameter: "{{inputs.input_name}}"
      other_param: "{{steps.previous_step.output}}"
    output_var: step_result
    condition: "optional_condition"
    foreach: "optional_list_expression"

outputs:
  - name: output_name
    value: "{{steps.final_step.output}}"
```

### Python Implementation

```python
from backend.app.core.skills import SkillDefinition, SkillStep, SkillOutput, SkillInput

my_skill = SkillDefinition(
    name="my_skill",
    version="1.0",
    description="My skill description",
    author="me",
    inputs=[
        SkillInput(
            name="param1",
            type="string",
            required=True,
        )
    ],
    steps=[
        SkillStep(
            id="process",
            tool="my_tool",
            args={"input": "{{inputs.param1}}"},
        ),
    ],
    outputs=[
        SkillOutput(name="result", value="{{steps.process.output}}")
    ],
)
```

## Validation

The framework validates skills at load time:

```python
loader = SkillLoader()
errors = loader.validate(skill)

# Checks:
# - All step IDs are unique
# - Output expressions reference valid steps
# - Foreach expressions are syntactically valid
# - Condition expressions are valid
```

## Execution Model

Skills execute steps sequentially with:

1. **Template Resolution**: `{{...}}` expressions resolved
2. **Condition Evaluation**: Skip if condition is false
3. **Foreach Iteration**: Repeat step for each item
4. **Tool Execution**: Call the tool with resolved arguments
5. **Result Storage**: Store output for next steps
6. **Output Extraction**: Extract final outputs

### Error Handling

- Step failures don't stop execution (continue with other steps)
- All errors collected and reported
- Success only if zero errors
- Detailed error information for debugging

## Tool Registry Integration

Skills integrate with X-Agent's tool registry:

```python
from backend.app.core.tool_registry import tool_registry
from backend.app.core.skills import SkillExecutor

executor = SkillExecutor(tool_registry)
result = await executor.execute(skill, inputs)
```

Tools must implement:
```python
class MyTool(Tool):
    async def execute(self, **kwargs):
        # Process arguments
        return result
```

## Monitoring and Observability

Execution results include:

```python
result.success                    # bool
result.skill_name                 # str
result.outputs                    # dict[str, Any]
result.errors                     # list[str]
result.step_results               # list[StepResult]
result.total_duration_ms          # float

# Each step result:
step.step_id                       # str
step.success                       # bool
step.output                        # Any
step.error                         # Optional[str]
step.duration_ms                   # float
```

## File Organization

```
backend/app/core/skills/
├── __init__.py                   # Main API exports
├── schema.py                      # Pydantic schemas
├── loader.py                      # YAML loading and validation
├── executor.py                    # Skill execution engine
├── builtin/                       # Built-in skills
│   ├── code_review.yaml
│   ├── test_gen.yaml
│   └── refactor.yaml
├── skill_base.py                  # Legacy skill class (kept for compatibility)
├── skill_loader.py                # Legacy loader
└── skill_registry.py              # Legacy registry
```

## Best Practices

1. **Use descriptive step IDs**: Makes debugging easier
2. **Document inputs/outputs**: Help other users understand the skill
3. **Handle errors gracefully**: Use conditions to skip optional steps
4. **Version your skills**: Update version when making changes
5. **Test locally first**: Validate YAML before committing
6. **Reuse tools**: Leverage existing tools from registry
7. **Compose skills**: Use skills as building blocks for larger workflows

## Troubleshooting

### "Tool not found" error
- Verify tool name matches registry
- Check tool is registered with tool_registry.register()

### "Undefined variable" error
- Check template syntax: `{{steps.step_id.output}}`
- Verify step_id exists in steps list
- Ensure step ran successfully before referencing

### "Duplicate step IDs" error
- Each step id must be unique within the skill
- Use descriptive names: "read_file", "analyze", "format_output"

### Foreach not iterating
- Expression must resolve to a list
- Use `{{steps.step_id.output}}` to reference list
- Check step ran successfully

## Performance Considerations

- Skills execute steps sequentially (not parallel)
- Use foreach for parallel-like iteration (handled by tool)
- Monitor step_duration_ms for bottlenecks
- Cache results in context when reusing expensive steps

## Future Enhancements

Planned features:
- Parallel step execution
- Retry logic and circuit breakers
- Skill composition and inheritance
- Dry-run mode for preview
- Skill marketplace and sharing
- Advanced error recovery
