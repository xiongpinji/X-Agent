# MCP端到端集成测试

## 概述

`tests/integration/test_mcp_e2e.py` 是X-Agent项目MCP模块的完整端到端集成测试套件。该测试验证了MCP工具发现、注册和调用的完整流程。

## 测试架构

### 核心组件

1. **MockMCPServer** - 模拟MCP服务器，用于测试而不依赖真实的外部服务
2. **Fixtures** - pytest异步fixtures提供测试所需的依赖注入
3. **测试类** - 按功能分组的测试用例

## 测试场景覆盖

### 1. MCP服务器连接 (TestMCPServerConnection)

- **test_add_single_server**: 验证添加单个MCP服务器的流程
- **test_add_disabled_server**: 验证禁用服务器不会被添加
- **test_add_server_health_check_failure**: 验证健康检查失败时的处理

**关键验证点**:
- 服务器配置正确加载
- 健康检查机制正常工作
- 服务器状态正确维护

### 2. 工具发现 (TestToolDiscovery)

- **test_discover_tools_from_server**: 从单个服务器发现工具
- **test_discover_tools_caching**: 验证工具发现缓存机制
- **test_discover_tools_from_nonexistent_server**: 错误处理
- **test_discover_all_tools**: 从多个服务器发现工具

**关键验证点**:
- 工具列表正确检索
- 缓存机制有效运作
- 错误处理正确

### 3. 工具注册 (TestToolRegistration)

- **test_register_single_tool**: 注册单个工具到ToolRegistry
- **test_register_tool_category_inference**: 自动推断工具类别
  - 文件操作 → FILE_SYSTEM
  - 数据库操作 → DATABASE
  - Web操作 → WEB
- **test_register_tool_risk_level_inference**: 自动推断风险级别
  - 读操作 → LOW
  - 写操作 → MEDIUM
  - 删除操作 → HIGH
- **test_discover_and_register_tools**: 发现并注册工具

**关键验证点**:
- 工具正确转换为ToolSchema
- 元数据正确设置
- 标签正确合并

### 4. 多服务器场景 (TestMultiServerScenario)

- **test_multiple_servers_initialization**: 初始化多个服务器
- **test_discover_and_register_all_servers**: 从所有服务器发现并注册工具

**关键验证点**:
- 多个服务器可以并行管理
- 工具不会冲突
- 统计信息正确聚合

### 5. 工具执行 (TestToolExecution)

- **test_execute_tool_success**: 成功执行工具
- **test_execute_tool_with_error**: 工具执行错误处理

**关键验证点**:
- 工具调用正确传递参数
- 返回值正确处理
- 错误正确捕获

### 6. 错误恢复 (TestErrorRecovery)

- **test_server_connection_retry**: 连接重试机制
- **test_remove_server**: 移除服务器
- **test_remove_nonexistent_server**: 移除不存在的服务器

**关键验证点**:
- 重试逻辑正常工作
- 资源正确清理
- 错误状态正确处理

### 7. MCP管理器集成 (TestMCPManagerIntegration)

- **test_manager_initialization_with_config**: 使用配置文件初始化
- **test_manager_health_check**: 健康检查功能
- **test_manager_get_stats**: 统计信息收集

**关键验证点**:
- 配置文件正确加载
- 健康检查聚合多个服务器状态
- 统计信息准确

### 8. 资源清理 (TestResourceCleanup)

- **test_close_all_servers**: 关闭所有服务器连接
- **test_manager_shutdown**: 管理器关闭流程
- **test_manager_shutdown_with_health_check_task**: 关闭带有后台任务的管理器

**关键验证点**:
- 所有连接正确关闭
- 后台任务正确取消
- 资源完全释放

### 9. 端到端流程 (TestEndToEndFlow)

- **test_complete_mcp_workflow**: 完整的单服务器工作流
  1. 创建发现器
  2. 添加服务器
  3. 发现工具
  4. 注册工具
  5. 验证工具属性
  6. 清理资源

- **test_multi_server_complete_workflow**: 完整的多服务器工作流
  1. 初始化多个服务器
  2. 发现所有工具
  3. 验证统计信息
  4. 清理所有资源

**关键验证点**:
- 完整流程无错误执行
- 所有中间步骤正确
- 最终状态符合预期

## 运行测试

### 运行所有MCP集成测试

```bash
pytest tests/integration/test_mcp_e2e.py -v
```

### 运行特定测试类

```bash
pytest tests/integration/test_mcp_e2e.py::TestMCPServerConnection -v
```

### 运行特定测试用例

```bash
pytest tests/integration/test_mcp_e2e.py::TestEndToEndFlow::test_complete_mcp_workflow -v
```

### 运行带有标记的测试

```bash
pytest tests/integration/test_mcp_e2e.py -m mcp -v
```

### 运行并生成覆盖率报告

```bash
pytest tests/integration/test_mcp_e2e.py --cov=backend.app.core.mcp --cov-report=html
```

## 测试依赖

### 必需的包

- `pytest>=7.0` - 测试框架
- `pytest-asyncio>=0.21.0` - 异步测试支持
- `pytest-cov>=4.0` - 覆盖率报告
- `pytest-timeout>=2.1` - 测试超时控制
- `httpx>=0.24.0` - HTTP客户端（用于MCP客户端）
- `pydantic>=2.0` - 数据验证
- `pyyaml>=6.0` - YAML配置解析

### 安装依赖

```bash
pip install pytest pytest-asyncio pytest-cov pytest-timeout httpx pydantic pyyaml
```

## Mock策略

### MockMCPServer

提供完整的模拟MCP服务器实现，包括：

- 工具列表管理
- 工具调用模拟
- 健康检查
- 调用历史记录

### AsyncMock

使用`unittest.mock.AsyncMock`模拟异步操作：

- `MCPClient.list_tools()`
- `MCPClient.call_tool()`
- `MCPClient.health_check()`
- `MCPClient.close()`

### Patch

使用`unittest.mock.patch`替换实际的MCP客户端创建：

```python
with patch("backend.app.core.mcp.discovery.MCPClient", return_value=mock_client):
    # 测试代码
```

## 测试数据

### 默认工具集

MockMCPServer提供三个默认工具：

1. **read_file** - 文件读取工具
   - 输入: path (string)
   - 输出: 文件内容 (string)
   - 风险级别: LOW

2. **write_file** - 文件写入工具
   - 输入: path, content (strings)
   - 输出: 成功标志 (boolean)
   - 风险级别: MEDIUM

3. **search_web** - Web搜索工具
   - 输入: query (string)
   - 输出: 搜索结果数组 (array)
   - 风险级别: LOW

## 关键测试模式

### 异步测试

所有测试使用`@pytest.mark.asyncio`装饰器：

```python
@pytest.mark.asyncio
async def test_example(self):
    result = await some_async_function()
    assert result is not None
```

### Fixture使用

```python
@pytest_asyncio.fixture
async def tool_registry():
    registry = ToolRegistry()
    yield registry
```

### Mock验证

```python
mock_client.call_tool.assert_called_once()
mock_client.close.assert_called_once()
```

## 扩展测试

### 添加新的测试场景

1. 创建新的测试类继承自`object`
2. 添加`@pytest.mark.asyncio`装饰器
3. 使用现有的fixtures
4. 遵循命名约定`test_*`

### 添加新的Mock工具

在`MockMCPServer._default_tools()`中添加新工具定义：

```python
{
    "name": "new_tool",
    "description": "Tool description",
    "input_schema": {...},
    "output_schema": {...},
    "tags": ["tag1", "tag2"],
}
```

## 故障排除

### 异步测试失败

确保：
- 使用`@pytest.mark.asyncio`装饰器
- 使用`await`调用异步函数
- pytest-asyncio已安装

### Mock不工作

检查：
- patch路径是否正确
- mock对象是否正确配置
- 是否使用了`AsyncMock`而不是`MagicMock`

### 超时问题

调整pytest.ini中的timeout值或使用`@pytest.mark.timeout(seconds)`

## 性能考虑

- 所有测试使用模拟对象，不涉及网络调用
- 测试执行时间通常< 1秒
- 可以并行运行多个测试

## 持续集成

在CI/CD管道中运行：

```bash
pytest tests/integration/test_mcp_e2e.py -v --cov=backend.app.core.mcp --cov-report=xml
```

## 相关文件

- `backend/app/core/mcp/manager.py` - MCP管理器
- `backend/app/core/mcp/discovery.py` - 工具发现
- `backend/app/core/mcp/client.py` - MCP客户端
- `backend/app/core/tool_registry.py` - 工具注册表
- `config/mcp_servers.example.yaml` - 配置示例
