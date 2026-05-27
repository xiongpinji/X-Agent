# Claude Code能力对齐 - 第三阶段集成指南

## 快速开始

### 1. MCP集成使用

#### 初始化MCP服务器

```python
from backend.app.core.mcp import MCPServer
from backend.app.core.mcp.tools import FileOperationTool, SearchOperationTool

# 创建服务器
mcp_server = MCPServer(host="localhost", port=8001)

# 初始化工具
file_tool = FileOperationTool(base_path="./data")
search_tool = SearchOperationTool()

# 注册工具
mcp_server.register_tool(
    "file_read",
    file_tool.read_file,
    description="Read file content",
    input_schema={"path": "string", "encoding": "string"},
)

mcp_server.register_tool(
    "search_web",
    search_tool.search_web,
    description="Search the web",
    input_schema={"query": "string", "num_results": "integer"},
)
```

#### 使用MCP客户端

```python
from backend.app.core.mcp import MCPClient

async def main():
    async with MCPClient("http://localhost:8001") as client:
        # 列出可用工具
        tools = await client.list_tools()
        print(f"Available tools: {[t['name'] for t in tools]}")
        
        # 调用工具
        result = await client.call_tool("file_read", {"path": "example.txt"})
        print(f"File content: {result}")
```

#### 通过API调用

```bash
# 列出工具
curl http://localhost:8000/api/v1/mcp/tools

# 调用工具
curl -X POST http://localhost:8000/api/v1/mcp/tools/file_read/call \
  -H "Content-Type: application/json" \
  -d '{"path": "example.txt"}'
```

### 2. 工件系统使用

#### 创建工件

```python
from backend.app.core.artifacts import Artifact, ArtifactStorage

# 初始化存储
storage = ArtifactStorage("./data/artifacts")

# 创建HTML工件
artifact = Artifact(
    name="My Dashboard",
    type="html",
    content="<h1>Welcome</h1><p>This is my dashboard</p>",
    tags=["dashboard", "important"],
    description="My personal dashboard"
)

# 保存工件
artifact_id = await storage.save_artifact(artifact)
print(f"Created artifact: {artifact_id}")
```

#### 创建图表工件

```python
artifact = Artifact(
    name="Sales Chart",
    type="chart",
    content="{}",
    metadata={
        "chart_type": "bar",
        "data": {
            "labels": ["Jan", "Feb", "Mar"],
            "datasets": [{
                "label": "Sales",
                "data": [100, 200, 150]
            }]
        }
    }
)

artifact_id = await storage.save_artifact(artifact)
```

#### 创建表格工件

```python
artifact = Artifact(
    name="Users Table",
    type="table",
    content="{}",
    metadata={
        "data": [
            {"name": "Alice", "email": "alice@example.com", "role": "Admin"},
            {"name": "Bob", "email": "bob@example.com", "role": "User"},
        ]
    }
)

artifact_id = await storage.save_artifact(artifact)
```

#### 渲染工件

```python
from backend.app.core.artifacts import ArtifactRenderer

renderer = ArtifactRenderer()

# 加载工件
artifact = await storage.load_artifact(artifact_id)

# 渲染为HTML
html = await renderer.render(artifact)
print(html)
```

#### 通过API管理工件

```bash
# 创建工件
curl -X POST http://localhost:8000/api/v1/artifacts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Artifact",
    "type": "html",
    "content": "<h1>Hello</h1>",
    "tags": ["test"]
  }'

# 列出工件
curl http://localhost:8000/api/v1/artifacts

# 获取工件
curl http://localhost:8000/api/v1/artifacts/{artifact_id}

# 搜索工件
curl "http://localhost:8000/api/v1/artifacts/search?query=dashboard"

# 渲染工件
curl http://localhost:8000/api/v1/artifacts/{artifact_id}/render

# 更新工件
curl -X PUT http://localhost:8000/api/v1/artifacts/{artifact_id} \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name"}'

# 删除工件
curl -X DELETE http://localhost:8000/api/v1/artifacts/{artifact_id}
```

### 3. Web搜索使用

#### 使用搜索缓存

```python
from backend.app.core.search import SearchCache

# 创建缓存
cache = SearchCache(ttl=3600)

# 缓存搜索结果
results = [
    {"title": "Result 1", "url": "http://example.com/1"},
    {"title": "Result 2", "url": "http://example.com/2"},
]
await cache.set("python tutorial", results, "web")

# 获取缓存结果
cached = await cache.get("python tutorial", "web")
print(f"Cached results: {cached}")

# 获取缓存统计
stats = await cache.get_stats()
print(f"Cache stats: {stats}")
```

#### 提取网页内容

```python
from backend.app.core.search import ContentExtractor

extractor = ContentExtractor(timeout=10.0)

# 提取内容
result = await extractor.extract("https://example.com")
print(f"Title: {result['title']}")
print(f"Content: {result['content']}")
print(f"Metadata: {result['metadata']}")
```

#### 通过API搜索

```bash
# 执行搜索
curl "http://localhost:8000/api/v1/search?query=python&num_results=10"

# 提取网页内容
curl "http://localhost:8000/api/v1/search/extract?url=https://example.com"

# 获取缓存统计
curl http://localhost:8000/api/v1/search/cache/stats

# 清空缓存
curl -X POST http://localhost:8000/api/v1/search/cache/clear

# 获取搜索建议
curl "http://localhost:8000/api/v1/search/suggestions?query=pyt"
```

## 高级用法

### 1. 自定义MCP工具

```python
from backend.app.core.mcp import MCPServer

mcp_server = MCPServer()

# 定义自定义工具
async def custom_tool(param1: str, param2: int) -> dict:
    """Custom tool implementation"""
    return {
        "param1": param1,
        "param2": param2,
        "result": f"Processed {param1} with {param2}"
    }

# 注册工具
mcp_server.register_tool(
    "custom_tool",
    custom_tool,
    description="A custom tool",
    input_schema={
        "param1": "string",
        "param2": "integer"
    },
    output_schema={
        "result": "string"
    },
    tags=["custom", "example"]
)
```

### 2. 工件过滤和搜索

```python
# 按类型过滤
html_artifacts = await storage.list_artifacts(artifact_type="html")

# 按标签过滤
important = await storage.list_artifacts(tags=["important"])

# 分页
page1 = await storage.list_artifacts(limit=10, offset=0)
page2 = await storage.list_artifacts(limit=10, offset=10)

# 搜索
results = await storage.search_artifacts("dashboard", limit=50)
```

### 3. 使用Redis缓存

```python
import redis
from backend.app.core.search import RedisSearchCache

# 连接Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# 创建Redis缓存
cache = RedisSearchCache(redis_client, ttl=3600)

# 使用方式与内存缓存相同
await cache.set("query", results, "web")
cached = await cache.get("query", "web")
```

## 配置指南

### 环境变量

```bash
# MCP配置
MCP_HOST=localhost
MCP_PORT=8001

# 工件存储
ARTIFACT_STORAGE_PATH=./data/artifacts

# 搜索缓存
SEARCH_CACHE_TTL=3600
SEARCH_CACHE_TYPE=memory  # memory or redis

# Redis配置（如果使用Redis缓存）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### 应用配置

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MCP配置
    mcp_host: str = "localhost"
    mcp_port: int = 8001
    
    # 工件存储
    artifact_storage_path: str = "./data/artifacts"
    
    # 搜索缓存
    search_cache_ttl: int = 3600
    search_cache_type: str = "memory"
    
    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## 测试指南

### 运行测试

```bash
# 运行所有测试
pytest tests/test_mcp.py tests/test_artifacts.py tests/test_search.py

# 运行特定测试
pytest tests/test_mcp.py::test_mcp_server_initialization

# 运行带覆盖率的测试
pytest --cov=backend tests/
```

### 编写测试

```python
import pytest
from backend.app.core.artifacts import Artifact, ArtifactStorage

@pytest.mark.asyncio
async def test_artifact_creation():
    artifact = Artifact(
        name="Test",
        type="html",
        content="<h1>Test</h1>"
    )
    assert artifact.name == "Test"
    assert artifact.type == "html"
```

## 故障排除

### MCP问题

**问题**: 工具调用失败
**解决方案**:
1. 检查工具是否已注册
2. 验证输入参数格式
3. 查看错误日志

**问题**: 连接超时
**解决方案**:
1. 检查服务器是否运行
2. 验证主机和端口配置
3. 检查防火墙设置

### 工件问题

**问题**: 工件保存失败
**解决方案**:
1. 检查存储路径权限
2. 验证磁盘空间
3. 检查JSON序列化

**问题**: 渲染失败
**解决方案**:
1. 验证工件类型
2. 检查内容格式
3. 查看渲染日志

### 搜索问题

**问题**: 缓存未生效
**解决方案**:
1. 检查TTL设置
2. 验证缓存键生成
3. 检查缓存清空

**问题**: 内容提取失败
**解决方案**:
1. 验证URL有效性
2. 检查网络连接
3. 增加超时时间

## 性能优化

### 1. 缓存优化

```python
# 使用Redis缓存提高性能
cache = RedisSearchCache(redis_client, ttl=7200)

# 定期清理过期缓存
await cache.cleanup_expired()
```

### 2. 工件优化

```python
# 使用分页减少内存占用
artifacts = await storage.list_artifacts(limit=100, offset=0)

# 定期清理旧工件
old_artifacts = await storage.list_artifacts()
for artifact in old_artifacts:
    if artifact.created_at < cutoff_date:
        await storage.delete_artifact(artifact.id)
```

### 3. 搜索优化

```python
# 限制搜索结果数量
results = await search_cache.get_stats()
if results['total_entries'] > 10000:
    await search_cache.clear()
```

## 安全最佳实践

### 1. 访问控制

```python
# 在API中检查权限
enforce_scope(principal, "artifacts:write")
enforce_scope(principal, "search:read")
enforce_scope(principal, "mcp:execute")
```

### 2. 输入验证

```python
# 验证工件内容
if len(artifact.content) > 1000000:
    raise ValueError("Content too large")

# 验证搜索查询
if len(query) > 500:
    raise ValueError("Query too long")
```

### 3. 错误处理

```python
try:
    result = await client.call_tool("tool_name", args)
except Exception as e:
    logger.error(f"Tool call failed: {e}")
    raise api_error(400, ErrorCode.INVALID_REQUEST, str(e))
```

## 监控和日志

### 日志配置

```python
import logging

logger = logging.getLogger(__name__)

# 记录工件操作
logger.info(f"Artifact created: {artifact_id}")
logger.error(f"Artifact save failed: {error}")

# 记录搜索操作
logger.info(f"Search query: {query}")
logger.debug(f"Cache hit: {query}")
```

### 性能监控

```python
import time

start = time.time()
result = await storage.load_artifact(artifact_id)
duration = time.time() - start

logger.info(f"Load artifact took {duration:.2f}s")
```

---

**文档版本**: 1.0  
**最后更新**: 2026-05-26
