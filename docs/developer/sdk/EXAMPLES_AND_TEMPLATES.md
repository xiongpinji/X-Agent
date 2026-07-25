# Web搜索与工件系统 - 使用示例和模板库

## 快速开始

### 示例1: 执行Web搜索

```python
import asyncio
from backend.app.services.search import SearchEngine, SearchProvider

async def main():
    # 初始化搜索引擎
    engine = SearchEngine({
        SearchProvider.SERPER: "your_serper_api_key",
    })
    
    try:
        # 执行搜索
        response = await engine.search(
            query="Python async programming best practices",
            num_results=10,
        )
        
        # 处理结果
        print(f"Query: {response.query}")
        print(f"Found {len(response.results)} results in {response.search_time_ms:.0f}ms")
        print(f"Cached: {response.cached}")
        
        for result in response.results:
            print(f"\n- {result.title}")
            print(f"  URL: {result.url}")
            print(f"  Snippet: {result.snippet[:100]}...")
            print(f"  Type: {result.content_type}")
            print(f"  Relevance: {result.relevance_score:.1%}")
    
    finally:
        await engine.close()

asyncio.run(main())
```

### 示例2: 多提供商并行搜索

```python
async def multi_provider_search():
    engine = SearchEngine({
        SearchProvider.SERPER: "serper_key",
        SearchProvider.SERPAPI: "serpapi_key",
    })
    
    try:
        # 并行搜索多个提供商
        responses = await engine.search_multi(
            query="machine learning frameworks",
            num_results=5,
            providers=[SearchProvider.SERPER, SearchProvider.SERPAPI],
        )
        
        for response in responses:
            print(f"\n{response.provider.upper()}:")
            print(f"  Results: {len(response.results)}")
            print(f"  Time: {response.search_time_ms:.0f}ms")
    
    finally:
        await engine.close()

asyncio.run(multi_provider_search())
```

### 示例3: 搜索结果解析

```python
from backend.app.services.search import SearchResultParser

async def parse_results():
    engine = SearchEngine({SearchProvider.SERPER: "key"})
    
    response = await engine.search("data science tools")
    
    # 解析结果
    parsed = SearchResultParser.parse_response(response)
    
    # 按相关性排序
    for item in parsed:
        print(f"Title: {item.title}")
        print(f"Domain: {item.domain}")
        print(f"Type: {item.content_type}")
        print(f"Relevance: {item.relevance_score:.1%}")
        print(f"Entities: {', '.join(item.key_entities)}")
        print()
    
    await engine.close()

asyncio.run(parse_results())
```

## 工件系统示例

### 示例4: 创建HTML工件

```python
from backend.app.services.artifacts import ArtifactEngine, ArtifactType

async def create_html_artifact():
    # 初始化引擎
    artifact_engine = ArtifactEngine(storage, version_control)
    
    html_content = """
    <div style="padding: 20px; font-family: Arial;">
        <h1>Welcome to X-Agent</h1>
        <p>This is an interactive HTML artifact.</p>
        <button onclick="alert('Hello!')">Click me</button>
    </div>
    """
    
    artifact = await artifact_engine.create(
        artifact_type=ArtifactType.HTML,
        content=html_content,
        title="Interactive Demo",
        author="user_123",
        description="A simple interactive HTML demo",
        tags=["demo", "interactive"],
    )
    
    print(f"Created artifact: {artifact.id}")
    return artifact

asyncio.run(create_html_artifact())
```

### 示例5: 创建Chart.js图表

```python
import json

async def create_chart_artifact():
    artifact_engine = ArtifactEngine(storage, version_control)
    
    chart_config = {
        "type": "bar",
        "data": {
            "labels": ["Q1", "Q2", "Q3", "Q4"],
            "datasets": [
                {
                    "label": "Sales",
                    "data": [12, 19, 3, 5],
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "borderColor": "rgba(75, 192, 192, 1)",
                    "borderWidth": 1,
                }
            ]
        },
        "options": {
            "responsive": True,
            "scales": {
                "y": {
                    "beginAtZero": True
                }
            }
        }
    }
    
    artifact = await artifact_engine.create(
        artifact_type=ArtifactType.CHART,
        content=json.dumps(chart_config),
        title="Q1-Q4 Sales Chart",
        author="user_123",
        tags=["sales", "chart"],
    )
    
    print(f"Created chart: {artifact.id}")
    return artifact

asyncio.run(create_chart_artifact())
```

### 示例6: 创建React组件

```python
async def create_react_artifact():
    artifact_engine = ArtifactEngine(storage, version_control)
    
    react_code = """
    function App() {
        const [count, setCount] = React.useState(0);
        
        return (
            <div style={{ padding: '20px', textAlign: 'center' }}>
                <h1>Counter: {count}</h1>
                <button onClick={() => setCount(count + 1)}>
                    Increment
                </button>
                <button onClick={() => setCount(count - 1)}>
                    Decrement
                </button>
            </div>
        );
    }
    
    ReactDOM.render(<App />, document.getElementById('root'));
    """
    
    artifact = await artifact_engine.create(
        artifact_type=ArtifactType.REACT,
        content=react_code,
        title="Counter App",
        author="user_123",
        tags=["react", "interactive"],
    )
    
    print(f"Created React app: {artifact.id}")
    return artifact

asyncio.run(create_react_artifact())
```

### 示例7: 创建Markdown文档

```python
async def create_markdown_artifact():
    artifact_engine = ArtifactEngine(storage, version_control)
    
    markdown_content = """
# Python Async Programming Guide

## Introduction
Async programming in Python allows you to write concurrent code.

## Key Concepts

### Coroutines
A coroutine is a function defined with `async def`.

### Event Loop
The event loop manages the execution of coroutines.

### Await
The `await` keyword pauses execution until a coroutine completes.

## Example

```python
async def fetch_data():
    await asyncio.sleep(1)
    return "Data"
```

## Best Practices

1. Use `asyncio.gather()` for parallel execution
2. Handle exceptions with try/except
3. Use context managers for resource management
"""
    
    artifact = await artifact_engine.create(
        artifact_type=ArtifactType.MARKDOWN,
        content=markdown_content,
        title="Async Programming Guide",
        author="user_123",
        tags=["python", "async", "guide"],
    )
    
    print(f"Created guide: {artifact.id}")
    return artifact

asyncio.run(create_markdown_artifact())
```

### 示例8: 创建数据表格

```python
import json

async def create_table_artifact():
    artifact_engine = ArtifactEngine(storage, version_control)
    
    table_data = {
        "columns": ["Name", "Email", "Department", "Salary"],
        "data": [
            ["Alice Johnson", "alice@example.com", "Engineering", 120000],
            ["Bob Smith", "bob@example.com", "Sales", 90000],
            ["Carol White", "carol@example.com", "Marketing", 85000],
            ["David Brown", "david@example.com", "Engineering", 115000],
        ]
    }
    
    artifact = await artifact_engine.create(
        artifact_type=ArtifactType.TABLE,
        content=json.dumps(table_data),
        title="Employee Directory",
        author="user_123",
        tags=["employees", "data"],
    )
    
    print(f"Created table: {artifact.id}")
    return artifact

asyncio.run(create_table_artifact())
```

### 示例9: 版本控制

```python
async def version_control_example():
    artifact_engine = ArtifactEngine(storage, version_control)
    version_control = artifact_engine.version_control
    
    # 创建工件
    artifact = await artifact_engine.create(
        artifact_type=ArtifactType.HTML,
        content="<h1>Version 1</h1>",
        title="Versioned Artifact",
        author="user_123",
    )
    
    # 更新工件
    updated = await artifact_engine.update(
        artifact_id=artifact.id,
        content="<h1>Version 2</h1><p>Updated content</p>",
        author="user_123",
        commit_message="Add paragraph",
    )
    
    # 列出版本
    versions, total = await version_control.list_versions(artifact.id)
    print(f"Total versions: {total}")
    for v in versions:
        print(f"  - {v.version_id}: {v.message}")
    
    # 获取版本历史
    history = await version_control.get_history(artifact.id)
    for entry in history:
        print(f"Version {entry['version_id']}: {entry['message']}")
    
    # 计算差异
    if len(versions) >= 2:
        diff = await version_control.get_diff(
            versions[0].version_id,
            versions[1].version_id,
        )
        print(f"Diff: +{diff['added_lines']} -{diff['removed_lines']}")

asyncio.run(version_control_example())
```

### 示例10: 分享工件

```python
async def sharing_example():
    artifact_engine = ArtifactEngine(storage, version_control)
    sharing_manager = SharingManager(storage)
    
    # 创建工件
    artifact = await artifact_engine.create(
        artifact_type=ArtifactType.CHART,
        content="...",
        title="Sales Report",
        author="user_123",
        is_public=False,
    )
    
    # 创建分享链接
    share = await sharing_manager.create_share(
        artifact_id=artifact.id,
        owner="user_123",
        is_public=True,
        allow_download=True,
        expires_in_days=30,
    )
    
    print(f"Share URL: {share.share_url}")
    print(f"Token: {share.share_token}")
    
    # 列出分享
    shares = await sharing_manager.list_shares(artifact.id)
    print(f"Total shares: {len(shares)}")
    
    # 获取分享统计
    stats = await sharing_manager.get_share_stats(artifact.id)
    print(f"Stats: {stats}")
    
    # 记录访问
    await sharing_manager.record_view(share.share_id)
    
    # 检查访问权限
    has_access = await sharing_manager.check_access(
        share.share_id,
        user_id=None,
        action="view",
    )
    print(f"Can view: {has_access}")

asyncio.run(sharing_example())
```

### 示例11: 渲染工件

```python
from backend.app.services.artifacts import ArtifactRenderer

async def rendering_example():
    artifact_engine = ArtifactEngine(storage, version_control)
    renderer = ArtifactRenderer()
    
    # 获取工件
    artifact = await artifact_engine.get("artifact_123")
    
    # 渲染为HTML
    html = renderer.render(artifact)
    
    # 保存到文件
    with open("artifact.html", "w") as f:
        f.write(html)
    
    # 获取依赖
    dependencies = renderer.get_dependencies(artifact)
    print(f"Dependencies: {dependencies}")

asyncio.run(rendering_example())
```

## 工件模板库

### 模板1: 销售仪表板

```python
SALES_DASHBOARD_TEMPLATE = {
    "type": "dashboard",
    "title": "Sales Dashboard",
    "content": """
    <div class="dashboard">
        <div class="card">
            <h3>Total Revenue</h3>
            <canvas id="revenue-chart"></canvas>
        </div>
        <div class="card">
            <h3>Top Products</h3>
            <canvas id="products-chart"></canvas>
        </div>
        <div class="card">
            <h3>Regional Sales</h3>
            <canvas id="regions-chart"></canvas>
        </div>
    </div>
    """,
    "tags": ["sales", "dashboard", "analytics"],
}
```

### 模板2: 技术文档

```python
TECH_DOC_TEMPLATE = {
    "type": "markdown",
    "title": "API Documentation",
    "content": """
# API Documentation

## Overview
This API provides access to...

## Authentication
Use Bearer tokens for authentication.

## Endpoints

### GET /api/v1/resource
Retrieve a resource.

**Parameters:**
- `id` (required): Resource ID

**Response:**
```json
{
  "id": "123",
  "name": "Resource"
}
```

## Error Handling
Errors are returned with appropriate HTTP status codes.
""",
    "tags": ["documentation", "api"],
}
```

### 模板3: 数据分析报告

```python
DATA_ANALYSIS_TEMPLATE = {
    "type": "html",
    "title": "Data Analysis Report",
    "content": """
    <div style="max-width: 1200px; margin: 0 auto; padding: 20px;">
        <h1>Data Analysis Report</h1>
        <section>
            <h2>Executive Summary</h2>
            <p>Key findings and insights...</p>
        </section>
        <section>
            <h2>Detailed Analysis</h2>
            <canvas id="analysis-chart"></canvas>
        </section>
        <section>
            <h2>Recommendations</h2>
            <ul>
                <li>Recommendation 1</li>
                <li>Recommendation 2</li>
            </ul>
        </section>
    </div>
    """,
    "tags": ["analysis", "report", "data"],
}
```

### 模板4: 交互式表单

```python
INTERACTIVE_FORM_TEMPLATE = {
    "type": "react",
    "title": "Interactive Form",
    "content": """
    function FormApp() {
        const [formData, setFormData] = React.useState({
            name: '',
            email: '',
            message: ''
        });
        
        const handleChange = (e) => {
            setFormData({
                ...formData,
                [e.target.name]: e.target.value
            });
        };
        
        const handleSubmit = (e) => {
            e.preventDefault();
            console.log('Submitted:', formData);
        };
        
        return (
            <form onSubmit={handleSubmit} style={{ maxWidth: '500px', margin: '20px auto' }}>
                <input
                    type="text"
                    name="name"
                    placeholder="Name"
                    value={formData.name}
                    onChange={handleChange}
                    style={{ width: '100%', padding: '10px', marginBottom: '10px' }}
                />
                <input
                    type="email"
                    name="email"
                    placeholder="Email"
                    value={formData.email}
                    onChange={handleChange}
                    style={{ width: '100%', padding: '10px', marginBottom: '10px' }}
                />
                <textarea
                    name="message"
                    placeholder="Message"
                    value={formData.message}
                    onChange={handleChange}
                    style={{ width: '100%', padding: '10px', marginBottom: '10px', minHeight: '100px' }}
                />
                <button type="submit" style={{ padding: '10px 20px', cursor: 'pointer' }}>
                    Submit
                </button>
            </form>
        );
    }
    
    ReactDOM.render(<FormApp />, document.getElementById('root'));
    """,
    "tags": ["form", "interactive", "react"],
}
```

## API集成示例

### 示例12: 通过HTTP API创建工件

```bash
curl -X POST http://localhost:8000/api/v1/artifacts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "type": "html",
    "content": "<h1>Hello World</h1>",
    "title": "Hello Artifact",
    "description": "A simple hello world artifact",
    "tags": ["hello", "world"],
    "is_public": true
  }'
```

### 示例13: 通过HTTP API执行搜索

```bash
curl -X POST http://localhost:8000/api/v1/search/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "machine learning",
    "num_results": 10,
    "provider": "serper"
  }'
```

### 示例14: 通过HTTP API创建分享链接

```bash
curl -X POST "http://localhost:8000/api/v1/artifacts/artifact_123/share?is_public=true&allow_download=true&expires_in_days=30" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 性能优化建议

1. **缓存搜索结果**: 相同查询在1小时内返回缓存结果
2. **批量操作**: 使用批量API减少请求数
3. **异步处理**: 使用异步API处理长时间操作
4. **CDN加速**: 工件依赖通过CDN加载
5. **数据库索引**: 为常用查询字段添加索引

## 故障排除

### 搜索返回空结果

```python
# 检查API密钥
# 检查网络连接
# 尝试不同的搜索词
# 检查缓存是否过期
```

### 工件渲染失败

```python
# 验证工件类型
# 检查内容格式
# 查看浏览器控制台错误
# 检查依赖是否加载
```

### 分享链接过期

```python
# 创建新的分享链接
# 增加过期时间
# 检查系统时间
```

## 相关资源

- [完整API文档](../api/WEB_SEARCH_ARTIFACTS_API.md)
- [集成方案](../../concepts/planning/INTEGRATION_PLAN.md)
- [源代码](../backend/app/services/)
