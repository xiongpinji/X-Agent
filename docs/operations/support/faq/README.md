# X-Agent 常见问题解答 (FAQ)

## 一般问题

### Q1: X-Agent 是什么？

**A:** X-Agent 是一个企业级的 AI 代理执行框架，提供完整的 Agent 编排、工作流管理、记忆系统、浏览器自动化等功能。它帮助开发者快速构建智能自动化系统。

### Q2: X-Agent 支持哪些 LLM？

**A:** X-Agent 支持多个 LLM 提供商：
- OpenAI (GPT-4, GPT-3.5-turbo)
- Anthropic (Claude)
- DeepSeek
- 本地模型 (通过 Ollama)

你可以在配置中指定默认模型，也可以为不同的任务使用不同的模型。

### Q3: X-Agent 需要什么硬件要求？

**A:** 最低要求：
- CPU: 2 核
- 内存: 4 GB
- 存储: 10 GB

推荐配置：
- CPU: 4+ 核
- 内存: 8+ GB
- 存储: 50+ GB

### Q4: X-Agent 支持多租户吗？

**A:** 是的，X-Agent 内置了多租户支持，包括：
- 租户隔离
- 基于角色的访问控制 (RBAC)
- 资源配额管理
- 审计日志

## 安装和配置

### Q5: 如何安装 X-Agent？

**A:** 参考 [快速开始指南](../../../developer/tutorials/tutorials/GETTING_STARTED.md)。基本步骤：

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Q6: 如何配置 LLM API 密钥？

**A:** 编辑 `.env` 文件：

```env
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
DEEPSEEK_API_KEY=sk-your-key
```

或设置环境变量：

```bash
export OPENAI_API_KEY=sk-your-key
```

### Q7: 如何使用本地数据库而不是 PostgreSQL？

**A:** X-Agent 目前主要支持 PostgreSQL。如果需要使用其他数据库，可以：

1. 修改 `DATABASE_URL` 环境变量
2. 实现相应的数据库适配器
3. 或使用 SQLite 进行开发测试

```env
# SQLite (仅用于开发)
DATABASE_URL=sqlite:///./xagent.db
```

### Q8: 如何在 Docker 中运行 X-Agent？

**A:** 使用 Docker Compose：

```bash
docker-compose up -d
```

或构建自定义镜像：

```bash
docker build -t x-agent:latest .
docker run -p 8000:8000 x-agent:latest
```

## Agent 相关

### Q9: 如何创建自定义 Agent？

**A:** 参考 [Agent 使用教程](../../../developer/tutorials/tutorials/01-agent-basics.md)。基本示例：

```python
from backend.app.core.agent import Agent

agent = Agent(
    name="MyAgent",
    description="我的自定义 Agent",
    tools=["tool1", "tool2"]
)

result = await agent.execute("任务描述")
```

### Q10: 如何为 Agent 添加自定义工具？

**A:** 创建工具类并注册：

```python
from backend.app.core.tool_schema import Tool

class MyTool:
    @staticmethod
    def get_definition() -> Tool:
        return Tool(
            name="my_tool",
            description="我的工具",
            parameters=[...]
        )
    
    @staticmethod
    async def execute(**kwargs):
        # 实现工具逻辑
        pass

# 注册工具
registry.register(MyTool)
```

### Q11: Agent 可以调用其他 Agent 吗？

**A:** 是的，可以使用多 Agent 协作：

```python
from backend.app.core.collaboration import AgentCollaborator

collaborator = AgentCollaborator()
collaborator.add_agent(agent1)
collaborator.add_agent(agent2)

result = await collaborator.execute(task)
```

### Q12: 如何处理 Agent 执行失败？

**A:** 使用错误处理和恢复机制：

```python
try:
    result = await agent.execute(task)
except Exception as e:
    # 获取恢复选项
    options = agent.get_recovery_options()
    
    # 选择恢复策略
    result = await agent.recover(strategy="retry")
```

## 工作流相关

### Q13: 工作流和 Agent 有什么区别？

**A:** 
- **Agent**: 智能执行单元，可以理解任务、制定计划、调用工具
- **Workflow**: 预定义的任务流程，节点按顺序或条件执行

工作流更适合结构化的业务流程，Agent 更适合需要智能决策的任务。

### Q14: 如何定义复杂的工作流？

**A:** 使用 YAML 或 Python DSL：

```yaml
name: ComplexWorkflow
nodes:
  - id: step1
    type: task
    action: fetch_data
  - id: decision
    type: decision
    condition: "data.length > 0"
  - id: process
    type: task
    action: process_data
edges:
  - from: step1
    to: decision
  - from: decision
    to: process
    condition: "true"
```

### Q15: 工作流支持循环吗？

**A:** 是的，支持多种循环方式：

```python
# 使用 Loop 节点
loop_node = WorkflowNode(
    id="process_items",
    type=NodeType.LOOP,
    loop_condition="items.length > 0"
)

# 或使用条件分支实现循环
workflow.add_edge(
    from_node="process",
    to_node="check",
    condition="has_more_items"
)

workflow.add_edge(
    from_node="check",
    to_node="process",
    condition="true"
)
```

## 记忆系统相关

### Q16: 记忆系统支持哪些存储后端？

**A:** X-Agent 支持多个存储后端：
- PostgreSQL (推荐用于生产)
- Qdrant (向量存储)
- Neo4j (图谱存储)
- Redis (缓存)
- JSONL (本地文件)

### Q17: 如何使用向量搜索？

**A:** 参考 [记忆系统教程](../../../developer/tutorials/tutorials/03-memory-system.md)：

```python
# 存储向量记忆
await memory.store(
    key="doc1",
    value="文档内容",
    memory_type=MemoryType.VECTOR
)

# 搜索
results = await memory.search(
    query="搜索词",
    top_k=5
)
```

### Q18: 如何清理过期的记忆？

**A:** 使用清理功能：

```python
# 自动清理过期记忆
cleaned = await memory.cleanup_expired()

# 或手动清理
await memory.clear(memory_type=MemoryType.SHORT_TERM)
```

### Q19: 记忆系统的性能如何？

**A:** 性能取决于存储后端和数据量：
- 关键词搜索: < 100ms (< 1M 条记忆)
- 向量搜索: < 500ms (< 1M 条记忆)
- 图谱查询: < 200ms (< 100K 个节点)

可以通过索引优化和缓存提高性能。

## 浏览器自动化相关

### Q20: 浏览器自动化支持哪些浏览器？

**A:** 支持以下浏览器：
- Chromium (推荐)
- Firefox
- WebKit

### Q21: 如何处理动态加载的内容？

**A:** 使用等待策略：

```python
# 等待特定元素
await page.wait_for_selector("div.content")

# 等待网络空闲
await page.wait_for_load_state("networkidle")

# 等待特定条件
await page.wait_for_function(
    "() => document.querySelectorAll('div.item').length > 0"
)
```

### Q22: 如何处理登录和认证？

**A:** 使用 Cookie 或会话管理：

```python
# 保存 Cookie
cookies = await browser.context.cookies()

# 恢复 Cookie
await browser.context.add_cookies(cookies)

# 或使用认证令牌
await page.set_extra_http_headers({
    "Authorization": "Bearer token"
})
```

### Q23: 浏览器自动化支持 JavaScript 吗？

**A:** 是的，完全支持：

```python
# 执行 JavaScript
result = await page.evaluate("() => 1 + 1")

# 获取页面数据
data = await page.evaluate("""
    () => {
        return {
            title: document.title,
            url: window.location.href
        };
    }
""")
```

## 性能和优化

### Q24: 如何提高 Agent 执行速度？

**A:** 几个优化技巧：

1. 使用缓存
```python
cached = await memory.retrieve(key)
if cached:
    return cached
```

2. 使用更快的模型
```python
agent.set_model("gpt-3.5-turbo")
```

3. 并行执行
```python
results = await asyncio.gather(*tasks)
```

### Q25: 如何监控 X-Agent 的性能？

**A:** 使用内置的监控工具：

```python
from backend.app.core.monitoring import PerformanceMonitor

monitor = PerformanceMonitor()
metrics = monitor.get_metrics()

print(f"平均执行时间: {metrics.avg_duration}s")
print(f"成功率: {metrics.success_rate}%")
```

### Q26: 如何优化数据库查询？

**A:** 使用索引和查询优化：

```python
# 创建索引
CREATE INDEX idx_user_id ON users(id);

# 使用 EXPLAIN 分析查询
EXPLAIN SELECT * FROM users WHERE id = 1;
```

## 安全相关

### Q27: X-Agent 如何保护敏感信息？

**A:** X-Agent 提供多层安全保护：

1. 加密存储
2. 访问控制 (RBAC)
3. 审计日志
4. 输入验证

### Q28: 如何实现审批工作流？

**A:** 使用审批管理器：

```python
from backend.app.core.approvals import ApprovalManager

approval_manager = ApprovalManager()
approval_manager.add_approval_rule(
    operation="delete_data",
    approvers=["admin@company.com"]
)

agent.set_approval_manager(approval_manager)
```

### Q29: 如何限制 Agent 的权限？

**A:** 使用策略引擎：

```python
from backend.app.core.policy import PolicyEngine

policy_engine = PolicyEngine()
policy_engine.add_policy(
    name="restrict_delete",
    rules=[{"tool": "delete_data", "action": "deny"}]
)

agent.set_policy_engine(policy_engine)
```

## 部署相关

### Q30: 如何在生产环境中部署 X-Agent？

**A:** 参考部署指南：

1. 使用 Docker 容器化
2. 配置反向代理 (Nginx)
3. 设置 SSL/TLS
4. 配置监控和告警
5. 设置备份和恢复

### Q31: 如何扩展 X-Agent？

**A:** 支持水平扩展：

1. 使用负载均衡器
2. 配置多个 X-Agent 实例
3. 使用共享数据库
4. 使用消息队列 (Redis)

### Q32: 如何更新 X-Agent？

**A:** 遵循更新流程：

```bash
# 备份数据
pg_dump xagent > backup.sql

# 更新代码
git pull origin main

# 运行迁移
python -m backend.app.core.migration upgrade

# 重启服务
systemctl restart xagent
```

## 获取更多帮助

- 📖 [完整文档](../README.md)
- 🐛 [报告问题](https://github.com/x-agent/x-agent-core/issues)
- 💬 [社区讨论](https://github.com/x-agent/x-agent-core/discussions)
- 📧 [联系支持](mailto:support@x-agent.dev)

## 下一步

- 阅读 [最佳实践](../../../developer/best-practices/best-practices/README.md)
- 阅读 [故障排除](../troubleshooting/COMMON_ISSUES.md)
- 探索 [示例代码库](../../examples/)
