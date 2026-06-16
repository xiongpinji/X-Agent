# RBAC Usage Guide

This guide explains how to add Role-Based Access Control (RBAC) permission enforcement to X-Agent API routes.

## Quick Start

Add permission enforcement to any route using pre-built dependencies:

```python
from fastapi import APIRouter, Depends
from backend.app.api.rbac_enforcement import require_admin, require_agent_run

router = APIRouter()

@router.post("/dangerous-action", dependencies=[Depends(require_admin)])
async def dangerous_action():
    """Only admins can call this endpoint."""
    return {"status": "ok"}

@router.post("/agent/run", dependencies=[Depends(require_agent_run)])
async def run_agent():
    """Developers and admins can call this endpoint."""
    return {"agent": "started"}
```

## How It Works

The RBAC enforcement layer integrates with FastAPI's dependency injection system:

1. **Request reaches route** with auth headers or session
2. **Authentication middleware** sets `request.state.principal` with user info
3. **RBAC dependency** checks `principal.role` against required permission
4. **If permission granted** → route executes normally
5. **If permission denied** → returns 403 Forbidden with details

### Permission Model

X-Agent uses a three-role model with increasing privilege:

| Role | Level | Description | Can Do |
|------|-------|-------------|--------|
| `viewer` | 1 | Read-only access | View agents, tasks, workflows, memory, skills, sandbox results, chat history |
| `developer` | 2 | Execution & management | Run agents, create/cancel tasks, execute tools, create/run workflows, write memory, install/run skills, run sandboxes, send chat |
| `admin` | 3 | Full system access | Everything + manage security config, user roles, API keys, audit logs, system settings |

## Available Dependencies

### High-Level Permissions (Tier-Based)

**Use these when permission maps to a broad role level:**

```python
from backend.app.api.rbac_enforcement import (
    require_admin,      # Requires admin role
    require_developer,  # Requires developer or admin
    require_viewer,     # Requires viewer, developer, or admin
)
```

Example:
```python
@router.post("/config/update", dependencies=[Depends(require_admin)])
async def update_system_config():
    """Admins only."""
    pass

@router.post("/task", dependencies=[Depends(require_developer)])
async def create_task():
    """Developers and admins."""
    pass

@router.get("/tasks", dependencies=[Depends(require_viewer)])
async def list_tasks():
    """Everyone."""
    pass
```

### Granular Permissions (Resource-Based)

**Use these when you need to enforce a specific permission:**

#### Agent Permissions
```python
from backend.app.api.rbac_enforcement import (
    require_agent_run,      # "agent:run"      - execute agents
    require_agent_read,     # "agent:read"     - view agent details
    require_agent_cancel,   # "agent:cancel"   - cancel running agents
)

@router.post("/agent/run", dependencies=[Depends(require_agent_run)])
async def run_agent():
    pass

@router.get("/agent/{agent_id}", dependencies=[Depends(require_agent_read)])
async def get_agent(agent_id: str):
    pass

@router.delete("/agent/{run_id}", dependencies=[Depends(require_agent_cancel)])
async def cancel_agent(run_id: str):
    pass
```

#### Task Permissions
```python
from backend.app.api.rbac_enforcement import (
    require_task_create,    # "task:create"    - create new tasks
    require_task_read,      # "task:read"      - view task details
    require_task_cancel,    # "task:cancel"    - cancel running tasks
)

@router.post("/task", dependencies=[Depends(require_task_create)])
async def create_task():
    pass

@router.get("/task/{task_id}", dependencies=[Depends(require_task_read)])
async def get_task(task_id: str):
    pass

@router.delete("/task/{task_id}", dependencies=[Depends(require_task_cancel)])
async def cancel_task(task_id: str):
    pass
```

#### Tool Permissions
```python
from backend.app.api.rbac_enforcement import (
    require_tool_execute,   # "tool:execute"   - run tools
    require_tool_read,      # "tool:read"      - list/view tools
)

@router.post("/tool/execute", dependencies=[Depends(require_tool_execute)])
async def execute_tool():
    pass

@router.get("/tools", dependencies=[Depends(require_tool_read)])
async def list_tools():
    pass
```

#### Workflow Permissions
```python
from backend.app.api.rbac_enforcement import (
    require_workflow_run,    # "workflow:run"    - execute workflows
    require_workflow_create, # "workflow:create" - create workflows
    require_workflow_read,   # "workflow:read"   - view workflows
)

@router.post("/workflow/run", dependencies=[Depends(require_workflow_run)])
async def run_workflow():
    pass

@router.post("/workflow", dependencies=[Depends(require_workflow_create)])
async def create_workflow():
    pass

@router.get("/workflow/{workflow_id}", dependencies=[Depends(require_workflow_read)])
async def get_workflow(workflow_id: str):
    pass
```

#### Memory Permissions
```python
from backend.app.api.rbac_enforcement import (
    require_memory_read,    # "memory:read"     - query memory
    require_memory_write,   # "memory:write"    - store/modify memory
)

@router.get("/memory/{session_id}", dependencies=[Depends(require_memory_read)])
async def query_memory(session_id: str):
    pass

@router.post("/memory", dependencies=[Depends(require_memory_write)])
async def store_memory():
    pass
```

#### Skill Permissions
```python
from backend.app.api.rbac_enforcement import (
    require_skill_run,      # "skill:run"       - execute skills
    require_skill_install,  # "skill:install"   - install new skills
    require_skill_read,     # "skill:read"      - list/view skills
)

@router.post("/skill/run", dependencies=[Depends(require_skill_run)])
async def run_skill():
    pass

@router.post("/skill/install", dependencies=[Depends(require_skill_install)])
async def install_skill():
    pass

@router.get("/skills", dependencies=[Depends(require_skill_read)])
async def list_skills():
    pass
```

#### Sandbox Permissions
```python
from backend.app.api.rbac_enforcement import (
    require_sandbox_run,    # "sandbox:run"     - execute sandboxes
    require_sandbox_read,   # "sandbox:read"    - view sandbox results
)

@router.post("/sandbox/run", dependencies=[Depends(require_sandbox_run)])
async def run_sandbox():
    pass

@router.get("/sandbox/{run_id}", dependencies=[Depends(require_sandbox_read)])
async def get_sandbox_result(run_id: str):
    pass
```

#### Chat Permissions
```python
from backend.app.api.rbac_enforcement import (
    require_chat_send,      # "chat:send"       - send messages
    require_chat_read,      # "chat:read"       - read messages
)

@router.post("/chat/message", dependencies=[Depends(require_chat_send)])
async def send_message():
    pass

@router.get("/chat/history", dependencies=[Depends(require_chat_read)])
async def get_chat_history():
    pass
```

## Complete Example

Here's a complete router module with multiple permission levels:

```python
from fastapi import APIRouter, Depends
from backend.app.api.rbac_enforcement import (
    require_admin,
    require_developer,
    require_viewer,
    require_agent_run,
    require_agent_read,
)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Read-only endpoint - viewers can see this
@router.get("")
async def list_agents(dependencies=[Depends(require_viewer)]):
    """List all agents. Available to all authenticated users."""
    return {"agents": []}

# Read with filters - viewers can see this
@router.get("/{agent_id}")
async def get_agent(agent_id: str, dependencies=[Depends(require_agent_read)]):
    """Get agent details. Available to all authenticated users."""
    return {"id": agent_id, "name": "Agent"}

# Execution endpoint - developers+ can do this
@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, dependencies=[Depends(require_agent_run)]):
    """Run an agent. Requires developer role or higher."""
    return {"status": "running", "agent_id": agent_id}

# Configuration endpoint - admins only
@router.post("/{agent_id}/config")
async def configure_agent(agent_id: str, dependencies=[Depends(require_admin)]):
    """Configure agent settings. Admins only."""
    return {"status": "configured"}
```

## Custom Permissions

If you need a permission that's not pre-built, use `PermissionDependency` directly:

```python
from fastapi import Depends
from backend.app.api.rbac_enforcement import PermissionDependency

# For a custom permission like "report:generate"
require_report_gen = Depends(PermissionDependency("report:generate"))

@router.post("/report/generate", dependencies=[require_report_gen])
async def generate_report():
    """Requires custom 'report:generate' permission."""
    pass
```

## Permission Denied Responses

When a user lacks required permissions, they receive a **403 Forbidden** response:

```json
{
    "detail": "Insufficient permissions: requires 'agent:run'"
}
```

The detail message includes the specific permission required, helping clients understand what they need to request access for.

## Unauthenticated Requests

If no authentication middleware ran and no principal is found:
- Request is treated as **viewer role** (read-only)
- Write operations will be blocked with 403
- Read operations will succeed

This allows graceful fallback for public APIs while still enforcing write protection.

## Best Practices

1. **Start specific, not broad**: Use `require_agent_run` instead of `require_developer` when you only need that specific permission
2. **Fail-safe defaults**: Unauthenticated requests default to viewer (read-only) - safe by default
3. **Document permissions**: Add permission requirements to route docstrings
4. **Log denials**: The RBAC system logs all permission denials for audit trails
5. **Use appropriate tier**: Match the permission level to the operation's risk level

## Integration with Existing Auth

The RBAC enforcement layer integrates with your existing authentication middleware:

```python
# In your main.py or middleware file
from fastapi import FastAPI
from backend.app.middleware.auth import auth_middleware

app = FastAPI()

@app.middleware("http")
async def add_auth_middleware(request, call_next):
    # Your auth logic here
    principal = get_principal_from_request(request)
    request.state.principal = principal
    return await call_next(request)
```

The RBAC dependencies automatically extract the principal from `request.state` and validate permissions.

## Testing RBAC-Protected Routes

```python
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

client = TestClient(app)

# Test admin access
def test_admin_access():
    request = MagicMock()
    request.state.principal = MagicMock(role="admin")
    # Route should succeed

# Test viewer blocked from write
def test_viewer_blocked():
    request = MagicMock()
    request.state.principal = MagicMock(role="viewer")
    # Route should fail with 403
```

## References

- **RBAC Module**: `backend/app/core/rbac.py` - Core permission logic
- **Dependencies**: `backend/app/api/rbac_enforcement.py` - FastAPI integration
- **Tests**: `tests/test_rbac_enforcement.py` - Permission test suite
