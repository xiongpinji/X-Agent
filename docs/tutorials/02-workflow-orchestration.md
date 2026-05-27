# 工作流编排教程

学习如何定义、执行和管理复杂的工作流。

## 目录

1. [工作流基础](#工作流基础)
2. [定义工作流](#定义工作流)
3. [节点类型](#节点类型)
4. [条件分支](#条件分支)
5. [错误处理](#错误处理)
6. [监控和调试](#监控和调试)

## 工作流基础

### 什么是工作流？

工作流是一系列有序的任务节点，支持：

- **顺序执行**：节点按顺序执行
- **条件分支**：根据条件选择不同的执行路径
- **并行执行**：多个节点同时执行
- **错误处理**：失败时自动重试或执行补偿操作

### 工作流的优势

- **可视化**：清晰地表示复杂的业务流程
- **可重用**：工作流可以被多次使用
- **可追踪**：记录每个步骤的执行情况
- **可恢复**：支持从失败点恢复

## 定义工作流

### 基础工作流

```python
from backend.app.core.workflows import Workflow, WorkflowNode, NodeType

# 创建工作流
workflow = Workflow(
    name="OrderProcessing",
    description="订单处理工作流"
)

# 添加节点
node1 = WorkflowNode(
    id="validate_order",
    name="验证订单",
    type=NodeType.TASK,
    action="validate_order",
    params={"strict": True}
)

node2 = WorkflowNode(
    id="check_inventory",
    name="检查库存",
    type=NodeType.TASK,
    action="check_inventory"
)

node3 = WorkflowNode(
    id="create_shipment",
    name="生成发货单",
    type=NodeType.TASK,
    action="create_shipment"
)

# 添加节点到工作流
workflow.add_node(node1)
workflow.add_node(node2)
workflow.add_node(node3)

# 定义节点之间的依赖关系
workflow.add_edge("validate_order", "check_inventory")
workflow.add_edge("check_inventory", "create_shipment")
```

### 使用 YAML 定义工作流

创建 `order_workflow.yaml`：

```yaml
name: OrderProcessing
description: 订单处理工作流
nodes:
  - id: validate_order
    name: 验证订单
    type: task
    action: validate_order
    params:
      strict: true
    timeout: 30
  
  - id: check_inventory
    name: 检查库存
    type: task
    action: check_inventory
    timeout: 60
  
  - id: create_shipment
    name: 生成发货单
    type: task
    action: create_shipment
    timeout: 45
  
  - id: notify_customer
    name: 通知客户
    type: task
    action: notify_customer
    timeout: 30

edges:
  - from: validate_order
    to: check_inventory
  
  - from: check_inventory
    to: create_shipment
  
  - from: create_shipment
    to: notify_customer
```

加载工作流：

```python
from backend.app.core.workflows import Workflow

workflow = Workflow.from_yaml("order_workflow.yaml")
```

### 使用 Python DSL 定义工作流

```python
from backend.app.core.workflows import WorkflowBuilder

# 使用 Builder 模式
workflow = (
    WorkflowBuilder("OrderProcessing")
    .add_task("validate_order", "验证订单")
    .add_task("check_inventory", "检查库存")
    .add_task("create_shipment", "生成发货单")
    .add_task("notify_customer", "通知客户")
    .connect("validate_order", "check_inventory")
    .connect("check_inventory", "create_shipment")
    .connect("create_shipment", "notify_customer")
    .build()
)
```

## 节点类型

### 1. 任务节点（Task）

执行单个操作：

```python
task_node = WorkflowNode(
    id="fetch_data",
    name="获取数据",
    type=NodeType.TASK,
    action="fetch_data",
    params={
        "source": "database",
        "query": "SELECT * FROM orders"
    },
    timeout=60,
    retry_count=3
)
```

### 2. 条件节点（Decision）

根据条件选择执行路径：

```python
decision_node = WorkflowNode(
    id="check_amount",
    name="检查金额",
    type=NodeType.DECISION,
    condition="amount > 1000"
)

# 添加条件分支
workflow.add_edge(
    "check_amount",
    "require_approval",
    condition="true"
)

workflow.add_edge(
    "check_amount",
    "process_payment",
    condition="false"
)
```

### 3. 并行节点（Parallel）

并行执行多个节点：

```python
parallel_node = WorkflowNode(
    id="parallel_processing",
    name="并行处理",
    type=NodeType.PARALLEL,
    nodes=["send_email", "update_database", "log_event"]
)

workflow.add_node(parallel_node)
```

### 4. 循环节点（Loop）

重复执行节点：

```python
loop_node = WorkflowNode(
    id="process_items",
    name="处理项目",
    type=NodeType.LOOP,
    action="process_item",
    loop_condition="items.length > 0",
    loop_variable="item"
)

workflow.add_node(loop_node)
```

### 5. 等待节点（Wait）

等待特定条件或时间：

```python
wait_node = WorkflowNode(
    id="wait_approval",
    name="等待审批",
    type=NodeType.WAIT,
    wait_condition="approval_received",
    timeout=3600  # 1 小时超时
)

workflow.add_node(wait_node)
```

### 6. 子工作流节点（SubWorkflow）

调用另一个工作流：

```python
subworkflow_node = WorkflowNode(
    id="payment_workflow",
    name="支付工作流",
    type=NodeType.SUBWORKFLOW,
    workflow_name="PaymentProcessing",
    params={
        "amount": 100,
        "currency": "USD"
    }
)

workflow.add_node(subworkflow_node)
```

## 条件分支

### 简单条件

```python
# 添加条件分支
workflow.add_edge(
    from_node="check_inventory",
    to_node="create_shipment",
    condition="inventory_available == true"
)

workflow.add_edge(
    from_node="check_inventory",
    to_node="notify_out_of_stock",
    condition="inventory_available == false"
)
```

### 复杂条件

```python
# 使用复杂条件表达式
workflow.add_edge(
    from_node="validate_order",
    to_node="require_approval",
    condition="amount > 1000 AND customer_type == 'new'"
)

workflow.add_edge(
    from_node="validate_order",
    to_node="process_payment",
    condition="amount <= 1000 OR customer_type == 'vip'"
)
```

### 条件函数

```python
def should_require_approval(context):
    """判断是否需要审批"""
    return context.get("amount", 0) > 1000

# 使用条件函数
workflow.add_edge(
    from_node="validate_order",
    to_node="require_approval",
    condition=should_require_approval
)
```

## 错误处理

### 重试策略

```python
# 为节点配置重试
node = WorkflowNode(
    id="fetch_data",
    name="获取数据",
    type=NodeType.TASK,
    action="fetch_data",
    retry_count=3,
    retry_delay=5,  # 秒
    retry_backoff=2  # 指数退避因子
)

workflow.add_node(node)
```

### 错误处理节点

```python
# 添加错误处理节点
error_handler = WorkflowNode(
    id="handle_error",
    name="错误处理",
    type=NodeType.ERROR_HANDLER,
    action="log_error_and_notify"
)

workflow.add_node(error_handler)

# 为所有节点添加错误处理
for node in workflow.nodes:
    workflow.add_edge(
        from_node=node.id,
        to_node="handle_error",
        condition="on_error"
    )
```

### 补偿操作

```python
# 定义补偿操作
workflow.add_compensation(
    node_id="create_shipment",
    compensation_action="cancel_shipment",
    compensation_params={"reason": "order_cancelled"}
)

# 当工作流失败时，自动执行补偿操作
```

## 执行工作流

### 基础执行

```python
import asyncio

async def main():
    # 执行工作流
    run = await workflow.execute(
        input_data={
            "order_id": "ORD-001",
            "amount": 500
        }
    )
    
    print(f"执行状态: {run.status}")
    print(f"执行时间: {run.duration}s")
    print(f"输出数据: {run.output}")

asyncio.run(main())
```

### 流式执行

```python
async def main():
    # 流式执行，实时获取节点执行情况
    async for event in workflow.execute_stream(
        input_data={"order_id": "ORD-001"}
    ):
        print(f"节点: {event.node_id}")
        print(f"状态: {event.status}")
        print(f"输出: {event.output}")

asyncio.run(main())
```

### 定时执行

```python
from backend.app.core.workflows import WorkflowScheduler

# 创建调度器
scheduler = WorkflowScheduler()

# 定时执行工作流
scheduler.schedule(
    workflow=workflow,
    schedule="0 9 * * *",  # 每天 9:00 执行
    input_data={"batch_size": 100}
)

# 启动调度器
await scheduler.start()
```

## 监控和调试

### 查看执行历史

```python
# 获取工作流的执行历史
runs = await workflow.get_runs(limit=10)

for run in runs:
    print(f"运行 ID: {run.id}")
    print(f"状态: {run.status}")
    print(f"开始时间: {run.start_time}")
    print(f"结束时间: {run.end_time}")
    print(f"执行时间: {run.duration}s")
```

### 查看节点执行详情

```python
# 获取特定运行的节点执行详情
run = await workflow.get_run(run_id="run-123")

for node_execution in run.node_executions:
    print(f"节点: {node_execution.node_id}")
    print(f"状态: {node_execution.status}")
    print(f"输入: {node_execution.input}")
    print(f"输出: {node_execution.output}")
    print(f"错误: {node_execution.error}")
```

### 性能分析

```python
# 获取性能指标
metrics = await workflow.get_metrics()

print(f"总执行次数: {metrics.total_runs}")
print(f"成功率: {metrics.success_rate}%")
print(f"平均执行时间: {metrics.avg_duration}s")
print(f"最长执行时间: {metrics.max_duration}s")
print(f"最短执行时间: {metrics.min_duration}s")

# 获取节点级别的性能指标
for node_id, node_metrics in metrics.node_metrics.items():
    print(f"节点 {node_id}:")
    print(f"  平均执行时间: {node_metrics.avg_duration}s")
    print(f"  成功率: {node_metrics.success_rate}%")
```

### 调试模式

```python
# 启用调试模式
workflow.enable_debug_mode()

# 执行工作流
run = await workflow.execute(
    input_data={"order_id": "ORD-001"}
)

# 获取调试信息
debug_info = run.get_debug_info()
print(f"执行步骤: {debug_info.steps}")
print(f"变量状态: {debug_info.variables}")
print(f"条件评估: {debug_info.conditions}")
```

## 最佳实践

1. **清晰的节点命名**：使用描述性的节点名称
2. **合理的超时设置**：根据操作复杂度设置超时
3. **完善的错误处理**：为每个节点配置重试和错误处理
4. **性能优化**：使用并行节点提高效率
5. **监控和告警**：监控工作流执行情况，及时发现问题
6. **版本管理**：管理工作流的不同版本
7. **文档记录**：记录工作流的目的和使用方法

## 下一步

- 阅读 [记忆系统教程](03-memory-system.md)
- 阅读 [浏览器自动化教程](04-browser-automation.md)
- 阅读 [最佳实践](../best-practices/README.md)
