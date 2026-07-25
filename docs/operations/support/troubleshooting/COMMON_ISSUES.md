# X-Agent 故障排除指南

解决 X-Agent 使用中的常见问题。

## 目录

1. [连接问题](#连接问题)
2. [Agent 执行问题](#agent-执行问题)
3. [工作流问题](#工作流问题)
4. [记忆系统问题](#记忆系统问题)
5. [浏览器自动化问题](#浏览器自动化问题)
6. [性能问题](#性能问题)
7. [数据库问题](#数据库问题)

## 连接问题

### 问题：无法连接到 X-Agent 服务

**症状**：
```
ConnectionError: Failed to connect to http://localhost:8000
```

**诊断步骤**：

1. 检查服务是否运行
```bash
# 检查进程
ps aux | grep uvicorn

# 或在 Windows 上
tasklist | findstr uvicorn
```

2. 检查端口是否被占用
```bash
# Linux/macOS
lsof -i :8000

# Windows
netstat -ano | findstr :8000
```

3. 检查防火墙设置
```bash
# Linux
sudo ufw status
sudo ufw allow 8000

# macOS
sudo pfctl -s nat
```

**解决方案**：

```bash
# 重启服务
pkill -f uvicorn
uvicorn backend.app.main:app --reload --port 8000

# 或使用不同的端口
uvicorn backend.app.main:app --reload --port 8001
```

### 问题：数据库连接失败

**症状**：
```
psycopg.OperationalError: could not connect to server
```

**诊断步骤**：

1. 检查数据库是否运行
```bash
docker ps | grep postgres
```

2. 检查数据库连接字符串
```python
# 验证连接字符串
import os
print(os.getenv("DATABASE_URL"))
```

3. 测试数据库连接
```bash
psql postgresql://xagent:xagent@localhost:5432/xagent
```

**解决方案**：

```bash
# 启动数据库
docker-compose up -d postgres

# 初始化数据库
python -m backend.app.core.migration init

# 检查数据库状态
docker-compose logs postgres
```

## Agent 执行问题

### 问题：Agent 执行超时

**症状**：
```
TimeoutError: Agent execution exceeded timeout of 300 seconds
```

**诊断步骤**：

1. 检查任务复杂度
```python
# 查看 Agent 执行日志
logs = await agent.get_logs()
for log in logs:
    print(log)
```

2. 检查工具调用
```python
# 查看工具调用情况
metrics = await agent.get_metrics()
print(f"工具调用次数: {metrics.tool_calls}")
print(f"平均工具调用时间: {metrics.avg_tool_call_time}s")
```

**解决方案**：

```python
# 增加超时时间
agent = Agent(
    name="MyAgent",
    timeout=600  # 10 分钟
)

# 或为特定任务增加超时
result = await agent.execute(
    task="复杂任务",
    timeout=900  # 15 分钟
)

# 或使用流式执行获取中间结果
async for step in agent.execute_stream(task):
    print(f"进度: {step.name}")
```

### 问题：Agent 无法找到合适的工具

**症状**：
```
ToolNotFoundError: No suitable tool found for task
```

**诊断步骤**：

1. 检查可用工具
```python
registry = ToolRegistry()
tools = registry.get_all_tools()
for tool in tools:
    print(f"工具: {tool.name}")
```

2. 检查 Agent 配置的工具
```python
print(f"Agent 工具: {agent.tools}")
```

**解决方案**：

```python
# 添加缺失的工具
agent.add_tool(registry.get_tool("required_tool"))

# 或在创建 Agent 时指定工具
agent = Agent(
    name="MyAgent",
    tools=[
        registry.get_tool("tool1"),
        registry.get_tool("tool2")
    ]
)
```

### 问题：Agent 执行失败并无法恢复

**症状**：
```
ExecutionError: Agent execution failed and recovery failed
```

**诊断步骤**：

1. 查看失败信息
```python
result = await agent.execute(task)
if result.status == "failed":
    print(f"失败原因: {result.error}")
    print(f"失败步骤: {result.failed_step}")
```

2. 查看恢复选项
```python
recovery_options = agent.get_recovery_options()
for option in recovery_options:
    print(f"恢复策略: {option.name}")
    print(f"描述: {option.description}")
```

**解决方案**：

```python
# 配置重试策略
agent.set_retry_policy(
    max_retries=3,
    backoff_factor=2
)

# 或手动恢复
if result.status == "failed":
    recovery_result = await agent.recover(
        strategy="retry_with_different_approach"
    )
```

## 工作流问题

### 问题：工作流节点卡住

**症状**：
```
WorkflowStuckError: Node has been running for too long
```

**诊断步骤**：

1. 查看节点执行状态
```python
run = await workflow.get_run(run_id)
for node_exec in run.node_executions:
    print(f"节点: {node_exec.node_id}")
    print(f"状态: {node_exec.status}")
    print(f"执行时间: {node_exec.duration}s")
```

2. 查看节点日志
```python
logs = await workflow.get_node_logs(run_id, node_id)
for log in logs:
    print(log)
```

**解决方案**：

```python
# 为节点设置合理的超时
node = WorkflowNode(
    id="long_running_task",
    timeout=600  # 10 分钟
)

# 或取消卡住的运行
await workflow.cancel_run(run_id)

# 然后重新执行
new_run = await workflow.execute()
```

### 问题：条件分支不工作

**症状**：
```
工作流总是走同一条分支，不管条件如何
```

**诊断步骤**：

1. 检查条件表达式
```python
# 验证条件
condition = "amount > 1000"
context = {"amount": 500}

# 手动评估条件
result = eval(condition, {"__builtins__": {}}, context)
print(f"条件结果: {result}")
```

2. 查看条件评估日志
```python
debug_info = run.get_debug_info()
print(f"条件评估: {debug_info.conditions}")
```

**解决方案**：

```python
# 检查条件语法
workflow.add_edge(
    from_node="check",
    to_node="branch_a",
    condition="amount > 1000"  # 确保语法正确
)

# 或使用条件函数
def check_amount(context):
    return context.get("amount", 0) > 1000

workflow.add_edge(
    from_node="check",
    to_node="branch_a",
    condition=check_amount
)
```

## 记忆系统问题

### 问题：记忆检索速度慢

**症状**：
```
记忆搜索需要超过 5 秒
```

**诊断步骤**：

1. 检查记忆大小
```python
stats = await memory.get_statistics()
print(f"总记忆数: {stats.total_memories}")
print(f"存储大小: {stats.storage_size} MB")
```

2. 检查索引状态
```python
index_stats = await memory.get_index_statistics()
print(f"索引大小: {index_stats.size}")
print(f"索引健康度: {index_stats.health}")
```

**解决方案**：

```python
# 清理过期记忆
cleaned = await memory.cleanup_expired()
print(f"清理了 {cleaned} 条过期记忆")

# 重建索引
await memory.rebuild_indexes()

# 或使用分页搜索
results = await memory.search(
    query="搜索词",
    top_k=10,
    offset=0
)
```

### 问题：向量搜索结果不准确

**症状**：
```
搜索结果与查询不相关
```

**诊断步骤**：

1. 检查嵌入模型
```python
model = await memory.get_embedding_model()
print(f"当前模型: {model}")
```

2. 检查相似度分数
```python
results = await memory.search(
    query="搜索词",
    top_k=5
)

for result in results:
    print(f"相似度: {result.similarity}")
    print(f"内容: {result.value}")
```

**解决方案**：

```python
# 使用更好的嵌入模型
await memory.set_embedding_model(
    "text-embedding-3-large"
)

# 重新索引
await memory.reindex_vectors()

# 或调整搜索参数
results = await memory.search(
    query="搜索词",
    top_k=20,  # 增加返回结果数
    threshold=0.5  # 降低相似度阈值
)
```

## 浏览器自动化问题

### 问题：页面加载超时

**症状**：
```
TimeoutError: Timeout waiting for page to load
```

**诊断步骤**：

1. 检查网络连接
```bash
ping example.com
```

2. 检查页面加载状态
```python
# 查看页面加载日志
logs = await page.evaluate("() => console.log.toString()")
```

**解决方案**：

```python
# 增加超时时间
await page.goto(
    "https://example.com",
    timeout=60000  # 60 秒
)

# 或使用不同的等待策略
await page.wait_for_load_state("domcontentloaded")

# 或跳过等待
await page.goto("https://example.com", wait_until="commit")
```

### 问题：元素定位失败

**症状**：
```
ElementNotFoundError: Element not found
```

**诊断步骤**：

1. 检查选择器
```python
# 验证选择器
element = await page.query_selector("button.submit")
if not element:
    print("元素不存在")
```

2. 查看页面 HTML
```python
html = await page.content()
print(html)
```

**解决方案**：

```python
# 等待元素出现
await page.wait_for_selector("button.submit", timeout=10000)

# 或使用不同的选择器
element = await page.query_selector("xpath=//button[@class='submit']")

# 或使用文本定位
element = await page.query_selector("text=提交")
```

## 性能问题

### 问题：内存使用过高

**症状**：
```
内存使用超过 80%
```

**诊断步骤**：

1. 检查内存使用
```python
import psutil
process = psutil.Process()
print(f"内存使用: {process.memory_info().rss / 1024 / 1024} MB")
```

2. 检查记忆大小
```python
stats = await memory.get_statistics()
print(f"记忆存储大小: {stats.storage_size} MB")
```

**解决方案**：

```python
# 清理过期记忆
await memory.cleanup_expired()

# 清理缓存
await cache.clear()

# 或限制记忆大小
await memory.set_max_size(1000)  # 最多 1000 条记忆
```

### 问题：CPU 使用率高

**症状**：
```
CPU 使用率超过 80%
```

**诊断步骤**：

1. 检查运行中的任务
```python
tasks = asyncio.all_tasks()
print(f"运行中的任务数: {len(tasks)}")
```

2. 检查性能指标
```python
metrics = await agent.get_metrics()
print(f"LLM 调用次数: {metrics.llm_calls}")
print(f"工具调用次数: {metrics.tool_calls}")
```

**解决方案**：

```python
# 限制并发任务数
semaphore = asyncio.Semaphore(5)

async def limited_execute(task):
    async with semaphore:
        return await agent.execute(task)

# 或使用批量处理
await agent.execute_batch(tasks, batch_size=5)
```

## 数据库问题

### 问题：数据库连接池耗尽

**症状**：
```
sqlalchemy.exc.InvalidRequestError: QueuePool limit exceeded
```

**诊断步骤**：

1. 检查连接数
```python
# 查看数据库连接
SELECT count(*) FROM pg_stat_activity;
```

2. 检查连接池配置
```python
print(f"连接池大小: {db.pool.size()}")
print(f"活跃连接: {db.pool.checkedout()}")
```

**解决方案**：

```python
# 增加连接池大小
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40
)

# 或确保连接被正确关闭
async with db.get_connection() as conn:
    result = await conn.execute(query)
```

## 获取更多帮助

- 📖 查看 [API 文档](http://localhost:8000/docs)
- 🐛 报告问题：https://github.com/x-agent/x-agent-core/issues
- 💬 社区讨论：https://github.com/x-agent/x-agent-core/discussions
- 📧 联系支持：support@x-agent.dev

## 下一步

- 阅读 [FAQ](../faq/README.md)
- 阅读 [最佳实践](../../../developer/best-practices/best-practices/README.md)
- 探索 [示例代码库](../../examples/)
