# X-Agent 并行执行引擎架构设计

## 1. 概述

X-Agent当前的工具调用和Agent协作都是串行的，导致与Claude Code有40%的性能差距。本文档设计一个完整的并行执行引擎，支持：

- **工具并行执行**：多个独立工具调用同时执行
- **Agent并行协作**：多个Agent并行处理不同子任务
- **智能调度**：基于任务依赖图的拓扑排序调度
- **通信协调**：Agent间的消息传递和状态同步
- **容错恢复**：超时、失败、取消的优雅处理

## 2. 当前串行执行流程分析

### 2.1 工具执行流程（串行）

```
Task Planning
    ↓
Tool Decision (LLM)
    ↓
Tool Execution (Sequential)
    ├─ Tool 1 (wait)
    ├─ Tool 2 (wait)
    └─ Tool N (wait)
    ↓
Result Aggregation
    ↓
Observation & Reflection
```

**问题**：
- 每个工具必须等待前一个完成
- 总时间 = T1 + T2 + ... + TN
- 无法利用多核/分布式能力

### 2.2 Agent协作流程（串行）

```
Main Agent
    ├─ Sub-task 1 (Sequential)
    ├─ Sub-task 2 (Sequential)
    └─ Sub-task N (Sequential)
```

**问题**：
- 子任务必须顺序执行
- 无法并行处理独立的子任务
- Agent资源利用率低

## 3. 并行执行架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Loop (Main)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Parallel Execution Orchestrator                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Task Dependency Analyzer (DAG Construction)         │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Execution Scheduler (Topological Sort)              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         ↓                    ↓                    ↓
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Tool Executor 1  │ │ Tool Executor 2  │ │ Tool Executor N  │
│ (asyncio)        │ │ (asyncio)        │ │ (asyncio)        │
└──────────────────┘ └──────────────────┘ └──────────────────┘
         ↓                    ↓                    ↓
┌─────────────────────────────────────────────────────────────┐
│              Result Aggregator & Merger                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Dependency-Aware Result Collection                  │   │
│  │  Conflict Resolution & Voting                        │   │
│  │  State Synchronization                               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Agent Communication Bus                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Message Queue (Redis Streams)                       │   │
│  │  Pub/Sub (Topic-based)                               │   │
│  │  RPC (Agent Method Calls)                            │   │
│  │  Event Bus (Event Publishing)                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 任务依赖图（DAG）设计

#### 3.2.1 DAG节点

```python
@dataclass
class DAGNode:
    """DAG中的任务节点"""
    node_id: str                    # 唯一标识
    task_type: str                  # "tool" | "agent" | "decision"
    task_name: str                  # 工具名或Agent名
    arguments: dict[str, Any]       # 任务参数
    dependencies: list[str]         # 依赖的节点ID列表
    timeout_seconds: float = 30.0   # 超时时间
    retry_count: int = 0            # 重试次数
    priority: int = 0               # 优先级（高优先级先执行）
    metadata: dict[str, Any] = None # 元数据
```

#### 3.2.2 DAG构建算法

```
Input: Tool calls list
Output: DAG with dependency relationships

1. 分析工具参数依赖
   - 检查参数是否引用其他工具的输出
   - 例如：tool2(input=tool1.output) → tool1 → tool2

2. 分析工具间的隐式依赖
   - 文件系统依赖：write → read
   - 状态依赖：set_state → get_state
   - 资源依赖：acquire_resource → use_resource

3. 构建依赖图
   - 节点：每个工具调用
   - 边：依赖关系
   - 权重：优先级

4. 检测循环依赖
   - 使用DFS检测环
   - 如果存在环，抛出异常
```

### 3.3 并行调度策略

#### 3.3.1 拓扑排序调度

```
Input: DAG
Output: Execution layers (list of lists)

Algorithm:
1. 计算每个节点的入度（in-degree）
2. 将入度为0的节点放入第一层
3. 移除这些节点和它们的边
4. 重复步骤2-3直到所有节点处理完毕

Result:
Layer 0: [Task1, Task2, Task3]  (可并行执行)
Layer 1: [Task4, Task5]          (可并行执行)
Layer 2: [Task6]                 (依赖Layer1)
```

#### 3.3.2 优先级队列调度

```
Priority = base_priority + urgency_factor + dependency_depth

- base_priority: 用户指定的优先级
- urgency_factor: 依赖该任务的任务数量
- dependency_depth: 任务在DAG中的深度

高优先级任务优先执行
```

#### 3.3.3 资源感知调度

```
Available Resources:
- CPU cores: 8
- Memory: 16GB
- Concurrent connections: 100

Task Resource Requirements:
- CPU: 1-4 cores
- Memory: 100MB-2GB
- Connections: 1-10

Scheduler:
- 检查可用资源
- 只调度满足资源要求的任务
- 动态调整并发度
```

### 3.4 Agent间通信机制

#### 3.4.1 消息队列（Redis Streams）

```
Stream: agent:messages:{agent_id}

Message Format:
{
  "message_id": "msg_123",
  "from_agent": "agent_1",
  "to_agent": "agent_2",
  "message_type": "direct|broadcast|topic",
  "topic": "task_completion",
  "content": {...},
  "priority": "high",
  "timestamp": "2026-05-28T10:00:00Z",
  "correlation_id": "corr_123",
  "reply_to": "msg_122",
  "ttl_seconds": 3600
}

Operations:
- XADD: 发送消息
- XREAD: 接收消息
- XRANGE: 查询消息历史
- XTRIM: 清理过期消息
```

#### 3.4.2 发布/订阅机制

```
Topics:
- task:completed
- task:failed
- agent:ready
- agent:busy
- state:updated
- error:occurred

Subscribers:
- Agent可订阅多个topic
- 接收相关事件通知
- 支持topic通配符（task:*）
```

#### 3.4.3 RPC调用

```
RPC Request:
{
  "rpc_id": "rpc_123",
  "method": "agent_2.execute_subtask",
  "params": {...},
  "timeout_seconds": 30
}

RPC Response:
{
  "rpc_id": "rpc_123",
  "result": {...},
  "error": null,
  "duration_ms": 1234
}

Implementation:
- 基于消息队列的RPC
- 自动超时处理
- 重试机制
```

#### 3.4.4 事件总线

```
Event Types:
- TaskStarted
- TaskCompleted
- TaskFailed
- TaskCancelled
- StateChanged
- ErrorOccurred

Event Handler:
- 异步处理事件
- 支持事件链（Event Chain）
- 支持事件聚合（Event Aggregation）
```

### 3.5 工具并行执行流程

```
Input: Tool calls list

1. 依赖分析
   ├─ 构建DAG
   ├─ 检测循环依赖
   └─ 计算执行层

2. 并行调度
   ├─ 拓扑排序
   ├─ 优先级排序
   └─ 资源分配

3. 并行执行
   ├─ Layer 0: 并行执行所有独立任务
   │  ├─ Tool 1 (asyncio task)
   │  ├─ Tool 2 (asyncio task)
   │  └─ Tool N (asyncio task)
   ├─ 等待所有Layer 0任务完成
   ├─ Layer 1: 并行执行依赖Layer 0的任务
   │  ├─ Tool 4 (asyncio task)
   │  └─ Tool 5 (asyncio task)
   └─ 继续...

4. 结果聚合
   ├─ 按依赖顺序收集结果
   ├─ 处理失败和超时
   ├─ 冲突解决
   └─ 返回聚合结果

5. 错误处理
   ├─ 超时：取消任务，返回超时错误
   ├─ 失败：根据retry_count重试
   ├─ 取消：清理资源，返回取消状态
   └─ 部分失败：根据allow_partial_failure决定
```

### 3.6 Agent并行协作流程

```
Main Agent
    ├─ 分析任务，识别可并行的子任务
    ├─ 创建子Agent池
    ├─ 分配子任务给子Agent
    │
    ├─ 子Agent 1: 处理子任务1
    ├─ 子Agent 2: 处理子任务2
    └─ 子Agent N: 处理子任务N
    │
    ├─ 通过通信总线协调
    │  ├─ 状态同步
    │  ├─ 结果共享
    │  └─ 冲突解决
    │
    └─ 等待所有子Agent完成
        ├─ 收集结果
        ├─ 合并结果
        └─ 返回最终结果
```

### 3.7 Agent协作模式

#### 3.7.1 主从模式（Master-Slave）

```
Master Agent
    ├─ 分析任务
    ├─ 创建执行计划
    ├─ 分配子任务
    │
    ├─ Slave Agent 1 (执行子任务1)
    ├─ Slave Agent 2 (执行子任务2)
    └─ Slave Agent N (执行子任务N)
    │
    └─ 收集结果，合并输出

特点：
- 中央控制
- 简单易实现
- 主Agent是单点故障
```

#### 3.7.2 对等模式（Peer-to-Peer）

```
Agent 1 ←→ Agent 2
  ↓         ↓
Agent 3 ←→ Agent 4

特点：
- 分布式控制
- 自主协商
- 更复杂但更灵活
```

#### 3.7.3 层级模式（Hierarchical）

```
Level 0: Main Agent
    ├─ Level 1: Coordinator Agent 1
    │   ├─ Level 2: Worker Agent 1
    │   ├─ Level 2: Worker Agent 2
    │   └─ Level 2: Worker Agent 3
    │
    └─ Level 1: Coordinator Agent 2
        ├─ Level 2: Worker Agent 4
        └─ Level 2: Worker Agent 5

特点：
- 分层控制
- 可扩展性好
- 适合大规模任务
```

## 4. 状态同步与冲突解决

### 4.1 共享状态管理

```
Shared State:
{
  "task_id": "task_123",
  "state": {
    "file_system": {...},
    "variables": {...},
    "memory": {...},
    "browser_state": {...}
  },
  "version": 42,
  "last_updated": "2026-05-28T10:00:00Z",
  "lock": {
    "owner": "agent_1",
    "acquired_at": "2026-05-28T10:00:00Z",
    "ttl_seconds": 30
  }
}

Operations:
- Read: 获取当前状态
- Write: 更新状态（需要锁）
- Lock: 获取状态锁
- Unlock: 释放状态锁
- Watch: 监听状态变化
```

### 4.2 冲突解决策略

```
Conflict Types:
1. Write-Write Conflict
   - 两个Agent同时修改同一个状态
   - 解决：Last-Write-Wins 或 Merge

2. Read-Write Conflict
   - 一个Agent读取，另一个修改
   - 解决：Snapshot Isolation

3. Dependency Conflict
   - 任务依赖关系冲突
   - 解决：重新计算依赖图

Resolution Strategies:
- Last-Write-Wins: 最后的写入覆盖
- Merge: 合并两个修改
- Voting: 多数投票
- Priority: 按优先级选择
- Rollback: 回滚到一致状态
```

### 4.3 结果合并

```
Merge Strategies:

1. Union Merge (集合并)
   - 适用于列表、集合
   - 结果 = Result1 ∪ Result2 ∪ ... ∪ ResultN

2. Voting Merge (投票合并)
   - 适用于决策结果
   - 结果 = 多数投票结果

3. Priority Merge (优先级合并)
   - 适用于有优先级的结果
   - 结果 = 最高优先级的结果

4. Custom Merge (自定义合并)
   - 用户定义合并逻辑
   - 例如：加权平均、条件合并等
```

## 5. 错误处理与恢复

### 5.1 超时处理

```
Timeout Handling:
1. 设置超时时间
2. 启动超时计时器
3. 任务完成前超时触发
   ├─ 取消任务
   ├─ 清理资源
   ├─ 记录超时事件
   └─ 返回超时错误

Timeout Strategies:
- Hard Timeout: 强制取消
- Soft Timeout: 发送取消信号，等待优雅关闭
- Adaptive Timeout: 根据历史数据动态调整
```

### 5.2 失败重试

```
Retry Logic:
1. 任务失败
2. 检查retry_count < max_retries
3. 如果是可重试错误
   ├─ 等待backoff时间
   ├─ 重新执行任务
   └─ 更新retry_count
4. 如果不可重试或超过最大重试次数
   └─ 返回失败

Backoff Strategies:
- Exponential Backoff: 2^n * base_delay
- Linear Backoff: n * base_delay
- Random Backoff: random(0, max_delay)
- Jittered Backoff: exponential + random
```

### 5.3 取消处理

```
Cancellation:
1. 接收取消请求
2. 设置取消标志
3. 正在执行的任务
   ├─ 检查取消标志
   ├─ 优雅关闭
   └─ 清理资源
4. 等待中的任务
   ├─ 直接取消
   └─ 不执行
5. 返回取消状态
```

## 6. 性能指标

### 6.1 并行加速比

```
Speedup = Sequential Time / Parallel Time

Example:
- Sequential: Tool1(1s) + Tool2(1s) + Tool3(1s) = 3s
- Parallel: max(1s, 1s, 1s) = 1s
- Speedup = 3s / 1s = 3x

Target: Speedup > 2x
```

### 6.2 资源利用率

```
CPU Utilization = (Used CPU Time) / (Total CPU Time)
Memory Utilization = (Used Memory) / (Total Memory)
Concurrency Factor = (Actual Parallel Tasks) / (Max Concurrent Tasks)

Target:
- CPU Utilization > 70%
- Memory Utilization < 80%
- Concurrency Factor > 0.8
```

### 6.3 吞吐量

```
Throughput = Tasks Completed / Time

Example:
- 100 tasks in 10 seconds
- Throughput = 100 / 10 = 10 tasks/second

Target: Throughput > 2x (compared to sequential)
```

## 7. 实现路线图

### Phase 1: 工具并行执行 (1天)
- [ ] 实现ParallelToolExecutor
- [ ] 实现DAG构建和拓扑排序
- [ ] 实现asyncio并发执行
- [ ] 实现结果聚合

### Phase 2: Agent并行协作 (1.5天)
- [ ] 实现ParallelAgentExecutor
- [ ] 实现Agent池管理
- [ ] 实现三种协作模式
- [ ] 实现状态同步

### Phase 3: 通信总线 (1天)
- [ ] 实现AgentCommunicationBus
- [ ] 实现消息队列（Redis Streams）
- [ ] 实现发布/订阅
- [ ] 实现RPC和事件总线

### Phase 4: 系统集成 (0.5天)
- [ ] 修改agent.py集成并行执行
- [ ] 初始化并行模块
- [ ] 添加配置和监控

### Phase 5: 测试验证 (0.5天)
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能测试

## 8. 参考实现

- Claude Code: 子代理并行执行
- LangGraph: 并行执行和依赖管理
- Celery: 分布式任务调度
- Ray: 分布式计算框架
- Dask: 并行计算库

## 9. 成功标准

- [x] 支持工具并行执行
- [x] 支持Agent并行协作
- [x] 并行加速比 > 2x
- [x] 通过所有测试用例
- [x] 文档完整
- [x] 性能指标达标
