# X-Agent 测试策略

## 描述

X-Agent 项目使用 pytest + pytest-asyncio，拥有 100+ 测试文件。测试覆盖 Agent 核心、API、记忆、工作流等模块。

## 适用场景

- 编写新功能的测试
- 调试失败的测试
- 提升测试覆盖率
- CI/CD 集成

## 测试框架

- pytest 8.2.0+
- pytest-asyncio 0.23.0+
- httpx (API 测试)
- ruff (代码检查)

## 测试目录结构

```
tests/
├── conftest.py          # 全局 fixtures
├── core/                # 核心模块测试
│   ├── test_agent.py
│   ├── test_memory.py
│   ├── test_workflows.py
│   └── ...
├── api/                 # API 路由测试
│   ├── test_agent_api.py
│   └── ...
└── services/            # 服务层测试
```

## 核心 Fixtures

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from backend.app.main import app

@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def db():
    # 使用测试数据库或 mock
    ...

@pytest.fixture
def mock_llm_response():
    return {
        "choices": [{"message": {"content": "Mocked LLM response"}}]
    }
```

## 测试类型

### 1. 单元测试

```python
# tests/core/test_planning.py
import pytest
from backend.app.core.planning import TaskPlanner

@pytest.mark.asyncio
async def test_plan_simple_task():
    planner = TaskPlanner()
    task = "Search for Python web frameworks"
    plan = await planner.create_plan(task)
    assert len(plan.steps) >= 1
    assert any("search" in step.action.lower() for step in plan.steps)
```

### 2. API 集成测试

```python
# tests/api/test_workflows.py
@pytest.mark.asyncio
async def test_create_workflow(client: AsyncClient):
    response = await client.post("/workflows", json={
        "name": "test-workflow",
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "end", "type": "end"}
        ],
        "edges": [{"from": "start", "to": "end"}]
    })
    assert response.status_code == 201
    data = response.json()
    assert data["workflow_id"] is not None
```

### 3. 异步测试

```python
@pytest.mark.asyncio
async def test_memory_concurrent_writes():
    from backend.app.core.memory import MemoryBackend

    memory = MemoryBackend()
    tasks = [
        memory.store(f"key_{i}", {"value": i})
        for i in range(10)
    ]
    await asyncio.gather(*tasks)

    # 验证所有写入成功
    for i in range(10):
        result = await memory.retrieve(f"key_{i}")
        assert result["value"] == i
```

## 代码检查

```bash
# 运行 ruff 检查
ruff check backend/

# 自动修复
ruff check --fix backend/

# 格式化
ruff format backend/
```

## 测试命令速查

```bash
# 全部测试
pytest

# 指定模块
pytest tests/core/test_agent.py -v

# 指定测试函数
pytest tests/core/test_agent.py::test_execute -v

# 失败时进入 pdb
pytest --pdb

# 覆盖率
pytest --cov=backend --cov-report=html

# 并行执行（需安装 pytest-xdist）
pytest -n auto
```

## Mock 策略

- **LLM API**: 使用 `respx` 或 `pytest-httpx` mock HTTP 请求
- **数据库**: 使用 `pytest-postgresql` 或 SQLite in-memory
- **Playwright**: 使用 `pytest-playwright` 的 page mock
- **Langfuse**: 设置环境变量 `LANGFUSE_SECRET_KEY=test` 关闭追踪
