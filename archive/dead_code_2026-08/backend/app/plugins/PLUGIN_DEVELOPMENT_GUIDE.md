# X-Agent Plugin Development Guide

## Overview

The X-Agent plugin system provides a standardized way to extend functionality through modular, sandboxed plugins. This guide covers plugin development, registration, and deployment.

## Plugin Architecture

### Core Components

1. **Plugin Schema** - Standardized metadata and configuration
2. **Plugin Loader** - Dynamic loading with sandboxing
3. **Plugin Marketplace** - Discovery and installation
4. **Lifecycle Manager** - Install/enable/disable/uninstall
5. **Audit System** - Complete operation tracking

## Plugin Structure

### Required Metadata

Every plugin must define:

```python
PLUGIN_NAME = "my_plugin"
PLUGIN_VERSION = "1.0.0"
PLUGIN_AUTHOR = "Your Name"
PLUGIN_DESCRIPTION = "What this plugin does"
PLUGIN_CAPABILITIES = ["capability1", "capability2"]
PLUGIN_PERMISSIONS = ["resource:action"]
PLUGIN_RISK_LEVEL = "medium"  # low, medium, high, critical
PLUGIN_DEPENDENCIES = []  # Other plugin IDs
```

### Plugin Interface

Implement these methods:

```python
def initialize(config: dict) -> bool:
    """Initialize plugin with configuration"""

def execute(action: str, **kwargs) -> dict:
    """Execute plugin action"""

def get_capabilities() -> list[str]:
    """Return list of capabilities"""

def get_permissions() -> list[str]:
    """Return required permissions"""

def get_metadata() -> dict:
    """Return plugin metadata"""

def shutdown() -> bool:
    """Graceful shutdown"""
```

## Development Workflow

### 1. Create Plugin

Start with the template:

```bash
cp backend/app/plugins/template_plugin.py backend/app/plugins/my_plugin.py
```

### 2. Implement Logic

```python
class MyPlugin:
    PLUGIN_NAME = "my_plugin"
    PLUGIN_VERSION = "1.0.0"
    # ... metadata ...

    def execute(self, action: str, **kwargs) -> dict:
        if action == "my_action":
            return self._my_action(**kwargs)
        return {"error": "Unknown action"}

    def _my_action(self, **kwargs) -> dict:
        # Your implementation
        return {"success": True, "data": result}
```

### 3. Register Plugin

```python
from backend.app.core.plugin_schema import PluginSchema
from backend.app.core.plugin_marketplace import marketplace

plugin_schema = PluginSchema(
    name="my_plugin",
    version="1.0.0",
    author="Your Name",
    description="Plugin description",
    capabilities=["capability1"],
    permissions=["resource:action"],
    risk_level="medium",
    install_url="file:///path/to/plugin",
    documentation_url="https://docs.example.com/my_plugin"
)

marketplace.register_plugin(plugin_schema)
```

### 4. Install Plugin

```python
from backend.app.core.plugin_marketplace import installation_manager
from backend.app.core.plugin_schema import PluginInstallRequest

request = PluginInstallRequest(
    plugin_id=plugin_schema.plugin_id,
    config={"key": "value"},
    auto_enable=True
)

success, error = installation_manager.install_plugin(request)
```

## Permissions System

Plugins request permissions for resources:

```python
PLUGIN_PERMISSIONS = [
    "file:read",
    "file:write",
    "network:http",
    "database:query"
]
```

Permissions are validated before execution:

```python
from backend.app.core.plugin_loader import permission_manager

if permission_manager.has_permission(plugin_id, "file:read"):
    # Safe to read files
    pass
```

## Sandboxing

Plugins run in restricted environments:

- Limited module imports (json, datetime, uuid, logging, re, collections)
- No access to file system (open, exec, eval)
- No access to globals/locals
- Restricted builtins

## Lifecycle Management

### Installation

```python
installation_manager.install_plugin(request)
# Status: INSTALLING -> INACTIVE
```

### Enabling

```python
installation_manager.enable_plugin(plugin_id)
# Status: INACTIVE -> ACTIVE
```

### Disabling

```python
installation_manager.disable_plugin(plugin_id)
# Status: ACTIVE -> DISABLED
```

### Uninstallation

```python
installation_manager.uninstall_plugin(request)
# Status: UNINSTALLING -> INACTIVE
```

### Upgrading

```python
installation_manager.upgrade_plugin(plugin_id, "2.0.0")
```

## Compatibility Checking

Verify plugin compatibility before installation:

```python
from backend.app.core.plugin_loader import compatibility_checker

check = compatibility_checker.check_compatibility(
    plugin_schema,
    installed_plugins
)

if not check.compatible:
    print(f"Issues: {check.issues}")
    print(f"Warnings: {check.warnings}")
```

## Audit and Monitoring

All plugin operations are audited:

```python
from backend.app.core.plugin_lifecycle import audit_system

# Get audit trail for plugin
records = audit_system.get_plugin_audit_trail(plugin_id)

# Export audit report
report = audit_system.export_audit_report(plugin_id)
```

## Error Handling

Plugins should handle errors gracefully:

```python
def execute(self, action: str, **kwargs) -> dict:
    try:
        # Your logic
        return {"success": True, "data": result}
    except ValueError as e:
        return {"success": False, "error": f"Invalid input: {e}"}
    except Exception as e:
        self.logger.error(f"Execution failed: {e}")
        return {"success": False, "error": "Internal error"}
```

## Testing Plugins

```python
from backend.app.core.plugin_loader import plugin_loader
from backend.app.core.plugin_schema import PluginSchema

# Create test plugin
plugin_schema = PluginSchema(
    name="test_plugin",
    version="1.0.0",
    author="Test",
    description="Test",
    install_url="file:///path/to/plugin",
    documentation_url="https://example.com"
)

# Load plugin
success, error = plugin_loader.load_plugin(plugin_schema)
assert success, error

# Execute action
plugin = plugin_loader.get_plugin(plugin_schema.plugin_id)
result = plugin.execute("test_action")
assert result["success"]
```

## Best Practices

1. **Minimal Dependencies** - Keep plugins lightweight
2. **Clear Permissions** - Request only needed permissions
3. **Error Handling** - Handle all error cases
4. **Logging** - Use logging for debugging
5. **Documentation** - Document all capabilities
6. **Testing** - Test before deployment
7. **Versioning** - Follow semantic versioning
8. **Security** - Validate all inputs

## Example: Data Processing Plugin

```python
class DataProcessorPlugin:
    PLUGIN_NAME = "data_processor"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_CAPABILITIES = ["filter", "transform", "aggregate"]
    PLUGIN_PERMISSIONS = ["data:read", "data:write"]

    def execute(self, action: str, **kwargs) -> dict:
        if action == "filter":
            return self._filter(kwargs.get("data"), kwargs.get("condition"))
        elif action == "transform":
            return self._transform(kwargs.get("data"), kwargs.get("mapping"))
        return {"error": "Unknown action"}

    def _filter(self, data, condition):
        try:
            result = [item for item in data if condition(item)]
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _transform(self, data, mapping):
        try:
            result = [{mapping.get(k, k): v for k, v in item.items()} for item in data]
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

## Troubleshooting

### Plugin Won't Load

- Check install path exists
- Verify __init__.py present (for packages)
- Check for syntax errors
- Review sandbox restrictions

### Permission Denied

- Verify permissions granted
- Check permission names match
- Review audit log for details

### Compatibility Issues

- Check dependencies installed
- Verify version compatibility
- Review compatibility check results

## Support

For issues or questions:
- Check audit logs: `audit_system.get_plugin_audit_trail(plugin_id)`
- Review plugin metadata: `marketplace.get_plugin(plugin_id)`
- Check lifecycle state: `lifecycle_manager.get_lifecycle_state(plugin_id)`
