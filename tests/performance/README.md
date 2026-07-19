# X-Agent 性能测试套件

完整的性能和压力测试框架，用于评估X-Agent系统的性能、容量和稳定性。

## 目录

- [快速开始](#快速开始)
- [测试类型](#测试类型)
- [运行测试](#运行测试)
- [生成报告](#生成报告)
- [性能指标](#性能指标)
- [优化建议](#优化建议)

## 快速开始

### 安装依赖

```bash
pip install pytest pytest-asyncio aiohttp psutil asyncpg
```

### 运行所有测试

```bash
python tests/performance/run_tests.py --suite all
```

### 运行特定测试套件

```bash
# 性能基准测试
python tests/performance/run_tests.py --suite benchmark

# 负载测试
python tests/performance/run_tests.py --suite load

# 压力测试
python tests/performance/run_tests.py --suite stress

# 稳定性测试
python tests/performance/run_tests.py --suite stability

# 瓶颈分析
python tests/performance/run_tests.py --suite bottleneck
```

## 测试类型

### 1. 性能基准测试 (test_benchmarks.py)

建立系统在标准条件下的性能基线。

**测试场景**:
- 健康检查端点: 1000请求，50并发
- 列表代理端点: 500请求，25并发
- 并发请求: 10-200并发级别

**关键指标**:
- 平均响应时间
- P95/P99响应时间
- 吞吐量 (RPS)
- 错误率

**运行方式**:
```bash
pytest tests/performance/test_benchmarks.py -m benchmark -v
```

### 2. 负载测试 (test_load.py)

评估系统在不同负载条件下的表现。

**测试场景**:
- 正常负载: 100用户，60秒
- 高负载: 1000用户，60秒
- 峰值负载: 5000用户，30秒
- 持续负载: 500用户，300秒
- 渐进式负载: 0-5000用户，300秒

**关键指标**:
- 吞吐量
- 错误率
- 响应时间分布
- 用户体验指标

**运行方式**:
```bash
pytest tests/performance/test_load.py -m load_test -v
```

### 3. 压力测试 (test_stress.py)

找到系统的破裂点和极限。

**测试场景**:
- 系统破裂点: 逐步增加用户数直到系统失败
- 资源耗尽: 10000用户，60秒
- 大数据量: 10-100MB数据，100请求
- 极限并发: 20000用户，30秒

**关键指标**:
- 破裂点用户数
- 最大吞吐量
- 资源耗尽点
- 故障模式

**运行方式**:
```bash
pytest tests/performance/test_stress.py -m stress_test -v
```

### 4. 稳定性测试 (test_stability.py)

评估系统的长期稳定性和可靠性。

**测试场景**:
- 长时间运行: 100用户，5分钟（演示）
- 内存泄漏检测: 1000次迭代
- 资源清理: 50个循环
- 错误恢复: 1000请求，10%错误注入

**关键指标**:
- 内存增长
- 内存泄漏检测
- 错误恢复率
- 资源稳定性

**运行方式**:
```bash
pytest tests/performance/test_stability.py -m stability_test -v
```

### 5. 瓶颈分析 (test_bottleneck_analysis.py)

识别系统中的性能瓶颈。

**分析类型**:
- CPU瓶颈: 使用cProfile分析
- 内存瓶颈: 使用tracemalloc分析
- IO瓶颈: 监控读写速率
- 网络瓶颈: 测试响应时间
- 数据库瓶颈: 分析查询性能

**关键指标**:
- 瓶颈类型
- 严重程度
- 优化建议

**运行方式**:
```bash
pytest tests/performance/test_bottleneck_analysis.py -m bottleneck_analysis -v
```

## 运行测试

### 基本命令

```bash
# 运行所有性能测试
pytest tests/performance/ -v

# 运行特定标记的测试
pytest tests/performance/ -m benchmark -v

# 运行特定文件
pytest tests/performance/test_benchmarks.py -v

# 运行特定测试类
pytest tests/performance/test_benchmarks.py::TestAPIBenchmark -v

# 运行特定测试方法
pytest tests/performance/test_benchmarks.py::TestAPIBenchmark::test_health_check_benchmark -v
```

### 高级选项

```bash
# 显示打印输出
pytest tests/performance/ -v -s

# 生成HTML报告
pytest tests/performance/ -v --html=report.html --self-contained-html

# 生成JUnit XML报告
pytest tests/performance/ -v --junit-xml=report.xml

# 并行运行测试
pytest tests/performance/ -v -n auto

# 显示最慢的10个测试
pytest tests/performance/ -v --durations=10

# 在第一个失败时停止
pytest tests/performance/ -v -x

# 显示本地变量
pytest tests/performance/ -v -l
```

### 使用测试运行器

```bash
# 运行所有测试套件
python tests/performance/run_tests.py --suite all --output-dir reports

# 运行特定套件
python tests/performance/run_tests.py --suite benchmark --output-dir reports

# 自定义输出目录
python tests/performance/run_tests.py --suite all --output-dir /path/to/reports
```

## 生成报告

### 自动生成报告

```bash
# 运行测试并自动生成报告
python tests/performance/run_tests.py --suite all

# 报告位置: performance_reports/
```

### 手动生成报告

```python
from tests.performance.report_generator import PerformanceReportGenerator

# 创建报告生成器
generator = PerformanceReportGenerator("X-Agent")

# 添加测试结果
generator.add_benchmark_results({...})
generator.add_load_test_results([...])
generator.add_stress_test_results([...])

# 生成报告
generator.generate_html_report('report.html')
generator.generate_json_report('report.json')
generator.generate_markdown_report('report.md')
```

### 报告格式

- **HTML报告**: 交互式可视化报告
- **JSON报告**: 机器可读的结构化数据
- **Markdown报告**: 文本格式的详细报告

## 性能指标

### 关键性能指标 (KPI)

| 指标 | 目标值 | 警告值 | 严重值 |
|------|-------|-------|-------|
| 平均响应时间 | < 100ms | 100-500ms | > 500ms |
| P95响应时间 | < 200ms | 200-1000ms | > 1000ms |
| P99响应时间 | < 300ms | 300-1500ms | > 1500ms |
| 吞吐量 | > 500 RPS | 200-500 RPS | < 200 RPS |
| 错误率 | < 1% | 1-5% | > 5% |
| 内存增长 | < 50MB | 50-200MB | > 200MB |
| CPU使用率 | < 50% | 50-80% | > 80% |

### 性能等级

- **优秀 (A)**: 所有指标都在目标值以内
- **良好 (B)**: 大部分指标在目标值以内
- **一般 (C)**: 部分指标在警告值范围
- **差 (D)**: 多个指标在严重值以上
- **极差 (F)**: 系统无法正常运行

## 优化建议

### 立即执行（高优先级）

1. **数据库查询优化**
   - 添加索引到频繁查询的列
   - 优化N+1查询问题
   - 预计性能提升: 30-50%

2. **实现缓存层**
   - 使用Redis缓存热数据
   - 缓存API响应
   - 预计性能提升: 40-60%

3. **连接池优化**
   - 调整数据库连接池大小
   - 实现连接复用
   - 预计性能提升: 20-30%

### 短期执行（中优先级）

1. **异步处理**
   - 使用异步IO
   - 实现后台任务队列
   - 预计性能提升: 25-35%

2. **HTTP优化**
   - 启用gzip压缩
   - 实现HTTP缓存
   - 预计性能提升: 15-25%

### 长期执行（低优先级）

1. **架构优化**
   - 实现微服务架构
   - 使用消息队列
   - 预计性能提升: 50-100%

2. **扩展性改进**
   - 实现水平扩展
   - 使用负载均衡
   - 预计容量提升: 200-300%

## 配置文件

### pytest.ini

```ini
[pytest]
testpaths = tests/performance
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    benchmark: mark test as benchmark test
    load_test: mark test as load test
    stress_test: mark test as stress test
    stability_test: mark test as stability test
    bottleneck_analysis: mark test as bottleneck analysis
asyncio_mode = auto
```

### conftest.py

性能测试夹具和配置在 `conftest.py` 中定义。

## 常见问题

### Q: 如何修改测试参数？

A: 编辑相应的测试文件，修改测试方法中的参数。例如：

```python
result = await tester.run_load_test(
    endpoint='/api/v1/health',
    num_users=100,  # 修改用户数
    duration_seconds=60,  # 修改持续时间
)
```

### Q: 如何添加新的测试场景？

A: 在相应的测试文件中添加新的测试方法。例如：

```python
@pytest.mark.load_test
async def test_custom_scenario(self):
    tester = LoadTester()
    result = await tester.run_load_test(...)
```

### Q: 如何集成到CI/CD流程？

A: 在CI/CD配置中添加性能测试步骤：

```yaml
- name: Run Performance Tests
  run: python tests/performance/run_tests.py --suite all
```

### Q: 如何处理测试失败？

A: 检查测试日志和报告，识别失败原因，然后：
1. 检查系统配置
2. 检查网络连接
3. 检查数据库连接
4. 查看详细的错误信息

## 相关文档

- [性能测试报告](PERFORMANCE_TEST_REPORT.md)
- [性能优化指南](../docs/PERFORMANCE_OPTIMIZATION.md)
- [容量规划指南](../docs/CAPACITY_PLANNING.md)

## 支持

如有问题或建议，请联系性能测试团队。

---

**最后更新**: 2026-05-28
**版本**: 1.0.0
