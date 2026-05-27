"""
X-Agent 集成测试执行指南

本文件提供了运行集成测试套件的完整说明
"""

# ============================================================================
# 测试执行指南
# ============================================================================

## 前置条件

### 1. 环境设置

```bash
# 克隆项目
cd "D:\AI编程库\项目库\进行中的项目\X-Agent 原创内核计划\X-Agent 原创内核计划"

# 创建虚拟环境
python -m venv venv
source venv/Scripts/activate  # Windows
# 或
source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -e ".[dev,test]"
```

### 2. 启动依赖服务

```bash
# PostgreSQL (用于追踪和审计)
docker run -d \
  --name xagent-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:15

# Qdrant (用于向量存储)
docker run -d \
  --name xagent-qdrant \
  -p 6333:6333 \
  qdrant/qdrant

# Redis (用于缓存)
docker run -d \
  --name xagent-redis \
  -p 6379:6379 \
  redis:7
```

### 3. 配置环境变量

```bash
# .env 文件
export PYTHONPATH=.
export TEST_ENV=integration
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/xagent
export QDRANT_URL=http://localhost:6333
export REDIS_URL=redis://localhost:6379
export LANGFUSE_PUBLIC_KEY=test-key
export LANGFUSE_SECRET_KEY=test-secret
```

---

## 测试执行

### 1. 运行端到端集成测试

```bash
# 运行所有端到端测试
pytest tests/test_integration_e2e.py -v -s

# 运行特定测试
pytest tests/test_integration_e2e.py::test_full_agent_workflow -v -s
pytest tests/test_integration_e2e.py::test_multi_agent_collaboration -v -s
pytest tests/test_integration_e2e.py::test_filesystem_operations -v -s
pytest tests/test_integration_e2e.py::test_browser_automation -v -s
pytest tests/test_integration_e2e.py::test_memory_system -v -s
pytest tests/test_integration_e2e.py::test_system_interactions -v -s
pytest tests/test_integration_e2e.py::test_error_handling -v -s
pytest tests/test_integration_e2e.py::test_data_consistency -v -s
pytest tests/test_integration_e2e.py::test_performance_baseline -v -s
```

### 2. 运行性能压力测试

```bash
# 运行所有性能测试
pytest tests/test_performance_stress.py -v -s

# 运行特定性能测试
pytest tests/test_performance_stress.py::test_concurrent_agent_requests -v -s
pytest tests/test_performance_stress.py::test_parallel_tool_calls -v -s
pytest tests/test_performance_stress.py::test_memory_scale -v -s
pytest tests/test_performance_stress.py::test_long_running_stability -v -s
```

### 3. 生成覆盖率报告

```bash
# 生成HTML覆盖率报告
pytest tests/test_integration_e2e.py tests/test_performance_stress.py \
  --cov=backend \
  --cov-report=html \
  --cov-report=term-missing

# 查看报告
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
```

### 4. 并行执行测试

```bash
# 安装pytest-xdist
pip install pytest-xdist

# 并行执行测试
pytest tests/test_integration_e2e.py tests/test_performance_stress.py \
  -n auto \
  -v
```

### 5. 生成详细测试报告

```bash
# 生成JUnit XML报告
pytest tests/test_integration_e2e.py tests/test_performance_stress.py \
  --junit-xml=test-results.xml \
  -v

# 生成HTML报告
pip install pytest-html
pytest tests/test_integration_e2e.py tests/test_performance_stress.py \
  --html=report.html \
  --self-contained-html \
  -v
```

---

## 测试场景详解

### 场景1: 完整Agent执行流程

**文件**: `tests/test_integration_e2e.py::test_full_agent_workflow`

**验证内容**:
- Agent初始化
- 上下文管理
- 记忆存储和检索
- 审计日志记录
- 追踪事件记录

**预期结果**: 所有步骤成功完成

**执行时间**: ~5秒

---

### 场景2: 多代理协作

**文件**: `tests/test_integration_e2e.py::test_multi_agent_collaboration`

**验证内容**:
- 3个并行Agent创建
- 并行任务执行
- 记忆共享
- 协作事件记录

**预期结果**: 所有Agent成功执行，记忆正确共享

**执行时间**: ~10秒

---

### 场景3: 文件系统操作

**文件**: `tests/test_integration_e2e.py::test_filesystem_operations`

**验证内容**:
- 工作区创建
- 目录结构创建
- 文件读写
- 权限验证

**预期结果**: 所有文件操作成功

**执行时间**: ~2秒

---

### 场景4: 浏览器自动化

**文件**: `tests/test_integration_e2e.py::test_browser_automation`

**验证内容**:
- 浏览器会话管理
- 网络监控
- 元素操作
- 控制台日志捕获

**预期结果**: 所有操作成功记录

**执行时间**: ~3秒

---

### 场景5: 记忆系统

**文件**: `tests/test_integration_e2e.py::test_memory_system`

**验证内容**:
- 三层记忆存储
- 混合查询
- 记忆合并
- 关系管理

**预期结果**: 所有记忆操作成功

**执行时间**: ~8秒

---

### 场景6: 系统间交互

**文件**: `tests/test_integration_e2e.py::test_system_interactions`

**验证内容**:
- Agent + 上下文管理
- Agent + 工具调用
- Agent + 记忆系统
- 工具 + 文件系统
- 浏览器 + 网络监控
- 任务 + 流式输出

**预期结果**: 所有集成点正常工作

**执行时间**: ~10秒

---

### 场景7: 错误处理

**文件**: `tests/test_integration_e2e.py::test_error_handling`

**验证内容**:
- 网络错误处理
- 超时错误处理
- 权限错误处理
- 资源错误处理
- 并发冲突处理
- 数据一致性错误处理

**预期结果**: 所有错误正确捕获

**执行时间**: ~3秒

---

### 场景8: 数据一致性

**文件**: `tests/test_integration_e2e.py::test_data_consistency`

**验证内容**:
- 三层记忆一致性
- 并发写入一致性
- 缓存一致性

**预期结果**: 所有数据保持一致

**执行时间**: ~15秒

---

### 场景9: 性能基准

**文件**: `tests/test_integration_e2e.py::test_performance_baseline`

**验证内容**:
- 100条记忆存储性能
- 50条并发存储性能

**预期结果**: 性能指标达到预期

**执行时间**: ~30秒

---

## 性能压力测试详解

### 压力测试1: 并发Agent请求 (100)

**文件**: `tests/test_performance_stress.py::test_concurrent_agent_requests`

**测试参数**:
- 并发Agent数: 100
- 每个Agent操作: 记忆存储 + 事件记录
- 预期成功率: ≥95%

**性能指标**:
- 总耗时: < 30秒
- 平均耗时: < 300ms
- 吞吐量: > 3 req/s

**执行时间**: ~30秒

---

### 压力测试2: 工具并行调用 (1000)

**文件**: `tests/test_performance_stress.py::test_parallel_tool_calls`

**测试参数**:
- 总调用数: 1000
- 工具类型: 10种
- 每个调用执行时间: 1ms
- 预期成功率: ≥95%

**性能指标**:
- 总耗时: < 30秒
- 平均耗时: < 30ms
- 吞吐量: > 30 calls/s

**执行时间**: ~30秒

---

### 压力测试3: 记忆系统规模 (10000)

**文件**: `tests/test_performance_stress.py::test_memory_scale`

**测试参数**:
- 总记忆数: 10000
- 分批大小: 100
- 查询样本: 1000

**性能指标**:
- 存储耗时: < 60秒
- 存储速率: > 150 items/s
- 查询耗时: < 10秒
- 查询速率: > 100 queries/s

**执行时间**: ~60秒

---

### 压力测试4: 长时间运行稳定性

**文件**: `tests/test_performance_stress.py::test_long_running_stability`

**测试参数**:
- 运行时间: 30秒
- 并发任务数: 10
- 每个任务间隔: 10ms

**性能指标**:
- 总迭代次数: > 30000
- 平均迭代次数: > 3000
- 吞吐量: > 1000 ops/s

**执行时间**: ~30秒

---

## 故障排查

### 问题1: 数据库连接失败

**症状**: `psycopg.OperationalError: could not connect to server`

**解决方案**:
```bash
# 检查PostgreSQL是否运行
docker ps | grep postgres

# 重启PostgreSQL
docker restart xagent-postgres

# 检查连接字符串
echo $DATABASE_URL
```

---

### 问题2: Qdrant连接失败

**症状**: `qdrant_client.http.exceptions.UnexpectedResponse`

**解决方案**:
```bash
# 检查Qdrant是否运行
docker ps | grep qdrant

# 重启Qdrant
docker restart xagent-qdrant

# 检查连接URL
echo $QDRANT_URL
```

---

### 问题3: 测试超时

**症状**: `pytest.PytestUnraisableExceptionWarning: TimeoutError`

**解决方案**:
```bash
# 增加超时时间
pytest tests/test_integration_e2e.py --timeout=300 -v

# 或在pytest.ini中配置
[pytest]
timeout = 300
```

---

### 问题4: 内存不足

**症状**: `MemoryError` 或 `OSError: [Errno 12] Cannot allocate memory`

**解决方案**:
```bash
# 减少并发数
pytest tests/test_performance_stress.py -n 2 -v

# 或运行单个测试
pytest tests/test_performance_stress.py::test_memory_scale -v
```

---

## 测试结果分析

### 查看测试日志

```bash
# 查看详细日志
pytest tests/test_integration_e2e.py -v -s --log-cli-level=DEBUG

# 保存日志到文件
pytest tests/test_integration_e2e.py -v -s --log-file=test.log
```

### 分析性能指标

```bash
# 运行性能测试并输出详细指标
pytest tests/test_performance_stress.py -v -s --tb=short
```

### 生成对比报告

```bash
# 运行两次测试并对比
pytest tests/test_integration_e2e.py -v --benchmark-only
pytest tests/test_integration_e2e.py -v --benchmark-compare
```

---

## 持续集成配置

### GitHub Actions

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      qdrant:
        image: qdrant/qdrant
        ports:
          - 6333:6333
      
      redis:
        image: redis:7
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev,test]"
      
      - name: Run integration tests
        run: |
          pytest tests/test_integration_e2e.py -v --cov=backend
      
      - name: Run performance tests
        run: |
          pytest tests/test_performance_stress.py -v
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 最佳实践

### 1. 测试隔离

- 每个测试应该独立运行
- 使用临时目录和数据库
- 清理测试数据

### 2. 性能测试

- 在稳定的环境中运行
- 多次运行取平均值
- 记录系统资源使用情况

### 3. 错误处理

- 捕获所有异常
- 记录详细的错误信息
- 提供清晰的错误消息

### 4. 文档维护

- 更新测试文档
- 记录已知问题
- 维护故障排查指南

---

## 相关文件

- `tests/test_integration_e2e.py` - 端到端集成测试
- `tests/test_performance_stress.py` - 性能压力测试
- `INTEGRATION_TEST_REPORT.md` - 集成测试报告
- `pyproject.toml` - 项目配置

---

**最后更新**: 2026-05-27
