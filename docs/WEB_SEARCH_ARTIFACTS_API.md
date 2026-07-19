# Web搜索与工件系统 - API文档与集成指南

## 概述

X-Agent Web搜索与工件系统提供两个核心功能：

1. **Web搜索模块** - 多搜索引擎支持、结果缓存、内容解析
2. **工件系统** - 多格式渲染、版本控制、分享管理

## 架构设计

### Web搜索架构

```
SearchEngine (主协调器)
├── SerperProvider (Serper.dev API)
├── SerpAPIProvider (SerpAPI)
├── FirecrawlProvider (Web爬虫)
├── SearchCache (Redis缓存)
└── SearchResultParser (结果解析)
```

### 工件系统架构

```
ArtifactEngine (主管理器)
├── ArtifactRenderer (多格式渲染)
│   ├── HTML渲染
│   ├── React渲染
│   ├── Markdown渲染
│   ├── SVG渲染
│   ├── Chart.js图表
│   ├── Grid.js表格
│   └── 代码高亮
├── VersionControl (Git风格版本控制)
│   ├── 版本创建
│   ├── Diff计算
│   ├── 回滚功能
│   └── 历史记录
└── SharingManager (分享与访问控制)
    ├── 分享链接生成
    ├── 权限管理
    ├── 过期控制
    └── 访问统计
```

## Web搜索API

### 1. 执行搜索

**端点**: `POST /api/v1/search/query`

**请求**:
```json
{
  "query": "Python async programming",
  "num_results": 10,
  "provider": "serper"
}
```

**响应**:
```json
{
  "query": "Python async programming",
  "results": [
    {
      "title": "Async IO in Python",
      "url": "https://docs.python.org/3/library/asyncio.html",
      "snippet": "The asyncio library provides a framework for writing concurrent code...",
      "domain": "docs.python.org",
      "content_type": "documentation",
      "relevance": "95%",
      "date": "2024-01-15"
    }
  ],
  "total_results": 1250000,
  "search_time_ms": 245,
  "provider": "serper",
  "cached": false
}
```

**性能指标**:
- 响应时间: <3秒 (目标)
- 缓存命中率: 60-80%
- 支持并行搜索: 多提供商同时查询

### 2. 列出可用提供商

**端点**: `GET /api/v1/search/providers`

**响应**:
```json
{
  "providers": [
    {
      "name": "serper",
      "description": "Serper.dev search API",
      "status": "active"
    },
    {
      "name": "serpapi",
      "description": "SerpAPI search engine",
      "status": "active"
    },
    {
      "name": "firecrawl",
      "description": "Firecrawl web scraping",
      "status": "active"
    }
  ]
}
```

### 3. 缓存管理

**获取缓存统计**: `GET /api/v1/search/cache/stats`

**清空缓存**: `DELETE /api/v1/search/cache`

## 工件系统API

### 1. 创建工件

**端点**: `POST /api/v1/artifacts`

**请求**:
```json
{
  "type": "chart",
  "content": "{\"type\": \"bar\", \"data\": {...}}",
  "title": "Q1销售数据",
  "description": "2026年第一季度销售统计",
  "tags": ["sales", "q1", "2026"],
  "is_public": false,
  "dependencies": []
}
```

**支持的工件类型**:
- `html` - 原始HTML
- `react` - React组件
- `markdown` - Markdown文档
- `svg` - SVG图形
- `chart` - Chart.js图表
- `table` - Grid.js数据表
- `code` - 代码片段
- `document` - 文档
- `dashboard` - 仪表板
- `visualization` - 数据可视化

**响应**:
```json
{
  "id": "artifact_abc123",
  "type": "chart",
  "status": "draft",
  "title": "Q1销售数据",
  "description": "2026年第一季度销售统计",
  "content": "{...}",
  "tags": ["sales", "q1", "2026"],
  "is_public": false,
  "version": 1,
  "created_at": "2026-05-28T10:30:00Z",
  "updated_at": "2026-05-28T10:30:00Z"
}
```

### 2. 获取工件

**端点**: `GET /api/v1/artifacts/{artifact_id}`

### 3. 更新工件

**端点**: `PUT /api/v1/artifacts/{artifact_id}`

**请求**:
```json
{
  "content": "{\"type\": \"bar\", \"data\": {...}}",
  "title": "Q1销售数据 (更新)",
  "description": "更新的描述",
  "tags": ["sales", "q1", "2026", "updated"],
  "commit_message": "更新图表数据"
}
```

### 4. 渲染工件

**端点**: `GET /api/v1/artifacts/{artifact_id}/render`

返回可在浏览器中直接显示的HTML。

### 5. 版本管理

**列出版本**: `GET /api/v1/artifacts/{artifact_id}/versions`

**获取特定版本**: `GET /api/v1/artifacts/{artifact_id}/versions/{version_id}`

**回滚版本**: `POST /api/v1/artifacts/{artifact_id}/versions/{version_id}/revert`

**版本响应**:
```json
{
  "version_id": "v_xyz789",
  "author": "user_123",
  "message": "更新图表数据",
  "created_at": "2026-05-28T10:35:00Z",
  "content_hash": "a1b2c3d4",
  "size_bytes": 2048
}
```

### 6. 发布工件

**端点**: `POST /api/v1/artifacts/{artifact_id}/publish`

将工件状态从`draft`改为`published`。

### 7. 分享工件

**创建分享链接**: `POST /api/v1/artifacts/{artifact_id}/share`

**查询参数**:
- `is_public` (bool) - 公开分享
- `allow_download` (bool) - 允许下载
- `allow_edit` (bool) - 允许编辑
- `expires_in_days` (int) - 过期天数

**响应**:
```json
{
  "share_id": "share_abc123",
  "share_url": "https://xagent.ai/artifacts/share/share_abc123",
  "share_token": "token_xyz789",
  "created_at": "2026-05-28T10:40:00Z",
  "expires_at": "2026-06-28T10:40:00Z",
  "is_public": true,
  "allow_download": true,
  "allow_edit": false
}
```

**列出分享**: `GET /api/v1/artifacts/{artifact_id}/shares`

**撤销分享**: `DELETE /api/v1/artifacts/{artifact_id}/shares/{share_id}`

### 8. 搜索工件

**端点**: `GET /api/v1/artifacts/search`

**查询参数**:
- `query` (string) - 搜索查询
- `artifact_type` (string) - 工件类型过滤
- `tags` (list) - 标签过滤
- `limit` (int) - 结果限制

## 集成步骤

### 1. 安装依赖

```bash
# 添加到requirements.txt
httpx==0.27.0
redis==5.0.0
```

### 2. 配置搜索引擎

```python
from backend.app.services.search import SearchEngine, SearchProvider

# 初始化搜索引擎
search_engine = SearchEngine(
    providers={
        SearchProvider.SERPER: "your_serper_api_key",
        SearchProvider.SERPAPI: "your_serpapi_api_key",
        SearchProvider.FIRECRAWL: "your_firecrawl_api_key",
    }
)
```

### 3. 配置工件系统

```python
from backend.app.services.artifacts import (
    ArtifactEngine,
    VersionControl,
    ArtifactRenderer,
    SharingManager,
)

# 初始化工件系统
artifact_engine = ArtifactEngine(
    storage_backend=db_storage,
    version_control=VersionControl(db_storage),
)

renderer = ArtifactRenderer()
sharing_manager = SharingManager(db_storage)
```

### 4. 在main.py中注册API

```python
from backend.app.api.search_api import router as search_router
from backend.app.api.artifacts_api import router as artifacts_router

app.include_router(search_router)
app.include_router(artifacts_router)
```

### 5. 添加依赖注入

```python
# 在dependencies.py中
from backend.app.services.search import SearchEngine

def get_search_engine() -> SearchEngine:
    return search_engine

def get_artifact_engine() -> ArtifactEngine:
    return artifact_engine
```

## 使用示例

### 示例1: 执行Web搜索

```python
import asyncio
from backend.app.services.search import SearchEngine, SearchProvider

async def search_example():
    engine = SearchEngine({
        SearchProvider.SERPER: "api_key",
    })
    
    response = await engine.search(
        query="machine learning best practices",
        num_results=10,
    )
    
    print(f"Found {len(response.results)} results")
    for result in response.results:
        print(f"- {result.title}: {result.url}")
    
    await engine.close()

asyncio.run(search_example())
```

### 示例2: 创建和渲染工件

```python
from backend.app.services.artifacts import (
    ArtifactEngine,
    ArtifactType,
    ArtifactRenderer,
)

async def artifact_example():
    # 创建工件
    artifact = await artifact_engine.create(
        artifact_type=ArtifactType.CHART,
        content='{"type": "bar", "data": {...}}',
        title="销售数据",
        author="user_123",
    )
    
    # 渲染工件
    renderer = ArtifactRenderer()
    html = renderer.render(artifact)
    
    # 创建分享链接
    share = await sharing_manager.create_share(
        artifact_id=artifact.id,
        owner="user_123",
        is_public=True,
        expires_in_days=30,
    )
    
    print(f"Share URL: {share.share_url}")

asyncio.run(artifact_example())
```

### 示例3: 版本控制

```python
async def version_example():
    # 获取版本历史
    versions, total = await version_control.list_versions(
        artifact_id="artifact_123",
        limit=10,
    )
    
    # 计算两个版本之间的差异
    diff = await version_control.get_diff(
        version_id_1="v_old",
        version_id_2="v_new",
    )
    
    print(f"Added: {diff['added_lines']} lines")
    print(f"Removed: {diff['removed_lines']} lines")
    
    # 回滚到之前的版本
    reverted = await version_control.revert(
        artifact_id="artifact_123",
        target_version_id="v_old",
        author="user_123",
    )

asyncio.run(version_example())
```

## 性能优化

### 搜索缓存策略

- **TTL**: 1小时（可配置）
- **缓存键**: MD5(query.lower()) + provider
- **缓存大小**: 无限制（由Redis管理）
- **命中率**: 预期60-80%

### 工件渲染优化

- **沙箱隔离**: iframe + CSP策略
- **依赖加载**: CDN加速（jsDelivr）
- **渲染时间**: <500ms
- **支持的库**: Chart.js, D3.js, Plotly, Mermaid, Grid.js

### 版本控制优化

- **存储**: 仅存储差异（Delta compression）
- **查询**: 索引支持快速查询
- **历史**: 无限版本历史

## 安全考虑

### Web搜索安全

- API密钥加密存储
- 请求速率限制
- 结果内容验证
- XSS防护

### 工件系统安全

- **沙箱执行**: iframe隔离
- **CSP策略**: 限制脚本执行
- **访问控制**: 基于角色的权限
- **分享链接**: 令牌验证
- **内容验证**: HTML/JS清理

## 故障排除

### 搜索超时

```python
# 增加超时时间
search_engine = SearchEngine(
    providers={...},
    timeout=15,  # 15秒
)
```

### 缓存问题

```python
# 清空缓存
await search_cache.clear()

# 查看缓存统计
stats = await search_cache.get_stats()
print(f"Cache entries: {stats['entries']}")
```

### 工件渲染问题

```python
# 检查依赖
dependencies = renderer.get_dependencies(artifact)
print(f"Required: {dependencies}")

# 验证内容
if artifact.type == ArtifactType.CHART:
    import json
    json.loads(artifact.content)  # 验证JSON
```

## 下一步

1. **数据库集成**: 实现PostgreSQL存储后端
2. **Redis集成**: 连接Redis缓存
3. **认证集成**: 与X-Agent认证系统集成
4. **监控**: 添加Prometheus指标
5. **测试**: 编写单元和集成测试
6. **文档**: 生成OpenAPI规范

## 相关文件

- 搜索模块: `/backend/app/services/search/`
- 工件模块: `/backend/app/services/artifacts/`
- API端点: `/backend/app/api/search_api.py`, `/backend/app/api/artifacts_api.py`
