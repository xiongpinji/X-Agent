# LLM 提示工程框架和监控系统

## 概述

X-Agent的LLM框架提供了完整的提示工程、A/B测试、监控和评估系统，用于优化和管理大型语言模型的使用。

## 核心组件

### 1. 提示工程框架 (prompt_engineering.py)

提示工程框架提供了模板管理、版本控制和优化建议。

#### 主要功能

- **提示模板系统**: 创建和管理可重用的提示模板
- **变量替换**: 支持动态变量替换和格式化
- **版本管理**: 跟踪提示的所有版本和变更
- **Few-shot示例**: 管理和组织示例用于上下文学习
- **优化建议**: 自动生成提示优化建议

#### 使用示例

```python
from backend.app.core.prompt_engineering import PromptEngineering, PromptType

# 初始化框架
pe = PromptEngineering()

# 创建模板
template = pe.create_template(
    name="Classification",
    content="Classify the following text as positive or negative: {text}",
    prompt_type=PromptType.USER,
    tags=["classification", "sentiment"]
)

# 格式化模板
result = template.format(text="This is great!")

# 创建新版本
version = pe.create_version(
    template.template_id,
    content="Classify the sentiment: {text}",
    changes="Improved clarity"
)

# 激活版本
pe.activate_version(template.template_id, 1)

# 添加Few-shot示例
pe.add_few_shot_example(
    template.template_id,
    input_text="This is amazing",
    output_text="positive",
    difficulty="easy"
)

# 使用示例格式化
prompt = pe.format_with_examples(
    template.template_id,
    example_count=3,
    text="This product is excellent"
)
```

### 2. A/B测试系统 (llm_ab_testing.py)

A/B测试系统支持多版本提示对比、自动流量分配和统计显著性检验。

#### 主要功能

- **多版本对比**: 同时测试多个提示版本
- **自动流量分配**: 支持等分、加权、多臂老虎机等策略
- **统计显著性检验**: 自动计算p值和效应大小
- **性能指标**: 跟踪延迟、成本、用户满意度等
- **赢家确定**: 基于综合指标自动选择最佳版本

#### 使用示例

```python
from backend.app.core.llm_ab_testing import ABTestingSystem, VariantType, TrafficAllocationStrategy

# 初始化系统
ab = ABTestingSystem()

# 创建实验
experiment = ab.create_experiment(
    name="Prompt Optimization",
    objective="improve_accuracy",
    duration_days=7,
    traffic_strategy=TrafficAllocationStrategy.EQUAL
)

# 添加变体
control = experiment.add_variant(
    name="Control",
    variant_type=VariantType.CONTROL,
    config={"version": 1}
)

treatment = experiment.add_variant(
    name="Treatment",
    variant_type=VariantType.TREATMENT,
    config={"version": 2}
)

# 启动实验
experiment.start()

# 分配用户到变体
variant = ab.assign_variant(experiment.experiment_id, "user123")

# 记录指标
ab.record_metric(experiment.experiment_id, variant.variant_id, "latency_ms", 150.0)
ab.record_success(experiment.experiment_id, variant.variant_id)

# 运行统计测试
test_result = ab.run_statistical_test(experiment.experiment_id)

# 确定赢家
winner = ab.determine_winner(experiment.experiment_id)
```

### 3. LLM监控系统 (llm_monitoring.py)

监控系统跟踪LLM调用的性能、成本和质量指标。

#### 主要功能

- **性能监控**: 延迟、吞吐量、缓存命中率
- **成本追踪**: 按模型、提供商、用户分组的成本统计
- **错误率监控**: 自动检测和报告错误
- **告警系统**: 基于规则的自动告警
- **聚合分析**: 按小时/天/周聚合指标

#### 使用示例

```python
from backend.app.core.llm_monitoring import LLMMonitoring, MetricType, AlertSeverity

# 初始化监控
mon = LLMMonitoring()

# 记录指标
metric = mon.record_metric(
    metric_type=MetricType.LATENCY,
    value=150.0,
    model_name="gpt-4",
    provider="openai"
)

# 记录成本
cost = mon.record_cost(
    model_name="gpt-4",
    provider="openai",
    input_tokens=100,
    output_tokens=50,
    input_price_per_1k=0.03,
    output_price_per_1k=0.06
)

# 创建告警规则
rule = mon.create_alert_rule(
    name="High Latency",
    metric_type=MetricType.LATENCY,
    condition="greater_than",
    threshold=5000.0,
    severity=AlertSeverity.WARNING
)

# 获取性能摘要
summary = mon.get_performance_summary(hours=24)
# {
#   "avg_latency_ms": 150.0,
#   "error_rate": 0.01,
#   "throughput_rps": 10.5,
#   "cache_hit_rate": 0.75
# }

# 获取成本摘要
cost_summary = mon.get_cost_summary(hours=24)
# {
#   "total_cost_usd": 25.50,
#   "total_tokens": 50000,
#   "by_provider": {...},
#   "by_model": {...}
# }

# 获取告警
alerts = mon.get_alerts(resolved=False, hours=24)
```

### 4. LLM评估系统 (llm_evaluation.py)

评估系统用于评估LLM响应的质量和正确性。

#### 主要功能

- **自动评估**: 相关性、连贯性、完整性、安全性、流畅性
- **人工评估**: 支持人工评分和反馈
- **评估数据集**: 创建和管理测试用例
- **评估运行**: 批量评估和报告生成
- **质量指标**: 多维度质量评分

#### 使用示例

```python
from backend.app.core.llm_evaluation import LLMEvaluation, EvaluationMethod

# 初始化评估系统
ev = LLMEvaluation()

# 记录响应
response = ev.record_response(
    prompt="What is 2+2?",
    response="The answer is 4",
    model_name="gpt-4",
    provider="openai"
)

# 评估响应
evaluation = ev.evaluate_response(
    response.response_id,
    method=EvaluationMethod.AUTOMATED
)

# 创建评估数据集
dataset = ev.create_dataset(
    name="Math Questions",
    description="Basic math questions"
)

# 添加测试用例
ev.add_test_case(
    dataset.dataset_id,
    prompt="What is 2+2?",
    expected_output="4"
)

# 创建评估运行
run = ev.create_evaluation_run(
    dataset.dataset_id,
    model_name="gpt-4",
    provider="openai"
)

# 完成运行
ev.complete_run(run.run_id)

# 获取报告
report = ev.get_evaluation_report(run.run_id)
```

### 5. 集成LLM管理器 (llm_manager.py)

LLMManager整合了所有子系统，提供统一的接口。

#### 主要功能

- **工作流设置**: 一键设置完整的优化工作流
- **综合报告**: 跨系统的统计和分析
- **仪表板数据**: 为前端仪表板导出数据
- **优化建议**: 基于指标的自动建议

#### 使用示例

```python
from backend.app.core.llm_manager import LLMManager

# 初始化管理器
manager = LLMManager(storage_path="/data/llm")

# 设置提示优化工作流
workflow = manager.setup_prompt_optimization_workflow(
    template_name="Classification",
    template_content="Classify: {text}",
    test_cases=[
        {"prompt": "Great product", "expected_output": "positive"},
        {"prompt": "Terrible service", "expected_output": "negative"}
    ]
)

# 设置A/B测试
ab_test = manager.setup_ab_test_for_prompts(
    experiment_name="Prompt v2 Test",
    template_id=workflow["template_id"],
    variant_configs=[
        {"name": "Control", "version": 1},
        {"name": "Treatment", "version": 2}
    ]
)

# 设置监控告警
alerts = manager.setup_monitoring_alerts()

# 获取综合报告
report = manager.get_comprehensive_report()

# 获取仪表板数据
dashboard = manager.export_metrics_for_dashboard()

# 获取优化建议
recommendations = manager.get_optimization_recommendations()
```

## API端点 (llm_api.py)

### 提示工程端点

- `POST /api/prompts/templates` - 创建模板
- `GET /api/prompts/templates/{id}` - 获取模板
- `GET /api/prompts/templates` - 列出模板
- `POST /api/prompts/templates/{id}/versions` - 创建版本
- `GET /api/prompts/templates/{id}/versions` - 列出版本
- `POST /api/prompts/templates/{id}/versions/{version}/activate` - 激活版本

### A/B测试端点

- `POST /api/experiments` - 创建实验
- `GET /api/experiments/{id}` - 获取实验
- `GET /api/experiments` - 列出实验
- `POST /api/experiments/{id}/variants` - 添加变体
- `POST /api/experiments/{id}/start` - 启动实验
- `GET /api/experiments/{id}/metrics` - 获取指标
- `POST /api/experiments/{id}/winner` - 确定赢家

### 监控端点

- `POST /api/metrics` - 记录指标
- `GET /api/metrics` - 获取指标
- `GET /api/performance` - 获取性能摘要
- `GET /api/costs` - 获取成本摘要
- `POST /api/alerts/rules` - 创建告警规则
- `GET /api/alerts` - 获取告警

### 评估端点

- `POST /api/responses` - 记录响应
- `POST /api/responses/{id}/evaluate` - 评估响应
- `POST /api/datasets` - 创建数据集
- `GET /api/datasets` - 列出数据集
- `POST /api/datasets/{id}/test-cases` - 添加测试用例
- `POST /api/evaluation-runs` - 创建评估运行
- `GET /api/evaluation-runs/{id}/report` - 获取报告

### 仪表板端点

- `GET /api/dashboard/report` - 综合报告
- `GET /api/dashboard/metrics` - 仪表板指标
- `GET /api/dashboard/recommendations` - 优化建议

## 工作流示例

### 完整的提示优化工作流

```python
from backend.app.core.llm_manager import LLMManager

manager = LLMManager()

# 1. 设置优化工作流
workflow = manager.setup_prompt_optimization_workflow(
    template_name="Customer Support",
    template_content="You are a helpful customer support agent. {context}",
    test_cases=[...]
)

# 2. 设置A/B测试
ab_test = manager.setup_ab_test_for_prompts(
    experiment_name="Support Prompt v2",
    template_id=workflow["template_id"],
    variant_configs=[
        {"name": "Current", "version": 1},
        {"name": "Improved", "version": 2}
    ]
)

# 3. 设置监控
manager.setup_monitoring_alerts()

# 4. 运行评估
eval_result = manager.run_evaluation_on_dataset(
    dataset_id=workflow["dataset_id"],
    model_name="gpt-4",
    provider="openai",
    responses=[...]
)

# 5. 获取结果
report = manager.get_comprehensive_report()
recommendations = manager.get_optimization_recommendations()
```

## 监控指标

### 性能指标

- **延迟 (Latency)**: 响应时间（毫秒）
- **吞吐量 (Throughput)**: 每秒请求数
- **错误率 (Error Rate)**: 失败请求的百分比
- **缓存命中率 (Cache Hit Rate)**: 缓存命中的百分比

### 成本指标

- **总成本**: 按时间段的总成本
- **按模型成本**: 按模型分组的成本
- **按提供商成本**: 按提供商分组的成本
- **单位成本**: 每1000个token的成本

### 质量指标

- **准确性 (Accuracy)**: 正确响应的百分比
- **相关性 (Relevance)**: 响应与提示的相关程度
- **连贯性 (Coherence)**: 响应的逻辑连贯性
- **完整性 (Completeness)**: 响应的完整程度
- **安全性 (Safety)**: 响应的安全程度

## 告警规则

系统支持以下告警条件：

- `greater_than`: 指标大于阈值
- `less_than`: 指标小于阈值
- `equals`: 指标等于阈值

告警严重级别：

- `INFO`: 信息性告警
- `WARNING`: 警告级别
- `CRITICAL`: 严重问题

## 存储

所有数据都以JSONL格式存储在磁盘上，支持以下文件：

- `templates.jsonl` - 提示模板
- `versions.jsonl` - 模板版本
- `examples.jsonl` - Few-shot示例
- `experiments.jsonl` - A/B测试实验
- `assignments.jsonl` - 用户变体分配
- `metrics.jsonl` - 监控指标
- `costs.jsonl` - 成本数据
- `alerts.jsonl` - 告警记录
- `responses.jsonl` - LLM响应
- `evaluations.jsonl` - 评估结果
- `datasets.jsonl` - 评估数据集
- `runs.jsonl` - 评估运行

## 最佳实践

1. **定期评估**: 定期运行评估以跟踪质量变化
2. **监控成本**: 设置成本告警以控制支出
3. **A/B测试**: 在部署前进行A/B测试验证改进
4. **版本管理**: 保持清晰的版本历史和变更记录
5. **示例管理**: 定期审查和更新Few-shot示例
6. **告警配置**: 根据业务需求配置适当的告警规则

## 性能考虑

- 指标存储限制为最近10,000条记录
- 成本数据限制为最近10,000条记录
- 告警限制为最近1,000条记录
- 定期清理过期数据以保持性能

## 扩展性

系统设计支持以下扩展：

- 自定义评估指标
- 自定义告警规则
- 集成外部监控系统
- 自定义流量分配策略
- 集成机器学习模型进行优化建议
