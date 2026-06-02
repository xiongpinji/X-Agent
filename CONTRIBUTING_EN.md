# Contributing to X-Agent Core

Thank you for your interest in contributing to X-Agent Core! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)
- [Reporting Issues](#reporting-issues)
- [Contact](#contact)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and constructive in all interactions.

### Our Pledge

In the interest of fostering an open and welcoming environment, we as contributors and maintainers pledge to making participation in our project and our community a harassment-free experience for everyone.

### Expected Behavior

- Use welcoming and inclusive language
- Be respectful of differing opinions and experiences
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment or discrimination
- Offensive comments or personal attacks
- Trolling or insulting comments
- Public or private harassment
- Publishing others' private information

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- PostgreSQL 14+
- Docker and Docker Compose (recommended)

### Setting Up Development Environment

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/x-agent-core.git
   cd x-agent-core
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up local services**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

5. **Initialize the database**
   ```bash
   python -m backend.app.core.migration init
   ```

6. **Run tests to verify setup**
   ```bash
   pytest tests/ -v
   ```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or for bug fixes:
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

- Write clean, readable code
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation as needed

### 3. Commit Your Changes

Follow the commit guidelines (see below):

```bash
git add .
git commit -m "feat: add new feature"
```

### 4. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 5. Create a Pull Request

- Provide a clear description of changes
- Reference related issues
- Ensure all tests pass
- Request review from maintainers

## Coding Standards

### Python Code Style

We follow PEP 8 with some modifications:

- Line length: 100 characters (soft limit)
- Use type hints for function signatures
- Use docstrings for modules, classes, and functions
- Use meaningful variable names

### Code Quality Tools

We use:
- **Black**: Code formatting
- **Flake8**: Linting
- **MyPy**: Type checking
- **Pytest**: Testing

Run before committing:

```bash
# Format code
black .

# Check linting
flake8 .

# Type checking
mypy .

# Run tests
pytest tests/ -v
```

### Example Code Style

```python
"""Module docstring explaining the module's purpose."""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class Agent:
    """Agent class for autonomous task execution.
    
    Attributes:
        name: Agent identifier
        model: LLM model to use
        tools: Available tools for the agent
    """
    
    name: str
    model: str
    tools: Optional[List[str]] = None
    
    def execute(self, task: str) -> str:
        """Execute a task using the agent.
        
        Args:
            task: Task description
            
        Returns:
            Task execution result
            
        Raises:
            ValueError: If task is empty
        """
        if not task:
            raise ValueError("Task cannot be empty")
        
        # Implementation
        return result
```

## Commit Guidelines

We follow Conventional Commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, etc.)
- **refactor**: Code refactoring
- **perf**: Performance improvements
- **test**: Test additions or changes
- **chore**: Build, dependency, or tooling changes

### Examples

```bash
# Feature
git commit -m "feat(agent): add multi-turn conversation support"

# Bug fix
git commit -m "fix(memory): resolve memory leak in vector search"

# Documentation
git commit -m "docs(api): update API reference for v2.0"

# With body
git commit -m "feat(workflow): add parallel task execution

- Implement DAG-based task scheduling
- Add task dependency resolution
- Support concurrent task execution

Closes #123"
```

## Pull Request Process

### Before Submitting

1. **Update your branch**
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **Run all checks**
   ```bash
   black .
   flake8 .
   mypy .
   pytest tests/ -v
   ```

3. **Update documentation**
   - Add docstrings
   - Update README if needed
   - Add examples if applicable

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Closes #123

## Testing
- [ ] Unit tests added
- [ ] Integration tests added
- [ ] Manual testing completed

## Documentation
- [ ] Documentation updated
- [ ] Examples added
- [ ] API reference updated

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally
```

### Review Process

1. At least one maintainer review required
2. All CI checks must pass
3. No merge conflicts
4. Approval from maintainers

## Testing

### Writing Tests

```python
import pytest
from x_agent import Agent


class TestAgent:
    """Test suite for Agent class."""
    
    @pytest.fixture
    def agent(self):
        """Create a test agent."""
        return Agent(name="test_agent", model="gpt-4")
    
    def test_agent_creation(self, agent):
        """Test agent creation."""
        assert agent.name == "test_agent"
        assert agent.model == "gpt-4"
    
    def test_execute_task(self, agent):
        """Test task execution."""
        result = agent.execute("test task")
        assert result is not None
    
    def test_execute_empty_task_raises_error(self, agent):
        """Test that empty task raises error."""
        with pytest.raises(ValueError):
            agent.execute("")
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_agent.py -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=html

# Run with markers
pytest tests/ -m "not slow" -v
```

## Documentation

### Documentation Standards

- Use clear, concise language
- Include code examples
- Keep documentation up-to-date
- Follow existing structure
- Use consistent terminology

### Adding Documentation

1. **Code documentation**
   - Add docstrings to modules, classes, functions
   - Use Google-style docstrings
   - Include type hints

2. **User documentation**
   - Add to `docs/` directory
   - Follow existing structure
   - Include examples

3. **API documentation**
   - Update API reference
   - Include request/response examples
   - Document error codes

## Reporting Issues

### Bug Reports

Include:
- X-Agent Core version
- Python version
- Operating system
- Minimal reproduction code
- Error logs
- Expected vs actual behavior

### Feature Requests

Include:
- Clear description of feature
- Use case and motivation
- Proposed implementation (optional)
- Examples or mockups (if applicable)

### Security Issues

Please email security@x-agent.dev instead of using GitHub issues.

## Contact

- **Email**: dev@x-agent.dev
- **GitHub**: https://github.com/x-agent/x-agent-core
- **Discussions**: GitHub Discussions
- **Issues**: GitHub Issues

## License

By contributing to X-Agent Core, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to X-Agent Core!

Last Updated: 2026-05-27
