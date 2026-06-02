# X-Agent 完整开发工作流

## 描述

从需求到上线的完整开发流程，专为 X-Agent AI Agent 内核项目设计。涵盖架构设计、编码、测试、调试、部署全生命周期。

## 适用场景

- 新功能开发
- Bug 修复
- 架构重构
- 性能优化
- 安全加固

---

## 阶段一：需求分析与架构设计

### 1.1 理解需求

**Claude Code 指令模板：**

```
请帮我分析这个需求：
[粘贴需求描述]

请用 sequential-thinking MCP 分步分析：
1. 这个需求涉及哪些核心模块？
2. 对现有状态机有什么影响？
3. 需要新增哪些数据模型？
4. 对记忆系统有什么要求？
5. 安全性方面需要注意什么？
```

### 1.2 架构设计

**使用 xagent-architecture skill 导航：**

```
参考 xagent-architecture，帮我设计 [功能名] 的架构：
- 应该放在哪个模块？
- 需要修改哪些现有文件？
- 新增哪些文件？
- 画出数据流图
```

**设计 checklist：**
- [ ] 确认影响的核心模块（agent/orchestrator/memory/workflow）
- [ ] 确认状态机变更（agent_state_manager）
- [ ] 确认 API 路由位置
- [ ] 确认数据库表变更
- [ ] 确认是否需要向量检索（Qdrant）
- [ ] 确认是否需要图关系（Neo4j）

---

## 阶段二：开发编码

### 2.1 环境准备

```bash
# 启动所有依赖服务
docker-compose up -d postgres qdrant neo4j redis

# 验证服务状态
docker-compose ps

# 激活虚拟环境
uv venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 安装依赖
uv pip install -e ".[dev]"
```

### 2.2 API 开发（使用 xagent-api-dev skill）

**顺序：**
1. 定义 Pydantic 请求/响应模型
2. 实现核心逻辑（backend/app/core/）
3. 注册 API 路由（backend/app/api/）
4. 添加错误处理

**Claude Code 指令：**

```
参考 xagent-api-dev，帮我实现 [功能名] 的 API：

1. 先定义 Pydantic 模型（字段验证规则）
2. 在 core/ 实现业务逻辑
3. 在 api/ 注册 FastAPI 路由
4. 确保异步处理
5. 加上 Langfuse 追踪
```

### 2.3 记忆系统集成（使用 xagent-memory-dev skill）

如果功能涉及记忆：

```
参考 xagent-memory-dev，帮我设计记忆存储方案：

1. 短期记忆：session 级别
2. 长期记忆：PostgreSQL 表结构
3. 语义检索：Qdrant collection 设计
4. 图关系：Neo4j 节点/关系定义
5. 写入时考虑并发冲突
```

### 2.4 代码质量检查

```bash
# 代码格式化
ruff format backend/

# 代码检查
ruff check backend/

# 类型检查（如果有 mypy）
mypy backend/ --strict
```

**Claude Code 指令：**

```
帮我检查这段代码：
1. 是否有类型注解？
2. 是否有安全风险？（参考 xagent-security）
3. 是否符合项目编码规范？
4. 异步处理是否正确？
```

---

## 阶段三：测试

### 3.1 单元测试（使用 xagent-testing skill）

**Claude Code 指令：**

```
参考 xagent-testing，帮我对 [模块名] 写测试：

1. 正常路径测试
2. 边界条件测试
3. 异常处理测试
4. 并发测试（如果适用）
5. Mock 外部依赖（LLM API、数据库）
```

**测试命令：**

```bash
# 运行单个测试文件
pytest tests/core/test_agent.py -v

# 运行直到失败
pytest tests/ -x -v

# 带覆盖率
pytest --cov=backend --cov-report=html

# 并行执行
pytest -n auto
```

### 3.2 API 集成测试

使用 PostgreSQL MCP 检查测试数据：

```
用 postgres MCP 查一下测试数据库的状态：
- 测试表是否创建？
- 测试数据是否正确插入？
- 清理残留数据
```

### 3.3 安全测试（使用 xagent-security skill）

```
参考 xagent-security，帮我审查这段代码的安全性：

1. 是否有命令注入风险？
2. SQL 是否参数化？
3. 是否有路径遍历风险？
4. 敏感信息是否泄露？
5. 输入是否经过验证？
```

---

## 阶段四：调试

### 4.1 日志分析

```bash
# 查看最新日志
tail -f backend/logs/app.log

# 查找错误
grep -i "error" backend/logs/app.log | tail -20

# Langfuse 追踪（如配置）
```

**Claude Code 指令：**

```
帮我分析这个错误：
[粘贴错误堆栈]

1. 定位出错代码位置
2. 分析根本原因
3. 提出修复方案
4. 验证修复后的测试
```

### 4.2 数据库调试（使用 PostgreSQL MCP）

```
用 postgres MCP 帮我调试：

1. 查这个表的结构：\d agent_runs
2. 查最近10条记录
3. 这个查询为什么慢？EXPLAIN ANALYZE
4. 检查索引是否命中
```

### 4.3 API 调试（使用 Fetch 或 curl）

```bash
# 测试 API
curl -X POST http://localhost:8000/agent/start \
  -H "Content-Type: application/json" \
  -d '{"task": "test", "model": "deepseek-chat"}'
```

### 4.4 浏览器/桌面自动化调试

```bash
# 检查 Playwright 浏览器状态
playwright show-browsers

# 录制调试
playwright codegen http://localhost:3000
```

---

## 阶段五：部署

### 5.1 构建 Docker 镜像

```bash
# 构建
docker build -t xagent:latest .

# 运行完整栈
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

### 5.2 数据库迁移

```bash
# 如果有 Alembic
alembic revision --autogenerate -m "add feature xxx"
alembic upgrade head

# 验证迁移
alembic current
alembic history
```

### 5.3 健康检查

```bash
# API 健康检查
curl http://localhost:8000/health

# 数据库连接检查
curl http://localhost:8000/health/db

# 向量数据库检查
curl http://localhost:8000/health/qdrant
```

---

## 阶段六：监控与运维

### 6.1 Langfuse 追踪监控

- 查看 Agent 执行链路
- 分析 LLM 调用耗时
- 追踪错误率

### 6.2 审计日志

使用 audit API 查看：
```bash
curl http://localhost:8000/audit/logs?limit=100
```

### 6.3 性能监控

```bash
# 查看慢查询
# PostgreSQL 慢查询日志

# API 性能分析
# 使用 wrk 或 ab
wrk -t4 -c100 -d30s http://localhost:8000/agent/status/xxx
```

---

## 常用 Claude Code 指令组合

### 场景1：开发新 Agent 功能

```
1. 用 sequential-thinking 分析需求
2. 用 xagent-architecture 确认模块位置
3. 用 xagent-api-dev 写 API
4. 用 xagent-memory-dev 设计记忆存储
5. 用 xagent-testing 写测试
6. 用 xagent-security 审查安全
```

### 场景2：修复 Bug

```
1. 查看错误日志
2. 用 postgres MCP 检查数据状态
3. 用 xagent-architecture 定位相关模块
4. 修复代码
5. 用 xagent-testing 写回归测试
6. 运行测试验证
```

### 场景3：性能优化

```
1. 用 postgres MCP 分析慢查询
2. 用 filesystem MCP 搜索相关代码
3. 识别瓶颈（数据库/LLM API/循环）
4. 实施优化（索引/缓存/批量）
5. 基准测试验证
```

### 场景4：安全加固

```
1. 用 xagent-security 全面审查
2. 用 ruff/bandit 静态分析
3. 修复高危问题
4. 写安全测试
5. 验证修复
```

---

## 快捷键速查

```bash
# 启动开发环境
docker-compose up -d postgres qdrant neo4j redis

# 启动后端
uvicorn backend.app.main:app --reload --port 8000

# 运行测试
pytest -x -v

# 代码检查
ruff check backend/ && ruff format backend/

# 清理进程
./cleanup_uvicorn.ps1

# 查看日志
tail -f backend/logs/app.log
```
