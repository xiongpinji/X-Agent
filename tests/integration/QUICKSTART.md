# MCP集成测试快速参考

## 文件位置

```
tests/
├── __init__.py
├── conftest.py                          # 全局pytest配置
├── integration/
│   ├── __init__.py
│   ├── test_mcp_e2e.py                 # MCP端到端集成测试
│   └── README.md                        # 详细文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install pytest pytest-asyncio pytest-cov httpx pydantic pyyaml
```

### 2. 运行所有测试

```bash
pytest tests/integration/test_mcp_e2e.py -v
```

### 3. 运行特定测试类

```bash
# 测试服务器连接
pytest tests/integration/test_mcp_e2e.py::TestMCPServerConnection -v

# 测试工具发现
pytest tests/integration/test_mcp_e2e.py::TestToolDiscovery -v

# 测试端到端流程
pytest tests/integration/test_mcp_e2e.py::TestEndToEndFlow -v
```

## 测试覆盖的端到端场景

### 场景1: 单服务器完整工作流

```
1. 创建MCP发现器
   ↓
2. 添加MCP服务器（健康检查）
   ↓
3. 发现服务器上的工具
   ↓
4. 将工具注册到ToolRegistry
   ↓
5. 验证工具属性（类别、风险级别、标签）
   ↓
6. 清理资源（关闭连接）
```

**测试用例**: `TestEndToEndFlow::test_complete_mcp_workflow`

### 场景2: 多服务器协调

```
1. 初始化多个MCP服务器
   ↓
2. 并行发现所有服务器的工具
   ↓
3. 注册所有工具到统一的ToolRegistry
   ↓
4. 验证统计信息聚合
   ↓
5. 清理所有资源
```

**测试用例**: `TestEndToEndFlow::test_multi_server_complete_workflow`

### 场景3: 工具执行流程

```
1. 从ToolRegistry获取工具schema
   ↓
2. 调用MCP客户端执行工具
   ↓
3. 处理返回结果
   ↓
4. 记录审计日志
```

**测试用例**: `TestToolExecution::test_execute_tool_success`

### 场景4: 错误恢复

```
1. 服务器连接失败
   ↓
2. 触发重试机制
   ↓
3. 重试成功或最终失败
   ↓
4. 正确清理资源
```

**测试用例**: `TestErrorRecovery::test_server_connection_retry`

## 测试类概览

| 测试类 | 测试数量 | 主要功能 |
|--------|---------|---------|
| TestMCPServerConnection | 3 | 服务器连接和健康检查 |
| TestToolDiscovery | 4 | 工具发现和缓存 |
| TestToolRegistration | 4 | 工具注册和元数据推断 |
| TestMultiServerScenario | 2 | 多服务器管理 |
| TestToolExecution | 2 | 工具调用和执行 |
| TestErrorRecovery | 3 | 错误处理和恢复 |
| TestMCPManagerIntegration | 3 | 管理器集成 |
| TestResourceCleanup | 3 | 资源清理 |
| TestEndToEndFlow | 2 | 完整端到端流程 |

**总计**: 26个测试用例

## 关键验证点

### 服务器连接
- ✓ 服务器配置正确加载
- ✓ 健康检查机制工作
- ✓ 禁用服务器不被添加
- ✓ 连接失败正确处理

### 工具发现
- ✓ 工具列表正确检索
- ✓ 工具缓存有效
- ✓ 多服务器工具不冲突
- ✓ 错误情况正确处理

### 工具注册
- ✓ 工具转换为ToolSchema
- ✓ 类别自动推断（文件、数据库、Web等）
- ✓ 风险级别自动推断（低、中、高）
- ✓ 标签正确合并

### 工具执行
- ✓ 参数正确传递
- ✓ 返回值正确处理
- ✓ 错误正确捕获
- ✓ 审计日志记录

### 资源清理
- ✓ 连接正确关闭
- ✓ 后台任务取消
- ✓ 内存正确释放
- ✓ 状态正确重置

## Mock对象

### MockMCPServer
模拟完整的MCP服务器，包括：
- 工具列表管理
- 工具调用模拟
- 健康检查
- 调用历史

### AsyncMock
模拟异步操作：
- `list_tools()` - 返回工具列表
- `call_tool()` - 执行工具
- `health_check()` - 健康检查
- `close()` - 关闭连接

## 常见问题

### Q: 如何添加新的测试工具？
A: 在`MockMCPServer._default_tools()`中添加工具定义

### Q: 如何测试新的错误场景？
A: 创建新的AsyncMock配置或修改现有mock的返回值

### Q: 如何验证工具属性？
A: 使用`tool_registry.get(tool_name)`获取工具，然后验证其属性

### Q: 如何调试测试失败？
A: 使用`pytest -v -s`查看详细输出，或添加`print()`语句

## 性能指标

- 总测试时间: ~2-3秒
- 平均单个测试: ~100ms
- 无网络调用（全部使用mock）
- 可并行执行

## 集成到CI/CD

```yaml
# GitHub Actions示例
- name: Run MCP Integration Tests
  run: |
    pytest tests/integration/test_mcp_e2e.py \
      -v \
      --cov=backend.app.core.mcp \
      --cov-report=xml \
      --cov-report=term-missing
```

## 相关命令

```bash
# 运行所有测试
pytest tests/integration/test_mcp_e2e.py -v

# 运行并显示打印输出
pytest tests/integration/test_mcp_e2e.py -v -s

# 运行特定标记的测试
pytest tests/integration/test_mcp_e2e.py -m asyncio -v

# 生成覆盖率报告
pytest tests/integration/test_mcp_e2e.py --cov=backend.app.core.mcp --cov-report=html

# 运行并在第一个失败处停止
pytest tests/integration/test_mcp_e2e.py -x

# 运行最后失败的测试
pytest tests/integration/test_mcp_e2e.py --lf

# 并行运行测试（需要pytest-xdist）
pytest tests/integration/test_mcp_e2e.py -n auto
```

## 下一步

1. 运行测试验证MCP模块功能
2. 根据需要扩展测试场景
3. 集成到CI/CD流程
4. 监控测试覆盖率
5. 定期更新测试以适应新功能
