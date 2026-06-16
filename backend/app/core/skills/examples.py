"""
Example: Using the X-Agent Skills Framework

This module demonstrates how to use the skills framework in practice.
"""

import asyncio
from pathlib import Path

from backend.app.core.skills import (
    SkillDefinition,
    SkillExecutor,
    SkillInput,
    SkillLoader,
    SkillOutput,
    SkillStep,
    load_builtin_skills,
)


async def example_load_builtin_skills():
    """Example 1: Load and inspect built-in skills."""
    print("Example 1: Loading built-in skills")
    print("=" * 50)

    skills = load_builtin_skills()
    for name, skill in skills.items():
        print(f"\nSkill: {name}")
        print(f"  Version: {skill.version}")
        print(f"  Description: {skill.description}")
        print(f"  Steps: {len(skill.steps)}")
        print(f"  Inputs: {[inp.name for inp in skill.inputs]}")
        print(f"  Outputs: {[out.name for out in skill.outputs]}")


async def example_create_custom_skill():
    """Example 2: Create and validate a custom skill."""
    print("\n\nExample 2: Creating a custom skill")
    print("=" * 50)

    # Define a skill that processes files in batch
    batch_skill = SkillDefinition(
        name="batch_process",
        version="1.0",
        description="Process multiple files in batch",
        author="example",
        inputs=[
            SkillInput(
                name="files",
                type="file_list",
                description="List of file paths to process",
                required=True,
            ),
            SkillInput(
                name="operation",
                type="string",
                description="Operation to perform (analyze, format, validate)",
                required=True,
            ),
        ],
        steps=[
            # Step 1: Get list of files
            SkillStep(
                id="get_files",
                tool="file_lister",
                args={"file_list": "{{inputs.files}}"},
            ),
            # Step 2: Process each file (foreach)
            SkillStep(
                id="process_file",
                tool="file_processor",
                args={
                    "file_path": "{{item}}",
                    "operation": "{{inputs.operation}}",
                },
                foreach="{{steps.get_files.output}}",
            ),
            # Step 3: Aggregate results
            SkillStep(
                id="aggregate",
                tool="results_aggregator",
                args={"results": "{{steps.process_file.output}}"},
            ),
        ],
        outputs=[
            SkillOutput(
                name="processed_files",
                value="{{steps.aggregate.output.count}}",
            ),
            SkillOutput(
                name="summary",
                value="{{steps.aggregate.output.summary}}",
            ),
        ],
    )

    print(f"Created skill: {batch_skill.name}")
    print(f"Steps: {[s.id for s in batch_skill.steps]}")

    # Validate the skill
    loader = SkillLoader()
    errors = loader.validate(batch_skill)

    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✓ Skill validation passed")


async def example_skill_with_conditions():
    """Example 3: Skill with conditional steps."""
    print("\n\nExample 3: Skill with conditional steps")
    print("=" * 50)

    skill = SkillDefinition(
        name="conditional_flow",
        version="1.0",
        description="Demonstrates conditional execution",
        inputs=[
            SkillInput(name="file_type", type="string", required=True),
        ],
        steps=[
            # Check file type
            SkillStep(
                id="check_type",
                tool="type_checker",
                args={"file_path": "{{inputs.file_type}}"},
            ),
            # Conditional steps based on type
            SkillStep(
                id="analyze_python",
                tool="python_analyzer",
                args={"file": "{{inputs.file_type}}"},
                condition="{{steps.check_type.output}} == python",
            ),
            SkillStep(
                id="analyze_javascript",
                tool="js_analyzer",
                args={"file": "{{inputs.file_type}}"},
                condition="{{steps.check_type.output}} == javascript",
            ),
        ],
        outputs=[
            SkillOutput(
                name="analysis",
                value="{{steps.analyze_python.output}}",
            ),
        ],
    )

    print(f"Skill: {skill.name}")
    print(f"Steps with conditions:")
    for step in skill.steps:
        if step.condition:
            print(f"  - {step.id}: condition={step.condition}")


async def example_load_from_yaml():
    """Example 4: Load skills from YAML files."""
    print("\n\nExample 4: Loading skills from YAML")
    print("=" * 50)

    loader = SkillLoader()

    # Load all built-in skills
    print("Loading built-in skills...")
    all_skills = loader.load_all()

    for name, skill in all_skills.items():
        print(f"\n✓ {name} ({skill.version})")
        print(f"  Description: {skill.description}")
        print(f"  Input parameters: {len(skill.inputs)}")
        print(f"  Workflow steps: {len(skill.steps)}")

        # Validate each skill
        errors = loader.validate(skill)
        if errors:
            print(f"  ⚠ Validation errors: {errors}")
        else:
            print(f"  ✓ Valid")


async def example_template_resolution():
    """Example 5: Understanding template variable resolution."""
    print("\n\nExample 5: Template variable resolution")
    print("=" * 50)

    # The skill executor handles template resolution
    from unittest.mock import MagicMock

    executor = SkillExecutor(MagicMock())

    # Example variables
    variables = {
        "inputs": {"file_path": "/path/to/file.py", "max_issues": 10},
        "steps": {
            "read": {"output": "file_content_here"},
            "analyze": {"output": {"issues": ["issue1", "issue2"]}},
        },
        "context": {"user_id": "user123"},
    }

    # Template expressions and their resolved values
    examples = [
        ("{{inputs.file_path}}", "/path/to/file.py"),
        ("{{inputs.max_issues}}", 10),
        ("{{steps.read.output}}", "file_content_here"),
        ("File: {{inputs.file_path}}", "File: /path/to/file.py"),
    ]

    print("Template resolution examples:")
    for template, expected in examples:
        resolved = executor._resolve_template(template, variables)
        match = "✓" if resolved == expected else "✗"
        print(f"  {match} {template}")
        print(f"      → {resolved}")


async def main():
    """Run all examples."""
    try:
        await example_load_builtin_skills()
        await example_create_custom_skill()
        await example_skill_with_conditions()
        await example_load_from_yaml()
        await example_template_resolution()

        print("\n" + "=" * 50)
        print("All examples completed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
