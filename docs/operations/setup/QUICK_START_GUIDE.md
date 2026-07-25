# X-Agent 快速入门指南 (5分钟上手)

欢迎使用 X-Agent Core！本指南将帮助你在5分钟内完成首次任务。

## 前置条件 (1分钟)

在开始前，请确保你已安装：

- **Python 3.11+** - 检查版本：`python --version`
- **Docker & Docker Compose** - 推荐用于快速启动数据库
- **Git** - 用于克隆仓库

如果未安装，请参考 [完整安装指南](./INSTALL.md)。

## 第一步：克隆并初始化 (1分钟)

```bash
# 克隆仓库
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -e ".[dev]"
```

## 第二步：启动数据库 (1分钟)

```bash
# 启动 PostgreSQL 和 Qdrant
docker-compose up -d

# 验证数据库已启动
docker-compose ps
```

## 第三步：配置环境 (30秒)

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件（可选，使用默认值即可开始）
# 关键变量：
# - DATABASE_URL: PostgreSQL 连接字符串
# - OPENAI_API_KEY: 如需使用 OpenAI（可选）
```

## 第四步：初始化数据库 (30秒)

```bash
# 运行数据库迁移
python -m backend.app.core.migration init

# 验证连接
curl http://localhost:8000/health
```

## 第五步：启动服务器 (1分钟)

```bash
# 启动 FastAPI 服务器
uvicorn backend.app.web:app --reload

# 服务器将在 http://localhost:8000 启动
# API 文档：http://localhost:8000/docs
```

## 你的第一个任务：Hello World Agent

现在让我们创建并运行你的第一个 Agent。

### 创建 Agent

打开新的终端窗口，运行以下 Python 代码：

```python
import requests
import json

# 创建一个简单的 Agent
agent_data = {
    "name": "HelloWorldAgent",
    "description": "My first X-Agent",
    "capabilities": ["reasoning", "planning"],
    "model": "gpt-4"
}

response = requests.post(
    "http://localhost:8000/api/v1/agents",
    json=agent_data,
    headers={"Content-Type": "application/json"}
)

agent = response.json()
print(f"Agent created: {agent['id']}")
agent_id = agent['id']
```

### 执行任务

```python
# 给 Agent 分配一个任务
task_data = {
    "description": "Say hello and introduce yourself",
    "priority": "high"
}

response = requests.post(
    f"http://localhost:8000/api/v1/agents/{agent_id}/tasks",
    json=task_data,
    headers={"Content-Type": "application/json"}
)

task = response.json()
print(f"Task created: {task['id']}")
print(f"Task status: {task['status']}")
print(f"Result: {task.get('result', 'Processing...')}")
```

### 查看结果

```python
# 获取任务结果
response = requests.get(
    f"http://localhost:8000/api/v1/agents/{agent_id}/tasks/{task['id']}"
)

result = response.json()
print(f"Final status: {result['status']}")
print(f"Output: {result['output']}")
```

## 核心概念速览

### Agent（智能体）
- 自主执行任务的实体
- 具有特定的能力和配置
- 可以访问工具和记忆

### Task（任务）
- Agent 需要完成的工作单元
- 有状态：pending → running → completed/failed
- 包含输入、输出和执行历史

### Memory（记忆）
- 持久化存储 Agent 的知识
- 支持语义搜索和关系图谱
- 跨任务和会话保留信息

### Workflow（工作流）
- 多步骤任务的编排
- 支持条件分支和并行执行
- 用于复杂的自动化场景

## 常用命令速查

```bash
# 运行测试
pytest tests/

# 代码格式化
ruff format backend/

# 代码检查
ruff check backend/

# 查看 API 文档
# 打开浏览器访问 http://localhost:8000/docs

# 查看数据库日志
docker-compose logs postgres

# 停止所有服务
docker-compose down

# 清理所有数据（谨慎！）
docker-compose down -v
```

## 下一步学习路径

### 初级 (30分钟)
1. 阅读 [Agent 基础教程](../../developer/tutorials/tutorials/01-agent-basics.md)
2. 学习如何创建自定义 Agent
3. 探索内置工具和能力

### 中级 (1小时)
1. 学习 [工作流编排](../../developer/tutorials/tutorials/02-workflow-orchestration.md)
2. 实现多步骤自动化任务
3. 配置 Agent 协作

### 高级 (2小时)
1. 深入 [记忆系统](../../developer/tutorials/tutorials/03-memory-system.md)
2. 实现自定义工具和插件
3. 优化性能和成本

### 生产部署 (4小时)
1. 阅读 [部署指南](../deployment/DEPLOYMENT_DETAILED.md)
2. 配置监控和告警
3. 实施安全策略

## 常见问题

**Q: 我可以在没有 Docker 的情况下运行吗？**
A: 可以，但需要手动安装 PostgreSQL 和 Qdrant。详见 [安装指南](./INSTALL.md)。

**Q: 如何使用不同的 LLM 提供商？**
A: 在 `.env` 中配置 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`，然后在 Agent 配置中指定模型。

**Q: 数据会保存在哪里？**
A: 所有数据存储在 PostgreSQL 数据库中。向量嵌入存储在 Qdrant 中。

**Q: 如何重置数据库？**
A: 运行 `docker-compose down -v` 删除所有数据，然后重新初始化。

## 获取帮助

- 📖 完整文档：[docs/README.md](./README.md)
- 🐛 报告问题：[GitHub Issues](https://github.com/x-agent/x-agent-core/issues)
- 💬 讨论：[GitHub Discussions](https://github.com/x-agent/x-agent-core/discussions)
- 📧 联系支持：support@x-agent.dev

## 故障排除

### 端口 8000 已被占用

```bash
# 使用不同的端口
uvicorn backend.app.web:app --port 8001
```

### 数据库连接失败

```bash
# 检查 Docker 容器状态
docker-compose ps

# 查看日志
docker-compose logs postgres

# 重启服务
docker-compose restart postgres
```

### 模块导入错误

```bash
# 重新安装依赖
pip install -e ".[dev]" --force-reinstall
```

### 虚拟环境未激活

```bash
# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate

# 验证激活（应显示 (venv) 前缀）
which python
```

## 下一步

恭喜！你已经成功启动了 X-Agent。现在你可以：

1. 创建更复杂的 Agent
2. 定义自定义工作流
3. 集成外部工具和 API
4. 部署到生产环境

查看 [完整文档](./README.md) 了解更多信息。

---

**提示**：保持这个快速入门指南打开，以便快速参考。如有任何问题，请查看 [FAQ](../support/FAQ.md) 或 [故障排除指南](../support/TROUBLESHOOTING_GUIDE.md)。
