# Contributing to X-Agent

Thank you for your interest in contributing to X-Agent! This document provides guidelines for reporting issues, submitting pull requests, and contributing code.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Code Style & Standards](#code-style--standards)
- [Testing Requirements](#testing-requirements)
- [Commit Message Format](#commit-message-format)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Security Vulnerabilities](#security-vulnerabilities)
- [Development Workflow](#development-workflow)
- [Release Process](#release-process)

## Code of Conduct

By participating in this project, you agree to:
- Be respectful and inclusive of all contributors
- Provide constructive feedback
- Report harassment or inappropriate behavior to maintainers

## Getting Started

### Development Environment Setup

```bash
# Clone the repository
git clone https://github.com/your-org/X-Agent.git
cd X-Agent

# Create a Python virtual environment (Python 3.11+)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
pytest tests/ -v
```

### Project Structure

```
X-Agent/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── main.py            # Entry point
│   │   ├── api/               # REST API endpoints
│   │   ├── core/              # Core business logic
│   │   ├── services/          # Service layer
│   │   └── models/            # Data models
│   └── tests/                 # Unit tests
├── frontend/                  # Next.js web UI
├── sdk/                       # Python client SDK
├── tests/                     # Integration tests
├── docs/                      # Documentation
├── monitoring/                # Prometheus/Grafana configs
├── extension/                 # Chrome extension
└── CHANGELOG.md               # Release notes
```

## Code Style & Standards

### Python

```bash
# Format code with Black
black backend/ sdk/ tests/

# Check linting with ruff
ruff check backend/ sdk/ tests/ --fix

# Type checking with mypy
mypy backend/ sdk/

# Security scanning with bandit
bandit -r backend/ sdk/
```

**Style Requirements:**
- Python 3.11+ syntax with full type annotations
- Google-style docstrings for all public functions/classes
- Line length: 100 characters (enforced by Black)
- Async-first design for I/O operations

### Example Code Style

```python
"""Module docstring explaining purpose."""

from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TaskRequest:
    """Request model for task creation.
    
    Attributes:
        name: Human-readable task name (required).
        description: Task description (optional).
        priority: Task priority (1-10, default 5).
    """
    name: str
    description: Optional[str] = None
    priority: int = 5


async def process_task(task: TaskRequest) -> dict:
    """Process a task asynchronously.
    
    Args:
        task: The task request containing processing parameters.
        
    Returns:
        Dictionary with task_id, status, and result fields.
        
    Raises:
        ValueError: If task name is empty.
    """
    if not task.name:
        raise ValueError("Task name cannot be empty")
    
    logger.info(f"Processing task: {task.name}")
    return {"task_id": "task-123", "status": "success"}
```

## Testing Requirements

### Test Coverage

- **Minimum coverage:** 70% (enforced by CI/CD)
- **Critical paths:** 90%+ (auth, security, database)
- Tests should run in <5 minutes for pre-commit

### Writing Tests

```python
"""tests/test_example.py"""

import pytest
from backend.app.core.example import process_task


@pytest.mark.asyncio
class TestProcessTask:
    """Test suite for process_task function."""
    
    async def test_process_task_success(self):
        """Test successful task processing."""
        request = TaskRequest(name="test-task", priority=5)
        result = await process_task(request)
        
        assert result["status"] == "success"
        assert result["task_id"] is not None
    
    async def test_process_task_empty_name_raises(self):
        """Test that empty task name raises ValueError."""
        request = TaskRequest(name="", priority=5)
        
        with pytest.raises(ValueError, match="Task name cannot be empty"):
            await process_task(request)
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_example.py

# Run with coverage
pytest --cov=backend --cov=sdk --cov-report=html

# Run only fast tests
pytest -m "not slow"
```

## Commit Message Format

Follow Conventional Commits:

```
<type>(<scope>): <subject>
<BLANK LINE>
<body>
<BLANK LINE>
<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding/updating tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `security`: Security fix

### Examples

```
feat(auth): add OAuth2 GitHub integration

Implement GitHub OAuth2 support with PKCE flow.
- Add GitHubOAuth2Provider class
- Add /api/v1/auth/github/callback endpoint

Closes #123
```

```
fix(sandbox): prevent rate limit exhaustion

Add semaphore to limit concurrent executions.

Fixes #456
```

## Pull Request Process

1. **Create feature branch** from `develop`:
   ```bash
   git checkout develop && git pull
   git checkout -b feat/your-feature-name
   ```

2. **Make changes** following code style and testing requirements

3. **Run pre-commit checks:**
   ```bash
   pre-commit run --all-files
   pytest tests/
   ```

4. **Push and open PR:**
   - Title: Keep under 60 characters
   - Description: Explain what and why
   - Link issues: "Fixes #123"

5. **PR Checklist:**
   - [ ] Tests pass locally
   - [ ] Coverage maintained (70%+)
   - [ ] Code formatted
   - [ ] Types checked
   - [ ] Docstrings added
   - [ ] CHANGELOG.md updated
   - [ ] No security issues

6. **Address review comments:**
   - Push additional commits
   - Re-request review when ready

## Issue Reporting

### Bug Reports

Include:
- **Title:** Clear bug description
- **Steps to reproduce:** Numbered steps
- **Expected behavior:** What should happen
- **Actual behavior:** What actually happens
- **Environment:** Python version, OS, deployment method
- **Logs:** Full stack trace

### Feature Requests

Include:
- **Problem statement:** What problem does this solve?
- **Proposed solution:** How should it work?
- **Alternatives considered:** Other approaches
- **Use case:** Real-world example

## Security Vulnerabilities

Do NOT open a public issue for security vulnerabilities.

Instead, email security@your-org.com with:
- Description of the vulnerability
- Steps to reproduce
- Your name/affiliation (optional)

We will:
- Acknowledge within 48 hours
- Provide status every 7 days
- Release coordinated security patch
- Credit you in advisory (if desired)

## Development Workflow

### Local Testing

```bash
# Start services
docker-compose up -d

# Run tests
pytest tests/enterprise/

# Check code quality
pre-commit run --all-files
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Add field to table"

# Apply locally
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Documentation

- Add docstrings to all new public APIs
- Update README.md for user-facing features
- Document new environment variables in .env.example
- Add migration guide for breaking changes

## Release Process

Releases are automated via GitHub Actions:

```bash
# Create tag (maintainers only)
git tag -a v1.0.1 -m "Release v1.0.1"
git push origin v1.0.1
```

## Additional Resources

- [Architecture Overview](./docs/ARCHITECTURE.md)
- [API Documentation](./docs/API_REFERENCE.md)
- [Deployment Guide](./monitoring/RUNBOOK.md)
- [Performance Benchmarks](./docs/BENCHMARKS.md)

---

**Thank you for contributing to X-Agent!**
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

- [Architecture Guide](./docs/ARCHITECTURE.md)
- [API Documentation](./docs/API.md)
- [Development Setup](./INSTALL.md#development-setup)

Thank you for contributing to X-Agent Core!
