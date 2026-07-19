# X-Agent Prompt Engineering Platform

## Overview

The X-Agent Prompt Engineering Platform provides a centralized, versioned system for managing prompts across the agent execution pipeline. This system enables:

- **Centralized Management**: All prompts in one place with version control
- **Semantic Versioning**: Track changes with major.minor.patch versions
- **Variable Substitution**: Dynamic prompt customization
- **Schema Validation**: Ensure prompt quality and consistency
- **Scope Organization**: Organize prompts by function (system, roles, tools, etc.)

## Directory Structure

```
prompts/
├── system/          # System-level prompts (agent behavior, core instructions)
├── roles/           # Role-specific prompts (planner, executor, verifier)
├── tools/           # Tool-specific prompts (browser, file operations, etc.)
├── recovery/        # Recovery strategies (retry, fallback, repair)
├── audit/           # Audit and logging prompts
├── memory/          # Memory management prompts
├── marketplace/     # Marketplace and tool discovery prompts
├── navigation/      # Task routing and navigation prompts
├── CHANGELOG.md     # Version history and changes
└── README.md        # This file
```

## Quick Start

### Loading Prompts

```python
from backend.app.core.prompt_manager import prompt_manager

# Initialize (loads all prompts from directory)
prompt_manager.initialize()

# Get system prompt
system_ctx = prompt_manager.get_system_prompt()
system_prompt = system_ctx.render()

# Get role prompt with variables
role_ctx = prompt_manager.get_role_prompt(
    "planner",
    variables={"max_steps": 10}
)
role_prompt = role_ctx.render()

# Build messages for LLM
messages = prompt_manager.build_messages(
    system_ctx,
    "Plan the following task: ...",
    role_ctx
)
```

### Creating New Prompts

1. Create a markdown file in the appropriate scope directory:

```markdown
---
id: my_prompt
name: My Custom Prompt
version: 1.0.0
purpose: Describe what this prompt does
scope: system  # or roles, tools, recovery, etc.
description: Detailed description
owner: x-agent
tags: [tag1, tag2]
deprecated: false
dependencies: [other_prompt_id]
variables:
  var1: default_value
---

# Prompt Title

Your prompt content here with {{var1}} for variables.

## Inputs

- input1: Description

## Outputs

- output1: Description
```

2. The prompt will be automatically loaded when `prompt_manager.initialize()` is called.

## Prompt Schema

Each prompt follows a consistent schema:

### Metadata
- `id`: Unique identifier (required)
- `name`: Human-readable name (required)
- `version`: Semantic version (required)
- `purpose`: What the prompt does (required)
- `scope`: Functional scope (required)
- `description`: Detailed description
- `owner`: Prompt owner/maintainer
- `tags`: Searchable tags
- `deprecated`: Deprecation status
- `deprecation_reason`: Why deprecated

### Content
- `content`: The actual prompt text
- `inputs`: List of input specifications
- `outputs`: List of output specifications
- `constraints`: Operational constraints
- `examples`: Usage examples
- `dependencies`: Other prompts this depends on
- `variables`: Template variables with defaults

## Integration Points

### Agent Initialization

```python
# In agent.py or agent_phases.py
from backend.app.core.prompt_manager import prompt_manager

system_ctx = prompt_manager.get_system_prompt({
    "agent_name": "X-Agent",
    "phase": "Phase 0"
})
```

### Role-Based Execution

```python
# In planning phase
planner_ctx = prompt_manager.get_role_prompt("planner", {
    "max_steps": 10,
    "max_subtasks": 5
})

# In execution phase
executor_ctx = prompt_manager.get_role_prompt("executor", {
    "max_iterations": 10,
    "timeout_seconds": 300
})

# In verification phase
verifier_ctx = prompt_manager.get_role_prompt("verifier", {
    "min_confidence": 0.8
})
```

### Tool Execution

```python
# When using a tool
tool_ctx = prompt_manager.get_tool_prompt("browser", {
    "timeout": 30,
    "max_retries": 3
})
```

### Error Recovery

```python
# When handling errors
recovery_ctx = prompt_manager.get_recovery_prompt("retry", {
    "max_retries": 3,
    "backoff_factor": 2
})
```

## Version Management

### Semantic Versioning

- **MAJOR.MINOR.PATCH**
- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

### Incrementing Versions

```python
from backend.app.core.prompt_loader import PromptVersionManager

# Increment patch version
new_version = PromptVersionManager.increment_version("1.0.0", "patch")  # 1.0.1

# Increment minor version
new_version = PromptVersionManager.increment_version("1.0.0", "minor")  # 1.1.0

# Increment major version
new_version = PromptVersionManager.increment_version("1.0.0", "major")  # 2.0.0
```

### Version History

```python
# Get version history for a prompt
history = prompt_manager.registry.get_version_history("agent_system")
# Returns: ["1.0.0", "1.1.0", "1.2.0"]

# Compare versions
from backend.app.core.prompt_loader import PromptVersionManager
result = PromptVersionManager.compare_versions("1.0.0", "1.1.0")
# Returns: -1 (v1 < v2)
```

## Validation

### Validate All Prompts

```python
valid_count, invalid_count = prompt_manager.validate_all_prompts()
print(f"Valid: {valid_count}, Invalid: {invalid_count}")
```

### Validate Single Prompt

```python
is_valid, errors = prompt_manager.registry.validate_prompt(prompt)
if not is_valid:
    for error in errors:
        print(f"Error: {error}")
```

## Export and Import

### Export Prompt

```python
# Export as JSON
json_str = prompt_manager.registry.export_prompt("agent_system", format="json")

# Export as Markdown
md_str = prompt_manager.registry.export_prompt("agent_system", format="markdown")
```

## Best Practices

1. **Use Semantic Versioning**: Follow major.minor.patch convention
2. **Document Changes**: Update CHANGELOG.md for each version
3. **Validate Prompts**: Run validation before deploying
4. **Use Variables**: Make prompts configurable with variables
5. **Organize by Scope**: Keep prompts organized in appropriate directories
6. **Add Examples**: Include usage examples in prompt documentation
7. **Maintain Dependencies**: Document prompt dependencies
8. **Test Thoroughly**: Test prompt changes before deployment

## Troubleshooting

### Prompt Not Found

```python
# Check if prompt is loaded
prompt = prompt_manager.registry.get_prompt("my_prompt")
if not prompt:
    print("Prompt not found")
    # List available prompts
    all_prompts = prompt_manager.registry.list_all_prompts()
    for p in all_prompts:
        print(f"- {p.metadata.id}")
```

### Variable Substitution Issues

```python
# Ensure variables match template placeholders
# Template: "Max steps: {{max_steps}}"
# Variables: {"max_steps": 10}

# Check rendered content
ctx = prompt_manager.get_role_prompt("planner", {"max_steps": 10})
rendered = ctx.render()
print(rendered)
```

### Version Conflicts

```python
# Get specific version
prompt = prompt_manager.registry.get_prompt("agent_system", version="1.0.0")

# Get version history
history = prompt_manager.registry.get_version_history("agent_system")
```

## Contributing

When adding new prompts:

1. Create file in appropriate scope directory
2. Follow schema format
3. Add YAML frontmatter with metadata
4. Include examples and documentation
5. Validate with `prompt_manager.validate_all_prompts()`
6. Update CHANGELOG.md
7. Test integration with agent pipeline

## Future Enhancements

- [ ] Prompt versioning with rollback support
- [ ] A/B testing framework for prompts
- [ ] Prompt performance metrics
- [ ] Automated prompt optimization
- [ ] Multi-language prompt support
- [ ] Prompt composition and inheritance
- [ ] Dynamic prompt generation
- [ ] Prompt caching and optimization
