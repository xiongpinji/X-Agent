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
- [Reporting Issues](#reporting-issues)
- [Contact](#contact)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and constructive in all interactions.

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
   docker-compose up -d
   ```

5. **Initialize the database**
   ```bash
   python -m backend.app.core.migration init
   ```

6. **Verify setup**
   ```bash
   pytest tests/test_ready_checks.py
   ```

## Development Workflow

### Git Flow Strategy

We follow a modified Git Flow workflow:

1. **Create a feature branch from `develop`**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Keep commits atomic and focused
   - Write clear commit messages
   - Add tests for new functionality

3. **Keep your branch updated**
   ```bash
   git fetch origin
   git rebase origin/develop
   ```

4. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**
   - Use the PR template
   - Link related issues
   - Request review from maintainers

### Branch Naming Convention

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test improvements
- `chore/description` - Maintenance tasks

## Coding Standards

### PEP 8 and Ruff

We use Ruff for code linting and formatting. Configuration is in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

### Code Style Guidelines

1. **Line Length**: Maximum 100 characters
2. **Imports**: Organize imports (stdlib, third-party, local)
3. **Type Hints**: Use type hints for function signatures
4. **Docstrings**: Use Google-style docstrings

Example:
```python
def process_workflow(
    workflow_id: str,
    context: Dict[str, Any],
) -> WorkflowResult:
    """Process a workflow with the given context.
    
    Args:
        workflow_id: The unique identifier for the workflow.
        context: Dictionary containing workflow execution context.
    
    Returns:
        WorkflowResult containing execution status and output.
    
    Raises:
        WorkflowNotFoundError: If workflow does not exist.
        ValidationError: If context is invalid.
    """
    pass
```

### Running Linter and Formatter

```bash
# Check code style
ruff check .

# Format code
ruff format .

# Fix common issues
ruff check . --fix
```

## Commit Guidelines

We follow Conventional Commits specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring without feature changes
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Build process, dependencies, tooling

### Examples

```
feat(memory): add semantic search to memory retrieval

Implement vector-based semantic search using Qdrant embeddings.
This allows more accurate context retrieval for agent reasoning.

Closes #123
```

```
fix(workflow): handle timeout in workflow execution

Add proper timeout handling and retry logic for long-running
workflow steps. Prevents hanging processes.

Fixes #456
```

## Pull Request Process

### Before Submitting

1. **Run tests locally**
   ```bash
   pytest
   ```

2. **Check code style**
   ```bash
   ruff check .
   ruff format .
   ```

3. **Update documentation** if needed
4. **Add tests** for new functionality
5. **Update CHANGELOG.md** with your changes

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Closes #(issue number)

## Testing
Describe testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new warnings generated
```

### Review Process

1. At least one maintainer review required
2. All CI checks must pass
3. No merge conflicts
4. Approval from code owners

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api.py

# Run with coverage
pytest --cov=backend tests/

# Run specific test
pytest tests/test_api.py::test_create_workflow
```

### Writing Tests

- Use pytest framework
- Follow naming convention: `test_*.py` and `test_*` functions
- Use fixtures for common setup
- Aim for >80% code coverage

Example:
```python
import pytest
from backend.app.api.workflows import create_workflow

@pytest.fixture
def workflow_data():
    return {
        "name": "Test Workflow",
        "description": "A test workflow",
        "steps": []
    }

def test_create_workflow(workflow_data):
    result = create_workflow(workflow_data)
    assert result.name == "Test Workflow"
    assert result.id is not None
```

## Reporting Issues

### Issue Template

```markdown
## Description
Clear description of the issue

## Steps to Reproduce
1. Step one
2. Step two
3. ...

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: 
- Python version:
- X-Agent version:

## Additional Context
Any other relevant information
```

### Issue Labels

- `bug` - Something isn't working
- `enhancement` - Feature request
- `documentation` - Documentation improvements
- `good first issue` - Good for newcomers
- `help wanted` - Need assistance
- `question` - Question about usage

## Contact

- **Email**: dev@x-agent.dev
- **GitHub Issues**: [Report issues](https://github.com/x-agent/x-agent-core/issues)
- **Discussions**: [Community discussions](https://github.com/x-agent/x-agent-core/discussions)

## Additional Resources

- [Architecture Guide](./docs/concepts/architecture/ARCHITECTURE.md)
- [API Documentation](./docs/developer/api/API.md)
- [Development Setup](./docs/operations/setup/INSTALL.md#development-setup)

Thank you for contributing to X-Agent Core!
