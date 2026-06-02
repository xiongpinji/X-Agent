# X-Agent 端到端测试执行指南

**版本**: 1.0  
**日期**: 2026-05-28  
**作者**: E2E Test Team

---

## 1. 快速开始

### 1.1 环境准备

```bash
# 克隆项目
git clone <project-repo>
cd X-Agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### 1.2 运行测试

```bash
# 运行所有端到端测试
pytest tests/e2e/ -v

# 运行特定测试类别
pytest tests/e2e/test_sync_e2e.py -v          # 同步测试
pytest tests/e2e/test_functional_e2e.py -v    # 功能测试
pytest tests/e2e/test_offline_e2e.py -v       # 离线测试
pytest tests/e2e/test_performance_security_e2e.py -v  # 性能和安全测试

# 运行特定测试用例
pytest tests/e2e/test_sync_e2e.py::TestSyncLocalToCloud::test_single_record_sync -v

# 生成覆盖率报告
pytest tests/e2e/ --cov=backend --cov-report=html --cov-report=term-missing

# 生成 JUnit XML 报告
pytest tests/e2e/ --junit-xml=test-results.xml

# 并行运行测试
pytest tests/e2e/ -n auto
```

---

## 2. 测试执行计划

### 2.1 第一周：单元和集成测试

**目标**: 验证核心模块功能

```bash
# 同步模块测试
pytest tests/e2e/test_sync_e2e.py::TestSyncLocalToCloud -v
pytest tests/e2e/test_sync_e2e.py::TestSyncCloudToMobile -v

# 功能模块测试
pytest tests/e2e/test_functional_e2e.py::TestAuthentication -v
pytest tests/e2e/test_functional_e2e.py::TestTaskManagement -v
pytest tests/e2e/test_functional_e2e.py::TestWorkflowOrchestration -v
```

**预期结果**: 通过率 >= 95%

### 2.2 第二周：离线和冲突测试

**目标**: 验证离线功能和冲突处理

```bash
# 离线测试
pytest tests/e2e/test_offline_e2e.py::TestOfflineDataOperations -v
pytest tests/e2e/test_offline_e2e.py::TestNetworkRecoverySynchronization -v
pytest tests/e2e/test_offline_e2e.py::TestConflictResolution -v

# 冲突测试
pytest tests/e2e/test_sync_e2e.py::TestSyncConflicts -v
```

**预期结果**: 通过率 >= 90%

### 2.3 第三周：性能测试

**目标**: 验证性能指标

```bash
# 同步延迟测试
pytest tests/e2e/test_performance_security_e2e.py::TestSyncPerformance -v

# 大数据量测试
pytest tests/e2e/test_performance_security_e2e.py::TestBulkSyncPerformance -v

# 并发测试
pytest tests/e2e/test_performance_security_e2e.py::TestConcurrentSync -v
```

**预期结果**: 
- 单条记录同步延迟 < 100ms
- 批量同步延迟 < 500ms
- 并发吞吐 > 1000 req/s

### 2.4 第四周：安全测试

**目标**: 验证安全机制

```bash
# 加密测试
pytest tests/e2e/test_performance_security_e2e.py::TestEncryption -v

# 认证测试
pytest tests/e2e/test_performance_security_e2e.py::TestAuthentication -v

# 审计日志测试
pytest tests/e2e/test_performance_security_e2e.py::TestAuditLogging -v
```

**预期结果**: 通过率 100%

### 2.5 第五周：回归测试

**目标**: 验证所有功能

```bash
# 完整回归测试
pytest tests/e2e/ -v --tb=short

# 生成最终报告
pytest tests/e2e/ --cov=backend --cov-report=html --junit-xml=final-report.xml
```

**预期结果**: 通过率 >= 98%

---

## 3. 测试数据准备

### 3.1 本地测试数据

```python
# tests/e2e/fixtures.py
import pytest

@pytest.fixture
def test_user():
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    }

@pytest.fixture
def test_task():
    return {
        "title": "Test Task",
        "description": "Test Description",
        "status": "pending"
    }

@pytest.fixture
def test_workflow():
    return {
        "name": "Test Workflow",
        "description": "Test Workflow Description",
        "nodes": [],
        "edges": []
    }
```

### 3.2 测试数据集

- **小数据集**: 10-100 条记录
- **中数据集**: 1K-10K 条记录
- **大数据集**: 100K-1M 条记录

---

## 4. 持续集成配置

### 4.1 GitHub Actions

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    
    - name: Run E2E tests
      run: |
        pytest tests/e2e/ -v --cov=backend --junit-xml=test-results.xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        files: ./coverage.xml
    
    - name: Upload test results
      if: always()
      uses: actions/upload-artifact@v2
      with:
        name: test-results
        path: test-results.xml
```

### 4.2 GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - test

e2e_tests:
  stage: test
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - pip install -r requirements-test.txt
    - pytest tests/e2e/ -v --cov=backend --junit-xml=test-results.xml
  artifacts:
    reports:
      junit: test-results.xml
    paths:
      - htmlcov/
```

---

## 5. 缺陷管理

### 5.1 缺陷报告模板

```markdown
## 缺陷报告

**缺陷 ID**: [自动生成]
**测试用例**: TC-XXX-XXX
**严重级别**: Critical / High / Medium / Low
**状态**: New / Assigned / Fixed / Verified / Closed

### 描述
[缺陷描述]

### 复现步骤
1. [步骤 1]
2. [步骤 2]
3. [步骤 3]

### 预期结果
[预期结果]

### 实际结果
[实际结果]

### 环境信息
- OS: [操作系统]
- Python: [Python 版本]
- 数据库: [数据库版本]

### 附件
[截图、日志等]
```

### 5.2 缺陷优先级

| 级别 | 描述 | 处理时间 |
|------|------|---------|
| Critical | 系统崩溃、数据丢失、安全漏洞 | 立即 |
| High | 功能不可用、数据不一致 | 24 小时 |
| Medium | 功能部分不可用、性能下降 | 3 天 |
| Low | 边界情况、优化建议 | 1 周 |

---

## 6. 性能基准

### 6.1 同步性能

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| 单条记录延迟 | < 100ms | - | 待测 |
| 批量同步延迟 | < 500ms | - | 待测 |
| 大文件同步 | < 2s | - | 待测 |
| 1K 记录同步 | < 1s | - | 待测 |
| 10K 记录同步 | < 5s | - | 待测 |
| 100K 记录同步 | < 30s | - | 待测 |

### 6.2 并发性能

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| 10 并发 | > 100 req/s | - | 待测 |
| 50 并发 | > 500 req/s | - | 待测 |
| 100 并发 | > 1000 req/s | - | 待测 |
| 500 并发 | > 5000 req/s | - | 待测 |

### 6.3 资源使用

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| CPU 使用率 | < 80% | - | 待测 |
| 内存使用率 | < 80% | - | 待测 |
| 网络带宽 | < 100 Mbps | - | 待测 |
| 磁盘 I/O | < 1000 IOPS | - | 待测 |

---

## 7. 测试报告

### 7.1 日报

每日生成测试执行日报，包括：
- 执行的测试数量
- 通过/失败/跳过的测试
- 新发现的缺陷
- 性能指标

### 7.2 周报

每周生成测试总结报告，包括：
- 周测试统计
- 缺陷趋势
- 性能趋势
- 建议和改进

### 7.3 最终报告

项目完成时生成最终测试报告，包括：
- 总体测试覆盖率
- 缺陷统计
- 性能评估
- 质量评分

---

## 8. 故障排查

### 8.1 常见问题

**Q: 测试超时**
```bash
# 增加超时时间
pytest tests/e2e/ --timeout=600
```

**Q: 网络连接失败**
```bash
# 检查网络配置
ping localhost
# 检查服务状态
curl http://localhost:8000/health
```

**Q: 数据库连接失败**
```bash
# 检查数据库服务
psql -U postgres -d xagent -c "SELECT 1"
```

### 8.2 调试技巧

```bash
# 显示详细输出
pytest tests/e2e/ -vv

# 显示打印语句
pytest tests/e2e/ -s

# 在失败时进入调试器
pytest tests/e2e/ --pdb

# 显示最慢的 10 个测试
pytest tests/e2e/ --durations=10
```

---

## 9. 最佳实践

### 9.1 测试编写

1. **单一职责**: 每个测试只测试一个功能
2. **清晰命名**: 使用描述性的测试名称
3. **独立性**: 测试之间不应该有依赖
4. **可重复性**: 测试应该能够重复运行
5. **快速执行**: 测试应该快速执行

### 9.2 测试维护

1. **定期更新**: 随着代码变化更新测试
2. **删除过时测试**: 删除不再相关的测试
3. **重构测试**: 提取公共代码到 fixtures
4. **文档化**: 为复杂测试添加注释

### 9.3 测试覆盖

1. **正常路径**: 测试正常的业务流程
2. **边界情况**: 测试边界值和特殊情况
3. **错误处理**: 测试错误和异常处理
4. **性能**: 测试性能和可扩展性

---

## 10. 联系方式

- **测试负责人**: [待填]
- **技术支持**: [待填]
- **问题反馈**: [待填]

---

**文档版本历史**

| 版本 | 日期 | 作者 | 变更 |
|------|------|------|------|
| 1.0 | 2026-05-28 | E2E Test Team | 初始版本 |

