# X-Agent 第三阶段功能 - API文档和使用指南

## 目录
1. [记忆融合系统](#记忆融合系统)
2. [Agent协作系统](#agent协作系统)
3. [浏览器自动化增强](#浏览器自动化增强)
4. [修复循环系统](#修复循环系统)
5. [集成示例](#集成示例)

---

## 记忆融合系统

### 概述
记忆融合系统提供高级的记忆管理功能，包括embedding生成、去重、压缩和关联发现。

### 基本使用

```python
from backend.app.core.memory_fusion import Memory, MemoryFusion

# 初始化
fusion = MemoryFusion(
    similarity_threshold=0.85,
    compression_ratio=0.7,
)

# 创建记忆
memory = Memory(
    id="mem_001",
    content="Python is a powerful programming language",
    metadata={"source": "documentation", "category": "programming"}
)

# 添加记忆
await fusion.add_memory(memory)
```

### API 参考

#### MemoryFusion 类

##### `__init__(embedding_model, similarity_threshold, compression_ratio)`
初始化记忆融合系统。

**参数**:
- `embedding_model` (EmbeddingModel, optional): Embedding模型，默认使用DeterministicEmbeddingModel
- `similarity_threshold` (float): 相似度阈值，默认0.85
- `compression_ratio` (float): 压缩比例，默认0.7

**示例**:
```python
from backend.app.core.embeddings import OpenAIEmbeddingModel

fusion = MemoryFusion(
    embedding_model=OpenAIEmbeddingModel(api_key="your_key"),
    similarity_threshold=0.9,
    compression_ratio=0.6,
)
```

##### `async add_memory(memory: Memory) -> Memory`
添加记忆并生成embedding。

**参数**:
- `memory` (Memory): 要添加的记忆

**返回**: 添加后的记忆对象

**示例**:
```python
memory = Memory(id="mem_001", content="Test content")
result = await fusion.add_memory(memory)
print(f"Embedding dimension: {len(result.embedding)}")
```

##### `async deduplicate(memories: List[Memory]) -> List[Memory]`
去除重复的记忆。

**参数**:
- `memories` (List[Memory]): 记忆列表

**返回**: 去重后的记忆列表

**示例**:
```python
memories = [
    Memory(id="mem_1", content="The quick brown fox"),
    Memory(id="mem_2", content="The quick brown fox jumps"),
    Memory(id="mem_3", content="Completely different"),
]

unique = await fusion.deduplicate(memories)
print(f"Original: {len(memories)}, Unique: {len(unique)}")
```

##### `async compress_memories(memories: List[Memory]) -> List[Memory]`
压缩记忆集合。

**参数**:
- `memories` (List[Memory]): 记忆列表

**返回**: 压缩后的记忆列表

**示例**:
```python
compressed = await fusion.compress_memories(memories)
print(f"Compression ratio: {len(compressed) / len(memories)}")
```

##### `async associate_memories(memory: Memory) -> List[Memory]`
发现相关的记忆。

**参数**:
- `memory` (Memory): 查询记忆

**返回**: 相关记忆列表

**示例**:
```python
query = Memory(id="query", content="Python programming")
related = await fusion.associate_memories(query)
for mem in related:
    print(f"Related: {mem.content}")
```

##### `get_memory_stats() -> Dict[str, Any]`
获取记忆统计信息。

**返回**: 统计信息字典

**示例**:
```python
stats = fusion.get_memory_stats()
print(f"Total memories: {stats['total_memories']}")
print(f"Average importance: {stats['avg_importance']}")
```

---

## Agent协作系统

### 概述
Agent协作系统提供多Agent通信、任务分配和负载均衡功能。

### 基本使用

```python
from backend.app.core.agent_collaboration import (
    AgentCollaboration,
    AgentMessage,
    MessageType,
)

# 初始化
collab = AgentCollaboration(redis_url="redis://localhost")
await collab.connect()

# 注册Agent
agent1 = await collab.register_agent("agent_1", capacity=10)
agent2 = await collab.register_agent("agent_2", capacity=10)

# 发送消息
message = AgentMessage(
    from_agent="agent_1",
    to_agent="agent_2",
    message_type=MessageType.TASK_REQUEST,
    payload={"task": "process_data", "data": [1, 2, 3]},
    priority=1,
)

await collab.send_message(message)

# 接收消息
messages = await collab.receive_messages("agent_2")
for msg in messages:
    print(f"Received: {msg.payload}")
    await collab.acknowledge_message("agent_2", msg.id)
```

### API 参考

#### AgentCollaboration 类

##### `__init__(redis_url, message_queue_prefix, agent_registry_key, heartbeat_timeout)`
初始化Agent协作系统。

**参数**:
- `redis_url` (str): Redis连接URL，默认"redis://localhost"
- `message_queue_prefix` (str): 消息队列前缀，默认"agent:messages"
- `agent_registry_key` (str): Agent注册表键，默认"agent:registry"
- `heartbeat_timeout` (float): 心跳超时时间（秒），默认30.0

##### `async connect() -> None`
连接到Redis。

##### `async disconnect() -> None`
断开Redis连接。

##### `async register_agent(agent_id: str, capacity: int) -> AgentInfo`
注册一个Agent。

**参数**:
- `agent_id` (str): Agent唯一标识
- `capacity` (int): 最大并发任务数

**返回**: Agent信息对象

**示例**:
```python
agent = await collab.register_agent("worker_1", capacity=20)
print(f"Agent status: {agent.status}")
```

##### `async send_message(message: AgentMessage) -> bool`
发送消息。

**参数**:
- `message` (AgentMessage): 要发送的消息

**返回**: 是否发送成功

##### `async receive_messages(agent_id: str, limit: int) -> List[AgentMessage]`
接收消息。

**参数**:
- `agent_id` (str): Agent标识
- `limit` (int): 最多接收消息数，默认10

**返回**: 消息列表

##### `async assign_task(task_payload: Dict, priority: int) -> str | None`
分配任务到最优Agent。

**参数**:
- `task_payload` (Dict): 任务负载
- `priority` (int): 优先级，默认0

**返回**: 分配到的Agent ID，或None

**示例**:
```python
agent_id = await collab.assign_task(
    {"operation": "analyze", "data": data},
    priority=2,
)
if agent_id:
    print(f"Task assigned to {agent_id}")
```

##### `async update_agent_status(agent_id, status, load, active_tasks)`
更新Agent状态。

**参数**:
- `agent_id` (str): Agent标识
- `status` (AgentStatus): Agent状态
- `load` (float): 当前负载（0-1）
- `active_tasks` (int): 活跃任务数

##### `async get_available_agents() -> List[AgentInfo]`
获取可用Agent列表。

**返回**: 按可用性排序的Agent列表

##### `async get_agent_stats() -> Dict[str, Any]`
获取Agent统计信息。

**返回**: 统计信息字典

---

## 浏览器自动化增强

### 概述
浏览器自动化增强提供AI元素检测、智能等待和错误恢复功能。

### 基本使用

```python
from backend.app.services.browser.enhanced_automation import (
    EnhancedBrowserAutomation,
    ElementDetectionMethod,
    WaitStrategy,
)
from playwright.async_api import async_playwright

# 初始化
automation = EnhancedBrowserAutomation(
    default_wait_strategy=WaitStrategy.ADAPTIVE,
    operation_timeout=30.0,
)

# 创建浏览器会话
async with async_playwright() as p:
    browser = await p.chromium.launch()
    context = await browser.new_context()
    page = await context.new_page()
    
    session = await automation.create_session(
        "session_1",
        browser,
        context,
        page,
    )
    
    # 导航到页面
    await page.goto("https://example.com")
    
    # 智能等待
    await automation.smart_wait("session_1", WaitStrategy.NETWORK_IDLE)
    
    # 查找元素
    element = await automation.find_element(
        "session_1",
        "Submit button",
        ElementDetectionMethod.AI_VISION,
    )
    
    # 点击元素
    if element:
        await automation.click_element("session_1", element)
    
    # 关闭会话
    await automation.close_session("session_1")
```

### API 参考

#### EnhancedBrowserAutomation 类

##### `__init__(ai_detector, default_wait_strategy, operation_timeout)`
初始化浏览器自动化。

**参数**:
- `ai_detector` (Any, optional): AI元素检测器
- `default_wait_strategy` (WaitStrategy): 默认等待策略
- `operation_timeout` (float): 操作超时时间（秒）

##### `async create_session(session_id, browser, context, page) -> BrowserSession`
创建浏览器会话。

##### `async close_session(session_id: str) -> bool`
关闭浏览器会话。

##### `async smart_wait(session_id, strategy, timeout, condition) -> bool`
智能等待。

**参数**:
- `session_id` (str): 会话ID
- `strategy` (WaitStrategy, optional): 等待策略
- `timeout` (float, optional): 超时时间
- `condition` (Callable, optional): 自定义条件

**示例**:
```python
# 等待网络空闲
await automation.smart_wait("session_1", WaitStrategy.NETWORK_IDLE)

# 自定义条件
async def custom_condition(page):
    return await page.evaluate("document.querySelectorAll('.loaded').length > 0")

await automation.smart_wait("session_1", WaitStrategy.CUSTOM, condition=custom_condition)
```

##### `async find_element(session_id, description, method) -> ElementInfo | None`
查找元素。

**参数**:
- `session_id` (str): 会话ID
- `description` (str): 元素描述
- `method` (ElementDetectionMethod): 检测方法

**返回**: 元素信息或None

##### `async click_element(session_id, element, retry_count) -> bool`
点击元素。

**参数**:
- `session_id` (str): 会话ID
- `element` (ElementInfo): 元素信息
- `retry_count` (int): 重试次数，默认3

**返回**: 是否成功

##### `async fill_input(session_id, element, value, clear_first) -> bool`
填充输入框。

**参数**:
- `session_id` (str): 会话ID
- `element` (ElementInfo): 元素信息
- `value` (str): 要填充的值
- `clear_first` (bool): 是否先清空，默认True

**返回**: 是否成功

##### `async extract_text(session_id, selector) -> str | None`
提取文本。

**参数**:
- `session_id` (str): 会话ID
- `selector` (str): CSS选择器

**返回**: 提取的文本或None

##### `async take_screenshot(session_id, path) -> bytes | None`
截图。

**参数**:
- `session_id` (str): 会话ID
- `path` (str, optional): 保存路径

**返回**: 截图字节或None

---

## 修复循环系统

### 概述
修复循环系统提供失败分析、修复建议和学习机制。

### 基本使用

```python
from backend.app.core.advanced_repair_loop import AdvancedRepairLoop

# 初始化
repair = AdvancedRepairLoop(
    max_retries=3,
    learning_enabled=True,
)

# 分析失败
try:
    result = await some_operation()
except Exception as e:
    failure = await repair.analyze_failure(e, {"operation": "test"})
    
    # 获取修复建议
    suggestion = await repair.suggest_repair(failure)
    print(f"Strategy: {suggestion.strategy}")
    print(f"Confidence: {suggestion.confidence}")
    
    # 执行修复
    success, result = await repair.execute_repair(
        failure,
        suggestion,
        some_operation,
    )
    
    if success:
        print(f"Repair successful: {result}")
    else:
        print("Repair failed")
```

### API 参考

#### AdvancedRepairLoop 类

##### `__init__(verification_engine, max_retries, learning_enabled)`
初始化修复循环。

**参数**:
- `verification_engine` (VerificationEngine, optional): 验证引擎
- `max_retries` (int): 最大重试次数，默认3
- `learning_enabled` (bool): 是否启用学习，默认True

##### `async analyze_failure(error, context) -> FailureRecord`
分析失败。

**参数**:
- `error` (Exception): 异常对象
- `context` (Dict, optional): 上下文信息

**返回**: 失败记录

##### `async suggest_repair(failure) -> RepairSuggestion`
建议修复策略。

**参数**:
- `failure` (FailureRecord): 失败记录

**返回**: 修复建议

**示例**:
```python
failure = await repair.analyze_failure(TimeoutError("Operation timed out"))
suggestion = await repair.suggest_repair(failure)

print(f"Strategy: {suggestion.strategy}")
print(f"Reason: {suggestion.reason}")
print(f"Follow-up: {suggestion.follow_up}")
```

##### `async execute_repair(failure, suggestion, operation, *args, **kwargs) -> Tuple[bool, Any]`
执行修复。

**参数**:
- `failure` (FailureRecord): 失败记录
- `suggestion` (RepairSuggestion): 修复建议
- `operation` (Callable): 要执行的操作
- `*args`: 操作参数
- `**kwargs`: 操作关键字参数

**返回**: (是否成功, 结果)

##### `register_compensation_handler(action, handler)`
注册补偿处理器。

**参数**:
- `action` (str): 操作类型
- `handler` (Callable): 处理器函数

**示例**:
```python
async def cleanup_handler(action):
    print(f"Cleaning up: {action}")

repair.register_compensation_handler("cleanup", cleanup_handler)
```

##### `get_learning_stats() -> Dict[str, Any]`
获取学习统计。

**返回**: 统计信息字典

---

## 集成示例

### 示例1: 完整的记忆管理工作流

```python
async def memory_workflow():
    from backend.app.core.memory_fusion import Memory, MemoryFusion
    
    fusion = MemoryFusion()
    
    # 添加多个记忆
    memories = []
    for i in range(10):
        memory = Memory(
            id=f"mem_{i}",
            content=f"Important information {i}",
            importance=0.5 + i * 0.05,
        )
        result = await fusion.add_memory(memory)
        memories.append(result)
    
    # 去重
    unique = await fusion.deduplicate(memories)
    print(f"Deduplicated: {len(memories)} -> {len(unique)}")
    
    # 压缩
    compressed = await fusion.compress_memories(unique)
    print(f"Compressed: {len(unique)} -> {len(compressed)}")
    
    # 获取统计
    stats = fusion.get_memory_stats()
    print(f"Stats: {stats}")
```

### 示例2: 多Agent任务分配

```python
async def agent_workflow():
    from backend.app.core.agent_collaboration import (
        AgentCollaboration,
        AgentMessage,
        MessageType,
    )
    
    collab = AgentCollaboration()
    await collab.connect()
    
    # 注册多个Agent
    agents = []
    for i in range(3):
        agent = await collab.register_agent(f"worker_{i}", capacity=10)
        agents.append(agent)
    
    # 分配任务
    for i in range(10):
        agent_id = await collab.assign_task(
            {"task_id": i, "data": f"data_{i}"},
            priority=i % 3,
        )
        print(f"Task {i} assigned to {agent_id}")
    
    # 获取统计
    stats = await collab.get_agent_stats()
    print(f"Agent stats: {stats}")
    
    await collab.disconnect()
```

### 示例3: 浏览器自动化与错误恢复

```python
async def browser_workflow():
    from backend.app.services.browser.enhanced_automation import (
        EnhancedBrowserAutomation,
        ElementDetectionMethod,
        WaitStrategy,
    )
    from backend.app.core.advanced_repair_loop import AdvancedRepairLoop
    from playwright.async_api import async_playwright
    
    automation = EnhancedBrowserAutomation()
    repair = AdvancedRepairLoop()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        
        session = await automation.create_session("session_1", browser, context, page)
        
        try:
            # 导航
            await page.goto("https://example.com")
            
            # 智能等待
            await automation.smart_wait("session_1", WaitStrategy.ADAPTIVE)
            
            # 查找并点击元素
            element = await automation.find_element(
                "session_1",
                "Login button",
                ElementDetectionMethod.CSS_SELECTOR,
            )
            
            if element:
                await automation.click_element("session_1", element)
        
        except Exception as e:
            # 分析失败
            failure = await repair.analyze_failure(e)
            suggestion = await repair.suggest_repair(failure)
            
            # 执行修复
            success, _ = await repair.execute_repair(
                failure,
                suggestion,
                page.reload,
            )
        
        finally:
            await automation.close_session("session_1")
```

---

## 最佳实践

### 1. 记忆管理
- 定期进行去重和压缩
- 设置合理的相似度阈值
- 监控记忆统计信息

### 2. Agent协作
- 合理设置Agent容量
- 监控Agent状态和负载
- 实现心跳检测

### 3. 浏览器自动化
- 使用适当的等待策略
- 实现错误恢复机制
- 定期清理会话

### 4. 修复循环
- 启用学习机制
- 注册补偿处理器
- 监控修复统计

---

## 故障排除

### 问题1: Redis连接失败
**解决方案**: 确保Redis服务正在运行
```bash
redis-server --port 6379
```

### 问题2: 浏览器操作超时
**解决方案**: 增加超时时间或使用自适应等待
```python
automation = EnhancedBrowserAutomation(operation_timeout=60.0)
```

### 问题3: 记忆去重效果不佳
**解决方案**: 调整相似度阈值
```python
fusion = MemoryFusion(similarity_threshold=0.9)
```

---

**文档版本**: 1.0  
**最后更新**: 2026-05-27
