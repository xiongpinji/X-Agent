# X-Agent 架构设计文档

**版本**: 1.0.0  
**最后更新**: 2026-05-27

---

## 目录

1. [系统架构](#系统架构)
2. [核心组件](#核心组件)
3. [数据流](#数据流)
4. [技术栈](#技术栈)
5. [设计决策](#设计决策)
6. [扩展性设计](#扩展性设计)
7. [安全架构](#安全架构)
8. [性能架构](#性能架构)

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend Layer                          │
│              (Web UI / Mobile App / CLI)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                         │
│         (Authentication, Rate Limiting, Routing)            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Agent API    │  │ Workflow API │  │ Tool API     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Memory API   │  │ Approval API │  │ Audit API    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Core Services Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ LLM Router   │  │ Memory Sys   │  │ Policy Eng   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Workflow Eng │  │ Approval Sys │  │ Audit Trail  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │PostgreSQL│  │ Qdrant   │  │Playwright│  │Langfuse  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │ Redis    │  │RabbitMQ  │  │Prometheus│                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

### 分层设计

#### 1. 表现层 (Presentation Layer)

**职责**: 提供用户界面和交互

**组件**:
- Web UI (React/Vue)
- Mobile App (React Native)
- CLI 工具
- API 文档 (Swagger/OpenAPI)

#### 2. API 网关层 (API Gateway Layer)

**职责**: 请求路由、认证、限流

**功能**:
- 请求验证
- 令牌认证
- 速率限制
- 请求日志
- 错误处理

#### 3. 应用层 (Application Layer)

**职责**: 业务逻辑实现

**模块**:
- Agent 管理
- Workflow 编排
- Tool 执行
- Memory 管理
- Approval 流程
- Audit 日志

#### 4. 核心服务层 (Core Services Layer)

**职责**: 核心功能实现

**服务**:
- LLM 路由
- 记忆系统
- 策略引擎
- 工作流引擎
- 审批系统
- 审计追踪

#### 5. 基础设施层 (Infrastructure Layer)

**职责**: 数据存储和外部服务

**组件**:
- PostgreSQL (结构化数据)
- Qdrant (向量数据)
- Playwright (浏览器自动化)
- Langfuse (追踪)
- Redis (缓存)
- RabbitMQ (消息队列)

---

## 核心组件

### 1. Agent 引擎

```python
class AgentEngine:
    """Agent 执行引擎"""
    
    def __init__(self, llm_router, memory, tools):
        self.llm_router = llm_router
        self.memory = memory
        self.tools = tools
    
    async def run(self, agent: Agent, task: str) -> Result:
        """执行 Agent 任务"""
        # 1. 初始化执行上下文
        context = ExecutionContext(agent, task)
        
        # 2. 思考阶段
        thought = await self.think(context)
        
        # 3. 行动阶段
        action = await self.act(thought)
        
        # 4. 观察阶段
        observation = await self.observe(action)
        
        # 5. 更新记忆
        await self.memory.store(observation)
        
        # 6. 返回结果
        return Result(observation)
    
    async def think(self, context: ExecutionContext) -> Thought:
        """思考下一步行动"""
        # 检索相关记忆
        memories = await self.memory.retrieve(context.task)
        
        # 调用 LLM 进行推理
        prompt = self.build_prompt(context, memories)
        thought = await self.llm_router.generate(prompt)
        
        return thought
    
    async def act(self, thought: Thought) -> Action:
        """执行行动"""
        # 解析思考结果
        action = self.parse_action(thought)
        
        # 执行工具
        result = await self.tools.execute(action)
        
        return result
```

### 2. Workflow 引擎

```python
class WorkflowEngine:
    """工作流编排引擎"""
    
    async def execute(self, workflow: Workflow) -> WorkflowRun:
        """执行工作流"""
        run = WorkflowRun(workflow)
        
        # 1. 验证工作流
        self.validate(workflow)
        
        # 2. 初始化执行上下文
        context = ExecutionContext(workflow)
        
        # 3. 执行节点
        for node in workflow.nodes:
            node_run = await self.execute_node(node, context)
            run.add_node_run(node_run)
            
            # 检查是否需要分支
            if node.has_condition:
                next_node = self.evaluate_condition(node, node_run)
                if next_node:
                    node = next_node
        
        # 4. 返回执行结果
        return run
    
    async def execute_node(self, node: Node, context: ExecutionContext) -> NodeRun:
        """执行单个节点"""
        node_run = NodeRun(node)
        
        try:
            # 1. 等待依赖完成
            await self.wait_dependencies(node, context)
            
            # 2. 执行节点动作
            result = await self.execute_action(node.action, node.params)
            
            # 3. 记录结果
            node_run.set_result(result)
            
        except Exception as e:
            # 处理错误
            if node.has_compensation:
                await self.execute_compensation(node)
            
            node_run.set_error(e)
        
        return node_run
```

### 3. 记忆系统

```python
class MemorySystem:
    """双层记忆系统"""
    
    def __init__(self, postgres_client, qdrant_client):
        self.postgres = postgres_client  # 结构化存储
        self.qdrant = qdrant_client      # 向量存储
    
    async def store(self, key: str, value: Any, metadata: Dict = None):
        """存储数据"""
        # 1. 存储到 PostgreSQL
        await self.postgres.store(key, value, metadata)
        
        # 2. 生成向量嵌入
        embedding = await self.generate_embedding(value)
        
        # 3. 存储到 Qdrant
        await self.qdrant.store(key, embedding, metadata)
    
    async def retrieve(self, key: str) -> Any:
        """按键检索"""
        return await self.postgres.retrieve(key)
    
    async def semantic_search(self, query: str, top_k: int = 5) -> List[Result]:
        """语义搜索"""
        # 1. 生成查询向量
        query_embedding = await self.generate_embedding(query)
        
        # 2. 在 Qdrant 中搜索
        results = await self.qdrant.search(query_embedding, top_k)
        
        # 3. 从 PostgreSQL 获取完整数据
        full_results = []
        for result in results:
            data = await self.postgres.retrieve(result.key)
            full_results.append(data)
        
        return full_results
    
    async def generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入"""
        # 使用 OpenAI 或其他嵌入模型
        pass
```

### 4. 策略引擎

```python
class PolicyEngine:
    """策略执行引擎"""
    
    def __init__(self, policy_store):
        self.policy_store = policy_store
    
    async def evaluate(self, action: Action, context: ExecutionContext) -> bool:
        """评估策略"""
        # 1. 获取适用的策略
        policies = await self.policy_store.get_policies(action.type)
        
        # 2. 评估每个策略
        for policy in policies:
            if not await self.evaluate_policy(policy, action, context):
                return False
        
        return True
    
    async def evaluate_policy(self, policy: Policy, action: Action, context: ExecutionContext) -> bool:
        """评估单个策略"""
        # 检查条件
        if not self.check_conditions(policy.conditions, context):
            return False
        
        # 检查权限
        if not self.check_permissions(policy.permissions, context.user):
            return False
        
        # 检查资源限制
        if not self.check_resource_limits(policy.limits, context):
            return False
        
        return True
```

---

## 数据流

### Agent 执行流程

```
┌─────────────┐
│  User Task  │
└──────┬──────┘
       ↓
┌─────────────────────────────────────┐
│  1. Parse Task & Build Context      │
│     - 提取任务参数                   │
│     - 初始化执行上下文               │
└──────┬──────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│  2. Retrieve Relevant Memory        │
│     - 语义搜索相关记忆               │
│     - 构建上下文信息                 │
└──────┬──────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│  3. LLM Reasoning                   │
│     - 调用 LLM 进行推理              │
│     - 生成思考和行动计划             │
└──────┬──────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│  4. Policy Evaluation               │
│     - 评估策略是否允许               │
│     - 检查权限和资源限制             │
└──────┬──────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│  5. Tool Execution                  │
│     - 执行选定的工具                 │
│     - 获取执行结果                   │
└──────┬──────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│  6. Store Memory & Audit            │
│     - 存储执行结果到记忆             │
│     - 记录审计日志                   │
└──────┬──────────────────────────────┘
       ↓
┌─────────────┐
│   Result    │
└─────────────┘
```

### Workflow 执行流程

```
┌──────────────────┐
│  Workflow Start  │
└────────┬─────────┘
         ↓
┌──────────────────────────────────────┐
│  1. Validate Workflow                │
│     - 检查节点和边的有效性            │
│     - 验证依赖关系                    │
└────────┬─────────────────────────────┘
         ↓
┌──────────────────────────────────────┐
│  2. Initialize Execution Context     │
│     - 创建执行实例                    │
│     - 初始化变量和状态                │
└────────┬─────────────────────────────┘
         ↓
┌──────────────────────────────────────┐
│  3. Execute Nodes (Topological Sort) │
│     - 按拓扑顺序执行节点              │
│     - 等待依赖完成                    │
└────────┬─────────────────────────────┘
         ↓
┌──────────────────────────────────────┐
│  4. Handle Conditions & Branches     │
│     - 评估条件                        │
│     - 选择分支                        │
└────────┬─────────────────────────────┘
         ↓
┌──────────────────────────────────────┐
│  5. Error Handling & Compensation    │
│     - 捕获错误                        │
│     - 执行补偿操作                    │
└────────┬─────────────────────────────┘
         ↓
┌──────────────────────────────────────┐
│  6. Collect Results & Metrics        │
│     - 收集所有节点结果                │
│     - 计算执行指标                    │
└────────┬─────────────────────────────┘
         ↓
┌──────────────────┐
│  Workflow End    │
└──────────────────┘
```

---

## 技术栈

### 后端

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 框架 | FastAPI | 0.100+ | Web 框架 |
| 数据库 | PostgreSQL | 14+ | 结构化数据 |
| 向量DB | Qdrant | 1.7+ | 向量搜索 |
| 缓存 | Redis | 7.0+ | 会话和缓存 |
| 消息队列 | RabbitMQ | 3.12+ | 异步任务 |
| ORM | SQLAlchemy | 2.0+ | 数据库映射 |
| 验证 | Pydantic | 2.0+ | 数据验证 |
| 异步 | asyncio | 内置 | 异步编程 |

### 前端

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 框架 | React | 18+ | UI 框架 |
| 状态管理 | Redux | 4.2+ | 状态管理 |
| HTTP | Axios | 1.4+ | HTTP 客户端 |
| 路由 | React Router | 6+ | 路由管理 |
| UI 库 | Material-UI | 5+ | UI 组件 |
| 图表 | ECharts | 5+ | 数据可视化 |

### 基础设施

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 容器 | Docker | 20.10+ | 容器化 |
| 编排 | Kubernetes | 1.24+ | 容器编排 |
| 监控 | Prometheus | 2.40+ | 指标收集 |
| 可视化 | Grafana | 9.0+ | 仪表板 |
| 追踪 | Langfuse | 2.0+ | 请求追踪 |
| 日志 | ELK Stack | 8.0+ | 日志管理 |

---

## 设计决策

### 1. 为什么选择 FastAPI？

**优点**:
- 高性能 (接近 Go 和 Node.js)
- 自动 API 文档生成
- 内置数据验证
- 原生异步支持
- 类型提示支持

**权衡**:
- 相对较新的框架
- 社区规模小于 Django

### 2. 为什么使用双层记忆系统？

**结构化存储 (PostgreSQL)**:
- 支持复杂查询
- 事务支持
- 数据一致性

**向量存储 (Qdrant)**:
- 语义搜索
- 快速相似度匹配
- 可扩展性

### 3. 为什么采用微服务架构？

**优点**:
- 独立部署
- 技术多样性
- 故障隔离
- 水平扩展

**挑战**:
- 分布式系统复杂性
- 网络延迟
- 数据一致性

---

## 扩展性设计

### 水平扩展

```yaml
# Kubernetes 自动扩展配置
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: x-agent-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: x-agent-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 垂直扩展

```python
# 资源优化
- 增加 CPU 和内存
- 优化数据库查询
- 实现缓存策略
- 使用连接池
```

### 功能扩展

```python
# 插件系统
class PluginInterface:
    def register_tools(self):
        """注册新工具"""
        pass
    
    def register_api(self):
        """注册新 API"""
        pass
    
    def register_models(self):
        """注册新数据模型"""
        pass
```

---

## 安全架构

### 认证和授权

```
┌─────────────────────────────────────┐
│  1. Authentication (认证)            │
│     - API Key / OAuth / JWT          │
│     - 验证用户身份                   │
└──────┬──────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│  2. Authorization (授权)             │
│     - RBAC (基于角色)                │
│     - 检查权限                       │
└──────┬──────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│  3. Audit (审计)                     │
│     - 记录所有操作                   │
│     - 追踪变更历史                   │
└─────────────────────────────────────┘
```

### 数据安全

- 传输层: TLS/SSL 加密
- 存储层: 数据库加密
- 应用层: 敏感数据脱敏

---

## 性能架构

### 缓存策略

```
┌─────────────────────────────────────┐
│  L1 Cache (应用内存)                 │
│  - LRU 缓存                          │
│  - 热数据                            │
└──────┬──────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│  L2 Cache (Redis)                    │
│  - 分布式缓存                        │
│  - 跨实例共享                        │
└──────┬──────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│  L3 Cache (数据库)                   │
│  - 持久化存储                        │
│  - 完整数据                          │
└─────────────────────────────────────┘
```

### 查询优化

- 索引策略
- 查询计划分析
- 连接池管理
- 批量操作

---

**X-Agent 架构设计文档** - 系统设计和实现指南
