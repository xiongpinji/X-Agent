# X-Agent 开发者指南

**版本**: 1.0.0  
**最后更新**: 2026-05-27  
**语言**: 中文 | [English](DEVELOPER_GUIDE_EN.md)

---

## 目录

1. [开发环境设置](#开发环境设置)
2. [项目架构详解](#项目架构详解)
3. [核心模块说明](#核心模块说明)
4. [开发工作流](#开发工作流)
5. [扩展开发](#扩展开发)
6. [调试技巧](#调试技巧)
7. [性能优化](#性能优化)

---

## 开发环境设置

### 前置要求

- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ (前端开发)
- Docker & Docker Compose
- Git

### 完整设置步骤

#### 1. 克隆并初始化项目

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core

# 初始化 Git 子模块
git submodule update --init --recursive
```

#### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 升级 pip
pip install --upgrade pip setuptools wheel
```

#### 3. 安装开发依赖

```bash
# 安装项目及开发依赖
pip install -e ".[dev]"

# 安装额外的开发工具
pip install pytest pytest-cov pytest-asyncio black ruff mypy
```

#### 4. 启动基础设施

```bash
# 使用 Docker Compose 启动 PostgreSQL 和 Qdrant
docker-compose up -d

# 验证服务状态
docker-compose ps
```

#### 5. 配置环境变量

```bash
cp .env.example .env.development

# 编辑 .env.development
cat > .env.development << EOF
# 数据库配置
DATABASE_URL=postgresql://postgres:password@localhost:5432/xagent_dev
QDRANT_URL=http://localhost:6333

# LLM 配置
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# 追踪配置
LANGFUSE_PUBLIC_KEY=your_key_here
LANGFUSE_SECRET_KEY=your_key_here

# 开发配置
DEBUG=true
LOG_LEVEL=DEBUG
EOF
```

#### 6. 初始化数据库

```bash
# 运行迁移
python -m backend.app.core.migration init

# 创建测试数据
python scripts/seed_dev_data.py
```

#### 7. 启动开发服务器

```bash
# 终端 1: 启动后端
uvicorn backend.app.web:app --reload --host 0.0.0.0 --port 8000

# 终端 2: 启动工作流处理器
xagent-workflow-worker --dev

# 终端 3: 启动前端（如果有）
cd frontend && npm run dev
```

#### 8. 验证安装

```bash
# 检查 API 健康状态
curl http://localhost:8000/health

# 查看 API 文档
# 访问 http://localhost:8000/docs
```

---

## 项目架构详解

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend Layer                         │
│              (React/Vue + TypeScript)                    │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                   │
│  /agents  /workflows  /tools  /memory  /approvals        │
│  /audit   /metrics    /ops    /auth    /tenants          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  Core Services Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ LLM Router   │  │ Memory Sys   │  │ Policy Eng   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Workflow Eng │  │ Approval Sys │  │ Audit Trail  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Infrastructure Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │PostgreSQL│  │ Qdrant   │  │Playwright│  │Langfuse  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 目录结构

```
x-agent-core/
├── backend/
│   ├── app/
│   │   ├── api/              # API 端点
│   │   ├── core/             # 核心业务逻辑
│   │   ├── services/         # 服务层
│   │   ├── models/           # 数据模型
│   │   ├── schemas/          # 请求/响应模式
│   │   └── web.py            # FastAPI 应用
│   ├── tests/                # 测试文件
│   └── requirements.txt       # 依赖列表
├── frontend/                 # 前端代码
├── docs/                     # 文档
├── scripts/                  # 工具脚本
├── deployment/               # 部署配置
└── docker-compose.yml        # 开发环境配置
```

---

## 核心模块说明

### 1. Agent 引擎 (`backend/app/core/agent.py`)

**职责**: 管理 Agent 的生命周期和执行

**关键类**:
```python
class Agent:
    """Agent 核心类"""
    
    def __init__(self, name: str, capabilities: List[str]):
        self.id = generate_id()
        self.name = name
        self.capabilities = capabilities
        self.state = AgentState.IDLE
    
    async def run(self, task: str, context: Dict) -> Result:
        """执行任务"""
        pass
    
    async def think(self, context: Dict) -> Thought:
        """思考下一步行动"""
        pass
    
    async def act(self, action: Action) -> Result:
        """执行动作"""
        pass
```

**扩展点**:
- 自定义 Agent 类型
- 自定义思考策略
- 自定义动作执行

### 2. 工具系统 (`backend/app/core/tools.py`)

**职责**: 管理和执行工具

**关键类**:
```python
class Tool:
    """工具基类"""
    
    name: str
    description: str
    parameters: Dict[str, Parameter]
    
    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        pass

class ToolRegistry:
    """工具注册表"""
    
    def register(self, tool: Tool) -> None:
        """注册工具"""
        pass
    
    def get(self, name: str) -> Tool:
        """获取工具"""
        pass
    
    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        pass
```

**内置工具**:
- `browser`: 浏览器自动化
- `file`: 文件操作
- `api`: HTTP 请求
- `code`: 代码执行
- `search`: 搜索功能

### 3. 记忆系统 (`backend/app/core/memory_*.py`)

**职责**: 提供持久化和语义存储

**关键类**:
```python
class Memory:
    """记忆系统"""
    
    async def store(self, key: str, value: Any, metadata: Dict = None) -> None:
        """存储数据"""
        pass
    
    async def retrieve(self, key: str) -> Any:
        """检索数据"""
        pass
    
    async def search(self, query: str, top_k: int = 5) -> List[Result]:
        """搜索数据"""
        pass
    
    async def semantic_search(self, query: str, top_k: int = 5) -> List[Result]:
        """语义搜索"""
        pass
```

**实现**:
- `MemoryPostgres`: 结构化存储
- `MemoryQdrant`: 向量存储

### 4. 工作流引擎 (`backend/app/core/execution_planner.py`)

**职责**: 编排和执行工作流

**关键类**:
```python
class Workflow:
    """工作流定义"""
    
    def add_node(self, node: Node) -> None:
        """添加节点"""
        pass
    
    def add_edge(self, edge: Edge) -> None:
        """添加边"""
        pass
    
    async def execute(self, context: Dict = None) -> WorkflowRun:
        """执行工作流"""
        pass

class WorkflowRun:
    """工作流执行实例"""
    
    status: WorkflowStatus
    nodes: Dict[str, NodeRun]
    
    def get_timeline(self) -> Timeline:
        """获取执行时间线"""
        pass
    
    def get_metrics(self) -> Metrics:
        """获取执行指标"""
        pass
```

### 5. 审批系统 (`backend/app/core/approvals.py`)

**职责**: 管理人工审批流程

**关键类**:
```python
class ApprovalRequest:
    """审批请求"""
    
    id: str
    action: str
    requester: str
    status: ApprovalStatus
    
    async def approve(self, approver: str, comment: str = None) -> None:
        """批准"""
        pass
    
    async def reject(self, approver: str, reason: str) -> None:
        """拒绝"""
        pass

class ApprovalPolicy:
    """审批策略"""
    
    def should_require_approval(self, action: Action) -> bool:
        """判断是否需要审批"""
        pass
```

### 6. 审计系统 (`backend/app/core/audit.py`)

**职责**: 记录所有操作的审计日志

**关键类**:
```python
class AuditLog:
    """审计日志"""
    
    timestamp: datetime
    actor: str
    action: str
    resource: str
    changes: Dict
    status: str
    
    async def save(self) -> None:
        """保存日志"""
        pass

class AuditTrail:
    """审计追踪"""
    
    async def log_action(self, action: str, **kwargs) -> None:
        """记录动作"""
        pass
    
    async def get_history(self, resource: str) -> List[AuditLog]:
        """获取历史记录"""
        pass
```

---

## 开发工作流

### 代码规范

#### Python 代码风格

遵循 PEP 8 标准，使用 Black 和 Ruff 进行格式化：

```bash
# 格式化代码
black backend/

# 检查代码风格
ruff check backend/

# 类型检查
mypy backend/
```

#### 命名规范

```python
# 类名：PascalCase
class WorkflowEngine:
    pass

# 函数名：snake_case
def execute_workflow():
    pass

# 常量：UPPER_SNAKE_CASE
MAX_RETRIES = 3

# 私有方法：_leading_underscore
def _internal_method():
    pass
```

#### 文档字符串

```python
def execute_workflow(workflow_id: str, context: Dict) -> WorkflowRun:
    """
    执行工作流。
    
    Args:
        workflow_id: 工作流 ID
        context: 执行上下文
    
    Returns:
        WorkflowRun: 工作流执行实例
    
    Raises:
        WorkflowNotFound: 工作流不存在
        ExecutionError: 执行失败
    
    Example:
        >>> run = await execute_workflow("wf_123", {})
        >>> print(run.status)
    """
    pass
```

### 测试要求

#### 单元测试

```python
import pytest
from backend.app.core.agent import Agent

@pytest.mark.asyncio
async def test_agent_creation():
    """测试 Agent 创建"""
    agent = Agent(name="TestAgent", capabilities=["run"])
    assert agent.name == "TestAgent"
    assert "run" in agent.capabilities

@pytest.mark.asyncio
async def test_agent_execution():
    """测试 Agent 执行"""
    agent = Agent(name="TestAgent", capabilities=["run"])
    result = await agent.run("test task", {})
    assert result is not None
```

#### 集成测试

```python
@pytest.mark.asyncio
async def test_workflow_execution(client):
    """测试工作流执行"""
    # 创建工作流
    response = await client.post("/api/v1/workflows", json={
        "name": "TestWorkflow",
        "nodes": [...]
    })
    assert response.status_code == 201
    
    # 执行工作流
    workflow_id = response.json()["id"]
    response = await client.post(f"/api/v1/workflows/{workflow_id}/execute")
    assert response.status_code == 200
```

#### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_agent.py

# 生成覆盖率报告
pytest --cov=backend tests/

# 运行异步测试
pytest -m asyncio
```

### PR 流程

#### 1. 创建分支

```bash
# 从 develop 分支创建新分支
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name

# 或修复 bug
git checkout -b bugfix/issue-description
```

#### 2. 开发和提交

```bash
# 进行开发...

# 格式化代码
black backend/
ruff check backend/ --fix

# 运行测试
pytest

# 提交更改
git add .
git commit -m "feat: add new feature

- Detailed description of changes
- Additional context if needed

Fixes #123"
```

#### 3. 推送和创建 PR

```bash
# 推送分支
git push origin feature/your-feature-name

# 在 GitHub 上创建 PR
# - 填写 PR 标题和描述
# - 链接相关 Issue
# - 请求代码审查
```

#### 4. 代码审查

- 至少需要 2 个批准
- 所有检查必须通过
- 解决所有评论

#### 5. 合并

```bash
# 合并到 develop
git checkout develop
git pull origin develop
git merge feature/your-feature-name
git push origin develop
```

---

## 扩展开发

### 自定义工具开发

```python
from backend.app.core.tools import Tool, Parameter

class CustomTool(Tool):
    """自定义工具示例"""
    
    name = "custom_tool"
    description = "执行自定义操作"
    
    parameters = {
        "input": Parameter(
            type="string",
            description="输入数据",
            required=True
        ),
        "mode": Parameter(
            type="string",
            description="处理模式",
            enum=["fast", "accurate"],
            default="fast"
        )
    }
    
    async def execute(self, input: str, mode: str = "fast") -> Dict:
        """执行工具"""
        # 实现工具逻辑
        result = self._process(input, mode)
        return {"result": result}
    
    def _process(self, input: str, mode: str) -> str:
        """处理逻辑"""
        if mode == "fast":
            return input.upper()
        else:
            return input.lower()

# 注册工具
from backend.app.core.tools import tool_registry
tool_registry.register(CustomTool())
```

### 插件开发

```python
from backend.app.core.plugin import Plugin

class MyPlugin(Plugin):
    """自定义插件"""
    
    name = "my_plugin"
    version = "1.0.0"
    description = "My custom plugin"
    
    def initialize(self):
        """初始化插件"""
        self.logger.info(f"Initializing {self.name}")
    
    def register_tools(self):
        """注册工具"""
        self.register_tool("my_tool", CustomTool())
    
    def register_api(self):
        """注册 API 端点"""
        @self.app.get("/api/v1/my-plugin/status")
        async def get_status():
            return {"status": "active"}
    
    def shutdown(self):
        """关闭插件"""
        self.logger.info(f"Shutting down {self.name}")
```

### API 扩展

```python
from fastapi import APIRouter, Depends
from backend.app.api.security import get_current_user

router = APIRouter(prefix="/api/v1/custom", tags=["custom"])

@router.get("/data")
async def get_custom_data(user = Depends(get_current_user)):
    """获取自定义数据"""
    return {"data": "custom"}

@router.post("/process")
async def process_data(data: Dict, user = Depends(get_current_user)):
    """处理数据"""
    # 处理逻辑
    return {"processed": data}

# 在 web.py 中注册路由
app.include_router(router)
```

---

## 调试技巧

### 启用调试模式

```python
# 在 .env 中设置
DEBUG=true
LOG_LEVEL=DEBUG

# 或在代码中设置
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 使用调试器

```python
# 使用 pdb
import pdb; pdb.set_trace()

# 或使用 ipdb（更好的体验）
import ipdb; ipdb.set_trace()

# 在 VS Code 中调试
# 1. 安装 Python 扩展
# 2. 创建 .vscode/launch.json
# 3. 设置断点并按 F5 启动调试
```

### 查看日志

```bash
# 查看实时日志
docker-compose logs -f backend

# 查看特定服务的日志
docker-compose logs -f postgres

# 查看历史日志
docker-compose logs backend | tail -100
```

### 使用 Langfuse 追踪

```python
from langfuse import Langfuse

langfuse = Langfuse()

@langfuse.trace
async def my_function():
    """被追踪的函数"""
    pass

# 在 Langfuse 仪表板查看追踪
# http://localhost:3000
```

### 数据库查询调试

```python
# 启用 SQLAlchemy 日志
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# 或在 .env 中设置
SQLALCHEMY_ECHO=true
```

---

## 性能优化

### 数据库优化

```python
# 1. 添加索引
from sqlalchemy import Index

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True)
    name = Column(String, index=True)
    status = Column(String, index=True)
    
    __table_args__ = (
        Index('idx_agent_status_created', 'status', 'created_at'),
    )

# 2. 使用连接池
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40
)

# 3. 批量操作
session.bulk_insert_mappings(Agent, agents_data)
session.commit()
```

### 缓存优化

```python
from functools import lru_cache
from backend.app.core.cache import cache

# 使用 LRU 缓存
@lru_cache(maxsize=128)
def get_agent_config(agent_id: str):
    return load_config(agent_id)

# 使用 Redis 缓存
@cache.cached(timeout=300)
async def get_workflow_template(template_id: str):
    return await load_template(template_id)
```

### 异步优化

```python
import asyncio

# 并发执行多个任务
async def execute_parallel_tasks(tasks):
    results = await asyncio.gather(*tasks)
    return results

# 使用连接池
async with aiohttp.ClientSession() as session:
    tasks = [fetch_url(session, url) for url in urls]
    results = await asyncio.gather(*tasks)
```

### 内存优化

```python
# 1. 使用生成器处理大数据集
def process_large_file(filepath):
    with open(filepath) as f:
        for line in f:
            yield process_line(line)

# 2. 及时释放资源
async with get_connection() as conn:
    result = await conn.execute(query)
    # 自动释放连接

# 3. 监控内存使用
import tracemalloc
tracemalloc.start()
# ... 执行代码 ...
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.1f}MB; Peak: {peak / 1024 / 1024:.1f}MB")
```

---

## 获取帮助

- **文档**: [完整文档](README.md)
- **API 参考**: [API 文档](API_REFERENCE.md)
- **示例代码**: [示例集合](../examples/)
- **GitHub Issues**: [报告问题](https://github.com/x-agent/x-agent-core/issues)
- **开发者论坛**: [讨论区](https://github.com/x-agent/x-agent-core/discussions)

---

**X-Agent 开发者指南** - 为智能系统贡献代码
