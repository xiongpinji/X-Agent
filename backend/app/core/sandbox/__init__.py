"""Code execution sandbox module for X-Agent."""

from backend.app.core.sandbox.manager import (
    ExecutionLanguage,
    SandboxManager,
    SecurityPolicy,
    execute_code,
    get_sandbox_manager,
)
from backend.app.core.sandbox.node_sandbox import (
    NodeExecutionResult,
    NodeSandbox,
    NodeSandboxConfig,
    NodeSandboxPool,
)
from backend.app.core.sandbox.python_sandbox import (
    ExecutionResult,
    PythonSandbox,
    PythonSandboxPool,
    SandboxConfig,
)
from backend.app.core.sandbox.security import (
    JavaScriptSecurityValidator,
    PythonSecurityValidator,
    RiskLevel,
    SecurityViolation,
    validate_javascript_code,
    validate_python_code,
)

__all__ = [
    "ExecutionLanguage",
    "ExecutionResult",
    "JavaScriptSecurityValidator",
    "NodeExecutionResult",
    # Node.js sandbox
    "NodeSandbox",
    "NodeSandboxConfig",
    "NodeSandboxPool",
    # Python sandbox
    "PythonSandbox",
    "PythonSandboxPool",
    # Security
    "PythonSecurityValidator",
    "RiskLevel",
    "SandboxConfig",
    # Manager
    "SandboxManager",
    "SecurityPolicy",
    "SecurityViolation",
    "execute_code",
    "get_sandbox_manager",
    "validate_javascript_code",
    "validate_python_code",
]
