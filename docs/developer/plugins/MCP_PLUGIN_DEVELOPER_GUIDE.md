# MCP插件开发者指南 v1.0

## 目录

1. [快速开始](#快速开始)
2. [项目结构](#项目结构)
3. [开发环境](#开发环境)
4. [创建第一个插件](#创建第一个插件)
5. [Manifest配置](#manifest配置)
6. [实现工具](#实现工具)
7. [实现资源](#实现资源)
8. [配置管理](#配置管理)
9. [错误处理](#错误处理)
10. [测试](#测试)
11. [文档](#文档)
12. [发布](#发布)
13. [常见问题](#常见问题)

## 快速开始

### 最快5分钟创建一个MCP插件

```bash
# 1. 克隆模板
git clone https://github.com/x-agent/mcp-plugin-template my-plugin
cd my-plugin

# 2. 编辑manifest.json
# 修改name, version, author等信息

# 3. 实现插件逻辑
# 编辑main.py或main.js

# 4. 测试插件
python -m pytest tests/

# 5. 提交到市场
# 上传到X-Agent插件市场
```

## 项目结构

### 推荐的项目结构

```
my-plugin/
├── manifest.json              # 插件清单（必需）
├── README.md                  # 英文文档
├── README_zh.md               # 中文文档
├── LICENSE                    # 许可证
├── requirements.txt           # Python依赖（如果是Python插件）
├── package.json               # Node.js依赖（如果是Node.js插件）
├── src/                       # 源代码
│   ├── main.py               # 入口点（Python）
│   ├── main.js               # 入口点（Node.js）
│   ├── tools/                # 工具实现
│   │   ├── __init__.py
│   │   ├── github_tools.py
│   │   └── ...
│   ├── resources/            # 资源实现
│   │   ├── __init__.py
│   │   ├── github_resources.py
│   │   └── ...
│   └── utils/                # 工具函数
│       ├── __init__.py
│       ├── config.py
│       ├── logger.py
│       └── ...
├── tests/                     # 测试
│   ├── __init__.py
│   ├── test_tools.py
│   ├── test_resources.py
│   ├── test_config.py
│   └── ...
├── docs/                      # 文档
│   ├── API.md
│   ├── EXAMPLES.md
│   ├── TROUBLESHOOTING.md
│   └── ...
└── .github/                   # GitHub配置
    └── workflows/
        └── ci.yml             # CI/CD流程
```

## 开发环境

### Python插件开发环境

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 2. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. 安装开发工具
pip install pytest pytest-cov pylint flake8 black bandit

# 4. 配置pre-commit钩子
pip install pre-commit
pre-commit install
```

### Node.js插件开发环境

```bash
# 1. 初始化项目
npm init -y

# 2. 安装依赖
npm install

# 3. 安装开发工具
npm install --save-dev eslint prettier jest @types/node

# 4. 配置pre-commit钩子
npm install husky lint-staged
npx husky install
```

## 创建第一个插件

### Python示例：Hello World插件

**manifest.json**：
```json
{
  "schema_version": "1.0",
  "name": "hello-world",
  "version": "1.0.0",
  "type": "mcp-plugin",
  "xagent_compatibility": {
    "min_version": "0.1.0",
    "max_version": "1.0.0"
  },
  "metadata": {
    "display_name": "Hello World",
    "description": "A simple hello world plugin",
    "description_zh": "一个简单的示例插件",
    "author": "Your Name",
    "license": "MIT"
  },
  "chinese": {
    "name": "你好世界",
    "description": "这是一个简单的示例插件，演示如何创建MCP插件"
  },
  "capabilities": {
    "tools": true,
    "resources": false,
    "prompts": false
  },
  "permissions": {
    "network": { "required": false },
    "filesystem": { "required": false },
    "environment": { "required": false }
  },
  "entry_point": {
    "type": "python",
    "module": "main",
    "class": "HelloWorldPlugin"
  },
  "dependencies": {
    "python": ">=3.11"
  },
  "tools": [
    {
      "name": "hello",
      "description": "Say hello",
      "description_zh": "问好",
      "input_schema": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name to greet"
          }
        },
        "required": ["name"]
      }
    }
  ]
}
```

**src/main.py**：
```python
"""Hello World MCP Plugin"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class HelloWorldPlugin:
    """Hello World Plugin Server"""

    def __init__(self, config: dict[str, Any] = None):
        """Initialize plugin"""
        self.config = config or {}
        logger.info("HelloWorldPlugin initialized")

    async def hello(self, name: str) -> dict[str, Any]:
        """Say hello to someone"""
        message = f"Hello, {name}!"
        logger.info(f"Greeting: {message}")
        return {
            "status": "success",
            "message": message
        }

    async def handle_tool_call(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Handle tool calls"""
        if tool_name == "hello":
            return await self.hello(**args)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
```

**tests/test_hello.py**：
```python
"""Tests for Hello World Plugin"""

import pytest
from src.main import HelloWorldPlugin


@pytest.fixture
def plugin():
    """Create plugin instance"""
    return HelloWorldPlugin()


@pytest.mark.asyncio
async def test_hello(plugin):
    """Test hello tool"""
    result = await plugin.hello("World")
    assert result["status"] == "success"
    assert "Hello, World!" in result["message"]


@pytest.mark.asyncio
async def test_hello_with_different_names(plugin):
    """Test hello with different names"""
    names = ["Alice", "Bob", "Charlie"]
    for name in names:
        result = await plugin.hello(name)
        assert result["status"] == "success"
        assert name in result["message"]
```

## Manifest配置

### 完整的Manifest示例

参见 [MCP_PLUGIN_MANIFEST_SPEC.md](./MCP_PLUGIN_MANIFEST_SPEC.md)

### 常见配置

#### 1. 基本信息

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "metadata": {
    "display_name": "My Plugin",
    "description": "Plugin description",
    "author": "Your Name",
    "license": "MIT"
  }
}
```

#### 2. 兼容性

```json
{
  "xagent_compatibility": {
    "min_version": "0.1.0",
    "max_version": "1.0.0"
  }
}
```

#### 3. 权限

```json
{
  "permissions": {
    "network": {
      "required": true,
      "domains": ["api.example.com"]
    },
    "filesystem": {
      "required": false,
      "paths": ["/tmp/plugin-data"]
    },
    "environment": {
      "required": false,
      "variables": ["API_KEY"]
    }
  }
}
```

#### 4. 配置参数

```json
{
  "configuration": {
    "api_key": {
      "type": "string",
      "required": true,
      "description": "API Key",
      "secret": true
    },
    "timeout": {
      "type": "integer",
      "required": false,
      "default": 30,
      "min": 1,
      "max": 300
    }
  }
}
```

## 实现工具

### 工具定义

在manifest.json中定义工具：

```json
{
  "tools": [
    {
      "name": "list_repos",
      "description": "List repositories",
      "description_zh": "列出仓库",
      "input_schema": {
        "type": "object",
        "properties": {
          "username": {
            "type": "string",
            "description": "GitHub username"
          },
          "limit": {
            "type": "integer",
            "default": 10
          }
        },
        "required": ["username"]
      }
    }
  ]
}
```

### 工具实现

**Python示例**：

```python
"""GitHub Tools"""

import logging
from typing import Any
import requests

logger = logging.getLogger(__name__)


class GitHubTools:
    """GitHub API Tools"""

    def __init__(self, api_key: str):
        """Initialize with API key"""
        self.api_key = api_key
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {api_key}",
            "Accept": "application/vnd.github.v3+json"
        }

    async def list_repos(self, username: str, limit: int = 10) -> dict[str, Any]:
        """List user repositories"""
        try:
            url = f"{self.base_url}/users/{username}/repos"
            params = {"per_page": limit}
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            repos = response.json()
            return {
                "status": "success",
                "data": repos,
                "count": len(repos)
            }
        except Exception as e:
            logger.error(f"Failed to list repos: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def create_issue(self, owner: str, repo: str, title: str, body: str) -> dict[str, Any]:
        """Create an issue"""
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/issues"
            data = {"title": title, "body": body}
            
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            
            issue = response.json()
            return {
                "status": "success",
                "data": issue,
                "issue_number": issue["number"]
            }
        except Exception as e:
            logger.error(f"Failed to create issue: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
```

## 实现资源

### 资源定义

在manifest.json中定义资源：

```json
{
  "resources": [
    {
      "uri": "github://repos/user/repo",
      "name": "Repository",
      "description": "GitHub repository",
      "mime_type": "application/json"
    }
  ]
}
```

### 资源实现

**Python示例**：

```python
"""GitHub Resources"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class GitHubResources:
    """GitHub API Resources"""

    def __init__(self, api_key: str):
        """Initialize with API key"""
        self.api_key = api_key

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository information"""
        try:
            # Implementation
            return {
                "status": "success",
                "data": {
                    "owner": owner,
                    "repo": repo,
                    "url": f"https://github.com/{owner}/{repo}"
                }
            }
        except Exception as e:
            logger.error(f"Failed to get repository: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
```

## 配置管理

### 读取配置

```python
"""Configuration Management"""

import os
import json
from typing import Any


class ConfigManager:
    """Manage plugin configuration"""

    def __init__(self, config_file: str = None):
        """Initialize config manager"""
        self.config_file = config_file or os.getenv("PLUGIN_CONFIG_FILE")
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file"""
        if not self.config_file or not os.path.exists(self.config_file):
            return {}

        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load config: {e}")
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def get_required(self, key: str) -> Any:
        """Get required configuration value"""
        if key not in self.config:
            raise ValueError(f"Required configuration missing: {key}")
        return self.config[key]

    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self.config[key] = value

    def save(self) -> None:
        """Save configuration to file"""
        if not self.config_file:
            raise ValueError("Config file not specified")

        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)
```

## 错误处理

### 标准错误响应

```python
"""Error Handling"""

from typing import Any


class PluginError(Exception):
    """Base plugin error"""
    pass


class ConfigurationError(PluginError):
    """Configuration error"""
    pass


class ToolExecutionError(PluginError):
    """Tool execution error"""
    pass


def error_response(error: Exception, context: str = "") -> dict[str, Any]:
    """Create error response"""
    return {
        "status": "error",
        "error_type": type(error).__name__,
        "message": str(error),
        "context": context
    }


async def safe_tool_call(tool_func, *args, **kwargs) -> dict[str, Any]:
    """Safely call a tool with error handling"""
    try:
        result = await tool_func(*args, **kwargs)
        return {
            "status": "success",
            "data": result
        }
    except ConfigurationError as e:
        return error_response(e, "configuration")
    except ToolExecutionError as e:
        return error_response(e, "execution")
    except Exception as e:
        return error_response(e, "unknown")
```

## 测试

### 单元测试

```python
"""Unit Tests"""

import pytest
from src.main import MyPlugin


@pytest.fixture
def plugin():
    """Create plugin instance"""
    return MyPlugin(config={"api_key": "test-key"})


def test_plugin_initialization(plugin):
    """Test plugin initialization"""
    assert plugin is not None
    assert plugin.config["api_key"] == "test-key"


@pytest.mark.asyncio
async def test_tool_execution(plugin):
    """Test tool execution"""
    result = await plugin.handle_tool_call("my_tool", {"param": "value"})
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_error_handling(plugin):
    """Test error handling"""
    result = await plugin.handle_tool_call("invalid_tool", {})
    assert result["status"] == "error"
```

### 集成测试

```python
"""Integration Tests"""

import pytest
from src.main import MyPlugin


@pytest.mark.asyncio
async def test_full_workflow():
    """Test full workflow"""
    plugin = MyPlugin(config={"api_key": "test-key"})
    
    # Test tool 1
    result1 = await plugin.handle_tool_call("tool1", {"param": "value"})
    assert result1["status"] == "success"
    
    # Test tool 2 with result from tool 1
    result2 = await plugin.handle_tool_call("tool2", {"data": result1["data"]})
    assert result2["status"] == "success"
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_tools.py

# 生成覆盖率报告
pytest --cov=src tests/

# 运行并显示详细输出
pytest -v
```

## 文档

### README.md模板

```markdown
# My Plugin

简短的插件描述。

## 功能

- 功能1
- 功能2
- 功能3

## 安装

```bash
# 在X-Agent中安装
# 或从源代码安装
git clone https://github.com/user/my-plugin
cd my-plugin
pip install -r requirements.txt
```

## 配置

```json
{
  "api_key": "your-api-key",
  "timeout": 30
}
```

## 使用

### 示例1

```python
# 代码示例
```

### 示例2

```python
# 代码示例
```

## API

### tool_name

描述

**参数**：
- param1 (string): 参数1
- param2 (integer): 参数2

**返回**：
```json
{
  "status": "success",
  "data": {}
}
```

## 常见问题

### Q: 如何配置API密钥？
A: 在插件配置中设置api_key字段。

## 许可证

MIT
```

## 发布

### 发布前检查清单

- [ ] Manifest.json有效且完整
- [ ] README.md完整
- [ ] README_zh.md完整
- [ ] 代码质量 >= 8.0/10
- [ ] 测试覆盖率 >= 80%
- [ ] 无CRITICAL安全漏洞
- [ ] 无HIGH安全漏洞
- [ ] 所有测试通过
- [ ] 文档完整

### 发布步骤

1. **准备发布**
   ```bash
   # 更新版本号
   # 更新CHANGELOG
   # 提交代码
   git add .
   git commit -m "Release v1.0.0"
   git tag v1.0.0
   git push origin main --tags
   ```

2. **提交到市场**
   ```bash
   # 打包插件
   zip -r my-plugin.zip .
   
   # 上传到X-Agent插件市场
   # 访问 https://marketplace.x-agent.com/submit
   ```

3. **等待审核**
   - 自动化检查：1-2小时
   - 人工审核：2-3天
   - 安全审核：1-2天
   - 兼容性测试：1-2天

4. **发布**
   - 审核通过后自动发布
   - 在插件市场中显示

## 常见问题

### Q: 如何调试插件？

A: 使用日志记录：

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

### Q: 如何处理异步操作？

A: 使用async/await：

```python
async def my_tool(self, param: str) -> dict:
    """My tool"""
    result = await self.async_operation(param)
    return result
```

### Q: 如何访问配置？

A: 使用ConfigManager：

```python
config = ConfigManager()
api_key = config.get_required("api_key")
timeout = config.get("timeout", 30)
```

### Q: 如何处理错误？

A: 使用标准错误响应：

```python
try:
    result = await self.do_something()
    return {"status": "success", "data": result}
except Exception as e:
    return {"status": "error", "message": str(e)}
```

### Q: 如何测试插件？

A: 使用pytest：

```bash
pytest tests/
pytest --cov=src tests/
```

### Q: 如何发布插件？

A: 参见[发布](#发布)部分。

## 相关资源

- [MCP插件Manifest规范](./MCP_PLUGIN_MANIFEST_SPEC.md)
- [MCP插件审核标准](./MCP_PLUGIN_REVIEW_STANDARDS.md)
- [MCP插件API参考](./MCP_PLUGIN_API_REFERENCE.md)
- [MCP插件示例](./MCP_PLUGIN_EXAMPLES.md)
