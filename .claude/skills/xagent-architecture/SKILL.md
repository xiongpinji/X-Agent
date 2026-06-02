# X-Agent 架构导航

## 描述

帮助理解和导航 X-Agent 原创内核计划的架构。这个项目采用分层设计，包含 Agent 核心、工作流、记忆、协作等多个子系统。

## 适用场景

- 新成员快速理解项目结构
- 修改代码前确认影响范围
- 架构重构和模块拆分
- 排查跨模块问题

## 架构分层

### 1. 接口层 (`backend/app/api/`)

50+ FastAPI 路由端点，按功能分组：
- `agent.py` - Agent 执行控制
- `workflows.py` - 工作流管理
- `memory.py` - 记忆操作
- `collaboration.py` - 多智能体协作
- `browser.py` - 浏览器自动化
- `desktop.py` - 桌面自动化
- `audit.py` - 审计日志
- `tools.py` - 工具注册

### 2. 核心层 (`backend/app/core/`)

60+ 核心模块：

| 模块 | 职责 |
|------|------|
| `agent.py` | 智能体主引擎 |
| `orchestrator.py` | 任务编排器 |
| `planning.py` | 任务规划 |
| `execution_planner.py` | 执行计划生成 |
| `repair_loop.py` | 失败修复循环 |
| `agent_state_manager.py` | 状态机管理 |
| `workflows.py` | DAG 工作流引擎 |
| `replay.py` | 执行回放 |
| `verification.py` | 结果验证 |
| `memory.py` | 记忆抽象层 |
| `memory_postgres.py` | PostgreSQL 记忆存储 |
| `memory_graph.py` | 图记忆（Neo4j） |
| `collaboration.py` | 多 Agent 协作 |
| `org.py` | 组织架构 |
| `browser.py` | Playwright 浏览器控制 |
| `desktop.py` | 桌面自动化 |
| `open_source*.py` | 开源工具发现系统 |
| `security.py` | 安全策略 |
| `tracing.py` | Langfuse 追踪 |

### 3. 服务层 (`backend/app/services/`)

具体业务服务实现，如记忆服务、LLM 服务等。

## 导航原则

1. **改 API 先看路由**，再追踪到 core 模块
2. **改核心逻辑先看状态机** (`agent_state_manager.py`)，确认状态转换影响
3. **改记忆系统** 需要同时考虑 `memory.py` + `memory_postgres.py` + `memory_graph.py`
4. **改工作流** 注意 `workflows.py` 和 `replay.py` 的联动
5. **新增工具** 在 `tools.py` 注册，在 `backend/app/core/` 实现逻辑

## 关键数据流

```
用户请求 → API Router → Core Module → Service/DB → LLM API
                ↓              ↓
         状态变更 → agent_state_manager
         审计日志 → tracing.py → Langfuse
         记忆更新 → memory.py → Postgres/Qdrant
```

## 常用命令

```bash
# 查找函数定义
rg "def function_name" backend/

# 查看模块依赖
rg "from backend.app.core" backend/ --stats

# 查看测试覆盖
pytest --co -q tests/ | grep module_name
```
