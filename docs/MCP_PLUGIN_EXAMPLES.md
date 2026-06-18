# MCP插件示例集合 v1.0

## 概述

本文档提供了三个完整的MCP插件示例，展示如何开发符合X-Agent标准的MCP插件。

## 示例1：GitHub MCP插件

### 功能概述

GitHub MCP插件提供了与GitHub API的集成，允许用户在X-Agent中直接管理GitHub仓库、问题和拉取请求。

**主要功能**：
- 列出用户的代码仓库
- 获取仓库详细信息
- 创建和管理问题（Issues）
- 列出仓库的问题
- 创建和管理拉取请求（Pull Requests）

### 项目结构

```
plugins/github-mcp/
├── manifest.json          # 插件清单
├── main.py               # 插件实现
├── requirements.txt      # Python依赖
├── README.md            # 英文文档
├── README_zh.md         # 中文文档
└── tests/
    ├── test_github.py
    └── test_integration.py
```

### 使用示例

#### 示例1：列出用户的仓库

```python
# 在X-Agent中使用
result = await plugin.list_repositories("torvalds", limit=5)
# 返回Linux内核仓库的最新5个仓库
```

**返回结果**：
```json
{
  "status": "success",
  "data": [
    {
      "name": "linux",
      "url": "https://github.com/torvalds/linux",
      "description": "Linux kernel source tree",
      "stars": 180000,
      "language": "C",
      "updated_at": "2026-05-27T10:30:00Z"
    }
  ],
  "count": 1
}
```

#### 示例2：创建一个Issue

```python
result = await plugin.create_issue(
    owner="x-agent",
    repo="x-agent",
    title="Add MCP plugin support",
    body="This issue tracks the implementation of MCP plugin support"
)
```

**返回结果**：
```json
{
  "status": "success",
  "data": {
    "number": 123,
    "title": "Add MCP plugin support",
    "url": "https://github.com/x-agent/x-agent/issues/123",
    "state": "open",
    "created_at": "2026-05-27T10:30:00Z"
  }
}
```

#### 示例3：创建一个Pull Request

```python
result = await plugin.create_pull_request(
    owner="x-agent",
    repo="x-agent",
    title="Implement MCP plugin adapter",
    head="feature/mcp-plugin",
    base="develop",
    body="This PR implements the MCP plugin adapter"
)
```

### 配置

```json
{
  "github_token": "gh_example_token_redacted",
  "timeout": 30
}
```

**配置说明**：
- `github_token`：GitHub Personal Access Token（必需）
- `timeout`：请求超时时间，单位秒（可选，默认30）

### 测试

```bash
# 运行单元测试
pytest tests/test_github.py

# 运行集成测试
pytest tests/test_integration.py

# 生成覆盖率报告
pytest --cov=main tests/
```

## 示例2：数据库MCP插件

### 功能概述

数据库MCP插件提供了与PostgreSQL和MySQL数据库的集成，允许用户在X-Agent中直接查询和管理数据库。

**主要功能**：
- 执行SQL查询
- 列出数据库中的所有表
- 获取表的架构信息
- 导出查询结果（CSV、JSON、Excel）
- 分析表的统计信息

### 项目结构

```
plugins/database-mcp/
├── manifest.json          # 插件清单
├── main.py               # 插件实现
├── requirements.txt      # Python依赖
├── README.md            # 英文文档
├── README_zh.md         # 中文文档
└── tests/
    ├── test_database.py
    └── test_integration.py
```

### 使用示例

#### 示例1：执行SQL查询

```python
result = await plugin.execute_query(
    query="SELECT * FROM users WHERE age > 18",
    limit=100
)
```

**返回结果**：
```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "Alice",
      "age": 25,
      "email": "alice@example.com"
    },
    {
      "id": 2,
      "name": "Bob",
      "age": 30,
      "email": "bob@example.com"
    }
  ],
  "count": 2,
  "columns": ["id", "name", "age", "email"]
}
```

#### 示例2：列出所有表

```python
result = await plugin.list_tables()
```

**返回结果**：
```json
{
  "status": "success",
  "data": ["users", "products", "orders", "categories"],
  "count": 4
}
```

#### 示例3：获取表的架构

```python
result = await plugin.get_table_schema("users")
```

**返回结果**：
```json
{
  "status": "success",
  "data": [
    {
      "name": "id",
      "type": "integer",
      "nullable": false
    },
    {
      "name": "name",
      "type": "character varying",
      "nullable": false
    },
    {
      "name": "age",
      "type": "integer",
      "nullable": true
    }
  ],
  "count": 3
}
```

#### 示例4：导出查询结果

```python
result = await plugin.export_query_result(
    query="SELECT * FROM users",
    format="csv",
    filename="users_export"
)
```

**返回结果**：
```json
{
  "status": "success",
  "message": "Exported to users_export.csv",
  "file_path": "users_export.csv",
  "rows": 100
}
```

#### 示例5：分析表的统计信息

```python
result = await plugin.analyze_table("users")
```

**返回结果**：
```json
{
  "status": "success",
  "data": {
    "table_name": "users",
    "row_count": 10000,
    "column_count": 5,
    "table_size": "2.5 MB"
  }
}
```

### 配置

```json
{
  "db_type": "postgresql",
  "db_host": "localhost",
  "db_port": 5432,
  "db_user": "postgres",
  "db_password": "password",
  "db_name": "mydb",
  "timeout": 30
}
```

**配置说明**：
- `db_type`：数据库类型（postgresql或mysql）
- `db_host`：数据库主机
- `db_port`：数据库端口
- `db_user`：数据库用户
- `db_password`：数据库密码
- `timeout`：查询超时时间，单位秒

### 测试

```bash
# 运行单元测试
pytest tests/test_database.py

# 运行集成测试
pytest tests/test_integration.py

# 生成覆盖率报告
pytest --cov=main tests/
```

## 示例3：文件系统MCP插件

### 功能概述

文件系统MCP插件提供了文件系统操作的集成，允许用户在X-Agent中直接读写和管理文件。

**主要功能**：
- 读取文件内容
- 写入内容到文件
- 列出目录中的文件
- 按模式搜索文件
- 删除文件
- 获取文件信息

### 项目结构

```
plugins/filesystem-mcp/
├── manifest.json          # 插件清单
├── main.py               # 插件实现
├── requirements.txt      # Python依赖
├── README.md            # 英文文档
├── README_zh.md         # 中文文档
└── tests/
    ├── test_filesystem.py
    └── test_integration.py
```

### 使用示例

#### 示例1：读取文件

```python
result = await plugin.read_file("/home/user/documents/readme.txt")
```

**返回结果**：
```json
{
  "status": "success",
  "data": {
    "path": "/home/user/documents/readme.txt",
    "content": "This is a readme file...",
    "size": 256,
    "encoding": "utf-8"
  }
}
```

#### 示例2：写入文件

```python
result = await plugin.write_file(
    path="/home/user/documents/new_file.txt",
    content="Hello, World!"
)
```

**返回结果**：
```json
{
  "status": "success",
  "data": {
    "path": "/home/user/documents/new_file.txt",
    "size": 13,
    "mode": "write"
  }
}
```

#### 示例3：列出目录中的文件

```python
result = await plugin.list_files("/home/user/documents", recursive=False)
```

**返回结果**：
```json
{
  "status": "success",
  "data": [
    {
      "name": "readme.txt",
      "path": "/home/user/documents/readme.txt",
      "type": "file",
      "size": 256,
      "modified": "2026-05-27T10:30:00Z"
    },
    {
      "name": "subfolder",
      "path": "/home/user/documents/subfolder",
      "type": "directory",
      "size": 4096,
      "modified": "2026-05-27T10:30:00Z"
    }
  ],
  "count": 2
}
```

#### 示例4：搜索文件

```python
result = await plugin.search_files(
    path="/home/user/documents",
    pattern="*.txt",
    recursive=True
)
```

**返回结果**：
```json
{
  "status": "success",
  "data": [
    {
      "name": "readme.txt",
      "path": "/home/user/documents/readme.txt",
      "type": "file",
      "size": 256,
      "modified": "2026-05-27T10:30:00Z"
    },
    {
      "name": "notes.txt",
      "path": "/home/user/documents/subfolder/notes.txt",
      "type": "file",
      "size": 512,
      "modified": "2026-05-27T10:30:00Z"
    }
  ],
  "count": 2
}
```

#### 示例5：获取文件信息

```python
result = await plugin.get_file_info("/home/user/documents/readme.txt")
```

**返回结果**：
```json
{
  "status": "success",
  "data": {
    "path": "/home/user/documents/readme.txt",
    "name": "readme.txt",
    "type": "file",
    "size": 256,
    "size_mb": 0.000244,
    "created": "2026-05-20T10:30:00Z",
    "modified": "2026-05-27T10:30:00Z",
    "accessed": "2026-05-27T10:30:00Z",
    "permissions": "644"
  }
}
```

### 配置

```json
{
  "allowed_paths": ["/home/user/documents", "/tmp"],
  "max_file_size_mb": 100,
  "enable_write": true
}
```

**配置说明**：
- `allowed_paths`：允许访问的目录路径列表（必需）
- `max_file_size_mb`：最大文件大小，单位MB（可选，默认100）
- `enable_write`：是否启用写入操作（可选，默认true）

### 测试

```bash
# 运行单元测试
pytest tests/test_filesystem.py

# 运行集成测试
pytest tests/test_integration.py

# 生成覆盖率报告
pytest --cov=main tests/
```

## 最佳实践

### 1. 错误处理

所有示例都遵循统一的错误处理模式：

```python
{
  "status": "error",
  "message": "Error description"
}
```

### 2. 配置管理

所有示例都支持通过配置字典进行配置：

```python
config = {
    "key1": "value1",
    "key2": "value2"
}
plugin = PluginClass(config)
```

### 3. 异步操作

所有示例都使用async/await进行异步操作：

```python
async def tool_method(self, param: str) -> dict:
    # 异步操作
    result = await self.async_operation(param)
    return result
```

### 4. 日志记录

所有示例都使用标准的Python logging模块：

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Info message")
logger.error("Error message")
```

### 5. 类型提示

所有示例都使用类型提示：

```python
async def method(self, param: str, limit: int = 10) -> dict[str, Any]:
    pass
```

## 发布到插件市场

### 发布前检查清单

- [ ] Manifest.json有效且完整
- [ ] README.md和README_zh.md完整
- [ ] 代码质量 >= 8.0/10
- [ ] 测试覆盖率 >= 80%
- [ ] 无CRITICAL和HIGH安全漏洞
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

2. **打包插件**
   ```bash
   zip -r plugin-name.zip .
   ```

3. **上传到市场**
   - 访问 https://marketplace.x-agent.com/submit
   - 上传插件包
   - 填写插件信息

4. **等待审核**
   - 自动化检查：1-2小时
   - 人工审核：2-3天
   - 安全审核：1-2天
   - 兼容性测试：1-2天

5. **发布**
   - 审核通过后自动发布
   - 在插件市场中显示

## 相关资源

- [MCP插件Manifest规范](MCP_PLUGIN_MANIFEST_SPEC.md)
- [MCP插件开发者指南](MCP_PLUGIN_DEVELOPER_GUIDE.md)
- [MCP插件审核标准](MCP_PLUGIN_REVIEW_STANDARDS.md)
- [MCP插件API参考](MCP_PLUGIN_API_REFERENCE.md)
