"""Code execution sandbox module for X-Agent."""

from backend.app.core.sandbox.container_cache import (
    DockerContainerPool,
    get_container_pool,
    reset_container_pools,
    shutdown_container_pools,
)
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
from backend.app.core.sandbox.serverless import (
    DaytonaSandbox,
    ModalSandbox,
    ServerlessSandboxError,
    UnifiedSandbox,
    create_sandbox,
)

__all__ = [
    "DaytonaSandbox",
    "DockerContainerPool",
    "ExecutionLanguage",
    "ExecutionResult",
    "JavaScriptSecurityValidator",
    "ModalSandbox",
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
    # Serverless backends & container caching
    "ServerlessSandboxError",
    "UnifiedSandbox",
    "create_sandbox",
    "execute_code",
    "get_container_pool",
    "get_sandbox_manager",
    "reset_container_pools",
    "shutdown_container_pools",
    "validate_javascript_code",
    "validate_python_code",
]
