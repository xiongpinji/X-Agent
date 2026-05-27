"""Integration Guide for Filesystem Management System

This document explains how to integrate the new workspace management system
with the existing tools.py and tool execution pipeline.
"""

# Filesystem Management Integration Guide

## Overview

The new filesystem management system provides flexible, secure file access through:
- **WorkspaceManager**: User-isolated workspace management
- **PathMapper**: Cross-platform path mapping and validation
- **MountManager**: Directory mounting with permission control
- **FileAccessControl**: Permission checking and audit logging
- **FileSystemManager**: Unified interface for all components

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Tool Execution                        │
│                   (tools.py/ToolRegistry)                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              FileSystemManager                           │
│  (Unified interface for file system operations)          │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬──────────────┐
        ▼            ▼            ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│ Workspace    │ │ Path     │ │ Mount    │ │ File Access  │
│ Manager      │ │ Mapper   │ │ Manager  │ │ Control      │
└──────────────┘ └──────────┘ └──────────┘ └──────────────┘
```

## Integration Steps

### 1. Initialize FileSystemManager in Tool Context

When creating a tool execution context, initialize the FileSystemManager:

```python
from backend.app.core.filesystem_manager import create_file_system_manager
from backend.app.settings import PROJECT_ROOT

# In your tool initialization code
fs_manager = create_file_system_manager(
    workspace_base=PROJECT_ROOT / "workspaces",
    user_id=context.user_id,
    data_dir=PROJECT_ROOT / "data",
)
```

### 2. Update Tool Path Resolution

Replace the existing `_resolve_tool_path()` function with FileSystemManager:

**Before:**
```python
def _resolve_tool_path(path: str) -> Path:
    """Restrict file paths to the project root."""
    base = Path(PROJECT_ROOT).resolve()
    target = Path(path).expanduser().resolve()
    # ... validation logic
    return target
```

**After:**
```python
def _resolve_tool_path(path: str, fs_manager: FileSystemManager) -> Path:
    """Resolve path using FileSystemManager."""
    return fs_manager.resolve_path(path)
```

### 3. Add Permission Checks to Tool Handlers

Before file operations, validate access:

```python
async def read_file_tool(path: str, fs_manager: FileSystemManager) -> str:
    """Read file with permission checking."""
    # Validate read access
    allowed, reason = fs_manager.validate_read_access(path)
    if not allowed:
        raise PermissionError(f"Read access denied: {reason}")
    
    # Resolve path
    real_path = fs_manager.resolve_path(path)
    
    # Perform operation
    content = real_path.read_text()
    
    # Audit operation
    fs_manager.audit_operation("read", path, True)
    
    return content
```

### 4. Integrate with ToolRegistry

Modify ToolRegistry to use FileSystemManager:

```python
class ToolRegistry:
    def __init__(
        self,
        policy_engine: ToolPolicyEngine,
        approval_store: ApprovalStore | None = None,
        execution_store: ToolExecutionStore | None = None,
        fs_manager: FileSystemManager | None = None,
    ) -> None:
        self._policy = policy_engine
        self._approval_store = approval_store
        self._execution_store = execution_store
        self._fs_manager = fs_manager
        self._tools: dict[str, ToolDefinition] = {}

    async def execute(
        self,
        context: RunContext,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolCallRecord:
        # ... existing code ...
        
        # Pass fs_manager to tool handler
        if self._fs_manager:
            arguments["_fs_manager"] = self._fs_manager
        
        # ... rest of execution ...
```

### 5. Update Tool Definitions

Add filesystem manager parameter to tool handlers:

```python
async def write_file_tool(
    path: str,
    content: str,
    _fs_manager: FileSystemManager,
) -> dict:
    """Write file with permission checking."""
    # Validate write access
    allowed, reason = _fs_manager.validate_write_access(path, len(content))
    if not allowed:
        raise PermissionError(f"Write access denied: {reason}")
    
    # Resolve path
    real_path = _fs_manager.resolve_path(path)
    
    # Perform operation
    real_path.parent.mkdir(parents=True, exist_ok=True)
    real_path.write_text(content)
    
    # Audit operation
    _fs_manager.audit_operation("write", path, True)
    
    return {"success": True, "path": path}
```

## API Integration

### Register Workspace API Routes

In your FastAPI app initialization:

```python
from fastapi import FastAPI
from backend.app.api.workspace import router as workspace_router

app = FastAPI()

# Register workspace management routes
app.include_router(workspace_router)
```

### Available Endpoints

- `POST /api/v1/workspace/create` - Create workspace
- `GET /api/v1/workspace/list` - List workspaces
- `DELETE /api/v1/workspace/{workspace_id}` - Delete workspace
- `POST /api/v1/workspace/mount` - Mount directory
- `DELETE /api/v1/workspace/mount/{mount_id}` - Unmount directory
- `GET /api/v1/workspace/mounts` - List mounts
- `POST /api/v1/workspace/validate-path` - Validate path access
- `GET /api/v1/workspace/audit-logs` - Get audit logs
- `POST /api/v1/workspace/cleanup-expired` - Clean up expired workspaces

## Frontend Integration

### Use FolderSelector Component

```tsx
import { FolderSelector } from './components/FolderSelector';

function App() {
  const handleMountChange = (mounts) => {
    console.log('Mounts updated:', mounts);
  };

  const handleError = (error) => {
    console.error('Mount error:', error);
  };

  return (
    <FolderSelector
      onMountChange={handleMountChange}
      onError={handleError}
    />
  );
}
```

## Security Considerations

### Path Traversal Prevention

The PathMapper prevents path traversal attacks:
- Validates all paths are within workspace
- Resolves symlinks and checks targets
- Blocks forbidden system directories

### User Isolation

WorkspaceManager ensures user isolation:
- Each user has separate workspace directory
- Mounts are per-user
- Access control is user-specific

### Permission Model

FileAccessControl implements:
- Read/write/delete permissions
- File type restrictions
- Size limits
- Operation auditing

### Audit Logging

All file operations are logged:
- User ID, operation type, path
- Success/failure status
- Reason for denial
- Timestamp

## Migration Path

### Phase 1: Parallel Operation
- Keep existing `_resolve_tool_path()` function
- Add FileSystemManager alongside
- Gradually migrate tools

### Phase 2: Gradual Migration
- Migrate high-risk tools first (write, delete)
- Then migrate read tools
- Monitor for issues

### Phase 3: Full Integration
- Remove old path resolution
- Make FileSystemManager mandatory
- Deprecate old functions

## Configuration

### Environment Variables

```bash
# Workspace configuration
XAGENT_WORKSPACE_BASE=/path/to/workspaces
XAGENT_WORKSPACE_MAX_SIZE_MB=1000
XAGENT_WORKSPACE_TTL_HOURS=24

# Mount configuration
XAGENT_MOUNT_STORAGE_PATH=/path/to/mounts.json

# Audit configuration
XAGENT_AUDIT_PATH=/path/to/audit.jsonl
XAGENT_AUDIT_HMAC_SECRET=your-secret-key
```

### Settings Integration

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    workspace_base: Path = PROJECT_ROOT / "workspaces"
    workspace_max_size_mb: int = 1000
    workspace_ttl_hours: int = 24
    mount_storage_path: Path = PROJECT_ROOT / "data" / "mounts.json"
    audit_path: Path = PROJECT_ROOT / "data" / "audit.jsonl"
```

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
pytest tests/test_workspace_management.py -v
```

### Integration Tests

Test with actual tool execution:

```bash
pytest tests/test_tools.py -v -k "filesystem"
```

### Security Tests

Verify security measures:

```bash
pytest tests/test_workspace_management.py::TestPathMapper -v
pytest tests/test_workspace_management.py::TestFileAccessControl -v
```

## Performance Considerations

### Path Resolution Caching

For frequently accessed paths, consider caching:

```python
from functools import lru_cache

@lru_cache(maxsize=1024)
def resolve_path_cached(path: str, user_id: str) -> Path:
    return fs_manager.resolve_path(path)
```

### Audit Log Rotation

Implement log rotation for audit logs:

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    audit_path,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=10,
)
```

## Troubleshooting

### Common Issues

1. **Path not found**: Verify path is within workspace
2. **Permission denied**: Check user permissions and mount mode
3. **Symlink attack**: Ensure symlink targets are within workspace
4. **Mount conflicts**: Check for duplicate mount paths

### Debug Logging

Enable debug logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("filesystem_manager")
```

## Future Enhancements

- [ ] Workspace quotas with enforcement
- [ ] Automatic workspace cleanup
- [ ] Mount point statistics
- [ ] Permission inheritance
- [ ] Workspace snapshots
- [ ] Collaborative workspaces
- [ ] Cloud storage integration
- [ ] Encryption at rest

## References

- PathMapper: Cross-platform path handling
- WorkspaceManager: User workspace isolation
- MountManager: Directory mounting
- FileAccessControl: Permission and audit system
- FileSystemManager: Unified interface
