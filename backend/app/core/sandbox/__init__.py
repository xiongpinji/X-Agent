"""Code execution sandbox module for X-Agent."""

from backend.app.core.sandbox.python_sandbox import (
    PythonSandbox,
    PythonSandboxPool,
    SandboxConfig,
    ExecutionResult,
)
from backend.app.core.sandbox.node_sandbox import (
    NodeSandbox,
    NodeSandboxPool,
    NodeSandboxConfig,
    NodeExecutionResult,
)
from backend.app.core.sandbox.manager import (
    SandboxManager,
    ExecutionLanguage,
    SecurityPolicy,
    get_sandbox_manager,
    execute_code,
)
from backend.app.core.sandbox.security import (
    PythonSecurityValidator,
    JavaScriptSecurityValidator,
    SecurityViolation,
    RiskLevel,
    validate_python_code,
    validate_javascript_code,
)

__all__ = [
    # Python sandbox
    "PythonSandbox",
    "PythonSandboxPool",
    "SandboxConfig",
    "ExecutionResult",
    # Node.js sandbox
    "NodeSandbox",
    "NodeSandboxPool",
    "NodeSandboxConfig",
    "NodeExecutionResult",
    # Manager
    "SandboxManager",
    "ExecutionLanguage",
    "SecurityPolicy",
    "get_sandbox_manager",
    "execute_code",
    # Security
    "PythonSecurityValidator",
    "JavaScriptSecurityValidator",
    "SecurityViolation",
    "RiskLevel",
    "validate_python_code",
    "validate_javascript_code",
]
