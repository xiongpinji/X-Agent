# X-Agent 用户使用手册

**版本**: 1.0.0  
**最后更新**: 2026-05-27  
**语言**: 中文 | [English](USER_MANUAL_EN.md)

---

## 目录

1. [快速开始](#快速开始)
2. [核心概念](#核心概念)
3. [功能详解](#功能详解)
4. [高级功能](#高级功能)
5. [常见问题](#常见问题)
6. [故障排除](#故障排除)

---

## 快速开始

### 系统要求

- Python 3.11 或更高版本
- PostgreSQL 14+
- 4GB 内存（推荐 8GB）
- 20GB 磁盘空间

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core
```

#### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

#### 3. 安装依赖

```bash
pip install -e ".[dev]"
```

#### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置以下关键变量：
# - DATABASE_URL: PostgreSQL 连接字符串
# - OPENAI_API_KEY: OpenAI API 密钥
# - QDRANT_URL: Qdrant 向量数据库地址
# - LANGFUSE_PUBLIC_KEY: Langfuse 追踪密钥
```

#### 5. 初始化数据库

```bash
python -m backend.app.core.migration init
```

#### 6. 启动服务

```bash
# 启动后端服务
uvicorn backend.app.web:app --reload

# 在另一个终端启动工作流处理器
xagent-workflow-worker
```

访问 `http://localhost:8000` 查看 API 文档。

---

## 核心概念

### Agent（代理）

Agent 是 X-Agent 系统中的执行单元，代表一个具有特定能力的自主实体。

**关键特性**：
- 独立的执行上下文
- 可配置的能力集合
- 持久化的状态管理
- 审计追踪

**示例**：
```python
from xagent_sdk import Agent

# 创建 Agent
agent = Agent(
    name="DataAnalyzer",
    capabilities=["run", "memory", "tools", "trace"],
    max_iterations=100
)

# 执行任务
result = agent.run("分析销售数据并生成报告")
```

### Workflow（工作流）

Workflow 是一系列有序的任务节点，定义了复杂任务的执行流程。

**关键特性**：
- 节点编排
- 条件分支
- 错误处理
- 并行执行
- 补偿机制

**示例**：
```python
from xagent_sdk import Workflow, Node

workflow = Workflow(name="DataPipeline")

# 添加节点
workflow.add_node(Node(
    id="fetch_data",
    action="fetch_from_api",
    params={"url": "https://api.example.com/data"}
))

workflow.add_node(Node(
    id="process_data",
    action="process",
    depends_on=["fetch_data"]
))

# 执行工作流
run = workflow.execute()
```

### Tool（工具）

Tool 是可被 Agent 调用的功能单元，用于执行特定操作。

**内置工具**：
- 浏览器自动化
- 文件操作
- 数据处理
- API 调用
- 代码执行

**示例**：
```python
from xagent_sdk import Tool

# 使用内置工具
browser = Tool.get("browser")
browser.navigate("https://example.com")
browser.click("#submit-button")

# 自定义工具
@Tool.register("my_tool")
def my_custom_tool(param1: str, param2: int) -> str:
    return f"Result: {param1} - {param2}"
```

### Memory（记忆系统）

Memory 系统提供持久化的上下文存储和语义检索能力。

**两层架构**：
- **结构化记忆**（PostgreSQL）：事实、关系、元数据
- **向量记忆**（Qdrant）：语义嵌入、相似度搜索

**示例**：
```python
from xagent_sdk import Memory

memory = Memory()

# 存储信息
memory.store("user_preference", {
    "name": "Alice",
    "interests": ["AI", "Data Science"]
})

# 检索信息
result = memory.retrieve("用户偏好", top_k=5)

# 语义搜索
similar = memory.semantic_search("机器学习相关内容", top_k=10)
```

---

## 功能详解

### 1. Agent 创建和管理

#### 创建 Agent

**API 端点**: `POST /api/v1/agents`

```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DataAnalyzer",
    "status": "active",
    "capabilities": ["run", "memory", "tools", "trace"],
    "max_iterations": 100
  }'
```

**响应**:
```json
{
  "id": "agent_a1b2c3d4",
  "name": "DataAnalyzer",
  "status": "active",
  "capabilities": ["run", "memory", "tools", "trace"],
  "max_iterations": 100,
  "created_at": "2026-05-27T10:30:00Z"
}
```

#### 列出所有 Agent

**API 端点**: `GET /api/v1/agents`

```bash
curl http://localhost:8000/api/v1/agents
```

#### 获取 Agent 详情

**API 端点**: `GET /api/v1/agents/{agent_id}`

```bash
curl http://localhost:8000/api/v1/agents/agent_a1b2c3d4
```

#### 更新 Agent

**API 端点**: `PUT /api/v1/agents/{agent_id}`

```bash
curl -X PUT http://localhost:8000/api/v1/agents/agent_a1b2c3d4 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "UpdatedAnalyzer",
    "status": "inactive"
  }'
```

#### 删除 Agent

**API 端点**: `DELETE /api/v1/agents/{agent_id}`

```bash
curl -X DELETE http://localhost:8000/api/v1/agents/agent_a1b2c3d4
```

**最佳实践**：
- 为不同的任务类型创建专门的 Agent
- 定期审查 Agent 的性能指标
- 使用有意义的名称便于识别
- 根据需要调整能力集合

### 2. 工具使用

#### 浏览器自动化

```python
from xagent_sdk import Tool

browser = Tool.get("browser")

# 导航
browser.navigate("https://example.com")

# 点击元素
browser.click("#button-id")

# 填充表单
browser.fill_form({
    "username": "user@example.com",
    "password": "password123"
})

# 获取页面内容
content = browser.get_page_content()

# 截图
screenshot = browser.screenshot()
```

#### 文件操作

```python
from xagent_sdk import Tool

file_tool = Tool.get("file")

# 读取文件
content = file_tool.read("/path/to/file.txt")

# 写入文件
file_tool.write("/path/to/file.txt", "content")

# 列出目录
files = file_tool.list_directory("/path/to/dir")

# 删除文件
file_tool.delete("/path/to/file.txt")
```

#### API 调用

```python
from xagent_sdk import Tool

api_tool = Tool.get("api")

# GET 请求
response = api_tool.get("https://api.example.com/data")

# POST 请求
response = api_tool.post(
    "https://api.example.com/data",
    json={"key": "value"}
)

# 带认证的请求
response = api_tool.get(
    "https://api.example.com/data",
    headers={"Authorization": "Bearer token"}
)
```

**最佳实践**：
- 始终验证工具返回的数据
- 实现适当的错误处理
- 使用超时防止无限等待
- 记录工具调用以便调试

### 3. 记忆系统

#### 存储信息

```python
from xagent_sdk import Memory

memory = Memory()

# 存储简单数据
memory.store("key", "value")

# 存储复杂对象
memory.store("user_profile", {
    "id": "user_123",
    "name": "Alice",
    "email": "alice@example.com",
    "preferences": {
        "language": "zh",
        "theme": "dark"
    }
})

# 存储带元数据的数据
memory.store(
    "analysis_result",
    {"data": [1, 2, 3]},
    metadata={"type": "analysis", "timestamp": "2026-05-27"}
)
```

#### 检索信息

```python
# 按键检索
result = memory.retrieve("user_profile")

# 模糊搜索
results = memory.search("用户信息", top_k=5)

# 语义搜索
similar = memory.semantic_search(
    "用户偏好设置",
    top_k=10,
    threshold=0.7
)
```

#### 更新和删除

```python
# 更新信息
memory.update("user_profile", {"name": "Bob"})

# 删除信息
memory.delete("user_profile")

# 清空所有记忆
memory.clear()
```

**最佳实践**：
- 为记忆数据添加有意义的键名
- 定期清理过期数据
- 使用元数据标记数据来源
- 实现记忆数据的版本控制

### 4. 工作流编排

#### 定义工作流

```python
from xagent_sdk import Workflow, Node, Edge

# 创建工作流
workflow = Workflow(
    name="DataProcessingPipeline",
    description="处理和分析数据的工作流"
)

# 添加节点
workflow.add_node(Node(
    id="fetch",
    name="获取数据",
    action="fetch_data",
    params={"source": "api"}
))

workflow.add_node(Node(
    id="validate",
    name="验证数据",
    action="validate",
    depends_on=["fetch"]
))

workflow.add_node(Node(
    id="process",
    name="处理数据",
    action="process",
    depends_on=["validate"]
))

workflow.add_node(Node(
    id="analyze",
    name="分析数据",
    action="analyze",
    depends_on=["process"]
))

# 添加边（连接）
workflow.add_edge(Edge(from_node="fetch", to_node="validate"))
workflow.add_edge(Edge(from_node="validate", to_node="process"))
workflow.add_edge(Edge(from_node="process", to_node="analyze"))
```

#### 执行工作流

```python
# 执行工作流
run = workflow.execute()

# 获取执行状态
status = run.get_status()  # "running", "completed", "failed"

# 获取执行结果
result = run.get_result()

# 获取执行时间线
timeline = run.get_timeline()

# 获取执行指标
metrics = run.get_metrics()
```

#### 条件分支

```python
from xagent_sdk import Condition

# 添加条件节点
workflow.add_node(Node(
    id="check_quality",
    name="检查数据质量",
    action="check_quality",
    depends_on=["validate"]
))

# 添加条件分支
workflow.add_condition(Condition(
    from_node="check_quality",
    condition="quality > 0.8",
    true_node="process",
    false_node="retry"
))
```

#### 错误处理

```python
# 添加重试策略
workflow.add_node(Node(
    id="fetch",
    action="fetch_data",
    retry_policy={
        "max_retries": 3,
        "backoff": "exponential",
        "initial_delay": 1
    }
))

# 添加补偿节点
workflow.add_node(Node(
    id="cleanup",
    action="cleanup",
    compensation_for="fetch"
))
```

**最佳实践**：
- 设计清晰的工作流结构
- 实现适当的错误处理和重试
- 添加日志记录便于调试
- 定期测试工作流的各个分支

### 5. 浏览器自动化

#### 基本操作

```python
from xagent_sdk import BrowserAutomation

browser = BrowserAutomation()

# 打开浏览器
browser.open()

# 导航到 URL
browser.navigate("https://example.com")

# 等待元素加载
browser.wait_for_element("#content", timeout=10)

# 获取页面标题
title = browser.get_title()

# 获取页面 URL
url = browser.get_url()

# 关闭浏览器
browser.close()
```

#### 元素交互

```python
# 点击元素
browser.click("#button-id")

# 双击元素
browser.double_click("#element-id")

# 右键点击
browser.right_click("#element-id")

# 悬停元素
browser.hover("#element-id")

# 拖拽元素
browser.drag_and_drop("#source", "#target")

# 滚动页面
browser.scroll(x=0, y=500)

# 获取元素文本
text = browser.get_text("#element-id")

# 获取元素属性
attr = browser.get_attribute("#element-id", "href")
```

#### 表单操作

```python
# 填充输入框
browser.fill_input("#username", "user@example.com")

# 清空输入框
browser.clear_input("#password")

# 选择下拉菜单
browser.select_option("#country", "China")

# 勾选复选框
browser.check_checkbox("#agree")

# 取消勾选
browser.uncheck_checkbox("#agree")

# 提交表单
browser.submit_form("#login-form")
```

#### 页面内容提取

```python
# 获取页面 HTML
html = browser.get_page_html()

# 获取页面文本
text = browser.get_page_text()

# 获取所有链接
links = browser.get_all_links()

# 获取所有图片
images = browser.get_all_images()

# 获取表格数据
table_data = browser.get_table_data("#data-table")

# 获取 JSON 数据
json_data = browser.get_json_data()
```

#### 截图和录制

```python
# 获取截图
screenshot = browser.screenshot()
screenshot.save("screenshot.png")

# 获取特定元素的截图
element_screenshot = browser.screenshot_element("#element-id")

# 开始录制
browser.start_recording()

# 执行操作...

# 停止录制
video = browser.stop_recording()
video.save("recording.mp4")
```

**最佳实践**：
- 使用显式等待而不是固定延迟
- 实现适当的错误处理
- 清理浏览器资源
- 使用无头模式提高性能

---

## 高级功能

### 1. 多代理协作

```python
from xagent_sdk import Agent, Collaboration

# 创建多个 Agent
analyzer = Agent(name="Analyzer", capabilities=["analysis"])
writer = Agent(name="Writer", capabilities=["writing"])
reviewer = Agent(name="Reviewer", capabilities=["review"])

# 创建协作
collab = Collaboration(
    agents=[analyzer, writer, reviewer],
    workflow="sequential"  # 或 "parallel"
)

# 执行协作任务
result = collab.execute("生成技术报告")
```

### 2. 自定义工具

```python
from xagent_sdk import Tool

@Tool.register("custom_analysis")
def analyze_data(data: list, method: str = "mean") -> dict:
    """自定义数据分析工具"""
    if method == "mean":
        result = sum(data) / len(data)
    elif method == "median":
        sorted_data = sorted(data)
        result = sorted_data[len(data) // 2]
    else:
        raise ValueError(f"Unknown method: {method}")
    
    return {"result": result, "method": method}

# 使用自定义工具
tool = Tool.get("custom_analysis")
result = tool(data=[1, 2, 3, 4, 5], method="mean")
```

### 3. 插件开发

```python
from xagent_sdk import Plugin

class MyPlugin(Plugin):
    name = "my_plugin"
    version = "1.0.0"
    
    def initialize(self):
        """插件初始化"""
        pass
    
    def register_tools(self):
        """注册工具"""
        self.register_tool("my_tool", self.my_tool)
    
    def my_tool(self, param: str) -> str:
        """自定义工具实现"""
        return f"Processed: {param}"

# 加载插件
plugin = MyPlugin()
plugin.initialize()
```

### 4. API 扩展

```python
from xagent_sdk import APIExtension

class CustomAPI(APIExtension):
    prefix = "/api/v1/custom"
    
    @APIExtension.route("GET", "/data")
    def get_data(self, request):
        """获取自定义数据"""
        return {"data": "custom"}
    
    @APIExtension.route("POST", "/process")
    def process_data(self, request):
        """处理数据"""
        data = request.json()
        return {"processed": data}

# 注册 API 扩展
api = CustomAPI()
api.register()
```

---

## 常见问题

### Q1: 如何提高 Agent 的执行效率？

**A**: 
- 优化工作流设计，减少不必要的步骤
- 使用并行执行处理独立任务
- 调整 LLM 模型选择，平衡质量和速度
- 实现缓存机制避免重复计算

### Q2: 记忆系统的数据量限制是多少？

**A**: 
- PostgreSQL 层：取决于磁盘空间，通常支持数百万条记录
- Qdrant 向量层：支持数千万维向量
- 建议定期清理过期数据以保持性能

### Q3: 如何处理工作流中的长时间运行任务？

**A**: 
- 使用异步执行模式
- 实现任务分解和流式处理
- 添加进度追踪和中断机制
- 配置适当的超时和重试策略

### Q4: 如何确保 Agent 的安全性？

**A**: 
- 实现审批工作流进行敏感操作
- 使用策略引擎限制 Agent 权限
- 启用审计日志记录所有操作
- 定期进行安全审计

### Q5: 如何调试工作流执行问题？

**A**: 
- 查看详细的执行日志
- 使用 Langfuse 追踪系统调用
- 启用调试模式获取更多信息
- 使用回放功能重现问题

---

## 故障排除

### 问题：Agent 执行超时

**症状**: Agent 任务在指定时间内未完成

**诊断步骤**:
1. 检查 Agent 日志查看具体操作
2. 验证外部服务可用性
3. 检查网络连接

**解决方案**:
```python
# 增加超时时间
agent.run(
    task="...",
    timeout=300  # 5 分钟
)

# 或配置全局超时
agent.config.timeout = 300
```

### 问题：内存使用过高

**症状**: 系统内存占用不断增加

**诊断步骤**:
1. 监控内存使用趋势
2. 检查是否有内存泄漏
3. 查看记忆系统的数据量

**解决方案**:
```python
# 定期清理记忆
memory.cleanup(older_than_days=30)

# 限制记忆大小
memory.config.max_size = "10GB"

# 启用自动清理
memory.config.auto_cleanup = True
```

### 问题：工作流执行失败

**症状**: 工作流在某个节点失败

**诊断步骤**:
1. 查看失败节点的错误信息
2. 检查节点的依赖关系
3. 验证输入数据的有效性

**解决方案**:
```python
# 查看执行详情
run = workflow.execute()
if run.status == "failed":
    failed_node = run.get_failed_node()
    error = run.get_error(failed_node)
    print(f"Failed at {failed_node}: {error}")

# 启用重试
workflow.add_node(Node(
    id="fetch",
    action="fetch_data",
    retry_policy={"max_retries": 3}
))
```

### 问题：浏览器自动化不稳定

**症状**: 浏览器操作间歇性失败

**诊断步骤**:
1. 检查浏览器驱动版本
2. 验证网络连接
3. 检查目标网站的变化

**解决方案**:
```python
# 使用显式等待
browser.wait_for_element("#element", timeout=10)

# 添加重试逻辑
for attempt in range(3):
    try:
        browser.click("#button")
        break
    except Exception as e:
        if attempt == 2:
            raise
        time.sleep(1)

# 启用调试模式
browser.config.debug = True
```

---

## 获取帮助

- **文档**: [完整文档](README.md)
- **API 参考**: [API 文档](../api/API_REFERENCE.md)
- **示例代码**: [示例集合](../examples/)
- **GitHub Issues**: [报告问题](https://github.com/x-agent/x-agent-core/issues)
- **邮件支持**: support@x-agent.dev

---

**X-Agent 用户手册** - 构建智能自主系统
