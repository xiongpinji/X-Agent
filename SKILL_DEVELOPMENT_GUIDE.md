"""
X-Agent Skill Development Guide

This guide provides comprehensive instructions for developing, testing, and publishing skills
for the X-Agent skill system.

## Table of Contents

1. Overview
2. Skill Architecture
3. Creating a Skill
4. Skill Lifecycle
5. Testing Skills
6. Publishing Skills
7. Best Practices
8. Security Considerations
9. Performance Optimization
10. Troubleshooting

## 1. Overview

Skills are modular, reusable components that extend X-Agent's capabilities. Each skill:
- Implements a standard interface (SkillProtocol)
- Declares its capabilities and requirements
- Runs in an isolated sandbox with resource limits
- Can be versioned and distributed through the marketplace

## 2. Skill Architecture

### Core Components

- **SkillMetadata**: Describes skill properties, capabilities, and requirements
- **SkillExecutionContext**: Contains execution state and input/output data
- **SkillProtocol**: Interface that all skills must implement
- **SkillSandbox**: Provides isolated execution environment with resource limits

### Skill Lifecycle

1. **Registration**: Skill is registered in the registry with metadata
2. **Loading**: Skill module is dynamically loaded into memory
3. **Initialization**: Skill's initialize() method is called
4. **Execution**: Skill's execute() method processes input
5. **Cleanup**: Skill's cleanup() method releases resources
6. **Unloading**: Skill is removed from memory

## 3. Creating a Skill

### Basic Skill Template

```python
from backend.app.core.skills_core import (
    SkillMetadata,
    SkillCapability,
    SkillRiskLevel,
    SkillExecutionContext,
)

class MyCustomSkill:
    \"\"\"Description of your skill\"\"\"

    metadata = SkillMetadata(
        name="My Custom Skill",
        version="1.0.0",
        description="What this skill does",
        author="Your Name",
        license="MIT",
        capabilities=[SkillCapability.TEXT_EXTRACT],
        risk_level=SkillRiskLevel.LOW,
        timeout_seconds=300,
        max_memory_mb=512,
        tags=["custom", "text"],
        dependencies={"requests": ">=2.28.0"},
    )

    async def initialize(self) -> None:
        \"\"\"Initialize the skill (called once before first execution)\"\"\"
        # Load dependencies, initialize resources
        import requests
        self.requests = requests

    async def execute(self, context: SkillExecutionContext) -> dict:
        \"\"\"Execute the skill\"\"\"
        input_data = context.input_data
        
        # Process input
        result = await self._process(input_data)
        
        return result

    async def validate_input(self, input_data: dict) -> tuple[bool, str | None]:
        \"\"\"Validate input data\"\"\"
        if "required_field" not in input_data:
            return False, "required_field is required"
        return True, None

    async def cleanup(self) -> None:
        \"\"\"Cleanup resources (called after execution)\"\"\"
        # Close connections, release resources
        pass

    async def _process(self, data: dict) -> dict:
        \"\"\"Internal processing method\"\"\"
        return {"processed": True}
```

### Skill Metadata Fields

- **name**: Human-readable skill name
- **version**: Semantic version (e.g., "1.0.0")
- **description**: What the skill does
- **author**: Skill author name
- **license**: License type (MIT, Apache-2.0, etc.)
- **capabilities**: List of SkillCapability enums
- **risk_level**: LOW, MEDIUM, HIGH, or CRITICAL
- **timeout_seconds**: Maximum execution time
- **max_memory_mb**: Maximum memory usage
- **tags**: Search tags for discovery
- **dependencies**: Required Python packages

## 4. Skill Lifecycle

### Initialization Phase

```python
async def initialize(self) -> None:
    # Import dependencies
    import pandas as pd
    self.pd = pd
    
    # Initialize resources
    self.cache = {}
    self.connection = await self.create_connection()
```

### Execution Phase

```python
async def execute(self, context: SkillExecutionContext) -> dict:
    context.start_time = datetime.now(UTC)
    
    try:
        # Validate input
        valid, error = await self.validate_input(context.input_data)
        if not valid:
            raise ValueError(error)
        
        # Process
        result = await self._process(context.input_data)
        
        context.output_data = result
        context.status = "completed"
        return result
        
    except Exception as e:
        context.error = str(e)
        context.status = "error"
        raise
```

### Cleanup Phase

```python
async def cleanup(self) -> None:
    # Close connections
    if hasattr(self, 'connection'):
        await self.connection.close()
    
    # Clear cache
    self.cache.clear()
```

## 5. Testing Skills

### Unit Tests

```python
import pytest
from backend.app.core.skills_core import SkillExecutionContext

@pytest.mark.asyncio
async def test_skill_execution():
    skill = MyCustomSkill()
    await skill.initialize()
    
    context = SkillExecutionContext(
        input_data={"text": "Hello World"}
    )
    
    result = await skill.execute(context)
    assert result["processed"] == True
    
    await skill.cleanup()

@pytest.mark.asyncio
async def test_input_validation():
    skill = MyCustomSkill()
    
    valid, error = await skill.validate_input({})
    assert not valid
    assert error is not None
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_skill_in_system():
    from backend.app.core.skills_manager import get_skill_system_manager
    
    manager = get_skill_system_manager()
    
    # Register skill
    await manager.registry.register_skill(MyCustomSkill.metadata)
    
    # Execute skill
    result = await manager.execute_skill(
        skill_name="my_custom_skill",
        input_data={"text": "test"}
    )
    
    assert result.success
```

## 6. Publishing Skills

### Package Your Skill

```python
# Create skill package
from backend.app.core.skills_marketplace import get_skill_marketplace

marketplace = get_skill_marketplace()

# Publish
success, error = await marketplace.publish_skill(
    metadata=MyCustomSkill.metadata,
    skill_file_path="/path/to/skill.py",
    author="Your Name"
)
```

### Version Management

Follow semantic versioning:
- MAJOR.MINOR.PATCH (e.g., 1.2.3)
- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

## 7. Best Practices

### Error Handling

```python
async def execute(self, context: SkillExecutionContext) -> dict:
    try:
        # Validate input
        valid, error = await self.validate_input(context.input_data)
        if not valid:
            raise ValueError(f"Validation failed: {error}")
        
        # Process with error handling
        try:
            result = await self._process(context.input_data)
        except TimeoutError:
            raise RuntimeError("Processing timeout")
        except Exception as e:
            raise RuntimeError(f"Processing failed: {str(e)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Skill execution failed: {str(e)}")
        raise
```

### Resource Management

```python
async def initialize(self) -> None:
    # Use context managers for resources
    self.resources = []

async def cleanup(self) -> None:
    # Always cleanup resources
    for resource in self.resources:
        try:
            await resource.close()
        except Exception as e:
            logger.warning(f"Cleanup error: {str(e)}")
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

async def execute(self, context: SkillExecutionContext) -> dict:
    logger.info(f"Executing skill with input: {context.input_data}")
    
    try:
        result = await self._process(context.input_data)
        logger.info(f"Skill execution successful")
        return result
    except Exception as e:
        logger.error(f"Skill execution failed: {str(e)}", exc_info=True)
        raise
```

## 8. Security Considerations

### Input Validation

Always validate and sanitize input:

```python
async def validate_input(self, input_data: dict) -> tuple[bool, str | None]:
    # Check required fields
    if "file_path" not in input_data:
        return False, "file_path is required"
    
    # Validate types
    if not isinstance(input_data["file_path"], str):
        return False, "file_path must be a string"
    
    # Validate values
    file_path = input_data["file_path"]
    if not file_path.endswith(".txt"):
        return False, "Only .txt files are supported"
    
    return True, None
```

### Resource Limits

Respect sandbox resource limits:

```python
metadata = SkillMetadata(
    name="Memory-Intensive Skill",
    timeout_seconds=600,  # 10 minutes
    max_memory_mb=2048,   # 2GB
    max_cpu_percent=80.0, # 80% CPU
)
```

### Dependency Security

- Use pinned versions: `requests==2.28.0`
- Avoid untrusted packages
- Keep dependencies updated
- Declare all dependencies

## 9. Performance Optimization

### Caching

```python
class CachedSkill:
    async def initialize(self) -> None:
        self.cache = {}
    
    async def execute(self, context: SkillExecutionContext) -> dict:
        cache_key = str(context.input_data)
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        result = await self._process(context.input_data)
        self.cache[cache_key] = result
        
        return result
```

### Async Operations

```python
async def execute(self, context: SkillExecutionContext) -> dict:
    # Use asyncio for concurrent operations
    tasks = [
        self._process_item(item)
        for item in context.input_data["items"]
    ]
    
    results = await asyncio.gather(*tasks)
    return {"results": results}
```

### Batch Processing

```python
async def execute(self, context: SkillExecutionContext) -> dict:
    items = context.input_data["items"]
    batch_size = 100
    
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        batch_result = await self._process_batch(batch)
        results.extend(batch_result)
    
    return {"results": results}
```

## 10. Troubleshooting

### Common Issues

**Issue**: Skill not loading
- Check metadata is valid
- Verify all required methods are implemented
- Check for import errors

**Issue**: Timeout errors
- Increase timeout_seconds in metadata
- Optimize processing logic
- Use async operations

**Issue**: Memory errors
- Increase max_memory_mb in metadata
- Implement streaming for large data
- Clear caches regularly

**Issue**: Dependency conflicts
- Use virtual environments
- Pin dependency versions
- Check compatibility

### Debugging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def execute(self, context: SkillExecutionContext) -> dict:
    logger.debug(f"Input: {context.input_data}")
    
    result = await self._process(context.input_data)
    
    logger.debug(f"Output: {result}")
    return result
```

## Resources

- Skill System API: backend/app/core/skills_*.py
- Example Skills: backend/app/core/skills_document.py
- Tests: tests/test_skills_system.py
- CLI: backend/app/core/skills_cli.py

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review example skills
3. Check test cases
4. Open an issue on the project repository
"""

# This is a documentation file - save as SKILL_DEVELOPMENT_GUIDE.md
