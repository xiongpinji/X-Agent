# X-Agent 原创内核计划 - Agent 上下文

## 项目概述

X-Agent 是一个面向 AI 代理执行系统的后端内核，采用 Python + FastAPI 构建。项目包含 118+ Python 文件、60+ 核心模块、100+ 测试文件，具备完整的 Agent 编排、记忆系统、工作流管理、浏览器自动化等功能。

## 技术栈

- **后端框架**: FastAPI 0.115.0+, Uvicorn 0.30.0+
- **数据验证**: Pydantic 2.7.0+
- **数据库**: PostgreSQL (asyncpg/psycopg), Qdrant (向量), Neo4j (图谱), Redis
- **LLM 集成**: OpenAI API 兼容, DeepSeek
- **浏览器自动化**: Playwright 1.48.0+
- **可观测性**: Langfuse 2.60.0+
- **测试**: pytest 8.2.0+, pytest-asyncio 0.23.0+
- **代码质量**: ruff
- **容器**: Docker, Docker Compose

## 项目结构

```
backend/app/
├── api/           # 50+ FastAPI 路由端点
├── core/          # 60+ 核心模块（Agent、工作流、记忆、协作等）
├── services/      # 业务服务层
└── main.py        # 应用入口

tests/             # 100+ 测试文件
data/              # 数据脚本
diagrams/          # 架构图
scripts/           # 工具脚本
templates/         # 模板文件
```

## 核心模块速查

| 模块 | 文件 | 职责 |
|------|------|------|
| Agent 引擎 | `core/agent.py` | 智能体主执行循环 |
| 编排器 | `core/orchestrator.py` | 任务调度与委派 |
| 规划器 | `core/planning.py` | 任务拆解与规划 |
| 状态机 | `core/agent_state_manager.py` | Agent 生命周期管理 |
| 修复循环 | `core/repair_loop.py` | 失败检测与自动修复 |
| 工作流 | `core/workflows.py` | DAG 工作流引擎 |
| 记忆 | `core/memory.py` | 记忆抽象层 |
| 图记忆 | `core/memory_graph.py` | Neo4j 关系图谱 |
| 协作 | `core/collaboration.py` | 多智能体通信 |
| 浏览器 | `core/browser.py` | Playwright 自动化 |
| 桌面 | `core/desktop.py` | 桌面自动化 |
| 审计 | `core/audit.py` | 执行审计 |
| 追踪 | `core/tracing.py` | Langfuse 链路追踪 |
| 安全 | `core/security.py` | 安全策略 |

## 环境变量

```bash
# 数据库
DATABASE_URL=postgresql+asyncpg://xagent:xagent@localhost:5432/xagent

# LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
XAGENT_LLM_BACKEND=mock

# 记忆
XAGENT_MEMORY_BACKEND=jsonl
XAGENT_MEMORY_STORE_PATH=.xagent_runtime/memory.jsonl

# 追踪
XAGENT_TRACE_BACKEND=jsonl
XAGENT_TRACE_STORE_PATH=.xagent_runtime/traces.jsonl
```

## 常用命令

```bash
# 启动后端
uvicorn backend.app.main:app --reload --port 8000

# 运行测试
pytest -v

# 代码检查
ruff check backend/
ruff format backend/

# 数据库（Docker）
docker-compose up postgres qdrant neo4j redis

# 清理 Uvicorn 进程
./cleanup_uvicorn.ps1
```

## 已知问题

- 审计报告发现 9 个高危安全问题（命令注入、SQL 注入、敏感信息泄露等）
- 核心模块耦合度过高，部分文件复杂度超标
- 依赖版本未完全锁定

## 开发原则

1. 所有新增功能必须配套测试
2. API 修改需同步更新 Pydantic 模型
3. 改核心逻辑前先确认状态机影响
4. 记忆操作需考虑并发冲突
5. 自动化模块必须做输入消毒（防命令注入）
