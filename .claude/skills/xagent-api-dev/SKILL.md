# X-Agent FastAPI API 开发

## 描述

针对 X-Agent 项目的 FastAPI API 开发规范。项目使用 Pydantic v2 进行数据验证，依赖注入管理数据库连接。

## 适用场景

- 新增 API 端点
- 修改请求/响应模型
- 数据库迁移
- 添加 API 测试

## 技术栈

- FastAPI 0.115.0+
- Pydantic 2.7.0+
- asyncpg / psycopg (PostgreSQL)
- Uvicorn 0.30.0+

## API 开发规范

### 1. 路由注册位置

所有 API 路由在 `backend/app/api/` 下：

```python
# backend/app/api/my_feature.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/my-feature", tags=["my-feature"])

@router.post("/execute")
async def execute(...):
    ...
```

然后在 `backend/app/main.py` 或路由聚合文件中注册。

### 2. Pydantic 模型规范

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal

class AgentRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=10000)
    model: Literal["gpt-4o", "claude-sonnet", "deepseek-chat"] = "gpt-4o"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_iterations: int = Field(default=10, ge=1, le=100)
```

### 3. 依赖注入模式

```python
from fastapi import Depends

async def get_db():
    # 返回 asyncpg 连接或 SQLAlchemy session
    ...

@router.get("/status/{agent_id}")
async def get_status(
    agent_id: str,
    db=Depends(get_db)
):
    ...
```

### 4. 错误处理

使用标准 HTTP 状态码：
- 400 - 请求参数错误
- 404 - Agent/任务/资源不存在
- 409 - 状态冲突（如任务已在运行）
- 422 - Pydantic 验证失败
- 500 - 内部错误（应配合 tracing）

```python
@router.post("/start")
async def start_agent(request: AgentRequest):
    if not request.task.strip():
        raise HTTPException(status_code=400, detail="Task cannot be empty")
    try:
        result = await agent_core.execute(request)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "started", "run_id": result.run_id}
```

### 5. 异步规范

- 所有 I/O 操作（DB、LLM API、Playwright）必须异步
- CPU 密集型任务应使用 `asyncio.to_thread` 或线程池
- 数据库使用 `asyncpg` 的异步连接

## 测试规范

```python
# tests/api/test_agent.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_start_agent(client: AsyncClient):
    response = await client.post("/agent/start", json={
        "task": "test task",
        "model": "deepseek-chat"
    })
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
```

## 启动调试

```bash
# 开发模式
uvicorn backend.app.main:app --reload --port 8000

# 带日志
uvicorn backend.app.main:app --reload --log-level debug

# 测试
pytest tests/api/ -v --tb=short
```
