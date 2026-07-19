# Plugins Development Guide

Complete guide to developing plugins for X-Agent Core.

## Table of Contents

- [Overview](#overview)
- [Plugin Architecture](#plugin-architecture)
- [Getting Started](#getting-started)
- [Plugin Structure](#plugin-structure)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Testing](#testing)
- [Publishing](#publishing)
- [Best Practices](#best-practices)

## Overview

Plugins extend X-Agent Core functionality by adding new capabilities, integrations, and tools.

### Plugin Types

1. **Tool Plugins**: Add new tools for agents to use
2. **Integration Plugins**: Connect with third-party services
3. **LLM Plugins**: Add new LLM providers
4. **Storage Plugins**: Add new storage backends
5. **Observability Plugins**: Add monitoring and tracing

## Plugin Architecture

### Plugin Lifecycle

```
Load → Initialize → Register → Execute → Cleanup
```

### Plugin Interface

```python
from xagent.plugins import BasePlugin

class MyPlugin(BasePlugin):
    name = "my-plugin"
    version = "1.0.0"
    description = "My custom plugin"
    
    def initialize(self):
        """Initialize plugin"""
        pass
    
    def register(self):
        """Register plugin components"""
        pass
    
    def execute(self, context):
        """Execute plugin logic"""
        pass
    
    def cleanup(self):
        """Cleanup resources"""
        pass
```

## Getting Started

### Create Plugin Project

```bash
# Create plugin directory
mkdir my-xagent-plugin
cd my-xagent-plugin

# Initialize Python project
python -m venv venv
source venv/bin/activate

# Create plugin structure
mkdir -p src/xagent_my_plugin
touch src/xagent_my_plugin/__init__.py
touch src/xagent_my_plugin/plugin.py
touch setup.py
touch README.md
```

### Plugin Manifest

Create `plugin.manifest.json`:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "My custom plugin",
  "author": "Your Name",
  "license": "MIT",
  "entry_point": "xagent_my_plugin:MyPlugin",
  "dependencies": {
    "xagent-core": ">=0.1.0"
  },
  "capabilities": [
    "tools",
    "integrations"
  ],
  "permissions": [
    "read:workflows",
    "write:workflows"
  ]
}
```

## Plugin Structure

### Directory Layout

```
my-xagent-plugin/
├── src/
│   └── xagent_my_plugin/
│       ├── __init__.py
│       ├── plugin.py
│       ├── tools/
│       │   ├── __init__.py
│       │   └── my_tool.py
│       └── integrations/
│           ├── __init__.py
│           └── my_service.py
├── tests/
│   ├── __init__.py
│   ├── test_plugin.py
│   └── test_tools.py
├── docs/
│   ├── README.md
│   └── USAGE.md
├── setup.py
├── plugin.manifest.json
└── LICENSE
```

### Basic Plugin

```python
# src/xagent_my_plugin/plugin.py
from xagent.plugins import BasePlugin
from xagent.tools import Tool

class MyPlugin(BasePlugin):
    name = "my-plugin"
    version = "1.0.0"
    description = "My custom plugin"
    
    def initialize(self):
        """Initialize plugin"""
        self.logger.info("Initializing my plugin")
    
    def register(self):
        """Register tools and integrations"""
        # Register tools
        self.register_tool(MyTool())
        
        # Register integrations
        self.register_integration("my_service", MyServiceIntegration())
    
    def execute(self, context):
        """Execute plugin logic"""
        return {"status": "success"}
    
    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up my plugin")

class MyTool(Tool):
    name = "my_tool"
    description = "My custom tool"
    
    def execute(self, **kwargs):
        """Execute tool"""
        return {"result": "success"}
```

## API Reference

### BasePlugin

```python
class BasePlugin:
    name: str                    # Plugin name
    version: str                 # Plugin version
    description: str             # Plugin description
    
    def initialize(self):        # Initialize plugin
        pass
    
    def register(self):          # Register components
        pass
    
    def execute(self, context):  # Execute plugin
        pass
    
    def cleanup(self):           # Cleanup resources
        pass
```

### Tool Interface

```python
class Tool:
    name: str                    # Tool name
    description: str             # Tool description
    parameters: Dict             # Tool parameters
    
    def execute(self, **kwargs): # Execute tool
        pass
    
    def validate(self, **kwargs):# Validate parameters
        pass
```

### Integration Interface

```python
class Integration:
    name: str                    # Integration name
    
    def connect(self):           # Connect to service
        pass
    
    def disconnect(self):        # Disconnect from service
        pass
    
    def execute(self, action, **kwargs):  # Execute action
        pass
```

## Examples

### Tool Plugin

```python
from xagent.plugins import BasePlugin
from xagent.tools import Tool

class CalculatorPlugin(BasePlugin):
    name = "calculator"
    version = "1.0.0"
    
    def register(self):
        self.register_tool(AddTool())
        self.register_tool(SubtractTool())
        self.register_tool(MultiplyTool())

class AddTool(Tool):
    name = "add"
    description = "Add two numbers"
    parameters = {
        "a": {"type": "number"},
        "b": {"type": "number"}
    }
    
    def execute(self, a: float, b: float):
        return {"result": a + b}
```

### Integration Plugin

```python
from xagent.plugins import BasePlugin
from xagent.integrations import Integration

class SlackPlugin(BasePlugin):
    name = "slack"
    version = "1.0.0"
    
    def register(self):
        self.register_integration("slack", SlackIntegration())

class SlackIntegration(Integration):
    name = "slack"
    
    def connect(self):
        self.client = SlackClient(token=os.getenv("SLACK_TOKEN"))
    
    def execute(self, action, **kwargs):
        if action == "send_message":
            return self.client.chat_postMessage(**kwargs)
        elif action == "list_channels":
            return self.client.conversations_list()
```

## Testing

### Unit Tests

```python
import pytest
from xagent_my_plugin import MyPlugin

@pytest.fixture
def plugin():
    return MyPlugin()

def test_plugin_initialization(plugin):
    plugin.initialize()
    assert plugin.name == "my-plugin"

def test_plugin_registration(plugin):
    plugin.register()
    assert len(plugin.tools) > 0

def test_tool_execution(plugin):
    plugin.register()
    result = plugin.tools[0].execute()
    assert result["status"] == "success"
```

### Integration Tests

```python
def test_plugin_with_xagent():
    from xagent import XAgent
    
    agent = XAgent()
    agent.load_plugin(MyPlugin())
    
    # Test plugin integration
    result = agent.execute_tool("my_tool")
    assert result["status"] == "success"
```

## Publishing

### Package Plugin

```bash
# Create distribution
python setup.py sdist bdist_wheel

# Upload to PyPI
twine upload dist/*
```

### setup.py

```python
from setuptools import setup, find_packages

setup(
    name="xagent-my-plugin",
    version="1.0.0",
    description="My custom X-Agent plugin",
    author="Your Name",
    author_email="your@email.com",
    url="https://github.com/yourusername/xagent-my-plugin",
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "xagent-core>=0.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=3.0",
            "black>=22.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "xagent.plugins": [
            "my_plugin = xagent_my_plugin:MyPlugin",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
    ],
)
```

### Plugin Registry

Register your plugin in the X-Agent Plugin Registry:

1. Create GitHub repository
2. Add `xagent-plugin` topic
3. Submit to registry: https://registry.x-agent.dev

## Best Practices

1. **Naming**: Use descriptive names with `xagent-` prefix
2. **Documentation**: Include comprehensive README and examples
3. **Testing**: Aim for >80% test coverage
4. **Error Handling**: Handle errors gracefully
5. **Logging**: Use structured logging
6. **Performance**: Optimize for performance
7. **Security**: Validate all inputs
8. **Compatibility**: Test with multiple X-Agent versions

## Troubleshooting

### Plugin Not Loading

```python
# Check plugin manifest
import json
with open("plugin.manifest.json") as f:
    manifest = json.load(f)
    print(manifest)

# Check entry point
from xagent.plugins import load_plugin
plugin = load_plugin("my-plugin")
```

### Tool Not Executing

```python
# Check tool registration
plugin.register()
print(plugin.tools)

# Check tool parameters
tool = plugin.tools[0]
print(tool.parameters)
```

## Additional Resources

- [Plugin Examples](https://github.com/x-agent/xagent-plugins)
- [Plugin Registry](https://registry.x-agent.dev)
- [API Documentation](./API.md)
- [Contributing Guide](./CONTRIBUTING.md)

---

Last Updated: 2026-05-28
