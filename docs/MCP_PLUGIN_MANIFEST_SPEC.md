# MCP插件Manifest规范 v1.0

## 概述

本文档定义了X-Agent MCP（Model Context Protocol）插件的标准Manifest规范。所有MCP插件必须遵循此规范才能在X-Agent插件市场中发布和使用。

## 文件格式

MCP插件Manifest必须是有效的JSON文件，命名为 `manifest.json`，放在插件根目录。

## 完整Schema

```json
{
  "schema_version": "1.0",
  "name": "plugin-name",
  "version": "1.0.0",
  "type": "mcp-plugin",
  "xagent_compatibility": {
    "min_version": "0.1.0",
    "max_version": "1.0.0"
  },
  "metadata": {
    "display_name": "插件显示名称",
    "description": "插件功能描述（英文）",
    "description_zh": "插件功能描述（中文）",
    "author": "作者名称",
    "author_email": "author@example.com",
    "license": "MIT",
    "homepage": "https://example.com",
    "repository": "https://github.com/user/repo",
    "icon_url": "https://example.com/icon.png",
    "category": "development"
  },
  "chinese": {
    "name": "插件中文名",
    "description": "这个插件是干什么的（小白语言）",
    "usage": "怎么用（步骤化）",
    "适合谁用": ["开发者", "数据分析师"],
    "常见问题": [
      {
        "question": "如何配置API密钥？",
        "answer": "在插件设置中输入你的API密钥..."
      }
    ],
    "tutorial": "详细的使用教程链接或内容"
  },
  "capabilities": {
    "tools": true,
    "resources": true,
    "prompts": false
  },
  "permissions": {
    "network": {
      "required": true,
      "domains": ["api.example.com", "*.example.com"]
    },
    "filesystem": {
      "required": false,
      "paths": ["/tmp/plugin-data"]
    },
    "environment": {
      "required": false,
      "variables": ["API_KEY", "DEBUG_MODE"]
    }
  },
  "entry_point": {
    "type": "python",
    "module": "main",
    "class": "PluginServer"
  },
  "dependencies": {
    "python": ">=3.11",
    "packages": {
      "requests": ">=2.31.0",
      "pydantic": ">=2.0.0"
    }
  },
  "configuration": {
    "api_key": {
      "type": "string",
      "required": true,
      "description": "API密钥",
      "description_zh": "用于认证的API密钥",
      "secret": true
    },
    "timeout": {
      "type": "integer",
      "required": false,
      "default": 30,
      "description": "Request timeout in seconds",
      "description_zh": "请求超时时间（秒）"
    },
    "debug": {
      "type": "boolean",
      "required": false,
      "default": false,
      "description": "Enable debug mode",
      "description_zh": "启用调试模式"
    }
  },
  "tools": [
    {
      "name": "tool_name",
      "description": "Tool description",
      "description_zh": "工具描述",
      "input_schema": {
        "type": "object",
        "properties": {
          "param1": {
            "type": "string",
            "description": "Parameter description"
          }
        },
        "required": ["param1"]
      }
    }
  ],
  "resources": [
    {
      "uri": "resource://example/data",
      "name": "Example Resource",
      "description": "Resource description",
      "mime_type": "application/json"
    }
  ],
  "security": {
    "sandbox": true,
    "max_memory_mb": 512,
    "max_cpu_percent": 50,
    "timeout_seconds": 300,
    "allowed_protocols": ["https", "http"],
    "blocked_paths": ["/etc", "/root", "/sys"]
  },
  "quality_metrics": {
    "code_quality_score": 8.5,
    "test_coverage": 85,
    "documentation_completeness": 90
  }
}
```

## 字段详解

### 顶级字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `schema_version` | string | 是 | Manifest规范版本，当前为 "1.0" |
| `name` | string | 是 | 插件唯一标识符（小写字母、数字、连字符） |
| `version` | string | 是 | 语义版本号（如 1.0.0） |
| `type` | string | 是 | 插件类型，必须为 "mcp-plugin" |
| `xagent_compatibility` | object | 是 | X-Agent兼容性版本范围 |
| `metadata` | object | 是 | 插件元数据 |
| `chinese` | object | 是 | 中文化内容 |
| `capabilities` | object | 是 | 插件能力声明 |
| `permissions` | object | 是 | 权限声明 |
| `entry_point` | object | 是 | 插件入口点 |
| `dependencies` | object | 是 | 依赖声明 |
| `configuration` | object | 否 | 配置参数定义 |
| `tools` | array | 否 | 工具定义 |
| `resources` | array | 否 | 资源定义 |
| `security` | object | 否 | 安全配置 |
| `quality_metrics` | object | 否 | 质量指标 |

### xagent_compatibility

定义插件与X-Agent版本的兼容性范围。

```json
{
  "min_version": "0.1.0",
  "max_version": "1.0.0"
}
```

### metadata

插件的基本信息。

```json
{
  "display_name": "GitHub助手",
  "description": "GitHub API integration for X-Agent",
  "description_zh": "GitHub API集成插件",
  "author": "X-Agent Team",
  "author_email": "team@x-agent.com",
  "license": "MIT",
  "homepage": "https://github.com/x-agent/github-plugin",
  "repository": "https://github.com/x-agent/github-plugin",
  "icon_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
  "category": "development"
}
```

**category 可选值**：
- `development` - 开发工具
- `data` - 数据分析
- `automation` - 自动化
- `office` - 办公助手
- `design` - 设计工具
- `network` - 网络工具
- `system` - 系统工具
- `learning` - 学习助手

### chinese

中文化内容，确保小白用户友好。

```json
{
  "name": "GitHub助手",
  "description": "这个插件让你可以在X-Agent中直接管理GitHub代码仓库、问题和拉取请求，无需离开X-Agent。",
  "usage": "1. 安装插件\n2. 配置GitHub Token\n3. 在对话中使用GitHub命令\n4. 查看结果",
  "适合谁用": ["开发者", "项目经理", "DevOps工程师"],
  "常见问题": [
    {
      "question": "如何获取GitHub Token？",
      "answer": "访问 https://github.com/settings/tokens 创建新的Personal Access Token..."
    }
  ],
  "tutorial": "https://example.com/github-plugin-tutorial"
}
```

### capabilities

声明插件支持的MCP能力。

```json
{
  "tools": true,
  "resources": true,
  "prompts": false
}
```

- `tools` - 是否提供工具（函数调用）
- `resources` - 是否提供资源（文件、数据访问）
- `prompts` - 是否提供提示词模板

### permissions

声明插件需要的权限。

```json
{
  "network": {
    "required": true,
    "domains": ["api.github.com", "*.github.com"]
  },
  "filesystem": {
    "required": false,
    "paths": ["/tmp/plugin-cache"]
  },
  "environment": {
    "required": false,
    "variables": ["GITHUB_TOKEN", "DEBUG"]
  }
}
```

### entry_point

定义插件的入口点。

```json
{
  "type": "python",
  "module": "main",
  "class": "PluginServer"
}
```

**type 可选值**：
- `python` - Python插件
- `node` - Node.js插件
- `docker` - Docker容器插件

### dependencies

声明插件的依赖。

```json
{
  "python": ">=3.11",
  "packages": {
    "requests": ">=2.31.0",
    "pydantic": ">=2.0.0",
    "pygithub": "^1.55"
  }
}
```

### configuration

定义插件的配置参数。

```json
{
  "api_key": {
    "type": "string",
    "required": true,
    "description": "API Key",
    "description_zh": "API密钥",
    "secret": true
  },
  "timeout": {
    "type": "integer",
    "required": false,
    "default": 30,
    "min": 1,
    "max": 300,
    "description": "Request timeout in seconds"
  },
  "debug": {
    "type": "boolean",
    "required": false,
    "default": false,
    "description": "Enable debug mode"
  }
}
```

**type 可选值**：
- `string` - 字符串
- `integer` - 整数
- `number` - 浮点数
- `boolean` - 布尔值
- `array` - 数组
- `object` - 对象

### tools

定义插件提供的工具。

```json
[
  {
    "name": "list_repositories",
    "description": "List user repositories",
    "description_zh": "列出用户的代码仓库",
    "input_schema": {
      "type": "object",
      "properties": {
        "username": {
          "type": "string",
          "description": "GitHub username"
        },
        "limit": {
          "type": "integer",
          "default": 10,
          "description": "Number of repositories to return"
        }
      },
      "required": ["username"]
    }
  }
]
```

### resources

定义插件提供的资源。

```json
[
  {
    "uri": "github://repos/user/repo",
    "name": "Repository",
    "description": "GitHub repository resource",
    "mime_type": "application/json"
  }
]
```

### security

定义安全配置。

```json
{
  "sandbox": true,
  "max_memory_mb": 512,
  "max_cpu_percent": 50,
  "timeout_seconds": 300,
  "allowed_protocols": ["https"],
  "blocked_paths": ["/etc", "/root", "/sys"]
}
```

### quality_metrics

质量指标（由审核系统填充）。

```json
{
  "code_quality_score": 8.5,
  "test_coverage": 85,
  "documentation_completeness": 90
}
```

## 验证规则

### 必需字段验证

- `schema_version` 必须为 "1.0"
- `name` 必须匹配正则表达式 `^[a-z0-9-]+$`
- `version` 必须遵循语义版本号规范
- `type` 必须为 "mcp-plugin"
- `metadata.author` 不能为空
- `metadata.license` 必须是有效的SPDX许可证标识符

### 兼容性验证

- `xagent_compatibility.min_version` 必须 <= `xagent_compatibility.max_version`
- 版本号必须遵循语义版本号规范

### 权限验证

- 网络权限中的域名必须是有效的域名格式
- 文件系统路径必须是绝对路径
- 环境变量名必须是有效的标识符

### 配置验证

- 配置参数名必须是有效的标识符
- 配置参数类型必须是支持的类型
- 如果设置了 `default`，其类型必须与 `type` 匹配

## 示例

### 最小化Manifest

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
    "author": "Example Author",
    "license": "MIT"
  },
  "chinese": {
    "name": "你好世界",
    "description": "一个简单的示例插件"
  },
  "capabilities": {
    "tools": true,
    "resources": false,
    "prompts": false
  },
  "permissions": {
    "network": {
      "required": false
    },
    "filesystem": {
      "required": false
    },
    "environment": {
      "required": false
    }
  },
  "entry_point": {
    "type": "python",
    "module": "main",
    "class": "HelloWorldPlugin"
  },
  "dependencies": {
    "python": ">=3.11"
  }
}
```

### 完整Manifest示例

参见本文档顶部的"完整Schema"部分。

## 版本历史

### v1.0 (2026-05-27)

- 初始版本
- 支持Python、Node.js、Docker插件
- 完整的权限和安全模型
- 中文化支持
- 质量指标集成

## 最佳实践

1. **命名规范**
   - 使用小写字母、数字和连字符
   - 名称应该简洁且具有描述性
   - 避免使用通用名称

2. **版本管理**
   - 遵循语义版本号规范
   - 在发布新版本前更新版本号
   - 在CHANGELOG中记录变更

3. **文档**
   - 提供清晰的中文描述
   - 包含使用示例
   - 列出常见问题和解决方案

4. **权限**
   - 只请求必要的权限
   - 明确列出需要的域名和路径
   - 避免请求过于宽泛的权限

5. **安全**
   - 不要在Manifest中存储敏感信息
   - 使用 `secret: true` 标记敏感配置
   - 遵循最小权限原则

6. **测试**
   - 提供至少80%的测试覆盖率
   - 包含集成测试
   - 测试错误处理

7. **性能**
   - 优化工具响应时间
   - 实现缓存机制
   - 监控资源使用

## 相关文档

- [MCP插件开发者指南](MCP_PLUGIN_DEVELOPER_GUIDE.md)
- [MCP插件审核标准](MCP_PLUGIN_REVIEW_STANDARDS.md)
- [MCP插件API参考](MCP_PLUGIN_API_REFERENCE.md)
