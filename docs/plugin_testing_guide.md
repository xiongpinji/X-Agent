# X-Agent 插件测试指南

## 目录

1. [测试概述](#测试概述)
2. [单元测试](#单元测试)
3. [集成测试](#集成测试)
4. [性能测试](#性能测试)
5. [安全测试](#安全测试)
6. [测试工具](#测试工具)
7. [最佳实践](#最佳实践)
8. [CI/CD 集成](#cicd-集成)

## 测试概述

### 测试金字塔

```
        /\
       /  \        E2E 测试 (10%)
      /────\
     /      \      集成测试 (30%)
    /────────\
   /          \    单元测试 (60%)
  /____________\
```

### 测试类型

1. **单元测试**: 测试单个函数或方法
2. **集成测试**: 测试多个组件的交互
3. **性能测试**: 测试性能指标
4. **安全测试**: 测试安全漏洞
5. **E2E 测试**: 端到端测试

## 单元测试

### 测试框架设置

创建 `tests/conftest.py`:

```python
"""Pytest configuration"""

import pytest
import asyncio
from xagent_my_plugin import MyPlugin

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def plugin():
    """Create plugin instance"""
    return MyPlugin()

@pytest.fixture
async def initialized_plugin(plugin):
    """Create initialized plugin"""
    await plugin.initialize()
    yield plugin
    await plugin.cleanup()
```

### 测试插件

创建 `tests/test_plugin.py`:

```python
"""Plugin tests"""

import pytest
from xagent_my_plugin import MyPlugin

class TestPluginMetadata:
    """Test plugin metadata"""
    
    def test_plugin_name(self, plugin):
        assert plugin.name == "my-plugin"
    
    def test_plugin_version(self, plugin):
        assert plugin.version == "0.1.0"
    
    def test_plugin_description(self, plugin):
        assert plugin.description is not None

class TestPluginLifecycle:
    """Test plugin lifecycle"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, plugin):
        await plugin.initialize()
        assert plugin.enabled is True
    
    @pytest.mark.asyncio
    async def test_registration(self, initialized_plugin):
        await initialized_plugin.register()
        assert len(initialized_plugin.tools) > 0
    
    @pytest.mark.asyncio
    async def test_enable_disable(self, initialized_plugin):
        await initialized_plugin.enable()
        assert initialized_plugin.enabled is True
        
        await initialized_plugin.disable()
        assert initialized_plugin.enabled is False
    
    @pytest.mark.asyncio
    async def test_cleanup(self, plugin):
        await plugin.initialize()
        await plugin.cleanup()
        # Verify cleanup
```

### 测试工具

创建 `tests/test_tools.py`:

```python
"""Tool tests"""

import pytest
from xagent_my_plugin import MyTool

class TestMyTool:
    """Test MyTool"""
    
    @pytest.fixture
    def tool(self):
        return MyTool()
    
    def test_tool_metadata(self, tool):
        assert tool.name == "my_tool"
        assert tool.description is not None
    
    def test_tool_parameters(self, tool):
        assert "input" in tool.parameters
        assert tool.parameters["input"]["required"] is True
    
    @pytest.mark.asyncio
    async def test_tool_execution(self, tool):
        result = await tool.execute(input="test")
        assert result["status"] == "success"
        assert "result" in result
    
    @pytest.mark.asyncio
    async def test_tool_validation(self, tool):
        # Test valid input
        assert tool.validate(input="test") is True
        
        # Test invalid input
        with pytest.raises(ValueError):
            await tool.execute(input="")
    
    @pytest.mark.asyncio
    async def test_tool_error_handling(self, tool):
        with pytest.raises(ValueError):
            await tool.execute(input=None)
```

## 集成测试

### 测试插件集成

创建 `tests/test_integration.py`:

```python
"""Integration tests"""

import pytest
from xagent import XAgent
from xagent_my_plugin import MyPlugin

class TestPluginIntegration:
    """Test plugin integration with X-Agent"""
    
    @pytest.fixture
    async def agent(self):
        agent = XAgent()
        yield agent
        await agent.shutdown()
    
    @pytest.mark.asyncio
    async def test_plugin_loading(self, agent):
        plugin = MyPlugin()
        await agent.load_plugin(plugin)
        
        assert plugin.name in agent.plugins
    
    @pytest.mark.asyncio
    async def test_tool_execution(self, agent):
        plugin = MyPlugin()
        await agent.load_plugin(plugin)
        
        result = await agent.execute_tool("my_tool", input="test")
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_plugin_unloading(self, agent):
        plugin = MyPlugin()
        await agent.load_plugin(plugin)
        await agent.unload_plugin(plugin.name)
        
        assert plugin.name not in agent.plugins
```

### 测试集成

创建 `tests/test_integrations.py`:

```python
"""Integration tests"""

import pytest
from xagent_my_plugin import MyServiceIntegration

class TestServiceIntegration:
    """Test service integration"""
    
    @pytest.fixture
    async def integration(self):
        integration = MyServiceIntegration()
        await integration.connect()
        yield integration
        await integration.disconnect()
    
    @pytest.mark.asyncio
    async def test_connection(self, integration):
        assert integration.is_connected() is True
    
    @pytest.mark.asyncio
    async def test_get_data(self, integration):
        result = await integration.execute("get_data")
        assert "data" in result
    
    @pytest.mark.asyncio
    async def test_send_data(self, integration):
        result = await integration.execute("send_data", data={"test": "data"})
        assert result["status"] == "sent"
```

## 性能测试

### 性能基准测试

创建 `tests/test_performance.py`:

```python
"""Performance tests"""

import pytest
import time
from xagent_my_plugin import MyTool

class TestPerformance:
    """Test performance"""
    
    @pytest.fixture
    def tool(self):
        return MyTool()
    
    @pytest.mark.asyncio
    async def test_tool_execution_speed(self, tool):
        """Test tool execution speed"""
        start = time.time()
        
        for _ in range(100):
            await tool.execute(input="test")
        
        elapsed = time.time() - start
        avg_time = elapsed / 100
        
        # Assert average execution time < 100ms
        assert avg_time < 0.1, f"Average execution time: {avg_time}s"
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, tool):
        """Test memory usage"""
        import tracemalloc
        
        tracemalloc.start()
        
        for _ in range(1000):
            await tool.execute(input="test")
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Assert peak memory < 100MB
        assert peak < 100 * 1024 * 1024
```

## 安全测试

### 安全漏洞测试

创建 `tests/test_security.py`:

```python
"""Security tests"""

import pytest
from xagent_my_plugin import MyTool

class TestSecurity:
    """Test security"""
    
    @pytest.fixture
    def tool(self):
        return MyTool()
    
    @pytest.mark.asyncio
    async def test_input_validation(self, tool):
        """Test input validation"""
        # Test SQL injection
        with pytest.raises(ValueError):
            await tool.execute(input="'; DROP TABLE users; --")
        
        # Test XSS
        with pytest.raises(ValueError):
            await tool.execute(input="<script>alert('xss')</script>")
    
    @pytest.mark.asyncio
    async def test_permission_check(self, tool):
        """Test permission check"""
        # Test unauthorized access
        with pytest.raises(PermissionError):
            await tool.execute(input="test", unauthorized=True)
    
    def test_no_hardcoded_secrets(self):
        """Test no hardcoded secrets"""
        import xagent_my_plugin
        import inspect
        
        source = inspect.getsource(xagent_my_plugin)
        
        # Check for common secret patterns
        assert "password=" not in source
        assert "api_key=" not in source
        assert "secret=" not in source
```

## 测试工具

### Pytest 配置

创建 `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    asyncio: marks tests as async
    slow: marks tests as slow
    security: marks tests as security tests
    performance: marks tests as performance tests
```

### 测试覆盖率

```bash
# 运行测试并生成覆盖率报告
pytest --cov=xagent_my_plugin --cov-report=html tests/

# 查看覆盖率报告
open htmlcov/index.html
```

### 测试命令

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_plugin.py

# 运行特定测试类
pytest tests/test_plugin.py::TestPluginMetadata

# 运行特定测试方法
pytest tests/test_plugin.py::TestPluginMetadata::test_plugin_name

# 运行带标记的测试
pytest -m asyncio

# 运行并显示详细输出
pytest -vv

# 运行并在第一个失败处停止
pytest -x

# 运行并显示最慢的 10 个测试
pytest --durations=10
```

## 最佳实践

### 1. 测试命名

```python
# 好的命名
def test_tool_execution_with_valid_input():
    pass

def test_tool_execution_with_invalid_input():
    pass

# 不好的命名
def test_tool():
    pass

def test_1():
    pass
```

### 2. 测试隔离

```python
# 使用 fixture 确保测试隔离
@pytest.fixture
def plugin():
    plugin = MyPlugin()
    yield plugin
    # Cleanup
```

### 3. 异步测试

```python
# 使用 pytest-asyncio
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None
```

### 4. 参数化测试

```python
# 使用参数化测试减少重复代码
@pytest.mark.parametrize("input,expected", [
    ("test1", "result1"),
    ("test2", "result2"),
    ("test3", "result3"),
])
def test_tool_with_multiple_inputs(input, expected):
    result = tool.execute(input)
    assert result == expected
```

### 5. Mock 和 Patch

```python
from unittest.mock import Mock, patch

@patch('xagent_my_plugin.external_service')
def test_tool_with_mock(mock_service):
    mock_service.return_value = {"data": "mocked"}
    result = tool.execute(input="test")
    assert result["data"] == "mocked"
```

## CI/CD 集成

### GitHub Actions

创建 `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    
    - name: Run tests
      run: pytest --cov=xagent_my_plugin --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml
```

### 本地测试

```bash
# 运行所有测试
make test

# 运行测试并生成覆盖率报告
make test-coverage

# 运行安全测试
make test-security

# 运行性能测试
make test-performance
```

---

最后更新: 2026-05-29
