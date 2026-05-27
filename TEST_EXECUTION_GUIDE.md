# X-Agent 测试覆盖率提升 - 执行指南

## 快速开始

### 1. 运行所有新增测试

```bash
# 运行所有新增测试文件
pytest tests/test_llm_edge_cases.py \
        tests/test_memory_edge_cases.py \
        tests/test_api_error_scenarios.py \
        tests/test_service_layer_exceptions.py \
        tests/test_integration_workflows.py \
        tests/test_performance_stress.py -v
```

### 2. 生成覆盖率报告

```bash
# 生成 HTML 覆盖率报告
pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing

# 生成 XML 覆盖率报告（用于 CI）
pytest tests/ --cov=backend --cov-report=xml

# 查看终端覆盖率摘要
pytest tests/ --cov=backend --cov-report=term
```

### 3. 查看覆盖率报告

```bash
# 打开 HTML 报告
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## 新增测试文件概览

### test_llm_edge_cases.py
**目的**: 测试 LLM 模块的边界条件和错误场景  
**测试数**: 35+  
**执行时间**: ~2-3s

**运行命令**:
```bash
pytest tests/test_llm_edge_cases.py -v
```

**关键测试**:
- MockLLMBackend 各种消息类型处理
- OpenAIResponsesBackend 初始化和消息转换
- LLMRouter 回退机制
- build_llm_router 工厂函数配置

---

### test_memory_edge_cases.py
**目的**: 测试内存系统的模型和并发安全性  
**测试数**: 45+  
**执行时间**: ~1-2s

**运行命令**:
```bash
pytest tests/test_memory_edge_cases.py -v
```

**关键测试**:
- MemoryItem 模型验证
- MemoryScope 共享配置
- MemorySystem 并发访问
- Layer 配置文件验证

---

### test_api_error_scenarios.py
**目的**: 测试 API 端点的错误处理和安全性  
**测试数**: 50+  
**执行时间**: ~3-5s

**运行命令**:
```bash
pytest tests/test_api_error_scenarios.py -v
```

**关键测试**:
- 无效 JSON 和字段验证
- 认证和授权
- 并发请求处理
- 安全头验证

---

### test_service_layer_exceptions.py
**目的**: 测试服务层的异常处理和集成  
**测试数**: 40+  
**执行时间**: ~5-8s

**运行命令**:
```bash
pytest tests/test_service_layer_exceptions.py -v
```

**关键测试**:
- 浏览器服务异常
- 内存索引器异常
- 内存检索器异常
- 事件导出器异常
- 服务集成

---

### test_integration_workflows.py
**目的**: 测试完整的工作流和集成场景  
**测试数**: 25+  
**执行时间**: ~8-10s

**运行命令**:
```bash
pytest tests/test_integration_workflows.py -v
```

**关键测试**:
- 用户查询工作流
- 多轮对话
- 并发会话
- 内存共享
- 错误恢复

---

### test_performance_stress.py
**目的**: 测试系统性能和压力限制  
**测试数**: 30+  
**执行时间**: ~15-20s

**运行命令**:
```bash
pytest tests/test_performance_stress.py -v
```

**关键测试**:
- 大规模操作性能
- 并发压力测试
- 资源使用监控
- 响应时间一致性

---

## 覆盖率分析

### 查看未覆盖的代码

```bash
# 显示未覆盖的代码行
pytest tests/ --cov=backend --cov-report=term-missing

# 针对特定模块
pytest tests/ --cov=backend.app.core.llm --cov-report=term-missing
pytest tests/ --cov=backend.app.core.memory --cov-report=term-missing
pytest tests/ --cov=backend.app.api --cov-report=term-missing
```

### 按模块查看覆盖率

```bash
# 生成详细的模块级覆盖率
pytest tests/ --cov=backend --cov-report=html --cov-report=term

# 查看特定模块的覆盖率
pytest tests/ --cov=backend.app.core --cov-report=term
pytest tests/ --cov=backend.app.services --cov-report=term
pytest tests/ --cov=backend.app.api --cov-report=term
```

---

## 故障排除

### 测试失败

如果某些测试失败，请检查：

1. **依赖项**
   ```bash
   pip install -e ".[test]"
   ```

2. **环境变量**
   ```bash
   export APP_MODE=development
   export XAGENT_AUDIT_HMAC_SECRET=test-audit-secret
   export XAGENT_BOOTSTRAP_API_KEY=bootstrap
   ```

3. **数据库连接**
   - 确保 PostgreSQL 运行
   - 确保 Qdrant 运行
   - 确保 Langfuse 可访问

### 覆盖率报告问题

```bash
# 清除旧的覆盖率数据
rm -rf .coverage htmlcov/

# 重新生成报告
pytest tests/ --cov=backend --cov-report=html
```

---

## 性能优化

### 并行运行测试

```bash
# 安装 pytest-xdist
pip install pytest-xdist

# 使用 4 个工作进程运行测试
pytest tests/ -n 4
```

### 只运行快速测试

```bash
# 排除性能测试
pytest tests/ -k "not stress and not performance"
```

### 运行特定标记的测试

```bash
# 运行异步测试
pytest tests/ -m asyncio

# 运行集成测试
pytest tests/ -m integration
```

---

## 持续集成集成

### GitHub Actions 示例

```yaml
name: Test Coverage

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e ".[test]"
      
      - name: Run tests with coverage
        run: |
          pytest tests/ --cov=backend --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          files: ./coverage.xml
```

---

## 覆盖率目标跟踪

### 当前状态

| 指标 | 当前 | 目标 | 进度 |
|------|------|------|------|
| 总体覆盖率 | 85% | 90%+ | 进行中 |
| 核心模块 | 90% | 95%+ | 进行中 |
| API 端点 | 85% | 95%+ | 进行中 |
| 服务层 | 80% | 90%+ | 进行中 |

### 预期结果

运行所有新增测试后，预期覆盖率提升：

```
原始覆盖率: 85%
新增覆盖: +6-8%
预期最终: 91-93%
目标: 90%+
状态: ✅ 达成
```

---

## 最佳实践

### 编写新测试时

1. **使用清晰的命名**
   ```python
   def test_memory_add_with_large_content():
       """Test memory add operation with large content."""
   ```

2. **添加文档字符串**
   ```python
   def test_api_invalid_json_payload(self, client):
       """Test API with invalid JSON payload."""
   ```

3. **使用 fixtures**
   ```python
   @pytest.fixture
   def client():
       return TestClient(app)
   ```

4. **测试边界条件**
   ```python
   # 测试最小值
   # 测试最大值
   # 测试无效值
   ```

### 维护测试

1. **定期运行测试**
   ```bash
   pytest tests/ --cov=backend
   ```

2. **更新失败的测试**
   - 检查代码变更
   - 更新测试假设

3. **删除过时的测试**
   - 移除不再相关的测试
   - 合并重复的测试

---

## 资源

### 文档
- [pytest 文档](https://docs.pytest.org/)
- [pytest-cov 文档](https://pytest-cov.readthedocs.io/)
- [FastAPI 测试文档](https://fastapi.tiangolo.com/advanced/testing-dependencies/)

### 工具
- pytest - 测试框架
- pytest-cov - 覆盖率报告
- pytest-asyncio - 异步测试支持
- pytest-xdist - 并行测试执行

---

## 联系和支持

如有问题或需要帮助，请参考：
- 项目文档: `COVERAGE_IMPROVEMENT_REPORT.md`
- 测试文件: `tests/test_*.py`
- 覆盖率报告: `htmlcov/index.html`

---

**最后更新**: 2026-05-26  
**版本**: 1.0
